from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.accounts.models import Role
from apps.core.permission_models_new import DataScope, Permission, RolePermission
from apps.masterdata.models import Customer, Item, Supplier

User = get_user_model()


class DatabaseSearchTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='search-user',
            employee_id='search-user',
            password='test-password',
        )
        self.role = Role.objects.create(name='搜索角色', code='search-role')
        self.user.roles.add(self.role)
        self.client.force_authenticate(self.user)
        self.item = Item.objects.create(sku='SERVO-001', name='伺服电机', specification='750W')
        Customer.objects.create(code='C-SEARCH', name='搜索客户')
        Supplier.objects.create(code='S-SEARCH', name='搜索供应商')

    def grant(self, *codes):
        for code in codes:
            permission = Permission.objects.create(code=code, name=code, type='menu')
            RolePermission.objects.create(role=self.role, permission=permission)

    def test_search_uses_database(self):
        self.grant('sales:customer', 'supply:supplier')
        response = self.client.get('/api/core/search/search/', {'q': '搜索', 'limit': 20})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['results']['customers']['total'], 1)
        self.assertEqual(response.data['results']['suppliers']['total'], 1)
        self.assertEqual(response.data['total_hits'], 2)

    def test_suggestions_use_database_and_clamp_invalid_limit(self):
        self.grant('supply:stock')
        response = self.client.get('/api/core/search/suggest/', {'q': '伺服', 'type': 'items', 'limit': 'invalid'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data['suggestions'],
            [{'id': self.item.id, 'text': '伺服电机', 'type': 'items', 'meta': 'SERVO-001'}],
        )

    def test_suggestions_reject_unknown_type(self):
        response = self.client.get('/api/core/search/suggest/', {'q': '测试', 'type': 'unknown'})

        self.assertEqual(response.status_code, 400)

    def test_explicit_search_type_requires_its_menu_permission(self):
        response = self.client.get('/api/core/search/search/', {'q': '搜索', 'type': 'customers'})

        self.assertEqual(response.status_code, 403)

    def test_project_search_applies_project_data_scope(self):
        from datetime import date

        from apps.projects.models import Project

        other_user = User.objects.create_user(
            username='other-search-user',
            employee_id='other-search-user',
            password='test-password',
        )
        customer = Customer.objects.get(code='C-SEARCH')
        Project.objects.create(
            code='PRJ-OWN-SEARCH',
            name='搜索本人项目',
            customer=customer,
            manager=self.user,
            start_date=date.today(),
            end_date=date.today(),
            created_by=self.user,
        )
        Project.objects.create(
            code='PRJ-OTHER-SEARCH',
            name='搜索他人项目',
            customer=customer,
            manager=other_user,
            start_date=date.today(),
            end_date=date.today(),
            created_by=other_user,
        )
        self.grant('projects:list')
        DataScope.objects.create(role=self.role, module='projects', scope_type='self')

        response = self.client.get('/api/core/search/search/', {'q': '搜索', 'type': 'projects', 'limit': 20})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['results']['projects']['total'], 1)
        self.assertEqual(response.data['results']['projects']['hits'][0]['code'], 'PRJ-OWN-SEARCH')
