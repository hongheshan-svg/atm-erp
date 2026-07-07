"""G5:委外加工单确认/取消 与 统一待付款项台账(PayableItem)的一致性。

背景与修复:
- 历史 confirm() 内联 `AccountPayable.objects.create(..., notes=...)`,但
  AccountPayable 没有 notes 字段,该调用一直抛 TypeError 使 confirm() 500 回滚
  ——外协确认从未成功建过应付,"幽灵应付"这一现象其实无从产生;且 AP 与
  OutsourceOrder 无任何可靠关联,取消时无从冲销。
- 修复改为直接走已存在但此前无生产者的 OutsourcePayableSource 适配器
  (source_type='outsource'):confirm() 经 register_payable 登记台账项、
  cancel() 经 cancel_payable 作废,台账项与外协单经 source_id=order.pk 可靠关联,
  无需新增 FK/迁移。取消后不再残留待付台账项。
"""

from decimal import Decimal

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.finance.models import AccountPayable
from apps.finance.payable_models import PayableItem
from apps.masterdata.models import Item, Supplier
from apps.purchase.outsource_models import OutsourceOrder, OutsourceOrderLine


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class OutsourceCancelReversesLedgerTest(TestCase):
    def setUp(self):
        self.supplier = Supplier.objects.create(code='OSAP1', name='外协商乙')
        self.item = Item.objects.create(sku='OSAP-ITEM1', name='外协测试物料')
        self.user = User.objects.create(
            username='osapadmin', employee_id='OSAP1', is_staff=True, is_superuser=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _make_order(self):
        # tax_rate 默认 13%,line qty=10 * unit_price=45 => 加工费 450,含税 508.50。
        order = OutsourceOrder.objects.create(
            supplier=self.supplier, required_date='2026-08-01', status='DRAFT',
        )
        OutsourceOrderLine.objects.create(
            outsource_order=order, item=self.item, process_content='车削',
            qty=Decimal('10'), unit_price=Decimal('45.00'),
        )
        return order

    def _confirm(self, order):
        resp = self.client.post(f'/api/purchase/outsource-orders/{order.pk}/confirm/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        order.refresh_from_db()
        return order

    def test_confirm_registers_outsource_ledger_item(self):
        order = self._make_order()
        order = self._confirm(order)
        self.assertEqual(order.status, 'CONFIRMED')
        # 含税总额已按明细重算。
        self.assertEqual(order.total_with_tax, Decimal('508.50'))

        item = PayableItem.objects.get(source_type='outsource', source_id=order.pk)
        self.assertEqual(item.status, PayableItem.STATUS_PENDING)
        self.assertEqual(item.amount_due, order.total_with_tax)
        self.assertEqual(item.payee_name, self.supplier.name)
        self.assertEqual(item.source_no, order.order_no)

        # 修复后不再内联创建 AccountPayable(历史实现会 500,从来建不成)。
        self.assertEqual(AccountPayable.objects.count(), 0)

    def test_cancel_after_confirm_cancels_ledger_item(self):
        order = self._make_order()
        order = self._confirm(order)
        item = PayableItem.objects.get(source_type='outsource', source_id=order.pk)

        resp = self.client.post(f'/api/purchase/outsource-orders/{order.pk}/cancel/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        order.refresh_from_db()
        self.assertEqual(order.status, 'CANCELLED')

        item.refresh_from_db()
        self.assertEqual(item.status, PayableItem.STATUS_CANCELLED)

    def test_cancel_does_not_reverse_settled_ledger_item(self):
        """已核销(amount_paid>0)的台账项不应被误冲——与 cancel_payable 的守卫语义一致。"""
        order = self._make_order()
        order = self._confirm(order)
        item = PayableItem.objects.get(source_type='outsource', source_id=order.pk)
        item.amount_paid = item.amount_due
        item.recalc_status()
        item.save()
        self.assertEqual(item.status, PayableItem.STATUS_PAID)

        resp = self.client.post(f'/api/purchase/outsource-orders/{order.pk}/cancel/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        order.refresh_from_db()
        self.assertEqual(order.status, 'CANCELLED')

        item.refresh_from_db()
        self.assertEqual(item.status, PayableItem.STATUS_PAID)  # 未被误冲

    def test_cancel_without_confirm_is_noop_on_ledger(self):
        """从未 confirm() 过的草稿单取消时,不存在台账项,cancel() 应正常完成。"""
        order = self._make_order()
        resp = self.client.post(f'/api/purchase/outsource-orders/{order.pk}/cancel/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        order.refresh_from_db()
        self.assertEqual(order.status, 'CANCELLED')
        self.assertFalse(PayableItem.objects.filter(source_type='outsource', source_id=order.pk).exists())
