"""
生产管理模块 URL 配置
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ProductionProcessViewSet, ProductionPlanViewSet,
    ProductionPlanProcessViewSet, ProductionLogViewSet,
    DebugRecordViewSet, DebugCheckItemViewSet,
    QualityInspectionViewSet, InspectionItemViewSet
)
from .aps import (
    WorkCenterViewSet, ScheduleOrderViewSet, ScheduleTaskViewSet
)
from .kanban import (
    ProductionKanbanView, WorkCenterKanbanView,
    ProductionTrendView, AndonAlertView
)
from .traceability import (
    ProductBatchViewSet, TraceSearchView
)
from .spc import (
    ControlChartViewSet, SPCDataPointViewSet, SubgroupStatisticsViewSet,
    ProcessCapabilityViewSet, SPCAlarmViewSet
)
from .andon import (
    AndonTypeViewSet, AndonStationViewSet, AndonCallViewSet, AndonActionViewSet
)
from .data_acquisition import (
    DataSourceViewSet, DataPointViewSet, DataRecordViewSet, DataAlarmViewSet
)

router = DefaultRouter()
router.register(r'processes', ProductionProcessViewSet, basename='process')
router.register(r'plans', ProductionPlanViewSet, basename='plan')
router.register(r'plan-processes', ProductionPlanProcessViewSet, basename='plan-process')
router.register(r'logs', ProductionLogViewSet, basename='log')
router.register(r'debug-records', DebugRecordViewSet, basename='debug-record')
router.register(r'debug-check-items', DebugCheckItemViewSet, basename='debug-check-item')
router.register(r'inspections', QualityInspectionViewSet, basename='inspection')
router.register(r'inspection-items', InspectionItemViewSet, basename='inspection-item')

# APS 高级排程
router.register(r'work-centers', WorkCenterViewSet, basename='work-center')
router.register(r'schedule-orders', ScheduleOrderViewSet, basename='schedule-order')
router.register(r'schedule-tasks', ScheduleTaskViewSet, basename='schedule-task')

# 追溯管理
router.register(r'product-lots', ProductBatchViewSet, basename='product-lot')

# SPC 统计过程控制
router.register(r'control-charts', ControlChartViewSet, basename='control-chart')
router.register(r'spc-data-points', SPCDataPointViewSet, basename='spc-data-point')
router.register(r'subgroup-stats', SubgroupStatisticsViewSet, basename='subgroup-stat')
router.register(r'process-capabilities', ProcessCapabilityViewSet, basename='process-capability')
router.register(r'spc-alarms', SPCAlarmViewSet, basename='spc-alarm')

# 安灯系统
router.register(r'andon-types', AndonTypeViewSet, basename='andon-type')
router.register(r'andon-stations', AndonStationViewSet, basename='andon-station')
router.register(r'andon-calls', AndonCallViewSet, basename='andon-call')
router.register(r'andon-actions', AndonActionViewSet, basename='andon-action')

# 数据采集
router.register(r'data-sources', DataSourceViewSet, basename='data-source')
router.register(r'data-points', DataPointViewSet, basename='data-point')
router.register(r'data-records', DataRecordViewSet, basename='data-record')
router.register(r'data-alarms', DataAlarmViewSet, basename='data-alarm')

urlpatterns = [
    path('', include(router.urls)),
    
    # 电子看板
    path('kanban/', ProductionKanbanView.as_view(), name='production-kanban'),
    path('kanban/work-center/<int:work_center_id>/', WorkCenterKanbanView.as_view(), name='work-center-kanban'),
    path('kanban/trend/', ProductionTrendView.as_view(), name='production-trend'),
    path('kanban/alerts/', AndonAlertView.as_view(), name='andon-alerts'),
    
    # 追溯搜索
    path('traceability/search/', TraceSearchView.as_view(), name='traceability-search'),
]
