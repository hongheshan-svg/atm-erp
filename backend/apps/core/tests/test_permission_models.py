from django.test import TestCase
from django.db import IntegrityError
from django.core.exceptions import ValidationError
from apps.core.permission_models_new import Permission


class PermissionModelTest(TestCase):
    """Test cases for Permission model"""

    def test_create_menu_permission(self):
        """Test creating a menu permission"""
        menu = Permission.objects.create(
            code='system',
            name='系统管理',
            type='menu',
            route_path='/system',
            icon='el-icon-setting',
            sort_order=1
        )
        self.assertEqual(menu.code, 'system')
        self.assertEqual(menu.name, '系统管理')
        self.assertEqual(menu.type, 'menu')
        self.assertEqual(menu.route_path, '/system')
        self.assertEqual(menu.icon, 'el-icon-setting')
        self.assertEqual(menu.sort_order, 1)
        self.assertTrue(menu.is_active)
        self.assertIsNone(menu.parent)

    def test_create_child_permission(self):
        """Test creating a child permission with parent"""
        parent = Permission.objects.create(
            code='system',
            name='系统管理',
            type='menu',
            sort_order=1
        )
        child = Permission.objects.create(
            parent=parent,
            code='system:user',
            name='用户管理',
            type='menu',
            route_path='/system/user',
            sort_order=1
        )
        self.assertEqual(child.parent, parent)
        self.assertEqual(child.code, 'system:user')
        self.assertEqual(child.name, '用户管理')

    def test_create_operation_permission(self):
        """Test creating an operation permission"""
        menu = Permission.objects.create(
            code='system:user',
            name='用户管理',
            type='menu',
            sort_order=1
        )
        operation = Permission.objects.create(
            parent=menu,
            code='system:user:create',
            name='创建用户',
            type='operation',
            resource='user',
            sort_order=1
        )
        self.assertEqual(operation.type, 'operation')
        self.assertEqual(operation.resource, 'user')
        self.assertEqual(operation.parent, menu)

    def test_create_field_permission(self):
        """Test creating a field permission"""
        operation = Permission.objects.create(
            code='system:user:view',
            name='查看用户',
            type='operation',
            resource='user',
            sort_order=1
        )
        field = Permission.objects.create(
            parent=operation,
            code='system:user:view:salary',
            name='查看薪资',
            type='field',
            resource='user',
            field_name='salary',
            sort_order=1
        )
        self.assertEqual(field.type, 'field')
        self.assertEqual(field.field_name, 'salary')
        self.assertEqual(field.resource, 'user')
        self.assertEqual(field.parent, operation)

    def test_permission_code_unique(self):
        """Test that permission code must be unique"""
        Permission.objects.create(
            code='system',
            name='系统管理',
            type='menu',
            sort_order=1
        )
        with self.assertRaises(IntegrityError):
            Permission.objects.create(
                code='system',
                name='系统管理2',
                type='menu',
                sort_order=2
            )

    def test_permission_str(self):
        """Test string representation of permission"""
        permission = Permission.objects.create(
            code='system',
            name='系统管理',
            type='menu',
            sort_order=1
        )
        self.assertEqual(str(permission), '系统管理 (system)')

    def test_is_active_filtering(self):
        """Test filtering by is_active status"""
        # Create active permission
        active = Permission.objects.create(
            code='system:active',
            name='Active Permission',
            type='menu',
            is_active=True,
            sort_order=1
        )
        # Create inactive permission
        inactive = Permission.objects.create(
            code='system:inactive',
            name='Inactive Permission',
            type='menu',
            is_active=False,
            sort_order=2
        )

        # Test filtering
        active_perms = Permission.objects.filter(is_active=True)
        inactive_perms = Permission.objects.filter(is_active=False)

        self.assertIn(active, active_perms)
        self.assertNotIn(inactive, active_perms)
        self.assertIn(inactive, inactive_perms)
        self.assertNotIn(active, inactive_perms)

    def test_validation_field_permission_without_field_name(self):
        """Test that field permission without field_name raises ValidationError"""
        field_perm = Permission(
            code='system:user:view:field',
            name='Field Permission',
            type='field',
            resource='user',
            sort_order=1
        )
        with self.assertRaises(ValidationError) as context:
            field_perm.full_clean()
        self.assertIn('field_name', context.exception.message_dict)

    def test_validation_operation_permission_without_resource(self):
        """Test that operation permission without resource raises ValidationError"""
        operation_perm = Permission(
            code='system:user:create',
            name='Create User',
            type='operation',
            sort_order=1
        )
        with self.assertRaises(ValidationError) as context:
            operation_perm.full_clean()
        self.assertIn('resource', context.exception.message_dict)

    def test_validation_self_referencing_parent(self):
        """Test that self-referencing parent raises ValidationError"""
        permission = Permission.objects.create(
            code='system',
            name='System',
            type='menu',
            sort_order=1
        )
        permission.parent = permission
        with self.assertRaises(ValidationError) as context:
            permission.full_clean()
        self.assertIn('parent', context.exception.message_dict)

    def test_children_relationship_queries(self):
        """Test querying children relationship"""
        parent = Permission.objects.create(
            code='system',
            name='System Management',
            type='menu',
            sort_order=1
        )
        child1 = Permission.objects.create(
            parent=parent,
            code='system:user',
            name='User Management',
            type='menu',
            sort_order=1
        )
        child2 = Permission.objects.create(
            parent=parent,
            code='system:role',
            name='Role Management',
            type='menu',
            sort_order=2
        )

        # Test children relationship
        children = parent.children.all()
        self.assertEqual(children.count(), 2)
        self.assertIn(child1, children)
        self.assertIn(child2, children)

        # Test ordering by sort_order
        ordered_children = list(children)
        self.assertEqual(ordered_children[0], child1)
        self.assertEqual(ordered_children[1], child2)
