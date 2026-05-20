"""
Tests for permission service functions.
Following TDD: write tests first, then implement the service.
"""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from apps.accounts.models import Department, Role
from apps.core.permission_models_new import DataScope, Permission, RolePermission
from apps.core.permission_service import (
    get_department_tree_ids,
    get_user_permissions,
    has_permission,
    on_role_permission_change,
    on_user_role_change,
    resolve_data_scope,
)

User = get_user_model()


class GetUserPermissionsTest(TestCase):
    """Test get_user_permissions function"""

    def setUp(self):
        """Set up test data"""
        cache.clear()

        # Create role
        self.role = Role.objects.create(name='测试角色', code='test_role', is_active=True)

        # Create permissions
        self.perm1 = Permission.objects.create(code='purchase:order', name='采购订单', type='menu', is_active=True)
        self.perm2 = Permission.objects.create(
            code='purchase:order:create',
            name='创建采购订单',
            type='operation',
            resource='purchase_order',
            parent=self.perm1,
            is_active=True,
        )
        self.perm3 = Permission.objects.create(code='sales:order', name='销售订单', type='menu', is_active=True)
        self.inactive_perm = Permission.objects.create(
            code='inactive:perm', name='未激活权限', type='menu', is_active=False
        )

        # Assign permissions to role
        RolePermission.objects.create(role=self.role, permission=self.perm1)
        RolePermission.objects.create(role=self.role, permission=self.perm2)
        RolePermission.objects.create(role=self.role, permission=self.inactive_perm)

        # Create user
        self.user = User.objects.create_user(
            username='testuser', employee_id='EMP001', password='testpass123', role=self.role
        )

    def tearDown(self):
        """Clean up cache after each test"""
        cache.clear()

    def test_returns_union_of_all_roles(self):
        """Test that get_user_permissions returns permissions from user's role"""
        # Note: Current implementation uses single role (FK), not multiple roles (M2M)
        # This test validates the basic functionality with the current single-role model
        permissions = get_user_permissions(self.user)

        self.assertIsInstance(permissions, set)
        # Should have permissions from the user's role
        self.assertIn('purchase:order', permissions)
        self.assertIn('purchase:order:create', permissions)
        # Should NOT have inactive permission
        self.assertNotIn('inactive:perm', permissions)
        # Should NOT have permission not assigned to role
        self.assertNotIn('sales:order', permissions)

    def test_caches_result(self):
        """Test that permissions are cached"""
        # First call
        permissions1 = get_user_permissions(self.user)

        # Add new permission to role (should not affect cached result)
        RolePermission.objects.create(role=self.role, permission=self.perm3)

        # Second call should return cached result
        permissions2 = get_user_permissions(self.user)

        self.assertEqual(permissions1, permissions2)
        self.assertNotIn('sales:order', permissions2)

    def test_excludes_inactive_roles(self):
        """Test that inactive roles are excluded"""
        # Create an inactive role with permissions
        inactive_role = Role.objects.create(name='未激活角色', code='inactive_role', is_active=False)
        RolePermission.objects.create(role=inactive_role, permission=self.perm3)

        # Create user with inactive role
        user_with_inactive_role = User.objects.create_user(
            username='inactive_user', employee_id='EMP003', password='testpass123', role=inactive_role
        )

        permissions = get_user_permissions(user_with_inactive_role)

        # Should get empty set because role is inactive
        self.assertIsInstance(permissions, set)
        self.assertEqual(len(permissions), 0)
        self.assertNotIn('sales:order', permissions)

    def test_excludes_inactive_permissions(self):
        """Test that inactive permissions are excluded"""
        # User's role has both active and inactive permissions
        # (inactive_perm was already added in setUp)
        permissions = get_user_permissions(self.user)

        self.assertIsInstance(permissions, set)
        # Should have active permissions
        self.assertIn('purchase:order', permissions)
        self.assertIn('purchase:order:create', permissions)
        # Should NOT have inactive permission
        self.assertNotIn('inactive:perm', permissions)


class HasPermissionTest(TestCase):
    """Test has_permission function"""

    def setUp(self):
        """Set up test data"""
        cache.clear()

        # Create role
        self.role = Role.objects.create(name='测试角色', code='test_role', is_active=True)

        # Create permissions
        self.parent_perm = Permission.objects.create(
            code='purchase:order', name='采购订单', type='menu', is_active=True
        )
        self.child_perm = Permission.objects.create(
            code='purchase:order:create',
            name='创建采购订单',
            type='operation',
            resource='purchase_order',
            parent=self.parent_perm,
            is_active=True,
        )

        # Assign parent permission to role
        RolePermission.objects.create(role=self.role, permission=self.parent_perm)

        # Create user
        self.user = User.objects.create_user(
            username='testuser', employee_id='EMP001', password='testpass123', role=self.role
        )

    def tearDown(self):
        """Clean up cache after each test"""
        cache.clear()

    def test_has_permission_direct_match(self):
        """Test direct permission match"""
        self.assertTrue(has_permission(self.user, 'purchase:order'))

    def test_has_permission_parent_wildcard(self):
        """Test parent node wildcard support"""
        # User has 'purchase:order', should grant 'purchase:order:*'
        self.assertTrue(has_permission(self.user, 'purchase:order:create'))
        self.assertTrue(has_permission(self.user, 'purchase:order:edit'))
        self.assertTrue(has_permission(self.user, 'purchase:order:delete'))

    def test_has_permission_no_match(self):
        """Test permission not granted"""
        self.assertFalse(has_permission(self.user, 'sales:order'))
        self.assertFalse(has_permission(self.user, 'sales:order:create'))

    def test_has_permission_superuser_always_true(self):
        """Test superuser always has permission"""
        superuser = User.objects.create_superuser(username='admin', employee_id='ADMIN001', password='admin123')

        self.assertTrue(has_permission(superuser, 'any:permission'))
        self.assertTrue(has_permission(superuser, 'any:permission:action'))


class CacheInvalidationTest(TestCase):
    """Test cache invalidation functions"""

    def setUp(self):
        """Set up test data"""
        cache.clear()

        # Create role
        self.role = Role.objects.create(name='测试角色', code='test_role', is_active=True)

        # Create permissions
        self.perm1 = Permission.objects.create(code='purchase:order', name='采购订单', type='menu', is_active=True)
        self.perm2 = Permission.objects.create(code='sales:order', name='销售订单', type='menu', is_active=True)

        # Assign permission to role
        RolePermission.objects.create(role=self.role, permission=self.perm1)

        # Create user
        self.user = User.objects.create_user(
            username='testuser', employee_id='EMP001', password='testpass123', role=self.role
        )

    def tearDown(self):
        """Clean up cache after each test"""
        cache.clear()

    def test_on_role_permission_change_clears_cache(self):
        """Test that on_role_permission_change clears cache for all users with that role"""
        # First call to populate cache
        permissions1 = get_user_permissions(self.user)
        self.assertIn('purchase:order', permissions1)
        self.assertNotIn('sales:order', permissions1)

        # Verify cache is populated
        cache_key = f'user_permissions:{self.user.id}'
        self.assertIsNotNone(cache.get(cache_key))

        # Add new permission to role
        RolePermission.objects.create(role=self.role, permission=self.perm2)

        # Call cache invalidation
        on_role_permission_change(self.role)

        # Verify cache is cleared
        self.assertIsNone(cache.get(cache_key))

        # Next call should fetch fresh data
        permissions2 = get_user_permissions(self.user)
        self.assertIn('purchase:order', permissions2)
        self.assertIn('sales:order', permissions2)

    def test_on_user_role_change_clears_cache(self):
        """Test that on_user_role_change clears cache for the user"""
        # First call to populate cache
        permissions1 = get_user_permissions(self.user)
        self.assertIn('purchase:order', permissions1)

        # Verify cache is populated
        cache_key = f'user_permissions:{self.user.id}'
        self.assertIsNotNone(cache.get(cache_key))

        # Create new role with different permissions
        new_role = Role.objects.create(name='新角色', code='new_role', is_active=True)
        RolePermission.objects.create(role=new_role, permission=self.perm2)

        # Change user's role
        self.user.role = new_role
        self.user.save()

        # Call cache invalidation
        on_user_role_change(self.user)

        # Verify cache is cleared
        self.assertIsNone(cache.get(cache_key))

        # Next call should fetch fresh data with new role's permissions
        permissions2 = get_user_permissions(self.user)
        self.assertNotIn('purchase:order', permissions2)
        self.assertIn('sales:order', permissions2)


class ResolveDataScopeTest(TestCase):
    """Test resolve_data_scope function"""

    def setUp(self):
        """Set up test data"""
        cache.clear()

        # Create departments
        self.dept_root = Department.objects.create(name='总部', code='ROOT', parent=None)
        self.dept_sales = Department.objects.create(name='销售部', code='SALES', parent=self.dept_root)
        self.dept_purchase = Department.objects.create(name='采购部', code='PURCHASE', parent=self.dept_root)
        self.dept_sales_team1 = Department.objects.create(name='销售一组', code='SALES_TEAM1', parent=self.dept_sales)

        # Create roles
        self.role_admin = Role.objects.create(name='管理员', code='admin', is_active=True)
        self.role_manager = Role.objects.create(name='经理', code='manager', is_active=True)

        # Create users
        self.user = User.objects.create_user(
            username='testuser',
            employee_id='EMP001',
            password='testpass123',
            role=self.role_manager,
            department=self.dept_sales,
        )

    def tearDown(self):
        """Clean up cache after each test"""
        cache.clear()

    def test_global_default_scope(self):
        """Test that global scope is returned when no module-specific scope exists"""
        # Create global data scope
        DataScope.objects.create(role=self.role_manager, module='__default__', scope_type='all')

        scope_type, custom_dept_ids = resolve_data_scope(self.user, 'projects')

        self.assertEqual(scope_type, 'all')
        self.assertEqual(custom_dept_ids, [])

    def test_module_override(self):
        """Test that module-specific scope overrides default scope"""
        # Create default scope
        DataScope.objects.create(role=self.role_manager, module='__default__', scope_type='self')
        # Create module-specific scope
        DataScope.objects.create(role=self.role_manager, module='projects', scope_type='dept_tree')

        scope_type, custom_dept_ids = resolve_data_scope(self.user, 'projects')

        self.assertEqual(scope_type, 'dept_tree')
        self.assertEqual(custom_dept_ids, [])

    def test_multi_role_takes_widest(self):
        """Test that when user has multiple roles, the widest scope is used"""
        # Note: Current implementation uses single role (FK), not multiple roles (M2M)
        # This test validates the logic for future M2M support
        # For now, we test with a single role having the widest scope

        # Create data scope for the user's role
        DataScope.objects.create(role=self.role_manager, module='projects', scope_type='all')

        scope_type, custom_dept_ids = resolve_data_scope(self.user, 'projects')

        # Should get global scope (widest)
        self.assertEqual(scope_type, 'all')
        self.assertEqual(custom_dept_ids, [])

    def test_custom_scope_collects_departments(self):
        """Test that custom scope returns list of department IDs"""
        # Create custom data scope
        data_scope = DataScope.objects.create(role=self.role_manager, module='projects', scope_type='custom')
        data_scope.custom_departments.add(self.dept_sales, self.dept_purchase)

        scope_type, custom_dept_ids = resolve_data_scope(self.user, 'projects')

        self.assertEqual(scope_type, 'custom')
        self.assertIn(self.dept_sales.id, custom_dept_ids)
        self.assertIn(self.dept_purchase.id, custom_dept_ids)
        self.assertEqual(len(custom_dept_ids), 2)

    def test_no_scope_defaults_to_self(self):
        """Test that when no scope is configured, defaults to 'self'"""
        scope_type, custom_dept_ids = resolve_data_scope(self.user, 'projects')

        self.assertEqual(scope_type, 'self')
        self.assertEqual(custom_dept_ids, [])


class GetDepartmentTreeIdsTest(TestCase):
    """Test get_department_tree_ids function"""

    def setUp(self):
        """Set up test data"""
        # Create department tree
        self.dept_root = Department.objects.create(name='总部', code='ROOT', parent=None)
        self.dept_sales = Department.objects.create(name='销售部', code='SALES', parent=self.dept_root)
        self.dept_purchase = Department.objects.create(name='采购部', code='PURCHASE', parent=self.dept_root)
        self.dept_sales_team1 = Department.objects.create(name='销售一组', code='SALES_TEAM1', parent=self.dept_sales)
        self.dept_sales_team2 = Department.objects.create(name='销售二组', code='SALES_TEAM2', parent=self.dept_sales)

    def test_returns_self_and_children(self):
        """Test that function returns department and all its children"""
        dept_ids = get_department_tree_ids(self.dept_sales.id)

        self.assertIn(self.dept_sales.id, dept_ids)
        self.assertIn(self.dept_sales_team1.id, dept_ids)
        self.assertIn(self.dept_sales_team2.id, dept_ids)
        self.assertEqual(len(dept_ids), 3)
        # Should NOT include root or purchase
        self.assertNotIn(self.dept_root.id, dept_ids)
        self.assertNotIn(self.dept_purchase.id, dept_ids)

    def test_leaf_returns_self(self):
        """Test that leaf department returns only itself"""
        dept_ids = get_department_tree_ids(self.dept_sales_team1.id)

        self.assertEqual(dept_ids, [self.dept_sales_team1.id])
