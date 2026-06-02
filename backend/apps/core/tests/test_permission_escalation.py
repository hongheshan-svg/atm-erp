"""
权限越权回归测试（审计 C1）+ 菜单级粒度设计确认（审计 C2）。

复现并锁定修复：
- A 类敏感 ViewSet（Permission / DataScope / CodeRule / Webhook / AuditLog）：
  普通员工(oa:*)、经理(system:report)、人事(system:user) 均不可读写；仅超管 /
  系统管理员(持顶层 'system' 码) 可访问。
- A 类“只写门槛”ViewSet（DictType 等）：非管理员可读、不可写。
- accounts 模块：oa 员工 / 经理不能再增删用户/角色/部门；人事(system:user) 可管用户/
  部门，但角色定义仅管理员可写。
- B/C 类协同/通用 ViewSet（公告 / 通知 / 附件）未被误伤：oa:* 员工仍可写。

采用与 test_permission_mixin.py 相同的轻量单元法：实例化真实 ViewSet + APIRequestFactory
调 check_permissions，从而真实跑通 permission_classes(IsSystemAdmin) + PermissionMixin
的完整鉴权栈，无需 URL 路由或重数据。
"""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIRequestFactory

from apps.accounts.models import Role
from apps.accounts.views import RoleViewSet, UserViewSet
from apps.core.announcement import AnnouncementViewSet
from apps.core.code_rule_views import CodeRuleViewSet
from apps.core.data_dict import DictTypeViewSet
from apps.core.permission_models_new import Permission, RolePermission
from apps.core.permission_views import DataScopeViewSet, PermissionViewSet
from apps.core.views import AttachmentViewSet, AuditLogViewSet, NotificationViewSet
from apps.core.webhook_views import WebhookEndpointViewSet

User = get_user_model()
factory = APIRequestFactory()

# action -> (HTTP method on APIRequestFactory)
_METHOD_FOR_ACTION = {
    'list': 'get',
    'retrieve': 'get',
    'create': 'post',
    'update': 'put',
    'partial_update': 'patch',
    'destroy': 'delete',
}


def _make_user(username, menu_codes=(), is_superuser=False):
    """Create a user whose (single) role holds the given menu-level permission codes."""
    # User.employee_id 唯一且默认空串，多用户须各自赋唯一值，否则触发唯一约束冲突
    user = User.objects.create_user(
        username=username, password='x', employee_id=username,
        is_superuser=is_superuser, is_staff=is_superuser,
    )
    if menu_codes:
        role = Role.objects.create(name=f'{username}_role', code=f'{username}_role')
        for code in menu_codes:
            perm, _ = Permission.objects.get_or_create(code=code, defaults={'name': code, 'type': 'menu'})
            RolePermission.objects.get_or_create(role=role, permission=perm)
        user.role = role
        user.save()
    return user


class PermissionEscalationTest(TestCase):
    def setUp(self):
        # 权限/数据范围结果带缓存，逐测试清空以免串扰
        cache.clear()
        # 普通员工：仅持 oa:* 叶子菜单码（审计 C1 中的越权主体）
        self.employee = _make_user('emp', menu_codes=['oa:announcement', 'oa:meeting'])
        # 各类经理：持 system:report（前缀 'system' 此前会误命中 system 模块）
        self.manager = _make_user('mgr', menu_codes=['system:report', 'sales'])
        # 人事行政：持 system:user / system:department（应能管用户/部门）
        self.hr = _make_user('hr', menu_codes=['system:user', 'system:department', 'oa'])
        # 系统管理员：真实 admin 角色持 '*'，会展开为含 'system' 顶层及 system:user/role/department
        # 等全部子码。菜单兜底按“持有前缀或其后代”匹配，故须显式包含这些子码（持父码不命中子前缀）。
        self.admin = _make_user('adm', menu_codes=['system', 'system:user', 'system:role', 'system:department'])
        # Django 超级用户
        self.superuser = _make_user('root', is_superuser=True)

    # ---- helpers -------------------------------------------------------
    def _check(self, viewset_cls, user, action):
        method = _METHOD_FOR_ACTION[action]
        request = getattr(factory, method)('/x/')
        request.user = user
        # DRF 的 permission_denied 会读取这两个属性（默认只有 DRF Request 才有）。
        # 置 authenticators=[] 使“被拒绝”时直接抛 PermissionDenied，而非 NotAuthenticated。
        request.authenticators = []
        request.successful_authenticator = None
        viewset = viewset_cls()
        viewset.request = request
        viewset.action = action
        viewset.check_permissions(request)

    def assertDenied(self, viewset_cls, user, action, msg=''):
        with self.assertRaises(PermissionDenied, msg=msg or f'{viewset_cls.__name__}.{action} 应被拒绝'):
            self._check(viewset_cls, user, action)

    def assertAllowed(self, viewset_cls, user, action, msg=''):
        try:
            self._check(viewset_cls, user, action)
        except PermissionDenied:
            self.fail(msg or f'{viewset_cls.__name__}.{action} 不应被拒绝')

    # ---- C1: A 类敏感 RBAC/配置（IsSystemAdmin，全方法管理员） -----------
    def test_datascope_write_blocked_for_non_admin(self):
        for user in (self.employee, self.manager, self.hr):
            self.assertDenied(DataScopeViewSet, user, 'create')
            self.assertDenied(DataScopeViewSet, user, 'update')
            self.assertDenied(DataScopeViewSet, user, 'destroy')

    def test_datascope_read_blocked_for_non_admin(self):
        # IsSystemAdmin 同时拦读：员工不能再窥探/篡改数据范围
        for user in (self.employee, self.manager, self.hr):
            self.assertDenied(DataScopeViewSet, user, 'list')

    def test_permission_tree_blocked_for_non_admin(self):
        for user in (self.employee, self.manager, self.hr):
            self.assertDenied(PermissionViewSet, user, 'create')
            self.assertDenied(PermissionViewSet, user, 'list')

    def test_code_rule_and_webhook_write_blocked_for_non_admin(self):
        for user in (self.employee, self.manager, self.hr):
            self.assertDenied(CodeRuleViewSet, user, 'create')
            self.assertDenied(WebhookEndpointViewSet, user, 'create')

    def test_audit_log_read_blocked_for_non_admin(self):
        # 审计 C1 明确点名“可读取全部审计日志”
        for user in (self.employee, self.manager, self.hr):
            self.assertDenied(AuditLogViewSet, user, 'list')

    def test_sensitive_resources_allowed_for_admin_and_superuser(self):
        for user in (self.admin, self.superuser):
            self.assertAllowed(DataScopeViewSet, user, 'create')
            self.assertAllowed(DataScopeViewSet, user, 'list')
            self.assertAllowed(PermissionViewSet, user, 'create')
            self.assertAllowed(CodeRuleViewSet, user, 'create')
            self.assertAllowed(WebhookEndpointViewSet, user, 'destroy')
            self.assertAllowed(AuditLogViewSet, user, 'list')

    # ---- C1: A 类“只写门槛”（IsSystemAdminOrReadOnly） -------------------
    def test_dict_type_readable_but_not_writable_by_non_admin(self):
        # 字典是参考数据：任何登录用户可读（allow_authenticated_read），但仅管理员可写
        self.assertAllowed(DictTypeViewSet, self.employee, 'list')
        self.assertDenied(DictTypeViewSet, self.employee, 'create')
        self.assertDenied(DictTypeViewSet, self.manager, 'update')
        self.assertAllowed(DictTypeViewSet, self.admin, 'create')

    # ---- C1: accounts 模块越权关闭 -------------------------------------
    def test_user_management_blocked_for_oa_and_managers(self):
        # 员工(oa:*) 与 经理(system:report) 不能再增删用户
        self.assertDenied(UserViewSet, self.employee, 'create')
        self.assertDenied(UserViewSet, self.employee, 'destroy')
        self.assertDenied(UserViewSet, self.manager, 'create')

    def test_user_management_allowed_for_hr_and_admin(self):
        # 人事(system:user) 与 管理员可管理用户
        self.assertAllowed(UserViewSet, self.hr, 'create')
        self.assertAllowed(UserViewSet, self.admin, 'create')

    def test_user_list_not_regressed(self):
        # UserViewSet allow_authenticated_read=True：列表读取不受影响
        self.assertAllowed(UserViewSet, self.employee, 'list')

    def test_role_writes_admin_only(self):
        # 角色定义属 RBAC：人事可读、不可写；仅管理员可写
        self.assertAllowed(RoleViewSet, self.hr, 'list')
        self.assertDenied(RoleViewSet, self.hr, 'create')
        self.assertDenied(RoleViewSet, self.employee, 'create')
        self.assertAllowed(RoleViewSet, self.admin, 'create')

    # ---- 无回归：B/C 类协同与通用 ViewSet ------------------------------
    def test_oa_collaboration_not_regressed(self):
        # 公告（permission_module='system'，无硬门槛）：oa:* 员工仍可创建
        self.assertAllowed(AnnouncementViewSet, self.employee, 'create')
        self.assertAllowed(AnnouncementViewSet, self.employee, 'list')

    def test_notification_and_attachment_not_regressed(self):
        # 通知“标记已读”与附件上传都依赖菜单兜底('oa')，员工不应被误伤
        self.assertAllowed(NotificationViewSet, self.employee, 'create')
        self.assertAllowed(AttachmentViewSet, self.employee, 'create')


class IsSystemAdminUnitTest(TestCase):
    """直接验证 IsSystemAdmin 判定函数。"""

    def setUp(self):
        cache.clear()

    def test_predicate(self):
        from apps.core.permissions import _is_system_admin

        emp = _make_user('u_emp', menu_codes=['oa:announcement'])
        mgr = _make_user('u_mgr', menu_codes=['system:report'])
        adm = _make_user('u_adm', menu_codes=['system'])
        root = _make_user('u_root', is_superuser=True)

        self.assertFalse(_is_system_admin(emp))
        self.assertFalse(_is_system_admin(mgr))
        self.assertTrue(_is_system_admin(adm))
        self.assertTrue(_is_system_admin(root))
