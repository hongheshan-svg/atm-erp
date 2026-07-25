from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.masterdata.models import Customer, Item, Supplier

User = get_user_model()


class DatabaseSearchTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='search-user',
            employee_id='search-user',
            password='test-password',
        )
        self.client.force_authenticate(self.user)
        self.item = Item.objects.create(sku='SERVO-001', name='伺服电机', specification='750W')
        Customer.objects.create(code='C-SEARCH', name='搜索客户')
        Supplier.objects.create(code='S-SEARCH', name='搜索供应商')

    def test_search_uses_database(self):
        response = self.client.get('/api/core/search/search/', {'q': '搜索', 'limit': 20})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['results']['customers']['total'], 1)
        self.assertEqual(response.data['results']['suppliers']['total'], 1)
        self.assertEqual(response.data['total_hits'], 2)

    def test_suggestions_use_database_and_clamp_invalid_limit(self):
        response = self.client.get('/api/core/search/suggest/', {'q': '伺服', 'type': 'items', 'limit': 'invalid'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data['suggestions'],
            [{'id': self.item.id, 'text': '伺服电机', 'type': 'items', 'meta': 'SERVO-001'}],
        )

    def test_suggestions_reject_unknown_type(self):
        response = self.client.get('/api/core/search/suggest/', {'q': '测试', 'type': 'unknown'})

        self.assertEqual(response.status_code, 400)
