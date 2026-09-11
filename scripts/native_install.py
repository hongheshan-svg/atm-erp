#!/usr/bin/env python3
"""Native Daphne/Nginx launcher; databases remain explicitly managed services."""

import argparse
import ipaddress
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def run(args, **kwargs):
    subprocess.run([str(arg) for arg in args], check=True, **kwargs)


def create_config(path):
    config = {
        "DB_HOST": "127.0.0.1", "DB_PORT": "5432", "DB_NAME": "atm_erp_lean",
        "DB_USER": "atm_erp_lean", "DB_PASSWORD": "CHANGE_ME",
        "REDIS_URL": "redis://127.0.0.1:6379/0",
        "SECRET_KEY": secrets.token_hex(48),
        "ADMIN_PASSWORD": "Lean-" + secrets.token_hex(24),
        "ALLOWED_HOSTS": "localhost,127.0.0.1", "APP_ENVIRONMENT": "production",
        "OTA_AGENT_TOKEN": secrets.token_hex(32),
        "BIND_ADDRESS": "127.0.0.1", "HTTP_PORT": 8080, "APP_PORT": 18001,
        "DATA_DIR": str(ROOT / ".native"), "NGINX_EXECUTABLE": "nginx",
    }
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(config, stream, ensure_ascii=False, indent=2)
    if os.name == "nt":
        identity = subprocess.check_output(["whoami"], text=True).strip()
        run(["icacls", path, "/inheritance:r", "/grant:r", identity + ":F"], stdout=subprocess.DEVNULL)


def load_config(path):
    with path.open(encoding="utf-8-sig") as stream:
        config = json.load(stream)
    for key in ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD", "REDIS_URL",
                "SECRET_KEY", "ADMIN_PASSWORD", "ALLOWED_HOSTS", "DATA_DIR", "NGINX_EXECUTABLE"):
        if not isinstance(config.get(key), str) or not config[key].strip():
            raise ValueError(f"配置缺少 {key}")
    if config["DB_PASSWORD"] == "CHANGE_ME" or len(config["SECRET_KEY"]) < 32:
        raise ValueError("请设置数据库密码和至少 32 字符的 SECRET_KEY")
    if config.get("APP_ENVIRONMENT") != "production":
        raise ValueError("发布安装必须设置 APP_ENVIRONMENT=production")
    if len(config["ADMIN_PASSWORD"]) < 12:
        raise ValueError("管理员密码至少 12 字符")
    if not config["REDIS_URL"].startswith(("redis://", "rediss://")):
        raise ValueError("REDIS_URL 必须为 Redis 服务地址")
    ipaddress.IPv4Address(config["BIND_ADDRESS"])
    for key in ("HTTP_PORT", "APP_PORT"):
        if type(config.get(key)) is not int or not 1024 <= config[key] <= 65535:
            raise ValueError(f"{key} 必须是 1024–65535 的整数")
    if config["HTTP_PORT"] == config["APP_PORT"]:
        raise ValueError("HTTP_PORT 与 APP_PORT 不能相同")
    data = Path(config["DATA_DIR"]).expanduser()
    if not data.is_absolute():
        raise ValueError("DATA_DIR 必须为绝对路径，升级时保持原值")
    return config, data.resolve()


def environment(config, data):
    env = os.environ.copy()
    for key in ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD", "REDIS_URL",
                "SECRET_KEY", "ADMIN_PASSWORD", "ALLOWED_HOSTS", "APP_ENVIRONMENT"):
        env[key] = config[key]
    env.update(DEBUG="false", MEDIA_ROOT=str(data / "uploads"), PYTHONUNBUFFERED="1", PYTHONUTF8="1")
    env['OTA_AGENT_TOKEN'] = config.get('OTA_AGENT_TOKEN', '')
    return env


def python_path(data):
    return data / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def nginx_path(config):
    executable = shutil.which(config["NGINX_EXECUTABLE"])
    if not executable:
        raise ValueError("未找到 Nginx，请安装并配置 NGINX_EXECUTABLE 的完整路径")
    return executable


def quote_path(path):
    value = Path(path).resolve().as_posix()
    if any(char in value for char in ('"', '$', '\n', '\r')):
        raise ValueError("安装路径不能包含双引号、美元符号或换行")
    return '"' + value + '"'


def nginx_config(config, data):
    public = quote_path(data / "www")
    return f'''worker_processes 1;
daemon off;
pid nginx.pid;
error_log logs/nginx-error.log warn;
events {{ worker_connections 1024; }}
http {{
  types {{ text/html html; text/css css; application/javascript js; application/json json;
    image/png png; image/jpeg jpg jpeg; image/svg+xml svg; image/x-icon ico;
    font/woff woff; font/woff2 woff2; }}
  default_type application/octet-stream;
  access_log logs/nginx-access.log;
  server_tokens off;
  client_body_temp_path temp/client;
  proxy_temp_path temp/proxy;
  fastcgi_temp_path temp/fastcgi;
  uwsgi_temp_path temp/uwsgi;
  scgi_temp_path temp/scgi;
  server {{
    listen {config['BIND_ADDRESS']}:{config['HTTP_PORT']};
    root {public};
    client_max_body_size 25m;
    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options DENY always;
    location = / {{ return 302 /erp/; }}
    location = /erp {{ return 301 /erp/; }}
    location = /erp/index.html {{ add_header Cache-Control 'no-cache'; }}
    location /erp/assets/ {{ try_files $uri =404; expires 1y; }}
    location /erp/ {{ try_files $uri $uri/ /erp/index.html; }}
    location /api/ {{
      proxy_pass http://127.0.0.1:{config['APP_PORT']};
      proxy_set_header Host $host;
      proxy_set_header X-Real-IP $remote_addr;
      proxy_set_header X-Forwarded-For $remote_addr;
      proxy_read_timeout 60;
    }}
    location / {{ return 404; }}
  }}
}}
'''


def available_ports(config):
    for host, port in ((config["BIND_ADDRESS"], config["HTTP_PORT"]), ("127.0.0.1", config["APP_PORT"])):
        with socket.socket() as sock:
            # Unix TIME_WAIT after a clean stop is not an active listener.
            # Windows REUSEADDR can steal a live port, so keep exclusive binding there.
            option = socket.SO_EXCLUSIVEADDRUSE if os.name == "nt" else socket.SO_REUSEADDR
            sock.setsockopt(socket.SOL_SOCKET, option, 1)
            sock.bind((host, port))


def check_services(python, env):
    # Ping dependencies before any migration; do not print connection credentials.
    run([python, "-c", "import django; django.setup(); "
         "from django.db import connection; connection.ensure_connection(); "
         "import os,redis; redis.Redis.from_url(os.environ['REDIS_URL']).ping()"],
        cwd=ROOT / "backend", env={**env, "DJANGO_SETTINGS_MODULE": "config.settings"})


def install(config, data):
    nginx = nginx_path(config)
    available_ports(config)
    if not (ROOT / "frontend/dist/index.html").is_file():
        raise ValueError("缺少已构建前端，请使用原生发布包，或先在 frontend 执行 npm ci 和 npm run build")
    data.mkdir(parents=True, exist_ok=True)
    for folder in ("uploads", "logs", "temp/client", "temp/proxy", "www"):
        (data / folder).mkdir(parents=True, exist_ok=True)
    python = python_path(data)
    if not python.exists():
        run([sys.executable, "-m", "venv", data / "venv"])
    if (ROOT / 'INSTALL-MANIFEST.json').exists():
        from release_install import native_dependencies
        dependencies = native_dependencies(ROOT)
    else:
        dependencies = ['--only-binary=:all:', '-r', ROOT / 'backend/requirements.txt']
    run([python, '-m', 'pip', 'install', *dependencies])
    env = environment(config, data)
    check_services(python, env)
    # The project's migrate command enforces the independent-database/schema guard.
    run([python, "manage.py", "migrate", "--noinput"], cwd=ROOT / "backend", env=env)
    run([python, "manage.py", "init_system"], cwd=ROOT / "backend", env=env)
    shutil.copytree(ROOT / "frontend/dist", data / "www/erp", dirs_exist_ok=True)
    (data / "nginx.conf").write_text(nginx_config(config, data), encoding="utf-8")
    run([nginx, "-p", data.as_posix() + "/", "-c", "nginx.conf", "-t"])
    print("安装完成。管理员 admin；首次密码见配置文件 ADMIN_PASSWORD。执行 start 启动。")
    print("访问 /erp/，首次登录自动进入快速安装向导，完成后使用新密码登录即可开单。")


def start(config, data, config_path=None, no_ota=False):
    python = python_path(data)
    if not python.exists() or not (data / "nginx.conf").exists():
        raise ValueError("请先执行 install")
    available_ports(config)
    env = environment(config, data)
    check_services(python, env)
    run([python, "manage.py", "check_schema"], cwd=ROOT / "backend", env=env)
    (data / "nginx.conf").write_text(nginx_config(config, data), encoding="utf-8")
    nginx = [nginx_path(config), "-p", data.as_posix() + "/", "-c", "nginx.conf"]
    run([*nginx, "-t"])
    children = []
    old_handlers = {}
    nonce = secrets.token_hex(16)
    runtime = data / 'native-runtime.json'
    stop_file = data / 'native-stop.txt'

    def heartbeat():
        temporary = data / 'native-runtime.tmp'
        temporary.write_text(json.dumps({'nonce': nonce, 'seen': time.time()}), encoding='utf-8')
        temporary.replace(runtime)
        if stop_file.exists() and stop_file.read_text(encoding='utf-8') == nonce:
            raise KeyboardInterrupt

    def stop_signal(signum, frame):
        raise KeyboardInterrupt

    try:
        heartbeat()
        for sig in (signal.SIGINT, signal.SIGTERM):
            old_handlers[sig] = signal.signal(sig, stop_signal)
        with (data / "logs/daphne.log").open("a", encoding="utf-8") as log:
            children.append(subprocess.Popen([str(python), "-m", "daphne", "-b", "127.0.0.1",
                            "-p", str(config["APP_PORT"]), "config.asgi:application"],
                           cwd=ROOT / "backend", env=env, stdout=log, stderr=log))
            children.append(subprocess.Popen(nginx, cwd=data))
            host = "127.0.0.1" if config["BIND_ADDRESS"] == "0.0.0.0" else config["BIND_ADDRESS"]
            url = f"http://{host}:{config['HTTP_PORT']}"
            for attempt in range(60):
                heartbeat()
                if any(child.poll() is not None for child in children):
                    raise RuntimeError("服务退出，请查看 DATA_DIR/logs")
                try:
                    with urllib.request.urlopen(url + "/api/health/", timeout=2) as response:
                        if response.status == 200:
                            break
                except (OSError, TimeoutError):
                    time.sleep(1)
            else:
                raise RuntimeError("服务未就绪，请查看 DATA_DIR/logs")
            if not no_ota and not os.environ.get('ATM_ERP_OTA_MANAGED'):
                from ota_service import install as install_ota
                install_ota('native', ROOT, config_path or ROOT / 'native-config.json', url)
            print(f"已启动 {url}/erp/；按 Ctrl+C 停止。", flush=True)
            while all(child.poll() is None for child in children):
                heartbeat()
                time.sleep(1)
            raise RuntimeError("服务意外退出，请查看 DATA_DIR/logs")
    except KeyboardInterrupt:
        print("正在停止服务…")
    finally:
        # Quit Nginx workers as well as the master on Windows.
        if len(children) > 1 and children[1].poll() is None:
            subprocess.run([*nginx, "-s", "quit"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for child in reversed(children):
            if child.poll() is None:
                try:
                    if child is children[0]:
                        child.terminate()
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
        for sig, handler in old_handlers.items():
            signal.signal(sig, handler)
        if runtime.exists() and json.loads(runtime.read_text(encoding='utf-8')).get('nonce') == nonce:
            runtime.unlink()
        if stop_file.exists() and stop_file.read_text(encoding='utf-8') == nonce:
            stop_file.unlink()


def stop(config, data):
    runtime = data / 'native-runtime.json'
    if not runtime.exists():
        available_ports(config)
        print('应用未运行。')
        return
    state = json.loads(runtime.read_text(encoding='utf-8'))
    if time.time() - state['seen'] > 15:
        raise ValueError('运行状态已过期，请检查原生进程后手动停止，不能强制终止未知进程')
    (data / 'native-stop.txt').write_text(state['nonce'], encoding='utf-8')
    for _ in range(60):
        if not runtime.exists():
            available_ports(config)
            print('应用已停止。')
            return
        time.sleep(1)
    raise RuntimeError('停止应用超时，升级未继续')


def main():
    # Redirected PowerShell output can otherwise use an ASCII/ANSI code page.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("configure", "install", "start", "stop", "check"))
    parser.add_argument("--config", type=Path, default=ROOT / "native-config.json")
    parser.add_argument('--no-ota', action='store_true', help='仅隔离测试：不注册宿主机升级服务')
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 11):
        parser.error("请使用 Python 3.11")
    try:
        if args.action == "configure":
            create_config(args.config)
            print(f"配置已创建：{args.config}。请填写独立 PostgreSQL 数据库密码和 Redis 地址后执行 install。")
            return
        config, data = load_config(args.config)
        if args.action == "check":
            nginx_path(config)
            check_services(python_path(data), environment(config, data))
            print("PostgreSQL / Redis 连接正常。")
        elif args.action == "install":
            if not config.get('OTA_AGENT_TOKEN'):
                config['OTA_AGENT_TOKEN'] = secrets.token_hex(32)
                with args.config.open('w', encoding='utf-8') as stream:
                    json.dump(config, stream, ensure_ascii=False, indent=2)
            install(config, data)
        elif args.action == "stop":
            stop(config, data)
        else:
            start(config, data, args.config, args.no_ota)
    except (ValueError, OSError, subprocess.CalledProcessError, RuntimeError) as exc:
        print(f"操作失败：{exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
