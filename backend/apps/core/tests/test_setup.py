import io
import os
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.core.models import ActionReceipt, AuditLog, CodeRule, Company


class SetupTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(pk=1, setup_required=True)
        self.admin = User.objects.create_user(username='admin', role='admin', password='Initial-Test-Password-2026')
        self.rule = CodeRule.objects.create(key='item', prefix='MAT')
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        self.data = {
            'display_name': '安装管理员',
            'old_password': 'Initial-Test-Password-2026',
            'new_password': 'Ready-For-ERP-2026-Password',
            'company': {'name': '测试自动化公司', 'address': '测试园区1号', 'phone': '010-12345678'},
            'team': [
                {
                    'username': 'buyer',
                    'display_name': '采购仓管',
                    'roles': ['purchaser', 'warehouse'],
                    'password': 'Team-Ready-Password-2026',
                }
            ],
            'codes': [
                {
                    'id': self.rule.pk,
                    'prefix': 'WL',
                    'date_format': 'YYYYMM',
                    'padding': 5,
                    'reset_cycle': 'month',
                    'expected_revision': 0,
                    'reason': '首次安装配置',
                }
            ],
            'confirmed': True,
        }

    def submit(self, key='first-setup'):
        return self.client.post('/api/core/setup/', self.data, format='json', HTTP_IDEMPOTENCY_KEY=key)

    def test_complete_reuses_facts_audits_and_replay(self):
        self.assertTrue(self.client.get('/api/auth/me/').data['setup_required'])
        response = self.submit()
        self.assertEqual(response.status_code, 200, response.data)
        self.company.refresh_from_db()
        self.admin.refresh_from_db()
        self.assertFalse(self.company.setup_required)
        self.assertIsNotNone(self.company.setup_completed_at)
        self.assertTrue(self.admin.check_password(self.data['new_password']))
        self.assertEqual(self.admin.display_name, '安装管理员')
        self.assertEqual(User.objects.get(username='buyer').additional_roles, ['warehouse'])
        self.rule.refresh_from_db()
        self.assertEqual(self.rule.prefix, 'WL')
        self.assertEqual(self.rule.counter, 0)
        self.assertEqual(self.submit().status_code, 200)
        self.assertEqual(User.objects.count(), 2)
        self.assertEqual(AuditLog.objects.filter(operation='system.setup').count(), 1)
        self.assertEqual(self.submit('another-key').status_code, 409)
        stored = str(list(AuditLog.objects.values())) + str(list(ActionReceipt.objects.values()))
        self.assertNotIn(self.data['new_password'], stored)
        self.assertNotIn(self.data['old_password'], stored)
        self.assertFalse(self.client.get('/api/auth/me/').data['setup_required'])

    def test_failed_last_step_rolls_back_people_company_and_password(self):
        self.data['codes'][0]['expected_revision'] = 99
        self.assertEqual(self.submit().status_code, 409)
        self.company.refresh_from_db()
        self.admin.refresh_from_db()
        self.assertTrue(self.company.setup_required)
        self.assertEqual(self.company.name, '我的公司')
        self.assertTrue(self.admin.check_password(self.data['old_password']))
        self.assertEqual(User.objects.count(), 1)
        self.assertFalse(ActionReceipt.objects.exists())
        self.assertFalse(AuditLog.objects.exists())

    def test_duplicate_team_and_invalid_roles_roll_back(self):
        self.data['team'].append(self.data['team'][0].copy())
        self.assertEqual(self.submit().status_code, 400)
        self.assertEqual(User.objects.count(), 1)
        self.data['team'] = [dict(self.data['team'][0], roles=['invented'])]
        self.assertEqual(self.submit().status_code, 400)
        self.assertEqual(User.objects.count(), 1)

    def test_admin_only_and_replay_rechecks_role(self):
        self.assertEqual(self.submit().status_code, 200)
        self.admin.role = 'member'
        self.admin.save()
        self.assertEqual(self.client.get('/api/core/setup/').status_code, 403)
        self.assertEqual(self.submit().status_code, 403)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get('/api/core/setup/').status_code, 401)

    def test_password_validation_confirmation_and_defaults(self):
        self.data['confirmed'] = False
        self.assertEqual(self.submit().status_code, 400)
        self.data['confirmed'] = True
        self.data['new_password'] = 'short'
        self.assertEqual(self.submit().status_code, 400)
        self.data['new_password'] = self.data['old_password']
        self.assertEqual(self.submit().status_code, 400)
        self.data['new_password'] = 'Ready-For-ERP-2026-Password'
        self.data['team'] = []
        self.data['codes'] = []
        self.assertEqual(self.submit().status_code, 200)
        self.assertEqual(User.objects.count(), 1)
        self.rule.refresh_from_db()
        self.assertEqual(self.rule.prefix, 'MAT')

    def test_old_tokens_revoked_after_setup(self):
        self.client.force_authenticate(None)
        token = self.client.post('/api/auth/login/', {'username': 'admin', 'password': self.data['old_password']}).data
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + token['access'])
        self.assertEqual(self.submit().status_code, 200)
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 401)
        self.client.credentials()
        self.assertEqual(self.client.post('/api/auth/refresh/', {'refresh': token['refresh']}).status_code, 401)
        self.assertEqual(
            self.client.post(
                '/api/auth/login/', {'username': 'admin', 'password': self.data['new_password']}
            ).status_code,
            200,
        )

    def test_existing_install_not_forced_or_overwritten(self):
        self.company.setup_required = False
        self.company.name = '已有公司'
        self.company.save()
        with patch.dict(os.environ, {'ADMIN_PASSWORD': 'Different-Installer-Password-2026'}):
            call_command('init_system', stdout=io.StringIO())
        self.company.refresh_from_db()
        self.assertFalse(self.company.setup_required)
        self.assertEqual(self.company.name, '已有公司')
        self.assertEqual(self.submit().status_code, 409)

    def test_previously_open_company_edit_cannot_reopen_setup(self):
        from types import SimpleNamespace

        from apps.core.views import CompanySerializer, CompanyView

        stale = CompanySerializer(self.company, data={'phone': '010-87654321'}, partial=True)
        self.assertTrue(stale.is_valid())
        self.assertEqual(self.submit().status_code, 200)
        view = CompanyView()
        view.request = SimpleNamespace(user=self.admin)
        view.perform_update(stale)
        self.company.refresh_from_db()
        self.assertFalse(self.company.setup_required)
        self.assertIsNotNone(self.company.setup_completed_at)
        self.assertEqual(self.company.name, self.data['company']['name'])
        self.assertEqual(self.company.phone, '010-87654321')
