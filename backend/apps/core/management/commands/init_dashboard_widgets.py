"""
Initialize default dashboard widgets.
"""
from django.core.management.base import BaseCommand

from apps.core.dashboard_config import DashboardWidget


class Command(BaseCommand):
    help = 'Initialize default dashboard widgets'

    def handle(self, *args, **options):
        widgets = [
            {
                'name': '项目统计',
                'code': 'project_stats',
                'widget_type': 'stat_card',
                'data_source': 'project_stats',
                'config': {
                    'title': '项目概览',
                    'icon': 'project',
                    'color': '#1890ff',
                    'metrics': ['total', 'active', 'completed']
                },
                'default_width': 3,
                'default_height': 150,
                'is_system': True,
            },
            {
                'name': '销售统计',
                'code': 'sales_stats',
                'widget_type': 'stat_card',
                'data_source': 'sales_stats',
                'config': {
                    'title': '本月销售',
                    'icon': 'shopping-cart',
                    'color': '#52c41a',
                    'unit': '元'
                },
                'default_width': 3,
                'default_height': 150,
                'is_system': True,
            },
            {
                'name': '库存统计',
                'code': 'inventory_stats',
                'widget_type': 'stat_card',
                'data_source': 'inventory_stats',
                'config': {
                    'title': '库存概览',
                    'icon': 'database',
                    'color': '#faad14',
                },
                'default_width': 3,
                'default_height': 150,
                'is_system': True,
            },
            {
                'name': '财务统计',
                'code': 'finance_stats',
                'widget_type': 'stat_card',
                'data_source': 'finance_stats',
                'config': {
                    'title': '财务概览',
                    'icon': 'dollar',
                    'color': '#722ed1',
                },
                'default_width': 3,
                'default_height': 150,
                'is_system': True,
            },
            {
                'name': '销售趋势图',
                'code': 'sales_chart',
                'widget_type': 'line_chart',
                'data_source': 'sales_stats',
                'config': {
                    'title': '销售趋势',
                    'x_field': 'order_date',
                    'y_field': 'amount',
                },
                'default_width': 6,
                'default_height': 300,
                'is_system': True,
            },
            {
                'name': '应收账龄分析',
                'code': 'ar_aging',
                'widget_type': 'bar_chart',
                'data_source': 'ar_aging',
                'config': {
                    'title': '应收账龄分析',
                    'colors': ['#52c41a', '#1890ff', '#faad14', '#fa8c16', '#f5222d'],
                },
                'default_width': 6,
                'default_height': 300,
                'is_system': True,
            },
            {
                'name': '应付账龄分析',
                'code': 'ap_aging',
                'widget_type': 'bar_chart',
                'data_source': 'ap_aging',
                'config': {
                    'title': '应付账龄分析',
                    'colors': ['#52c41a', '#1890ff', '#faad14', '#fa8c16', '#f5222d'],
                },
                'default_width': 6,
                'default_height': 300,
                'is_system': True,
            },
            {
                'name': '项目利润排行',
                'code': 'project_profit',
                'widget_type': 'table',
                'data_source': 'project_profit',
                'config': {
                    'title': '项目利润排行',
                    'columns': ['project_name', 'revenue', 'cost', 'profit', 'margin'],
                    'limit': 10,
                },
                'default_width': 12,
                'default_height': 400,
                'is_system': True,
            },
            {
                'name': '现金流预测',
                'code': 'cash_flow',
                'widget_type': 'line_chart',
                'data_source': 'cash_flow',
                'config': {
                    'title': '30天现金流预测',
                },
                'default_width': 6,
                'default_height': 300,
                'is_system': True,
            },
            {
                'name': '库存周转率',
                'code': 'inventory_turnover',
                'widget_type': 'gauge',
                'data_source': 'inventory_turnover',
                'config': {
                    'title': '库存周转率',
                    'unit': '次/月',
                },
                'default_width': 3,
                'default_height': 200,
                'is_system': True,
            },
        ]

        created_count = 0
        updated_count = 0

        for widget_data in widgets:
            widget, created = DashboardWidget.objects.update_or_create(
                code=widget_data['code'],
                defaults=widget_data
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Dashboard widgets initialized: {created_count} created, {updated_count} updated'
            )
        )
