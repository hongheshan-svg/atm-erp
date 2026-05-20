"""
URL configuration for projects app.
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .acceptance import AcceptanceCheckItemViewSet, AcceptanceIssueViewSet, AcceptanceTemplateViewSet, AcceptanceViewSet
from .advanced_cost_tracking import (
    CostComparisonReportView,
    CostElementReportView,
    CostVarianceAnalysisViewSet,
    LaborRateStandardViewSet,
    ProjectCostAnalysisDashboardView,
    ProjectCostDetailViewSet,
    ProjectCostSummaryViewSet,
    StandardCostCategoryViewSet,
)
from .bom_advanced import BOMCompareView, BOMComparisonViewSet, BOMSubstituteViewSet, BOMVersionViewSet
from .bom_compare import BOMCompareViewSet, BOMSnapshotViewSet
from .bom_cost_rollup import BOMCostDetailViewSet, BOMCostSnapshotViewSet
from .bom_integration import BOMIntegrationViewSet
from .bug_views import BugAttachmentViewSet, BugCommentViewSet, BugViewSet
from .cad_integration import (
    CADBOMImportViewSet,
    CADFileViewSet,
    CADPropertyMappingViewSet,
    CADSessionViewSet,
    CADSoftwareViewSet,
)
from .cost_tracking import (
    CostAlertViewSet,
    CostOverviewDashboardView,
    ProjectBudgetViewSet,
    ProjectCostDashboardView,
    ProjectCostRecordViewSet,
)
from .creo_integration import CreoBOMImportViewSet
from .dashboard import (
    BOMCostRollupView,
    DeliveryTrackingView,
    ProcurementTrackingView,
    ProductionProgressView,
    ProjectDashboardView,
    ProjectListDashboardView,
)
from .document import DocumentCategoryViewSet, DocumentShareViewSet, ProjectDocumentViewSet
from .document_collaboration import (
    DocumentAnnotationViewSet,
    DocumentReviewViewSet,
    TechDocumentCategoryViewSet,
    TechnicalDocumentViewSet,
)
from .drawing_import import DrawingImportViewSet
from .drawing_version import DrawingAffectedPartViewSet, DrawingVersionViewSet
from .equipment_archive import (
    EquipmentArchiveViewSet,
    EquipmentMaintenancePlanViewSet,
    EquipmentMaintenanceRecordViewSet,
    EquipmentSparePartViewSet,
)
from .equipment_inspection import (
    InspectionItemViewSet,
    InspectionRecordViewSet,
    InspectionResultViewSet,
    InspectionTemplateViewSet,
)
from .equipment_oee import DowntimeReasonViewSet, EquipmentOEERecordViewSet, EquipmentShiftViewSet
from .equipment_views import (
    EquipmentAcceptanceViewSet,
    EquipmentInstallationViewSet,
    EquipmentShipmentViewSet,
    EquipmentViewSet,
    FixtureCalibrationViewSet,
    FixtureCategoryViewSet,
    FixtureMaintenanceViewSet,
    FixtureUsageRecordViewSet,
    FixtureViewSet,
    InstallationLogViewSet,
    MaintenanceScheduleViewSet,
    TrainingRecordViewSet,
)
from .field_service import (
    ServiceCheckInViewSet,
    ServiceDispatchViewSet,
    ServiceExpenseViewSet,
    ServiceLogViewSet,
    ServiceOrderViewSet,
    SkillCategoryViewSet,
    SkillViewSet,
    TechnicianProfileViewSet,
    TechnicianScheduleViewSet,
    TechnicianSkillViewSet,
)
from .installation import (
    CommissioningRecordViewSet,
    CustomerAcceptanceViewSet,
    InstallationTaskViewSet,
    SiteIssueViewSet,
    SiteLogViewSet,
)
from .knowledge_views import (
    KnowledgeArticleViewSet,
    KnowledgeCategoryViewSet,
    ProjectArchiveViewSet,
    StandardComponentViewSet,
    TechnicalIssueViewSet,
)
from .maintenance_calendar import EquipmentMaintenanceHistoryView, MaintenanceCalendarView, MaintenanceStatisticsView
from .maintenance_views import MaintenanceReminderView
from .milestone import MilestoneChecklistViewSet, MilestoneViewSet
from .progress_alert import ProjectAlertRuleViewSet, ProjectAlertViewSet
from .proposal import ProposalCategoryViewSet, ProposalDocumentViewSet, ProposalReviewViewSet, TechnicalProposalViewSet
from .remote_monitoring import (
    DiagnosticSessionViewSet,
    EquipmentAlarmViewSet,
    EquipmentConnectionViewSet,
    EquipmentDataPointViewSet,
    EquipmentDataRecordViewSet,
    EquipmentMonitoringDashboardView,
    PredictiveMaintenanceResultViewSet,
)
from .requirement import RequirementCategoryViewSet, RequirementChangeViewSet, RequirementViewSet
from .requirement_review import RequirementReviewViewSet, ReviewActionItemViewSet, ReviewTemplateViewSet
from .technical_agreement import (
    TechnicalAgreementChangeViewSet,
    TechnicalAgreementTemplateViewSet,
    TechnicalAgreementViewSet,
)
from .views import (
    AfterSalesOrderViewSet,
    DrawingChangeNoticeViewSet,
    DrawingViewSet,
    ECNItemViewSet,
    ECNViewSet,
    ProjectBOMViewSet,
    ProjectMemberViewSet,
    ProjectTaskViewSet,
    ProjectViewSet,
    ServiceRecordViewSet,
    SparePartUsageViewSet,
    TimeLogViewSet,
)
from .work_dispatch import WorkDispatchViewSet, WorkLogViewSet, WorkOrderViewSet

router = DefaultRouter()
router.register(r'projects', ProjectViewSet, basename='project')
router.register(r'members', ProjectMemberViewSet, basename='member')
router.register(r'tasks', ProjectTaskViewSet, basename='task')
router.register(r'bom', ProjectBOMViewSet, basename='bom')
router.register(r'time-logs', TimeLogViewSet, basename='time-log')
router.register(r'ecn', ECNViewSet, basename='ecn')
router.register(r'ecn-items', ECNItemViewSet, basename='ecn-item')

# 售后管理
router.register(r'aftersales', AfterSalesOrderViewSet, basename='aftersales')
router.register(r'service-records', ServiceRecordViewSet, basename='service-record')
router.register(r'spare-parts', SparePartUsageViewSet, basename='spare-part')

# Bug跟踪
router.register(r'bugs', BugViewSet, basename='bug')
router.register(r'bug-comments', BugCommentViewSet, basename='bug-comment')
router.register(r'bug-attachments', BugAttachmentViewSet, basename='bug-attachment')

# 图纸管理
router.register(r'drawings', DrawingViewSet, basename='drawing')
router.register(r'drawing-notices', DrawingChangeNoticeViewSet, basename='drawing-notice')
router.register(r'drawing-import', DrawingImportViewSet, basename='drawing-import')

# 设备台账管理
router.register(r'equipment', EquipmentViewSet, basename='equipment')
router.register(r'equipment-shipments', EquipmentShipmentViewSet, basename='equipment-shipment')
router.register(r'equipment-installations', EquipmentInstallationViewSet, basename='equipment-installation')
router.register(r'installation-logs', InstallationLogViewSet, basename='installation-log')
router.register(r'equipment-acceptances', EquipmentAcceptanceViewSet, basename='equipment-acceptance')
router.register(r'maintenance-schedules', MaintenanceScheduleViewSet, basename='maintenance-schedule')
router.register(r'training-records', TrainingRecordViewSet, basename='training-record')

# 工装夹具管理
router.register(r'fixture-categories', FixtureCategoryViewSet, basename='fixture-category')
router.register(r'fixtures', FixtureViewSet, basename='fixture')
router.register(r'fixture-usages', FixtureUsageRecordViewSet, basename='fixture-usage')
router.register(r'fixture-calibrations', FixtureCalibrationViewSet, basename='fixture-calibration')
router.register(r'fixture-maintenances', FixtureMaintenanceViewSet, basename='fixture-maintenance')

# 知识库管理
router.register(r'knowledge-categories', KnowledgeCategoryViewSet, basename='knowledge-category')
router.register(r'knowledge-articles', KnowledgeArticleViewSet, basename='knowledge-article')
router.register(r'project-archives', ProjectArchiveViewSet, basename='project-archive')
router.register(r'technical-issues', TechnicalIssueViewSet, basename='technical-issue')
router.register(r'standard-components', StandardComponentViewSet, basename='standard-component')

# 维保提醒
router.register(r'maintenance-reminders', MaintenanceReminderView, basename='maintenance-reminder')

# 项目里程碑
router.register(r'milestones', MilestoneViewSet, basename='milestone')
router.register(r'milestone-checklists', MilestoneChecklistViewSet, basename='milestone-checklist')

# 工单派工
router.register(r'work-orders', WorkOrderViewSet, basename='work-order')
router.register(r'work-dispatches', WorkDispatchViewSet, basename='work-dispatch')
router.register(r'work-logs', WorkLogViewSet, basename='work-log')

# 设备点检
router.register(r'inspection-templates', InspectionTemplateViewSet, basename='inspection-template')
router.register(r'inspection-items', InspectionItemViewSet, basename='inspection-item')
router.register(r'inspection-records', InspectionRecordViewSet, basename='inspection-record')
router.register(r'inspection-results', InspectionResultViewSet, basename='inspection-result')

# 项目文档管理
router.register(r'document-categories', DocumentCategoryViewSet, basename='document-category')
router.register(r'documents', ProjectDocumentViewSet, basename='document')
router.register(r'document-shares', DocumentShareViewSet, basename='document-share')

# 设备OEE
router.register(r'equipment-shifts', EquipmentShiftViewSet, basename='equipment-shift')
router.register(r'downtime-reasons', DowntimeReasonViewSet, basename='downtime-reason')
router.register(r'oee-records', EquipmentOEERecordViewSet, basename='oee-record')

# 项目预警
router.register(r'alert-rules', ProjectAlertRuleViewSet, basename='alert-rule')
router.register(r'alerts', ProjectAlertViewSet, basename='alert')

# PLM - 需求管理
router.register(r'requirement-categories', RequirementCategoryViewSet, basename='requirement-category')
router.register(r'requirements', RequirementViewSet, basename='requirement')
router.register(r'requirement-changes', RequirementChangeViewSet, basename='requirement-change')

# PLM - 方案设计
router.register(r'proposal-categories', ProposalCategoryViewSet, basename='proposal-category')
router.register(r'proposals', TechnicalProposalViewSet, basename='proposal')
router.register(r'proposal-reviews', ProposalReviewViewSet, basename='proposal-review')
router.register(r'proposal-documents', ProposalDocumentViewSet, basename='proposal-document')

# PLM - 需求评审
router.register(r'review-templates', ReviewTemplateViewSet, basename='review-template')
router.register(r'requirement-reviews', RequirementReviewViewSet, basename='requirement-review')
router.register(r'review-action-items', ReviewActionItemViewSet, basename='review-action-item')

# PLM - BOM高级功能
router.register(r'bom-substitutes', BOMSubstituteViewSet, basename='bom-substitute')
router.register(r'bom-versions', BOMVersionViewSet, basename='bom-version')
router.register(r'bom-comparisons', BOMComparisonViewSet, basename='bom-comparison')

# PLM - CAD集成
router.register(r'cad-software', CADSoftwareViewSet, basename='cad-software')
router.register(r'cad-sessions', CADSessionViewSet, basename='cad-session')
router.register(r'cad-files', CADFileViewSet, basename='cad-file')
router.register(r'cad-bom-imports', CADBOMImportViewSet, basename='cad-bom-import')
router.register(r'cad-property-mappings', CADPropertyMappingViewSet, basename='cad-property-mapping')

# CREO BOM导入
router.register(r'creo-bom-imports', CreoBOMImportViewSet, basename='creo-bom-import')

# BOM版本对比与快照
router.register(r'bom-compare', BOMCompareViewSet, basename='bom-compare')
router.register(r'bom-snapshots', BOMSnapshotViewSet, basename='bom-snapshot')

# BOM集成(采购/生产)
router.register(r'bom-integration', BOMIntegrationViewSet, basename='bom-integration')

# 技术协议管理
router.register(r'agreement-templates', TechnicalAgreementTemplateViewSet, basename='agreement-template')
router.register(r'agreements', TechnicalAgreementViewSet, basename='agreement')
router.register(r'agreement-changes', TechnicalAgreementChangeViewSet, basename='agreement-change')

# 设备档案管理
router.register(r'equipment-archives', EquipmentArchiveViewSet, basename='equipment-archive')
router.register(r'archive-maintenance-plans', EquipmentMaintenancePlanViewSet, basename='archive-maintenance-plan')
router.register(r'archive-maintenance-records', EquipmentMaintenanceRecordViewSet, basename='archive-maintenance-record')
router.register(r'archive-spare-parts', EquipmentSparePartViewSet, basename='archive-spare-part')

# FAT/SAT验收管理
router.register(r'acceptance-templates', AcceptanceTemplateViewSet, basename='acceptance-template')
router.register(r'acceptances', AcceptanceViewSet, basename='acceptance')
router.register(r'acceptance-items', AcceptanceCheckItemViewSet, basename='acceptance-item')
router.register(r'acceptance-issues', AcceptanceIssueViewSet, basename='acceptance-issue')

# 现场服务派工管理
router.register(r'skill-categories', SkillCategoryViewSet, basename='skill-category')
router.register(r'skills', SkillViewSet, basename='skill')
router.register(r'technician-profiles', TechnicianProfileViewSet, basename='technician-profile')
router.register(r'technician-skills', TechnicianSkillViewSet, basename='technician-skill')
router.register(r'service-orders', ServiceOrderViewSet, basename='service-order')
router.register(r'service-dispatches', ServiceDispatchViewSet, basename='service-dispatch')
router.register(r'service-checkins', ServiceCheckInViewSet, basename='service-checkin')
router.register(r'service-logs', ServiceLogViewSet, basename='service-log')
router.register(r'service-expenses', ServiceExpenseViewSet, basename='service-expense')
router.register(r'technician-schedules', TechnicianScheduleViewSet, basename='technician-schedule')

# 项目成本跟踪
router.register(r'project-budgets', ProjectBudgetViewSet, basename='project-budget')
router.register(r'project-cost-records', ProjectCostRecordViewSet, basename='project-cost-record')
router.register(r'cost-alerts', CostAlertViewSet, basename='cost-alert')

# 设备远程运维
router.register(r'equipment-data-points', EquipmentDataPointViewSet, basename='equipment-data-point')
router.register(r'equipment-connections', EquipmentConnectionViewSet, basename='equipment-connection')
router.register(r'equipment-data-records', EquipmentDataRecordViewSet, basename='equipment-data-record')
router.register(r'equipment-alarms', EquipmentAlarmViewSet, basename='equipment-alarm')
router.register(r'diagnostic-sessions', DiagnosticSessionViewSet, basename='diagnostic-session')
router.register(r'pm-results', PredictiveMaintenanceResultViewSet, basename='pm-result')

# 高级成本核算（非标自动化增强）
router.register(r'cost-categories', StandardCostCategoryViewSet, basename='cost-category')
router.register(r'labor-rates', LaborRateStandardViewSet, basename='labor-rate')
router.register(r'cost-details', ProjectCostDetailViewSet, basename='cost-detail')
router.register(r'cost-summaries', ProjectCostSummaryViewSet, basename='cost-summary')
router.register(r'variance-analyses', CostVarianceAnalysisViewSet, basename='variance-analysis')

# 技术文档协同
router.register(r'tech-doc-categories', TechDocumentCategoryViewSet, basename='tech-doc-category')
router.register(r'tech-documents', TechnicalDocumentViewSet, basename='tech-document')
router.register(r'doc-annotations', DocumentAnnotationViewSet, basename='doc-annotation')
router.register(r'doc-reviews', DocumentReviewViewSet, basename='doc-review')

# BOM多层级成本卷积
router.register(r'bom-cost-snapshots', BOMCostSnapshotViewSet, basename='bom-cost-snapshot')
router.register(r'bom-cost-details', BOMCostDetailViewSet, basename='bom-cost-detail')

# 图纸版本管理
router.register(r'drawing-versions', DrawingVersionViewSet, basename='drawing-version')
router.register(r'drawing-affected-parts', DrawingAffectedPartViewSet, basename='drawing-affected-part')

# 安装调试现场管理
router.register(r'installation-tasks', InstallationTaskViewSet, basename='installation-task')
router.register(r'site-logs', SiteLogViewSet, basename='site-log')
router.register(r'commissioning-records', CommissioningRecordViewSet, basename='commissioning-record')
router.register(r'site-issues', SiteIssueViewSet, basename='site-issue')
router.register(r'customer-acceptances', CustomerAcceptanceViewSet, basename='customer-acceptance')

urlpatterns = [
    path('', include(router.urls)),

    # 设备维护日历
    path('maintenance/calendar/', MaintenanceCalendarView.as_view(), name='maintenance-calendar'),
    path('maintenance/statistics/', MaintenanceStatisticsView.as_view(), name='maintenance-statistics'),
    path('maintenance/history/<int:equipment_id>/', EquipmentMaintenanceHistoryView.as_view(), name='maintenance-history'),

    # BOM对比
    path('bom/compare/', BOMCompareView.as_view(), name='bom-compare'),

    # 项目仪表盘增强
    path('dashboard/<int:project_id>/', ProjectDashboardView.as_view(), name='project-dashboard'),
    path('dashboard/overview/', ProjectListDashboardView.as_view(), name='project-list-dashboard'),
    path('dashboard/<int:project_id>/bom-cost/', BOMCostRollupView.as_view(), name='bom-cost-rollup'),

    # 业务跟踪仪表盘
    path('tracking/delivery/', DeliveryTrackingView.as_view(), name='delivery-tracking'),
    path('tracking/procurement/', ProcurementTrackingView.as_view(), name='procurement-tracking'),
    path('tracking/production/', ProductionProgressView.as_view(), name='production-progress'),

    # 项目成本看板
    path('cost/dashboard/<int:project_id>/', ProjectCostDashboardView.as_view(), name='project-cost-dashboard'),
    path('cost/overview/', CostOverviewDashboardView.as_view(), name='cost-overview-dashboard'),

    # 设备监控看板
    path('monitoring/dashboard/', EquipmentMonitoringDashboardView.as_view(), name='equipment-monitoring-dashboard'),

    # 高级成本分析报表
    path('cost/analysis/<int:project_id>/', ProjectCostAnalysisDashboardView.as_view(), name='project-cost-analysis'),
    path('cost/comparison/', CostComparisonReportView.as_view(), name='cost-comparison-report'),
    path('cost/elements/', CostElementReportView.as_view(), name='cost-element-report'),
]
