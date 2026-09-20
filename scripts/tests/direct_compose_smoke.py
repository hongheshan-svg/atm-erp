"""Isolated Compose-only install: no installer or host OTA service is invoked."""
import argparse
import json
import secrets
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.package_release import docker_compose


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--image', required=True, help='Locally built test image; never a production project')
    parser.add_argument('--port', type=int, default=18498)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    project = 'erp-compose-smoke-' + secrets.token_hex(5)
    # A local fixture exercises release-shaped Compose; it does not claim a registry pull.
    with tempfile.TemporaryDirectory(prefix=project) as folder:
        folder = Path(folder)
        template = docker_compose((root / 'docker-compose.yml').read_text(),
                                  'ghcr.io/hongheshan-svg/atm-erp@sha256:' + 'a' * 64)
        (folder / 'docker-compose.yml').write_text(template)
        password = 'Smoke-' + secrets.token_hex(20)
        values = {'LEAN_PROJECT_NAME': project, 'LEAN_IMAGE': args.image, 'LEAN_HTTP_PORT': str(args.port),
                  'LEAN_DB_PASSWORD': secrets.token_hex(32), 'LEAN_SECRET_KEY': secrets.token_hex(32),
                  'LEAN_ADMIN_PASSWORD': password}
        env = (root / '.env.example').read_text()
        for key, value in values.items():
            env = '\n'.join(key + '=' + value if line.startswith(key + '=') else line for line in env.split('\n'))
        (folder / '.env').write_text(env)
        (folder / '.env').chmod(0o600)
        compose = ['docker', 'compose', '--project-directory', str(folder)]
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

        def request(path, payload=None, token=None):
            headers = {'Content-Type': 'application/json'}
            if token:
                headers['Authorization'] = 'Bearer ' + token
            req = urllib.request.Request(f'http://127.0.0.1:{args.port}' + path,
                                         data=json.dumps(payload).encode() if payload else None, headers=headers)
            with opener.open(req, timeout=5) as response:
                return json.load(response)

        try:
            subprocess.run([*compose, 'up', '-d', '--no-build', '--pull', 'never', '--wait', '--wait-timeout', '180'], check=True)
            for _ in range(30):
                try:
                    health = request('/api/health/')
                    break
                except OSError:
                    time.sleep(1)
            else:
                raise RuntimeError('Compose-only application did not become healthy')
            login = request('/api/auth/login/', {'username': 'admin', 'password': password})
            for _ in range(20):
                state = request('/api/core/upgrade/', token=login['access'])
                if state['runner']:
                    break
                time.sleep(1)
            assert state['configured'] is True and state['runner']['execution'] == 'container', state
            subprocess.run([*compose, 'up', '-d', '--no-build', '--pull', 'never', '--wait'], check=True)
            assert request('/api/auth/login/', {'username': 'admin', 'password': password})['access']
            print('Compose-only install/repeat start/login and real container OTA heartbeat passed; version=' + health['version'])
        finally:
            subprocess.run([*compose, 'down', '-v'], check=True)  # Only this random isolated project's test volumes.


if __name__ == '__main__':
    main()
