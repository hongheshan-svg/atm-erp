"""
Configurable dashboard components and widgets.
"""

from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class DashboardWidget(models.Model):
    """
    Dashboard widget definition.
    """

    WIDGET_TYPES = [
        ('stat_card', '统计卡片'),
        ('line_chart', '折线图'),
        ('bar_chart', '柱状图'),
        ('pie_chart', '饼图'),
        ('table', '数据表格'),
        ('progress', '进度条'),
        ('list', '列表'),
        ('gauge', '仪表盘'),
    ]

    DATA_SOURCES = [
        ('project_stats', '项目统计'),
        ('sales_stats', '销售统计'),
        ('purchase_stats', '采购统计'),
        ('inventory_stats', '库存统计'),
        ('finance_stats', '财务统计'),
        ('ar_aging', '应收账龄'),
        ('ap_aging', '应付账龄'),
        ('cash_flow', '现金流'),
        ('project_profit', '项目利润'),
        ('inventory_turnover', '库存周转'),
        ('custom_sql', '自定义SQL'),
        ('api_endpoint', 'API接口'),
    ]

    name = models.CharField(max_length=100, verbose_name='组件名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='组件编码')
    widget_type = models.CharField(max_length=30, choices=WIDGET_TYPES, verbose_name='组件类型')
    data_source = models.CharField(max_length=30, choices=DATA_SOURCES, verbose_name='数据源')

    # Configuration
    config = models.JSONField(default=dict, verbose_name='配置')
    # Example config:
    # {
    #   "title": "本月销售额",
    #   "icon": "money",
    #   "color": "#1890ff",
    #   "unit": "元",
    #   "compare_period": "last_month",
    #   "filters": {"status": "COMPLETED"}
    # }

    # For custom SQL
    custom_query = models.TextField(blank=True, verbose_name='自定义查询')

    # Display settings
    default_width = models.IntegerField(default=6, verbose_name='默认宽度(1-12)')
    default_height = models.IntegerField(default=200, verbose_name='默认高度(px)')
    refresh_interval = models.IntegerField(default=300, verbose_name='刷新间隔(秒)')

    is_active = models.BooleanField(default=True, verbose_name='启用')
    is_system = models.BooleanField(default=False, verbose_name='系统组件')

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'dashboard_widget'
        verbose_name = '仪表盘组件'
        verbose_name_plural = verbose_name
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.get_widget_type_display()})'


class UserDashboard(models.Model):
    """
    User's personalized dashboard configuration.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='dashboard', verbose_name='用户'
    )

    # Layout configuration
    layout = models.JSONField(default=list, verbose_name='布局配置')
    # Example layout:
    # [
    #   {"widget": "sales_total", "x": 0, "y": 0, "w": 3, "h": 1},
    #   {"widget": "project_count", "x": 3, "y": 0, "w": 3, "h": 1},
    #   {"widget": "sales_chart", "x": 0, "y": 1, "w": 6, "h": 2},
    # ]

    # Theme settings
    theme = models.CharField(max_length=20, default='light', verbose_name='主题')

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'user_dashboard'
        verbose_name = '用户仪表盘'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.user.username}'s Dashboard"


class DashboardDataService:
    """
    Service for fetching dashboard widget data.
    """

    @classmethod
    def get_widget_data(cls, widget, params=None):
        """
        Get data for a dashboard widget.

        Args:
            widget: DashboardWidget instance
            params: Optional query parameters

        Returns:
            dict with widget data
        """
        params = params or {}
        data_source = widget.data_source
        config = widget.config or {}

        # Merge config filters with params
        filters = {**config.get('filters', {}), **params}

        # Get date range
        date_range = cls._get_date_range(params.get('period', 'month'))

        method_map = {
            'project_stats': cls._get_project_stats,
            'sales_stats': cls._get_sales_stats,
            'purchase_stats': cls._get_purchase_stats,
            'inventory_stats': cls._get_inventory_stats,
            'finance_stats': cls._get_finance_stats,
            'ar_aging': cls._get_ar_aging,
            'ap_aging': cls._get_ap_aging,
            'cash_flow': cls._get_cash_flow,
            'project_profit': cls._get_project_profit,
            'inventory_turnover': cls._get_inventory_turnover,
        }

        if data_source in method_map:
            return method_map[data_source](date_range, filters, config)
        elif data_source == 'custom_sql' and widget.custom_query:
            return cls._execute_custom_query(widget.custom_query, params)

        return {'error': 'Unknown data source'}

    @classmethod
    def _get_date_range(cls, period):
        """Get date range for period."""
        today = timezone.now().date()

        if period == 'today':
            return today, today
        elif period == 'week':
            start = today - timedelta(days=today.weekday())
            return start, today
        elif period == 'month':
            start = today.replace(day=1)
            return start, today
        elif period == 'quarter':
            quarter_start_month = ((today.month - 1) // 3) * 3 + 1
            start = today.replace(month=quarter_start_month, day=1)
            return start, today
        elif period == 'year':
            start = today.replace(month=1, day=1)
            return start, today
        else:
            # Default to last 30 days
            return today - timedelta(days=30), today

    @classmethod
    def _get_project_stats(cls, date_range, filters, config):
        """Get project statistics."""
        from django.db.models import Count, Sum

        from apps.projects.models import Project

        queryset = Project.objects.filter(is_deleted=False)

        stats = queryset.aggregate(
            total=Count('id'),
            active=Count('id', filter=models.Q(status='ACTIVE')),
            completed=Count('id', filter=models.Q(status='COMPLETED')),
            total_budget=Sum('budget_total'),
        )

        return {
            'total': stats['total'] or 0,
            'active': stats['active'] or 0,
            'completed': stats['completed'] or 0,
            'total_budget': float(stats['total_budget'] or 0),
        }

    @classmethod
    def _get_sales_stats(cls, date_range, filters, config):
        """Get sales statistics."""
        from django.db.models import Count, Sum

        from apps.sales.models import SalesOrder

        start_date, end_date = date_range

        queryset = SalesOrder.objects.filter(order_date__range=[start_date, end_date], is_deleted=False)

        stats = queryset.aggregate(
            total_orders=Count('id'),
            total_amount=Sum('total_amount'),
            confirmed=Count('id', filter=models.Q(status='CONFIRMED')),
            completed=Count('id', filter=models.Q(status='COMPLETED')),
        )

        # Get trend data
        trend = list(
            queryset.values('order_date').annotate(amount=Sum('total_amount'), count=Count('id')).order_by('order_date')
        )

        return {
            'total_orders': stats['total_orders'] or 0,
            'total_amount': float(stats['total_amount'] or 0),
            'confirmed': stats['confirmed'] or 0,
            'completed': stats['completed'] or 0,
            'trend': trend,
        }

    @classmethod
    def _get_purchase_stats(cls, date_range, filters, config):
        """Get purchase statistics."""
        from django.db.models import Count, Sum

        from apps.purchase.models import PurchaseOrder

        start_date, end_date = date_range

        queryset = PurchaseOrder.objects.filter(order_date__range=[start_date, end_date], is_deleted=False)

        stats = queryset.aggregate(total_orders=Count('id'), total_amount=Sum('total_amount'))

        return {
            'total_orders': stats['total_orders'] or 0,
            'total_amount': float(stats['total_amount'] or 0),
        }

    @classmethod
    def _get_inventory_stats(cls, date_range, filters, config):
        """Get inventory statistics."""
        from django.db.models import Count, F, Sum

        from apps.inventory.models import Stock

        stats = Stock.objects.aggregate(
            total_value=Sum(F('qty_on_hand') * F('weighted_avg_cost')), total_items=Count('id')
        )

        # Low stock count
        low_stock = Stock.objects.filter(qty_on_hand__lt=F('item__min_stock'), item__min_stock__gt=0).count()

        return {
            'total_value': float(stats['total_value'] or 0),
            'total_items': stats['total_items'] or 0,
            'low_stock_count': low_stock,
        }

    @classmethod
    def _get_finance_stats(cls, date_range, filters, config):
        """Get finance statistics."""
        from django.db.models import F, Sum

        from apps.finance.models import AccountPayable, AccountReceivable

        ar_stats = AccountReceivable.objects.filter(status__in=['PENDING', 'PARTIAL'], is_deleted=False).aggregate(
            total=Sum(F('amount_due') - F('amount_paid'))
        )

        ap_stats = AccountPayable.objects.filter(status__in=['PENDING', 'PARTIAL'], is_deleted=False).aggregate(
            total=Sum(F('amount_due') - F('amount_paid'))
        )

        return {
            'receivables': float(ar_stats['total'] or 0),
            'payables': float(ap_stats['total'] or 0),
            'net_position': float((ar_stats['total'] or 0) - (ap_stats['total'] or 0)),
        }

    @classmethod
    def _get_ar_aging(cls, date_range, filters, config):
        """Get AR aging analysis."""
        from apps.finance.models import AccountReceivable

        today = timezone.now().date()
        ars = AccountReceivable.objects.filter(status__in=['PENDING', 'PARTIAL'], is_deleted=False)

        aging = {
            'current': 0,
            '1_30': 0,
            '31_60': 0,
            '61_90': 0,
            'over_90': 0,
        }

        for ar in ars:
            days = (today - ar.due_date).days
            amount = float(ar.amount_due - ar.amount_paid)

            if days <= 0:
                aging['current'] += amount
            elif days <= 30:
                aging['1_30'] += amount
            elif days <= 60:
                aging['31_60'] += amount
            elif days <= 90:
                aging['61_90'] += amount
            else:
                aging['over_90'] += amount

        return aging

    @classmethod
    def _get_ap_aging(cls, date_range, filters, config):
        """Get AP aging analysis."""
        from apps.finance.models import AccountPayable

        today = timezone.now().date()
        aps = AccountPayable.objects.filter(status__in=['PENDING', 'PARTIAL'], is_deleted=False)

        aging = {
            'current': 0,
            '1_30': 0,
            '31_60': 0,
            '61_90': 0,
            'over_90': 0,
        }

        for ap in aps:
            days = (today - ap.due_date).days
            amount = float(ap.amount_due - ap.amount_paid)

            if days <= 0:
                aging['current'] += amount
            elif days <= 30:
                aging['1_30'] += amount
            elif days <= 60:
                aging['31_60'] += amount
            elif days <= 90:
                aging['61_90'] += amount
            else:
                aging['over_90'] += amount

        return aging

    @classmethod
    def _get_cash_flow(cls, date_range, filters, config):
        """Get cash flow forecast."""
        from apps.analytics.services import CashFlowForecastService

        return CashFlowForecastService.forecast_next_30_days()

    @classmethod
    def _get_project_profit(cls, date_range, filters, config):
        """Get project profitability."""
        from apps.reports.services.cost_service import CostCalculationService

        df = CostCalculationService.calculate_all_projects_profit(status='ACTIVE')

        if df.empty:
            return {'projects': []}

        return {
            'projects': df.to_dict('records'),
            'total_revenue': df['revenue'].sum(),
            'total_cost': df['total_cost'].sum(),
            'total_profit': df['profit'].sum(),
        }

    @classmethod
    def _get_inventory_turnover(cls, date_range, filters, config):
        """Get inventory turnover analysis."""
        from apps.analytics.services import InventoryAnalyticsService

        return InventoryAnalyticsService.calculate_turnover_rate(days=30)

    @classmethod
    def _execute_custom_query(cls, query, params):
        """Execute custom SQL query (read-only) with strict security validation."""
        import re

        from django.db import connection

        query_stripped = query.strip()
        query_upper = query_stripped.upper()

        # Security: Only allow SELECT queries
        if not query_upper.startswith('SELECT'):
            return {'error': 'Only SELECT queries are allowed'}

        # Security: Block dangerous SQL keywords
        dangerous_patterns = [
            r'\bINSERT\b',
            r'\bUPDATE\b',
            r'\bDELETE\b',
            r'\bDROP\b',
            r'\bCREATE\b',
            r'\bALTER\b',
            r'\bTRUNCATE\b',
            r'\bGRANT\b',
            r'\bREVOKE\b',
            r'\bEXEC\b',
            r'\bEXECUTE\b',
            r'\bUNION\b',
            r'INTO\s+OUTFILE',
            r'LOAD_FILE',
            r'INTO\s+DUMPFILE',
            r'INFORMATION_SCHEMA',
            r'PG_CATALOG',
            r'PG_SHADOW',
        ]

        for pattern in dangerous_patterns:
            if re.search(pattern, query_upper):
                return {'error': 'Query contains forbidden keywords'}

        # Security: Block SQL comments and multiple statements
        if '--' in query_stripped or '/*' in query_stripped or ';' in query_stripped[:-1]:
            return {'error': 'Query contains forbidden characters'}

        # Security: Limit query complexity
        if query_upper.count('SELECT') > 3:
            return {'error': 'Query too complex (max 3 subqueries)'}

        # Security: Limit result size
        if 'LIMIT' not in query_upper:
            query_stripped = query_stripped.rstrip(';') + ' LIMIT 1000'

        try:
            with connection.cursor() as cursor:
                cursor.execute(query_stripped, params)
                columns = [col[0] for col in cursor.description]
                rows = cursor.fetchall()

                return {'columns': columns, 'data': [dict(zip(columns, row, strict=False)) for row in rows]}
        except Exception:
            # Don't expose detailed error messages
            return {'error': 'Query execution failed'}
