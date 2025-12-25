"""
Utility functions for the core app.
"""
import random
import string
from datetime import datetime


def generate_code(prefix, length=8, rule_type=None):
    """
    Generate unique code with prefix and timestamp + random suffix.
    如果指定了rule_type，则使用编码规则生成；否则使用默认规则。
    
    Args:
        prefix: 前缀（仅在无编码规则时使用）
        length: 长度（仅在无编码规则时使用）
        rule_type: 编码规则类型（如：'PROJECT', 'ITEM'等）
    
    Returns:
        生成的编码
    """
    # 如果指定了规则类型，尝试使用编码规则
    if rule_type:
        try:
            from apps.core.code_rule_models import CodeRule, CodeHistory
            
            # 查找活动的编码规则
            rule = CodeRule.objects.filter(rule_type=rule_type, is_active=True).first()
            if rule:
                code = rule.generate_code()
                
                # 记录历史（可选）
                try:
                    CodeHistory.objects.create(
                        rule=rule,
                        generated_code=code,
                        sequence_number=rule.current_seq
                    )
                except:
                    pass  # 历史记录失败不影响编码生成
                
                return code
        except Exception as e:
            # 编码规则不可用时，使用默认规则
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f'使用编码规则失败，回退到默认规则: {e}')
    
    # 默认规则：前缀 + 日期 + 时间戳后缀 + 随机后缀
    date_str = datetime.now().strftime('%Y%m%d')
    import time
    timestamp_suffix = str(int(time.time() * 1000))[-4:]
    random_suffix = ''.join(random.choices(string.digits, k=2))
    return f"{prefix}{date_str}{timestamp_suffix}{random_suffix}"


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

