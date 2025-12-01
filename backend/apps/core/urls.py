from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .search_views import GlobalSearchViewSet
from . import export_views
from .security_views import LoginLogViewSet, SensitiveOperationLogViewSet, PasswordPolicyViewSet
from .webhook_views import WebhookEndpointViewSet, WebhookDeliveryViewSet
from .dashboard_views import DashboardWidgetViewSet, UserDashboardViewSet
from . import health_views

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
]

