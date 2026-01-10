"""
URL configuration for reports app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .timelog_report import (
    TimelogStatisticsView, TimelogByUserView, TimelogByProjectView,
    TimelogWeeklyReportView, TimelogOvertimeView
)
from .cost_analysis import (
    ProjectCostAnalysisView, ProjectCostComparisonView, CostTrendView
)
from .export_service import ExportTemplateViewSet, ExportHistoryViewSet, ScheduledExportViewSet

router = DefaultRouter()
router.register(r'export-templates', ExportTemplateViewSet, basename='export-template')
router.register(r'export-history', ExportHistoryViewSet, basename='export-history')
router.register(r'scheduled-exports', ScheduledExportViewSet, basename='scheduled-export')

urlpatterns = [
    path('profitability/', views.project_profitability, name='project-profitability'),
    path('cost-detail/', views.project_cost_detail, name='project-cost-detail'),
    path('refresh-cache/', views.refresh_project_cache, name='refresh-cache'),
    path('dashboard/', views.dashboard_summary, name='dashboard-summary'),
    path('inventory-turnover/', views.inventory_turnover_report, name='inventory-turnover'),
    path('purchase-price-trend/', views.purchase_price_trend_report, name='purchase-price-trend'),
    path('aging/', views.aging_report, name='aging-report'),
    
    # 工时报表
    path('timelog/statistics/', TimelogStatisticsView.as_view(), name='timelog-statistics'),
    path('timelog/by-user/', TimelogByUserView.as_view(), name='timelog-by-user'),
    path('timelog/by-project/', TimelogByProjectView.as_view(), name='timelog-by-project'),
    path('timelog/weekly/', TimelogWeeklyReportView.as_view(), name='timelog-weekly'),
    path('timelog/overtime/', TimelogOvertimeView.as_view(), name='timelog-overtime'),
    
    # 成本分析报表
    path('cost/analysis/', ProjectCostAnalysisView.as_view(), name='cost-analysis'),
    path('cost/comparison/', ProjectCostComparisonView.as_view(), name='cost-comparison'),
    path('cost/trend/', CostTrendView.as_view(), name='cost-trend'),
    
    # 导出服务
    path('', include(router.urls)),
]

