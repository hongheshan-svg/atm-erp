"""主数据创建不依赖外部搜索服务。"""

from django.test import TestCase

from apps.masterdata.models import Customer, Supplier


class CreateWithoutSearchServiceTest(TestCase):
    def test_create_customer(self):
        customer = Customer.objects.create(code='C-NOES-01', name='无ES建档客户')
        self.assertIsNotNone(customer.pk)

    def test_create_supplier(self):
        supplier = Supplier.objects.create(code='S-NOES-01', name='无ES建档供应商')
        self.assertIsNotNone(supplier.pk)
