"""
Tests for PermissionMixin
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import serializers, viewsets
from rest_framework.test import APIRequestFactory

from apps.accounts.models import Role
from apps.core.permission_mixin import PermissionMixin
from apps.core.permission_models_new import Permission, RolePermission
from apps.projects.models import Project

User = get_user_model()


class TestModel:
    """Mock model for testing"""

    def __init__(self, created_by=None, assignee=None):
        self.created_by = created_by
        self.assignee = assignee


class TestSerializer(serializers.Serializer):
    """Mock serializer for testing"""

    name = serializers.CharField()
    sensitive_field = serializers.CharField()


class TestViewSet(PermissionMixin, viewsets.ModelViewSet):
    """Mock ViewSet for testing"""

    permission_module = 'projects'
    permission_resource = 'project'
    context_role_fields = {'owner': 'created_by', 'assignee': 'assignee'}
    serializer_class = TestSerializer
    queryset = Project.objects.all()


class PermissionMixinCheckPermissionsTest(TestCase):
    """Test check_permissions method"""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.role = Role.objects.create(name='Test Role', code='test_role')
        self.user.role = self.role
        self.user.save()

    def test_allowed_action_passes(self):
        """Test that allowed action passes permission check"""
        # Create permission for projects:project:view
        perm = Permission.objects.create(code='projects:project:view', name='View Project', type='operation')
        RolePermission.objects.create(role=self.role, permission=perm)

        # Create request
        request = self.factory.get('/api/projects/')
        request.user = self.user

        # Create viewset instance
        viewset = TestViewSet()
        viewset.request = request
        viewset.action = 'list'

        # Should not raise exception
        try:
            viewset.check_permissions(request)
            passed = True
        except Exception:
            passed = False

        self.assertTrue(passed, 'Permission check should pass for allowed action')

    def test_denied_action_blocked(self):
        """Test that denied action is blocked"""
        # Don't create permission for projects:project:delete
        # User should be denied

        # Create request
        request = self.factory.delete('/api/projects/1/')
        request.user = self.user

        # Create viewset instance
        viewset = TestViewSet()
        viewset.request = request
        viewset.action = 'destroy'

        # Should raise PermissionDenied
        from rest_framework.exceptions import PermissionDenied

        with self.assertRaises(PermissionDenied):
            viewset.check_permissions(request)


class PermissionMixinContextRoleTest(TestCase):
    """Test context role permissions (@owner, @assignee)"""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.owner_user = User.objects.create_user(username='owner', password='testpass123')
        self.other_user = User.objects.create_user(username='other', password='testpass123')
        self.role = Role.objects.create(name='Test Role', code='test_role')
        self.owner_user.role = self.role
        self.owner_user.save()
        self.other_user.role = self.role
        self.other_user.save()

        # Create project
        self.project = Project.objects.create(name='Test Project', code='TEST001', created_by=self.owner_user)

    def test_owner_context_permission(self):
        """Test that @owner context role grants permission"""
        # Create permission for @owner to edit: projects:project:edit@owner
        perm = Permission.objects.create(code='projects:project:edit@owner', name='Edit Own Project', type='operation')
        RolePermission.objects.create(role=self.role, permission=perm)

        # Owner should have permission
        request = self.factory.put(f'/api/projects/{self.project.id}/')
        request.user = self.owner_user

        viewset = TestViewSet()
        viewset.request = request
        viewset.action = 'update'

        # Should not raise exception for owner
        try:
            viewset.check_object_permissions(request, self.project)
            owner_passed = True
        except Exception:
            owner_passed = False

        self.assertTrue(owner_passed, 'Owner should have permission')

        # Other user should NOT have permission
        request.user = self.other_user
        viewset.request = request

        from rest_framework.exceptions import PermissionDenied

        with self.assertRaises(PermissionDenied):
            viewset.check_object_permissions(request, self.project)

    def test_context_permission_requires_context(self):
        """测试上下文权限需要上下文才生效"""
        from apps.core.permission_service import has_permission

        # Create permission for @owner to edit: projects:project:edit@owner
        perm = Permission.objects.create(code='projects:project:edit@owner', name='Edit Own Project', type='operation')
        RolePermission.objects.create(role=self.role, permission=perm)
        # 用户有 @owner 上下文权限
        self.assertTrue(has_permission(self.owner_user, 'projects:project:edit@owner'))
        # 但没有静态 edit 权限
        self.assertFalse(has_permission(self.owner_user, 'projects:project:edit'))
