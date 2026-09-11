#!/usr/bin/env python3
"""Install a per-deployment host service; keep Docker privileges outside the app."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import time


def command(args):
    subprocess.run([str(value) for value in args], check=True)


def private_json(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
    temporary.chmod(0o600)
    temporary.replace(path)


def location(mode, config, deployment=None):
    key = hashlib.sha256(f'{mode}:{deployment or config.resolve()}'.encode()).hexdigest()[:16]
    return Path.home() / '.local/share/atm-erp-ota' / key


def fresh(directory, since=0):
    try:
        stamp = json.loads((directory / 'heartbeat.json').read_text())['seen']
        return stamp >= since and 0 <= time.time() - stamp < 30
    except (OSError, ValueError, KeyError, TypeError):
        return False


def service_args(directory):
    return [sys.executable, str(directory / 'ota_service.py'), 'supervise', '--state-dir', str(directory)]


def unit(args, directory):
    # systemd interprets percent specifiers and C-style escapes even in quotes.
    def quote(value):
        return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%').replace('$', '$$').replace('\n', '\\n').replace('\r', '\\r') + '"'
    return ('[Unit]\nDescription=Lean ERP host upgrade executor\nAfter=network-online.target\n'
            '[Service]\nType=simple\nExecStart=' + ' '.join(map(quote, args)) + '\n'
            'Restart=always\nRestartSec=10\nUMask=0077\n'
            '[Install]\nWantedBy=default.target\n')


def register(directory):
    name = 'com.atm-erp.ota.' + hashlib.sha256(str(directory.resolve()).encode()).hexdigest()[:16]
    args = service_args(directory)
    if sys.platform == 'darwin':
        target = Path.home() / 'Library/LaunchAgents' / (name + '.plist')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(plistlib.dumps({
            'Label': name, 'ProgramArguments': args, 'RunAtLoad': True, 'KeepAlive': True,
            'ThrottleInterval': 10, 'WorkingDirectory': str(directory),
            'StandardOutPath': str(directory / 'service.log'),
            'StandardErrorPath': str(directory / 'service.log'),
        }))
        target.chmod(0o600)
        domain = f'gui/{os.getuid()}'
        subprocess.run(['launchctl', 'bootout', domain, str(target)], check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        command(['launchctl', 'bootstrap', domain, target])
        command(['launchctl', 'kickstart', domain + '/' + name])
    elif sys.platform == 'linux':
        system = os.getuid() == 0
        target = (Path('/etc/systemd/system') if system else Path.home() / '.config/systemd/user') / (name + '.service')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(unit(args, directory), encoding='utf-8')
        ctl = ['systemctl'] + ([] if system else ['--user'])
        command([*ctl, 'daemon-reload'])
        command([*ctl, 'enable', '--now', target.name])
        command([*ctl, 'restart', target.name])
        if not system:
            command(['loginctl', 'enable-linger', str(os.getuid())])
    elif sys.platform == 'win32':
        # Task Scheduler runs as the installing user, without storing a password.
        # A one-minute trigger also recovers a terminated supervisor.
        import xml.etree.ElementTree as ET
        ns = 'http://schemas.microsoft.com/windows/2004/02/mit/task'
        ET.register_namespace('', ns)
        def add(parent, tag, value=None, **attrs):
            child = ET.SubElement(parent, '{' + ns + '}' + tag, attrs)
            if value is not None:
                child.text = value
            return child
        task = ET.Element('{' + ns + '}Task', version='1.2')
        triggers = add(task, 'Triggers')
        add(triggers, 'LogonTrigger')
        trigger = add(triggers, 'TimeTrigger')
        repeat = add(trigger, 'Repetition')
        add(repeat, 'Interval', 'PT1M')
        add(trigger, 'StartBoundary', time.strftime('%Y-%m-%dT%H:%M:%S'))
        principals = add(task, 'Principals')
        principal = add(principals, 'Principal', id='Author')
        identity = subprocess.check_output(['whoami'], text=True).strip()
        add(principal, 'UserId', identity)
        add(principal, 'LogonType', 'InteractiveToken')
        add(principal, 'RunLevel', 'LeastPrivilege')
        settings = add(task, 'Settings')
        add(settings, 'MultipleInstancesPolicy', 'IgnoreNew')
        add(settings, 'DisallowStartIfOnBatteries', 'false')
        add(settings, 'StopIfGoingOnBatteries', 'false')
        add(settings, 'ExecutionTimeLimit', 'PT0S')
        actions = add(task, 'Actions', Context='Author')
        execute = add(actions, 'Exec')
        add(execute, 'Command', args[0])
        add(execute, 'Arguments', subprocess.list2cmdline(args[1:]))
        add(execute, 'WorkingDirectory', str(directory))
        target = directory / 'service.xml'
        ET.ElementTree(task).write(target, encoding='utf-16', xml_declaration=True)
        subprocess.run(['schtasks', '/End', '/TN', name], check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        command(['schtasks', '/Create', '/TN', name, '/XML', target, '/F'])
        command(['schtasks', '/Run', '/TN', name])
    else:
        raise ValueError('不支持的宿主机平台')


def install(mode, root, config, url=None, directory=None):
    from ota_runner import config_values
    root, config = root.resolve(), config.resolve()
    values = config_values(config, mode)
    token = values.get('LEAN_OTA_AGENT_TOKEN' if mode == 'docker' else 'OTA_AGENT_TOKEN', '')
    if len(token) < 32:
        raise ValueError('升级密钥缺失；请重新运行当前版本安装器生成配置')
    if url is None:
        host = values.get('LEAN_BIND_ADDRESS' if mode == 'docker' else 'BIND_ADDRESS', '127.0.0.1')
        host = '127.0.0.1' if host == '0.0.0.0' else host
        port = values.get('LEAN_HTTP_PORT' if mode == 'docker' else 'HTTP_PORT', 8080)
        url = f'http://{host}:{port}'
    deployment = values.get('LEAN_PROJECT_NAME', 'atm-erp-lean') if mode == 'docker' else str(Path(values['DATA_DIR']).expanduser().resolve())
    directory = (directory or location(mode, config, deployment)).resolve()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    directory.chmod(0o700)
    if os.name == 'nt':
        identity = subprocess.check_output(['whoami'], text=True).strip()
        command(['icacls', directory, '/inheritance:r', '/grant:r', identity + ':(OI)(CI)F'])
    descriptor = {'mode': mode, 'root': str(root), 'config': str(config), 'url': url, 'deployment': deployment,
                  'token_hash': hashlib.sha256(token.encode()).hexdigest(),
                  'path': os.environ.get('PATH', '')}
    manifest = directory / 'service.json'
    if manifest.exists():
        existing = json.loads(manifest.read_text())
        if any(existing[key] != descriptor[key] for key in ('mode', 'url', 'deployment')):
            raise ValueError('执行器目录属于另一套安装，拒绝覆盖')
        if fresh(directory) and existing.get('token_hash') == descriptor['token_hash']:
            print('升级执行器已连接。', flush=True)
            return directory
    # Never interrupt an active upgrade just because its heartbeat is stale during downtime.
    if (directory / 'state.json').exists():
        state = json.loads((directory / 'state.json').read_text())
        if state.get('inflight'):
            raise ValueError('存在未完成升级，请先核对执行器日志，不能覆盖后台服务')
    private_json(manifest, descriptor)
    shutil.copyfile(__file__, directory / 'ota_service.py')
    started = time.time()
    register(directory)
    for _ in range(60):
        if fresh(directory, started):
            print('升级执行器已自动启动并连接，后台服务已配置。', flush=True)
            return directory
        time.sleep(1)
    raise RuntimeError(f'ERP 已启动，但升级执行器未连接。检查 {directory / "service.log"}')


def supervise(directory):
    descriptor = json.loads((directory / 'service.json').read_text())
    env = {**os.environ, 'PATH': descriptor['path'], 'PYTHONUNBUFFERED': '1', 'ATM_ERP_OTA_MANAGED': '1'}
    while True:
        # The runner persists the new release directory after a successful upgrade.
        state = json.loads((directory / 'state.json').read_text()) if (directory / 'state.json').exists() else {}
        root = Path(state.get('root', descriptor['root']))
        config = state.get('config', descriptor['config'])
        with (directory / 'service.log').open('a', encoding='utf-8') as log:
            subprocess.run([sys.executable, str(root / 'scripts/ota_runner.py'), '--mode', descriptor['mode'],
                            '--root', str(root), '--config', config, '--state-dir', str(directory),
                            '--url', descriptor['url']], env=env, stdout=log, stderr=log, check=False)
        time.sleep(10)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['install', 'supervise'])
    parser.add_argument('--mode', choices=['docker', 'native'])
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--config', type=Path)
    parser.add_argument('--url')
    parser.add_argument('--state-dir', type=Path)
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 11):
        parser.error('安装器需要宿主机 Python 3.11')
    os.umask(0o077)
    if args.action == 'supervise':
        supervise(args.state_dir.resolve())
    else:
        if not args.config or not args.mode:
            parser.error('install requires --mode and --config')
        install(args.mode, args.root, args.config, args.url, args.state_dir)


if __name__ == '__main__':
    main()
