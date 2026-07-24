"""
审计日志脱敏回归测试（P1 安全修复）。

修复点：AuditLogMiddleware 原样把请求体 json.loads 进 AuditLog.changes，
创建用户/改密/重置密码等接口的明文密码/令牌会被永久写入审计表。
本用例锁定敏感键在入库前被递归脱敏。
"""

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from apps.core.middleware import AuditLogMiddleware, mask_sensitive
from apps.core.models import AuditLog

User = get_user_model()
factory = APIRequestFactory()


class MaskSensitiveUnitTest(TestCase):
    def test_masks_top_level_and_nested(self):
        payload = {
            'username': 'bob',
            'password': 'S3cret!',
            'new_password': 'Another1!',
            'profile': {'old_password': 'x', 'email': 'b@x.com'},
            'items': [{'api_key': 'k-123', 'name': 'ok'}],
            'access': 'jwt-access',
            'refresh': 'jwt-refresh',
        }
        masked = mask_sensitive(payload)

        self.assertEqual(masked['password'], '***')
        self.assertEqual(masked['new_password'], '***')
        self.assertEqual(masked['profile']['old_password'], '***')
        self.assertEqual(masked['items'][0]['api_key'], '***')
        self.assertEqual(masked['access'], '***')
        self.assertEqual(masked['refresh'], '***')
        # 非敏感字段保持不变
        self.assertEqual(masked['username'], 'bob')
        self.assertEqual(masked['profile']['email'], 'b@x.com')
        self.assertEqual(masked['items'][0]['name'], 'ok')

    def test_stem_variants_masked(self):
        masked = mask_sensitive(
            {'user_password': 'p', 'access_token': 't', 'client_secret': 's', 'count': 3}
        )
        self.assertEqual(masked['user_password'], '***')
        self.assertEqual(masked['access_token'], '***')
        self.assertEqual(masked['client_secret'], '***')
        self.assertEqual(masked['count'], 3)


class AuditMiddlewareMaskingTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='auditor', password='x', employee_id='auditor'
        )

    def test_middleware_masks_password_in_changes(self):
        request = factory.post(
            '/api/accounts/users/',
            data={'username': 'newuser', 'password': 'PlainText1!'},
            format='json',
        )
        request.user = self.user
        response = HttpResponse(status=201)

        AuditLogMiddleware(lambda r: response).process_response(request, response)

        log = AuditLog.objects.order_by('-id').first()
        self.assertIsNotNone(log)
        self.assertEqual(log.changes.get('password'), '***')
        self.assertEqual(log.changes.get('username'), 'newuser')
