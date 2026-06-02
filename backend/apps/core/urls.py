from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import export_views, health_views, views
from .announcement import AnnouncementViewSet
from .audit_analytics import AuditLogAnalyticsView, AuditLogSecurityView, UserActivityView
from .backup_service import BackupCleanupView, BackupCreateView, BackupDeleteView, BackupListView, BackupRestoreView
from .custom_fields import CustomFieldDefinitionViewSet, CustomFieldValueViewSet
from .dashboard_api import (
    ExecutiveDashboardView,
    FinanceDashboardView,
    ProductionDashboardView,
    ProjectManagerDashboardView,
    SalesDashboardView,
)
from .dashboard_views import DashboardWidgetViewSet, UserDashboardViewSet
from .data_dict import DictItemViewSet, DictTypeViewSet
from .email_templates import EmailLogViewSet, EmailTemplateViewSet
from .file_preview import FileListView, FilePreviewView, FileUploadView
from .import_export_views import (
    BOMExportView,
    CustomerExportView,
    ItemExportView,
    ItemImportView,
    SupplierExportView,
    SupplierImportView,
)
from .import_templates import ImportTemplateDownloadView, ImportTemplateListView
from .mobile_api import (
    MobileApprovalViewSet,
    MobileDashboardView,
    MobileNotificationViewSet,
    MobilePhotoViewSet,
    MobileQuickActionsView,
    MobileScanRecordViewSet,
    MobileTimeEntryViewSet,
)
from .permission_views import DataScopeViewSet, PermissionViewSet
from .print_service import BatchPrintView, PrintTemplateListView, PrintView
from .schedule import MeetingRoomViewSet, MeetingViewSet, ScheduleViewSet
from .search_views import GlobalSearchViewSet
from .security_views import LoginLogViewSet, PasswordPolicyViewSet, SensitiveOperationLogViewSet
from .webhook_views import WebhookDeliveryViewSet, WebhookEndpointViewSet

router = DefaultRouter()
router.register(r'audit-logs', views.AuditLogViewSet, basename='audit-log')
router.register(r'notifications', views.NotificationViewSet, basename='notification')
router.register(r'attachments', views.AttachmentViewSet, basename='attachment')
router.register(r'search', GlobalSearchViewSet, basename='search')
router.register(r'notification-channels', views.NotificationChannelViewSet, basename='notification-channel')

# Security
router.register(r'login-logs', LoginLogViewSet, basename='login-log')
router.register(r'sensitive-operations', SensitiveOperationLogViewSet, basename='sensitive-operation')
router.register(r'password-policy', PasswordPolicyViewSet, basename='password-policy')

# Webhooks
router.register(r'webhooks', WebhookEndpointViewSet, basename='webhook')
router.register(r'webhook-deliveries', WebhookDeliveryViewSet, basename='webhook-delivery')

# Dashboard
router.register(r'dashboard-widgets', DashboardWidgetViewSet, basename='dashboard-widget')
router.register(r'user-dashboard', UserDashboardViewSet, basename='user-dashboard')

# Code Rules
from .code_rule_views import CodeHistoryViewSet, CodeRuleViewSet

router.register(r'code-rules', CodeRuleViewSet, basename='code-rule')
router.register(r'code-history', CodeHistoryViewSet, basename='code-history')

# System Config
router.register(r'system-config', views.SystemConfigViewSet, basename='system-config')

# Data Dictionary
router.register(r'dict-types', DictTypeViewSet, basename='dict-type')
router.register(r'dict-items', DictItemViewSet, basename='dict-item')

# Email Templates
router.register(r'email-templates', EmailTemplateViewSet, basename='email-template')
router.register(r'email-logs', EmailLogViewSet, basename='email-log')

# Custom Fields
router.register(r'custom-field-definitions', CustomFieldDefinitionViewSet, basename='custom-field-definition')
router.register(r'custom-field-values', CustomFieldValueViewSet, basename='custom-field-value')

# Announcements
router.register(r'announcements', AnnouncementViewSet, basename='announcement')

# OA - 日程会议
router.register(r'schedules', ScheduleViewSet, basename='schedule')
router.register(r'meetings', MeetingViewSet, basename='meeting')
router.register(r'meeting-rooms', MeetingRoomViewSet, basename='meeting-room')

# 移动端API
router.register(r'mobile/time-entries', MobileTimeEntryViewSet, basename='mobile-time-entry')
router.register(r'mobile/photos', MobilePhotoViewSet, basename='mobile-photo')
router.register(r'mobile/scan-records', MobileScanRecordViewSet, basename='mobile-scan-record')
router.register(r'mobile/approvals', MobileApprovalViewSet, basename='mobile-approval')
router.register(r'mobile/notifications', MobileNotificationViewSet, basename='mobile-notification')

# 权限管理
router.register(r'permissions', PermissionViewSet, basename='permission')
router.register(r'data-scopes', DataScopeViewSet, basename='data-scope')

urlpatterns = [
    path('', include(router.urls)),
    path('workflow/', include('apps.core.workflow.urls')),
    # Export endpoints
    path('export/projects/', export_views.export_projects, name='export-projects'),
    path('export/sales-orders/', export_views.export_sales_orders, name='export-sales-orders'),
    path('export/purchase-orders/', export_views.export_purchase_orders, name='export-purchase-orders'),
    path('export/stock/', export_views.export_stock, name='export-stock'),
    path('export/expenses/', export_views.export_expenses, name='export-expenses'),
    path('export/ar/', export_views.export_ar, name='export-ar'),
    path('export/ap/', export_views.export_ap, name='export-ap'),
    path('export/project-profit/', export_views.export_project_profit_report, name='export-project-profit'),
    # Health check endpoints
    path('health/', health_views.health_check, name='health-check'),
    path('health/ready/', health_views.readiness_check, name='readiness-check'),
    path('health/status/', health_views.system_status, name='system-status'),
    path('health/security/', health_views.security_status, name='security-status'),
    # Dashboard API endpoints
    path('dashboards/executive/', ExecutiveDashboardView.as_view(), name='dashboard-executive'),
    path('dashboards/project-manager/', ProjectManagerDashboardView.as_view(), name='dashboard-pm'),
    path('dashboards/sales/', SalesDashboardView.as_view(), name='dashboard-sales'),
    path('dashboards/production/', ProductionDashboardView.as_view(), name='dashboard-production'),
    path('dashboards/finance/', FinanceDashboardView.as_view(), name='dashboard-finance'),
    # Import/Export endpoints
    path('import/items/', ItemImportView.as_view(), name='import-items'),
    path('export/items/', ItemExportView.as_view(), name='export-items'),
    path('import/suppliers/', SupplierImportView.as_view(), name='import-suppliers'),
    path('export/suppliers/', SupplierExportView.as_view(), name='export-suppliers'),
    path('export/customers/', CustomerExportView.as_view(), name='export-customers'),
    path('export/bom/', BOMExportView.as_view(), name='export-bom'),
    # Print endpoints
    path('print/templates/', PrintTemplateListView.as_view(), name='print-templates'),
    path('print/<str:template_name>/<int:pk>/', PrintView.as_view(), name='print-preview'),
    path('print/<str:template_name>/batch/', BatchPrintView.as_view(), name='batch-print'),
    # Backup endpoints
    path('backups/', BackupListView.as_view(), name='backup-list'),
    path('backups/create/', BackupCreateView.as_view(), name='backup-create'),
    path('backups/restore/', BackupRestoreView.as_view(), name='backup-restore'),
    path('backups/cleanup/', BackupCleanupView.as_view(), name='backup-cleanup'),
    path('backups/<str:backup_name>/', BackupDeleteView.as_view(), name='backup-delete'),
    # Audit analytics endpoints
    path('audit-analytics/', AuditLogAnalyticsView.as_view(), name='audit-analytics'),
    path('audit-analytics/security/', AuditLogSecurityView.as_view(), name='audit-security'),
    path('audit-analytics/user-activity/', UserActivityView.as_view(), name='user-activity'),
    # Import template endpoints
    path('import-templates/', ImportTemplateListView.as_view(), name='import-template-list'),
    path(
        'import-templates/<str:template_type>/download/',
        ImportTemplateDownloadView.as_view(),
        name='import-template-download',
    ),
    # File preview endpoints
    path('files/preview/', FilePreviewView.as_view(), name='file-preview'),
    path('files/upload/', FileUploadView.as_view(), name='file-upload'),
    path('files/list/', FileListView.as_view(), name='file-list'),
    # 移动端API
    path('mobile/dashboard/', MobileDashboardView.as_view(), name='mobile-dashboard'),
    path('mobile/quick-actions/', MobileQuickActionsView.as_view(), name='mobile-quick-actions'),
]
