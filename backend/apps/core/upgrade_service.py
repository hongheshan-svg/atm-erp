"""升级编排:检查更新(缓存)、单飞锁、建 job、投递任务到 Redis 队列。"""
from __future__ import annotations

import json
import re

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django_redis import get_redis_connection

from .manifest_client import ManifestError, fetch_manifest
from .models import UpgradeJob
from .version import compare_versions, get_app_version, get_deploy_mode

MANIFEST_URL = settings.ERP_UPDATE_MANIFEST_URL
CACHE_KEY = 'erp:upgrade:check'
CACHE_TTL = 1200  # 20min
QUEUE_KEY = 'erp:upgrade:queue'
LOCK_KEY = 'erp:upgrade:lock'
LOCK_TTL = 3600  # 安全上限,避免死锁
PROGRESS_PREFIX = 'erp:upgrade:progress:'  # agent 直写的进度键(不依赖 pub/sub,用于兜底对账)
TERMINAL_STATUSES = (UpgradeJob.STATUS_SUCCESS, UpgradeJob.STATUS_FAILED, UpgradeJob.STATUS_ROLLED_BACK)


class UpgradeBusy(Exception):
    pass


class NoUpdateAvailable(Exception):
    pass


class UpgradeNotAllowed(Exception):
    pass


def _redis():
    return get_redis_connection('default')


def _acquire_lock() -> bool:
    return bool(_redis().set(LOCK_KEY, '1', nx=True, ex=LOCK_TTL))


def _release_lock() -> None:
    _redis().delete(LOCK_KEY)


def release_url(version: str = '') -> str:
    """从 manifest URL 推导 GitHub 发布页链接(供前端「查看更新内容」点击自行查看)。

    manifest 形如 https://raw.githubusercontent.com/<owner>/<repo>/<branch>/manifest.json,
    带版本时给 tag 页,否则给 releases 列表页;非 GitHub 源返回空串。
    """
    m = re.match(r'https?://raw\.githubusercontent\.com/([^/]+)/([^/]+)/', MANIFEST_URL) or \
        re.match(r'https?://github\.com/([^/]+)/([^/]+)', MANIFEST_URL)
    if not m:
        return ''
    base = f'https://github.com/{m.group(1)}/{m.group(2)}/releases'
    v = (version or '').lstrip('v')
    return f'{base}/tag/v{v}' if v else base


def _enqueue(job: UpgradeJob, manifest_raw: dict) -> None:
    payload = {
        'id': str(job.id), 'action': job.action, 'mode': job.mode,
        'target_version': job.target_version, 'from_version': job.from_version,
        'manifest': manifest_raw,
    }
    _redis().lpush(QUEUE_KEY, json.dumps(payload))


def check_update(force: bool = False) -> dict:
    current = get_app_version()
    if not force:
        cached = cache.get(CACHE_KEY)
        if cached:
            cached['cached'] = True
            return cached
    try:
        m = fetch_manifest(MANIFEST_URL)
    except ManifestError as exc:
        return {
            'current_version': current, 'latest_version': current, 'has_update': False,
            'deploy_mode': get_deploy_mode(), 'release_notes_md': '', 'release_url': release_url(),
            'min_upgradable_from': '', 'cached': False, 'warning': str(exc),
        }
    info = {
        'current_version': current, 'latest_version': m.latest_version,
        'has_update': compare_versions(current, m.latest_version) < 0,
        'deploy_mode': get_deploy_mode(), 'release_notes_md': m.release_notes_md,
        'release_url': release_url(m.latest_version),
        'min_upgradable_from': m.min_upgradable_from, 'cached': False, 'warning': '',
    }
    cache.set(CACHE_KEY, info, CACHE_TTL)
    return info


def perform_upgrade(user) -> UpgradeJob:
    current = get_app_version()
    m = fetch_manifest(MANIFEST_URL)
    if compare_versions(current, m.latest_version) >= 0:
        raise NoUpdateAvailable('current version is latest')
    if m.min_upgradable_from and compare_versions(current, m.min_upgradable_from) < 0:
        raise UpgradeNotAllowed(
            f'must upgrade to {m.min_upgradable_from} first (current {current})')
    mode = get_deploy_mode()
    if mode not in (UpgradeJob.MODE_DOCKER, UpgradeJob.MODE_NATIVE):
        raise UpgradeNotAllowed(f'deploy mode {mode!r} is not upgradable')
    if mode == UpgradeJob.MODE_NATIVE:
        raise UpgradeNotAllowed(
            '原生部署的一键升级暂未支持，请使用手动升级流程（见 docs/REMOTE_UPGRADE.md）')
    if not _acquire_lock():
        raise UpgradeBusy('another upgrade is in progress')
    try:
        job = UpgradeJob.objects.create(
            action=UpgradeJob.ACTION_UPGRADE, mode=mode,
            from_version=current, target_version=m.latest_version,
            status=UpgradeJob.STATUS_PENDING, triggered_by=user,
            started_at=timezone.now(),
        )
        _enqueue(job, m.raw)
        return job
    except Exception:
        _release_lock()
        raise


def perform_rollback(user) -> UpgradeJob:
    last = (UpgradeJob.objects.filter(action=UpgradeJob.ACTION_UPGRADE,
                                      status=UpgradeJob.STATUS_SUCCESS)
            .order_by('-created_at').first())
    if last is None:
        raise NoUpdateAvailable('no successful upgrade to roll back')
    mode = get_deploy_mode()
    if mode not in (UpgradeJob.MODE_DOCKER, UpgradeJob.MODE_NATIVE):
        raise UpgradeNotAllowed(f'deploy mode {mode!r} is not upgradable')
    if mode == UpgradeJob.MODE_NATIVE:
        raise UpgradeNotAllowed(
            '原生部署的一键升级暂未支持，请使用手动升级流程（见 docs/REMOTE_UPGRADE.md）')
    if not _acquire_lock():
        raise UpgradeBusy('another upgrade is in progress')
    try:
        job = UpgradeJob.objects.create(
            action=UpgradeJob.ACTION_ROLLBACK, mode=mode,
            from_version=get_app_version(), target_version=last.from_version,
            status=UpgradeJob.STATUS_PENDING, triggered_by=user, started_at=timezone.now(),
        )
        _enqueue(job, {'rollback_to': last.from_version})
        return job
    except Exception:
        _release_lock()
        raise


def get_job(job_id):
    return UpgradeJob.objects.filter(id=job_id).first()


def reconcile_job(job):
    """以 agent 直写的 redis 进度键为准,兜底对账非终态的 DB job。

    进度落库由 upgrade_progress_relay(跑在 app 容器内)订阅 pub/sub 完成,但升级会重建 app →
    relay 随之重启,期间 agent 在重建后 publish 的 healthcheck/success 事件会丢失,使 DB job
    停在 running。agent 同时把完整状态写入 ``erp:upgrade:progress:<id>``(不依赖订阅),故读取
    job 时若 DB 仍为非终态,以该键回填 steps/status,保证前端轮询能看到真正结果。
    """
    if job is None or job.status in TERMINAL_STATUSES:
        return job
    raw = _redis().get(PROGRESS_PREFIX + str(job.id))
    if not raw:
        return job
    try:
        state = json.loads(raw)
    except (ValueError, TypeError):
        return job
    changed = False
    steps = state.get('steps')
    if steps is not None and steps != job.steps:
        job.steps = steps
        changed = True
    new_status = state.get('status')
    if new_status and new_status != job.status:
        job.status = new_status
        changed = True
    if changed:
        fields = ['status', 'steps', 'updated_at']
        if job.status in TERMINAL_STATUSES and not job.finished_at:
            job.finished_at = timezone.now()
            fields.append('finished_at')
        job.save(update_fields=fields)
    return job


def list_jobs(limit: int = 20):
    return list(UpgradeJob.objects.all().order_by('-created_at')[:limit])
