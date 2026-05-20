"""
Utility functions for the core app.
"""

import random
import string
from datetime import datetime

from apps.core.permission_service import get_department_tree_ids, resolve_data_scope


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
            from apps.core.code_rule_models import CodeHistory, CodeRule

            # 查找活动的编码规则
            rule = CodeRule.objects.filter(rule_type=rule_type, is_active=True).first()
            if rule:
                code = rule.generate_code()

                # 记录历史（可选）
                try:
                    CodeHistory.objects.create(rule=rule, generated_code=code, sequence_number=rule.current_seq)
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
    return f'{prefix}{date_str}{timestamp_suffix}{random_suffix}'


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

    if not user or not user.is_authenticated:
        return queryset.none()

    scope_type, custom_dept_ids = resolve_data_scope(user, module_name or queryset.model._meta.app_label)

    if scope_type == 'all':
        return queryset

    if scope_type == 'self':
        filter_kwargs = {field_name: user}
        return queryset.filter(**filter_kwargs)

    if scope_type == 'dept':
        if not user.department:
            return queryset.none()
        filter_kwargs = {f'{field_name}__department': user.department}
        return queryset.filter(**filter_kwargs)

    if scope_type == 'dept_tree':
        if not user.department:
            return queryset.none()
        dept_ids = get_department_tree_ids(user.department.id)
        filter_kwargs = {f'{field_name}__department_id__in': dept_ids}
        return queryset.filter(**filter_kwargs)

    if scope_type == 'custom':
        if not custom_dept_ids:
            return queryset.none()
        filter_kwargs = {f'{field_name}__department_id__in': custom_dept_ids}
        return queryset.filter(**filter_kwargs)

    return queryset.none()
