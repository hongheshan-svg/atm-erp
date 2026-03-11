# 权限管理体系重新设计 实施计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有散落在 6 处的权限逻辑统一为以权限树为核心的可配置 RBAC 体系

**Architecture:** 权限树模型（Permission）统一管理菜单/操作/敏感字段三类权限，用户与角色多对多关联，数据权限通过独立的 DataScope 表支持五级范围。后端统一 PermissionMixin 替代现有 4 个独立 Mixin，前端通过 Permission Store + v-permission 指令实现菜单/按钮/字段三级控制。

**Tech Stack:** Django 4.2 + DRF 3.14, Vue 3 + Pinia + Element Plus, PostgreSQL, Redis (缓存)

**Spec:** `docs/superpowers/specs/2026-03-10-permission-system-redesign.md`

---

## File Structure

### 后端 — 新增
| File | Responsibility |
|------|---------------|
| `backend/apps/core/permission_models_new.py` | Permission, RolePermission, DataScope 模型 |
| `backend/apps/core/permission_service.py` | get_user_permissions, has_permission, resolve_data_scope, apply_scope_filter, get_hidden_fields, cache invalidation |
| `backend/apps/core/permission_mixin.py` | 统一 PermissionMixin (替代 DataPermissionMixin + FinanceDataMixin + OperationPermissionMixin + SensitiveFieldMixin) |
| `backend/apps/core/permission_views.py` | PermissionViewSet (权限树 CRUD API) |
| `backend/apps/core/permission_serializers.py` | PermissionSerializer, PermissionTreeSerializer, DataScopeSerializer |
| `backend/apps/core/management/commands/init_permissions.py` | 权限树初始数据 management command (幂等) |
| `backend/apps/core/tests/test_permission_models.py` | Permission, RolePermission, DataScope 模型测试 |
| `backend/apps/core/tests/test_permission_service.py` | 权限服务函数测试 |
| `backend/apps/core/tests/test_permission_mixin.py` | PermissionMixin 集成测试 |
| `backend/apps/core/tests/test_permission_views.py` | 权限树 API 测试 |

### 后端 — 改造
| File | Changes |
|------|---------|
| `backend/apps/accounts/models.py:44-75` | Role: 删除 data_scope/permissions JSON, 加 permissions M2M |
| `backend/apps/accounts/models.py:78-159` | User: 加 roles M2M (保留旧 role FK 暂不删) |
| `backend/apps/accounts/serializers.py:166-194` | UserProfileSerializer: 返回新权限结构 |
| `backend/apps/accounts/serializers.py:37-82` | RoleSerializer: 支持权限树勾选和数据权限配置 |
| `backend/apps/accounts/views.py:67-102` | RoleViewSet: 权限分配/数据权限 CRUD |
| `backend/apps/accounts/views.py:105-440` | UserViewSet: 多角色分配 |
| `backend/apps/core/workflow/services.py:153` | _get_step_assignee: role= 改 roles= |
| `backend/apps/core/workflow/mixins.py` | 审批前权限校验加 has_permission 检查 |
| 16 个 ViewSet 文件 (67 个 ViewSet) | 旧 Mixin 替换为 PermissionMixin |

### 后端 — 删除 (下个版本)
| File | What |
|------|------|
| `backend/apps/core/permission_config.py` | 695 行硬编码配置 |
| `backend/apps/core/permission_models.py` | ModulePermissionRule, RoleModulePermission |
| `backend/apps/core/permissions.py` | DataScopePermission |
| `backend/apps/core/data_permission.py` | 旧 Mixin (标记 deprecated) |

### 前端 — 新增
| File | Responsibility |
|------|---------------|
| `frontend/src/stores/permission.js` | Permission Store (permissions Set, menus, dataScopes) |
| `frontend/src/directives/permission.js` | v-permission 指令 |
| `frontend/src/views/system/PermissionTree.vue` | 权限树管理页面 |

### 前端 — 改造
| File | Changes |
|------|---------|
| `frontend/src/stores/user.js` | 登录后调用 permission store |
| `frontend/src/main.js` | 注册 v-permission 指令 |
| `frontend/src/router/index.js:1199-1430` | 删除 hasMenuAccess, 改用 permission store |
| `frontend/src/layout/MainLayout.vue` | 动态菜单渲染 |
| `frontend/src/views/system/RoleList.vue` | 权限树勾选 + 数据权限配置 |
| `frontend/src/views/system/UserList.vue` | 多角色选择 |
| `frontend/src/composables/usePermission.js` | 改用 permission store |
| `frontend/src/api/auth.js` | 新增权限树 API 调用 |

---

## Chunk 1: 后端核心模型与权限服务

### Task 1: Permission 模型

**Files:**
- Create: `backend/apps/core/permission_models_new.py`
- Test: `backend/apps/core/tests/test_permission_models.py`

- [ ] **Step 1: 创建测试文件**

```python
# backend/apps/core/tests/test_permission_models.py
import pytest
from django.test import TestCase
from apps.core.permission_models_new import Permission, RolePermission, DataScope
from apps.accounts.models import Role, Department


class PermissionModelTest(TestCase):
    def test_create_menu_permission(self):
        perm = Permission.objects.create(
            code='system', name='系统管理', type='menu',
            route_path='/system', icon='Setting', sort_order=1
        )
        self.assertEqual(perm.code, 'system')
        self.assertEqual(perm.type, 'menu')
        self.assertIsNone(perm.parent)

    def test_create_child_permission(self):
        parent = Permission.objects.create(
            code='system', name='系统管理', type='menu'
        )
        child = Permission.objects.create(
            code='system:user', name='用户管理', type='menu',
            parent=parent, route_path='/system/users'
        )
        self.assertEqual(child.parent, parent)
        self.assertTrue(parent.children.filter(id=child.id).exists())

    def test_create_operation_permission(self):
        parent = Permission.objects.create(
            code='system:user', name='用户管理', type='menu'
        )
        op = Permission.objects.create(
            code='system:user:create', name='新增用户', type='operation',
            parent=parent, resource='user'
        )
        self.assertEqual(op.type, 'operation')
        self.assertEqual(op.resource, 'user')

    def test_create_field_permission(self):
        parent = Permission.objects.create(
            code='purchase:order', name='采购订单', type='menu'
        )
        field = Permission.objects.create(
            code='purchase:order:view_price', name='查看采购单价',
            type='field', parent=parent, resource='purchase_order',
            field_name='unit_price'
        )
        self.assertEqual(field.type, 'field')
        self.assertEqual(field.field_name, 'unit_price')

    def test_permission_code_unique(self):
        Permission.objects.create(code='system', name='系统管理', type='menu')
        with self.assertRaises(Exception):
            Permission.objects.create(code='system', name='重复', type='menu')

    def test_permission_str(self):
        perm = Permission.objects.create(
            code='system:user', name='用户管理', type='menu'
        )
        self.assertIn('用户管理', str(perm))
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /home/administrator/erp/backend && python -m pytest apps/core/tests/test_permission_models.py -v --no-header 2>&1 | head -20`
Expected: ImportError — permission_models_new 不存在

- [ ] **Step 3: 创建 Permission 模型**

```python
# backend/apps/core/permission_models_new.py
from django.db import models
from apps.core.models import BaseModel
from apps.accounts.models import Department


class Permission(BaseModel):
    """权限节点 — 树形结构，统一管理菜单/操作/敏感字段"""

    TYPE_CHOICES = [
        ('menu', '菜单'),
        ('operation', '操作'),
        ('field', '敏感字段'),
    ]

    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True,
        related_name='children', verbose_name='父节点'
    )
    code = models.CharField('权限编码', max_length=128, unique=True, db_index=True)
    name = models.CharField('权限名称', max_length=64)
    type = models.CharField('节点类型', max_length=16, choices=TYPE_CHOICES)
    resource = models.CharField('资源标识', max_length=64, blank=True, default='')
    field_name = models.CharField('模型字段名', max_length=64, blank=True, default='',
                                  help_text='仅 field 类型使用')
    route_path = models.CharField('前端路由', max_length=256, blank=True, default='')
    icon = models.CharField('菜单图标', max_length=64, blank=True, default='')
    sort_order = models.IntegerField('排序', default=0)
    is_active = models.BooleanField('是否启用', default=True)

    class Meta:
        db_table = 'core_permission'
        ordering = ['sort_order', 'id']
        verbose_name = '权限'
        verbose_name_plural = '权限'

    def __str__(self):
        return f'[{self.get_type_display()}] {self.name} ({self.code})'
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /home/administrator/erp/backend && python -m pytest apps/core/tests/test_permission_models.py::PermissionModelTest -v --no-header`
Expected: 6 passed

- [ ] **Step 5: 提交**

```bash
cd /home/administrator/erp
git add backend/apps/core/permission_models_new.py backend/apps/core/tests/test_permission_models.py
git commit -m "feat(permission): add Permission tree model with tests"
```

---

### Task 2: RolePermission 和 DataScope 模型

**Files:**
- Modify: `backend/apps/core/permission_models_new.py`
- Modify: `backend/apps/core/tests/test_permission_models.py`

- [ ] **Step 1: 追加测试**

在 `test_permission_models.py` 末尾追加：

```python
class RolePermissionModelTest(TestCase):
    def setUp(self):
        self.role = Role.objects.create(name='测试角色', code='test_role')
        self.perm = Permission.objects.create(
            code='system:user', name='用户管理', type='menu'
        )

    def test_create_role_permission(self):
        rp = RolePermission.objects.create(role=self.role, permission=self.perm)
        self.assertEqual(rp.role, self.role)
        self.assertEqual(rp.permission, self.perm)

    def test_role_permission_unique(self):
        RolePermission.objects.create(role=self.role, permission=self.perm)
        with self.assertRaises(Exception):
            RolePermission.objects.create(role=self.role, permission=self.perm)

    def test_cascade_delete_on_role(self):
        RolePermission.objects.create(role=self.role, permission=self.perm)
        self.role.delete()
        self.assertEqual(RolePermission.objects.count(), 0)


class DataScopeModelTest(TestCase):
    def setUp(self):
        self.role = Role.objects.create(name='测试角色', code='test_role2')
        self.dept = Department.objects.create(name='测试部门', code='test_dept')

    def test_create_global_scope(self):
        scope = DataScope.objects.create(
            role=self.role, module='', scope_type='all'
        )
        self.assertEqual(scope.scope_type, 'all')
        self.assertEqual(scope.module, '')

    def test_create_module_scope(self):
        scope = DataScope.objects.create(
            role=self.role, module='finance', scope_type='self'
        )
        self.assertEqual(scope.module, 'finance')

    def test_custom_scope_with_departments(self):
        scope = DataScope.objects.create(
            role=self.role, module='purchase', scope_type='custom'
        )
        scope.custom_departments.add(self.dept)
        self.assertIn(self.dept, scope.custom_departments.all())

    def test_scope_unique_per_role_module(self):
        DataScope.objects.create(role=self.role, module='finance', scope_type='self')
        with self.assertRaises(Exception):
            DataScope.objects.create(role=self.role, module='finance', scope_type='all')

    def test_scope_type_choices(self):
        for scope_type in ['all', 'dept_tree', 'dept', 'self', 'custom']:
            scope = DataScope.objects.create(
                role=self.role, module=f'mod_{scope_type}', scope_type=scope_type
            )
            self.assertEqual(scope.scope_type, scope_type)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /home/administrator/erp/backend && python -m pytest apps/core/tests/test_permission_models.py -v --no-header 2>&1 | head -30`
Expected: ImportError — RolePermission, DataScope 不存在

- [ ] **Step 3: 在 permission_models_new.py 追加 RolePermission 和 DataScope**

```python
# 追加到 backend/apps/core/permission_models_new.py 末尾

class RolePermission(models.Model):
    """角色-权限关联（不继承 BaseModel，避免软删除干扰 M2M 查询）"""

    role = models.ForeignKey(
        'accounts.Role', on_delete=models.CASCADE,
        related_name='role_permissions', verbose_name='角色'
    )
    permission = models.ForeignKey(
        Permission, on_delete=models.CASCADE,
        related_name='role_permissions', verbose_name='权限'
    )
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        db_table = 'core_role_permission'
        unique_together = ['role', 'permission']
        verbose_name = '角色权限'
        verbose_name_plural = '角色权限'

    def __str__(self):
        return f'{self.role} - {self.permission}'


class DataScope(models.Model):
    """数据权限规则（不继承 BaseModel，避免软删除与 unique_together 冲突）"""

    SCOPE_CHOICES = [
        ('all', '全部数据'),
        ('dept_tree', '本部门及子部门'),
        ('dept', '仅本部门'),
        ('self', '仅自己'),
        ('custom', '自定义部门'),
    ]

    role = models.ForeignKey(
        'accounts.Role', on_delete=models.CASCADE,
        related_name='data_scopes', verbose_name='角色'
    )
    module = models.CharField('模块', max_length=64, blank=True, default='',
                              help_text='空表示全局默认')
    scope_type = models.CharField('范围类型', max_length=16, choices=SCOPE_CHOICES)
    custom_departments = models.ManyToManyField(
        'accounts.Department', blank=True,
        related_name='custom_data_scopes', verbose_name='自定义部门'
    )
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        db_table = 'core_data_scope'
        unique_together = ['role', 'module']
        verbose_name = '数据权限'
        verbose_name_plural = '数据权限'

    def __str__(self):
        return f'{self.role} - {self.module or "全局"}: {self.get_scope_type_display()}'
```

- [ ] **Step 4: 生成并执行迁移**

Run: `cd /home/administrator/erp/backend && python manage.py makemigrations core --name permission_tree_models && python manage.py migrate`

- [ ] **Step 5: 运行测试确认通过**

Run: `cd /home/administrator/erp/backend && python -m pytest apps/core/tests/test_permission_models.py -v --no-header`
Expected: 12 passed

- [ ] **Step 6: 提交**

```bash
cd /home/administrator/erp
git add backend/apps/core/permission_models_new.py backend/apps/core/tests/test_permission_models.py backend/apps/core/migrations/
git commit -m "feat(permission): add RolePermission and DataScope models"
```

---

### Task 3: 权限服务函数 — get_user_permissions 和 has_permission

**Files:**
- Create: `backend/apps/core/permission_service.py`
- Create: `backend/apps/core/tests/test_permission_service.py`

- [ ] **Step 1: 创建测试**

```python
# backend/apps/core/tests/test_permission_service.py
from django.test import TestCase, override_settings
from django.core.cache import cache
from apps.core.permission_models_new import Permission, RolePermission, DataScope
from apps.accounts.models import Role, User, Department
from apps.core.permission_service import (
    get_user_permissions, has_permission, resolve_data_scope,
    apply_scope_filter, get_hidden_fields,
    on_role_permission_change, on_user_role_change,
    get_department_tree_ids,
)


class GetUserPermissionsTest(TestCase):
    def setUp(self):
        cache.clear()
        self.dept = Department.objects.create(name='技术部', code='tech')
        self.role_pm = Role.objects.create(name='项目经理', code='project_manager')
        self.role_eng = Role.objects.create(name='工程师', code='engineer')
        self.user = User.objects.create_user(
            username='testuser', password='test1234', department=self.dept
        )
        self.user.roles.add(self.role_pm, self.role_eng)

        # 权限树
        self.p_proj = Permission.objects.create(code='projects', name='项目管理', type='menu')
        self.p_bom = Permission.objects.create(
            code='projects:bom', name='BOM管理', type='menu', parent=self.p_proj
        )
        self.p_bom_view = Permission.objects.create(
            code='projects:bom:view', name='查看BOM', type='operation', parent=self.p_bom
        )
        self.p_bom_create = Permission.objects.create(
            code='projects:bom:create', name='创建BOM', type='operation', parent=self.p_bom
        )
        self.p_purchase = Permission.objects.create(
            code='purchase:order:view', name='查看采购单', type='operation'
        )

        # 角色权限
        RolePermission.objects.create(role=self.role_pm, permission=self.p_proj)
        RolePermission.objects.create(role=self.role_pm, permission=self.p_bom)
        RolePermission.objects.create(role=self.role_pm, permission=self.p_bom_view)
        RolePermission.objects.create(role=self.role_eng, permission=self.p_bom_create)
        RolePermission.objects.create(role=self.role_eng, permission=self.p_purchase)

    def tearDown(self):
        cache.clear()

    def test_returns_union_of_all_roles(self):
        perms = get_user_permissions(self.user)
        self.assertIn('projects', perms)
        self.assertIn('projects:bom:view', perms)
        self.assertIn('projects:bom:create', perms)
        self.assertIn('purchase:order:view', perms)

    def test_caches_result(self):
        get_user_permissions(self.user)
        cached = cache.get(f'user_perms:{self.user.id}')
        self.assertIsNotNone(cached)

    def test_excludes_inactive_roles(self):
        self.role_eng.is_active = False
        self.role_eng.save()
        cache.clear()
        perms = get_user_permissions(self.user)
        self.assertNotIn('projects:bom:create', perms)
        self.assertNotIn('purchase:order:view', perms)

    def test_excludes_inactive_permissions(self):
        self.p_bom_view.is_active = False
        self.p_bom_view.save()
        cache.clear()
        perms = get_user_permissions(self.user)
        self.assertNotIn('projects:bom:view', perms)


class HasPermissionTest(TestCase):
    def setUp(self):
        cache.clear()
        self.dept = Department.objects.create(name='技术部', code='tech2')
        self.role = Role.objects.create(name='经理', code='manager')
        self.user = User.objects.create_user(
            username='testuser2', password='test1234', department=self.dept
        )
        self.user.roles.add(self.role)
        self.superuser = User.objects.create_superuser(
            username='admin', password='admin1234'
        )

        p_purchase = Permission.objects.create(
            code='purchase:order', name='采购订单', type='menu'
        )
        RolePermission.objects.create(role=self.role, permission=p_purchase)

    def tearDown(self):
        cache.clear()

    def test_exact_match(self):
        self.assertTrue(has_permission(self.user, 'purchase:order'))

    def test_parent_wildcard(self):
        """拥有 purchase:order 则自动拥有 purchase:order:view"""
        self.assertTrue(has_permission(self.user, 'purchase:order:view'))
        self.assertTrue(has_permission(self.user, 'purchase:order:create'))

    def test_no_permission(self):
        self.assertFalse(has_permission(self.user, 'finance:expense:view'))

    def test_superuser_always_true(self):
        self.assertTrue(has_permission(self.superuser, 'anything:at:all'))
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /home/administrator/erp/backend && python -m pytest apps/core/tests/test_permission_service.py -v --no-header 2>&1 | head -10`
Expected: ImportError

- [ ] **Step 3: 创建 permission_service.py — 第一部分**

```python
# backend/apps/core/permission_service.py
from django.core.cache import cache
from apps.core.permission_models_new import Permission, DataScope


CACHE_TIMEOUT = 300  # 5 minutes


def get_user_permissions(user):
    """获取用户所有角色的权限并集，带缓存"""
    cache_key = f'user_perms:{user.id}'
    perms = cache.get(cache_key)
    if perms is None:
        perms = set(
            Permission.objects.filter(
                role_permissions__role__in=user.roles.filter(is_active=True),
                is_active=True
            ).values_list('code', flat=True)
        )
        cache.set(cache_key, perms, timeout=CACHE_TIMEOUT)
    return perms


def has_permission(user, permission_code):
    """检查用户是否拥有某权限（支持父节点通配）"""
    if user.is_superuser:
        return True
    perms = get_user_permissions(user)
    if permission_code in perms:
        return True
    # 父节点匹配：拥有 'purchase:order' 则自动拥有 'purchase:order:*'
    parts = permission_code.rsplit(':', 1)
    while len(parts) > 1:
        parent_code = parts[0]
        if parent_code in perms:
            return True
        parts = parent_code.rsplit(':', 1)
    return False


def on_role_permission_change(role):
    """角色权限变更时清除相关用户缓存"""
    from apps.accounts.models import User
    user_ids = User.objects.filter(roles=role).values_list('id', flat=True)
    cache.delete_many([f'user_perms:{uid}' for uid in user_ids])


def on_user_role_change(user):
    """用户角色变更时清除缓存"""
    cache.delete(f'user_perms:{user.id}')
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /home/administrator/erp/backend && python -m pytest apps/core/tests/test_permission_service.py::GetUserPermissionsTest apps/core/tests/test_permission_service.py::HasPermissionTest -v --no-header`
Expected: 8 passed

- [ ] **Step 5: 提交**

```bash
cd /home/administrator/erp
git add backend/apps/core/permission_service.py backend/apps/core/tests/test_permission_service.py
git commit -m "feat(permission): add get_user_permissions and has_permission service"
```

---

### Task 4: 权限服务函数 — resolve_data_scope 和 apply_scope_filter

**Files:**
- Modify: `backend/apps/core/permission_service.py`
- Modify: `backend/apps/core/tests/test_permission_service.py`

- [ ] **Step 1: 追加测试**

在 `test_permission_service.py` 末尾追加：

```python
class ResolvDataScopeTest(TestCase):
    def setUp(self):
        cache.clear()
        self.dept = Department.objects.create(name='技术部', code='tech3')
        self.role_a = Role.objects.create(name='角色A', code='role_a')
        self.role_b = Role.objects.create(name='角色B', code='role_b')
        self.user = User.objects.create_user(
            username='scopeuser', password='test1234', department=self.dept
        )
        self.user.roles.add(self.role_a, self.role_b)

    def tearDown(self):
        cache.clear()

    def test_global_default_scope(self):
        DataScope.objects.create(role=self.role_a, module='', scope_type='dept')
        scope_type, _ = resolve_data_scope(self.user, 'purchase')
        self.assertEqual(scope_type, 'dept')

    def test_module_override(self):
        DataScope.objects.create(role=self.role_a, module='', scope_type='dept')
        DataScope.objects.create(role=self.role_a, module='finance', scope_type='self')
        scope_type, _ = resolve_data_scope(self.user, 'finance')
        self.assertEqual(scope_type, 'self')

    def test_multi_role_takes_widest(self):
        DataScope.objects.create(role=self.role_a, module='', scope_type='self')
        DataScope.objects.create(role=self.role_b, module='', scope_type='dept_tree')
        scope_type, _ = resolve_data_scope(self.user, 'purchase')
        self.assertEqual(scope_type, 'dept_tree')

    def test_custom_scope_collects_departments(self):
        dept2 = Department.objects.create(name='销售部', code='sales_dept')
        scope_a = DataScope.objects.create(
            role=self.role_a, module='purchase', scope_type='custom'
        )
        scope_a.custom_departments.add(self.dept)
        scope_b = DataScope.objects.create(
            role=self.role_b, module='purchase', scope_type='custom'
        )
        scope_b.custom_departments.add(dept2)
        scope_type, custom_depts = resolve_data_scope(self.user, 'purchase')
        self.assertEqual(scope_type, 'custom')
        self.assertEqual(custom_depts, {self.dept.id, dept2.id})

    def test_no_scope_defaults_to_self(self):
        scope_type, _ = resolve_data_scope(self.user, 'purchase')
        self.assertEqual(scope_type, 'self')


class GetDepartmentTreeIdsTest(TestCase):
    def test_returns_self_and_children(self):
        parent = Department.objects.create(name='总部', code='hq')
        child1 = Department.objects.create(name='技术部', code='tech4', parent=parent)
        child2 = Department.objects.create(name='销售部', code='sales4', parent=parent)
        grandchild = Department.objects.create(name='前端组', code='fe', parent=child1)
        ids = get_department_tree_ids(parent.id)
        self.assertEqual(ids, {parent.id, child1.id, child2.id, grandchild.id})

    def test_leaf_returns_self(self):
        leaf = Department.objects.create(name='独立部门', code='lone')
        ids = get_department_tree_ids(leaf.id)
        self.assertEqual(ids, {leaf.id})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /home/administrator/erp/backend && python -m pytest apps/core/tests/test_permission_service.py::ResolvDataScopeTest apps/core/tests/test_permission_service.py::GetDepartmentTreeIdsTest -v --no-header 2>&1 | head -15`
Expected: ImportError — resolve_data_scope 等不存在

- [ ] **Step 3: 在 permission_service.py 追加数据权限函数**

```python
# 追加到 backend/apps/core/permission_service.py 末尾

def resolve_data_scope(user, module):
    """解析用户在某模块的数据范围（多角色取最宽）"""
    SCOPE_PRIORITY = {'all': 5, 'custom': 4, 'dept_tree': 4, 'dept': 3, 'self': 2}
    best_type = 'self'
    best_priority = 0
    custom_depts = set()

    for role in user.roles.filter(is_active=True):
        scope = (
            DataScope.objects.filter(role=role, module=module).first()
            or DataScope.objects.filter(role=role, module='').first()
        )
        if not scope:
            continue
        priority = SCOPE_PRIORITY.get(scope.scope_type, 0)
        if priority > best_priority:
            best_priority = priority
            best_type = scope.scope_type
        if scope.scope_type == 'custom':
            custom_depts.update(
                scope.custom_departments.values_list('id', flat=True)
            )

    return best_type, custom_depts


def get_department_tree_ids(dept_id):
    """递归获取部门及所有子部门 ID"""
    from apps.accounts.models import Department
    ids = {dept_id}
    children = Department.objects.filter(
        parent_id=dept_id, is_deleted=False
    ).values_list('id', flat=True)
    for child_id in children:
        ids.update(get_department_tree_ids(child_id))
    return ids


def apply_scope_filter(queryset, user, scope_result):
    """根据数据范围过滤查询集"""
    scope_type, custom_depts = scope_result

    if scope_type == 'all':
        return queryset
    elif scope_type == 'self':
        return queryset.filter(created_by=user)
    elif scope_type == 'dept':
        return queryset.filter(created_by__department=user.department)
    elif scope_type == 'dept_tree':
        dept_ids = get_department_tree_ids(user.department_id)
        return queryset.filter(created_by__department_id__in=dept_ids)
    elif scope_type == 'custom':
        return queryset.filter(created_by__department_id__in=custom_depts)
    else:
        return queryset.none()


def get_hidden_fields(user, module, resource):
    """获取用户在某资源上不可见的敏感字段列表"""
    if user.is_superuser:
        return []
    perms = get_user_permissions(user)
    field_permissions = Permission.objects.filter(
        type='field',
        code__startswith=f'{module}:{resource}:',
        is_active=True,
    )
    hidden = []
    for fp in field_permissions:
        if fp.code not in perms:
            hidden.append(fp.field_name)
    return hidden
```

- [ ] **Step 4: 运行全部测试确认通过**

Run: `cd /home/administrator/erp/backend && python -m pytest apps/core/tests/test_permission_service.py -v --no-header`
Expected: 15 passed

- [ ] **Step 5: 提交**

```bash
cd /home/administrator/erp
git add backend/apps/core/permission_service.py backend/apps/core/tests/test_permission_service.py
git commit -m "feat(permission): add resolve_data_scope, apply_scope_filter, get_hidden_fields"
```

---

## Chunk 2: PermissionMixin 与 User/Role 模型改造

### Task 5: 统一 PermissionMixin

**Files:**
- Create: `backend/apps/core/permission_mixin.py`
- Create: `backend/apps/core/tests/test_permission_mixin.py`

- [ ] **Step 1: 创建测试**

```python
# backend/apps/core/tests/test_permission_mixin.py
from django.test import TestCase, RequestFactory
from django.core.cache import cache
from rest_framework.test import force_authenticate
from rest_framework import viewsets, serializers, status
from apps.core.permission_models_new import Permission, RolePermission, DataScope
from apps.core.permission_mixin import PermissionMixin
from apps.accounts.models import Role, User, Department
from apps.core.models import BaseModel
from django.db import models


# 测试用模型 — 使用已有的 AuditLog 作为代理，避免创建新表
# 实际测试中用 User 模型的查询来验证过滤逻辑


class PermissionMixinCheckPermissionsTest(TestCase):
    """测试操作权限校验"""

    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()
        self.dept = Department.objects.create(name='技术部', code='mixin_dept')
        self.role = Role.objects.create(name='测试角色', code='mixin_role')
        self.user = User.objects.create_user(
            username='mixinuser', password='test1234', department=self.dept
        )
        self.user.roles.add(self.role)

        # 权限
        p = Permission.objects.create(
            code='test:item:view', name='查看', type='operation'
        )
        Permission.objects.create(
            code='test:item:create', name='创建', type='operation'
        )
        RolePermission.objects.create(role=self.role, permission=p)

    def tearDown(self):
        cache.clear()

    def test_allowed_action_passes(self):
        """有 view 权限，list 操作应通过"""
        from apps.core.permission_service import has_permission
        self.assertTrue(has_permission(self.user, 'test:item:view'))

    def test_denied_action_blocked(self):
        """无 create 权限，应被拒绝"""
        from apps.core.permission_service import has_permission
        self.assertFalse(has_permission(self.user, 'test:item:create'))


class PermissionMixinContextRoleTest(TestCase):
    """测试上下文角色权限（owner/assignee）"""

    def setUp(self):
        cache.clear()
        self.dept = Department.objects.create(name='技术部', code='ctx_dept')
        self.role = Role.objects.create(name='普通员工', code='ctx_employee')
        self.user = User.objects.create_user(
            username='ctxuser', password='test1234', department=self.dept
        )
        self.user.roles.add(self.role)

        # 只给 @owner 上下文权限，不给静态 edit 权限
        p_owner = Permission.objects.create(
            code='test:item:edit:@owner', name='创建人可编辑', type='operation'
        )
        RolePermission.objects.create(role=self.role, permission=p_owner)

    def tearDown(self):
        cache.clear()

    def test_owner_context_permission(self):
        from apps.core.permission_service import has_permission
        # 没有静态 edit 权限
        self.assertFalse(has_permission(self.user, 'test:item:edit'))
        # 有 @owner 上下文权限
        self.assertTrue(has_permission(self.user, 'test:item:edit:@owner'))
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /home/administrator/erp/backend && python -m pytest apps/core/tests/test_permission_mixin.py -v --no-header 2>&1 | head -10`
Expected: ImportError

- [ ] **Step 3: 创建 PermissionMixin**

```python
# backend/apps/core/permission_mixin.py
from rest_framework.exceptions import PermissionDenied
from apps.core.permission_service import (
    has_permission, resolve_data_scope, apply_scope_filter, get_hidden_fields,
)


class PermissionMixin:
    """统一权限 Mixin — 替代 DataPermissionMixin + FinanceDataMixin +
    OperationPermissionMixin + SensitiveFieldMixin"""

    permission_module = ''
    permission_resource = ''

    # 上下文角色映射，子类可覆盖
    context_role_fields = {
        'owner': 'created_by',
        'assignee': 'assignee',
    }

    def get_queryset(self):
        """数据权限过滤"""
        qs = super().get_queryset()
        user = self.request.user
        if not user.is_authenticated or user.is_superuser:
            return qs
        if not self.permission_module:
            return qs
        scope = resolve_data_scope(user, self.permission_module)
        return apply_scope_filter(qs, user, scope)

    def check_permissions(self, request):
        """操作权限校验（列表/创建等无对象的操作）"""
        super().check_permissions(request)
        if not self.permission_module or not self.permission_resource:
            return
        if not request.user.is_authenticated or request.user.is_superuser:
            return
        action_map = {
            'list': 'view', 'retrieve': 'view',
            'create': 'create', 'update': 'edit',
            'partial_update': 'edit', 'destroy': 'delete',
        }
        action = action_map.get(self.action, self.action)
        code = f'{self.permission_module}:{self.permission_resource}:{action}'
        if not has_permission(request.user, code):
            raise PermissionDenied(f'没有权限: {code}')

    def check_object_permissions(self, request, obj):
        """对象级权限校验 — 支持上下文角色"""
        super().check_object_permissions(request, obj)
        if not self.permission_module or not self.permission_resource:
            return
        user = request.user
        if not user.is_authenticated or user.is_superuser:
            return

        action_map = {
            'retrieve': 'view', 'update': 'edit',
            'partial_update': 'edit', 'destroy': 'delete',
        }
        action = action_map.get(self.action, self.action)
        code = f'{self.permission_module}:{self.permission_resource}:{action}'

        if has_permission(user, code):
            return

        for ctx_role, field_or_func in self.context_role_fields.items():
            ctx_code = f'{code}:@{ctx_role}'
            if has_permission(user, ctx_code):
                if callable(field_or_func):
                    if field_or_func(obj, user):
                        return
                else:
                    field_value = getattr(obj, field_or_func, None)
                    if field_value == user or field_value == user.id:
                        return

        raise PermissionDenied(f'没有权限: {code}')

    def get_serializer(self, *args, **kwargs):
        """敏感字段过滤"""
        serializer = super().get_serializer(*args, **kwargs)
        if not self.permission_module or not self.permission_resource:
            return serializer
        user = self.request.user
        if not user.is_authenticated or user.is_superuser:
            return serializer
        hidden = get_hidden_fields(user, self.permission_module, self.permission_resource)
        for field_name in hidden:
            serializer.fields.pop(field_name, None)
        return serializer
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /home/administrator/erp/backend && python -m pytest apps/core/tests/test_permission_mixin.py -v --no-header`
Expected: 4 passed

- [ ] **Step 5: 提交**

```bash
cd /home/administrator/erp
git add backend/apps/core/permission_mixin.py backend/apps/core/tests/test_permission_mixin.py
git commit -m "feat(permission): add unified PermissionMixin"
```

---

### Task 6: User 模型添加 roles M2M 字段

**Files:**
- Modify: `backend/apps/accounts/models.py:78-159`

- [ ] **Step 1: 在 User 模型中添加 roles 字段**

在 `backend/apps/accounts/models.py` 的 User 类中，在现有 `role = models.ForeignKey(Role, ...)` 行之后添加：

```python
    roles = models.ManyToManyField(
        Role, blank=True, related_name='users_new',
        verbose_name='角色列表',
        help_text='用户可拥有多个角色，权限取并集'
    )
```

注意：保留旧的 `role` FK 字段不删除，确保向后兼容。

- [ ] **Step 2: 更新 User.has_permission() 方法**

将 `backend/apps/accounts/models.py` 中 User 类的 `has_permission` 方法改为：

```python
    def has_permission(self, permission_code):
        """检查用户是否拥有指定权限（使用新权限服务）"""
        from apps.core.permission_service import has_permission as check_perm
        return check_perm(self, permission_code)
```

- [ ] **Step 3: 生成并执行迁移**

Run: `cd /home/administrator/erp/backend && python manage.py makemigrations accounts --name add_user_roles_m2m && python manage.py migrate`

- [ ] **Step 4: 创建数据迁移 — 从 User.role FK 同步到 User.roles M2M**

Run: `cd /home/administrator/erp/backend && python manage.py makemigrations accounts --empty --name migrate_user_role_to_roles`

编辑生成的迁移文件，添加：

```python
from django.db import migrations

def forward(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    for user in User.objects.filter(role__isnull=False):
        user.roles.add(user.role)

def reverse(apps, schema_editor):
    pass  # 不可逆

class Migration(migrations.Migration):
    dependencies = [
        ('accounts', 'XXXX_add_user_roles_m2m'),  # 替换为实际迁移名
    ]
    operations = [
        migrations.RunPython(forward, reverse),
    ]
```

- [ ] **Step 5: 执行数据迁移**

Run: `cd /home/administrator/erp/backend && python manage.py migrate accounts`

- [ ] **Step 6: 验证迁移结果**

Run: `cd /home/administrator/erp/backend && python manage.py shell -c "from apps.accounts.models import User; u = User.objects.filter(role__isnull=False).first(); print(f'User: {u.username}, old role: {u.role}, new roles: {list(u.roles.values_list(\"code\", flat=True))}') if u else print('No users with roles')"`

- [ ] **Step 7: 提交**

```bash
cd /home/administrator/erp
git add backend/apps/accounts/models.py backend/apps/accounts/migrations/
git commit -m "feat(permission): add User.roles M2M and migrate from FK"
```

---

### Task 7: Role 模型添加 permissions M2M 字段

**Files:**
- Modify: `backend/apps/accounts/models.py:44-75`

- [ ] **Step 1: 在 Role 模型中添加 permissions M2M**

在 `backend/apps/accounts/models.py` 的 Role 类中添加：

```python
    from apps.core.permission_models_new import Permission, RolePermission

    permissions_new = models.ManyToManyField(
        'core.Permission', through='core.RolePermission',
        blank=True, related_name='roles',
        verbose_name='权限列表'
    )
```

注意：字段名用 `permissions_new` 避免与现有 `permissions` JSONField 冲突。保留旧字段不删除。

- [ ] **Step 2: 生成并执行迁移**

Run: `cd /home/administrator/erp/backend && python manage.py makemigrations accounts --name add_role_permissions_m2m && python manage.py migrate`

- [ ] **Step 3: 提交**

```bash
cd /home/administrator/erp
git add backend/apps/accounts/models.py backend/apps/accounts/migrations/
git commit -m "feat(permission): add Role.permissions_new M2M via RolePermission"
```

---

## Chunk 3: 权限管理 API 与初始化命令

由于计划文件已经很长（1000+ 行），剩余的 Chunk 3-6 将简化为关键任务概要。完整的分步实现细节请参考设计文档 `docs/superpowers/specs/2026-03-10-permission-system-redesign.md`。

### Task 8: 权限树序列化器和 ViewSet

**Files:**
- Create: `backend/apps/core/permission_serializers.py`
- Create: `backend/apps/core/permission_views.py`
- Modify: `backend/config/urls.py`

**关键步骤：**
1. 创建 PermissionSerializer（支持树形结构递归序列化）
2. 创建 PermissionViewSet（CRUD + 树形列表接口）
3. 创建 DataScopeSerializer
4. 注册路由到 `/api/permissions/`
5. 编写 API 测试
6. 提交

---

### Task 9: init_permissions 管理命令

**Files:**
- Create: `backend/apps/core/management/commands/init_permissions.py`

**关键步骤：**
1. 从 `permission_config.py` 读取 DEFAULT_ROLES、OPERATION_PERMISSIONS、SENSITIVE_FIELDS
2. 生成权限树初始数据（幂等，按 code 创建或更新）
3. 为每个模块生成菜单/操作/字段权限节点
4. 测试命令可重复执行
5. 提交

---

### Task 10: UserProfileSerializer 返回新权限结构

**Files:**
- Modify: `backend/apps/accounts/serializers.py:166-194`
- Modify: `backend/apps/accounts/views.py:105-440`

**关键步骤：**
1. UserProfileSerializer 添加 `permissions`、`menus`、`data_scopes` 字段
2. 实现 `get_permissions()` 方法调用 `get_user_permissions()`
3. 实现 `get_menus()` 方法根据权限树生成菜单结构
4. 实现 `get_data_scopes()` 方法返回数据权限配置
5. 测试登录接口返回新结构
6. 提交

---

### Task 11: RoleSerializer 支持权限树勾选

**Files:**
- Modify: `backend/apps/accounts/serializers.py:37-82`
- Modify: `backend/apps/accounts/views.py:67-102`

**关键步骤：**
1. RoleSerializer 添加 `permission_ids`、`data_scopes` 字段
2. 实现 `create()` 和 `update()` 方法处理权限分配
3. RoleViewSet 添加 `assign_permissions` action
4. 添加 `set_data_scope` action
5. 测试角色权限分配
6. 提交

---

## Chunk 4: 前端权限 Store 与指令

### Task 12: Permission Store

**Files:**
- Create: `frontend/src/stores/permission.js`

**关键步骤：**
1. 创建 permission store（permissions Set, menus, dataScopes）
2. 实现 `setPermissions()` action
3. 实现 `hasPermission()` getter（支持父节点通配）
4. 实现 `setMenus()` 和 `setDataScopes()` actions
5. 提交

---

### Task 13: v-permission 指令

**Files:**
- Create: `frontend/src/directives/permission.js`
- Modify: `frontend/src/main.js`

**关键步骤：**
1. 创建 v-permission 指令（mounted 时检查权限并移除元素）
2. 在 main.js 中注册指令
3. 测试指令在按钮和表格列上的使用
4. 提交

---

### Task 14: 用户登录流程改造

**Files:**
- Modify: `frontend/src/stores/user.js`
- Modify: `frontend/src/api/auth.js`

**关键步骤：**
1. user store 的 `getProfile()` 调用 permission store 的 `setPermissions()`、`setMenus()`、`setDataScopes()`
2. auth.js 添加权限树 API 调用方法
3. 测试登录后权限数据正确加载
4. 提交

---

### Task 15: 路由守卫改造

**Files:**
- Modify: `frontend/src/router/index.js:1199-1430`

**关键步骤：**
1. 删除 `hasMenuAccess()` 函数
2. 删除 `adminOnlyMenus` 和 `menuFallbackPermissions` 配置
3. 路由守卫改为使用 `permissionStore.hasPermission(to.meta?.permission)`
4. 测试路由权限控制
5. 提交

---

### Task 16: MainLayout 动态菜单渲染

**Files:**
- Modify: `frontend/src/layout/MainLayout.vue`

**关键步骤：**
1. 删除所有 `v-if="hasMenuAccess(...)"` 判断
2. 改为直接渲染 `permissionStore.menus`
3. 递归渲染子菜单
4. 测试菜单根据权限动态显示
5. 提交

---

## Chunk 5: 替换旧 Mixin（67 个 ViewSet）

### Task 17: 批量替换 finance 模块 ViewSet（26 个）

**Files:**
- Modify: `backend/apps/finance/views.py`
- Modify: `backend/apps/finance/accounting.py`
- Modify: `backend/apps/finance/asset.py`
- Modify: `backend/apps/finance/bank_statement_views.py`
- Modify: `backend/apps/finance/collection_views.py`
- Modify: `backend/apps/finance/reconciliation_views.py`
- Modify: `backend/apps/finance/tax_management.py`

**关键步骤：**
1. 导入 `from apps.core.permission_mixin import PermissionMixin`
2. 替换 `DataPermissionMixin`、`FinanceDataMixin`、`SensitiveFieldMixin` 为 `PermissionMixin`
3. 为每个 ViewSet 添加 `permission_module` 和 `permission_resource` 属性
4. 运行 finance 模块测试确认无回归
5. 提交

---

### Task 18: 批量替换 purchase 模块 ViewSet（15 个）

**Files:**
- Modify: `backend/apps/purchase/views.py`
- Modify: `backend/apps/purchase/rfq_views.py`
- Modify: `backend/apps/purchase/evaluation_views.py`
- Modify: `backend/apps/purchase/outsource_views.py`

**关键步骤：**
1. 同 Task 17，替换 Mixin 并添加 permission 属性
2. 运行 purchase 模块测试
3. 提交

---

### Task 19: 批量替换 inventory/projects/sales 模块 ViewSet（14 个）

**Files:**
- Modify: `backend/apps/inventory/material_views.py`
- Modify: `backend/apps/inventory/views.py`
- Modify: `backend/apps/masterdata/views.py`
- Modify: `backend/apps/projects/views.py`
- Modify: `backend/apps/sales/views.py`

**关键步骤：**
1. 同 Task 17，替换 Mixin 并添加 permission 属性
2. 运行相关模块测试
3. 提交

---

### Task 20: 工作流服务改造

**Files:**
- Modify: `backend/apps/core/workflow/services.py:153`
- Modify: `backend/apps/core/workflow/mixins.py`

**关键步骤：**
1. `_get_step_assignee()` 中 `User.objects.filter(role=...)` 改为 `User.objects.filter(roles=...)`
2. WorkflowEnforcementMixin 在审批前调用 `has_permission()` 检查审批权限
3. 运行工作流测试
4. 提交

---

## Chunk 6: 前端页面改造与集成测试

### Task 21: 权限树管理页面

**Files:**
- Create: `frontend/src/views/system/PermissionTree.vue`
- Modify: `frontend/src/router/index.js`

**关键步骤：**
1. 创建权限树管理页面（树形展示、新增/编辑/删除/排序）
2. 添加路由 `/system/permissions`
3. 测试权限树 CRUD 功能
4. 提交

---

### Task 22: 角色管理页面改造

**Files:**
- Modify: `frontend/src/views/system/RoleList.vue`

**关键步骤：**
1. 添加权限树勾选组件（el-tree with checkable）
2. 添加数据权限配置表单（全局默认 + 按模块覆盖）
3. 保存时调用新的角色权限分配 API
4. 测试角色权限配置
5. 提交

---

### Task 23: 用户管理页面改造

**Files:**
- Modify: `frontend/src/views/system/UserList.vue`

**关键步骤：**
1. 角色选择从单选改为多选（el-select multiple）
2. 添加权限预览面板（展示用户所有角色的权限并集）
3. 测试用户多角色分配
4. 提交

---

### Task 24: 业务页面添加 v-permission 指令（示例）

**Files:**
- Modify: `frontend/src/views/purchase/PurchaseOrderList.vue`
- Modify: `frontend/src/views/projects/BOMList.vue`

**关键步骤：**
1. 为按钮添加 v-permission（如 `v-permission="'purchase:order:create'"`）
2. 为敏感字段列添加 v-permission（如 `v-permission="'purchase:order:view_price'"`）
3. 测试权限控制生效
4. 提交

注：其余业务页面的 v-permission 添加可在后续迭代中逐步完成。

---

### Task 25: 端到端集成测试

**Files:**
- Create: `backend/apps/core/tests/test_permission_integration.py`

**关键步骤：**
1. 创建集成测试：用户登录 → 获取权限 → 访问 API → 验证权限控制
2. 测试多角色权限并集
3. 测试数据权限过滤
4. 测试敏感字段隐藏
5. 测试上下文角色权限（owner/assignee）
6. 运行全部测试确认通过
7. 提交

---

### Task 26: 文档更新与清理

**Files:**
- Update: `README.md`
- Update: `CLAUDE.md`
- Mark deprecated: `backend/apps/core/permission_config.py`
- Mark deprecated: `backend/apps/core/data_permission.py`

**关键步骤：**
1. 更新 README 说明新权限体系
2. 更新 CLAUDE.md 中的权限相关说明
3. 在旧文件顶部添加 `# DEPRECATED: 使用 permission_service.py 替代` 注释
4. 提交

---

## 执行建议

**总任务数：26 个**
**预计工作量：5-7 天**

**执行顺序：**
1. Chunk 1-2（Task 1-7）：后端核心模型与服务 — 2 天
2. Chunk 3（Task 8-11）：权限管理 API — 1 天
3. Chunk 4（Task 12-16）：前端权限 Store 与指令 — 1 天
4. Chunk 5（Task 17-20）：替换旧 Mixin — 1.5 天
5. Chunk 6（Task 21-26）：前端页面改造与集成测试 — 1.5 天

**风险点：**
- Task 17-19 涉及 67 个 ViewSet 的批量替换，需要仔细测试避免回归
- Task 10 的菜单树生成逻辑需要与前端路由定义对齐
- Task 25 的集成测试需要覆盖所有权限场景

**回滚方案：**
- 保留旧字段（User.role、Role.permissions、Role.data_scope）直到新系统稳定
- 新表（Permission、RolePermission、DataScope）不影响旧代码运行
- 可随时回滚代码到旧版本

---

计划完成。准备执行？
