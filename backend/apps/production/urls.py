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
    ScheduleOrderViewSet, APSScheduleTaskViewSet
)
from .scheduling import WorkCenterViewSet
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
from .sn_traceability import (
    SNRuleViewSet, SerialNumberViewSet, SNTraceRecordViewSet, ComponentBindingViewSet
)
from .routing import (
    WorkStationViewSet, RoutingTemplateViewSet, RoutingOperationViewSet,
    ProjectRoutingViewSet, ProjectRoutingOperationViewSet
)
from .assembly_guide import (
    AssemblyGuideViewSet, AssemblyStepViewSet, AssemblySessionViewSet
)
from .smart_scheduling import (
    SchedulingObjectiveViewSet, SchedulingConstraintViewSet,
    SchedulingScenarioViewSet, ResourceConflictViewSet,
    BottleneckAnalysisViewSet, SchedulingComparisonViewSet
)
from .capacity_planning import (
    ResourceTypeViewSet, ResourceViewSet, ResourceAllocationViewSet,
    CapacityResourceConflictViewSet,
    CapacityDashboardView
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
router.register(r'schedule-tasks', APSScheduleTaskViewSet, basename='schedule-task')

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

# 序列号与批次追溯
router.register(r'sn-rules', SNRuleViewSet, basename='sn-rule')
router.register(r'serial-numbers', SerialNumberViewSet, basename='serial-number')
router.register(r'sn-traces', SNTraceRecordViewSet, basename='sn-trace')
router.register(r'component-bindings', ComponentBindingViewSet, basename='component-binding')

# 工艺路线管理
router.register(r'work-stations', WorkStationViewSet, basename='work-station')
router.register(r'routing-templates', RoutingTemplateViewSet, basename='routing-template')
router.register(r'routing-operations', RoutingOperationViewSet, basename='routing-operation')
router.register(r'project-routings', ProjectRoutingViewSet, basename='project-routing')
router.register(r'project-routing-operations', ProjectRoutingOperationViewSet, basename='project-routing-operation')

# 3D装配指导
router.register(r'assembly-guides', AssemblyGuideViewSet, basename='assembly-guide')
router.register(r'assembly-steps', AssemblyStepViewSet, basename='assembly-step')
router.register(r'assembly-sessions', AssemblySessionViewSet, basename='assembly-session')

# 智能排产优化
router.register(r'scheduling-objectives', SchedulingObjectiveViewSet, basename='scheduling-objective')
router.register(r'scheduling-constraints', SchedulingConstraintViewSet, basename='scheduling-constraint')
router.register(r'scheduling-scenarios', SchedulingScenarioViewSet, basename='scheduling-scenario')
router.register(r'resource-conflicts', ResourceConflictViewSet, basename='resource-conflict')
router.register(r'bottleneck-analyses', BottleneckAnalysisViewSet, basename='bottleneck-analysis')
router.register(r'scheduling-comparisons', SchedulingComparisonViewSet, basename='scheduling-comparison')

# 产能资源规划
router.register(r'resource-types', ResourceTypeViewSet, basename='resource-type')
router.register(r'resources', ResourceViewSet, basename='resource')
router.register(r'resource-allocations', ResourceAllocationViewSet, basename='resource-allocation')
router.register(r'capacity-conflicts', CapacityResourceConflictViewSet, basename='capacity-conflict')

urlpatterns = [
    path('', include(router.urls)),
    
    # 电子看板
    path('kanban/', ProductionKanbanView.as_view(), name='production-kanban'),
    path('kanban/work-center/<int:work_center_id>/', WorkCenterKanbanView.as_view(), name='work-center-kanban'),
    path('kanban/trend/', ProductionTrendView.as_view(), name='production-trend'),
    path('kanban/alerts/', AndonAlertView.as_view(), name='andon-alerts'),
    
    # 追溯搜索
    path('traceability/search/', TraceSearchView.as_view(), name='traceability-search'),
    
    # 产能资源规划看板
    path('capacity/dashboard/', CapacityDashboardView.as_view(), name='capacity-dashboard'),
]
