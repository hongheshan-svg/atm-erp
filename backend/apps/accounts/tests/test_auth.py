from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.core.models import AuditLog, Company

PASSWORD = 'Test-Accounts-Only-982'


class AuthenticationTests(TestCase):
    @override_settings(APP_ENVIRONMENT='production')
    def test_forwarding_headers_cannot_rotate_direct_client_throttle(self):
        for i in range(12):
            response = self.client.post(
                '/api/auth/login/',
                {'username': 'missing', 'password': 'wrong'},
                REMOTE_ADDR='198.51.100.10',
                HTTP_X_FORWARDED_FOR=f'203.0.113.{i}',
                HTTP_X_REAL_IP=f'203.0.113.{i}',
            )
            self.assertEqual(response.status_code, 401 if i < 10 else 429)

    @override_settings(APP_ENVIRONMENT='production')
    def test_trusted_proxy_uses_single_canonical_address_and_rejects_chains(self):
        from rest_framework.test import APIRequestFactory

        from apps.accounts.api import LoginThrottle

        factory = APIRequestFactory()
        throttle = LoginThrottle()
        for value in ['not-an-ip', '203.0.113.1, 203.0.113.2', '', '::ffff:192.0.2.1, bad']:
            self.assertEqual(
                throttle.get_ident(factory.get('/', REMOTE_ADDR='127.0.0.1', HTTP_X_FORWARDED_FOR=value)), '127.0.0.1'
            )
        self.assertEqual(
            throttle.get_ident(factory.get('/', REMOTE_ADDR='127.0.0.1', HTTP_X_FORWARDED_FOR='2001:0db8::1')),
            '2001:db8::1',
        )
        for address in ['203.0.113.1', '203.0.113.2']:
            for i in range(11):
                response = self.client.post(
                    '/api/auth/refresh/', {'refresh': 'invalid'}, REMOTE_ADDR='127.0.0.1', HTTP_X_FORWARDED_FOR=address
                )
                self.assertEqual(response.status_code, 401 if i < 10 else 429)

    def setUp(self):
        cache.clear()
        Company.objects.create(pk=1)
        self.users = {
            role: User.objects.create_user(username=role, password=PASSWORD, role=role) for role in User.Role.values
        }
        self.client = APIClient()

    def login(self, role='admin', *, remote_addr='127.0.0.1'):
        response = self.client.post(
            '/api/auth/login/', {'username': role, 'password': PASSWORD}, REMOTE_ADDR=remote_addr
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {response.data["access"]}')
        return response.data

    def test_fixed_roles_login_and_read_safe_profile(self):
        # These are distinct users' clients, not eleven attempts from one IP.
        # Production's ten-attempt throttle is independently exercised below.
        for index, role in enumerate(User.Role.values, 1):
            self.login(role, remote_addr=f'198.51.100.{index}')
            response = self.client.get('/api/auth/me/')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['role'], role)
            self.assertEqual(response.data['roles'], [role])
            self.assertEqual(
                set(response.data),
                {'id', 'username', 'display_name', 'role', 'roles', 'management_reports', 'setup_required'},
            )

    def test_all_fixed_roles_can_be_assigned_and_unknown_roles_are_rejected(self):
        self.login()
        selected = list(User.Role.values)
        self.assertEqual(len(selected), 11)
        self.assertEqual(
            dict(User.Role.choices),
            {
                'admin': '管理员',
                'manager': '项目经理',
                'production_manager': '生产经理',
                'sales_manager': '销售经理',
                'purchase_manager': '采购经理',
                'purchaser': '采购员',
                'warehouse': '仓管',
                'finance': '财务',
                'mechanical_engineer': '机械工程师',
                'electrical_engineer': '电气工程师',
                'member': '普通成员',
            },
        )
        response = self.client.post(
            '/api/auth/users/', {'username': 'all-fixed-roles', 'roles': selected, 'password': PASSWORD}, format='json'
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['roles'], sorted(selected))
        created = User.objects.get(pk=response.data['id'])
        self.assertEqual(created.additional_roles, selected[1:])
        self.assertNotIn('password', response.data)
        before = User.objects.count()
        audits = AuditLog.objects.count()
        for invalid in [selected + ['admin'], ['mechanical_engineer', 'unlisted'], ['purchase_manager'] * 2]:
            with self.subTest(roles=invalid):
                response = self.client.post(
                    '/api/auth/users/',
                    {'username': 'invalid-roles', 'roles': invalid, 'password': PASSWORD},
                    format='json',
                )
                self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(User.objects.count(), before)
        self.assertEqual(AuditLog.objects.count(), audits)
        updated = self.client.patch(
            f'/api/auth/users/{created.pk}/',
            {'roles': ['electrical_engineer', 'mechanical_engineer']},
            format='json',
        )
        self.assertEqual(updated.status_code, 200, updated.data)
        created.refresh_from_db()
        self.assertEqual(created.role, 'electrical_engineer')
        self.assertEqual(created.additional_roles, ['mechanical_engineer'])

    def test_specialist_roles_appear_in_directory_and_secondary_role_filters(self):
        self.login()
        selected = ['mechanical_engineer', 'purchase_manager', 'electrical_engineer', 'production_manager']
        response = self.client.post(
            '/api/auth/users/',
            {'username': 'combined-specialist', 'roles': selected, 'password': PASSWORD},
            format='json',
        )
        self.assertEqual(response.status_code, 201, response.data)
        identity = response.data['id']
        for role in selected:
            response = self.client.get('/api/auth/users/', {'role': role, 'is_active': 'true'})
            self.assertEqual(response.status_code, 200)
            self.assertEqual({row['id'] for row in response.data['results']}, {identity, self.users[role].pk})
        directory = self.client.get('/api/auth/directory/')
        account = next(row for row in directory.data if row['id'] == identity)
        self.assertEqual(account['roles'], sorted(selected))
        self.assertEqual(set(account), {'id', 'display_name', 'role', 'roles'})
        self.assertEqual(self.client.patch(f'/api/auth/users/{identity}/', {'is_active': False}).status_code, 200)
        self.assertNotIn(identity, [row['id'] for row in self.client.get('/api/auth/directory/').data])

    def test_specialist_roles_do_not_implicitly_gain_management_reports(self):
        self.login()
        for role in ['purchase_manager', 'mechanical_engineer', 'electrical_engineer', 'production_manager']:
            response = self.client.patch(
                f'/api/auth/users/{self.users[role].pk}/', {'management_reports': True}, format='json'
            )
            self.assertEqual(response.status_code, 400, response.data)
        for role in ['purchase_manager', 'mechanical_engineer', 'electrical_engineer', 'production_manager']:
            self.login(role)
            self.assertEqual(self.client.get('/api/business/reports/').status_code, 403)
            self.assertFalse(self.client.get('/api/auth/me/').data['management_reports'])
        self.login()
        response = self.client.patch(
            f'/api/auth/users/{self.users["purchase_manager"].pk}/',
            {'roles': ['purchase_manager', 'manager'], 'management_reports': True},
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.login('purchase_manager')
        self.assertEqual(self.client.get('/api/business/reports/').status_code, 200)

    def test_fixed_primary_role_database_constraint_rejects_unlisted_role(self):
        before = list(User.objects.values('id', 'role', 'additional_roles'))
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.filter(pk=self.users['admin'].pk).update(role='unlisted')
        self.assertEqual(list(User.objects.values('id', 'role', 'additional_roles')), before)

    def test_setup_accepts_specialist_team_without_granting_management_reports(self):
        self.login()
        Company.objects.filter(pk=1).update(setup_required=True)
        selected = ['purchase_manager', 'mechanical_engineer', 'electrical_engineer', 'production_manager']
        response = self.client.post(
            '/api/core/setup/',
            {
                'display_name': '安装管理员',
                'old_password': PASSWORD,
                'new_password': 'Ready-Specialist-Team-2026-only',
                'company': {'name': '角色验证自动化公司', 'address': '测试园区', 'phone': '010-12345678'},
                'team': [{'username': f'setup-{role}', 'roles': [role], 'password': PASSWORD} for role in selected],
                'codes': [],
                'confirmed': True,
            },
            format='json',
            HTTP_IDEMPOTENCY_KEY='specialist-team-setup',
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(Company.objects.get(pk=1).setup_required)
        for role in selected:
            created = User.objects.get(username=f'setup-{role}')
            self.assertEqual((created.role, created.additional_roles, created.management_reports), (role, [], False))
            self.assertEqual(
                AuditLog.objects.get(operation='user.create', resource=f'user:{created.pk}').detail,
                {'roles': [role], 'management_reports': False},
            )

    def test_report_access_requires_explicit_admin_grant_and_revokes_immediately(self):
        self.login('admin')
        url = f'/api/auth/users/{self.users["manager"].pk}/'
        self.assertEqual(self.client.patch(url, {'management_reports': True}, format='json').status_code, 200)
        member_url = f'/api/auth/users/{self.users["member"].pk}/'
        self.assertEqual(self.client.patch(member_url, {'management_reports': True}, format='json').status_code, 400)
        self.login('manager')
        self.assertEqual(self.client.get('/api/business/reports/').status_code, 200)
        self.assertEqual(self.client.patch(url, {'management_reports': True}, format='json').status_code, 403)
        User.objects.filter(pk=self.users['manager'].pk).update(management_reports=False)
        self.assertEqual(self.client.get('/api/business/reports/').status_code, 403)
        detail = AuditLog.objects.filter(operation='user.update').latest('id').detail
        self.assertEqual(detail['management_reports'], {'before': False, 'after': True})

    def test_only_admin_can_manage_users_or_read_rates(self):
        for index, role in enumerate(User.Role.values, 1):
            self.login(role, remote_addr=f'198.51.100.{index}')
            response = self.client.get('/api/auth/users/')
            self.assertEqual(response.status_code, 200 if role == 'admin' else 403)
            directory = self.client.get('/api/auth/directory/')
            self.assertEqual(directory.status_code, 200)
        self.assertTrue(all(set(row) == {'id', 'display_name', 'role', 'roles'} for row in directory.data))

    def test_deactivated_user_loses_access_and_refresh(self):
        tokens = self.login('member')
        User.objects.filter(pk=self.users['member'].pk).update(is_active=False)
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 401)
        self.assertEqual(self.client.post('/api/auth/refresh/', {'refresh': tokens['refresh']}).status_code, 401)

    def test_password_change_revokes_access_and_refresh(self):
        tokens = self.login('member')
        response = self.client.post(
            '/api/auth/password/', {'old_password': PASSWORD, 'new_password': 'Changed-Only-For-Tests-893'}
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 401)
        self.assertEqual(self.client.post('/api/auth/refresh/', {'refresh': tokens['refresh']}).status_code, 401)
        self.assertNotIn('Changed-Only', str(list(AuditLog.objects.values('detail'))))

    def test_wrong_original_password_does_not_change_password(self):
        self.login('member')
        response = self.client.post(
            '/api/auth/password/', {'old_password': 'incorrect', 'new_password': 'Changed-Only-For-Tests-893'}
        )
        self.assertEqual(response.status_code, 400)
        self.users['member'].refresh_from_db()
        self.assertTrue(self.users['member'].check_password(PASSWORD))

    def test_password_rejects_non_object_json_without_changing_credentials(self):
        self.login('member')
        self.client.raise_request_exception = False
        before = self.users['member'].password
        for payload in [[], ['invalid'], 'invalid', 123, True]:
            with self.subTest(payload=payload):
                response = self.client.post('/api/auth/password/', payload, format='json')
                self.assertEqual(response.status_code, 400)
        self.users['member'].refresh_from_db()
        self.assertEqual(self.users['member'].password, before)
        self.assertFalse(AuditLog.objects.filter(operation='user.password').exists())

    def test_last_admin_cannot_be_demoted_or_deactivated(self):
        self.login()
        url = f'/api/auth/users/{self.users["admin"].pk}/'
        for data in ({'role': 'member'}, {'is_active': False}):
            response = self.client.patch(url, data)
            self.assertEqual(response.status_code, 400, response.data)
        self.users['admin'].refresh_from_db()
        self.assertTrue(self.users['admin'].is_active)
        self.assertEqual(self.users['admin'].role, 'admin')

    def test_user_create_and_password_validation(self):
        self.login()
        response = self.client.post('/api/auth/users/', {'username': 'new', 'role': 'member', 'password': 'short'})
        self.assertEqual(response.status_code, 400)
        response = self.client.post(
            '/api/auth/users/', {'username': 'new', 'role': 'member', 'password': PASSWORD, 'is_superuser': True}
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertNotIn('password', response.data)
        self.assertFalse(User.objects.get(username='new').is_superuser)

    def test_public_uploads_and_removed_endpoints_do_not_exist(self):
        self.login()
        for url in ['/media/a.pdf', '/api/ai/chat/', '/api/oa/', '/api/production/', '/admin/']:
            self.assertEqual(self.client.get(url).status_code, 404)

    @override_settings(APP_ENVIRONMENT='production')
    def test_login_is_throttled(self):
        for _ in range(10):
            response = self.client.post('/api/auth/login/', {'username': 'member', 'password': 'incorrect'})
            self.assertEqual(response.status_code, 401)
        self.assertEqual(
            self.client.post('/api/auth/login/', {'username': 'member', 'password': PASSWORD}).status_code, 429
        )

    @override_settings(APP_ENVIRONMENT='development')
    def test_development_login_does_not_throttle(self):
        for _ in range(12):
            response = self.client.post('/api/auth/login/', {'username': 'member', 'password': 'incorrect'})
            self.assertEqual(response.status_code, 401)
        self.assertEqual(
            self.client.post('/api/auth/login/', {'username': 'member', 'password': PASSWORD}).status_code, 200
        )

    def test_environment_defaults_to_production_and_rejects_typos(self):
        import os
        import subprocess
        import sys

        env = dict(os.environ)
        env.pop('APP_ENVIRONMENT', None)
        for value, expected in [(None, 'production'), ('development', 'development'), ('develpment', None)]:
            current = env if value is None else {**env, 'APP_ENVIRONMENT': value}
            result = subprocess.run(
                [sys.executable, '-c', 'from config.settings import APP_ENVIRONMENT; print(APP_ENVIRONMENT)'],
                env=current,
                capture_output=True,
                text=True,
            )
            if expected:
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), expected)
            else:
                self.assertNotEqual(result.returncode, 0)
