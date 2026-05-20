"""
Security enhancements: login logging, password policy, sensitive operation confirmation.
"""

import logging
import re
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

logger = logging.getLogger(__name__)


class LoginLog(models.Model):
    """
    Login attempt logging for security audit.
    """

    STATUS_CHOICES = [
        ('SUCCESS', '成功'),
        ('FAILED', '失败'),
        ('LOCKED', '账户锁定'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='login_logs',
        verbose_name='用户',
    )
    username = models.CharField(max_length=150, verbose_name='用户名')
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP地址')
    user_agent = models.TextField(blank=True, verbose_name='用户代理')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, verbose_name='状态')
    failure_reason = models.CharField(max_length=200, blank=True, verbose_name='失败原因')
    login_time = models.DateTimeField(auto_now_add=True, verbose_name='登录时间', db_index=True)
    location = models.CharField(max_length=200, blank=True, verbose_name='登录地点')
    device_type = models.CharField(max_length=50, blank=True, verbose_name='设备类型')

    class Meta:
        db_table = 'login_log'
        verbose_name = '登录日志'
        verbose_name_plural = verbose_name
        ordering = ['-login_time']
        indexes = [
            models.Index(fields=['username', '-login_time']),
            models.Index(fields=['ip_address', '-login_time']),
        ]

    def __str__(self):
        return f'{self.username} - {self.status} - {self.login_time}'


class PasswordPolicy:
    """
    Password policy enforcement.
    """

    # Default policy settings
    MIN_LENGTH = 8
    REQUIRE_UPPERCASE = True
    REQUIRE_LOWERCASE = True
    REQUIRE_DIGIT = True
    REQUIRE_SPECIAL = True
    SPECIAL_CHARS = '!@#$%^&*()_+-=[]{}|;:,.<>?'
    PASSWORD_EXPIRY_DAYS = 90
    PASSWORD_HISTORY_COUNT = 5
    MAX_LOGIN_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 30

    @classmethod
    def validate_password(cls, password, user=None):
        """
        Validate password against policy.

        Returns:
            tuple: (is_valid, error_messages)
        """
        errors = []

        # Length check
        min_length = getattr(settings, 'PASSWORD_MIN_LENGTH', cls.MIN_LENGTH)
        if len(password) < min_length:
            errors.append(f'密码长度至少{min_length}位')

        # Uppercase check
        if getattr(settings, 'PASSWORD_REQUIRE_UPPERCASE', cls.REQUIRE_UPPERCASE):
            if not re.search(r'[A-Z]', password):
                errors.append('密码必须包含大写字母')

        # Lowercase check
        if getattr(settings, 'PASSWORD_REQUIRE_LOWERCASE', cls.REQUIRE_LOWERCASE):
            if not re.search(r'[a-z]', password):
                errors.append('密码必须包含小写字母')

        # Digit check
        if getattr(settings, 'PASSWORD_REQUIRE_DIGIT', cls.REQUIRE_DIGIT):
            if not re.search(r'\d', password):
                errors.append('密码必须包含数字')

        # Special character check
        if getattr(settings, 'PASSWORD_REQUIRE_SPECIAL', cls.REQUIRE_SPECIAL):
            special_chars = getattr(settings, 'PASSWORD_SPECIAL_CHARS', cls.SPECIAL_CHARS)
            if not any(c in special_chars for c in password):
                errors.append(f'密码必须包含特殊字符({special_chars[:10]}...)')

        # Check against username
        if user and user.username:
            if user.username.lower() in password.lower():
                errors.append('密码不能包含用户名')

        return len(errors) == 0, errors

    @classmethod
    def check_password_expiry(cls, user):
        """
        Check if user's password has expired.

        Returns:
            tuple: (is_expired, days_until_expiry)
        """
        expiry_days = getattr(settings, 'PASSWORD_EXPIRY_DAYS', cls.PASSWORD_EXPIRY_DAYS)

        if expiry_days <= 0:
            return False, None

        # Get last password change date
        last_change = getattr(user, 'password_changed_at', None)
        if not last_change:
            last_change = user.date_joined

        expiry_date = last_change + timedelta(days=expiry_days)
        days_until_expiry = (expiry_date - timezone.now()).days

        return days_until_expiry <= 0, days_until_expiry

    @classmethod
    def check_account_lockout(cls, username):
        """
        Check if account is locked due to failed login attempts.

        Returns:
            tuple: (is_locked, remaining_minutes)
        """
        max_attempts = getattr(settings, 'MAX_LOGIN_ATTEMPTS', cls.MAX_LOGIN_ATTEMPTS)
        lockout_minutes = getattr(settings, 'LOCKOUT_DURATION_MINUTES', cls.LOCKOUT_DURATION_MINUTES)

        # Get recent failed attempts
        cutoff_time = timezone.now() - timedelta(minutes=lockout_minutes)
        failed_attempts = LoginLog.objects.filter(
            username=username, status='FAILED', login_time__gte=cutoff_time
        ).count()

        if failed_attempts >= max_attempts:
            # Find the last failed attempt
            last_attempt = LoginLog.objects.filter(username=username, status='FAILED').order_by('-login_time').first()

            if last_attempt:
                unlock_time = last_attempt.login_time + timedelta(minutes=lockout_minutes)
                remaining = (unlock_time - timezone.now()).total_seconds() / 60
                if remaining > 0:
                    return True, int(remaining)

        return False, 0


class SensitiveOperationLog(models.Model):
    """
    Log for sensitive operations requiring confirmation.
    """

    OPERATION_TYPES = [
        ('DELETE', '删除'),
        ('BULK_DELETE', '批量删除'),
        ('EXPORT', '数据导出'),
        ('PASSWORD_RESET', '密码重置'),
        ('ROLE_CHANGE', '角色变更'),
        ('PERMISSION_CHANGE', '权限变更'),
        ('SYSTEM_CONFIG', '系统配置'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='sensitive_operations',
        verbose_name='操作用户',
    )
    operation_type = models.CharField(max_length=30, choices=OPERATION_TYPES, verbose_name='操作类型')
    target_model = models.CharField(max_length=100, verbose_name='目标模型')
    target_id = models.CharField(max_length=100, blank=True, verbose_name='目标ID')
    target_desc = models.CharField(max_length=500, verbose_name='目标描述')
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP地址')
    confirmed = models.BooleanField(default=False, verbose_name='已确认')
    confirmed_at = models.DateTimeField(null=True, blank=True, verbose_name='确认时间')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'sensitive_operation_log'
        verbose_name = '敏感操作日志'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user} - {self.get_operation_type_display()} - {self.target_desc}'


class SecurityService:
    """
    Security service for common operations.
    """

    @classmethod
    def log_login(cls, request, username, status, failure_reason='', user=None):
        """
        Log a login attempt.
        """
        ip_address = cls.get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
        device_type = cls.detect_device_type(user_agent)

        LoginLog.objects.create(
            user=user,
            username=username,
            ip_address=ip_address,
            user_agent=user_agent,
            status=status,
            failure_reason=failure_reason,
            device_type=device_type,
        )

    @classmethod
    def get_client_ip(cls, request):
        """
        Get client IP address from request.
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

    @classmethod
    def detect_device_type(cls, user_agent):
        """
        Detect device type from user agent.
        """
        user_agent = user_agent.lower()
        if 'mobile' in user_agent or 'android' in user_agent:
            return 'Mobile'
        elif 'tablet' in user_agent or 'ipad' in user_agent:
            return 'Tablet'
        elif 'miniprogram' in user_agent or 'micromessenger' in user_agent:
            return 'WeChat'
        else:
            return 'Desktop'

    @classmethod
    def log_sensitive_operation(cls, request, operation_type, target_model, target_id, target_desc):
        """
        Log a sensitive operation.
        """
        return SensitiveOperationLog.objects.create(
            user=request.user if request.user.is_authenticated else None,
            operation_type=operation_type,
            target_model=target_model,
            target_id=str(target_id) if target_id else '',
            target_desc=target_desc,
            ip_address=cls.get_client_ip(request),
        )

    @classmethod
    def get_login_history(cls, user, days=30):
        """
        Get login history for a user.
        """
        cutoff = timezone.now() - timedelta(days=days)
        return LoginLog.objects.filter(user=user, login_time__gte=cutoff).order_by('-login_time')
