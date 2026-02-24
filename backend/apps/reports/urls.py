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
from .industry_reports import (
    ProjectProfitabilityReportView, EquipmentLifecycleReportView,
    CapacityUtilizationReportView, CustomerValueReportView,
    ProjectDeliveryReportView, OutsourceAnalysisReportView
)

router = DefaultRouter()
router.register(r'export-templates', ExportTemplateViewSet, basename='export-template')
router.register(r'export-history', ExportHistoryViewSet, basename='export-history')
router.register(r'scheduled-exports', ScheduledExportViewSet, basename='scheduled-export')

urlpatterns = [
    path('profitability/', views.project_profitability, name='project-profitability'),
    path('cost-detail/', views.project_cost_detail, name='project-cost-detail'),
    path('refresh-cache/', views.refresh_project_cache, name='refresh-cache'),
    path('dashboard/', views.dashboard_summary, name='dashboard-summary'),
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
    
    # 非标自动化行业专用报表
    path('industry/project-profitability/', ProjectProfitabilityReportView.as_view(), name='project-profitability-report'),
    path('industry/equipment-lifecycle/', EquipmentLifecycleReportView.as_view(), name='equipment-lifecycle-report'),
    path('industry/capacity-utilization/', CapacityUtilizationReportView.as_view(), name='capacity-utilization-report'),
    path('industry/customer-value/', CustomerValueReportView.as_view(), name='customer-value-report'),
    path('industry/project-delivery/', ProjectDeliveryReportView.as_view(), name='project-delivery-report'),
    path('industry/outsource-analysis/', OutsourceAnalysisReportView.as_view(), name='outsource-analysis-report'),
]

