from datetime import date, timedelta

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.accounts.models import Role
from apps.core.permission_models_new import DataScope, Permission, RolePermission
from apps.masterdata.models import Customer
from apps.projects.equipment_models import Equipment
from apps.projects.models import Project

User = get_user_model()


class MaintenanceReminderPermissionTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='maintenance-self',
            employee_id='maintenance-self',
            password='test-password',
        )
        self.other_user = User.objects.create_user(
            username='maintenance-other',
            employee_id='maintenance-other',
            password='test-password',
        )
        self.role = Role.objects.create(name='维保本人范围', code='maintenance-self-role')
        self.user.roles.add(self.role)
        self.client.force_authenticate(self.user)
        customer = Customer.objects.create(code='C-MAINTENANCE', name='维保客户')
        own_project = Project.objects.create(
            code='PRJ-MAINT-OWN',
            name='本人项目',
            customer=customer,
            manager=self.user,
            start_date=date.today(),
            end_date=date.today(),
            created_by=self.user,
        )
        other_project = Project.objects.create(
            code='PRJ-MAINT-OTHER',
            name='他人项目',
            customer=customer,
            manager=self.other_user,
            start_date=date.today(),
            end_date=date.today(),
            created_by=self.other_user,
        )
        expiry = date.today() + timedelta(days=7)
        Equipment.objects.create(
            equipment_no='EQ-MAINT-OWN',
            name='本人设备',
            project=own_project,
            customer=customer,
            warranty_end_date=expiry,
            created_by=self.user,
        )
        Equipment.objects.create(
            equipment_no='EQ-MAINT-OTHER',
            name='他人设备',
            project=other_project,
            customer=customer,
            warranty_end_date=expiry,
            created_by=self.other_user,
        )

    def _grant_maintenance(self):
        permission = Permission.objects.create(code='equipment:maintenance', name='设备维保', type='menu')
        RolePermission.objects.create(role=self.role, permission=permission)
        DataScope.objects.create(role=self.role, module='projects', scope_type='self')

    def test_reminders_require_maintenance_menu(self):
        response = self.client.get('/api/projects/maintenance-reminders/warranty_expiring/')

        self.assertEqual(response.status_code, 403)

    def test_warranty_reminders_respect_project_data_scope(self):
        self._grant_maintenance()

        response = self.client.get('/api/projects/maintenance-reminders/warranty_expiring/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item['equipment_no'] for item in response.data], ['EQ-MAINT-OWN'])
