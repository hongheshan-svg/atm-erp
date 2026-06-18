"""宿主升级代理:从 Redis 取升级任务,执行备份/拉新/迁移/健康门/回滚,
进度持久写 Redis(后端轮询落库 + 转发 WS)。本文件含核心循环与通用步骤;
Docker/native 具体执行在 _apply_docker / _apply_native。"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import time


def verify_sha256(path: str, expected: str) -> None:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    actual = h.hexdigest()
    if actual.lower() != expected.lower():
        raise ValueError(f'sha256 mismatch: {actual} != {expected}')


def set_env_image_tag(env_path: str, new_tag: str) -> str:
    """把 .env 里的 IMAGE_TAG 改成 new_tag,返回旧值(没有则空串)。"""
    old = ''
    lines = []
    found = False
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('IMAGE_TAG='):
                old = line.split('=', 1)[1].strip()
                lines.append(f'IMAGE_TAG={new_tag}\n')
                found = True
            else:
                lines.append(line)
    if not found:
        lines.append(f'IMAGE_TAG={new_tag}\n')
    with open(env_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    return old

QUEUE_KEY = 'erp:upgrade:queue'
PROGRESS_PREFIX = 'erp:upgrade:progress:'
LOCK_KEY = 'erp:upgrade:lock'
HEALTH_URL = os.environ.get('ERP_HEALTH_URL', 'http://localhost/api/v1/health/')
HEALTH_TIMEOUT = int(os.environ.get('ERP_HEALTH_TIMEOUT', '600'))
PROJECT_DIR = os.environ.get('ERP_PROJECT_DIR', '/app')


class Agent:
    RELEASES_DIR = os.environ.get('ERP_RELEASES_DIR', '/opt/erp/releases')
    CURRENT_LINK = os.environ.get('ERP_CURRENT_LINK', '/opt/erp/current')

    def __init__(self, redis_client, *, dry_run: bool = False):
        self.r = redis_client
        self.dry_run = dry_run

    # ---- 进度 ----
    def _progress_key(self, job_id: str) -> str:
        return PROGRESS_PREFIX + job_id

    def report(self, job: dict, stage: str, message: str, level: str = 'info',
               status: str | None = None) -> None:
        key = self._progress_key(job['id'])
        raw = self.r.get(key)
        state = json.loads(raw) if raw else {'id': job['id'], 'steps': [], 'status': 'running'}
        state['steps'].append({'stage': stage, 'message': message, 'level': level, 'ts': time.time()})
        if status:
            state['status'] = status
        self.r.set(key, json.dumps(state), ex=86400)
        # 通知后端(后端订阅此频道,落库 + 转发 WS)
        self.r.publish('erp:upgrade:events', json.dumps({'job_id': job['id'], 'state': state}))

    # ---- 通用步骤 ----
    def backup_db(self, job: dict) -> str:
        ts = time.strftime('%Y%m%d-%H%M%S')
        path = f'/var/backups/erp/pre-upgrade-{ts}.sql'
        self.report(job, 'backup', f'pg_dump -> {path}')
        if self.dry_run:
            return path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._run(['pg_dump', '-f', path], env_db=True)
        return path

    def health_gate(self, job: dict) -> bool:
        self.report(job, 'healthcheck', f'polling {HEALTH_URL}', status='healthcheck')
        if self.dry_run:
            return True
        import requests
        deadline = time.time() + HEALTH_TIMEOUT
        while time.time() < deadline:
            try:
                resp = requests.get(HEALTH_URL, timeout=5)
                if resp.status_code == 200 and \
                        resp.json().get('version') == job['target_version']:
                    return True
            except Exception:
                pass
            time.sleep(5)
        return False

    def _run(self, cmd: list[str], *, cwd: str | None = None, env_db: bool = False) -> None:
        env = dict(os.environ)
        subprocess.run(cmd, cwd=cwd or PROJECT_DIR, env=env, check=True)

    # ---- 分派 ----
    def handle(self, job: dict) -> None:
        self.report(job, 'plan', f"{job['action']} -> {job.get('target_version')} (mode={job['mode']}, dry_run={self.dry_run})", status='running')
        try:
            backup = self.backup_db(job)
            if job['mode'] == 'docker':
                self._apply_docker(job, backup)
            else:
                self._apply_native(job, backup)
            if self.health_gate(job):
                self.report(job, 'done', 'health OK', status='success')
            else:
                self.report(job, 'healthcheck', 'health gate failed, rolling back', level='error')
                self._rollback(job, backup)
                self.report(job, 'done', 'rolled back', status='rolled_back')
        except Exception as exc:  # noqa: BLE001
            self.report(job, 'error', str(exc), level='error')
            try:
                self._rollback(job, locals().get('backup', ''))
                self.report(job, 'done', 'rolled back after error', status='rolled_back')
            except Exception as rexc:  # noqa: BLE001
                self.report(job, 'error', f'rollback failed: {rexc}', level='error', status='failed')
        finally:
            self.r.delete(LOCK_KEY)

    # ---- Docker 分支 (Task 8) ----
    def _compose(self, *args: str) -> None:
        self._run(['docker', 'compose', *args], cwd=PROJECT_DIR)

    def _apply_docker(self, job: dict, backup: str) -> None:
        new_tag = job['manifest']['docker']['image_tag']
        env_path = os.path.join(PROJECT_DIR, '.env')
        self.report(job, 'apply', f'set IMAGE_TAG={new_tag}; docker compose pull && up -d')
        if self.dry_run:
            job['_old_tag'] = '0.0.0'
            return
        job['_old_tag'] = set_env_image_tag(env_path, new_tag)
        self._compose('pull')
        self._compose('up', '-d')

    def _apply_native(self, job: dict, backup: str) -> None:
        target = job['target_version']
        if not re.fullmatch(r'[A-Za-z0-9._-]{1,64}', target or '') or target.startswith('.') or '..' in target:
            raise ValueError(f'invalid target_version: {target!r}')
        nat = job['manifest']['native']
        self.report(job, 'apply', f"download {nat['tarball_url']} -> release {target}, migrate, restart")
        if self.dry_run:
            return
        job['_old_link'] = os.path.realpath(self.CURRENT_LINK) if os.path.islink(self.CURRENT_LINK) else ''
        import requests
        rel_dir = os.path.join(self.RELEASES_DIR, target)
        if os.path.commonpath([os.path.realpath(rel_dir), os.path.realpath(self.RELEASES_DIR)]) != os.path.realpath(self.RELEASES_DIR):
            raise ValueError('release dir escapes RELEASES_DIR')
        os.makedirs(rel_dir, exist_ok=True)
        tar_path = os.path.join(rel_dir, 'release.tar.gz')
        with requests.get(nat['tarball_url'], stream=True, timeout=60) as resp:
            resp.raise_for_status()
            with open(tar_path, 'wb') as f:
                for chunk in resp.iter_content(1024 * 1024):
                    f.write(chunk)
        verify_sha256(tar_path, nat['sha256'])
        self._run(['tar', '--no-same-owner', '--no-same-permissions', '--no-overwrite-dir',
                   '-xzf', tar_path, '-C', rel_dir, '--strip-components=1'])
        # 迁移与静态(在新发布目录)
        py = os.path.join(rel_dir, 'venv/bin/python')
        py = py if os.path.exists(py) else 'python'
        self._run([py, 'manage.py', 'migrate', '--noinput'], cwd=os.path.join(rel_dir, 'backend'))
        self._run([py, 'manage.py', 'collectstatic', '--noinput'], cwd=os.path.join(rel_dir, 'backend'))
        # 切换 current 软链 + 重启
        tmp_link = self.CURRENT_LINK + '.new'
        if os.path.lexists(tmp_link):
            os.remove(tmp_link)
        os.symlink(rel_dir, tmp_link)
        os.replace(tmp_link, self.CURRENT_LINK)
        self._run(['systemctl', 'restart', 'erp-backend', 'erp-celery', 'erp-celery-beat'])

    def _rollback(self, job: dict, backup: str) -> None:
        self.report(job, 'rollback', f'rollback (dry_run={self.dry_run})')
        if self.dry_run:
            return
        if job['mode'] == 'docker':
            old = job.get('_old_tag') or job.get('from_version')
            set_env_image_tag(os.path.join(PROJECT_DIR, '.env'), old)
            self._compose('up', '-d')
        else:
            self._rollback_native(job, backup)

    def _rollback_native(self, job: dict, backup: str) -> None:
        old = job.get('_old_link')
        if old and os.path.isdir(old):
            tmp = self.CURRENT_LINK + '.rb'
            if os.path.lexists(tmp):
                os.remove(tmp)
            os.symlink(old, tmp)
            os.replace(tmp, self.CURRENT_LINK)
            self._run(['systemctl', 'restart', 'erp-backend', 'erp-celery', 'erp-celery-beat'])

    # ---- 循环 ----
    def run_once(self) -> bool:
        item = self.r.rpop(QUEUE_KEY)
        if not item:
            return False
        job = json.loads(item)
        self.handle(job)
        return True

    def run_forever(self, poll: float = 2.0) -> None:  # pragma: no cover
        while True:
            if not self.run_once():
                time.sleep(poll)


def _main() -> None:  # pragma: no cover
    import redis
    url = os.environ.get('REDIS_URL', 'redis://redis:6379/1')
    Agent(redis.Redis.from_url(url)).run_forever()


if __name__ == '__main__':  # pragma: no cover
    _main()
