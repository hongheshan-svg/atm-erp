"""升级编排:检查更新(缓存)、单飞锁、建 job、投递任务到 Redis 队列。"""
from __future__ import annotations

import json

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
            'deploy_mode': get_deploy_mode(), 'release_notes_md': '',
            'min_upgradable_from': '', 'cached': False, 'warning': str(exc),
        }
    info = {
        'current_version': current, 'latest_version': m.latest_version,
        'has_update': compare_versions(current, m.latest_version) < 0,
        'deploy_mode': get_deploy_mode(), 'release_notes_md': m.release_notes_md,
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
    if not _acquire_lock():
        raise UpgradeBusy('another upgrade is in progress')
    try:
        job = UpgradeJob.objects.create(
            action=UpgradeJob.ACTION_UPGRADE, mode=get_deploy_mode(),
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
    if not _acquire_lock():
        raise UpgradeBusy('another upgrade is in progress')
    try:
        job = UpgradeJob.objects.create(
            action=UpgradeJob.ACTION_ROLLBACK, mode=get_deploy_mode(),
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


def list_jobs(limit: int = 20):
    return list(UpgradeJob.objects.all()[:limit])
