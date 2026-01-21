"""
URL configuration for projects app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ProjectViewSet,
    ProjectMemberViewSet,
    ProjectTaskViewSet,
    ProjectBOMViewSet,
    TimeLogViewSet,
    ECNViewSet,
    ECNItemViewSet,
    AfterSalesOrderViewSet,
    ServiceRecordViewSet,
    SparePartUsageViewSet,
    DrawingViewSet,
    DrawingChangeNoticeViewSet
)
from .bug_views import BugViewSet, BugCommentViewSet, BugAttachmentViewSet
from .equipment_views import (
    EquipmentViewSet, EquipmentShipmentViewSet, EquipmentInstallationViewSet,
    InstallationLogViewSet, EquipmentAcceptanceViewSet, MaintenanceScheduleViewSet,
    TrainingRecordViewSet, FixtureCategoryViewSet, FixtureViewSet,
    FixtureUsageRecordViewSet, FixtureCalibrationViewSet, FixtureMaintenanceViewSet
)
from .knowledge_views import (
    KnowledgeCategoryViewSet, KnowledgeArticleViewSet, ProjectArchiveViewSet,
    TechnicalIssueViewSet, StandardComponentViewSet
)
from .maintenance_views import MaintenanceReminderView
from .milestone import MilestoneViewSet, MilestoneChecklistViewSet
from .work_dispatch import WorkOrderViewSet, WorkDispatchViewSet, WorkLogViewSet
from .equipment_inspection import (
    InspectionTemplateViewSet, InspectionItemViewSet,
    InspectionRecordViewSet, InspectionResultViewSet
)
from .document import DocumentCategoryViewSet, ProjectDocumentViewSet, DocumentShareViewSet
from .equipment_oee import EquipmentShiftViewSet, DowntimeReasonViewSet, EquipmentOEERecordViewSet
from .progress_alert import ProjectAlertRuleViewSet, ProjectAlertViewSet
from .maintenance_calendar import (
    MaintenanceCalendarView, MaintenanceStatisticsView, EquipmentMaintenanceHistoryView
)
from .requirement import (
    RequirementCategoryViewSet, RequirementViewSet, RequirementChangeViewSet
)
from .proposal import (
    ProposalCategoryViewSet, TechnicalProposalViewSet,
    ProposalReviewViewSet, ProposalDocumentViewSet
)
from .configurator import (
    ProductTemplateViewSet, ConfigParameterViewSet, ParameterOptionViewSet,
    ConfigRuleViewSet, ConfigBOMRuleViewSet, ProductConfigurationViewSet
)
from .requirement_review import (
    ReviewTemplateViewSet, RequirementReviewViewSet, ReviewActionItemViewSet
)
from .bom_advanced import (
    BOMSubstituteViewSet, BOMVersionViewSet, BOMComparisonViewSet, BOMCompareView
)
from .cad_integration import (
    CADSoftwareViewSet, CADSessionViewSet, CADFileViewSet,
    CADBOMImportViewSet, CADPropertyMappingViewSet
)
from .bom_integration import BOMIntegrationViewSet
from .technical_agreement import (
    TechnicalAgreementTemplateViewSet, TechnicalAgreementViewSet, TechnicalAgreementChangeViewSet
)
from .equipment_archive import (
    EquipmentArchiveViewSet, EquipmentMaintenancePlanViewSet,
    EquipmentMaintenanceRecordViewSet, EquipmentSparePartViewSet
)
from .acceptance import (
    AcceptanceTemplateViewSet, AcceptanceViewSet,
    AcceptanceCheckItemViewSet, AcceptanceIssueViewSet
)

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

# PLM - 产品配置器
router.register(r'product-templates', ProductTemplateViewSet, basename='product-template')
router.register(r'config-parameters', ConfigParameterViewSet, basename='config-parameter')
router.register(r'parameter-options', ParameterOptionViewSet, basename='parameter-option')
router.register(r'config-rules', ConfigRuleViewSet, basename='config-rule')
router.register(r'config-bom-rules', ConfigBOMRuleViewSet, basename='config-bom-rule')
router.register(r'product-configurations', ProductConfigurationViewSet, basename='product-configuration')

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

urlpatterns = [
    path('', include(router.urls)),
    
    # 设备维护日历
    path('maintenance/calendar/', MaintenanceCalendarView.as_view(), name='maintenance-calendar'),
    path('maintenance/statistics/', MaintenanceStatisticsView.as_view(), name='maintenance-statistics'),
    path('maintenance/history/<int:equipment_id>/', EquipmentMaintenanceHistoryView.as_view(), name='maintenance-history'),
    
    # BOM对比
    path('bom/compare/', BOMCompareView.as_view(), name='bom-compare'),
]
