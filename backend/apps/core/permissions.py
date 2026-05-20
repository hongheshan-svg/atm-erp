"""
Custom permission classes for data scope filtering.
"""
from rest_framework import permissions
from apps.core.permission_service import resolve_data_scope, get_department_tree_ids


class DataScopePermission(permissions.BasePermission):
    """
    Permission class for data scope.
    
    当前策略：数据权限不做限制，所有认证用户可访问所有数据。
    权限控制通过菜单访问权限实现。
    """
    
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        # 所有认证用户可访问所有数据对象
        return request.user and request.user.is_authenticated

