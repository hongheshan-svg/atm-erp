from django.contrib import admin
from .models import Project, ProjectMember, ProjectTask, ProjectBOM


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'customer', 'manager', 'status', 'start_date', 'end_date', 'is_deleted']
    list_filter = ['status', 'is_deleted', 'created_at']
    search_fields = ['code', 'name']
    ordering = ['-created_at']


@admin.register(ProjectMember)
class ProjectMemberAdmin(admin.ModelAdmin):
    list_display = ['project', 'user', 'role', 'hourly_rate', 'allocated_hours', 'actual_hours', 'is_active']
    list_filter = ['is_active', 'created_at']
    search_fields = ['project__code', 'user__username']
    ordering = ['-created_at']


@admin.register(ProjectTask)
class ProjectTaskAdmin(admin.ModelAdmin):
    list_display = ['project', 'code', 'name', 'assignee', 'status', 'progress_percent', 'is_deleted']
    list_filter = ['status', 'is_deleted', 'created_at']
    search_fields = ['project__code', 'code', 'name']
    ordering = ['project', 'sort_order']


@admin.register(ProjectBOM)
class ProjectBOMAdmin(admin.ModelAdmin):
    list_display = ['project', 'item', 'planned_qty', 'actual_qty', 'estimated_cost', 'is_deleted']
    list_filter = ['is_deleted', 'created_at']
    search_fields = ['project__code', 'item__sku']
    ordering = ['-created_at']

