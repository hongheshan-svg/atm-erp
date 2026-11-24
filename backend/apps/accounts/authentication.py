from django.core.cache import cache
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication

REVOKED_PREFIX = 'jwt.revoked.'


def is_revoked(token):
    jti = token.get('jti')
    return bool(jti and cache.get(f'{REVOKED_PREFIX}{jti}'))


def revoke_token(token):
    jti = token.get('jti')
    exp = token.get('exp')
    if not jti or exp is None:
        return
    ttl = int(exp) - int(timezone.now().timestamp())
    if ttl > 0:
        cache.set(f'{REVOKED_PREFIX}{jti}', 1, timeout=ttl + 5)


class RevocableJWTAuthentication(JWTAuthentication):
    def get_validated_token(self, raw_token):
        token = super().get_validated_token(raw_token)
        if is_revoked(token):
            raise AuthenticationFailed('登录状态已退出，请重新登录。')
        return token
