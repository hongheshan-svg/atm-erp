"""Real native application smoke test against explicitly isolated PostgreSQL/Redis."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--db-port", required=True)
    parser.add_argument("--redis-port", required=True)
    parser.add_argument("--http-port", type=int, default=18480)
    parser.add_argument("--app-port", type=int, default=18481)
    args = parser.parse_args()
    root = args.root.resolve()
    config_path = root / "native-smoke-config.json"
    command = [sys.executable, str(root / "scripts/native_install.py")]
    subprocess.run([*command, "configure", "--config", str(config_path)], check=True)
    config = json.loads(config_path.read_text())
    config.update(DB_PORT=args.db_port, DB_PASSWORD=os.environ["NATIVE_SMOKE_DB_PASSWORD"],
                  REDIS_URL=f"redis://127.0.0.1:{args.redis_port}/0",
                  HTTP_PORT=args.http_port, APP_PORT=args.app_port)
    config_path.write_text(json.dumps(config))
    base = f"http://127.0.0.1:{args.http_port}"

    def request(path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(base + path, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=3) as response:
                return response.status, response.read(), response.headers
        except urllib.error.HTTPError as response:
            return response.code, response.read(), response.headers

    for iteration in range(2):
        # A repeat installation must retain account identity/password and data.
        subprocess.run([*command, "install", "--config", str(config_path)], check=True)
        process = subprocess.Popen([*command, "start", "--config", str(config_path)])
        try:
            for _ in range(90):
                if process.poll() is not None:
                    raise RuntimeError("Native launcher exited before ready")
                try:
                    if request("/api/health/")[0] == 200:
                        break
                except OSError:
                    pass
                time.sleep(1)
            else:
                raise RuntimeError("Native startup timeout")
            status, body, headers = request("/erp/")
            assert status == 200 and b"<html" in body.lower()
            assets = list((root / "frontend/dist/assets").glob("*.js"))
            assert assets
            assert "javascript" in request("/erp/assets/" + assets[0].name)[2]["Content-Type"]
            assert request("/uploads/private.pdf")[0] == 404
            denied_status, denied_body, _ = request("/api/business/projects/")
            assert denied_status == 403, (denied_status, denied_body)
            credentials = {"username": "admin", "password": config["ADMIN_PASSWORD"]}
            status, body, _ = request("/api/auth/login/", credentials)
            assert status == 200, body
            assert json.loads(body)["access"]
            if iteration == 1:
                statuses = [request("/api/auth/login/", {**credentials, "password": "wrong"})[0] for _ in range(12)]
                assert 429 in statuses, "Release login throttle must be enabled"
            print(f"Native installation {iteration + 1}: login, assets, auth and upload protection passed", flush=True)
        finally:
            process.send_signal(signal.SIGTERM)
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            assert process.returncode == 0, process.returncode


if __name__ == "__main__":
    main()
