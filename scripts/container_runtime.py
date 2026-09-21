"""Stable container launcher. OTA replaces application releases, never the host/image."""
import hashlib
import hmac
import json
import os
import re
import subprocess
import sys
from pathlib import Path

DATA = Path(os.environ.get('ERP_RUNTIME_DIR', '/app/runtime'))
BASE = Path('/app')


def version(root):
    text = (root / 'apps/core/version.py').read_text()
    match = re.search(r"VERSION\s*=\s*['\"](\d+\.\d+\.\d+)['\"]", text)
    if not match:
        raise ValueError('无法确认程序版本')
    return tuple(map(int, match[1].split('.')))


def selected():
    pointer = DATA / 'active.json'
    if not pointer.exists():
        return BASE, Path(sys.executable), Path('/var/www/erp')
    name = json.loads(pointer.read_text())['release']
    if not re.fullmatch(r'job-\d+/release/atm-erp-v\d+\.\d+\.\d+-linux-native', name):
        raise ValueError('持久化版本路径无效')
    root = (DATA / name).resolve()
    if not root.is_relative_to(DATA.resolve()):
        raise ValueError('持久化版本路径越界')
    backend = root / 'backend'
    # Keep the persistent version on recreation; a newer base image may move forward only.
    if version(BASE) > version(backend):
        return BASE, Path(sys.executable), Path('/var/www/erp')
    return backend, root / '.venv/bin/python', root / 'frontend/dist'


def journal():
    path = DATA / 'maintenance.json'
    return json.loads(path.read_text()) if path.exists() else {}


def assert_bootable():
    if journal().get('phase') in ('migrating', 'blocked'):
        raise RuntimeError('升级在迁移阶段中断；已阻止旧程序启动。请核对 runtime 卷中的备份与日志，禁止清卷。')


def frontend(path):
    directory = Path('/tmp/erp-www')
    directory.mkdir(exist_ok=True)
    temporary = directory / 'erp.next'
    temporary.unlink(missing_ok=True)
    temporary.symlink_to(path)
    temporary.replace(directory / 'erp')


def initialize():
    DATA.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(DATA, 0o700)
    if os.environ.get('OTA_MODE', 'container') == 'container':
        # Internal capability, deterministic across recreation; never sent to the browser.
        os.environ['OTA_AGENT_TOKEN'] = hmac.new(
            os.environ['SECRET_KEY'].encode(), b'erp-container-ota-v1', hashlib.sha256,
        ).hexdigest()
    assert_bootable()
    backend, python, web = selected()
    for action in (['migrate', '--noinput'], ['init_system']):
        subprocess.run([str(python), 'manage.py', *action], cwd=backend, check=True)
    frontend(web)
    # Prior to migration, stopping/restarting the unchanged program is safe.
    if journal().get('phase') == 'backup':
        (DATA / 'maintenance.json').unlink(missing_ok=True)


def main():
    if sys.argv[1:2] == ['manage']:
        assert_bootable()
        backend, python, _ = selected()
        os.chdir(backend)
        os.execv(str(python), [str(python), 'manage.py', *sys.argv[2:]])
    if sys.argv[1:] == ['serve']:
        assert_bootable()
        backend, python, _ = selected()
        os.chdir(backend)
        os.execv(str(python), [str(python), '-m', 'daphne', '-b', '127.0.0.1', '-p', '8000', 'config.asgi:application'])
    initialize()
    os.execvp(sys.argv[1], sys.argv[1:])


if __name__ == '__main__':
    main()
