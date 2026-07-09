"""
登录失败锁定 + 登录日志回归测试（P1 安全修复）。

修复点：CustomTokenObtainPairSerializer 原来只调用 super().validate()，
既不写 LoginLog 也不检查/执行账户锁定——security.py 里的
PasswordPolicy.check_account_lockout / SecurityService.log_login 形同死代码。
本用例锁定：
- 每次失败登录写一条 status=FAILED 的 LoginLog；
- 连续失败达 MAX_LOGIN_ATTEMPTS 后账户被锁，即使密码正确也拒绝，并写 LOCKED 日志；
- 成功登录写 status=SUCCESS 日志。

直接实例化序列化器（绕过 URL/DRF 限流），避免登录限流(5/min)与锁定逻辑相互干扰。
"""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.test import APIRequestFactory

from apps.accounts.views import CustomTokenObtainPairSerializer
from apps.core.security import LoginLog

User = get_user_model()
factory = APIRequestFactory()

CORRECT_PASSWORD = 'CorrectPass1!'


@override_settings(MAX_LOGIN_ATTEMPTS=5, LOCKOUT_DURATION_MINUTES=30)
class LoginLockoutTest(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username='alice', password=CORRECT_PASSWORD, employee_id='alice'
        )

    def _attempt(self, password):
        request = factory.post('/api/auth/login/')
        serializer = CustomTokenObtainPairSerializer(
            data={'username': 'alice', 'password': password},
            context={'request': request},
        )
        # is_valid() 会让 validate() 抛出的 AuthenticationFailed 直接透传（非 ValidationError）
        return serializer

    def test_failed_login_writes_log(self):
        with self.assertRaises(AuthenticationFailed):
            self._attempt('wrong-password').is_valid()
        logs = LoginLog.objects.filter(username='alice', status='FAILED')
        self.assertEqual(logs.count(), 1)

    def test_failed_login_message_is_generic(self):
        # 不泄露是用户名不存在还是密码错误
        with self.assertRaises(AuthenticationFailed) as ctx:
            self._attempt('wrong-password').is_valid()
        self.assertIn('用户名或密码错误', str(ctx.exception.detail))

    def test_lockout_after_max_attempts(self):
        for _ in range(5):
            with self.assertRaises(AuthenticationFailed):
                self._attempt('wrong-password').is_valid()

        self.assertEqual(
            LoginLog.objects.filter(username='alice', status='FAILED').count(), 5
        )

        # 第 6 次即使密码正确也应被锁定拒绝
        with self.assertRaises(AuthenticationFailed) as ctx:
            self._attempt(CORRECT_PASSWORD).is_valid()
        self.assertEqual(ctx.exception.detail.code, 'account_locked')
        self.assertTrue(
            LoginLog.objects.filter(username='alice', status='LOCKED').exists()
        )

    def test_successful_login_writes_log(self):
        serializer = self._attempt(CORRECT_PASSWORD)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertIn('access', serializer.validated_data)
        self.assertTrue(
            LoginLog.objects.filter(username='alice', status='SUCCESS').exists()
        )
