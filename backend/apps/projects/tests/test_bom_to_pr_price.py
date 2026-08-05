"""BOM 询价价格推送到采购申请时的口径回归测试。

修复前 generate_purchase_request 用 `price_without_tax or price_with_tax or standard_cost`
取值，只有含税报价的 BOM 行会把含税单价直接塞进 estimated_price（未税字段），
采购申请随后又按税率加一次税，含税总额虚高——与用户反馈截图里手工误填的
319.20→360.70 是同一个坑的自动化版本。

同时锁定第二处缺陷：pr.tax_amount / total_with_tax 当时从不落库，
采购申请列表「含税总额」列恒显示 ¥0.00。
"""

from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.masterdata.models import Customer, Item, Supplier
from apps.projects.models import Project, ProjectBOM
from apps.purchase.models import PurchaseRequest


class BOMToPurchaseRequestPriceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(username='bom2pr', employee_id='BOM2PR', is_staff=True, is_superuser=True)
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.customer = Customer.objects.create(code='B2PC', name='BOM推送客户')
        self.project = Project.objects.create(
            code='B2PPRJ',
            name='BOM推送项目',
            customer=self.customer,
            manager=self.user,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            budget_material=Decimal('0'),
        )
        self.supplier = Supplier.objects.create(code='B2PSUP', name='BOM推送供应商')

    def _make_bom(self, item, **quote):
        defaults = {
            'project': self.project,
            'item': item,
            'planned_qty': Decimal('1'),
            'actual_qty': Decimal('0'),
            'quote_status': 'QUOTED',
            'order_status': 'NOT_ORDERED',
            'quote_supplier': self.supplier,
            'created_by': self.user,
        }
        defaults.update(quote)
        return ProjectBOM.objects.create(**defaults)

    def _generate(self):
        resp = self.client.post(
            '/api/projects/bom/generate_purchase_request/',
            {'project': self.project.id, 'required_date': str(date.today() + timedelta(days=30))},
            format='json',
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        return PurchaseRequest.objects.get(request_no=resp.data['purchase_request']['request_no'])

    def test_inclusive_only_quote_is_reverse_calculated(self):
        """BOM 只有含税单价时，未税单价必须反算，不能原样搬进 estimated_price。"""
        item = Item.objects.create(sku='B2P-INCL', name='仅含税报价物料')
        self._make_bom(item, price_with_tax=Decimal('319.20'), tax_rate=Decimal('13'))

        pr = self._generate()
        line = pr.lines.get()
        self.assertEqual(line.estimated_price, Decimal('282.48'))
        self.assertEqual(line.price_with_tax, Decimal('319.20'))
        # 关键断言：含税总额回到 319.20，而不是在含税价上再叠 13% 的 360.70
        self.assertEqual(pr.total_with_tax.quantize(Decimal('0.01')), Decimal('319.20'))

    def test_exclusive_quote_is_used_as_is(self):
        item = Item.objects.create(sku='B2P-EXCL', name='有未税报价物料')
        self._make_bom(
            item,
            price_without_tax=Decimal('282.48'),
            price_with_tax=Decimal('319.20'),
            tax_rate=Decimal('13'),
        )

        pr = self._generate()
        line = pr.lines.get()
        self.assertEqual(line.estimated_price, Decimal('282.48'))
        self.assertEqual(line.price_with_tax, Decimal('319.20'))

    def test_bom_tax_rate_takes_precedence_over_pr_tax_rate(self):
        """BOM 行自带税率时按它反算，而不是采购申请表头的默认 13%。"""
        item = Item.objects.create(sku='B2P-RATE', name='6%税率物料')
        self._make_bom(item, price_with_tax=Decimal('106.00'), tax_rate=Decimal('6'))

        pr = self._generate()
        self.assertEqual(pr.lines.get().estimated_price, Decimal('100.00'))

    def test_falls_back_to_standard_cost_as_exclusive(self):
        item = Item.objects.create(sku='B2P-STD', name='无报价物料', standard_cost=Decimal('50.00'))
        self._make_bom(item)

        pr = self._generate()
        line = pr.lines.get()
        self.assertEqual(line.estimated_price, Decimal('50.00'))
        self.assertEqual(line.price_with_tax, Decimal('56.50'))

    def test_tax_amount_and_total_with_tax_are_persisted(self):
        """修复前这两个字段从不落库，列表「含税总额」恒为 ¥0.00。"""
        item = Item.objects.create(sku='B2P-TOTAL', name='合计物料')
        self._make_bom(item, planned_qty=Decimal('2'), price_without_tax=Decimal('100'), tax_rate=Decimal('13'))

        pr = self._generate()
        self.assertEqual(pr.total_amount, Decimal('200.00'))
        self.assertEqual(pr.tax_amount.quantize(Decimal('0.01')), Decimal('26.00'))
        self.assertEqual(pr.total_with_tax.quantize(Decimal('0.01')), Decimal('226.00'))
