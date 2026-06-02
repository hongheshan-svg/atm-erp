"""
供应商黑名单采购拦截回归测试（审计 medium：黑名单原先无任何采购拦截）。

- SupplierBlacklist.is_blacklisted：status=ACTIVE 视为在黑名单，LIFTED/无记录则否。
- PurchaseOrderViewSet.perform_create：黑名单供应商创建 PO 时抛 ValidationError（拦截发生在
  super().perform_create 之前，仅验证本次新增的 guard，不依赖框架其余行为）。
"""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory

from apps.masterdata.models import Supplier
from apps.purchase.evaluation_models import SupplierBlacklist
from apps.purchase.views import PurchaseOrderViewSet

User = get_user_model()
factory = APIRequestFactory()


class _POStub:
    def __init__(self, supplier):
        self.validated_data = {'supplier': supplier}
        self.saved = False

    def save(self, **kwargs):
        self.saved = True


class SupplierBlacklistTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='bl_u', password='x', employee_id='bl_u')
        self.bad = Supplier.objects.create(code='BAD', name='Bad Supplier')
        self.good = Supplier.objects.create(code='GOOD', name='Good Supplier')
        SupplierBlacklist.objects.create(
            supplier=self.bad, blacklist_date=date.today(), reason='质量问题', status='ACTIVE'
        )

    def test_is_blacklisted(self):
        self.assertTrue(SupplierBlacklist.is_blacklisted(self.bad))
        self.assertTrue(SupplierBlacklist.is_blacklisted(self.bad.id))  # 也接受 id
        self.assertFalse(SupplierBlacklist.is_blacklisted(self.good))
        self.assertFalse(SupplierBlacklist.is_blacklisted(None))

    def test_lifted_supplier_not_blacklisted(self):
        SupplierBlacklist.objects.filter(supplier=self.bad).update(status='LIFTED')
        self.assertFalse(SupplierBlacklist.is_blacklisted(self.bad))

    def test_po_create_blocked_for_blacklisted_supplier(self):
        request = factory.post('/x/')
        request.user = self.user
        viewset = PurchaseOrderViewSet()
        viewset.request = request
        viewset.action = 'create'
        with self.assertRaises(ValidationError):
            viewset.perform_create(_POStub(self.bad))
