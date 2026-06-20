import json
from unittest import mock
from django.core.cache import cache
from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.core import upgrade_service as svc
from apps.core.manifest_client import Manifest, ManifestError
from apps.core.models import UpgradeJob

User = get_user_model()


def _manifest(latest='0.3.0', minfrom='0.0.0'):
    return Manifest(latest_version=latest, min_upgradable_from=minfrom,
                    docker={'image_tag': latest}, native={'sha256': 'x'},
                    release_notes_md='notes')


class CheckUpdateTest(TestCase):
    @mock.patch('apps.core.upgrade_service.get_app_version', return_value='0.2.0')
    @mock.patch('apps.core.upgrade_service.fetch_manifest')
    def test_has_update(self, fetch, _v):
        fetch.return_value = _manifest('0.3.0')
        info = svc.check_update(force=True)
        self.assertTrue(info['has_update'])
        self.assertEqual(info['latest_version'], '0.3.0')

    @mock.patch('apps.core.upgrade_service.get_app_version', return_value='0.3.0')
    @mock.patch('apps.core.upgrade_service.fetch_manifest')
    def test_no_update(self, fetch, _v):
        fetch.return_value = _manifest('0.3.0')
        info = svc.check_update(force=True)
        self.assertFalse(info['has_update'])


class PerformUpgradeTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(username='admin', employee_id='A1')
        svc._release_lock()  # 保证干净

    @mock.patch('apps.core.upgrade_service.get_deploy_mode', return_value='docker')
    @mock.patch('apps.core.upgrade_service.get_app_version', return_value='0.2.0')
    @mock.patch('apps.core.upgrade_service.fetch_manifest', return_value=_manifest('0.3.0'))
    @mock.patch('apps.core.upgrade_service._enqueue')
    def test_creates_job_and_enqueues(self, enq, *_):
        job = svc.perform_upgrade(self.user)
        self.assertEqual(job.action, UpgradeJob.ACTION_UPGRADE)
        self.assertEqual(job.target_version, '0.3.0')
        enq.assert_called_once()

    @mock.patch('apps.core.upgrade_service.get_deploy_mode', return_value='docker')
    @mock.patch('apps.core.upgrade_service.get_app_version', return_value='0.2.0')
    @mock.patch('apps.core.upgrade_service.fetch_manifest', return_value=_manifest('0.3.0'))
    @mock.patch('apps.core.upgrade_service._enqueue')
    def test_single_flight(self, *_):
        svc.perform_upgrade(self.user)
        with self.assertRaises(svc.UpgradeBusy):
            svc.perform_upgrade(self.user)

    @mock.patch('apps.core.upgrade_service.get_app_version', return_value='0.3.0')
    @mock.patch('apps.core.upgrade_service.fetch_manifest', return_value=_manifest('0.3.0'))
    def test_no_update_raises(self, *_):
        with self.assertRaises(svc.NoUpdateAvailable):
            svc.perform_upgrade(self.user)

    @mock.patch('apps.core.upgrade_service.get_deploy_mode', return_value='docker')
    @mock.patch('apps.core.upgrade_service.get_app_version', return_value='0.2.0')
    @mock.patch('apps.core.upgrade_service.fetch_manifest',
                return_value=_manifest('0.9.0', minfrom='0.5.0'))
    def test_upgrade_not_allowed_when_below_min(self, *_):
        with self.assertRaises(svc.UpgradeNotAllowed):
            svc.perform_upgrade(self.user)

    @mock.patch('apps.core.upgrade_service.get_deploy_mode', return_value='unknown')
    @mock.patch('apps.core.upgrade_service.get_app_version', return_value='0.2.0')
    @mock.patch('apps.core.upgrade_service.fetch_manifest',
                return_value=_manifest('0.3.0'))
    def test_upgrade_refused_unknown_mode(self, *_):
        with self.assertRaises(svc.UpgradeNotAllowed):
            svc.perform_upgrade(self.user)

    @mock.patch('apps.core.upgrade_service.get_deploy_mode', return_value='native')
    @mock.patch('apps.core.upgrade_service.get_app_version', return_value='0.2.0')
    @mock.patch('apps.core.upgrade_service.fetch_manifest',
                return_value=_manifest('0.3.0'))
    def test_upgrade_refused_native_mode(self, *_):
        with self.assertRaises(svc.UpgradeNotAllowed):
            svc.perform_upgrade(self.user)

    @mock.patch('apps.core.upgrade_service.get_deploy_mode', return_value='native')
    def test_rollback_refused_native_mode(self, _mode):
        # plant a successful upgrade so rollback has a record to find
        UpgradeJob.objects.create(
            action=UpgradeJob.ACTION_UPGRADE, mode=UpgradeJob.MODE_DOCKER,
            from_version='0.2.0', target_version='0.3.0',
            status=UpgradeJob.STATUS_SUCCESS, triggered_by=self.user,
        )
        with self.assertRaises(svc.UpgradeNotAllowed):
            svc.perform_rollback(self.user)


class CheckUpdateCacheTest(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()  # cache 走共享 redis,清掉以免污染本地运行栈/其他用例

    @mock.patch('apps.core.upgrade_service.get_deploy_mode', return_value='docker')
    @mock.patch('apps.core.upgrade_service.get_app_version', return_value='0.2.0')
    @mock.patch('apps.core.upgrade_service.fetch_manifest')
    def test_check_update_cache_hit(self, fetch, _v, _m):
        fetch.return_value = _manifest('0.3.0')
        svc.check_update(force=True)
        info = svc.check_update(force=False)
        self.assertTrue(info['cached'])

    @mock.patch('apps.core.upgrade_service.get_deploy_mode', return_value='docker')
    @mock.patch('apps.core.upgrade_service.fetch_manifest')
    def test_cached_reflects_live_version_after_upgrade(self, fetch, _m):
        """升级后走缓存:current_version/has_update 按实时版本重算,不复用旧缓存值。"""
        fetch.return_value = _manifest('0.3.0')
        with mock.patch('apps.core.upgrade_service.get_app_version', return_value='0.2.0'):
            svc.check_update(force=True)  # 落缓存:current 0.2.0 / has_update True
        # 升级到 0.3.0 后再走缓存(force=False)
        with mock.patch('apps.core.upgrade_service.get_app_version', return_value='0.3.0'):
            info = svc.check_update(force=False)
        self.assertTrue(info['cached'])
        self.assertEqual(info['current_version'], '0.3.0')
        self.assertFalse(info['has_update'])

    @mock.patch('apps.core.upgrade_service.get_deploy_mode', return_value='docker')
    @mock.patch('apps.core.upgrade_service.get_app_version', return_value='0.2.0')
    @mock.patch('apps.core.upgrade_service.fetch_manifest')
    def test_check_update_manifest_error(self, fetch, _v, _m):
        cache.clear()
        fetch.side_effect = ManifestError('boom')
        info = svc.check_update(force=True)
        self.assertFalse(info['has_update'])
        self.assertTrue(info['warning'])


class ReconcileJobTest(TestCase):
    """升级会重建 app(relay 在其中),漏掉的进度事件以 redis 进度键兜底对账。"""

    def setUp(self):
        self.user = User.objects.create(username='admin', employee_id='A1')

    def _job(self, status):
        return UpgradeJob.objects.create(
            action=UpgradeJob.ACTION_UPGRADE, mode=UpgradeJob.MODE_DOCKER,
            from_version='0.1.0', target_version='0.2.0',
            status=status, triggered_by=self.user,
        )

    @mock.patch('apps.core.upgrade_service._redis')
    def test_reconciles_running_to_success(self, redis):
        job = self._job(UpgradeJob.STATUS_RUNNING)
        state = {'id': str(job.id), 'status': 'success',
                 'steps': [{'stage': 'done', 'message': 'health OK', 'level': 'info'}]}
        redis.return_value.get.return_value = json.dumps(state).encode()
        out = svc.reconcile_job(job)
        out.refresh_from_db()
        self.assertEqual(out.status, UpgradeJob.STATUS_SUCCESS)
        self.assertEqual(len(out.steps), 1)
        self.assertIsNotNone(out.finished_at)

    @mock.patch('apps.core.upgrade_service._redis')
    def test_terminal_job_not_touched(self, redis):
        job = self._job(UpgradeJob.STATUS_FAILED)
        svc.reconcile_job(job)
        redis.assert_not_called()  # 终态短路,不查 redis
        job.refresh_from_db()
        self.assertEqual(job.status, UpgradeJob.STATUS_FAILED)

    @mock.patch('apps.core.upgrade_service._redis')
    def test_no_progress_key_keeps_status(self, redis):
        job = self._job(UpgradeJob.STATUS_RUNNING)
        redis.return_value.get.return_value = None
        out = svc.reconcile_job(job)
        self.assertEqual(out.status, UpgradeJob.STATUS_RUNNING)
