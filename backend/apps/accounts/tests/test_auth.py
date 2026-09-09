from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.core.models import AuditLog, Company

PASSWORD = 'Test-Accounts-Only-982'


class AuthenticationTests(TestCase):
    def setUp(self):
        cache.clear()
        Company.objects.create(pk=1)
        self.users = {
            role: User.objects.create_user(username=role, password=PASSWORD, role=role) for role in User.Role.values
        }
        self.client = APIClient()

    def login(self, role='admin'):
        response = self.client.post('/api/auth/login/', {'username': role, 'password': PASSWORD})
        self.assertEqual(response.status_code, 200, response.data)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {response.data["access"]}')
        return response.data

    def test_six_roles_login_and_read_safe_profile(self):
        for role in User.Role.values:
            self.login(role)
            response = self.client.get('/api/auth/me/')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['role'], role)
            self.assertEqual(set(response.data), {'id', 'username', 'display_name', 'role'})

    def test_only_admin_can_manage_users_or_read_rates(self):
        for role in User.Role.values:
            self.login(role)
            response = self.client.get('/api/auth/users/')
            self.assertEqual(response.status_code, 200 if role == 'admin' else 403)
            directory = self.client.get('/api/auth/directory/')
            self.assertEqual(directory.status_code, 200)
            self.assertTrue(all(set(row) == {'id', 'display_name'} for row in directory.data))

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

    def test_login_is_throttled(self):
        for _ in range(10):
            response = self.client.post('/api/auth/login/', {'username': 'member', 'password': 'incorrect'})
            self.assertEqual(response.status_code, 401)
        self.assertEqual(
            self.client.post('/api/auth/login/', {'username': 'member', 'password': PASSWORD}).status_code, 429
        )
