from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.core.models import Company, UpgradeJob
from apps.core.ota import RELEASE_CACHE, version

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
        for role in set(User.Role.values) - {'admin'}:
            self.admin.role = role
            self.admin.save()
            self.assertEqual(self.client.get('/api/core/upgrade/?check=1').status_code, 403)
            self.assertEqual(self.queue().status_code, 403)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get('/api/core/upgrade/').status_code, 403)

    def test_check_cache_force_refresh_and_poll_without_external_request(self):
        with patch('apps.core.ota.release_info', return_value=self.info) as fetch:
            self.client.get('/api/core/upgrade/')
            fetch.assert_not_called()
            first = self.client.get('/api/core/upgrade/?check=1').data
            self.assertFalse(first['cached'])
            self.assertTrue(first['available'])
            second = self.client.get('/api/core/upgrade/?check=1').data
            self.assertTrue(second['cached'])
            self.assertEqual(first['checked_at'], second['checked_at'])
            self.assertEqual(fetch.call_count, 1)
            self.client.get('/api/core/upgrade/?check=1&force=1')
            self.assertEqual(fetch.call_count, 2)

    def test_failed_check_keeps_last_release_but_disables_upgrade_and_retries(self):
        cache.set(RELEASE_CACHE, {'release': self.info, 'checked_at': 1}, 60)
        with patch('apps.core.ota.release_info', side_effect=ValidationError('offline')):
            result = self.client.get('/api/core/upgrade/?check=1').data
        self.assertEqual(result['release'], self.info)
        self.assertTrue(result['cached'])
        self.assertFalse(result['available'])
        self.assertIn('check_error', result)
        with patch('apps.core.ota.release_info', return_value=self.info) as fetch:
            self.assertTrue(self.client.get('/api/core/upgrade/?check=1').data['available'])
            fetch.assert_called_once()

    def test_queue_revalidates_release_instead_of_trusting_cached_version(self):
        self.poll()
        cache.set(RELEASE_CACHE, {'release': self.info, 'checked_at': 9999999999}, 60)
        with patch('apps.core.ota.release_info', return_value={**self.info, 'version': 'v10.0.0'}):
            response = self.client.post(
                '/api/core/upgrade/',
                {'target': 'v9.0.0', 'confirmed': True},
                format='json',
                HTTP_IDEMPOTENCY_KEY='fresh-check',
            )
        self.assertEqual(response.status_code, 409)
        self.assertFalse(UpgradeJob.objects.exists())

    def test_runner_token_disabled_bad_unicode_and_valid(self):
        self.assertEqual(self.poll('wrong').status_code, 403)
        self.assertEqual(self.poll('错误密钥').status_code, 403)
        with override_settings(OTA_AGENT_TOKEN=''):
            self.assertEqual(self.poll().status_code, 403)
        self.assertEqual(self.poll().status_code, 200)
        data = self.client.get('/api/core/upgrade/').data
        self.assertEqual(data['runner']['mode'], 'docker')
        self.assertNotIn(TOKEN, str(data))

    @override_settings(OTA_MODE='container')
    def test_container_runner_rejects_host_and_selects_linux_program_package(self):
        self.assertEqual(self.poll().status_code, 409)
        response = self.client.post(
            '/api/core/upgrade/agent/',
            {
                'action': 'poll',
                'mode': 'native',
                'platform': 'linux',
                'execution': 'container',
                'runner_id': 'd' * 32,
            },
            format='json',
            HTTP_X_OTA_TOKEN=TOKEN,
        )
        self.assertEqual(response.status_code, 200)
        self.info['assets'][0]['name'] = 'atm-erp-v9.0.0-linux-native.zip'
        self.assertEqual(self.queue().status_code, 200)
        job = UpgradeJob.objects.get()
        self.assertEqual(job.mode, 'native')
        self.assertEqual(job.asset['_execution'], 'container')
        state = self.client.get('/api/core/upgrade/').data
        self.assertEqual(state['execution'], 'container')
        self.assertEqual(state['runner']['execution'], 'container')
        self.assertNotIn(TOKEN, str(state))

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

    @override_settings(OTA_MODE='container')
    def test_prepared_update_requires_admin_restart_and_preserves_backup_order(self):
        def poll():
            return self.client.post(
                '/api/core/upgrade/agent/',
                {
                    'action': 'poll',
                    'mode': 'native',
                    'platform': 'linux',
                    'execution': 'container',
                    'runner_id': 'd' * 32,
                },
                format='json',
                HTTP_X_OTA_TOKEN=TOKEN,
            )

        poll()
        self.info['assets'][0]['name'] = 'atm-erp-v9.0.0-linux-native.zip'
        self.queue()
        job = poll().data['job']

        def report(status):
            return self.client.post(
                '/api/core/upgrade/agent/',
                {
                    'action': 'report',
                    'id': job['id'],
                    'claim': job['claim'],
                    'status': status,
                },
                format='json',
                HTTP_X_OTA_TOKEN=TOKEN,
            )

        def restart(key='restart', confirmed=True):
            return self.client.post(
                '/api/core/upgrade/restart/',
                {'id': job['id'], 'confirmed': confirmed},
                format='json',
                HTTP_IDEMPOTENCY_KEY=key,
            )

        self.assertEqual(restart().status_code, 409)
        self.assertEqual(report('backing_up').status_code, 409)
        self.assertEqual(report('ready').status_code, 200)
        self.assertTrue(self.client.get('/api/core/upgrade/').data['job']['need_restart'])
        self.assertEqual(poll().data['job']['status'], 'ready')
        self.assertEqual(report('restarting').status_code, 409)
        self.assertEqual(self.queue(key='second').status_code, 409)
        self.assertEqual(restart(confirmed=False).status_code, 400)
        self.admin.role = 'member'
        self.admin.save()
        self.assertEqual(restart().status_code, 403)
        self.admin.role = 'admin'
        self.admin.save()
        cache.delete('ota.runner')
        self.assertEqual(restart().status_code, 409)
        poll()
        with patch('apps.core.ota.VERSION', '8.0.0'):
            self.assertEqual(restart().status_code, 409)
        response = restart()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['status'], 'restarting')
        self.assertFalse(response.data['need_restart'])
        self.assertEqual(restart().data, response.data)
        self.assertEqual(restart(key='other').status_code, 409)
        self.assertEqual(report('ready').data['status'], 'restarting')
        self.assertEqual(report('installing').status_code, 409)
        for status in ('backing_up', 'installing', 'verifying', 'succeeded'):
            self.assertEqual(report(status).status_code, 200)

    def test_legacy_host_cannot_use_container_restart(self):
        self.poll()
        self.queue()
        job = UpgradeJob.objects.get()
        job.status = 'ready'
        job.save()
        response = self.client.post(
            '/api/core/upgrade/restart/',
            {'id': job.pk, 'confirmed': True},
            format='json',
            HTTP_IDEMPOTENCY_KEY='host-restart',
        )
        self.assertEqual(response.status_code, 409)

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
