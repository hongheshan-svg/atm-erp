"""宿主升级代理:从 Redis 取升级任务,执行备份/拉新/迁移/健康门/回滚,
进度持久写 Redis(后端轮询落库 + 转发 WS)。本文件含核心循环与通用步骤;
Docker/native 具体执行在 _apply_docker / _apply_native。"""
from __future__ import annotations

import json
import os
import subprocess
import time

QUEUE_KEY = 'erp:upgrade:queue'
PROGRESS_PREFIX = 'erp:upgrade:progress:'
LOCK_KEY = 'erp:upgrade:lock'
HEALTH_URL = os.environ.get('ERP_HEALTH_URL', 'http://localhost/api/v1/health/')
HEALTH_TIMEOUT = int(os.environ.get('ERP_HEALTH_TIMEOUT', '600'))
PROJECT_DIR = os.environ.get('ERP_PROJECT_DIR', '/app')


class Agent:
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

    # ---- 占位:Task 8/9 实现 ----
    def _apply_docker(self, job: dict, backup: str) -> None:
        self.report(job, 'apply', 'docker apply (placeholder)')
        if self.dry_run:
            return
        raise NotImplementedError('docker apply implemented in Task 8')

    def _apply_native(self, job: dict, backup: str) -> None:
        self.report(job, 'apply', 'native apply (placeholder)')
        if self.dry_run:
            return
        raise NotImplementedError('native apply implemented in Task 9')

    def _rollback(self, job: dict, backup: str) -> None:
        self.report(job, 'rollback', f'rollback (dry_run={self.dry_run})')
        if self.dry_run:
            return
        # Docker/native 各自回滚在 Task 8/9 覆盖
        pass

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
