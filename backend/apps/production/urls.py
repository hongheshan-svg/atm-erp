"""
生产管理模块 URL 配置
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.projects.equipment_oee import EquipmentOEERecordViewSet

from .andon import AndonActionViewSet, AndonCallViewSet, AndonStationViewSet, AndonTypeViewSet
from .aps import APSScheduleTaskViewSet, ScheduleOrderViewSet
from .assembly_guide import AssemblyGuideViewSet, AssemblySessionViewSet, AssemblyStepViewSet
from .capacity_planning import (
    CapacityDashboardView,
    CapacityResourceConflictViewSet,
    ResourceAllocationViewSet,
    ResourceTypeViewSet,
    ResourceViewSet,
)
from .data_acquisition import DataAlarmViewSet, DataPointViewSet, DataRecordViewSet, DataSourceViewSet
from .equipment_capability import EquipmentCapabilityViewSet
from .finite_capacity import FiniteCapacityPlanViewSet, ScheduledTaskViewSet
from .kanban import AndonAlertView, ProductionKanbanView, ProductionTrendView, WorkCenterKanbanView
from .kanban_wip import KanbanWIPAlertViewSet, KanbanWIPRuleViewSet, KanbanWIPStatusView
from .routing import (
    ProjectRoutingOperationViewSet,
    ProjectRoutingViewSet,
    RoutingOperationViewSet,
    RoutingTemplateViewSet,
    WorkStationViewSet,
)
from .scheduling import WorkCenterViewSet
from .sn_traceability import ComponentBindingViewSet, SerialNumberViewSet, SNRuleViewSet, SNTraceRecordViewSet
from .views import (
    DebugCheckItemViewSet,
    DebugRecordViewSet,
    InspectionItemViewSet,
    ProductionLogViewSet,
    ProductionPlanProcessViewSet,
    ProductionPlanViewSet,
    ProductionProcessViewSet,
    QualityInspectionViewSet,
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

# 产能资源规划
router.register(r'resource-types', ResourceTypeViewSet, basename='resource-type')
router.register(r'resources', ResourceViewSet, basename='resource')
router.register(r'resource-allocations', ResourceAllocationViewSet, basename='resource-allocation')
router.register(r'capacity-conflicts', CapacityResourceConflictViewSet, basename='capacity-conflict')

# APS有限产能排程
router.register(r'finite-capacity-plans', FiniteCapacityPlanViewSet, basename='finite-capacity-plan')
router.register(r'scheduled-tasks', ScheduledTaskViewSet, basename='scheduled-task')

# 设备能力矩阵与OEE
router.register(r'equipment-capabilities', EquipmentCapabilityViewSet, basename='equipment-capability')
router.register(r'equipment-oee', EquipmentOEERecordViewSet, basename='equipment-oee')

# 看板WIP限制
router.register(r'kanban-wip-rules', KanbanWIPRuleViewSet, basename='kanban-wip-rule')
router.register(r'kanban-wip-alerts', KanbanWIPAlertViewSet, basename='kanban-wip-alert')

urlpatterns = [
    path('', include(router.urls)),

    # 电子看板
    path('kanban/', ProductionKanbanView.as_view(), name='production-kanban'),
    path('kanban/work-center/<int:work_center_id>/', WorkCenterKanbanView.as_view(), name='work-center-kanban'),
    path('kanban/trend/', ProductionTrendView.as_view(), name='production-trend'),
    path('kanban/alerts/', AndonAlertView.as_view(), name='andon-alerts'),

    # 产能资源规划看板
    path('capacity/dashboard/', CapacityDashboardView.as_view(), name='capacity-dashboard'),

    # 看板WIP状态
    path('kanban/wip-status/', KanbanWIPStatusView.as_view(), name='kanban-wip-status'),
]
