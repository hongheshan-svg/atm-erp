"""
Cost calculation service using Pandas for project profitability analysis.
"""

import logging
from decimal import Decimal

import pandas as pd
from django.core.cache import cache
from django.db.models import Case, DecimalField, F, Sum, When

logger = logging.getLogger(__name__)


class CostCalculationService:
    """
    Service class for calculating project costs and profitability.
    Uses Pandas for complex calculations and caching for performance.
    """

    CACHE_TIMEOUT = 3600  # 1 hour

    @classmethod
    def calculate_project_material_cost(cls, project_id):
        """
        Calculate material cost from OUT_PROJECT stock moves.
        Returns: Decimal
        """
        from apps.inventory.models import StockMove

        outbound = StockMove.objects.filter(
            project_id=project_id, move_type='OUT_PROJECT', status='COMPLETED', is_deleted=False
        ).aggregate(total=Sum(F('qty') * F('unit_cost')))
        returned = StockMove.objects.filter(
            project_id=project_id,
            move_type='ADJUSTMENT',
            reference_type='MaterialReturn',
            status='COMPLETED',
            is_deleted=False,
        ).aggregate(total=Sum(F('qty') * F('unit_cost')))

        return (outbound['total'] or Decimal('0')) - (returned['total'] or Decimal('0'))

    @classmethod
    def calculate_project_labor_cost(cls, project_id):
        """
        Calculate labor cost from approved time logs and project-member rates.
        Returns: Decimal
        """
        from apps.projects.models import Project

        project = Project.objects.filter(pk=project_id, is_deleted=False).first()
        return project.get_actual_labor_cost() if project else Decimal('0')

    @classmethod
    def calculate_project_expense_cost(cls, project_id):
        """
        Calculate expense cost from approved expenses.
        Returns: Decimal
        """
        from apps.finance.models import Expense

        result = Expense.objects.filter(
            project_id=project_id, status__in=['APPROVED', 'PAID'], is_deleted=False
        ).aggregate(
            total=Sum(
                Case(
                    When(base_amount__isnull=False, then=F('base_amount')),
                    default=F('amount'),
                    output_field=DecimalField(max_digits=18, decimal_places=2),
                )
            )
        )

        return result['total'] or Decimal('0')

    @classmethod
    def calculate_project_revenue(cls, project_id):
        """
        Calculate contract revenue from confirmed sales orders linked to project.
        Revenue excludes output VAT.
        Returns: Decimal
        """
        from apps.sales.models import SalesOrder

        result = SalesOrder.objects.filter(
            project_id=project_id, status__in=['CONFIRMED', 'PARTIAL', 'COMPLETED'], is_deleted=False
        ).aggregate(total_amount=Sum('total_amount'))

        return result['total_amount'] or Decimal('0')

    @classmethod
    def calculate_project_profit(cls, project_id):
        """
        Calculate project profitability: Revenue - (Material + Labor + Expense).
        Returns: dict with detailed breakdown
        """
        cache_key = f'project_profit_{project_id}'

        # Try to get from cache, but gracefully handle connection errors
        try:
            cached_result = cache.get(cache_key)
            if cached_result:
                return cached_result
        except Exception as e:
            logger.warning(f'Cache unavailable, calculating directly: {e}')

        # Calculate all cost components
        revenue = cls.calculate_project_revenue(project_id)
        material_cost = cls.calculate_project_material_cost(project_id)
        labor_cost = cls.calculate_project_labor_cost(project_id)
        expense_cost = cls.calculate_project_expense_cost(project_id)

        total_cost = material_cost + labor_cost + expense_cost
        profit = revenue - total_cost

        # Calculate margin percentage
        margin = (profit / revenue * 100) if revenue > 0 else Decimal('0')

        result = {
            'project_id': project_id,
            'revenue': float(revenue),
            'material_cost': float(material_cost),
            'labor_cost': float(labor_cost),
            'expense_cost': float(expense_cost),
            'total_cost': float(total_cost),
            'profit': float(profit),
            'margin_percent': float(margin),
        }

        # Try to cache the result, but don't fail if cache is unavailable
        try:
            cache.set(cache_key, result, cls.CACHE_TIMEOUT)
        except Exception as e:
            logger.warning(f'Failed to cache result: {e}')

        return result

    @classmethod
    def calculate_projects_profit(cls, project_ids):
        """批量计算多个项目的利润。

        逐项目调 calculate_project_profit 会发 5~6 条查询（收入/出库/退料/费用/工时/费率），
        导出上千个项目时就是上万次查询。这里改成按项目分组的固定几条聚合。
        返回 {project_id: 与 calculate_project_profit 同结构的 dict}。
        """
        from apps.finance.models import Expense
        from apps.inventory.models import StockMove
        from apps.projects.models import ProjectMember, TimeLog
        from apps.sales.models import SalesOrder

        project_ids = list(project_ids)
        if not project_ids:
            return {}

        zero = Decimal('0')

        def _sum_by_project(queryset, expression):
            return {
                row['project_id']: row['total'] or zero
                for row in queryset.values('project_id').annotate(total=Sum(expression))
            }

        revenue_map = _sum_by_project(
            SalesOrder.objects.filter(
                project_id__in=project_ids, status__in=['CONFIRMED', 'PARTIAL', 'COMPLETED'], is_deleted=False
            ),
            'total_amount',
        )
        outbound_map = _sum_by_project(
            StockMove.objects.filter(
                project_id__in=project_ids, move_type='OUT_PROJECT', status='COMPLETED', is_deleted=False
            ),
            F('qty') * F('unit_cost'),
        )
        returned_map = _sum_by_project(
            StockMove.objects.filter(
                project_id__in=project_ids,
                move_type='ADJUSTMENT',
                reference_type='MaterialReturn',
                status='COMPLETED',
                is_deleted=False,
            ),
            F('qty') * F('unit_cost'),
        )
        expense_map = _sum_by_project(
            Expense.objects.filter(project_id__in=project_ids, status__in=['APPROVED', 'PAID'], is_deleted=False),
            Case(
                When(base_amount__isnull=False, then=F('base_amount')),
                default=F('amount'),
                output_field=DecimalField(max_digits=18, decimal_places=2),
            ),
        )

        # 人工成本口径与 Project.get_actual_labor_cost 一致：已批准工时 × 该项目成员费率，
        # 这里用两条查询覆盖全部项目
        rates = {
            (row['project_id'], row['user_id']): row['hourly_rate'] or zero
            for row in ProjectMember.objects.filter(project_id__in=project_ids, is_deleted=False).values(
                'project_id', 'user_id', 'hourly_rate'
            )
        }
        labor_map = {}
        for row in (
            TimeLog.objects.filter(project_id__in=project_ids, status='APPROVED', is_deleted=False)
            .values('project_id', 'user_id')
            .annotate(total_hours=Sum('hours'))
        ):
            rate = rates.get((row['project_id'], row['user_id']), zero)
            labor_map[row['project_id']] = labor_map.get(row['project_id'], zero) + (row['total_hours'] or zero) * rate

        results = {}
        for pid in project_ids:
            revenue = revenue_map.get(pid, zero)
            material = outbound_map.get(pid, zero) - returned_map.get(pid, zero)
            labor = labor_map.get(pid, zero)
            expense = expense_map.get(pid, zero)
            total_cost = material + labor + expense
            profit = revenue - total_cost
            margin = (profit / revenue * 100) if revenue > 0 else zero
            results[pid] = {
                'project_id': pid,
                'revenue': float(revenue),
                'material_cost': float(material),
                'labor_cost': float(labor),
                'expense_cost': float(expense),
                'total_cost': float(total_cost),
                'profit': float(profit),
                'margin_percent': float(margin),
            }
        return results

    @classmethod
    def calculate_all_projects_profit(cls, status=None):
        """
        Calculate profitability for projects.
        Args:
            status: filter by project status (optional)。可传单个状态字符串，
                也可传状态列表——项目「进行中」同时存在 IN_PROGRESS(主用)与 ACTIVE(保留兼容)
                两个值，调用方需要一次覆盖两者。
        Returns: pandas DataFrame
        """
        from apps.projects.models import Project

        queryset = Project.objects.filter(is_deleted=False)
        if status:
            if isinstance(status, (list, tuple, set)):
                queryset = queryset.filter(status__in=list(status))
            else:
                queryset = queryset.filter(status=status)

        active_projects = list(queryset.values('id', 'code', 'name', 'status', 'manager__username'))

        # 批量算，避免每个项目 5~6 条查询
        profit_by_project = cls.calculate_projects_profit([p['id'] for p in active_projects])

        results = []
        for project in active_projects:
            profit_data = dict(profit_by_project.get(project['id'], {}))
            profit_data.update(
                {
                    'code': project['code'],
                    'name': project['name'],
                    'status': project['status'],
                    'manager': project['manager__username'] or '',
                }
            )
            results.append(profit_data)

        df = pd.DataFrame(results)

        if not df.empty:
            # Reorder columns for better readability
            columns_order = [
                'code',
                'name',
                'manager',
                'status',
                'revenue',
                'material_cost',
                'labor_cost',
                'expense_cost',
                'total_cost',
                'profit',
                'margin_percent',
            ]
            df = df[columns_order]

        return df

    @classmethod
    def get_project_cost_detail_with_pandas(cls, project_id):
        """
        Get detailed cost breakdown using Pandas for analysis.
        Returns: dict with DataFrames for each cost category
        """
        from apps.finance.models import Expense
        from apps.inventory.models import StockMove
        from apps.projects.models import ProjectMember

        # Material costs
        material_moves = (
            StockMove.objects.filter(
                project_id=project_id, move_type='OUT_PROJECT', status='COMPLETED', is_deleted=False
            )
            .select_related('item')
            .values('item__sku', 'item__name', 'item__unit', 'qty', 'unit_cost', 'move_date')
        )

        df_materials = pd.DataFrame(list(material_moves))
        if not df_materials.empty:
            df_materials['total_cost'] = df_materials['qty'] * df_materials['unit_cost']
            df_materials = df_materials.rename(
                columns={
                    'item__sku': 'SKU',
                    'item__name': '物料名称',
                    'item__unit': '单位',
                    'qty': '数量',
                    'unit_cost': '单价',
                    'move_date': '日期',
                }
            )

        # Labor costs
        members = (
            ProjectMember.objects.filter(project_id=project_id, is_deleted=False)
            .select_related('user')
            .values(
                'user__username',
                'user__first_name',
                'user__last_name',
                'role',
                'hourly_rate',
                'allocated_hours',
                'actual_hours',
            )
        )

        df_labor = pd.DataFrame(list(members))
        if not df_labor.empty:
            df_labor['total_cost'] = df_labor['actual_hours'] * df_labor['hourly_rate']
            df_labor['full_name'] = df_labor.apply(
                lambda x: (
                    f'{x["user__first_name"]} {x["user__last_name"]}' if x['user__first_name'] else x['user__username']
                ),
                axis=1,
            )
            df_labor = df_labor[['full_name', 'role', 'hourly_rate', 'allocated_hours', 'actual_hours', 'total_cost']]
            df_labor = df_labor.rename(
                columns={
                    'full_name': '成员',
                    'role': '角色',
                    'hourly_rate': '时薪',
                    'allocated_hours': '分配工时',
                    'actual_hours': '实际工时',
                    'total_cost': '人工成本',
                }
            )

        # Expenses
        expenses = (
            Expense.objects.filter(project_id=project_id, status__in=['APPROVED', 'PAID'], is_deleted=False)
            .select_related('user')
            .annotate(
                project_cost=Case(
                    When(base_amount__isnull=False, then=F('base_amount')),
                    default=F('amount'),
                    output_field=DecimalField(max_digits=18, decimal_places=2),
                )
            )
            .values('expense_no', 'user__username', 'expense_date', 'category', 'amount', 'project_cost', 'description')
        )

        df_expenses = pd.DataFrame(list(expenses))
        if not df_expenses.empty:
            df_expenses = df_expenses.rename(
                columns={
                    'expense_no': '报销单号',
                    'user__username': '报销人',
                    'expense_date': '日期',
                    'category': '类别',
                    'amount': '金额',
                    'project_cost': '项目成本（基准币）',
                    'description': '说明',
                }
            )

        return {
            'materials': df_materials.to_dict('records') if not df_materials.empty else [],
            'labor': df_labor.to_dict('records') if not df_labor.empty else [],
            'expenses': df_expenses.to_dict('records') if not df_expenses.empty else [],
            'summary': cls.calculate_project_profit(project_id),
        }

    @classmethod
    def clear_project_cache(cls, project_id):
        """Clear cached calculations for a project."""
        cache_key = f'project_profit_{project_id}'
        try:
            cache.delete(cache_key)
        except Exception as e:
            logger.warning(f'Failed to clear cache: {e}')
