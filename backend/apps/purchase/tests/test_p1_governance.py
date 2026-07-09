"""P1 采购/SRM 治理修复回归测试。

覆盖三项修复：
1) 预算事前控制（真正拦截）：
   - 超项目材料预算的采购申请在序列化器 create() 阶段被拒（raise ValidationError）。
   - BudgetService 消费/释放：审批消费预算、取消释放预算，幂等且锁行（TOCTOU 收口）。
2) 比价转采购订单治理（comparison_service.convert_to_po）：
   - 黑名单供应商被拒。
   - 报价明细带 BOM 关联时，回填到 PurchaseOrderLine.bom_item（使 sync_bom_on_po_confirm 信号可触发）。
3) 供应商等级落地（Supplier.grade）：
   - 评价审批通过把等级写入 Supplier.grade（权威字段）。
   - 仅当等级实际变化时才新增一条 SupplierGradeHistory。
"""

from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.masterdata.models import Customer, Item, Supplier
from apps.projects.models import Project, ProjectBOM
from apps.purchase.budget import BudgetService, BudgetUsageRecord, PurchaseBudget
from apps.purchase.comparison_service import QuotationComparisonService
from apps.purchase.evaluation_models import (
    SupplierBlacklist,
    SupplierEvaluation,
    SupplierEvaluationTemplate,
    SupplierGradeHistory,
)
from apps.purchase.models import PurchaseOrder, PurchaseRequest
from apps.purchase.rfq_models import (
    RFQ,
    QuotationComparison,
    RFQLine,
    RFQSupplier,
    SupplierQuotation,
    SupplierQuotationLine,
)
from apps.purchase.serializers import PurchaseRequestSerializer


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class BudgetPreControlTest(TestCase):
    """采购申请事前预算控制 + 预算消费/释放。"""

    def setUp(self):
        self.user = User.objects.create(
            username='p1budget', employee_id='P1B', is_staff=True, is_superuser=True
        )
        self.customer = Customer.objects.create(code='P1C', name='客户甲')
        self.item = Item.objects.create(sku='P1-ITEM1', name='测试物料1')
        self.project = Project.objects.create(
            code='P1PRJ',
            name='预算项目',
            customer=self.customer,
            manager=self.user,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            budget_material=Decimal('100.00'),
        )

    def _pr_serializer(self, qty, price):
        data = {
            'project': self.project.id,
            'required_date': '2026-08-01',
            'tax_rate': 13,
            'lines': [{'item': self.item.id, 'qty': str(qty), 'estimated_price': str(price)}],
        }
        serializer = PurchaseRequestSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        return serializer

    def test_over_budget_pr_rejected(self):
        """总额 200 > 材料预算 100，create() 抛 ValidationError，且不落库。"""
        serializer = self._pr_serializer(qty=10, price=20)  # 200
        with self.assertRaises(ValidationError):
            serializer.save(created_by=self.user, requestor=self.user)
        self.assertEqual(PurchaseRequest.objects.filter(project=self.project).count(), 0)

    def test_within_budget_pr_created(self):
        """总额 50 <= 材料预算 100，正常创建。"""
        serializer = self._pr_serializer(qty=5, price=10)  # 50
        pr = serializer.save(created_by=self.user, requestor=self.user)
        self.assertEqual(pr.status, 'DRAFT')
        self.assertEqual(pr.total_amount, Decimal('50.00'))
        self.assertEqual(pr.lines.count(), 1)

    def _active_budget(self):
        return PurchaseBudget.objects.create(
            budget_no='P1BUD',
            name='项目采购预算',
            budget_type='PROJECT',
            year=2026,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            total_amount=Decimal('1000.00'),
            status='ACTIVE',
            project=self.project,
        )

    def test_budget_consumed_on_approve_and_released_on_cancel(self):
        budget = self._active_budget()

        # 消费（订单确认时的挂钩）
        rec = BudgetService.consume_for_reference(
            project_id=self.project.id,
            amount=Decimal('300.00'),
            reference_no='PO-A',
            reference_id=1,
            user=self.user,
        )
        self.assertIsNotNone(rec)
        budget.refresh_from_db()
        self.assertEqual(budget.used_amount, Decimal('300.00'))
        self.assertEqual(budget.available_amount, Decimal('700.00'))
        self.assertEqual(
            BudgetUsageRecord.objects.filter(
                budget=budget, usage_type='PURCHASE_ORDER', reference_no='PO-A', is_reserved=False
            ).count(),
            1,
        )

        # 幂等：重复消费不二次记账（防重复触发确认钩子）
        BudgetService.consume_for_reference(
            project_id=self.project.id,
            amount=Decimal('300.00'),
            reference_no='PO-A',
            reference_id=1,
            user=self.user,
        )
        budget.refresh_from_db()
        self.assertEqual(budget.used_amount, Decimal('300.00'))
        self.assertEqual(
            BudgetUsageRecord.objects.filter(
                budget=budget, usage_type='PURCHASE_ORDER', reference_no='PO-A', is_reserved=False
            ).count(),
            1,
        )

        # 取消释放
        released = BudgetService.release_for_reference(
            project_id=self.project.id, reference_no='PO-A', reference_id=1, user=self.user
        )
        self.assertTrue(released)
        budget.refresh_from_db()
        self.assertEqual(budget.used_amount, Decimal('0.00'))

        # 幂等：重复释放为 no-op
        again = BudgetService.release_for_reference(
            project_id=self.project.id, reference_no='PO-A', reference_id=1, user=self.user
        )
        self.assertIsNone(again)
        budget.refresh_from_db()
        self.assertEqual(budget.used_amount, Decimal('0.00'))

    def test_reserve_is_idempotent(self):
        budget = self._active_budget()
        BudgetService.reserve_for_reference(
            project_id=self.project.id, amount=Decimal('120.00'), reference_no='PR-A', reference_id=9, user=self.user
        )
        BudgetService.reserve_for_reference(
            project_id=self.project.id, amount=Decimal('120.00'), reference_no='PR-A', reference_id=9, user=self.user
        )
        budget.refresh_from_db()
        self.assertEqual(budget.reserved_amount, Decimal('120.00'))


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class ComparisonToPOGovernanceTest(TestCase):
    """比价转 PO：黑名单准入 + BOM 关联回填。"""

    def setUp(self):
        self.user = User.objects.create(
            username='p1cmp', employee_id='P1CMP', is_staff=True, is_superuser=True
        )
        self.customer = Customer.objects.create(code='P1CC', name='客户乙')
        self.item = Item.objects.create(sku='P1-CMP-ITEM', name='比价物料')

    def _build_comparison(self, supplier, project=None, bom_item=None):
        rfq = RFQ.objects.create(project=project, response_deadline=date.today() + timedelta(days=7))
        rfq_line = RFQLine.objects.create(
            rfq=rfq, item=self.item, qty=Decimal('2'), required_date=date.today() + timedelta(days=30),
            bom_item=bom_item,
        )
        rfq_supplier = RFQSupplier.objects.create(rfq=rfq, supplier=supplier)
        quotation = SupplierQuotation.objects.create(
            rfq_supplier=rfq_supplier,
            valid_until=date.today() + timedelta(days=30),
            payment_terms='NET30',
            delivery_terms='FOB',
            status='ACCEPTED',
        )
        SupplierQuotationLine.objects.create(
            quotation=quotation, rfq_line=rfq_line, unit_price=Decimal('50.00'), qty=Decimal('2'),
            lead_time_days=15,
        )
        comparison = QuotationComparison.objects.create(
            rfq=rfq, recommended_quotation=quotation, status='APPROVED'
        )
        return comparison

    def test_convert_to_po_refuses_blacklisted_supplier(self):
        bad = Supplier.objects.create(code='P1BAD', name='黑名单供应商')
        SupplierBlacklist.objects.create(
            supplier=bad, blacklist_date=date.today(), reason='严重质量事故', status='ACTIVE'
        )
        comparison = self._build_comparison(bad)
        with self.assertRaises(ValueError):
            QuotationComparisonService.convert_to_po(comparison.id, self.user)
        self.assertEqual(PurchaseOrder.objects.count(), 0)

    def test_convert_to_po_sets_bom_item(self):
        good = Supplier.objects.create(code='P1GOOD', name='正常供应商')
        project = Project.objects.create(
            code='P1CMPPRJ',
            name='比价项目',
            customer=self.customer,
            manager=self.user,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            budget_material=Decimal('0'),  # 未设材料预算 => 预算校验放行
        )
        bom = ProjectBOM.objects.create(project=project, item=self.item, planned_qty=Decimal('2'))
        comparison = self._build_comparison(good, project=project, bom_item=bom)

        po = QuotationComparisonService.convert_to_po(comparison.id, self.user)

        line = po.lines.first()
        self.assertIsNotNone(line)
        self.assertEqual(line.bom_item_id, bom.id)
        self.assertTrue(po.lines.filter(bom_item__isnull=False).exists())


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class SupplierGradeWritebackTest(TestCase):
    """评价审批把等级写入 Supplier.grade，仅在变化时记历史。"""

    def setUp(self):
        self.user = User.objects.create(
            username='p1grade', employee_id='P1G', is_staff=True, is_superuser=True
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.supplier = Supplier.objects.create(code='P1SUP', name='被评供应商')
        self.template = SupplierEvaluationTemplate.objects.create(name='标准评价', code='STD-EVAL')

    def _make_evaluation(self, grade, score):
        return SupplierEvaluation.objects.create(
            supplier=self.supplier,
            template=self.template,
            evaluation_date=date.today(),
            period_start=date(2026, 1, 1),
            period_end=date(2026, 3, 31),
            total_score=Decimal(str(score)),
            grade=grade,
            status='SUBMITTED',
        )

    def _approve(self, evaluation):
        resp = self.client.post(f'/api/purchase/evaluations/{evaluation.pk}/approve/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        return resp

    def test_grade_written_and_history_only_on_change(self):
        # 首次评级 B：写入 Supplier.grade，记 1 条历史
        ev1 = self._make_evaluation('B', 85)
        self._approve(ev1)
        self.supplier.refresh_from_db()
        self.assertEqual(self.supplier.grade, 'B')
        self.assertEqual(SupplierGradeHistory.objects.filter(supplier=self.supplier).count(), 1)

        # 再次评级仍为 B：等级未变，不新增历史
        ev2 = self._make_evaluation('B', 82)
        self._approve(ev2)
        self.supplier.refresh_from_db()
        self.assertEqual(self.supplier.grade, 'B')
        self.assertEqual(SupplierGradeHistory.objects.filter(supplier=self.supplier).count(), 1)

        # 评级变为 A：等级变化，写入并新增 1 条历史
        ev3 = self._make_evaluation('A', 92)
        self._approve(ev3)
        self.supplier.refresh_from_db()
        self.assertEqual(self.supplier.grade, 'A')
        history = SupplierGradeHistory.objects.filter(supplier=self.supplier).order_by('id')
        self.assertEqual(history.count(), 2)
        last = history.last()
        self.assertEqual(last.old_grade, 'B')
        self.assertEqual(last.new_grade, 'A')
