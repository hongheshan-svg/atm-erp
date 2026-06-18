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


class CheckUpdateCacheTest(TestCase):
    def setUp(self):
        cache.clear()

    @mock.patch('apps.core.upgrade_service.get_deploy_mode', return_value='docker')
    @mock.patch('apps.core.upgrade_service.get_app_version', return_value='0.2.0')
    @mock.patch('apps.core.upgrade_service.fetch_manifest')
    def test_check_update_cache_hit(self, fetch, _v, _m):
        fetch.return_value = _manifest('0.3.0')
        svc.check_update(force=True)
        info = svc.check_update(force=False)
        self.assertTrue(info['cached'])

    @mock.patch('apps.core.upgrade_service.get_deploy_mode', return_value='docker')
    @mock.patch('apps.core.upgrade_service.get_app_version', return_value='0.2.0')
    @mock.patch('apps.core.upgrade_service.fetch_manifest')
    def test_check_update_manifest_error(self, fetch, _v, _m):
        cache.clear()
        fetch.side_effect = ManifestError('boom')
        info = svc.check_update(force=True)
        self.assertFalse(info['has_update'])
        self.assertTrue(info['warning'])
