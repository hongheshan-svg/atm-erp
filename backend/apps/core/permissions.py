"""
Custom permission classes for data scope filtering.
"""

from rest_framework import permissions

from apps.core.permission_service import get_department_tree_ids, resolve_data_scope


class DataScopePermission(permissions.BasePermission):
    """
    Permission class that enforces data scope via DataScope records.
    """

    def has_permission(self, request, view):
        # Authenticated users always have permission at the view level
        # The actual filtering happens in the queryset
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        user = request.user

        # Superuser can access everything
        if user.is_superuser:
            return True

        module_name = getattr(view, 'permission_module', None) or obj._meta.app_label
        scope_type, custom_dept_ids = resolve_data_scope(user, module_name)

        if scope_type == 'all':
            return True

        if scope_type == 'self':
            if hasattr(obj, 'created_by'):
                return obj.created_by == user
            return hasattr(obj, 'user') and obj.user == user

        if scope_type == 'dept':
            if hasattr(obj, 'department') and user.department:
                return obj.department_id == user.department.id
            if hasattr(obj, 'created_by') and obj.created_by and user.department:
                return obj.created_by.department_id == user.department.id
            if hasattr(obj, 'user') and obj.user and user.department:
                return obj.user.department_id == user.department.id
            return False

        if scope_type in {'dept_tree', 'custom'}:
            if scope_type == 'dept_tree' and user.department:
                allowed_dept_ids = set(get_department_tree_ids(user.department.id))
            else:
                allowed_dept_ids = set(custom_dept_ids)

            if hasattr(obj, 'department') and obj.department_id:
                return obj.department_id in allowed_dept_ids
            if hasattr(obj, 'created_by') and obj.created_by and obj.created_by.department_id:
                return obj.created_by.department_id in allowed_dept_ids
            if hasattr(obj, 'user') and obj.user and obj.user.department_id:
                return obj.user.department_id in allowed_dept_ids
            return False

        return False
