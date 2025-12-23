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


# 角色模块全访问权限映射
# 键为角色名称关键字，值为该角色可全访问的模块列表
ROLE_MODULE_FULL_ACCESS = {
    '销售': ['sales'],
    '采购': ['purchase'],
    '项目': ['projects', 'sales'],  # 项目经理可查看销售订单
    '财务': ['finance', 'sales', 'purchase'],  # 财务可查看销售和采购
    '仓库': ['inventory'],
    '库存': ['inventory'],
    '生产': ['projects', 'inventory'],
}


def apply_data_scope_filter(queryset, user, field_name='created_by', module_name=None):
    """
    Apply data scope filtering to a queryset based on user's role.
    
    Args:
        queryset: Django queryset to filter
        user: User making the request
        field_name: Name of the field that links to the user (default: 'created_by')
        module_name: Optional module name for module-based access control
    
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
    
    # 检查角色是否对当前模块有全访问权限
    if module_name and user.role:
        role_name = user.role.name or ''
        for keyword, modules in ROLE_MODULE_FULL_ACCESS.items():
            if keyword in role_name and module_name in modules:
                # 该角色对此模块有全访问权限
                return queryset
    
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

