from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.core.models import Company, UpgradeJob
from apps.core.ota import version

TOKEN = 'a' * 64


@override_settings(OTA_AGENT_TOKEN=TOKEN)
class UpgradeTests(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_user(username='ota-admin', password='test', role='admin')
        Company.objects.get_or_create(pk=1)
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        self.info = {
            'version': 'v9.0.0',
            'name': 'next',
            'notes': '',
            'url': '',
            'assets': [
                {
                    'name': 'atm-erp-v9.0.0-linux-docker.zip',
                    'url': 'https://github.com/test.zip',
                    'sha256': 'b' * 64,
                    'size': 5,
                },
            ],
        }

    def poll(self, token=TOKEN):
        return self.client.post(
            '/api/core/upgrade/agent/',
            {'action': 'poll', 'mode': 'docker', 'platform': 'linux', 'runner_id': 'c' * 32},
            format='json',
            HTTP_X_OTA_TOKEN=token,
        )

    def queue(self, key='request', target='v9.0.0'):
        with patch('apps.core.ota.release_info', return_value=self.info):
            return self.client.post(
                '/api/core/upgrade/', {'target': target, 'confirmed': True}, format='json', HTTP_IDEMPOTENCY_KEY=key
            )

    def test_permissions_apply_to_read_check_and_write(self):
        for role in ('manager', 'purchaser', 'warehouse', 'finance', 'member'):
            self.admin.role = role
            self.admin.save()
            self.assertEqual(self.client.get('/api/core/upgrade/?check=1').status_code, 403)
            self.assertEqual(self.queue().status_code, 403)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get('/api/core/upgrade/').status_code, 403)

    def test_runner_token_disabled_bad_unicode_and_valid(self):
        self.assertEqual(self.poll('wrong').status_code, 403)
        self.assertEqual(self.poll('错误密钥').status_code, 403)
        with override_settings(OTA_AGENT_TOKEN=''):
            self.assertEqual(self.poll().status_code, 403)
        self.assertEqual(self.poll().status_code, 200)
        data = self.client.get('/api/core/upgrade/').data
        self.assertEqual(data['runner']['mode'], 'docker')
        self.assertNotIn(TOKEN, str(data))

    def test_queue_requires_runner_and_prevents_downgrade_and_missing_asset(self):
        self.assertEqual(self.queue().status_code, 409)
        self.poll()
        self.assertEqual(self.queue(target='v0.1.0').status_code, 409)
        self.info['assets'] = []
        self.assertEqual(self.queue().status_code, 409)
        self.assertFalse(UpgradeJob.objects.exists())

    def test_idempotence_active_job_and_claim_once(self):
        self.poll()
        response = self.queue()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self.queue().data['id'], response.data['id'])
        self.assertEqual(self.queue(key='another').status_code, 409)
        claimed = self.poll().data['job']
        self.assertEqual(claimed['id'], response.data['id'])
        recovered = self.poll().data['job']
        self.assertTrue(recovered['recovered'])
        self.assertEqual(recovered['claim'], claimed['claim'])
        self.assertNotIn('claim', self.client.get('/api/core/upgrade/').data['job'])

    def test_claim_rechecks_admin_permission(self):
        self.poll()
        self.queue()
        self.admin.role = 'member'
        self.admin.save()
        self.assertIsNone(self.poll().data['job'])
        self.assertEqual(UpgradeJob.objects.get().status, 'failed')

    def test_progress_cannot_skip_backup_or_overwrite_finished_job(self):
        self.poll()
        self.queue()
        job = self.poll().data['job']

        def report(status, claim=job['claim']):
            return self.client.post(
                '/api/core/upgrade/agent/',
                {'action': 'report', 'id': job['id'], 'claim': claim, 'status': status},
                format='json',
                HTTP_X_OTA_TOKEN=TOKEN,
            )

        self.assertEqual(report('succeeded').status_code, 409)
        self.assertEqual(report('backing_up', 'bad').status_code, 403)
        for status in ('backing_up', 'installing', 'verifying', 'succeeded'):
            self.assertEqual(report(status).status_code, 200)
        self.assertEqual(report('failed').status_code, 409)
        self.assertEqual(report('succeeded').status_code, 200)

    def test_semantic_versions_and_request_confirmation(self):
        self.assertGreater(version('v1.10.0'), version('v1.9.0'))
        self.assertEqual(self.client.post('/api/core/upgrade/', {'target': 'v9.0.0'}, format='json').status_code, 400)

    def test_progress_keeps_runner_connected_only_with_valid_claim(self):
        self.poll()
        self.queue()
        job = self.poll().data['job']
        cache.delete('ota.runner')
        payload = {'action': 'report', 'id': job['id'], 'claim': 'wrong', 'status': 'downloading', 'detail': '构建镜像'}
        url = '/api/core/upgrade/agent/'
        self.assertEqual(self.client.post(url, payload, format='json', HTTP_X_OTA_TOKEN=TOKEN).status_code, 403)
        self.assertIsNone(cache.get('ota.runner'))
        payload['claim'] = job['claim']
        self.assertEqual(self.client.post(url, payload, format='json', HTTP_X_OTA_TOKEN=TOKEN).status_code, 200)
        self.assertEqual(self.client.get('/api/core/upgrade/').data['runner']['id'], 'c' * 32)
