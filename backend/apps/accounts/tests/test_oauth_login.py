"""企业 IM 扫码登录 + 首登自动建号测试(打桩 resolve_identity,免真实 code/网络)。"""
from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.accounts.models import Role, User
from apps.accounts.oauth.base import OAuthError, OAuthIdentity
from apps.accounts.oauth.services import find_or_create_user, issue_state, verify_state
from apps.accounts.oauth.views import STATE_COOKIE
from apps.accounts.oauth.wecom import WeComProvider

CALLBACK = '/api/auth/oauth/wecom/callback'


class OAuthServiceTests(TestCase):
    """find_or_create_user 直测(不走 HTTP)。"""

    def setUp(self):
        self.employee = Role.objects.create(name='普通员工', code='employee', data_scope='SELF', is_active=True)

    def test_first_login_auto_creates_employee(self):
        ident = OAuthIdentity(external_id='wx_zhang', name='张三', mobile='13800138000', email='z@corp.com')
        user, created = find_or_create_user('wecom', ident)
        self.assertTrue(created)
        self.assertEqual(user.wechat_work_id, 'wx_zhang')
        self.assertEqual(user.phone, '13800138000')
        self.assertFalse(user.has_usable_password())  # OAuth-only
        self.assertTrue(user.is_active)
        self.assertIn(self.employee, user.roles.all())  # 默认 employee
        self.assertEqual(user.last_name + user.first_name, '张三')

    def test_second_login_binds_no_duplicate(self):
        ident = OAuthIdentity(external_id='wx_li', name='李四', mobile='13900139000')
        u1, c1 = find_or_create_user('wecom', ident)
        u2, c2 = find_or_create_user('wecom', ident)
        self.assertTrue(c1)
        self.assertFalse(c2)
        self.assertEqual(u1.id, u2.id)
        self.assertEqual(User.objects.filter(is_deleted=False).count(), 1)

    @override_settings(OAUTH_BIND_EXISTING_BY_PHONE=True)
    def test_backfill_when_binding_enabled(self):
        """显式开启绑定后:非特权既有账号按 IM 核验手机号绑定并回填 *_id。"""
        existing = User.objects.create_user(username='wang', employee_id='E001', phone='13700137000')
        ident = OAuthIdentity(external_id='wx_wang', name='王五', mobile='137-0013-7000')  # 含分隔符
        user, created = find_or_create_user('wecom', ident)
        self.assertFalse(created)
        self.assertEqual(user.id, existing.id)
        user.refresh_from_db()
        self.assertEqual(user.wechat_work_id, 'wx_wang')  # 回填

    def test_existing_match_refused_by_default(self):
        """默认不绑定既有账号:phone 命中既有 → 拒绝(防接管),不建重复、不发 token。"""
        User.objects.create_user(username='wang', employee_id='E001', phone='13700137000')
        ident = OAuthIdentity(external_id='wx_wang', mobile='13700137000')
        with self.assertRaises(OAuthError):
            find_or_create_user('wecom', ident)
        self.assertEqual(User.objects.filter(is_deleted=False).count(), 1)  # 未建重复

    @override_settings(OAUTH_BIND_EXISTING_BY_PHONE=True)
    def test_privileged_account_refused_even_when_binding_enabled(self):
        """特权账号(superuser)即便开了绑定也拒绝扫码自动登录。"""
        User.objects.create_user(username='boss', employee_id='E000', phone='13800138001',
                                 is_superuser=True, is_staff=True)
        ident = OAuthIdentity(external_id='wx_boss', mobile='13800138001')
        with self.assertRaises(OAuthError):
            find_or_create_user('wecom', ident)

    def test_email_not_used_for_binding(self):
        """email 不作匹配键:同邮箱、无手机 → 不绑定既有,按新人自动建号。"""
        existing = User.objects.create_user(username='z', employee_id='E002', email='z@corp.com')
        ident = OAuthIdentity(external_id='wx_z', email='z@corp.com')  # 无 mobile
        user, created = find_or_create_user('wecom', ident)
        self.assertTrue(created)
        self.assertNotEqual(user.id, existing.id)

    @override_settings(OAUTH_AUTO_CREATE=False)
    def test_auto_create_disabled_returns_none(self):
        ident = OAuthIdentity(external_id='wx_new', mobile='13600136000')
        user, created = find_or_create_user('wecom', ident)
        self.assertIsNone(user)
        self.assertFalse(created)

    @override_settings(OAUTH_ALLOWED_EMAIL_DOMAINS=['corp.com'])
    def test_domain_whitelist_blocks_outsider(self):
        ident = OAuthIdentity(external_id='wx_out', email='x@gmail.com')
        user, _ = find_or_create_user('wecom', ident)
        self.assertIsNone(user)

    def test_state_sign_verify(self):
        s = issue_state('wecom')
        self.assertTrue(verify_state(s, 'wecom'))
        self.assertFalse(verify_state(s, 'dingtalk'))  # 平台不符
        self.assertFalse(verify_state('tampered', 'wecom'))


@override_settings(WECHAT_WORK_CORP_ID='corp', WECHAT_WORK_CORP_SECRET='secret', LOGIN_THROTTLE_ENABLED=False)
class OAuthCallbackHTTPTests(TestCase):
    """端到端 HTTP:回调 → 建号 → 发 JWT(返回体同密码登录)。"""

    def setUp(self):
        Role.objects.create(name='普通员工', code='employee', data_scope='SELF', is_active=True)

    def _post(self, identity, state=None):
        state = state or issue_state('wecom')
        self.client.cookies[STATE_COOKIE] = state  # state 绑定本浏览器(防 CSRF)
        with patch.object(WeComProvider, 'resolve_identity', return_value=identity):
            return self.client.post(CALLBACK, {'code': 'CODE_%s' % identity.external_id, 'state': state})

    def test_callback_creates_and_returns_tokens(self):
        ident = OAuthIdentity(external_id='wx_a', name='赵六', mobile='13500135000')
        resp = self._post(ident)
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.json()
        self.assertIn('access', body)
        self.assertIn('refresh', body)
        self.assertTrue(body['is_new_user'])
        # 返回体结构与密码登录一致(含权限/菜单/数据范围)
        for key in ('permissions', 'menus', 'data_scopes'):
            self.assertIn(key, body['user'])
        self.assertTrue(User.objects.filter(wechat_work_id='wx_a').exists())

    def test_callback_bad_state_400(self):
        ident = OAuthIdentity(external_id='wx_b')
        resp = self._post(ident, state='bad-state')
        self.assertEqual(resp.status_code, 400)

    def test_callback_missing_state_cookie_400(self):
        """有效签名 state 但浏览器无对应 cookie → 拒绝(登录 CSRF 防护)。"""
        ident = OAuthIdentity(external_id='wx_d', mobile='13300133000')
        state = issue_state('wecom')
        self.client.cookies.pop(STATE_COOKIE, None)  # 显式不带 cookie
        with patch.object(WeComProvider, 'resolve_identity', return_value=ident):
            resp = self.client.post(CALLBACK, {'code': 'CODE_d', 'state': state})
        self.assertEqual(resp.status_code, 400)

    def test_callback_code_replay_400(self):
        ident = OAuthIdentity(external_id='wx_c', mobile='13400134000')
        s1, s2 = issue_state('wecom'), issue_state('wecom')
        with patch.object(WeComProvider, 'resolve_identity', return_value=ident):
            self.client.cookies[STATE_COOKIE] = s1
            r1 = self.client.post(CALLBACK, {'code': 'SAME', 'state': s1})
            self.client.cookies[STATE_COOKIE] = s2
            r2 = self.client.post(CALLBACK, {'code': 'SAME', 'state': s2})
        self.assertEqual(r1.status_code, 200, r1.content)
        self.assertEqual(r2.status_code, 400)  # 同 code 重放被拒
