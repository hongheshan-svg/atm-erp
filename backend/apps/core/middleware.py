"""
Middleware for audit logging
"""

import json
import logging

from django.utils.deprecation import MiddlewareMixin

from .models import AuditLog

logger = logging.getLogger(__name__)

# 需在审计日志中脱敏的键（精确匹配，小写）。
SENSITIVE_KEYS = {
    'password',
    'new_password',
    'old_password',
    'password_confirm',
    'new_password_confirm',
    'token',
    'access',
    'refresh',
    'secret',
    'authorization',
    'api_key',
    'apikey',
}

# 只要键名包含这些词根即视为敏感（覆盖 user_password / access_token / client_secret 等变体）。
SENSITIVE_KEY_STEMS = ('password', 'secret', 'token', 'api_key', 'apikey')

MASK = '***'


def _is_sensitive_key(key):
    if not isinstance(key, str):
        return False
    lowered = key.lower()
    if lowered in SENSITIVE_KEYS:
        return True
    return any(stem in lowered for stem in SENSITIVE_KEY_STEMS)


def mask_sensitive(value):
    """递归地对 dict/list 中的敏感字段值做脱敏，返回脱敏后的副本。

    审计日志的 changes 直接来自请求体（POST/PUT/PATCH），若原样入库会把
    创建用户、改密、重置密码等接口里的明文密码/令牌永久留在库中。
    """
    if isinstance(value, dict):
        return {k: (MASK if _is_sensitive_key(k) else mask_sensitive(v)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [mask_sensitive(item) for item in value]
    return value


class AuditLogMiddleware(MiddlewareMixin):
    """
    Middleware to automatically log API changes
    """

    def process_response(self, request, response):
        # Only log authenticated requests
        if not request.user.is_authenticated:
            return response

        # Only log specific methods
        if request.method not in ['POST', 'PUT', 'PATCH', 'DELETE']:
            return response

        # Don't log authentication endpoints
        if '/api/auth/login' in request.path or '/api/auth/refresh' in request.path:
            return response

        # Only log successful requests
        if response.status_code >= 400:
            return response

        try:
            # Extract model name from URL
            model_name = self._extract_model_name(request.path)
            action = self._map_method_to_action(request.method)

            # Get IP address
            ip_address = self._get_client_ip(request)

            # Get user agent
            user_agent = request.META.get('HTTP_USER_AGENT', '')

            # Try to extract changes（脱敏后再入库，绝不保存明文密码/令牌）
            changes = None
            if request.method in ['POST', 'PUT', 'PATCH']:
                try:
                    if hasattr(request, 'body'):
                        changes = mask_sensitive(json.loads(request.body.decode('utf-8')))
                except (ValueError, UnicodeDecodeError):
                    pass

            # Create audit log
            AuditLog.objects.create(
                user=request.user,
                action=action,
                model_name=model_name,
                object_repr=model_name,
                changes=changes,
                ip_address=ip_address,
                user_agent=user_agent[:200] if user_agent else None,
            )
        except Exception as e:
            # Don't break the request if audit logging fails
            logger.warning('Audit logging error: %s', e)

        return response

    def _extract_model_name(self, path):
        """Extract model name from API path"""
        parts = path.split('/')
        if len(parts) >= 3 and parts[1] == 'api':
            return parts[2]
        return 'unknown'

    def _map_method_to_action(self, method):
        """Map HTTP method to action"""
        mapping = {'POST': 'CREATE', 'PUT': 'UPDATE', 'PATCH': 'UPDATE', 'DELETE': 'DELETE'}
        return mapping.get(method, 'UPDATE')

    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
