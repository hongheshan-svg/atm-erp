from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from django.test import TestCase
from rest_framework import serializers

from apps.accounts.models import User
from apps.finance.models import Currency, Expense
from apps.inventory.models import StockMove
from apps.masterdata.models import Customer, Item, Warehouse
from apps.projects.models import Project, ProjectMember, TimeLog
from apps.reports.services.cost_service import CostCalculationService
from apps.sales.models import SalesOrder


class ProjectCostAccountingTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='cost-auditor', employee_id='COST-AUDITOR')
        self.customer = Customer.objects.create(code='COST-CUSTOMER', name='成本审计客户')
        self.project = Project.objects.create(
            code='PRJ-COST-AUDIT',
            name='成本审计项目',
            customer=self.customer,
            manager=self.user,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 12, 31),
        )

    def test_paid_expense_remains_in_project_cost_using_base_currency(self):
        usd = Currency.objects.create(
            code='USD',
            name='美元',
            symbol='$',
            exchange_rate=Decimal('7'),
        )
        Expense.objects.create(
            project=self.project,
            user=self.user,
            expense_date=date(2026, 7, 20),
            category='TRAVEL',
            currency=usd,
            amount=Decimal('100'),
            exchange_rate=Decimal('7'),
            description='项目差旅',
            status='PAID',
        )

        self.assertEqual(CostCalculationService.calculate_project_expense_cost(self.project.id), Decimal('700'))
        self.assertEqual(self.project.get_actual_expense_cost(), Decimal('700'))

    def test_labor_cost_uses_only_approved_time_logs(self):
        member = ProjectMember.objects.create(
            project=self.project,
            user=self.user,
            hourly_rate=Decimal('120'),
            actual_hours=Decimal('99'),
        )
        TimeLog.objects.create(
            project=self.project,
            user=self.user,
            date=date(2026, 7, 20),
            hours=Decimal('2.5'),
            status='APPROVED',
        )
        TimeLog.objects.create(
            project=self.project,
            user=self.user,
            date=date(2026, 7, 21),
            hours=Decimal('8'),
            status='PENDING',
        )

        self.assertEqual(CostCalculationService.calculate_project_labor_cost(self.project.id), Decimal('300'))
        self.assertEqual(self.project.get_actual_labor_cost(), Decimal('300'))
        member.refresh_from_db()
        self.assertEqual(member.actual_hours, Decimal('99'))

    def test_good_material_return_reduces_project_material_cost(self):
        warehouse = Warehouse.objects.create(code='COST-WH', name='成本审计仓')
        item = Item.objects.create(sku='COST-ITEM', name='成本审计物料')
        StockMove.objects.create(
            item=item,
            warehouse_to=warehouse,
            qty=Decimal('10'),
            unit_cost=Decimal('8'),
            move_type='IN_PURCHASE',
            move_date=date(2026, 7, 10),
            status='COMPLETED',
        )
        StockMove.objects.create(
            item=item,
            warehouse_from=warehouse,
            qty=Decimal('4'),
            unit_cost=Decimal('8'),
            move_type='OUT_PROJECT',
            project=self.project,
            move_date=date(2026, 7, 11),
            status='COMPLETED',
        )
        # 历史口径:IN_RETURN 启用前的退料入库写的是 ADJUSTMENT + reference_type='MaterialReturn'。
        # 这类存量行不做数据迁移,必须继续被扣减,否则老项目的材料成本会凭空虚高。
        StockMove.objects.create(
            item=item,
            warehouse_to=warehouse,
            qty=Decimal('1'),
            unit_cost=Decimal('8'),
            move_type='ADJUSTMENT',
            reference_type='MaterialReturn',
            project=self.project,
            move_date=date(2026, 7, 12),
            status='COMPLETED',
        )

        self.assertEqual(CostCalculationService.calculate_project_material_cost(self.project.id), Decimal('24'))
        self.assertEqual(self.project.get_actual_material_cost(), Decimal('24'))

        # 新口径:IN_RETURN 同样扣减,且与历史行可以共存于同一项目。
        StockMove.objects.create(
            item=item,
            warehouse_to=warehouse,
            qty=Decimal('1'),
            unit_cost=Decimal('8'),
            move_type='IN_RETURN',
            reference_type='MaterialReturn',
            project=self.project,
            move_date=date(2026, 7, 13),
            status='COMPLETED',
        )

        self.assertEqual(CostCalculationService.calculate_project_material_cost(self.project.id), Decimal('16'))
        self.assertEqual(self.project.get_actual_material_cost(), Decimal('16'))

        # 批量口径(calculate_projects_profit)与单项目口径必须同源,否则报表汇总与明细对不上。
        batch = CostCalculationService.calculate_projects_profit([self.project.id])
        self.assertEqual(Decimal(str(batch[self.project.id]['material_cost'])), Decimal('16'))

    def test_project_return_derives_cost_and_blocks_over_return(self):
        from apps.inventory.material_serializers import MaterialReturnSerializer

        warehouse = Warehouse.objects.create(code='RETURN-WH', name='退料成本仓')
        item = Item.objects.create(sku='RETURN-ITEM', name='退料成本物料')
        StockMove.objects.create(
            item=item,
            warehouse_to=warehouse,
            qty=Decimal('10'),
            unit_cost=Decimal('8'),
            move_type='IN_PURCHASE',
            move_date=date(2026, 7, 10),
            status='COMPLETED',
        )
        StockMove.objects.create(
            item=item,
            warehouse_from=warehouse,
            qty=Decimal('4'),
            unit_cost=Decimal('8'),
            move_type='OUT_PROJECT',
            project=self.project,
            move_date=date(2026, 7, 11),
            status='COMPLETED',
        )
        context = {'request': SimpleNamespace(user=self.user)}
        payload = {
            'return_type': 'PROJECT',
            'return_reason': 'SURPLUS',
            'project': self.project.id,
            'warehouse': warehouse.id,
            'lines': [{'item': item.id, 'qty': '2'}],
        }
        serializer = MaterialReturnSerializer(data=payload, context=context)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        material_return = serializer.save()
        self.assertEqual(material_return.lines.get().unit_cost, Decimal('8.0000'))

        over_return = MaterialReturnSerializer(
            data={**payload, 'lines': [{'item': item.id, 'qty': '3'}]},
            context=context,
        )
        self.assertTrue(over_return.is_valid(), over_return.errors)
        with self.assertRaisesMessage(serializers.ValidationError, '超过项目净可退数量'):
            over_return.save()

    def test_project_revenue_excludes_output_tax(self):
        SalesOrder.objects.create(
            customer=self.customer,
            project=self.project,
            order_date=date(2026, 7, 1),
            delivery_date=date(2026, 8, 1),
            status='CONFIRMED',
            total_amount=Decimal('100'),
            tax_amount=Decimal('13'),
            total_with_tax=Decimal('113'),
        )

        self.assertEqual(CostCalculationService.calculate_project_revenue(self.project.id), Decimal('100'))
