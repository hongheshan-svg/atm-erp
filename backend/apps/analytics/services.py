"""
Analytics and KPI calculation services
"""

from datetime import datetime, timedelta

from django.db.models import Avg, Count, F, Q, Sum

from apps.finance.models import AccountPayable, AccountReceivable, Expense
from apps.inventory.models import Stock, StockMove
from apps.projects.models import Project, ProjectTask
from apps.purchase.models import PurchaseOrder
from apps.sales.models import SalesOrder


class DashboardKPIService:
    """Calculate key performance indicators for executive dashboard"""

    @staticmethod
    def get_financial_kpis(start_date=None, end_date=None):
        """Calculate financial KPIs"""
        # 构建销售订单查询
        sales_qs = SalesOrder.objects.filter(status__in=['CONFIRMED', 'COMPLETED'], is_deleted=False)

        # 构建采购订单查询
        purchase_qs = PurchaseOrder.objects.filter(is_deleted=False)

        # 如果有日期范围，添加日期过滤
        if start_date and end_date:
            sales_qs = sales_qs.filter(order_date__range=[start_date, end_date])
            purchase_qs = purchase_qs.filter(order_date__range=[start_date, end_date])

        # Revenue metrics - 使用含税金额（优先）或不含税金额
        sales_data = sales_qs.aggregate(
            total_revenue=Sum('total_with_tax'),
            total_amount=Sum('total_amount'),
            order_count=Count('id'),
            avg_order_value=Avg('total_with_tax'),
        )

        # Purchase metrics - 使用含税金额（优先）或不含税金额
        purchase_data = purchase_qs.aggregate(
            total_purchases=Sum('total_with_tax'), total_amount=Sum('total_amount'), po_count=Count('id')
        )

        # AR/AP metrics
        ar_data = AccountReceivable.objects.filter(status__in=['PENDING', 'PARTIAL', 'OVERDUE']).aggregate(
            total_receivable=Sum(F('amount_due') - F('amount_paid'))
        )

        ap_data = AccountPayable.objects.filter(status__in=['PENDING', 'PARTIAL', 'OVERDUE']).aggregate(
            total_payable=Sum(F('amount_due') - F('amount_paid'))
        )

        # 优先使用含税金额，如果没有则使用不含税金额
        sales_total = sales_data['total_revenue'] or sales_data['total_amount'] or 0
        purchase_total = purchase_data['total_purchases'] or purchase_data['total_amount'] or 0
        receivables = ar_data['total_receivable'] or 0
        payables = ap_data['total_payable'] or 0

        return {
            'revenue': {
                'total': float(sales_total),
                'orders': sales_data['order_count'] or 0,
                'average_order': float(sales_data['avg_order_value'] or 0),
            },
            'purchases': {'total': float(purchase_total), 'orders': purchase_data['po_count'] or 0},
            'receivables': float(receivables),
            'payables': float(payables),
            'net_cash_position': float(receivables - payables),
        }

    @staticmethod
    def get_project_kpis():
        """Calculate project-related KPIs"""
        projects = Project.objects.filter(status__in=['IN_PROGRESS', 'ACTIVE'])

        total_budget = projects.aggregate(Sum('budget_total'))['budget_total__sum'] or 0
        project_count = projects.count()

        # Calculate completion rates
        tasks = ProjectTask.objects.filter(project__status__in=['IN_PROGRESS', 'ACTIVE'])
        task_completion = tasks.aggregate(total=Count('id'), completed=Count('id', filter=Q(status='COMPLETED')))

        completion_rate = 0
        if task_completion['total'] > 0:
            completion_rate = (task_completion['completed'] / task_completion['total']) * 100

        return {
            'active_projects': project_count,
            'total_budget': total_budget,
            'task_completion_rate': round(completion_rate, 2),
            'total_tasks': task_completion['total'],
            'completed_tasks': task_completion['completed'],
        }

    @staticmethod
    def get_inventory_kpis():
        """Calculate inventory KPIs"""
        # Total inventory value
        inventory_value = (
            Stock.objects.aggregate(total_value=Sum(F('qty_on_hand') * F('weighted_avg_cost')))['total_value'] or 0
        )

        # Stock items count
        total_items = Stock.objects.count()
        low_stock_items = Stock.objects.filter(qty_on_hand__lte=F('item__min_stock')).count()

        # Recent stock movements
        recent_moves = StockMove.objects.filter(move_date__gte=datetime.now() - timedelta(days=7)).count()

        return {
            'inventory_value': inventory_value,
            'total_items': total_items,
            'low_stock_items': low_stock_items,
            'recent_movements': recent_moves,
        }

    @staticmethod
    def get_all_kpis(start_date=None, end_date=None):
        """Get comprehensive KPI dashboard"""
        return {
            'financial': DashboardKPIService.get_financial_kpis(start_date, end_date),
            'projects': DashboardKPIService.get_project_kpis(),
            'inventory': DashboardKPIService.get_inventory_kpis(),
            'timestamp': datetime.now().isoformat(),
        }


class CashFlowForecastService:
    """Cash flow forecasting service"""

    @staticmethod
    def forecast_next_30_days():
        """Forecast cash flow for next 30 days"""
        today = datetime.now().date()
        forecast_end = today + timedelta(days=30)

        # Expected receivables
        expected_inflows = (
            AccountReceivable.objects.filter(
                due_date__range=[today, forecast_end], status__in=['PENDING', 'PARTIAL']
            ).aggregate(total=Sum(F('amount_due') - F('amount_paid')))['total']
            or 0
        )

        # Expected payables
        expected_outflows = (
            AccountPayable.objects.filter(
                due_date__range=[today, forecast_end], status__in=['PENDING', 'PARTIAL']
            ).aggregate(total=Sum(F('amount_due') - F('amount_paid')))['total']
            or 0
        )

        # Projected expenses
        avg_monthly_expense = (
            Expense.objects.filter(expense_date__gte=today - timedelta(days=90), status='APPROVED').aggregate(
                Avg('amount')
            )['amount__avg']
            or 0
        )

        projected_expenses = avg_monthly_expense

        return {
            'period': {'start': today.isoformat(), 'end': forecast_end.isoformat()},
            'expected_inflows': float(expected_inflows),
            'expected_outflows': float(expected_outflows) + float(projected_expenses),
            'net_cash_flow': float(expected_inflows) - float(expected_outflows) - float(projected_expenses),
            'breakdown': {
                'receivables': float(expected_inflows),
                'payables': float(expected_outflows),
                'expenses': float(projected_expenses),
            },
        }


class InventoryAnalyticsService:
    """Inventory turnover and analytics"""

    @staticmethod
    def calculate_turnover_rate(days=30):
        """Calculate inventory turnover rate"""
        start_date = datetime.now() - timedelta(days=days)

        # Stock movements out
        outbound_moves = (
            StockMove.objects.filter(move_date__gte=start_date, move_type__in=['OUT_SALES', 'OUT_PROJECT']).aggregate(
                total_cost=Sum(F('qty') * F('unit_cost'))
            )['total_cost']
            or 0
        )

        # Average inventory value
        avg_inventory = (
            Stock.objects.aggregate(total_value=Sum(F('qty_on_hand') * F('weighted_avg_cost')))['total_value'] or 0
        )

        turnover_rate = 0
        if avg_inventory > 0:
            turnover_rate = (float(outbound_moves) / float(avg_inventory)) * (365 / days)

        return {
            'turnover_rate': round(turnover_rate, 2),
            'period_days': days,
            'outbound_value': float(outbound_moves),
            'average_inventory_value': float(avg_inventory),
        }

    @staticmethod
    def get_slow_moving_items(days=90):
        """Identify slow-moving inventory.

        返回字段与前端 SlowMovingReport.vue / InventoryAnalytics.vue 对齐：
        item_code/item_name/category_name/specification/unit/warehouse_name/
        qty/unit_cost/total_value/aging_days/last_move_date 以及 id 字段。
        """
        from django.db.models import Max

        today = datetime.now().date()
        start_date = today - timedelta(days=days)

        # 有近期移动的物料（按物料维度，不区分仓库）
        moved_item_ids = (
            StockMove.objects.filter(move_date__gte=start_date).values_list('item_id', flat=True).distinct()
        )

        # 每个物料的最后移动日期（用于计算呆滞天数）
        last_move_map = {
            row['item_id']: row['last_date']
            for row in StockMove.objects.values('item_id').annotate(last_date=Max('move_date'))
        }

        stocks = (
            Stock.objects.filter(is_deleted=False, qty_on_hand__gt=0)
            .exclude(item_id__in=moved_item_ids)
            .select_related('item', 'item__category', 'warehouse')
        )

        items = []
        for stock in stocks:
            item = stock.item
            qty = float(stock.qty_on_hand or 0)
            unit_cost = float(stock.weighted_avg_cost or 0)
            last_move_date = last_move_map.get(item.id)
            aging_days = (today - last_move_date).days if last_move_date else days
            items.append(
                {
                    'id': stock.id,
                    'item_id': item.id,
                    'warehouse_id': stock.warehouse_id,
                    'item_code': item.sku,
                    'item_name': item.name,
                    'specification': item.specification or '',
                    'unit': item.unit,
                    'category_name': item.category.name if item.category else '',
                    'warehouse_name': stock.warehouse.name if stock.warehouse else '',
                    'qty': qty,
                    'unit_cost': unit_cost,
                    'total_value': round(qty * unit_cost, 2),
                    'last_move_date': last_move_date.isoformat() if last_move_date else '',
                    'aging_days': aging_days,
                }
            )

        items.sort(key=lambda x: x['aging_days'], reverse=True)
        return items
