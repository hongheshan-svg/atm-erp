from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.accounts.models import Role
from apps.accounts.serializers import RoleSerializer, UserProfileSerializer
from apps.accounts.views import RoleViewSet

User = get_user_model()


class RoleMembershipPermissionTest(TestCase):
    def setUp(self):
        self.role = Role.objects.create(name='多角色成员角色', code='multi_member_role')
        self.member = User.objects.create_user(
            username='multi-member',
            employee_id='MULTI001',
            password='testpass123',
        )
        self.member.roles.add(self.role)

    def test_role_user_count_includes_m2m_memberships(self):
        self.assertEqual(RoleSerializer(self.role).data['user_count'], 1)

    def test_role_with_m2m_members_cannot_be_deleted(self):
        root = User.objects.create_superuser(
            username='root-role-delete',
            employee_id='ROOTROLE001',
            password='testpass123',
        )
        request = APIRequestFactory().delete(f'/api/accounts/roles/{self.role.id}/')
        force_authenticate(request, user=root)

        response = RoleViewSet.as_view({'delete': 'destroy'})(request, pk=self.role.id)

        self.assertEqual(response.status_code, 400)
        self.assertTrue(Role.objects.filter(pk=self.role.id).exists())

    def test_profile_roles_include_legacy_and_m2m_assignments(self):
        legacy_role = Role.objects.create(name='旧角色', code='legacy_role')
        self.member.role = legacy_role
        self.member.save(update_fields=['role'])

        roles = UserProfileSerializer(self.member).data['roles']

        self.assertCountEqual(roles, ['legacy_role', 'multi_member_role'])
