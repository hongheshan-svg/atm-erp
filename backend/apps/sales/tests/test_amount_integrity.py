from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.masterdata.models import Customer
from apps.sales.models import SalesOrder, SalesOrderLine
from apps.sales.serializers import SalesOrderLineSerializer


class SalesOrderLineAmountIntegrityTest(TestCase):
    def setUp(self):
        customer = Customer.objects.create(code='AMT-C1', name='金额审计客户')
        self.order = SalesOrder.objects.create(
            customer=customer,
            delivery_date=date.today(),
            status='CONFIRMED',
            total_amount=Decimal('100.00'),
            total_with_tax=Decimal('100.00'),
        )
        self.line = SalesOrderLine.objects.create(
            so=self.order,
            custom_name='审计产品',
            custom_unit='件',
            qty=Decimal('1'),
            unit_price=Decimal('100.00'),
        )

    def test_confirmed_order_line_amount_cannot_be_patched_directly(self):
        serializer = SalesOrderLineSerializer(self.line, data={'qty': '2'}, partial=True)

        self.assertFalse(serializer.is_valid())
        self.assertIn('只有草稿或已拒绝销售订单可以修改明细', str(serializer.errors))

    def test_draft_order_line_rejects_non_positive_quantity(self):
        self.order.status = 'DRAFT'
        self.order.save(update_fields=['status', 'updated_at'])
        serializer = SalesOrderLineSerializer(self.line, data={'qty': '0'}, partial=True)

        self.assertFalse(serializer.is_valid())
        self.assertIn('数量必须大于 0', str(serializer.errors))
