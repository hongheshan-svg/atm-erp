"""采购申请/订单「单价含税口径」与列表溯源字段回归测试。

对应用户反馈两点：
  1. 单价字段固定为未税，用户拿到的却是含税报价，直接填进去会被再加一次税
     （反馈截图里 319.20 被算成 360.70）。现在表头可切 INCLUSIVE 口径，
     系统反算未税单价入账，金额/税额/含税价链条与手工算未税时逐分一致。
  2. 采购申请列表只有申请号，没有项目号和采购合同 PO 号。

同时锁定两条不变量：
  - estimated_price / unit_price 永远是未税，是唯一入账基准；
  - price_with_tax 只作展示，不参与金额计算。
"""

from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.masterdata.models import Customer, Item, Supplier
from apps.projects.models import Project
from apps.purchase.models import (
    PurchaseOrder,
    PurchaseRequest,
    PurchaseRequestLine,
    price_exclusive_from_inclusive,
    price_inclusive_from_exclusive,
)
from apps.purchase.serializers import resolve_po_line_prices


class PriceTaxHelperTest(TestCase):
    """两个换算函数的口径与舍入。"""

    def test_exclusive_from_inclusive_matches_feedback_screenshot(self):
        # 反馈截图：含税 319.20 @13% 应还原成未税 282.48
        self.assertEqual(price_exclusive_from_inclusive(Decimal('319.20'), Decimal('13')), Decimal('282.48'))

    def test_inclusive_from_exclusive_matches_feedback_screenshot(self):
        # 反过来：未税 282.48 @13% 得含税 319.20
        self.assertEqual(price_inclusive_from_exclusive(Decimal('282.48'), Decimal('13')), Decimal('319.20'))

    def test_round_trip_is_stable_at_two_decimals(self):
        excl = price_exclusive_from_inclusive(Decimal('319.20'), Decimal('13'))
        self.assertEqual(price_inclusive_from_exclusive(excl, Decimal('13')), Decimal('319.20'))

    def test_zero_tax_rate_is_identity(self):
        self.assertEqual(price_exclusive_from_inclusive(Decimal('100.00'), Decimal('0')), Decimal('100.00'))
        self.assertEqual(price_inclusive_from_exclusive(Decimal('100.00'), Decimal('0')), Decimal('100.00'))

    def test_none_and_string_inputs_do_not_blow_up(self):
        self.assertEqual(price_exclusive_from_inclusive(None, None), Decimal('0.00'))
        self.assertEqual(price_inclusive_from_exclusive('113', '13'), Decimal('127.69'))

    def test_rounding_is_half_up(self):
        # 100 / 1.03 = 97.0873...  → 97.09
        self.assertEqual(price_exclusive_from_inclusive(Decimal('100'), Decimal('3')), Decimal('97.09'))


class PurchaseRequestPriceModeApiTest(TestCase):
    """创建/更新采购申请时两种口径的落库结果。"""

    def setUp(self):
        self.user = User.objects.create(username='taxmode', employee_id='TAXMODE', is_staff=True, is_superuser=True)
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.customer = Customer.objects.create(code='TMC', name='口径客户')
        self.project = Project.objects.create(
            code='TMPRJ-001',
            name='口径项目',
            customer=self.customer,
            manager=self.user,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            budget_material=Decimal('0'),
        )
        self.item = Item.objects.create(sku='TM-ITEM-1', name='气缸')
        self.supplier = Supplier.objects.create(code='TMSUP', name='口径供应商')

    def _payload(self, **overrides):
        payload = {
            'project': self.project.id,
            'supplier': self.supplier.id,
            'required_date': str(date.today() + timedelta(days=15)),
            'tax_rate': 13,
            'lines': [],
        }
        payload.update(overrides)
        return payload

    def test_inclusive_mode_reverse_calculates_exclusive_price(self):
        """含税口径：填 319.20，落库未税 282.48，含税总额回到 319.20 而不是 360.70。"""
        resp = self.client.post(
            '/api/purchase/requests/',
            self._payload(
                price_input_mode='INCLUSIVE',
                lines=[{'item': self.item.id, 'qty': 1, 'price_with_tax': 319.20}],
            ),
            format='json',
        )
        self.assertEqual(resp.status_code, 201, resp.data)

        pr = PurchaseRequest.objects.get(id=resp.data['id'])
        line = pr.lines.get()
        self.assertEqual(pr.price_input_mode, 'INCLUSIVE')
        self.assertEqual(line.estimated_price, Decimal('282.48'))
        self.assertEqual(line.price_with_tax, Decimal('319.20'))
        self.assertEqual(line.line_amount, Decimal('282.48'))
        self.assertEqual(pr.total_amount, Decimal('282.48'))
        self.assertEqual(pr.tax_amount.quantize(Decimal('0.01')), Decimal('36.72'))
        self.assertEqual(pr.total_with_tax.quantize(Decimal('0.01')), Decimal('319.20'))

    def test_exclusive_mode_backfills_price_with_tax(self):
        """未税口径（默认）：行为不变，同时反向补出含税单价供展示。"""
        resp = self.client.post(
            '/api/purchase/requests/',
            self._payload(lines=[{'item': self.item.id, 'qty': 2, 'estimated_price': 282.48}]),
            format='json',
        )
        self.assertEqual(resp.status_code, 201, resp.data)

        pr = PurchaseRequest.objects.get(id=resp.data['id'])
        line = pr.lines.get()
        self.assertEqual(pr.price_input_mode, 'EXCLUSIVE')
        self.assertEqual(line.estimated_price, Decimal('282.48'))
        self.assertEqual(line.price_with_tax, Decimal('319.20'))
        self.assertEqual(pr.total_amount, Decimal('564.96'))

    def test_update_switching_to_inclusive_recalculates(self):
        create = self.client.post(
            '/api/purchase/requests/',
            self._payload(lines=[{'item': self.item.id, 'qty': 1, 'estimated_price': 100}]),
            format='json',
        )
        pr_id = create.data['id']

        resp = self.client.put(
            f'/api/purchase/requests/{pr_id}/',
            self._payload(
                price_input_mode='INCLUSIVE',
                lines=[{'item': self.item.id, 'qty': 1, 'price_with_tax': 319.20}],
            ),
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)

        pr = PurchaseRequest.objects.get(id=pr_id)
        self.assertEqual(pr.price_input_mode, 'INCLUSIVE')
        self.assertEqual(pr.lines.get().estimated_price, Decimal('282.48'))
        self.assertEqual(pr.total_amount, Decimal('282.48'))

    def test_update_changing_tax_rate_and_lines_together(self):
        """同一次 PUT 里改税率+改行，必须按新税率反算，不能用库里的旧税率。"""
        create = self.client.post(
            '/api/purchase/requests/',
            self._payload(
                price_input_mode='INCLUSIVE',
                lines=[{'item': self.item.id, 'qty': 1, 'price_with_tax': 113}],
            ),
            format='json',
        )
        pr_id = create.data['id']

        resp = self.client.put(
            f'/api/purchase/requests/{pr_id}/',
            self._payload(
                tax_rate=6,
                price_input_mode='INCLUSIVE',
                lines=[{'item': self.item.id, 'qty': 1, 'price_with_tax': 106}],
            ),
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)

        pr = PurchaseRequest.objects.get(id=pr_id)
        self.assertEqual(pr.tax_rate, Decimal('6.00'))
        self.assertEqual(pr.lines.get().estimated_price, Decimal('100.00'))

    def test_line_save_backfills_price_with_tax_for_direct_orm_writes(self):
        """绕过序列化器直接建行（BOM 生成、导入等路径）也要有含税单价。"""
        pr = PurchaseRequest.objects.create(
            project=self.project,
            requestor=self.user,
            required_date=date.today() + timedelta(days=10),
            tax_rate=Decimal('13'),
            created_by=self.user,
        )
        line = PurchaseRequestLine.objects.create(
            pr=pr, item=self.item, qty=Decimal('1'), estimated_price=Decimal('282.48'), created_by=self.user
        )
        self.assertEqual(line.price_with_tax, Decimal('319.20'))


class PurchaseRequestListTraceFieldsTest(TestCase):
    """列表新增的项目号与采购合同 PO 号。"""

    def setUp(self):
        self.user = User.objects.create(username='trace', employee_id='TRACE', is_staff=True, is_superuser=True)
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.customer = Customer.objects.create(code='TRC', name='溯源客户')
        self.project = Project.objects.create(
            code='TRPRJ-2026',
            name='溯源项目',
            customer=self.customer,
            manager=self.user,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            budget_material=Decimal('0'),
        )
        self.item = Item.objects.create(sku='TR-ITEM-1', name='溯源物料')
        self.supplier = Supplier.objects.create(code='TRSUP', name='溯源供应商')

    def _make_pr(self, status='APPROVED', price_input_mode='EXCLUSIVE'):
        pr = PurchaseRequest.objects.create(
            project=self.project,
            requestor=self.user,
            required_date=date.today() + timedelta(days=20),
            tax_rate=Decimal('13'),
            price_input_mode=price_input_mode,
            status=status,
            created_by=self.user,
        )
        PurchaseRequestLine.objects.create(
            pr=pr, item=self.item, qty=Decimal('1'), estimated_price=Decimal('282.48'), created_by=self.user
        )
        return pr

    def test_list_exposes_project_code_and_empty_po_numbers(self):
        self._make_pr()
        resp = self.client.get('/api/purchase/requests/')
        self.assertEqual(resp.status_code, 200, resp.data)
        row = resp.data['results'][0]
        self.assertEqual(row['project_code'], 'TRPRJ-2026')
        self.assertEqual(row['po_numbers'], [])
        # 单价两个口径都要能拿到，列表才能同时显示未税/含税两列
        self.assertEqual(row['item_summary']['unit_price'], 282.48)
        self.assertEqual(row['item_summary']['price_with_tax'], 319.20)

    def test_convert_to_po_inherits_mode_and_fills_po_numbers(self):
        pr = self._make_pr(price_input_mode='INCLUSIVE')
        resp = self.client.post(
            f'/api/purchase/requests/{pr.id}/convert_to_po/',
            {'supplier': self.supplier.id},
            format='json',
        )
        self.assertEqual(resp.status_code, 201, resp.data)

        po = PurchaseOrder.objects.get(id=resp.data['id'])
        self.assertEqual(po.source_pr_id, pr.id)
        self.assertEqual(po.price_input_mode, 'INCLUSIVE')
        self.assertEqual(po.tax_rate, Decimal('13.00'))
        po_line = po.lines.get()
        self.assertEqual(po_line.unit_price, Decimal('282.48'))
        self.assertEqual(po_line.price_with_tax, Decimal('319.20'))

        # 申请列表现在能反查出 PO 号
        list_resp = self.client.get('/api/purchase/requests/')
        row = next(r for r in list_resp.data['results'] if r['id'] == pr.id)
        self.assertEqual(row['po_numbers'], [po.order_no])

    def test_soft_deleted_po_is_not_listed(self):
        pr = self._make_pr()
        resp = self.client.post(
            f'/api/purchase/requests/{pr.id}/convert_to_po/',
            {'supplier': self.supplier.id},
            format='json',
        )
        po = PurchaseOrder.objects.get(id=resp.data['id'])
        po.soft_delete()

        list_resp = self.client.get('/api/purchase/requests/')
        row = next(r for r in list_resp.data['results'] if r['id'] == pr.id)
        self.assertEqual(row['po_numbers'], [])


class PurchaseOrderPriceModeTest(TestCase):
    """采购订单侧的口径解析，含订单页只送 unit_price 的兼容退路。"""

    def test_inclusive_mode_uses_price_with_tax_when_provided(self):
        unit_price, price_with_tax = resolve_po_line_prices({'price_with_tax': '319.20'}, Decimal('13'), 'INCLUSIVE')
        self.assertEqual(unit_price, Decimal('282.48'))
        self.assertEqual(price_with_tax, Decimal('319.20'))

    def test_inclusive_mode_falls_back_to_unit_price_when_absent(self):
        """PO 继承了 INCLUSIVE，但订单页只提交 unit_price——不能把单价静默算成 0。"""
        unit_price, price_with_tax = resolve_po_line_prices({'unit_price': '282.48'}, Decimal('13'), 'INCLUSIVE')
        self.assertEqual(unit_price, Decimal('282.48'))
        self.assertEqual(price_with_tax, Decimal('319.20'))

    def test_exclusive_mode_ignores_price_with_tax(self):
        unit_price, price_with_tax = resolve_po_line_prices(
            {'unit_price': '100', 'price_with_tax': '999'}, Decimal('13'), 'EXCLUSIVE'
        )
        self.assertEqual(unit_price, Decimal('100'))
        self.assertEqual(price_with_tax, Decimal('113.00'))
