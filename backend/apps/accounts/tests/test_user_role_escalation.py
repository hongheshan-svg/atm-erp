"""
用户角色提权 + 审计分析权限回归测试（提交后对抗式复核发现的提权路径）。

修复点：
1. audit_analytics 的 AuditLogAnalyticsView/AuditLogSecurityView 曾被误降级为 IsAuthenticated
   （任意登录用户可读全系统审计情报）→ 恢复为仅系统管理员（IsSystemAdmin）。
2. update_profile 是 SELF_ACTION（仅需登录），原用含 role/is_staff/is_active 的 UserUpdateSerializer，
   任意登录用户可 PUT /users/update_profile/ 自助提权 → 改用 ProfileSelfUpdateSerializer（仅个人非权限字段）。
3. UserViewSet 建/改用户：非系统管理员（如持 system:user 的 HR）不得分配「特权角色」（授予 system 权限的角色）。
"""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.accounts.models import Role
from apps.accounts.serializers import (
    ProfileSelfUpdateSerializer,
    UserCreateSerializer,
    UserUpdateSerializer,
)
from apps.core.permission_models_new import Permission, RolePermission

User = get_user_model()
factory = APIRequestFactory()


class UserRoleEscalationTest(TestCase):
    def setUp(self):
        cache.clear()
        # 特权角色：授予 system 权限
        self.sys_perm = Permission.objects.create(code='system', name='系统管理', type='menu', is_active=True)
        self.admin_role = Role.objects.create(name='管理员', code='admin', is_active=True)
        RolePermission.objects.create(role=self.admin_role, permission=self.sys_perm)
        # 普通角色：无 system 权限
        self.normal_role = Role.objects.create(name='员工', code='employee', is_active=True)

        self.hr = User.objects.create_user(username='hr', password='x', employee_id='hr', role=self.normal_role)
        self.employee = User.objects.create_user(
            username='emp', password='x', employee_id='emp', role=self.normal_role
        )
        self.root = User.objects.create_superuser(username='root', password='x', employee_id='root')

    def _req(self, user):
        r = factory.post('/x/')
        r.user = user
        return r

    def _create_payload(self, username, role_id):
        return {
            'username': username,
            'email': f'{username}@x.com',
            'password': 'pass12',
            'password_confirm': 'pass12',
            'role': role_id,
        }

    def test_non_admin_cannot_assign_privileged_role_on_create(self):
        s = UserCreateSerializer(
            data=self._create_payload('n1', self.admin_role.id), context={'request': self._req(self.hr)}
        )
        self.assertFalse(s.is_valid())
        self.assertIn('role', s.errors)

    def test_non_admin_can_assign_normal_role_on_create(self):
        s = UserCreateSerializer(
            data=self._create_payload('n2', self.normal_role.id), context={'request': self._req(self.hr)}
        )
        self.assertTrue(s.is_valid(), s.errors)

    def test_superuser_can_assign_privileged_role(self):
        s = UserCreateSerializer(
            data=self._create_payload('n3', self.admin_role.id), context={'request': self._req(self.root)}
        )
        self.assertTrue(s.is_valid(), s.errors)

    def test_non_admin_cannot_escalate_existing_user_via_update(self):
        s = UserUpdateSerializer(
            instance=self.employee,
            data={'role': self.admin_role.id},
            partial=True,
            context={'request': self._req(self.hr)},
        )
        self.assertFalse(s.is_valid())
        self.assertIn('role', s.errors)

    def test_profile_self_serializer_excludes_privileged_fields(self):
        fields = set(ProfileSelfUpdateSerializer().fields.keys())
        self.assertFalse(
            fields & {'role', 'is_staff', 'is_active', 'department', 'position', 'hire_date'},
            f'自助资料序列化器不得暴露管理字段，实际含: {fields}',
        )

    def test_update_profile_ignores_role_and_is_staff(self):
        # 任意登录用户经 update_profile 自助提权应无效：role/is_staff 被忽略
        s = ProfileSelfUpdateSerializer(
            instance=self.employee,
            data={'first_name': 'A', 'role': self.admin_role.id, 'is_staff': True},
            partial=True,
        )
        self.assertTrue(s.is_valid(), s.errors)
        s.save()
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.role_id, self.normal_role.id)  # role 未被改
        self.assertFalse(self.employee.is_staff)  # is_staff 未被改
        self.assertEqual(self.employee.first_name, 'A')  # 合法字段已更新


class AuditAnalyticsPermissionTest(TestCase):
    def setUp(self):
        cache.clear()
        self.employee = User.objects.create_user(username='emp2', password='x', employee_id='emp2')
        self.root = User.objects.create_superuser(username='root2', password='x', employee_id='root2')

    def _get(self, view_cls, user):
        request = factory.get('/x/')
        force_authenticate(request, user=user)
        return view_cls.as_view()(request)

    def test_employee_denied_audit_analytics(self):
        from apps.core.audit_analytics import AuditLogAnalyticsView, AuditLogSecurityView

        self.assertEqual(self._get(AuditLogAnalyticsView, self.employee).status_code, 403)
        self.assertEqual(self._get(AuditLogSecurityView, self.employee).status_code, 403)

    def test_superuser_allowed_audit_analytics(self):
        from apps.core.audit_analytics import AuditLogAnalyticsView

        self.assertEqual(self._get(AuditLogAnalyticsView, self.root).status_code, 200)
