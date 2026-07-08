"""
仪表盘自定义 SQL 组件的管理员硬门槛回归测试（P1 安全修复）。

修复点：DashboardWidgetViewSet 仅有 permission_module='system'，靠 PermissionMixin
菜单兜底——任何持有 system:* 叶子菜单（如经理的 system:report）的用户都能创建
data_source='custom_sql' 的组件，其 custom_query 可 SELECT 任意表（含用户密码哈希）。
加 IsSystemAdminOrReadOnly 后：读取不变（SAFE 方法放行），但增删改仅系统管理员可为。

沿用 test_permission_escalation.py 的轻量单元法：实例化真实 ViewSet + APIRequestFactory
调 check_permissions，真实跑通 permission_classes(IsSystemAdminOrReadOnly) + PermissionMixin。
"""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIRequestFactory

from apps.accounts.models import Role
from apps.core.dashboard_views import DashboardWidgetViewSet
from apps.core.permission_models_new import Permission, RolePermission

User = get_user_model()
factory = APIRequestFactory()

_METHOD_FOR_ACTION = {
    'list': 'get',
    'retrieve': 'get',
    'create': 'post',
    'update': 'put',
    'partial_update': 'patch',
    'destroy': 'delete',
}


def _make_user(username, menu_codes=(), is_superuser=False):
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


class DashboardWidgetGateTest(TestCase):
    def setUp(self):
        cache.clear()
        # 非管理员，但持有宽泛的 system:* 菜单（审计中的越权主体）
        self.manager = _make_user('mgr', menu_codes=['system:report'])
        # 系统管理员（顶层 'system' 码）
        self.admin = _make_user('adm', menu_codes=['system'])
        # Django 超级用户
        self.superuser = _make_user('root', is_superuser=True)

    def _check(self, user, action):
        method = _METHOD_FOR_ACTION[action]
        request = getattr(factory, method)('/x/')
        request.user = user
        request.authenticators = []
        request.successful_authenticator = None
        viewset = DashboardWidgetViewSet()
        viewset.request = request
        viewset.action = action
        viewset.check_permissions(request)

    def assertDenied(self, user, action):
        with self.assertRaises(PermissionDenied, msg=f'{action} 应被拒绝'):
            self._check(user, action)

    def assertAllowed(self, user, action):
        try:
            self._check(user, action)
        except PermissionDenied:
            self.fail(f'{action} 不应被拒绝')

    def test_non_admin_cannot_create_or_update_widget(self):
        # 关键回归：宽泛 system:* 菜单不足以创建/改自定义 SQL 组件
        self.assertDenied(self.manager, 'create')
        self.assertDenied(self.manager, 'update')
        self.assertDenied(self.manager, 'destroy')

    def test_non_admin_can_still_read_widgets(self):
        # 读取不被破坏：SAFE 方法经 IsSystemAdminOrReadOnly 放行，菜单兜底通过
        self.assertAllowed(self.manager, 'list')

    def test_admin_can_author_widget(self):
        for user in (self.admin, self.superuser):
            self.assertAllowed(user, 'create')
            self.assertAllowed(user, 'update')
