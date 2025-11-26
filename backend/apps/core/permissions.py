"""
Custom permission classes for data scope filtering.
"""
from rest_framework import permissions


class DataScopePermission(permissions.BasePermission):
    """
    Permission class that enforces data scope based on user's role.
    - SELF: User can only see their own data
    - DEPARTMENT: User can see their department's data
    - ALL: User can see all data
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
        
        # Get user's data scope from role
        if not hasattr(user, 'role') or not user.role:
            return False
        
        data_scope = user.role.data_scope
        
        if data_scope == 'ALL':
            return True
        elif data_scope == 'DEPARTMENT':
            # Check if object belongs to same department
            if hasattr(obj, 'created_by') and obj.created_by:
                return obj.created_by.department == user.department
            return True
        elif data_scope == 'SELF':
            # Check if user created this object
            if hasattr(obj, 'created_by'):
                return obj.created_by == user
            return True
        
        return False

