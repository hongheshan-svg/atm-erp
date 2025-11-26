"""
Utility functions for the core app.
"""
import random
import string
from datetime import datetime


def generate_code(prefix, length=8):
    """
    Generate a unique code with prefix.
    Example: PR20240101001, SO20240101001
    """
    date_str = datetime.now().strftime('%Y%m%d')
    random_str = ''.join(random.choices(string.digits, k=length - len(date_str)))
    return f"{prefix}{date_str}{random_str}"


def apply_data_scope_filter(queryset, user, field_name='created_by'):
    """
    Apply data scope filtering to a queryset based on user's role.
    
    Args:
        queryset: Django queryset to filter
        user: User making the request
        field_name: Name of the field that links to the user (default: 'created_by')
    
    Returns:
        Filtered queryset
    """
    # Superuser sees everything
    if user.is_superuser:
        return queryset
    
    # Check if user has a role with data scope
    if not hasattr(user, 'role') or not user.role:
        # No role = no access
        return queryset.none()
    
    data_scope = user.role.data_scope
    
    if data_scope == 'ALL':
        return queryset
    elif data_scope == 'DEPARTMENT' and user.department:
        # Filter by department
        filter_kwargs = {f'{field_name}__department': user.department}
        return queryset.filter(**filter_kwargs)
    elif data_scope == 'SELF':
        # Filter by user
        filter_kwargs = {field_name: user}
        return queryset.filter(**filter_kwargs)
    
    return queryset.none()

