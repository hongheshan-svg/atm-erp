"""扫码登录 / 绑定 REST 端点(企业微信/钉钉/飞书)。

免鉴权(登录用):
- GET  /api/auth/oauth/providers            可用登录方式(按是否配 secret)
- GET  /api/auth/oauth/<platform>/login-url 扫码授权 URL + state(?mode=bind 走绑定回调)
- POST /api/auth/oauth/<platform>/callback  code+state → 身份 → 建号/绑定 → 发 JWT(同密码登录)

需鉴权(自助绑定用):
- GET    /api/auth/oauth/bindings            当前用户各平台绑定状态
- POST   /api/auth/oauth/<platform>/bind     已登录用户把自己的 IM 身份绑定到本账号(安全显式绑定)
- DELETE /api/auth/oauth/<platform>/bind     解绑

login-url/callback 复用密码登录的 login 限流。
"""
import logging

from django.conf import settings
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.serializers import UserProfileSerializer

from .base import OAuthError, all_providers, get_provider
from .services import (
    PROVIDER_ID_FIELD,
    bind_identity_to_user,
    build_redirect_uri,
    consume_code_once,
    find_or_create_user,
    issue_state,
    unbind_platform,
    verify_state,
)

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


# state 绑定到本浏览器的 HttpOnly cookie(防登录 CSRF):回调要求 cookie==提交的 state。
STATE_COOKIE = 'erp_oauth_state'
STATE_COOKIE_PATH = '/api'


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
        mode = 'bind' if request.query_params.get('mode') == 'bind' else 'login'
        state = issue_state(platform)
        resp = Response({
            'auth_url': provider.get_authorize_url(state, build_redirect_uri(platform, mode)),
            'state': state,
        })
        # 把 state 钉到发起扫码的这个浏览器;回调若 cookie 缺失/不符即拒绝,防止被诱导登入他人账号。
        resp.set_cookie(
            STATE_COOKIE, state, max_age=300, httponly=True,
            samesite='Lax', secure=request.is_secure(), path=STATE_COOKIE_PATH,
        )
        return resp


def _verify_and_resolve(request, platform):
    """共享校验:code/state 存在 → 签名 → cookie 绑定 → code 一次性 → provider 解析身份。
    返回 (identity, None) 或 (None, error_Response)。"""
    code = request.data.get('code') or request.query_params.get('code')
    state = request.data.get('state') or request.query_params.get('state')
    if not code or not state:
        return None, Response({'detail': '缺少 code 或 state'}, status=400)
    if not verify_state(state, platform):
        return None, Response({'detail': '登录状态校验失败(state 无效或已过期),请重新扫码'}, status=400)
    cookie_state = request.COOKIES.get(STATE_COOKIE)
    if not cookie_state or cookie_state != state:
        return None, Response({'detail': '登录状态校验失败(请在发起扫码的同一浏览器完成),请重新扫码'}, status=400)
    if not consume_code_once(platform, code):
        return None, Response({'detail': '该登录码已使用,请重新扫码'}, status=400)
    try:
        provider = get_provider(platform)
    except OAuthError:
        return None, Response({'detail': '未知登录平台'}, status=404)
    if not provider.is_configured():
        return None, Response({'detail': '该登录方式未启用'}, status=400)
    try:
        return provider.resolve_identity(code), None
    except OAuthError as e:
        logger.warning('OAuth %s 身份解析失败: %s', platform, e)
        return None, Response({'detail': str(e)}, status=400)
    except Exception:
        logger.exception('OAuth %s 回调异常', platform)
        return None, Response({'detail': '第三方登录失败,请稍后重试'}, status=502)


class OAuthCallbackView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = 'login'
    throttle_classes = _login_throttles()

    def post(self, request, platform):
        return self._handle(request, platform)

    def get(self, request, platform):
        return self._handle(request, platform)

    def _handle(self, request, platform):
        identity, err = _verify_and_resolve(request, platform)
        if err is not None:
            return err
        try:
            user, created = find_or_create_user(platform, identity)
        except OAuthError as e:
            # 既有账号需显式绑定 / 特权账号拒绝 / 绑定未开启等(防账号接管)
            logger.warning('OAuth %s 绑定/建号被拒: %s', platform, e)
            return Response({'detail': str(e)}, status=403)
        if user is None:
            return Response({'detail': '账号不存在且未开启自动建号,请联系管理员'}, status=403)
        if not user.is_active:
            return Response({'detail': '账号未激活,请联系管理员'}, status=403)

        _audit(user, platform, '首登自动建号' if created else '登录')
        refresh = RefreshToken.for_user(user)
        resp = Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserProfileSerializer(user).data,
            'is_new_user': created,
        })
        resp.delete_cookie(STATE_COOKIE, path=STATE_COOKIE_PATH)  # state 一次性
        return resp


class OAuthBindingsView(APIView):
    """当前用户各平台绑定状态(供个人中心展示)。"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        out = []
        for p in all_providers():
            id_field = PROVIDER_ID_FIELD.get(p.platform, '')
            bound = bool(getattr(request.user, id_field, '')) if id_field else False
            out.append({'platform': p.platform, 'name': p.display_name, 'enabled': p.is_configured(), 'bound': bound})
        return Response(out)


class OAuthBindView(APIView):
    """已登录用户自助绑定/解绑自己的企业 IM 身份(安全显式绑定,无账号接管风险)。"""

    permission_classes = [IsAuthenticated]

    def post(self, request, platform):
        identity, err = _verify_and_resolve(request, platform)
        if err is not None:
            return err
        try:
            bind_identity_to_user(request.user, platform, identity)
        except OAuthError as e:
            return Response({'detail': str(e)}, status=409)  # 该 IM 已绑到他人
        _audit(request.user, platform, '自助绑定')
        resp = Response({'bound': True, 'platform': platform})
        resp.delete_cookie(STATE_COOKIE, path=STATE_COOKIE_PATH)
        return resp

    def delete(self, request, platform):
        try:
            get_provider(platform)  # 校验平台合法
        except OAuthError:
            return Response({'detail': '未知登录平台'}, status=404)
        unbind_platform(request.user, platform)
        _audit(request.user, platform, '解绑')
        return Response(status=204)


def _audit(user, platform, action_desc):
    try:
        from apps.core.models import AuditLog
        AuditLog.objects.create(
            user=user,
            action='CREATE' if action_desc == '首登自动建号' else 'UPDATE',
            model_name='User',
            object_id=str(user.id),
            object_repr=('%s 扫码%s: %s' % (platform, action_desc, user.username)),
        )
    except Exception:
        logger.debug('OAuth 审计写入失败', exc_info=True)
