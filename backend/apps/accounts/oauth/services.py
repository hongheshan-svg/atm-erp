"""扫码登录的用户匹配/建号 + state/code 安全工具。

find_or_create_user 三步:① 按 <platform>_id 绑定查;② 按 phone>email 匹配既有用户并回填(仅当为空);
③ 自动建号(employee 最小权限,fail-closed)。并发重复建号由 select_for_update + DB partial unique 兜底。
"""
import hashlib
import logging
import uuid

from django.conf import settings
from django.core import signing
from django.core.cache import cache
from django.db import IntegrityError, transaction

from apps.accounts.models import Department, Role, User

from .base import OAuthError, OAuthIdentity

logger = logging.getLogger(__name__)

PROVIDER_ID_FIELD = {'wecom': 'wechat_work_id', 'dingtalk': 'dingtalk_id', 'feishu': 'feishu_id'}

_STATE_SALT = 'accounts.oauth.scan-login.state'
_STATE_MAX_AGE = 300  # 秒


# ── state / code 安全 ───────────────────────────────────────────────────────

def issue_state(platform: str) -> str:
    """签名 state(无状态 CSRF 防护,自带过期)。"""
    return signing.dumps({'p': platform, 'n': uuid.uuid4().hex}, salt=_STATE_SALT)


def verify_state(state: str, platform: str) -> bool:
    try:
        data = signing.loads(state, salt=_STATE_SALT, max_age=_STATE_MAX_AGE)
    except signing.BadSignature:
        return False
    return data.get('p') == platform


def consume_code_once(platform: str, code: str) -> bool:
    """同一 code 只接受一次(防重放)。返回 False 表示已用过。"""
    key = 'oauth_code:%s:%s' % (platform, hashlib.sha256(code.encode()).hexdigest())
    return cache.add(key, 1, 300)


def build_redirect_uri(platform: str) -> str:
    """前端回调地址(含 base path /erp/)。后端自拼,不取自请求,防开放重定向/SSRF。"""
    base = settings.FRONTEND_URL.rstrip('/')
    return f'{base}/erp/login/callback?platform={platform}'


# ── 用户匹配 / 建号 ─────────────────────────────────────────────────────────

def _normalize_mobile(m: str) -> str:
    if not m:
        return ''
    m = m.strip().replace(' ', '').replace('-', '')
    if m.startswith('+86'):
        m = m[3:]
    elif m.startswith('86') and len(m) > 11:
        m = m[2:]
    return m


def _domain_allowed(email: str) -> bool:
    domains = settings.OAUTH_ALLOWED_EMAIL_DOMAINS
    if not domains:
        return True
    if not email or '@' not in email:
        return False
    return email.rsplit('@', 1)[1].lower() in domains


def _is_privileged_account(user) -> bool:
    """特权账号:superuser/staff 或拥有 system 权限。禁止经扫码自动绑定/登录(防账号接管)。"""
    if user.is_superuser or user.is_staff:
        return True
    try:
        from apps.core.permission_service import get_user_permissions

        perms = get_user_permissions(user)
    except Exception:  # noqa: BLE001
        return False
    return any(p == 'system' or p.startswith('system:') for p in perms)


def _match_existing(identity: OAuthIdentity):
    # 仅按 phone 匹配(IM 平台核验过的登录手机号)。**不按 email 匹配**——email 多为用户可改/易冒名,
    # 用其绑定既有账号会导致账号接管(安全评审 HIGH)。email 仅用于新建账号填充,不作匹配键。
    mobile = _normalize_mobile(identity.mobile)
    if not mobile:
        return None
    return User.objects.filter(is_deleted=False, phone=mobile).first()


def _unique_username(identity: OAuthIdentity, platform: str) -> str:
    base = (
        _normalize_mobile(identity.mobile)
        or (identity.email.split('@')[0] if identity.email else '')
        or f'{platform}_{identity.external_id[:12]}'
    )
    candidate, i = base, 1
    while User.objects.filter(username=candidate).exists():
        i += 1
        candidate = f'{base}_{i}'
    return candidate


def _split_name(user: User, name: str) -> None:
    name = (name or '').strip()
    if not name:
        return
    # 中文姓名:首字为姓,其余为名(get_full_name = last_name + first_name)
    user.last_name = name[0]
    user.first_name = name[1:]


def _auto_create(platform: str, id_field: str, identity: OAuthIdentity) -> User:
    user = User.objects.create_user(
        username=_unique_username(identity, platform),
        employee_id=f'EMP{uuid.uuid4().hex[:8].upper()}',
        email=identity.email or '',
        phone=_normalize_mobile(identity.mobile),
        is_active=settings.OAUTH_NEW_USER_ACTIVE,
        **{id_field: identity.external_id},
    )
    user.set_unusable_password()  # OAuth-only,不能走密码登录
    _split_name(user, identity.name)
    if identity.dept_name:
        dept = Department.objects.filter(is_deleted=False, name=identity.dept_name).first()
        if dept:
            user.department = dept
    user.save()
    # 默认角色:FK(role) + M2M(roles)双写 —— permission_service 双源读取
    role = Role.objects.filter(code=settings.OAUTH_DEFAULT_ROLE_CODE, is_deleted=False, is_active=True).first()
    if role:
        user.role = role
        user.save(update_fields=['role'])
        user.roles.add(role)
    logger.info('OAuth 首登自动建号: platform=%s user_id=%s', platform, user.id)
    return user


def _find_or_create(platform: str, identity: OAuthIdentity):
    id_field = PROVIDER_ID_FIELD[platform]
    ext = identity.external_id
    with transaction.atomic():
        # (1) 已绑定:按 <platform>_id 直接查(行锁防并发双开)
        bound = (
            User.objects.select_for_update()
            .filter(is_deleted=False, **{id_field: ext})
            .exclude(**{id_field: ''})
            .first()
        )
        if bound:
            return bound, False
        # (2) 命中既有账号(按 phone):默认**不**自动绑定/登入,防账号接管(安全评审 HIGH)。
        matched = _match_existing(identity)
        if matched:
            if _is_privileged_account(matched):
                # 特权账号始终拒绝扫码自动绑定:必须密码登录或管理员显式绑定
                raise OAuthError('该账号涉及管理权限,不能通过扫码登录;请用密码登录或联系管理员')
            if not settings.OAUTH_BIND_EXISTING_BY_PHONE:
                raise OAuthError('该手机号已存在 ERP 账号;请用密码登录,或联系管理员绑定企业 IM 后再扫码')
            # 显式开启后:仅按 IM 核验手机号绑定非特权账号,且仅在 *_id 为空时回填(不覆盖手工值)
            if not getattr(matched, id_field):
                setattr(matched, id_field, ext)
                matched.save(update_fields=[id_field])
            return matched, False
        # (3) 自动建号(受开关 + 域白名单约束;fail-closed)
        if not settings.OAUTH_AUTO_CREATE:
            return None, False
        if not _domain_allowed(identity.email):
            return None, False
        return _auto_create(platform, id_field, identity), True


def find_or_create_user(platform: str, identity: OAuthIdentity):
    """返回 (User|None, created)。None 表示未匹配且未开启自动建号(或域不允许)。"""
    try:
        return _find_or_create(platform, identity)
    except IntegrityError:
        # 并发建号撞 partial unique:重查绑定返回已存在用户
        id_field = PROVIDER_ID_FIELD[platform]
        u = (
            User.objects.filter(is_deleted=False, **{id_field: identity.external_id})
            .exclude(**{id_field: ''})
            .first()
        )
        if u:
            return u, False
        raise
