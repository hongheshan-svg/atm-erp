"""In-container OTA, with no Docker API, root privileges or host service."""
import json
import os
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.request
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace

import container_runtime as runtime
from ota_runner import Runner, atomic_json, download, file_hash, trusted_asset, unpack
from release_install import native_dependencies


class ContainerRunner(Runner):
    execution = 'container'

    def __init__(self):
        config = runtime.DATA / 'config.json'
        atomic_json(config, {key: value for key, value in os.environ.items() if key in (
            'SECRET_KEY', 'OTA_AGENT_TOKEN', 'DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_USER', 'DB_PASSWORD',
            'REDIS_URL', 'MEDIA_ROOT', 'ALLOWED_HOSTS', 'APP_ENVIRONMENT', 'OTA_MODE',
        )})
        super().__init__(SimpleNamespace(mode='native', root=runtime.BASE, config=config,
                                        state_dir=runtime.DATA, url='http://127.0.0.1:8080'))

    def control(self, action, log):
        command = ['supervisorctl', '-c', '/etc/supervisord.conf']
        status = subprocess.run([*command, 'status', 'daphne'], capture_output=True, text=True, timeout=15)
        fields = status.stdout.split()
        if len(fields) >= 2 and ((action == 'start' and fields[1] == 'RUNNING')
                                or (action == 'stop' and fields[1] in ('STOPPED', 'EXITED', 'FATAL'))):
            return
        self.command([*command, action, 'daphne'], log, timeout=45)

    def phase(self, value, job):
        atomic_json(runtime.DATA / 'maintenance.json', {'phase': value, 'job': job['id']})

    def is_prepared(self, job):
        prepared = self.state.get('prepared', {})
        return prepared.get('id') == job['id'] and prepared.get('target') == job['target']

    def recover(self):
        phase = runtime.journal().get('phase')
        inflight = self.state.get('inflight')
        with (self.directory / 'recovery.log').open('a') as log:
            if phase == 'backup':
                # No migration has begun. Restore availability before attempting HTTP reports.
                self.control('start', log)
                (runtime.DATA / 'maintenance.json').unlink(missing_ok=True)
            elif phase in ('migrating', 'blocked'):
                self.control('stop', log)
                if inflight:
                    self.phase('blocked', inflight)
            elif phase == 'verifying':
                try:
                    if not inflight or runtime.version(runtime.selected()[0]) != tuple(
                            map(int, inflight['target'].lstrip('v').split('.'))):
                        raise RuntimeError('无法确认已切换的目标版本')
                    self.control('start', log)
                    completed = self.state.get('terminal') == inflight['id']
                    if not completed:
                        self.report(inflight, 'verifying', '升级进程恢复，重新核验已切换的新版本',
                                    str(self.directory / f'job-{inflight["id"]}/backup'))
                    self.verify(inflight)
                    self.report(inflight, 'succeeded', '中断恢复后已确认新版本健康',
                                str(self.directory / f'job-{inflight["id"]}/backup'))
                    (runtime.DATA / 'maintenance.json').unlink(missing_ok=True)
                    self.state.pop('inflight', None)
                    self.save()
                except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
                    atomic_json(runtime.DATA / 'maintenance.json', {
                        'phase': 'blocked', 'job': runtime.journal().get('job'),
                    })
                    self.control('stop', log)
        # A prepared package is inert. Recover this waiting state across container recreation.
        if not phase and inflight and self.is_prepared(inflight):
            self.state.pop('inflight')
            self.save()
        super().recover()

    def reserve_space(self, required):
        if shutil.disk_usage(self.directory).free < required:
            raise RuntimeError(f'升级磁盘空间不足，至少需要 {required // (1024 * 1024) + 1} MiB 可用空间；未开始迁移')

    def check_backup_space(self):
        import psycopg2
        with closing(psycopg2.connect(host=os.environ['DB_HOST'], port=os.environ.get('DB_PORT', '5432'),
                             dbname=os.environ['DB_NAME'], user=os.environ['DB_USER'],
                             password=os.environ['DB_PASSWORD'], connect_timeout=5)) as connection:
            with connection.cursor() as cursor:
                cursor.execute('SELECT pg_database_size(current_database())')
                database_size = cursor.fetchone()[0]
        uploads = sum(path.stat().st_size for path in Path(
            os.environ.get('MEDIA_ROOT', '/app/uploads')).rglob('*') if path.is_file())
        # Conservative estimate; not a reservation against concurrent disk writers.
        self.reserve_space(database_size * 2 + uploads + 512 * 1024 * 1024)

    def verify(self, job):
        for _ in range(60):
            try:
                with urllib.request.urlopen(self.url + '/api/health/', timeout=3) as response:
                    if json.load(response).get('version') == job['target'].lstrip('v'):
                        return
            except (OSError, ValueError):
                pass
            time.sleep(2)
        raise RuntimeError('新版本健康检查未通过，不会自动回退数据库')

    def dispatch(self, job):
        if self.is_prepared(job):
            if tuple(self.state['prepared']['source']) != self.running_version():
                self.state.pop('prepared')
                self.save()
                self.report(job, 'failed', '运行版本已变化，已取消旧的待重启更新；未开始迁移')
                return
            if job['status'] == 'ready':
                return
            if job['status'] == 'downloading':
                self.report(job, 'ready', '新版本已准备完成，等待管理员重启生效')
                return
            if job['status'] == 'restarting':
                self.execute(job)
                return
        super().dispatch(job)

    def prepare(self, target, log, job):
        manifest = json.loads((target / 'INSTALL-MANIFEST.json').read_text())
        if manifest.get('container_runtime') != 1:
            raise ValueError('目标包不兼容当前容器运行时，请按文档更新基础镜像；不会强行迁移')
        dependencies = native_dependencies(target)
        self.command([sys.executable, '-m', 'venv', target / '.venv'], log)
        python = target / '.venv/bin/python'
        self.command([python, '-m', 'pip', 'install', *dependencies], log,
                     progress=lambda seconds: self.report(job, 'downloading', f'正在离线安装预编译依赖 · {seconds} 秒'))
        self.command([python, 'manage.py', 'check'], log, cwd=target / 'backend')

    def backup(self, directory, log):
        self.command(['/opt/pg/bin/pg_dump', '-h', os.environ['DB_HOST'], '-p', os.environ.get('DB_PORT', '5432'),
                      '-U', os.environ['DB_USER'], '-d', os.environ['DB_NAME'], '-Fc', '--no-owner', '--no-acl',
                      '-f', directory / 'database.dump'], log,
                     env={**os.environ, 'PGPASSWORD': os.environ['DB_PASSWORD'], 'LD_LIBRARY_PATH': '/opt/pg/lib'})
        with tarfile.open(directory / 'uploads.tar', 'w') as archive:
            archive.add(os.environ.get('MEDIA_ROOT', '/app/uploads'), arcname='uploads')
        shutil.copyfile(self.config, directory / 'config.json')
        for name in ('database.dump', 'uploads.tar', 'config.json'):
            with (directory / name).open('rb') as stream:
                os.fsync(stream.fileno())
        backend, _, _ = runtime.selected()
        atomic_json(directory / 'manifest.json', {
            'version': '.'.join(map(str, runtime.version(backend))),
            'sha256': {name: file_hash(directory / name) for name in ('database.dump', 'uploads.tar', 'config.json')},
        })

    def execute(self, job):
        folder = self.directory / f'job-{job["id"]}'
        restarting = job.get('status') == 'restarting'
        if restarting and not self.is_prepared(job):
            self.report(job, 'failed', '已准备的更新状态丢失，未开始备份或迁移，请重新下载更新')
            return
        folder.mkdir(mode=0o700, exist_ok=restarting)
        backup = folder / 'backup'
        self.state['inflight'] = job
        prepared = self.state.get('prepared', {})
        if restarting:
            self.state.pop('prepared', None)
        self.save()
        stopped = migrated = backed_up = False
        with (folder / 'upgrade.log').open('a') as log:
            try:
                current = self.running_version()
                target_version = tuple(map(int, job['target'].lstrip('v').split('.')))
                if target_version <= current:
                    raise ValueError('拒绝重复安装或降级')
                if restarting and tuple(prepared['source']) != current:
                    raise ValueError('运行版本已变化，请重新下载更新')
                asset = trusted_asset(job, 'native', 'linux')
                archive = folder / 'package.zip'
                if not restarting:
                    self.reserve_space(asset['size'] + 3 * 1024 ** 3)
                    self.report(job, 'downloading', '正在下载并校验容器内更新包，无需宿主机执行器')
                    download(asset, archive, lambda size, total: self.report(
                        job, 'downloading', f'下载并校验程序包：{size * 100 // total}%'))
                    target = unpack(archive, folder / 'release', job['target'], 'native', 'linux')
                    self.prepare(target, log, job)
                    self.state['prepared'] = {'id': job['id'], 'target': job['target'], 'source': current}
                    self.save()
                    self.report(job, 'ready', '新版本已准备完成，等待管理员重启生效；当前服务未停止')
                    return
                if file_hash(archive) != asset['sha256']:
                    raise ValueError('已准备的升级包校验失败，请重新下载更新')
                target = folder / 'release' / f'atm-erp-{job["target"]}-linux-native'
                if runtime.version(target / 'backend') != target_version or not (target / '.venv/bin/python').is_file():
                    raise ValueError('已准备的更新不完整，请重新下载更新')
                self.check_backup_space()
                backup.mkdir(mode=0o700)
                self.report(job, 'backing_up', '正在暂停业务服务并备份数据库、附件及配置')
                self.phase('backup', job)
                stopped = True
                self.control('stop', log)
                self.backup(backup, log)
                backed_up = True
                self.report(job, 'installing', '完整备份已完成，开始前向迁移', str(backup))
                self.phase('migrating', job)
                migrated = True
                self.command([target / '.venv/bin/python', 'manage.py', 'migrate', '--noinput'], log,
                             cwd=target / 'backend')
                self.command([target / '.venv/bin/python', 'manage.py', 'init_system'], log,
                             cwd=target / 'backend')
                atomic_json(runtime.DATA / 'active.json', {'release': str(target.relative_to(runtime.DATA))})
                runtime.frontend(target / 'frontend/dist')
                self.phase('verifying', job)
                self.control('start', log)
                self.report(job, 'verifying', '新版本已启动，正在验证运行版本', str(backup))
                self.verify(job)
                self.report(job, 'succeeded', '新版本已启动且已持久化，刷新页面即可使用', str(backup))
                (runtime.DATA / 'maintenance.json').unlink(missing_ok=True)
                # Only the reproducible download is disposable. Keep active code, logs and all backups.
                try:
                    archive.unlink(missing_ok=True)
                except OSError as exc:
                    print(f'下载缓存清理失败：{type(exc).__name__}', file=log, flush=True)
            except Exception as exc:
                print(f'{type(exc).__name__}: {exc}', file=log, flush=True)
                if migrated:
                    self.phase('blocked', job)
                    try:
                        self.control('stop', log)
                    except subprocess.SubprocessError:
                        pass
                else:
                    if stopped:
                        try:
                            self.control('start', log)
                        except subprocess.SubprocessError:
                            # Keep the journal and inflight task for the supervised worker's recovery.
                            raise
                    (runtime.DATA / 'maintenance.json').unlink(missing_ok=True)
                self.report(job, 'failed',
                            ('迁移已开始，已停止应用，禁止自动回退。' if migrated else '升级未完成，数据库迁移尚未开始。')
                            + f'请检查 runtime 卷日志：job-{job["id"]}/upgrade.log', str(backup) if backed_up else '')
            finally:
                if runtime.journal().get('phase') != 'backup':
                    self.state.pop('inflight', None)
                self.save()


if __name__ == '__main__':
    os.umask(0o077)
    if os.environ.get('OTA_MODE', 'container') == 'container':
        ContainerRunner().serve()
    else:
        # Supervisor keeps the optional worker idle for explicit legacy/disabled mode.
        while True:
            time.sleep(3600)
