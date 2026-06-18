# backend/apps/core/tests/test_upgrade_api.py
from unittest import mock
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from apps.core import upgrade_service as svc

User = get_user_model()


class UpgradeApiTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(username='admin', employee_id='A1',
                                        is_staff=True, is_superuser=True)
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        svc._release_lock()

    @mock.patch('apps.core.upgrade_views.upgrade_service.get_app_version', return_value='0.2.0')
    def test_version_endpoint(self, _v):
        r = self.client.get('/api/v1/system/version')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['version'], '0.2.0')

    @mock.patch('apps.core.upgrade_views.upgrade_service.check_update')
    def test_check_update(self, chk):
        chk.return_value = {'current_version': '0.2.0', 'latest_version': '0.3.0',
                            'has_update': True, 'deploy_mode': 'docker',
                            'release_notes_md': 'n', 'min_upgradable_from': '',
                            'cached': False, 'warning': ''}
        r = self.client.get('/api/v1/system/check-update?force=1')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['has_update'])

    @mock.patch('apps.core.upgrade_views.upgrade_service.perform_upgrade')
    def test_upgrade_returns_job(self, perform):
        perform.return_value = mock.Mock(id='abc', status='pending')
        r = self.client.post('/api/v1/system/upgrade')
        self.assertEqual(r.status_code, 202)
        self.assertEqual(r.json()['job_id'], 'abc')

    @mock.patch('apps.core.upgrade_views.upgrade_service.perform_upgrade',
                side_effect=svc.UpgradeBusy('busy'))
    def test_upgrade_busy_409(self, _p):
        r = self.client.post('/api/v1/system/upgrade')
        self.assertEqual(r.status_code, 409)

    @mock.patch('apps.core.upgrade_views.upgrade_service.perform_upgrade',
                side_effect=svc.NoUpdateAvailable('x'))
    def test_upgrade_no_update_409(self, _p):
        r = self.client.post('/api/v1/system/upgrade')
        self.assertEqual(r.status_code, 409)

    @mock.patch('apps.core.upgrade_views.upgrade_service.perform_upgrade',
                side_effect=svc.UpgradeNotAllowed('x'))
    def test_upgrade_not_allowed_400(self, _p):
        r = self.client.post('/api/v1/system/upgrade')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'UPGRADE_NOT_ALLOWED')

    @mock.patch('apps.core.upgrade_views.upgrade_service.perform_rollback')
    def test_rollback_success_202(self, perform):
        perform.return_value = mock.Mock(id='rb1', status='pending')
        r = self.client.post('/api/v1/system/rollback')
        self.assertEqual(r.status_code, 202)
        self.assertEqual(r.json()['job_id'], 'rb1')

    @mock.patch('apps.core.upgrade_views.upgrade_service.perform_rollback',
                side_effect=svc.UpgradeNotAllowed('x'))
    def test_rollback_not_allowed_400(self, _p):
        r = self.client.post('/api/v1/system/rollback')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'UPGRADE_NOT_ALLOWED')

    @mock.patch('apps.core.upgrade_views.upgrade_service.get_job', return_value=None)
    def test_job_detail_404(self, _g):
        r = self.client.get('/api/v1/system/upgrade/jobs/00000000-0000-0000-0000-000000000000')
        self.assertEqual(r.status_code, 404)
