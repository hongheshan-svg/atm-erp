"""
MRP 净需求修正 + ABC 分类 回归测试（P2 库存改进）。

覆盖：
1. MRP 缺口不应被“已预留给其他项目/订单”的库存低估（专料专用，审计 gap a）。
2. 多级 BOM（parent→children 递归）需求包含子件/孙件，且环路不死循环（审计 gap b）。
3. 建议采购日期不得早于今天（提前期倒推落到过去时收敛到今天）。
4. ABC 分类按 80/15/5 累计价值法正确分派 A/B/C。

运行：python manage.py test apps.inventory.tests.test_mrp_and_abc
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.inventory.models import Stock, StockMove
from apps.inventory.mrp import MRPLine, MRPPlan, MRPService
from apps.inventory.stock_alert import ABCClassificationService
from apps.masterdata.models import Customer, Item, Warehouse
from apps.projects.models import Project, ProjectBOM


class MRPNetRequirementTest(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.wh = Warehouse.objects.create(code='WH_MRP', name='MRP测试仓')
        self.customer = Customer.objects.create(code='CUST_MRP', name='MRP测试客户')
        self.manager = get_user_model().objects.create_user(username='mrp_tester', password='x')
        self.project = Project.objects.create(
            code='PRJ_MRP',
            name='MRP测试项目',
            customer=self.customer,
            manager=self.manager,
            start_date=self.today,
            end_date=self.today + timedelta(days=30),
            status='IN_PROGRESS',
        )

    def _make_plan(self):
        return MRPPlan.objects.create(
            plan_no='MRP_TEST_1',
            name='测试计划',
            start_date=self.today,
            end_date=self.today + timedelta(days=30),
            projects=[self.project.id],
        )

    def test_reserved_stock_excluded_from_availability(self):
        """已预留给其他项目的在库不应被当作本计划可用 → 缺口不被低估（gap a）。"""
        item = Item.objects.create(sku='SKU_RSV', name='预留物料', purchase_price=Decimal('10'), lead_time=7)
        ProjectBOM.objects.create(
            project=self.project,
            item=item,
            planned_qty=Decimal('100'),
            required_date=self.today + timedelta(days=20),
        )
        # 在库 100，但全部已预留（给其他项目/订单）→ 对本计划的可用在库应为 0
        Stock.objects.create(
            warehouse=self.wh,
            item=item,
            qty_on_hand=Decimal('100'),
            qty_reserved=Decimal('100'),
        )

        plan = self._make_plan()
        MRPService.calculate_plan(plan)

        line = MRPLine.objects.get(plan=plan, item=item)
        # 修复前：available=100 → 净需求 0（漏判缺料）；修复后：可用=0 → 净需求=100
        self.assertEqual(line.net_requirement, Decimal('100'))
        self.assertEqual(line.suggested_action, 'PURCHASE')
        # 明细口径自洽：allocated_qty 计入预留量
        self.assertEqual(line.allocated_qty, Decimal('100'))
        self.assertGreaterEqual(plan.shortage_items, 1)

    def test_unreserved_stock_still_counted(self):
        """未预留在库仍应正常抵扣，确认修复未误伤正常可用库存。"""
        item = Item.objects.create(sku='SKU_FREE', name='自由物料', purchase_price=Decimal('10'), lead_time=7)
        ProjectBOM.objects.create(
            project=self.project,
            item=item,
            planned_qty=Decimal('100'),
            required_date=self.today + timedelta(days=20),
        )
        Stock.objects.create(
            warehouse=self.wh,
            item=item,
            qty_on_hand=Decimal('100'),
            qty_reserved=Decimal('0'),
        )
        plan = self._make_plan()
        MRPService.calculate_plan(plan)
        line = MRPLine.objects.get(plan=plan, item=item)
        self.assertEqual(line.net_requirement, Decimal('0'))
        self.assertEqual(line.suggested_action, 'NONE')

    def test_multi_level_bom_includes_subcomponents(self):
        """多级 BOM（装配→子件→孙件）的子件/孙件需求应全部纳入毛需求（gap b）。"""
        asm = Item.objects.create(sku='SKU_ASM', name='装配体')
        child = Item.objects.create(sku='SKU_CHILD', name='子件')
        grandchild = Item.objects.create(sku='SKU_GC', name='孙件')

        bom_asm = ProjectBOM.objects.create(project=self.project, item=asm, planned_qty=Decimal('1'), level=0)
        bom_child = ProjectBOM.objects.create(
            project=self.project, item=child, planned_qty=Decimal('4'), level=1, parent=bom_asm
        )
        ProjectBOM.objects.create(
            project=self.project, item=grandchild, planned_qty=Decimal('8'), level=2, parent=bom_child
        )

        plan = self._make_plan()
        MRPService.calculate_plan(plan)

        # 三个层级的物料都应出现，毛需求 = 各自 planned_qty（本系统绝对量约定，不重复计数）
        self.assertEqual(MRPLine.objects.get(plan=plan, item=asm).gross_requirement, Decimal('1'))
        self.assertEqual(MRPLine.objects.get(plan=plan, item=child).gross_requirement, Decimal('4'))
        self.assertEqual(MRPLine.objects.get(plan=plan, item=grandchild).gross_requirement, Decimal('8'))
        # 恰好三行，未因“既平铺又递归”而重复计数
        self.assertEqual(MRPLine.objects.filter(plan=plan).count(), 3)

    def test_bom_cycle_does_not_hang_and_counts_once(self):
        """父子环路数据不应死循环，且每行只计一次（visited + 深度保护）。"""
        a = Item.objects.create(sku='SKU_CYC_A', name='环A')
        b = Item.objects.create(sku='SKU_CYC_B', name='环B')
        bom_a = ProjectBOM.objects.create(project=self.project, item=a, planned_qty=Decimal('2'))
        bom_b = ProjectBOM.objects.create(project=self.project, item=b, planned_qty=Decimal('3'), parent=bom_a)
        # 制造环路：A 的父指向 B，B 的父指向 A
        bom_a.parent = bom_b
        bom_a.save(update_fields=['parent'])

        plan = self._make_plan()
        MRPService.calculate_plan(plan)  # 不应挂起

        self.assertEqual(MRPLine.objects.get(plan=plan, item=a).gross_requirement, Decimal('2'))
        self.assertEqual(MRPLine.objects.get(plan=plan, item=b).gross_requirement, Decimal('3'))
        self.assertEqual(MRPLine.objects.filter(plan=plan).count(), 2)

    def test_suggested_date_never_in_past(self):
        """需求日期临近/过期时，按提前期倒推的建议日期不得早于今天。"""
        item = Item.objects.create(sku='SKU_PAST', name='紧急物料', purchase_price=Decimal('10'), lead_time=7)
        # 需求日期=今天，提前期 7 天 → 倒推 = 今天-7（过去）→ 应收敛到今天
        ProjectBOM.objects.create(
            project=self.project, item=item, planned_qty=Decimal('5'), required_date=self.today
        )
        plan = self._make_plan()
        MRPService.calculate_plan(plan)
        line = MRPLine.objects.get(plan=plan, item=item)
        self.assertGreaterEqual(line.suggested_date, self.today)
        self.assertEqual(line.suggested_date, self.today)


class ABCClassificationTest(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.wh = Warehouse.objects.create(code='WH_ABC', name='ABC仓')

    def _seed_consumption(self, sku, name, qty, unit_cost):
        item = Item.objects.create(sku=sku, name=name)
        # 预置足量库存，避免 COMPLETED 出库触发“库存不足”
        Stock.objects.create(warehouse=self.wh, item=item, qty_on_hand=Decimal('100000'))
        StockMove.objects.create(
            move_no=f'SM_ABC_{sku}',
            item=item,
            warehouse_from=self.wh,
            qty=Decimal(qty),
            unit_cost=Decimal(unit_cost),
            move_type='OUT_PROJECT',
            move_date=self.today,
            status='COMPLETED',
        )
        return item

    def test_abc_split_80_15_5(self):
        """年消耗金额 A=800 / B=150 / C=50（合计 1000）→ 累计占比 0.80/0.95/1.00。"""
        item_a = self._seed_consumption('ABC_A', '高价值', '8', '100')  # 800
        item_b = self._seed_consumption('ABC_B', '中价值', '15', '10')  # 150
        item_c = self._seed_consumption('ABC_C', '低价值', '10', '5')  # 50

        mapping = ABCClassificationService.classify()
        self.assertEqual(mapping[item_a.id], 'A')
        self.assertEqual(mapping[item_b.id], 'B')
        self.assertEqual(mapping[item_c.id], 'C')

    def test_abc_values_and_ordering(self):
        """compute() 应按消耗金额降序，且金额 = 数量 × 单价（Decimal）。"""
        item_a = self._seed_consumption('ABC_A2', '高价值', '8', '100')
        self._seed_consumption('ABC_B2', '中价值', '15', '10')
        rows = ABCClassificationService.compute()
        self.assertEqual(rows[0]['item_id'], item_a.id)
        self.assertEqual(rows[0]['annual_value'], Decimal('800'))
        self.assertEqual(rows[0]['annual_qty'], Decimal('8'))
        self.assertEqual(rows[1]['annual_value'], Decimal('150'))

    def test_no_consumption_item_excluded(self):
        """无出库消耗的物料不参与分级（不在结果映射中）。"""
        item = Item.objects.create(sku='ABC_NONE', name='无消耗')
        Stock.objects.create(warehouse=self.wh, item=item, qty_on_hand=Decimal('50'))
        mapping = ABCClassificationService.classify()
        self.assertNotIn(item.id, mapping)
