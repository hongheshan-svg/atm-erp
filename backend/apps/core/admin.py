"""
Admin configuration for core app.
"""

from django.contrib import admin

from .dashboard_config import DashboardWidget, UserDashboard
from .models import Attachment, AuditLog, SystemNotification
from .security import LoginLog, SensitiveOperationLog
from .webhook import WebhookDelivery, WebhookEndpoint


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'user', 'action', 'model_name', 'object_repr', 'ip_address']
    list_filter = ['action', 'model_name', 'timestamp']
    search_fields = ['user__username', 'object_repr', 'ip_address']
    readonly_fields = [
        'user',
        'action',
        'model_name',
        'object_id',
        'object_repr',
        'changes',
        'ip_address',
        'user_agent',
        'timestamp',
    ]
    date_hierarchy = 'timestamp'


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = [
        'original_name',
        'related_model',
        'related_id',
        'category',
        'file_size',
        'uploaded_by',
        'uploaded_at',
    ]
    list_filter = ['category', 'related_model', 'uploaded_at']
    search_fields = ['original_name', 'description']


@admin.register(SystemNotification)
class SystemNotificationAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'type', 'is_read', 'created_at']
    list_filter = ['type', 'is_read', 'created_at']
    search_fields = ['title', 'message', 'user__username']


@admin.register(LoginLog)
class LoginLogAdmin(admin.ModelAdmin):
    list_display = ['login_time', 'username', 'status', 'ip_address', 'device_type', 'location']
    list_filter = ['status', 'device_type', 'login_time']
    search_fields = ['username', 'ip_address']
    readonly_fields = [
        'user',
        'username',
        'ip_address',
        'user_agent',
        'status',
        'failure_reason',
        'login_time',
        'location',
        'device_type',
    ]
    date_hierarchy = 'login_time'


@admin.register(SensitiveOperationLog)
class SensitiveOperationLogAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'user', 'operation_type', 'target_model', 'target_desc', 'confirmed']
    list_filter = ['operation_type', 'confirmed', 'created_at']
    search_fields = ['target_desc', 'user__username']
    readonly_fields = ['user', 'operation_type', 'target_model', 'target_id', 'target_desc', 'ip_address', 'created_at']


@admin.register(WebhookEndpoint)
class WebhookEndpointAdmin(admin.ModelAdmin):
    list_display = ['name', 'url', 'is_active', 'max_retries', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'url']


@admin.register(WebhookDelivery)
class WebhookDeliveryAdmin(admin.ModelAdmin):
    list_display = ['endpoint', 'event_type', 'status', 'attempts', 'response_status', 'created_at', 'delivered_at']
    list_filter = ['status', 'event_type', 'created_at']
    search_fields = ['endpoint__name', 'event_type']
    readonly_fields = [
        'endpoint',
        'event_type',
        'payload',
        'status',
        'response_status',
        'response_body',
        'error_message',
        'attempts',
        'next_retry_at',
        'created_at',
        'delivered_at',
    ]


@admin.register(DashboardWidget)
class DashboardWidgetAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'widget_type', 'data_source', 'is_active', 'is_system', 'created_at']
    list_filter = ['widget_type', 'data_source', 'is_active', 'is_system']
    search_fields = ['name', 'code']


@admin.register(UserDashboard)
class UserDashboardAdmin(admin.ModelAdmin):
    list_display = ['user', 'theme', 'created_at', 'updated_at']
    search_fields = ['user__username']
