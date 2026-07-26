from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.accounts.models import Role
from apps.core.permission_models_new import DataScope, Permission, RolePermission
from apps.masterdata.models import Customer
from apps.sales.models import SalesOrder

User = get_user_model()


class SalesPerformancePermissionTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='sales-self',
            employee_id='sales-self',
            password='test-password',
            first_name='本人',
        )
        self.other_user = User.objects.create_user(
            username='sales-other',
            employee_id='sales-other',
            password='test-password',
            first_name='他人',
        )
        self.role = Role.objects.create(name='销售本人范围', code='sales-self-role')
        self.user.roles.add(self.role)
        self.client.force_authenticate(self.user)
        customer = Customer.objects.create(code='C-PERFORMANCE', name='业绩客户')
        SalesOrder.objects.create(
            order_no='SO-PERF-OWN',
            customer=customer,
            delivery_date=date.today(),
            status='CONFIRMED',
            total_amount=Decimal('100.00'),
            created_by=self.user,
        )
        SalesOrder.objects.create(
            order_no='SO-PERF-OTHER',
            customer=customer,
            delivery_date=date.today(),
            status='CONFIRMED',
            total_amount=Decimal('900.00'),
            created_by=self.other_user,
        )

    def _grant_performance(self):
        permission = Permission.objects.create(code='sales:performance', name='销售业绩', type='menu')
        RolePermission.objects.create(role=self.role, permission=permission)
        DataScope.objects.create(role=self.role, module='sales', scope_type='self')

    def test_performance_endpoints_require_performance_menu(self):
        response = self.client.get('/api/sales/performance/team_ranking/', {'year': date.today().year})

        self.assertEqual(response.status_code, 403)

    def test_team_ranking_respects_sales_data_scope(self):
        self._grant_performance()

        response = self.client.get('/api/sales/performance/team_ranking/', {'year': date.today().year})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['user_id'], self.user.id)
        self.assertEqual(response.data[0]['total_amount'], 100.0)
