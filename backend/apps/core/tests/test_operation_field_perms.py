"""
操作级 + 字段级权限回归测试（审计 C2 整改）。

锁定三条不变式：

(a) 向后兼容（必须通过）：仅持菜单权、未配置任何操作级权限的角色，view/create/edit/delete
    全部放行 —— 与历史“菜单级粒度”授权一致，绝不因本次整改变成 403。
(b) 操作级“可选启用”限制：一旦角色对某 resource 被授予了部分 CRUD 却缺失某个 action，
    该 action 即被拒绝（edit=403），已授予的 action 仍放行（view=200）。
(c) 字段级脱敏：对某敏感字段未被授予字段权限的角色，序列化器输出中该字段被剔除；
    被授予的角色仍可见。

采用与 test_permission_escalation.py 相同的轻量单元法：实例化 PermissionMixin ViewSet +
APIRequestFactory 直接调 check_permissions / get_serializer，真实跑通鉴权与脱敏栈。
"""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework import serializers, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIRequestFactory

from apps.accounts.models import Role
from apps.core.permission_mixin import PermissionMixin
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


def _make_user(username, perms=(), is_superuser=False):
    """Create a user whose single role holds the given Permission objects."""
    user = User.objects.create_user(
        username=username, password='x', employee_id=username,
        is_superuser=is_superuser, is_staff=is_superuser,
    )
    if perms:
        role = Role.objects.create(name=f'{username}_role', code=f'{username}_role')
        for perm in perms:
            RolePermission.objects.get_or_create(role=role, permission=perm)
        user.role = role
        user.save()
    return user


def _menu(code):
    perm, _ = Permission.objects.get_or_create(code=code, defaults={'name': code, 'type': 'menu'})
    return perm


def _op(module, resource, action):
    code = f'{module}:{resource}:{action}'
    perm, _ = Permission.objects.get_or_create(
        code=code, defaults={'name': code, 'type': 'operation', 'resource': resource}
    )
    return perm


def _field(module, resource, field_name):
    code = f'{module}:{resource}:field:{field_name}'
    perm, _ = Permission.objects.get_or_create(
        code=code,
        defaults={'name': code, 'type': 'field', 'resource': resource, 'field_name': field_name},
    )
    return perm


class _CrudViewSet(PermissionMixin, viewsets.ModelViewSet):
    """Synthetic ViewSet exercising only PermissionMixin.check_permissions."""

    permission_classes = []  # isolate PermissionMixin from project-wide auth defaults
    permission_module = 'projects'
    permission_resource = 'project'


class _StockMoveSerializer(serializers.Serializer):
    name = serializers.CharField()
    qty = serializers.IntegerField()
    unit_cost = serializers.DecimalField(max_digits=12, decimal_places=2)


class _StockMoveViewSet(PermissionMixin, viewsets.ModelViewSet):
    permission_classes = []
    permission_module = 'inventory'
    permission_resource = 'stock_move'
    serializer_class = _StockMoveSerializer


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class OperationPermissionTest(TestCase):
    def setUp(self):
        cache.clear()

    def _check(self, viewset_cls, user, action):
        method = _METHOD_FOR_ACTION[action]
        request = getattr(factory, method)('/x/')
        request.user = user
        request.authenticators = []
        request.successful_authenticator = None
        viewset = viewset_cls()
        viewset.request = request
        viewset.action = action
        viewset.check_permissions(request)

    def assertAllowed(self, viewset_cls, user, action):
        try:
            self._check(viewset_cls, user, action)
        except PermissionDenied:
            self.fail(f'{viewset_cls.__name__}.{action} 不应被拒绝')

    def assertDenied(self, viewset_cls, user, action):
        with self.assertRaises(PermissionDenied):
            self._check(viewset_cls, user, action)

    # ---- (a) 向后兼容：仅菜单权、无操作权 -> 全 CRUD 放行 ----
    def test_menu_only_role_keeps_full_crud(self):
        user = _make_user('menuonly', perms=[_menu('projects')])
        for action in ('list', 'retrieve', 'create', 'update', 'partial_update', 'destroy'):
            self.assertAllowed(_CrudViewSet, user, action)

    def test_menu_only_role_via_mapped_prefix(self):
        # 'projects' 模块菜单映射含 'projects' 前缀；持子菜单码亦应全放行（无操作权配置时）
        user = _make_user('submenu', perms=[_menu('projects:task')])
        for action in ('list', 'create', 'update', 'destroy'):
            self.assertAllowed(_CrudViewSet, user, action)

    # ---- (b) 操作级限制：配置了部分 CRUD、缺失 edit -> edit 403，view 200 ----
    def test_partial_operation_perms_enforce_missing_action(self):
        user = _make_user('restricted', perms=[
            _menu('projects'),  # 即便持菜单权，操作级限制仍应覆盖它
            _op('projects', 'project', 'view'),
            _op('projects', 'project', 'create'),
            _op('projects', 'project', 'delete'),
            # 故意缺失 edit
        ])
        # 已授予的 action 放行
        self.assertAllowed(_CrudViewSet, user, 'list')
        self.assertAllowed(_CrudViewSet, user, 'retrieve')
        self.assertAllowed(_CrudViewSet, user, 'create')
        self.assertAllowed(_CrudViewSet, user, 'destroy')
        # 缺失的 edit 被拒绝（update / partial_update 均映射到 edit）
        self.assertDenied(_CrudViewSet, user, 'update')
        self.assertDenied(_CrudViewSet, user, 'partial_update')

    def test_full_operation_perms_allow_all(self):
        user = _make_user('fullops', perms=[
            _op('projects', 'project', 'view'),
            _op('projects', 'project', 'create'),
            _op('projects', 'project', 'edit'),
            _op('projects', 'project', 'delete'),
        ])
        for action in ('list', 'create', 'update', 'destroy'):
            self.assertAllowed(_CrudViewSet, user, action)

    def test_superuser_always_allowed(self):
        root = _make_user('root_op', is_superuser=True)
        for action in ('list', 'create', 'update', 'destroy'):
            self.assertAllowed(_CrudViewSet, root, action)

    def test_operation_perms_for_other_resource_do_not_restrict(self):
        # 对 sales:order 配置的操作权不应牵连 projects:project（按 resource 隔离）
        user = _make_user('otherres', perms=[
            _menu('projects'),
            _op('sales', 'order', 'view'),  # 与被测 resource 无关
        ])
        for action in ('list', 'create', 'update', 'destroy'):
            self.assertAllowed(_CrudViewSet, user, action)


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class FieldPermissionMaskingTest(TestCase):
    def setUp(self):
        cache.clear()

    def _serializer_fields(self, user):
        request = factory.get('/x/')
        request.user = user
        request.authenticators = []
        request.successful_authenticator = None
        viewset = _StockMoveViewSet()
        viewset.request = request
        viewset.format_kwarg = None
        viewset.action = 'list'
        serializer = viewset.get_serializer()
        return set(serializer.fields.keys())

    def test_no_field_perms_configured_masks_nothing(self):
        # 未种子化任何字段权限 -> 全字段可见（历史行为）
        user = _make_user('plain', perms=[_menu('supply')])
        fields = self._serializer_fields(user)
        self.assertIn('unit_cost', fields)

    def test_denied_role_gets_field_masked(self):
        # 种子化 unit_cost 字段权限，但不授予该角色 -> 被屏蔽
        _field('inventory', 'stock_move', 'unit_cost')
        denied = _make_user('denied', perms=[_menu('supply')])
        fields = self._serializer_fields(denied)
        self.assertNotIn('unit_cost', fields)
        self.assertIn('name', fields)
        self.assertIn('qty', fields)

    def test_granted_role_sees_field(self):
        perm = _field('inventory', 'stock_move', 'unit_cost')
        allowed = _make_user('allowed', perms=[_menu('supply'), perm])
        fields = self._serializer_fields(allowed)
        self.assertIn('unit_cost', fields)

    def test_superuser_sees_field_even_when_configured(self):
        _field('inventory', 'stock_move', 'unit_cost')
        root = _make_user('root_field', is_superuser=True)
        fields = self._serializer_fields(root)
        self.assertIn('unit_cost', fields)
