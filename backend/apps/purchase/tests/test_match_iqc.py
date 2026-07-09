"""采购三单匹配 + IQC 来料检验 回归测试。

覆盖：
1) IQC 入库门禁：
   - FAIL 检验单 -> 该收货行不入库(不产生 StockMove、不计已收、行标记不合格)。
   - PASS 检验单 -> 正常入库(产生 StockMove、po_line.received_qty 增加)。
   - 免检物料(inspection_type='NONE') -> 无检验单也放行(不破坏既有流程)。
   - 强制门禁(IQC_ENFORCE_INSPECTION=True) + 需检物料 + 无合格检验单 -> confirm 被拦截。
2) 三单匹配：over_received 标记 + ok=False。
3) assert_can_pay：拟付金额超过已收货物可结算价值时抛 ValidationError。
"""

from datetime import date
from decimal import Decimal

from django.test import TestCase, override_settings
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.inventory.models import StockMove
from apps.masterdata.models import Item, Supplier, Warehouse
from apps.purchase.iqc import IncomingInspection, evaluate_line_inspection
from apps.purchase.matching import assert_can_pay, three_way_match
from apps.purchase.models import GoodsReceipt, GoodsReceiptLine, PurchaseOrder, PurchaseOrderLine


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class BaseMatchIQCTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            username='iqcadmin', employee_id='IQC1', is_staff=True, is_superuser=True
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.supplier = Supplier.objects.create(code='IQCSUP', name='来料供应商')
        self.warehouse = Warehouse.objects.create(code='IQCWH', name='来料仓')
        # 默认 inspection_type='INCOMING' => 需检
        self.item = Item.objects.create(sku='IQC-ITEM1', name='需检物料')

    def _make_po(self, qty=Decimal('10'), unit_price=Decimal('100'), tax_rate=13, item=None):
        po = PurchaseOrder.objects.create(
            supplier=self.supplier,
            delivery_date=date(2026, 9, 1),
            tax_rate=tax_rate,
            status='CONFIRMED',
            created_by=self.user,
        )
        line = PurchaseOrderLine.objects.create(
            po=po, item=item or self.item, qty=qty, unit_price=unit_price, created_by=self.user
        )
        # 重算金额（与真实确认口径一致）
        po.total_amount = line.line_amount
        po.tax_amount = po.total_amount * tax_rate / 100
        po.total_with_tax = po.total_amount + po.tax_amount
        po.save()
        return po, line

    def _make_receipt(self, po, po_line, qty=Decimal('10'), item=None):
        receipt = GoodsReceipt.objects.create(
            po=po, warehouse=self.warehouse, receipt_date=date(2026, 9, 2),
            status='DRAFT', created_by=self.user,
        )
        line = GoodsReceiptLine.objects.create(
            receipt=receipt, po_line=po_line, item=item or self.item, qty=qty, created_by=self.user
        )
        return receipt, line

    def _confirm(self, receipt):
        return self.client.post(f'/api/purchase/receipts/{receipt.pk}/confirm/', {}, format='json')

    def _stock_move_count(self, receipt):
        return StockMove.objects.filter(
            reference_type='GoodsReceipt', reference_id=receipt.id, move_type='IN_PURCHASE', is_deleted=False
        ).count()


class IQCGateTest(BaseMatchIQCTest):
    def test_fail_inspection_blocks_stock_in(self):
        po, po_line = self._make_po()
        receipt, r_line = self._make_receipt(po, po_line)
        IncomingInspection.objects.create(
            goods_receipt=receipt, receipt_line=r_line, item=self.item,
            inspected_qty=Decimal('10'), defect_qty=Decimal('4'),
            result='FAIL', disposition='REJECT', status='SUBMITTED', created_by=self.user,
        )

        resp = self._confirm(receipt)
        self.assertEqual(resp.status_code, 200, getattr(resp, 'data', resp))

        # FAIL 行不入库：无 StockMove、po_line 已收保持 0、收货行标记不合格
        self.assertEqual(self._stock_move_count(receipt), 0)
        po_line.refresh_from_db()
        self.assertEqual(po_line.received_qty, Decimal('0'))
        r_line.refresh_from_db()
        self.assertEqual(r_line.quality_status, 'FAILED')

    def test_pass_inspection_allows_stock_in(self):
        po, po_line = self._make_po()
        receipt, r_line = self._make_receipt(po, po_line)
        IncomingInspection.objects.create(
            goods_receipt=receipt, receipt_line=r_line, item=self.item,
            inspected_qty=Decimal('10'), defect_qty=Decimal('0'),
            result='PASS', disposition='ACCEPT', status='SUBMITTED', created_by=self.user,
        )

        resp = self._confirm(receipt)
        self.assertEqual(resp.status_code, 200, getattr(resp, 'data', resp))

        self.assertEqual(self._stock_move_count(receipt), 1)
        po_line.refresh_from_db()
        self.assertEqual(po_line.received_qty, Decimal('10'))
        po.refresh_from_db()
        self.assertEqual(po.status, 'COMPLETED')

    def test_exempt_item_allows_stock_in_without_inspection(self):
        """免检物料(inspection_type='NONE')无检验单也放行——门禁默认不破坏既有流程。"""
        exempt = Item.objects.create(sku='IQC-EXEMPT', name='免检物料', inspection_type='NONE')
        po, po_line = self._make_po(item=exempt)
        receipt, r_line = self._make_receipt(po, po_line, item=exempt)

        # 需检判定为 False
        self.assertEqual(evaluate_line_inspection(r_line)[0], 'ALLOW')

        resp = self._confirm(receipt)
        self.assertEqual(resp.status_code, 200, getattr(resp, 'data', resp))
        self.assertEqual(self._stock_move_count(receipt), 1)

    def test_default_no_inspection_does_not_block(self):
        """默认(未开启强制门禁)：需检物料即使无检验单也不阻断，仅 FAIL 才拦截。"""
        po, po_line = self._make_po()
        receipt, r_line = self._make_receipt(po, po_line)

        self.assertEqual(evaluate_line_inspection(r_line)[0], 'ALLOW')
        resp = self._confirm(receipt)
        self.assertEqual(resp.status_code, 200, getattr(resp, 'data', resp))
        self.assertEqual(self._stock_move_count(receipt), 1)

    @override_settings(IQC_ENFORCE_INSPECTION=True)
    def test_enforce_missing_inspection_blocks_confirm(self):
        """强制门禁开启 + 需检物料 + 无合格检验单 -> confirm 被硬拦截(400)。"""
        po, po_line = self._make_po()
        receipt, r_line = self._make_receipt(po, po_line)

        self.assertEqual(evaluate_line_inspection(r_line)[0], 'MISSING_BLOCK')
        resp = self._confirm(receipt)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(self._stock_move_count(receipt), 0)
        po_line.refresh_from_db()
        self.assertEqual(po_line.received_qty, Decimal('0'))

    @override_settings(IQC_ENFORCE_INSPECTION=True)
    def test_enforce_pass_inspection_allows_confirm(self):
        po, po_line = self._make_po()
        receipt, r_line = self._make_receipt(po, po_line)
        IncomingInspection.objects.create(
            goods_receipt=receipt, receipt_line=r_line, item=self.item,
            inspected_qty=Decimal('10'), result='PASS', disposition='ACCEPT',
            status='SUBMITTED', created_by=self.user,
        )
        resp = self._confirm(receipt)
        self.assertEqual(resp.status_code, 200, getattr(resp, 'data', resp))
        self.assertEqual(self._stock_move_count(receipt), 1)

    def test_draft_inspection_not_counted(self):
        """未提交(DRAFT)的 FAIL 检验单不参与门禁——只有 SUBMITTED 生效。"""
        po, po_line = self._make_po()
        receipt, r_line = self._make_receipt(po, po_line)
        IncomingInspection.objects.create(
            goods_receipt=receipt, receipt_line=r_line, item=self.item,
            inspected_qty=Decimal('10'), result='FAIL', disposition='REJECT',
            status='DRAFT', created_by=self.user,
        )
        # DRAFT 不生效 -> 默认放行
        self.assertEqual(evaluate_line_inspection(r_line)[0], 'ALLOW')

    def test_iqc_viewset_create_and_submit(self):
        """通过 API 创建检验单(自动回填物料/检验员)并 submit。"""
        po, po_line = self._make_po()
        receipt, r_line = self._make_receipt(po, po_line)

        resp = self.client.post(
            '/api/purchase/incoming-inspections/',
            {
                'goods_receipt': receipt.id,
                'receipt_line': r_line.id,
                'inspected_qty': '10',
                'result': 'PASS',
                'disposition': 'ACCEPT',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        insp_id = resp.data['id']
        self.assertEqual(resp.data['item'], self.item.id)  # 自动回填物料
        self.assertTrue(resp.data['inspection_no'])
        self.assertEqual(resp.data['status'], 'DRAFT')

        submit = self.client.post(f'/api/purchase/incoming-inspections/{insp_id}/submit/', {}, format='json')
        self.assertEqual(submit.status_code, 200, submit.data)
        self.assertEqual(submit.data['status'], 'SUBMITTED')


class ThreeWayMatchTest(BaseMatchIQCTest):
    def test_matched_when_received_within_ordered(self):
        po, po_line = self._make_po(qty=Decimal('10'), unit_price=Decimal('100'))
        PurchaseOrderLine.objects.filter(pk=po_line.pk).update(received_qty=Decimal('10'))

        report = three_way_match(po)
        self.assertTrue(report['ok'])
        self.assertFalse(report['over_invoiced'])
        self.assertEqual(report['lines'][0]['status'], 'matched')
        self.assertEqual(report['received_amount'], Decimal('1000'))
        # 含税 1000 * 1.13
        self.assertEqual(report['received_amount_with_tax'], Decimal('1130.00'))

    def test_over_received_flagged(self):
        po, po_line = self._make_po(qty=Decimal('10'), unit_price=Decimal('100'))
        PurchaseOrderLine.objects.filter(pk=po_line.pk).update(received_qty=Decimal('12'))

        report = three_way_match(po)
        self.assertFalse(report['ok'])
        self.assertEqual(report['lines'][0]['status'], 'over_received')

    def test_three_way_match_action_endpoint(self):
        po, po_line = self._make_po(qty=Decimal('10'), unit_price=Decimal('100'))
        PurchaseOrderLine.objects.filter(pk=po_line.pk).update(received_qty=Decimal('12'))

        resp = self.client.get(f'/api/purchase/orders/{po.pk}/three_way_match/')
        self.assertEqual(resp.status_code, 200, getattr(resp, 'data', resp))
        self.assertFalse(resp.data['ok'])
        self.assertEqual(resp.data['lines'][0]['status'], 'over_received')


class AssertCanPayTest(BaseMatchIQCTest):
    def test_assert_can_pay_blocks_overpay(self):
        po, po_line = self._make_po(qty=Decimal('10'), unit_price=Decimal('100'), tax_rate=13)
        # 已收 5 -> 不含税 500, 含税 565
        PurchaseOrderLine.objects.filter(pk=po_line.pk).update(received_qty=Decimal('5'))

        # 含税 565 之内可付
        report = assert_can_pay(po, Decimal('565.00'))
        self.assertEqual(report['received_amount_with_tax'], Decimal('565.00'))

        # 超过已收含税价值 -> 抛 ValidationError（阻断超付）
        with self.assertRaises(ValidationError):
            assert_can_pay(po, Decimal('1130.00'))

    def test_assert_can_pay_zero_received_blocks_any(self):
        po, po_line = self._make_po(qty=Decimal('10'), unit_price=Decimal('100'))
        # 未收货 -> 任何正数付款都应被拦截
        with self.assertRaises(ValidationError):
            assert_can_pay(po, Decimal('100.00'))
