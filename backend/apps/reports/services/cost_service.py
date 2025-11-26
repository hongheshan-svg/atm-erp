"""
Cost calculation service using Pandas for project profitability analysis.
"""
import logging
import pandas as pd
from decimal import Decimal
from django.db.models import Sum, F, Q
from django.core.cache import cache

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
        
        result = StockMove.objects.filter(
            project_id=project_id,
            move_type='OUT_PROJECT',
            status='COMPLETED',
            is_deleted=False
        ).aggregate(
            total=Sum(F('qty') * F('unit_cost'))
        )
        
        return result['total'] or Decimal('0')
    
    @classmethod
    def calculate_project_labor_cost(cls, project_id):
        """
        Calculate labor cost from project tasks and member hours.
        Returns: Decimal
        """
        from apps.projects.models import ProjectMember
        
        # Calculate from actual hours × hourly rate
        result = ProjectMember.objects.filter(
            project_id=project_id,
            is_deleted=False
        ).aggregate(
            total=Sum(F('actual_hours') * F('hourly_rate'))
        )
        
        return result['total'] or Decimal('0')
    
    @classmethod
    def calculate_project_expense_cost(cls, project_id):
        """
        Calculate expense cost from approved expenses.
        Returns: Decimal
        """
        from apps.finance.models import Expense
        
        result = Expense.objects.filter(
            project_id=project_id,
            status__in=['APPROVED', 'REIMBURSED'],
            is_deleted=False
        ).aggregate(total=Sum('amount'))
        
        return result['total'] or Decimal('0')
    
    @classmethod
    def calculate_project_revenue(cls, project_id):
        """
        Calculate revenue from sales orders linked to project.
        Returns: Decimal
        """
        from apps.sales.models import SalesOrder
        
        result = SalesOrder.objects.filter(
            project_id=project_id,
            status__in=['CONFIRMED', 'PARTIAL', 'COMPLETED'],
            is_deleted=False
        ).aggregate(total=Sum('total_amount'))
        
        return result['total'] or Decimal('0')
    
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
            logger.warning(f"Cache unavailable, calculating directly: {e}")
        
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
            'margin_percent': float(margin)
        }
        
        # Try to cache the result, but don't fail if cache is unavailable
        try:
            cache.set(cache_key, result, cls.CACHE_TIMEOUT)
        except Exception as e:
            logger.warning(f"Failed to cache result: {e}")
        
        return result
    
    @classmethod
    def calculate_all_projects_profit(cls, status=None):
        """
        Calculate profitability for projects.
        Args:
            status: filter by project status (optional)
        Returns: pandas DataFrame
        """
        from apps.projects.models import Project
        
        queryset = Project.objects.filter(is_deleted=False)
        if status:
            queryset = queryset.filter(status=status)
        
        active_projects = queryset.values('id', 'code', 'name', 'status', 'manager__username')
        
        results = []
        for project in active_projects:
            profit_data = cls.calculate_project_profit(project['id'])
            profit_data.update({
                'code': project['code'],
                'name': project['name'],
                'status': project['status'],
                'manager': project['manager__username'] or ''
            })
            results.append(profit_data)
        
        df = pd.DataFrame(results)
        
        if not df.empty:
            # Reorder columns for better readability
            columns_order = [
                'code', 'name', 'manager', 'status', 'revenue', 'material_cost',
                'labor_cost', 'expense_cost', 'total_cost', 'profit', 'margin_percent'
            ]
            df = df[columns_order]
        
        return df
    
    @classmethod
    def get_project_cost_detail_with_pandas(cls, project_id):
        """
        Get detailed cost breakdown using Pandas for analysis.
        Returns: dict with DataFrames for each cost category
        """
        from apps.inventory.models import StockMove
        from apps.projects.models import ProjectMember
        from apps.finance.models import Expense
        
        # Material costs
        material_moves = StockMove.objects.filter(
            project_id=project_id,
            move_type='OUT_PROJECT',
            status='COMPLETED',
            is_deleted=False
        ).select_related('item').values(
            'item__sku',
            'item__name',
            'item__unit',
            'qty',
            'unit_cost',
            'move_date'
        )
        
        df_materials = pd.DataFrame(list(material_moves))
        if not df_materials.empty:
            df_materials['total_cost'] = df_materials['qty'] * df_materials['unit_cost']
            df_materials = df_materials.rename(columns={
                'item__sku': 'SKU',
                'item__name': '物料名称',
                'item__unit': '单位',
                'qty': '数量',
                'unit_cost': '单价',
                'move_date': '日期'
            })
        
        # Labor costs
        members = ProjectMember.objects.filter(
            project_id=project_id,
            is_deleted=False
        ).select_related('user').values(
            'user__username',
            'user__first_name',
            'user__last_name',
            'role',
            'hourly_rate',
            'allocated_hours',
            'actual_hours'
        )
        
        df_labor = pd.DataFrame(list(members))
        if not df_labor.empty:
            df_labor['total_cost'] = df_labor['actual_hours'] * df_labor['hourly_rate']
            df_labor['full_name'] = df_labor.apply(
                lambda x: f"{x['user__first_name']} {x['user__last_name']}" if x['user__first_name'] else x['user__username'],
                axis=1
            )
            df_labor = df_labor[['full_name', 'role', 'hourly_rate', 'allocated_hours', 'actual_hours', 'total_cost']]
            df_labor = df_labor.rename(columns={
                'full_name': '成员',
                'role': '角色',
                'hourly_rate': '时薪',
                'allocated_hours': '分配工时',
                'actual_hours': '实际工时',
                'total_cost': '人工成本'
            })
        
        # Expenses
        expenses = Expense.objects.filter(
            project_id=project_id,
            status__in=['APPROVED', 'REIMBURSED'],
            is_deleted=False
        ).select_related('user').values(
            'expense_no',
            'user__username',
            'expense_date',
            'category',
            'amount',
            'description'
        )
        
        df_expenses = pd.DataFrame(list(expenses))
        if not df_expenses.empty:
            df_expenses = df_expenses.rename(columns={
                'expense_no': '报销单号',
                'user__username': '报销人',
                'expense_date': '日期',
                'category': '类别',
                'amount': '金额',
                'description': '说明'
            })
        
        return {
            'materials': df_materials.to_dict('records') if not df_materials.empty else [],
            'labor': df_labor.to_dict('records') if not df_labor.empty else [],
            'expenses': df_expenses.to_dict('records') if not df_expenses.empty else [],
            'summary': cls.calculate_project_profit(project_id)
        }
    
    @classmethod
    def clear_project_cache(cls, project_id):
        """Clear cached calculations for a project."""
        cache_key = f'project_profit_{project_id}'
        try:
            cache.delete(cache_key)
        except Exception as e:
            logger.warning(f"Failed to clear cache: {e}")

