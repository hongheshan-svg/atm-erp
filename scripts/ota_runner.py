#!/usr/bin/env python3
"""Opt-in host OTA runner. Never mount the Docker socket into the ERP app."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import secrets
import shutil
import stat
import subprocess
import sys
import tarfile
import time
import urllib.parse
import urllib.request
import zipfile

REPO = 'hongheshan-svg/atm-erp'
PLATFORM = {'Darwin': 'macos', 'Linux': 'linux', 'Windows': 'windows'}.get(platform.system())
LIMIT = 500_000_000


def atomic_json(path, data):
    temporary = path.with_suffix('.tmp')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
    temporary.replace(path)


def file_hash(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


@contextmanager
def exclusive(path):
    """OS lock releases on crashes; no stale pid guessing or killing other processes."""
    with path.open('a+b') as stream:
        stream.seek(0)
        stream.write(b'0')
        stream.flush()
        stream.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            if os.name == 'nt':
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


def config_values(path, mode):
    if mode == 'native':
        return json.loads(path.read_text(encoding='utf-8-sig'))
    values = {}
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        if line.strip() and not line.lstrip().startswith('#'):
            key, sep, value = line.partition('=')
            if not sep:
                raise ValueError('Invalid environment configuration')
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def trusted_asset(job, mode, host_platform):
    tag = job['target']
    if not re.fullmatch(r'v\d+\.\d+\.\d+', tag):
        raise ValueError('Invalid release version')
    request = urllib.request.Request(f'https://api.github.com/repos/{REPO}/releases/tags/{tag}',
                                     headers={'User-Agent': 'Lean-ERP-host-upgrade'})
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read(2_000_001)
    if len(raw) > 2_000_000:
        raise ValueError('Release metadata too large')
    release = json.loads(raw)
    if release.get('tag_name') != tag or release.get('draft') or release.get('prerelease'):
        raise ValueError('Not a published stable release')
    name = f'atm-erp-{tag}-{host_platform}-{mode}.zip'
    asset = next((asset for asset in release['assets'] if asset['name'] == name), None)
    if not asset:
        raise ValueError('No matching installation package')
    expected = f'https://github.com/{REPO}/releases/download/{tag}/{name}'
    digest = asset.get('digest') or ''
    if (asset.get('browser_download_url') != expected or not re.fullmatch(r'sha256:[a-f0-9]{64}', digest)
            or digest[7:] != job['asset']['sha256'] or not 0 < asset['size'] <= LIMIT):
        raise ValueError('Release package changed or is not verifiable')
    return {'url': expected, 'sha256': digest[7:], 'size': asset['size'], 'name': name}


def download(asset, destination, progress=None):
    digest = hashlib.sha256()
    size = 0
    last_report = 0
    request = urllib.request.Request(asset['url'], headers={'User-Agent': 'Lean-ERP-host-upgrade'})
    with urllib.request.urlopen(request, timeout=60) as response, destination.open('xb') as output:
        while chunk := response.read(1024 * 1024):
            size += len(chunk)
            if size > LIMIT or size > asset['size']:
                raise ValueError('Package size exceeds release metadata')
            digest.update(chunk)
            output.write(chunk)
            if progress and (time.monotonic() - last_report >= 2 or size == asset['size']):
                progress(size, asset['size'])
                last_report = time.monotonic()
    if digest.hexdigest() != asset['sha256'] or size != asset['size']:
        raise ValueError('Package SHA256 mismatch')


def unpack(archive, destination, target, mode, host_platform):
    with zipfile.ZipFile(archive) as bundle:
        entries = bundle.infolist()
        if len(entries) > 20000 or sum(entry.file_size for entry in entries) > 1_000_000_000:
            raise ValueError('Unpacked package too large')
        names = set()
        for entry in entries:
            path = PurePosixPath(entry.filename)
            if (path.is_absolute() or '..' in path.parts or '\\' in entry.filename or ':' in entry.filename
                    or stat.S_ISLNK(entry.external_attr >> 16) or entry.filename in names):
                raise ValueError('Unsafe archive entry')
            names.add(entry.filename)
        roots = {PurePosixPath(entry.filename).parts[0] for entry in entries}
        if len(roots) != 1:
            raise ValueError('Package must contain one root directory')
        bundle.extractall(destination)
        # The service uses umask 077 for credentials and backups. Source files
        # copied into a non-root container must still be readable there.
        # The private parent directory continues to protect the host workspace.
        for entry in entries:
            extracted = destination / entry.filename
            if extracted.is_file():
                extracted.chmod(0o755 if entry.external_attr >> 16 & 0o111 else 0o644)
            for parent in [extracted] if extracted.is_dir() else extracted.parents:
                if parent == destination:
                    break
                parent.chmod(0o755)
    root = destination / roots.pop()
    manifest = json.loads((root / 'INSTALL-MANIFEST.json').read_text(encoding='utf-8'))
    if any(manifest.get(key) != value for key, value in (
            ('version', target), ('mode', mode), ('platform', host_platform))):
        raise ValueError('Package manifest does not match requested upgrade')
    for relative in ('backend/manage.py', 'backend/apps/core/version.py', 'frontend/dist/index.html',
                     'scripts/native_install.py', 'scripts/backup.py', 'docker-compose.yml'):
        if not (root / relative).is_file():
            raise ValueError('Package does not support managed upgrades')
    # Never install a package labelled with a different runtime version.
    expected = re.search(r"VERSION\s*=\s*['\"]([^'\"]+)['\"]", (root / 'backend/apps/core/version.py').read_text())
    if not expected or expected.group(1) != target.lstrip('v'):
        raise ValueError('Runtime version does not match release tag')
    return root


class Runner:
    def __init__(self, args):
        self.mode = args.mode
        self.root = args.root.resolve()
        self.config = args.config.resolve()
        self.directory = args.state_dir.resolve()
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        if os.name != 'nt':
            os.chmod(self.directory, 0o700)
        with exclusive(self.directory / 'runner.lock'):
            self.initialize(args)

    def initialize(self, args):
        self.path = self.directory / 'state.json'
        self.state = json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else {'root': str(self.root), 'pending': []}
        self.state.setdefault('runner_id', secrets.token_hex(16))
        self.root = Path(self.state['root'])
        self.config = Path(self.state.get('config', str(self.config)))
        self.values = config_values(self.config, self.mode)
        self.token = self.values.get('LEAN_OTA_AGENT_TOKEN' if self.mode == 'docker' else 'OTA_AGENT_TOKEN', '')
        if not isinstance(self.token, str) or len(self.token) < 32:
            raise ValueError('先在安装配置中设置至少 32 字符的 OTA 执行器密钥，并重新启动应用使配置生效')
        self.url = args.url.rstrip('/')
        url = urllib.parse.urlsplit(self.url)
        if (url.username or url.password or url.query or url.fragment or url.path
                or (url.scheme != 'https' and not (url.scheme == 'http' and url.hostname in ('127.0.0.1', 'localhost', '::1')))):
            raise ValueError('API URL must be HTTPS or local loopback HTTP, without a path or credentials')
        if self.state.get('url', self.url) != self.url or self.state.get('mode', self.mode) != self.mode:
            raise ValueError('State directory belongs to another deployment')
        self.state.update(url=self.url, mode=self.mode)
        if os.name == 'nt':
            identity = subprocess.check_output(['whoami'], text=True).strip()
            subprocess.run(['icacls', str(self.directory), '/inheritance:r', '/grant:r', identity + ':(OI)(CI)F'],
                           check=True, stdout=subprocess.DEVNULL)
        self.save()

    def save(self):
        atomic_json(self.path, self.state)

    def api(self, data):
        request = urllib.request.Request(self.url + '/api/core/upgrade/agent/',
                                         data=json.dumps(data).encode(), headers={'Content-Type': 'application/json', 'X-OTA-Token': self.token})
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.load(response)

    def flush(self):
        while self.state['pending']:
            self.api(self.state['pending'][0])
            self.state['pending'].pop(0)
            self.save()

    def report(self, job, status, detail, backup=''):
        if status in ('succeeded', 'failed'):
            self.state['terminal'] = job['id']
        self.state['pending'].append({'action': 'report', 'id': job['id'], 'claim': job['claim'],
                                      'status': status, 'detail': detail, 'backup': backup})
        self.save()
        try:
            self.flush()
        except OSError:
            pass  # During application downtime, reports remain durably queued.

    def command(self, argv, log, progress=None, **kwargs):
        kwargs.setdefault('env', {**{key: value for key, value in os.environ.items() if not key.startswith(('LEAN_', 'COMPOSE_'))},
                                  'ATM_ERP_OTA_MANAGED': '1'})
        kwargs.setdefault('timeout', 1800)
        args = [str(arg) for arg in argv]
        if progress is None:
            subprocess.run(args, check=True, stdout=log, stderr=log, **kwargs)
            return
        timeout = kwargs.pop('timeout')
        started = time.monotonic()
        with subprocess.Popen(args, stdout=log, stderr=log, **kwargs) as process:
            try:
                while True:
                    elapsed = int(time.monotonic() - started)
                    if elapsed >= timeout:
                        raise subprocess.TimeoutExpired(args, timeout)
                    try:
                        code = process.wait(timeout=min(5, timeout - elapsed))
                        if code:
                            raise subprocess.CalledProcessError(code, args)
                        return
                    except subprocess.TimeoutExpired:
                        progress(int(time.monotonic() - started))
            except BaseException:
                process.kill()
                process.wait()
                raise

    def running_version(self):
        """The checkout can be newer than the container; only running code is authoritative."""
        with urllib.request.urlopen(self.url + '/api/health/', timeout=10) as response:
            health_version = json.load(response).get('version', '')
        if not re.fullmatch(r'\d+\.\d+\.\d+', health_version):
            raise ValueError('无法确认正在运行的 ERP 版本，升级未开始。')
        if self.mode == 'docker':
            environment = {key: value for key, value in os.environ.items() if not key.startswith(('LEAN_', 'COMPOSE_'))}
            container_version = subprocess.check_output(
                [*self.compose(), 'exec', '-T', 'app', 'python', '-c',
                 'from apps.core.version import VERSION; print(VERSION)'],
                text=True, encoding='utf-8', timeout=30, env=environment,
            ).strip()
            if container_version != health_version:
                raise ValueError('网页地址与 Docker 容器版本不一致，请检查执行器配置。')
        return tuple(map(int, health_version.split('.')))

    def compose(self, root=None, config=None):
        return ['docker', 'compose', '--env-file', str(config or self.config), '-f', str((root or self.root) / 'docker-compose.yml')]

    def native(self, root, action):
        return [sys.executable, root / 'scripts/native_install.py', action, '--config', self.config]

    def native_backup(self, backup, log):
        values = self.values
        env = {**os.environ, 'PGPASSWORD': values['DB_PASSWORD']}
        self.command(['pg_dump', '-h', values['DB_HOST'], '-p', values['DB_PORT'], '-U', values['DB_USER'],
                      '-d', values['DB_NAME'], '-Fc', '--no-owner', '--no-acl', '-f', backup / 'database.dump'], log, env=env)
        uploads = Path(values['DATA_DIR']).expanduser().resolve() / 'uploads'
        if not uploads.is_dir():
            raise ValueError('Uploads directory is missing; refusing an incomplete backup')
        def walk(directory):
            # iterdir propagates permission errors; rglob may silently omit them.
            for path in directory.iterdir():
                if path.is_symlink():
                    raise ValueError('Uploads backup contains a symlink')
                if path.is_dir():
                    yield from walk(path)
                elif path.is_file():
                    yield path
                else:
                    raise ValueError('Uploads backup contains a special file')
        with tarfile.open(backup / 'uploads.tar', 'w') as tar:
            for path in walk(uploads):
                tar.add(path, arcname=path.relative_to(uploads).as_posix(), recursive=False)
        shutil.copyfile(self.config, backup / 'native-config.json')
        atomic_json(backup / 'manifest.json', {'sha256': {name: file_hash(backup / name)
                    for name in ('database.dump', 'uploads.tar', 'native-config.json')}})

    def execute(self, job):
        folder = self.directory / f"job-{job['id']}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}"
        folder.mkdir(mode=0o700)
        backup = folder / 'backup'
        backup.mkdir(mode=0o700)
        self.state['inflight'] = job
        self.save()
        stopped = False
        migration_started = False
        backup_complete = False
        phase = '版本预检'
        with (folder / 'upgrade.log').open('a', encoding='utf-8') as log:
            try:
                self.report(job, 'downloading', '正在核对运行中版本与升级目标')
                current = self.running_version()
                if (not re.fullmatch(r'v\d+\.\d+\.\d+', job['target'])
                        or tuple(map(int, job['target'][1:].split('.'))) <= current):
                    raise ValueError('目标版本不高于正在运行的版本，拒绝重复安装或降级。')
                phase = '下载与校验'
                self.report(job, 'downloading', '正在校验 GitHub 正式发布信息')
                asset = trusted_asset(job, self.mode, PLATFORM)
                archive = folder / 'package.zip'
                download(asset, archive, lambda size, total: self.report(
                    job, 'downloading', f'下载安装包：{size * 100 // total}%（{size // 1024} / {total // 1024} KB）'))
                self.report(job, 'downloading', '下载完成，正在验证并解压安装包')
                target = unpack(archive, folder / 'release', job['target'], self.mode, PLATFORM)
                if self.mode == 'docker':
                    phase = '准备发布镜像'
                    new_config = folder / '.env.lean'
                    contents = self.config.read_text(encoding='utf-8')
                    new_config.write_text(contents, encoding='utf-8')
                    os.chmod(new_config, 0o600)
                    if not json.loads((target / 'INSTALL-MANIFEST.json').read_text()).get('docker_image'):
                        raise ValueError('目标发布包没有预构建镜像，请选择新版发布包；不会本地编译')
                    self.report(job, 'downloading', '正在获取 GitHub 已构建镜像，原系统保持运行')
                    self.command([sys.executable, target / 'scripts/release_install.py', '--root', target, '--config', new_config], log,
                                 progress=lambda seconds: self.report(job, 'downloading', f'正在获取已构建镜像 · 已运行 {seconds} 秒，原系统保持运行'))
                else:
                    if not shutil.which('pg_dump'):
                        raise ValueError('pg_dump is required before stopping a native application')
                    client_version = subprocess.check_output(['pg_dump', '--version'], text=True)
                    if not re.search(r'PostgreSQL\) 15\.', client_version):
                        raise ValueError('Use the PostgreSQL 15 pg_dump client for this database')
                phase = '备份数据'
                self.report(job, 'backing_up', '正在停机并备份数据库与附件；完成前不显示可用备份位置')
                if self.mode == 'docker':
                    self.command([*self.compose(), 'stop', 'app'], log)
                    stopped = True
                    self.command([sys.executable, self.root / 'scripts/backup.py', 'backup', '--env-file', self.config,
                                  '--archive', backup / 'database-and-uploads.zip'], log)
                    shutil.copyfile(self.config, backup / '.env.lean')
                else:
                    self.command(self.native(self.root, 'stop'), log)
                    stopped = True
                    self.native_backup(backup, log)
                backup_complete = True
                phase = '安装与迁移'
                self.report(job, 'installing', '备份完成，正在执行前向迁移与安装', str(backup))
                migration_started = True
                if self.mode == 'docker':
                    self.command([*self.compose(target, new_config), 'up', '-d', '--no-build', '--wait', '--wait-timeout', '180'], log)
                else:
                    self.command(self.native(target, 'install'), log)
                    subprocess.Popen([str(arg) for arg in self.native(target, 'start')], stdout=log, stderr=log,
                                     env={**os.environ, 'ATM_ERP_OTA_MANAGED': '1'},
                                     **({'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == 'nt' else {'start_new_session': True}))
                phase = '验证新版本'
                self.report(job, 'verifying', '正在验证新版本健康状态', str(backup))
                for _ in range(60):
                    try:
                        with urllib.request.urlopen(self.url + '/api/health/', timeout=3) as response:
                            health = json.load(response)
                        if health.get('version') == job['target'].lstrip('v'):
                            break
                    except (OSError, ValueError):
                        pass
                    time.sleep(2)
                else:
                    raise RuntimeError('New version health check failed')
                self.root = target
                if self.mode == 'docker':
                    self.config = new_config
                self.state.update(root=str(self.root), config=str(self.config))
                self.report(job, 'succeeded', '新版本已启动，刷新页面即可使用', str(backup))
            except Exception as exc:
                print(f'Upgrade failed: {type(exc).__name__}: {exc}', file=log, flush=True)
                # Before migrations, restart the unchanged source safely. After migrations,
                # never point an old application at a possibly newer database schema.
                if stopped and not migration_started:
                    try:
                        if self.mode == 'docker':
                            self.command([*self.compose(), 'start', '--wait', 'app'], log)
                        else:
                            subprocess.Popen([str(arg) for arg in self.native(self.root, 'start')], stdout=log, stderr=log,
                                             env={**os.environ, 'ATM_ERP_OTA_MANAGED': '1'},
                                             **({'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == 'nt' else {'start_new_session': True}))
                    except Exception:
                        pass
                cause = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
                backup_note = '完整备份已保留。' if backup_complete else '尚未生成完整备份。'
                safety_note = '迁移已开始，不会自动回退数据库。' if migration_started else '数据库迁移尚未开始。'
                self.report(job, 'failed', f'{phase}失败：{cause} {backup_note}{safety_note} 日志：{folder / "upgrade.log"}',
                            str(backup) if backup_complete else '')
            finally:
                self.state.pop('inflight', None)
                self.save()
        print(f"任务 {job['id']} 处理结束；日志：{folder / 'upgrade.log'}", flush=True)

    def serve(self, once=False):
        with exclusive(self.directory / 'runner.lock'):
            if self.state.get('inflight'):
                if self.state.get('terminal') != self.state['inflight']['id']:
                    self.report(self.state['inflight'], 'failed', '执行器曾意外中断，请人工核对宿主机日志和备份；不会自动重复升级。')
                self.state.pop('inflight')
                self.save()
            print('OTA 执行器已启动；保持此进程运行，可在 ERP 左上角发起升级。', flush=True)
            while True:
                try:
                    self.flush()
                    job = self.api({'action': 'poll', 'mode': self.mode, 'platform': PLATFORM, 'runner_id': self.state['runner_id']}).get('job')
                    atomic_json(self.directory / 'heartbeat.json', {'seen': time.time()})
                    if job:
                        if job.get('recovered'):
                            self.report(job, 'failed', '检测到执行器上次中断的任务，已停止自动重试。请核对宿主机日志及备份后重新发起。', job.get('backup', ''))
                        else:
                            self.execute(job)
                except OSError:
                    print('暂时无法连接 ERP，将重试。', flush=True)
                if once:
                    return
                time.sleep(10)


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('docker', 'native'), required=True)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--state-dir', type=Path, required=True)
    parser.add_argument('--url', required=True)
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 11) or PLATFORM is None:
        parser.error('Use Python 3.11 on macOS, Linux or Windows')
    os.umask(0o077)
    try:
        Runner(args).serve(args.once)
    except KeyboardInterrupt:
        print('执行器停止；应用继续运行。')
    except (OSError, ValueError) as exc:
        parser.exit(1, f'执行器启动失败：{exc}\n')


if __name__ == '__main__':
    main()
