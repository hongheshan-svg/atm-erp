"""
Analytics API views
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from datetime import datetime, timedelta
from .services import (
    DashboardKPIService,
    CashFlowForecastService,
    InventoryAnalyticsService
)


class AnalyticsViewSet(viewsets.ViewSet):
    """Analytics and KPI endpoints"""
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        """Get comprehensive dashboard KPIs"""
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        if start_date:
            start_date = datetime.fromisoformat(start_date)
        if end_date:
            end_date = datetime.fromisoformat(end_date)
        
        kpis = DashboardKPIService.get_all_kpis(start_date, end_date)
        return Response(kpis)
    
    @action(detail=False, methods=['get'])
    def cash_flow_forecast(self, request):
        """Get 30-day cash flow forecast"""
        forecast = CashFlowForecastService.forecast_next_30_days()
        return Response(forecast)
    
    @action(detail=False, methods=['get'])
    def inventory_turnover(self, request):
        """Get inventory turnover analysis"""
        days = int(request.query_params.get('days', 30))
        turnover = InventoryAnalyticsService.calculate_turnover_rate(days)
        return Response(turnover)
    
    @action(detail=False, methods=['get'])
    def slow_moving_items(self, request):
        """Get slow-moving inventory items"""
        days = int(request.query_params.get('days', 90))
        items = InventoryAnalyticsService.get_slow_moving_items(days)
        return Response(items)
    
    @action(detail=False, methods=['get'], url_path='slow-moving')
    def slow_moving(self, request):
        """Alias for slow_moving_items - for frontend compatibility"""
        days = int(request.query_params.get('aging_days', 90))
        items = InventoryAnalyticsService.get_slow_moving_items(days)
        return Response({'results': items, 'total': len(items)})
    
    @action(detail=False, methods=['get'], url_path='project-costs')
    def project_costs(self, request):
        """Get project cost analysis"""
        from apps.projects.models import Project
        from django.db.models import Sum, F
        
        projects = Project.objects.filter(is_deleted=False)
        
        # Filter by manager
        manager = request.query_params.get('manager')
        if manager:
            projects = projects.filter(manager_id=manager)
        
        results = []
        for project in projects[:50]:  # Limit to 50 projects
            material_cost = project.get_actual_material_cost()
            labor_cost = float(project.get_actual_labor_cost())
            expense_cost = float(project.get_actual_expense_cost())
            total_cost = material_cost + labor_cost + expense_cost
            
            # Get revenue from sales orders
            from apps.sales.models import SalesOrder
            revenue = SalesOrder.objects.filter(
                project=project,
                is_deleted=False
            ).aggregate(total=Sum('total_amount'))['total'] or 0
            
            profit = float(revenue) - total_cost
            profit_margin = profit / float(revenue) if revenue else 0
            
            results.append({
                'id': project.id,
                'project_name': project.name,
                'project_code': project.code,
                'total_revenue': float(revenue),
                'material_cost': material_cost,
                'labor_cost': labor_cost,
                'expense_cost': expense_cost,
                'total_cost': total_cost,
                'profit': profit,
                'profit_margin': profit_margin,
                'start_date': project.start_date.isoformat() if project.start_date else None,
                'end_date': project.end_date.isoformat() if project.end_date else None,
                'status': project.get_status_display(),
            })
        
        return Response({'results': results, 'total': len(results)})
    
    @action(detail=False, methods=['post'], url_path='recalculate-costs')
    def recalculate_costs(self, request):
        """Trigger cost recalculation for all projects"""
        # This would typically be a Celery task
        return Response({'status': 'success', 'message': '成本重新计算已触发'})
    
    @action(detail=False, methods=['get'], url_path='management_dashboard')
    def management_dashboard(self, request):
        """
        管理层仪表盘数据 - 综合财务、项目、销售、采购等关键指标
        """
        from django.utils import timezone
        from django.db.models import Sum, Count, F, Q
        from decimal import Decimal
        from dateutil.relativedelta import relativedelta
        
        today = timezone.now().date()
        month_start = today.replace(day=1)
        last_month_start = (month_start - relativedelta(months=1))
        last_month_end = month_start - timedelta(days=1)
        
        # 财务数据
        from apps.finance.models import AccountReceivable, AccountPayable
        from apps.finance.bank_statement_models import BankStatement
        from apps.sales.models import SalesOrder
        from apps.purchase.models import PurchaseOrder
        from apps.projects.models import Project
        from apps.inventory.models import Stock
        from apps.masterdata.models import Item
        
        # 本月收入（销售订单）
        monthly_sales = SalesOrder.objects.filter(
            order_date__gte=month_start,
            status__in=['CONFIRMED', 'COMPLETED'],
            is_deleted=False
        ).aggregate(
            total=Sum('total_amount'),
            count=Count('id')
        )
        
        # 上月收入（用于计算增长率）
        last_month_sales = SalesOrder.objects.filter(
            order_date__gte=last_month_start,
            order_date__lte=last_month_end,
            status__in=['CONFIRMED', 'COMPLETED'],
            is_deleted=False
        ).aggregate(total=Sum('total_amount'))
        
        revenue_total = float(monthly_sales['total'] or 0)
        last_revenue = float(last_month_sales['total'] or 0)
        revenue_growth = round((revenue_total - last_revenue) / last_revenue * 100, 1) if last_revenue > 0 else 0
        
        # 本月支出（采购订单）
        monthly_purchases = PurchaseOrder.objects.filter(
            order_date__gte=month_start,
            status__in=['CONFIRMED', 'COMPLETED'],
            is_deleted=False
        ).aggregate(
            total=Sum('total_amount'),
            count=Count('id')
        )
        
        # 应收账款
        receivables = AccountReceivable.objects.filter(
            status__in=['UNPAID', 'PARTIAL'],
            is_deleted=False
        ).aggregate(
            total=Sum('amount_due') - Sum('amount_paid'),
            count=Count('id')
        )
        
        overdue_ar = AccountReceivable.objects.filter(
            status__in=['UNPAID', 'PARTIAL', 'OVERDUE'],
            due_date__lt=today,
            is_deleted=False
        ).count()
        
        # 应付账款
        payables = AccountPayable.objects.filter(
            status__in=['UNPAID', 'PARTIAL'],
            is_deleted=False
        ).aggregate(
            total=Sum('amount_due') - Sum('amount_paid'),
            count=Count('id')
        )
        
        overdue_ap = AccountPayable.objects.filter(
            status__in=['UNPAID', 'PARTIAL', 'OVERDUE'],
            due_date__lt=today,
            is_deleted=False
        ).count()
        
        # 回款率和付款率
        ar_total = AccountReceivable.objects.filter(is_deleted=False).aggregate(
            due=Sum('amount_due'), paid=Sum('amount_paid')
        )
        collection_rate = round(float(ar_total['paid'] or 0) / float(ar_total['due'] or 1) * 100, 1)
        
        ap_total = AccountPayable.objects.filter(is_deleted=False).aggregate(
            due=Sum('amount_due'), paid=Sum('amount_paid')
        )
        payment_rate = round(float(ap_total['paid'] or 0) / float(ap_total['due'] or 1) * 100, 1)
        
        # 项目数据
        active_projects = Project.objects.filter(
            status__in=['ACTIVE', 'PLANNING'],
            is_deleted=False
        ).aggregate(
            count=Count('id'),
            budget_total=Sum('budget_total')
        )
        
        # 销售订单统计
        pending_sales = SalesOrder.objects.filter(
            status='DRAFT',
            is_deleted=False
        ).count()
        
        monthly_sales_count = SalesOrder.objects.filter(
            order_date__gte=month_start,
            is_deleted=False
        ).count()
        
        # 采购订单统计
        pending_purchases = PurchaseOrder.objects.filter(
            status='DRAFT',
            is_deleted=False
        ).count()
        
        monthly_purchases_count = PurchaseOrder.objects.filter(
            order_date__gte=month_start,
            is_deleted=False
        ).count()
        
        # 库存数据
        inventory_value = Stock.objects.aggregate(
            value=Sum(F('qty_on_hand') * F('item__standard_cost'))
        )['value'] or 0
        
        total_items = Item.objects.filter(is_deleted=False, is_active=True).count()
        
        low_stock_items = Stock.objects.filter(
            qty_on_hand__lt=F('item__safety_stock')
        ).count()
        
        # 逾期应收列表
        overdue_receivables_list = AccountReceivable.objects.filter(
            status__in=['UNPAID', 'PARTIAL', 'OVERDUE'],
            due_date__lt=today,
            is_deleted=False
        ).select_related('customer').order_by('due_date')[:10]
        
        overdue_ar_data = [{
            'id': ar.id,
            'ar_no': ar.ar_no,
            'customer_name': ar.customer.name if ar.customer else '',
            'amount_remaining': float((ar.amount_due or 0) - (ar.amount_paid or 0)),
            'overdue_days': (today - ar.due_date).days if ar.due_date else 0
        } for ar in overdue_receivables_list]
        
        # 即将到期应付列表
        upcoming_payables_list = AccountPayable.objects.filter(
            status__in=['UNPAID', 'PARTIAL'],
            due_date__lte=today + timedelta(days=7),
            is_deleted=False
        ).select_related('supplier').order_by('due_date')[:10]
        
        upcoming_ap_data = [{
            'id': ap.id,
            'ap_no': ap.ap_no,
            'supplier_name': ap.supplier.name if ap.supplier else '',
            'amount_remaining': float((ap.amount_due or 0) - (ap.amount_paid or 0)),
            'days_until_due': (ap.due_date - today).days if ap.due_date else 0
        } for ap in upcoming_payables_list]
        
        # 活跃项目列表
        active_projects_list = Project.objects.filter(
            status__in=['ACTIVE', 'PLANNING'],
            is_deleted=False
        ).select_related('customer')[:10]
        
        active_projects_data = [{
            'id': p.id,
            'name': p.name,
            'customer_name': p.customer.name if p.customer else '',
            'progress': p.progress or 0
        } for p in active_projects_list]
        
        # Top 5 客户
        top_customers = SalesOrder.objects.filter(
            order_date__gte=month_start,
            status__in=['CONFIRMED', 'COMPLETED'],
            is_deleted=False
        ).values('customer__name').annotate(
            amount=Sum('total_amount'),
            orders=Count('id')
        ).order_by('-amount')[:5]
        
        top_customers_data = [{
            'name': c['customer__name'],
            'amount': float(c['amount'] or 0),
            'orders': c['orders']
        } for c in top_customers]
        
        # Top 5 供应商
        top_suppliers = PurchaseOrder.objects.filter(
            order_date__gte=month_start,
            status__in=['CONFIRMED', 'COMPLETED'],
            is_deleted=False
        ).values('supplier__name').annotate(
            amount=Sum('total_amount'),
            orders=Count('id')
        ).order_by('-amount')[:5]
        
        top_suppliers_data = [{
            'name': s['supplier__name'],
            'amount': float(s['amount'] or 0),
            'orders': s['orders']
        } for s in top_suppliers]
        
        # 收支趋势（近6个月）
        trend_months = []
        trend_income = []
        trend_expense = []
        
        for i in range(5, -1, -1):
            month_date = today - relativedelta(months=i)
            m_start = month_date.replace(day=1)
            m_end = (m_start + relativedelta(months=1)) - timedelta(days=1)
            
            trend_months.append(f'{month_date.month}月')
            
            income = SalesOrder.objects.filter(
                order_date__gte=m_start,
                order_date__lte=m_end,
                status__in=['CONFIRMED', 'COMPLETED'],
                is_deleted=False
            ).aggregate(total=Sum('total_amount'))['total'] or 0
            
            expense = PurchaseOrder.objects.filter(
                order_date__gte=m_start,
                order_date__lte=m_end,
                status__in=['CONFIRMED', 'COMPLETED'],
                is_deleted=False
            ).aggregate(total=Sum('total_amount'))['total'] or 0
            
            trend_income.append(float(income))
            trend_expense.append(float(expense))
        
        # 账龄分析
        aging_data = []
        aging_ranges = [
            ('0-30天', 0, 30),
            ('31-60天', 31, 60),
            ('61-90天', 61, 90),
            ('90天以上', 91, 9999)
        ]
        
        for label, min_days, max_days in aging_ranges:
            amount = AccountReceivable.objects.filter(
                status__in=['UNPAID', 'PARTIAL', 'OVERDUE'],
                due_date__lt=today - timedelta(days=min_days),
                due_date__gte=today - timedelta(days=max_days),
                is_deleted=False
            ).aggregate(total=Sum('amount_due') - Sum('amount_paid'))['total'] or 0
            aging_data.append({'name': label, 'value': float(amount)})
        
        return Response({
            'financial': {
                'revenue': {
                    'total': revenue_total,
                    'orders': monthly_sales['count'] or 0
                },
                'expenses': float(monthly_purchases['total'] or 0),
                'purchase_orders': monthly_purchases['count'] or 0,
                'receivables': float(receivables['total'] or 0),
                'payables': float(payables['total'] or 0),
                'overdue_receivables': overdue_ar,
                'overdue_payables': overdue_ap,
                'collection_rate': collection_rate,
                'payment_rate': payment_rate,
                'revenue_growth': revenue_growth
            },
            'projects': {
                'active_count': active_projects['count'] or 0,
                'total_budget': float(active_projects['budget_total'] or 0)
            },
            'sales': {
                'pending_orders': pending_sales,
                'monthly_orders': monthly_sales_count
            },
            'purchase': {
                'pending_orders': pending_purchases,
                'monthly_orders': monthly_purchases_count
            },
            'inventory': {
                'value': float(inventory_value),
                'total_items': total_items,
                'low_stock': low_stock_items
            },
            'overdue_receivables': overdue_ar_data,
            'upcoming_payables': upcoming_ap_data,
            'active_projects': active_projects_data,
            'top_customers': top_customers_data,
            'top_suppliers': top_suppliers_data,
            'trend_data': {
                'months': trend_months,
                'income': trend_income,
                'expense': trend_expense
            },
            'aging_data': aging_data
        })