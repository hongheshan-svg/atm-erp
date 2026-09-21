#!/usr/bin/env python3
"""Linux application service. Its stable launcher follows successful forward installs."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def managed(data):
    return (data / 'application-service.json').is_file()


def name(data):
    return 'atm-erp-native-' + hashlib.sha256(str(data.resolve()).encode()).hexdigest()[:16] + '.service'


def update(root, config, data):
    previous = json.loads((data / 'application-service.json').read_text()) if managed(data) else {'uid': os.getuid()}
    if previous['uid'] != os.getuid():
        raise ValueError('请使用原安装账户管理原生服务')
    temporary = data / 'application-service.tmp'
    temporary.write_text(json.dumps({'root': str(root.resolve()), 'config': str(config.resolve()), 'uid': previous['uid']}))
    temporary.chmod(0o600)
    temporary.replace(data / 'application-service.json')


def quote(value):
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%').replace('$', '$$').replace('\n', '\\n').replace('\r', '\\r') + '"'


def unit(data, executable, system):
    return ('[Unit]\nDescription=Lean ERP native application\nAfter=network-online.target\n'
            'Wants=network-online.target\n[Service]\nType=simple\n'
            'ExecStart=' + ' '.join(map(quote, [executable, data / 'native_service.py', data])) + '\n'
            'Restart=on-failure\nRestartSec=5\nTimeoutStopSec=45\nUMask=0077\n'
            'StandardOutput=journal\nStandardError=journal\n'
            '[Install]\nWantedBy=' + ('multi-user.target' if system else 'default.target') + '\n')


def control(data, action):
    if sys.platform != 'linux' or not managed(data):
        raise ValueError('未配置 Linux 原生应用服务，请先执行 service-install')
    descriptor = json.loads((data / 'application-service.json').read_text())
    if descriptor['uid'] != os.getuid():
        raise ValueError('请使用原安装账户管理原生服务')
    args = ['systemctl'] + ([] if descriptor['uid'] == 0 else ['--user'])
    subprocess.run([*args, action, name(data)], check=True)


def register(root, config, data):
    if sys.platform != 'linux':
        raise ValueError('service-install 仅支持 Linux systemd')
    if not (data / 'nginx.conf').is_file():
        raise ValueError('请先执行 install')
    # Do not create a second supervisor for an existing foreground application.
    if (data / 'native-runtime.json').exists():
        raise ValueError('应用正在运行或状态未清理，请先停止并核对，再注册服务')
    system = os.getuid() == 0
    target = (Path('/etc/systemd/system') if system else Path.home() / '.config/systemd/user') / name(data)
    target.parent.mkdir(parents=True, exist_ok=True)
    update(root, config, data)
    shutil.copyfile(__file__, data / 'native_service.py')
    target.write_text(unit(data, sys.executable, system))
    args = ['systemctl'] + ([] if system else ['--user'])
    subprocess.run([*args, 'daemon-reload'], check=True)
    if not system:
        subprocess.run(['loginctl', 'enable-linger', str(os.getuid())], check=True)
    subprocess.run([*args, 'enable', '--now', name(data)], check=True)
    print('原生应用服务已注册；请用 service-status 和 check 核对服务及依赖。')


def launch(data):
    descriptor = json.loads((data / 'application-service.json').read_text())
    # exec keeps systemd's main PID equal to the application supervisor; SIGTERM reaches it.
    os.execv(sys.executable, [sys.executable, str(Path(descriptor['root']) / 'scripts/native_install.py'),
                             'start', '--foreground', '--config', descriptor['config']])


if __name__ == '__main__':
    launch(Path(sys.argv[1]).resolve())
