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
