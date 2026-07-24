"""PR→RFQ 转换入口回归测试。

覆盖审计 P1(采购申请与询价断链)修复：已审批的采购申请(PR)可一键转询价(RFQ)，
逐条明细映射为 RFQLine(item/qty/需求日期/BOM关联)，并继承项目；非审批态 PR 被拒。
"""

from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.masterdata.models import Customer, Item, Supplier
from apps.projects.models import Project, ProjectBOM
from apps.purchase.models import PurchaseRequest, PurchaseRequestLine
from apps.purchase.rfq_models import RFQ, RFQLine, RFQSupplier
from apps.purchase.rfq_service import BatchRFQService


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class PRToRFQServiceTest(TestCase):
    """service 层 create_rfq_from_purchase_request。"""

    def setUp(self):
        self.user = User.objects.create(
            username='pr2rfq', employee_id='PR2RFQ', is_staff=True, is_superuser=True
        )
        self.customer = Customer.objects.create(code='PRC', name='转询价客户')
        self.project = Project.objects.create(
            code='PRPRJ',
            name='转询价项目',
            customer=self.customer,
            manager=self.user,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            budget_material=Decimal('0'),
        )
        self.item1 = Item.objects.create(sku='PR-ITEM-1', name='采购物料一')
        self.item2 = Item.objects.create(sku='PR-ITEM-2', name='采购物料二')
        self.supplier = Supplier.objects.create(code='PRSUP', name='受邀供应商')

    def _make_pr(self, status='APPROVED', with_bom=False):
        pr = PurchaseRequest.objects.create(
            project=self.project,
            requestor=self.user,
            required_date=date.today() + timedelta(days=30),
            status=status,
            created_by=self.user,
        )
        bom = None
        if with_bom:
            bom = ProjectBOM.objects.create(
                project=self.project, item=self.item1, planned_qty=Decimal('3')
            )
        PurchaseRequestLine.objects.create(
            pr=pr,
            item=self.item1,
            qty=Decimal('3.00'),
            estimated_price=Decimal('12.50'),
            required_date=date.today() + timedelta(days=20),
            bom_item=bom,
            is_critical=True,
            function_module='夹爪模块',
            notes='需SUS304',
            created_by=self.user,
        )
        PurchaseRequestLine.objects.create(
            pr=pr,
            item=self.item2,
            qty=Decimal('5.00'),
            estimated_price=Decimal('8.00'),
            created_by=self.user,
        )
        return pr

    def test_approved_pr_converts_to_rfq_with_matching_lines(self):
        pr = self._make_pr(status='APPROVED', with_bom=True)

        rfq = BatchRFQService.create_rfq_from_purchase_request(pr, self.user)

        # RFQ 基本属性 + 项目继承
        self.assertIsInstance(rfq, RFQ)
        self.assertTrue(rfq.rfq_no)
        self.assertEqual(rfq.project_id, self.project.id)
        self.assertEqual(rfq.status, 'DRAFT')

        # 明细逐条映射(item/qty)
        lines = rfq.lines.filter(is_deleted=False).order_by('id')
        self.assertEqual(lines.count(), 2)

        line1 = lines.first()
        self.assertEqual(line1.item_id, self.item1.id)
        self.assertEqual(line1.qty, Decimal('3.00'))
        self.assertEqual(line1.required_date, date.today() + timedelta(days=20))
        self.assertEqual(line1.specifications, '需SUS304')
        self.assertTrue(line1.is_critical)
        self.assertEqual(line1.target_price, Decimal('12.50'))
        self.assertEqual(line1.technical_specs.get('功能模块'), '夹爪模块')
        # BOM 关联回填
        self.assertIsNotNone(line1.bom_item_id)

        line2 = lines.last()
        self.assertEqual(line2.item_id, self.item2.id)
        self.assertEqual(line2.qty, Decimal('5.00'))

    def test_convert_with_invited_suppliers(self):
        pr = self._make_pr(status='APPROVED')

        rfq = BatchRFQService.create_rfq_from_purchase_request(
            pr, self.user, supplier_ids=[self.supplier.id, self.supplier.id]
        )

        invitees = RFQSupplier.objects.filter(rfq=rfq, supplier=self.supplier)
        # 去重: 重复 supplier_id 只建一条
        self.assertEqual(invitees.count(), 1)

    def test_non_approved_pr_rejected(self):
        pr = self._make_pr(status='DRAFT')

        with self.assertRaises(ValueError):
            BatchRFQService.create_rfq_from_purchase_request(pr, self.user)

        self.assertEqual(RFQ.objects.count(), 0)
        self.assertEqual(RFQLine.objects.count(), 0)

    def test_pr_without_lines_rejected(self):
        pr = PurchaseRequest.objects.create(
            project=self.project,
            requestor=self.user,
            required_date=date.today() + timedelta(days=30),
            status='APPROVED',
            created_by=self.user,
        )
        with self.assertRaises(ValueError):
            BatchRFQService.create_rfq_from_purchase_request(pr, self.user)


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class PRToRFQApiTest(TestCase):
    """RFQ ViewSet detail=False action create_from_pr。"""

    def setUp(self):
        self.user = User.objects.create(
            username='pr2rfqapi', employee_id='PR2RFQAPI', is_staff=True, is_superuser=True
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.customer = Customer.objects.create(code='PRAC', name='API客户')
        self.project = Project.objects.create(
            code='PRAPRJ',
            name='API项目',
            customer=self.customer,
            manager=self.user,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            budget_material=Decimal('0'),
        )
        self.item = Item.objects.create(sku='PR-API-ITEM', name='API物料')

    def _make_pr(self, status='APPROVED'):
        pr = PurchaseRequest.objects.create(
            project=self.project,
            requestor=self.user,
            required_date=date.today() + timedelta(days=30),
            status=status,
            created_by=self.user,
        )
        PurchaseRequestLine.objects.create(
            pr=pr, item=self.item, qty=Decimal('4.00'), created_by=self.user
        )
        return pr

    def test_api_convert_approved_pr(self):
        pr = self._make_pr(status='APPROVED')
        resp = self.client.post(
            '/api/purchase/rfqs/create_from_pr/',
            {'purchase_request_id': pr.id},
            format='json',
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        rfq_id = resp.data['id']
        rfq = RFQ.objects.get(id=rfq_id)
        self.assertEqual(rfq.project_id, self.project.id)
        self.assertEqual(rfq.lines.count(), 1)

    def test_api_missing_pr_id(self):
        resp = self.client.post('/api/purchase/rfqs/create_from_pr/', {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_api_non_approved_rejected(self):
        pr = self._make_pr(status='DRAFT')
        resp = self.client.post(
            '/api/purchase/rfqs/create_from_pr/',
            {'purchase_request_id': pr.id},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)
