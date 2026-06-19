"""扫码登录 REST 端点(企业微信/钉钉/飞书)。

- GET  /api/auth/oauth/providers           可用登录方式(按是否配 secret)
- GET  /api/auth/oauth/<platform>/login-url 扫码授权 URL + state
- POST /api/auth/oauth/<platform>/callback  code+state → 身份 → 建号/绑定 → 发 JWT(同密码登录)

均免鉴权(AllowAny);login-url/callback 复用密码登录的 login 限流。
"""
import logging

from django.conf import settings
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.serializers import UserProfileSerializer

from .base import OAuthError, all_providers, get_provider
from .services import build_redirect_uri, consume_code_once, find_or_create_user, issue_state, verify_state

logger = logging.getLogger(__name__)


def _login_throttles():
    return [ScopedRateThrottle] if settings.LOGIN_THROTTLE_ENABLED else []


class OAuthProvidersView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response([
            {'platform': p.platform, 'name': p.display_name, 'enabled': p.is_configured()}
            for p in all_providers()
        ])


class OAuthLoginURLView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = 'login'
    throttle_classes = _login_throttles()

    def get(self, request, platform):
        try:
            provider = get_provider(platform)
        except OAuthError:
            return Response({'detail': '未知登录平台'}, status=404)
        if not provider.is_configured():
            return Response({'detail': '该登录方式未启用'}, status=400)
        state = issue_state(platform)
        return Response({'auth_url': provider.get_authorize_url(state, build_redirect_uri(platform)), 'state': state})


class OAuthCallbackView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = 'login'
    throttle_classes = _login_throttles()

    def post(self, request, platform):
        return self._handle(request, platform)

    def get(self, request, platform):
        return self._handle(request, platform)

    def _handle(self, request, platform):
        code = request.data.get('code') or request.query_params.get('code')
        state = request.data.get('state') or request.query_params.get('state')
        if not code or not state:
            return Response({'detail': '缺少 code 或 state'}, status=400)
        if not verify_state(state, platform):
            return Response({'detail': '登录状态校验失败(state 无效或已过期),请重新扫码'}, status=400)
        if not consume_code_once(platform, code):
            return Response({'detail': '该登录码已使用,请重新扫码'}, status=400)

        try:
            provider = get_provider(platform)
        except OAuthError:
            return Response({'detail': '未知登录平台'}, status=404)
        if not provider.is_configured():
            return Response({'detail': '该登录方式未启用'}, status=400)

        try:
            identity = provider.resolve_identity(code)
        except OAuthError as e:
            logger.warning('OAuth %s 身份解析失败: %s', platform, e)
            return Response({'detail': str(e)}, status=400)
        except Exception:
            logger.exception('OAuth %s 回调异常', platform)
            return Response({'detail': '第三方登录失败,请稍后重试'}, status=502)

        user, created = find_or_create_user(platform, identity)
        if user is None:
            return Response({'detail': '账号不存在且未开启自动建号,请联系管理员'}, status=403)
        if not user.is_active:
            return Response({'detail': '账号未激活,请联系管理员'}, status=403)

        _audit(user, platform, created)
        refresh = RefreshToken.for_user(user)
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserProfileSerializer(user).data,
            'is_new_user': created,
        })


def _audit(user, platform, created):
    try:
        from apps.core.models import AuditLog
        AuditLog.objects.create(
            user=user,
            action='CREATE' if created else 'UPDATE',
            model_name='User',
            object_id=str(user.id),
            object_repr=('%s 扫码%s: %s' % (platform, '首登自动建号' if created else '登录', user.username)),
        )
    except Exception:
        logger.debug('OAuth 审计写入失败', exc_info=True)
