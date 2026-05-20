from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Department, Role, User


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'parent', 'manager', 'sort_order', 'is_deleted']
    list_filter = ['is_deleted', 'created_at']
    search_fields = ['code', 'name']
    ordering = ['sort_order', 'code']


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'data_scope', 'is_active', 'sort_order', 'is_deleted']
    list_filter = ['data_scope', 'is_active', 'is_deleted']
    search_fields = ['code', 'name']
    ordering = ['sort_order', 'code']


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['username', 'employee_id', 'email', 'department', 'role', 'is_active', 'is_staff']
    list_filter = ['is_active', 'is_staff', 'is_superuser', 'department', 'role']
    search_fields = ['username', 'employee_id', 'email', 'first_name', 'last_name']
    ordering = ['-date_joined']

    fieldsets = BaseUserAdmin.fieldsets + (
        (
            '扩展信息',
            {
                'fields': (
                    'employee_id',
                    'phone',
                    'avatar',
                    'gender',
                    'birth_date',
                    'department',
                    'role',
                    'position',
                    'hire_date',
                )
            },
        ),
        ('软删除', {'fields': ('is_deleted', 'deleted_at')}),
    )

    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('扩展信息', {'fields': ('employee_id', 'phone', 'department', 'role')}),
    )
