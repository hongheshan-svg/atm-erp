"""
非标自动化行业ERP - 数据权限系统

核心设计理念：
1. 项目数据全员可查看 - 促进团队协作和信息透明
2. 财务敏感数据严格控制 - 保护商业机密
3. 操作权限和查看权限分离 - 能看不代表能改
4. 基于角色的权限控制 - 简化管理

使用示例：
    class ProjectViewSet(DataPermissionMixin, viewsets.ModelViewSet):
        queryset = Project.objects.all()
        # 自动应用数据权限
"""
from django.db.models import Q
from rest_framework import permissions
from .permission_config import (
    MODULE_VIEW_POLICY,
    get_module_view_policy,
)
from .permission_service import (
    get_user_permissions,
    has_permission,
    get_hidden_fields,
    resolve_data_scope,
    get_department_tree_ids,
)


def is_finance_allowed(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    user_permissions = get_user_permissions(user)
    return any(code == 'finance' or code.startswith('finance:') for code in user_permissions)


def get_user_view_scope(user, module_name: str, model_name: str = None):
    """
    获取用户对指定模块的查看权限范围
    
    当前策略：数据权限不做限制，所有认证用户可查看所有数据。
    权限控制通过菜单访问权限实现。
    
    Returns:
        str: 'all' | 'none'
    """
    # 未认证用户
    if not user or not user.is_authenticated:
        return 'none'
    
    # 所有认证用户可查看所有数据，权限通过菜单访问控制
    return 'all'


def build_view_filter(user, module_name: str, model_name: str = None, model_class=None):
    """
    构建数据查看过滤条件
    
    Returns:
        Q对象用于filter，None表示不过滤，empty Q()表示返回空
    """
    scope = get_user_view_scope(user, module_name, model_name)
    
    if scope == 'all':
        return None  # 不过滤
    
    if scope == 'none':
        return Q(pk__isnull=True) & Q(pk__isnull=False)  # 返回空
    
    q = Q()
    
    if scope == 'self':
        # 仅自己创建的
        q = Q(created_by=user)
        # 如果有user字段（如报销单的报销人）
        if model_class and hasattr(model_class, 'user'):
            q |= Q(user=user)
        return q
    
    if scope == 'department':
        # 部门数据
        if user.department:
            dept_ids = [user.department.id]
            scope_type, custom_dept_ids = resolve_data_scope(user, module_name)
            if scope_type == 'dept_tree':
                dept_ids = get_department_tree_ids(user.department.id)
            elif scope_type == 'custom' and custom_dept_ids:
                dept_ids = custom_dept_ids

            q = Q(created_by__department_id__in=dept_ids)
        else:
            q = Q(created_by=user)
        return q
    
    if scope == 'related':
        # 相关人员数据 - 根据模块定义关联规则
        rules = get_related_rules(module_name, model_name)
        for rule in rules:
            try:
                field = rule['field']
                rule_type = rule.get('type', 'user')
                
                if rule_type == 'user':
                    q |= Q(**{field: user})
                elif rule_type == 'department' and user.department:
                    q |= Q(**{field: user.department})
            except Exception:
                continue
        
        # 确保至少包含自己创建的
        q |= Q(created_by=user)
        return q
    
    return None


def get_related_rules(module_name: str, model_name: str = None):
    """
    获取模块的关联规则
    用于 view_related 策略下，判断用户是否与数据有关联
    """
    # 通用关联规则 - 创建人总是可以看到自己创建的数据
    rules = [
        {'field': 'created_by', 'type': 'user'},
    ]
    
    # 模块特定规则
    module_rules = {
        'sales': [
            {'field': 'salesperson', 'type': 'user'},
            {'field': 'project__manager', 'type': 'user'},
            {'field': 'project__members__user', 'type': 'user'},
        ],
        'purchase': [
            {'field': 'requestor', 'type': 'user'},       # 采购申请人
            {'field': 'buyer', 'type': 'user'},            # 采购员
            {'field': 'project__manager', 'type': 'user'},
            {'field': 'project__members__user', 'type': 'user'},
        ],
        'aftersales': [
            {'field': 'project__manager', 'type': 'user'},
            {'field': 'project__members__user', 'type': 'user'},
            {'field': 'assignee', 'type': 'user'},
        ],
        'finance': [
            {'field': 'applicant', 'type': 'user'},        # 付款申请人
            {'field': 'user', 'type': 'user'},              # 费用报销人
            {'field': 'reconciled_by', 'type': 'user'},     # 对账人
        ],
    }
    
    rules.extend(module_rules.get(module_name, []))
    return rules


class DataPermissionMixin:
    """
    数据权限Mixin - 应用于ViewSet
    
    自动根据用户角色和模块配置过滤数据
    """
    
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        if not user or not user.is_authenticated:
            return queryset.none()
        
        # 获取模块和模型名
        model = queryset.model
        module_name = model._meta.app_label
        model_name = model._meta.model_name
        
        # 构建过滤条件
        filter_q = build_view_filter(user, module_name, model_name, model)
        
        if filter_q is None:
            return queryset
        
        # 空Q检查
        if str(filter_q) == "(AND: ('pk__isnull', True), ('pk__isnull', False))":
            return queryset.none()
        
        return queryset.filter(filter_q).distinct()


class FinanceDataMixin:
    """
    财务数据权限Mixin
    
    当前策略：数据权限不做限制，所有认证用户可查看所有财务数据。
    权限控制通过菜单访问权限实现。
    """
    
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        if not user or not user.is_authenticated:
            return queryset.none()
        
        return queryset


class OperationPermissionMixin:
    """
    操作权限Mixin - 控制创建/编辑/删除等操作
    """
    
    def check_operation_permission(self, operation: str, obj=None):
        """检查操作权限"""
        user = self.request.user
        
        if not user or not user.is_authenticated:
            return False
        
        if user.is_superuser:
            return True
        
        model = self.get_queryset().model
        module_name = model._meta.app_label
        model_name = model._meta.model_name
        
        permission_code = f'{module_name}:{model_name}:{operation}'

        # 检查基本操作权限
        if has_permission(user, permission_code):
            return True
        
        # 检查 owner 上下文权限
        if obj and has_permission(user, f'{permission_code}@owner'):
            if hasattr(obj, 'created_by') and obj.created_by == user:
                return True
            if hasattr(obj, 'manager') and obj.manager == user:
                return True
        
        # 检查 assignee 上下文权限
        if obj and has_permission(user, f'{permission_code}@assignee'):
            if hasattr(obj, 'assignee') and obj.assignee == user:
                return True
        
        return False
    
    def perform_create(self, serializer):
        if not self.check_operation_permission('create'):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('没有创建权限')
        super().perform_create(serializer)
    
    def perform_update(self, serializer):
        if not self.check_operation_permission('edit', serializer.instance):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('没有编辑权限')
        super().perform_update(serializer)
    
    def perform_destroy(self, instance):
        if not self.check_operation_permission('delete', instance):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('没有删除权限')
        super().perform_destroy(instance)


class SensitiveFieldMixin:
    """
    敏感字段过滤Mixin - 从序列化器输出中移除敏感字段
    """
    
    def get_serializer(self, *args, **kwargs):
        serializer = super().get_serializer(*args, **kwargs)
        
        user = self.request.user
        if not user or not user.is_authenticated:
            return serializer
        
        model = self.get_queryset().model
        module_name = model._meta.app_label
        model_name = model._meta.model_name
        
        # 获取需要隐藏的字段
        hidden_fields = get_hidden_fields(user, module_name, model_name)
        
        # 从序列化器中移除敏感字段
        for field_name in hidden_fields:
            if field_name in serializer.fields:
                serializer.fields.pop(field_name)
        
        return serializer


# ============================================================
# 权限检查装饰器
# ============================================================

def require_finance_permission(view_func):
    """财务权限装饰器（当前策略：数据权限不做限制，直接放行）"""
    def wrapper(self, request, *args, **kwargs):
        return view_func(self, request, *args, **kwargs)
    return wrapper


def require_operation_permission(operation: str):
    """要求操作权限的装饰器"""
    def decorator(view_func):
        def wrapper(self, request, *args, **kwargs):
            if hasattr(self, 'check_operation_permission'):
                obj = self.get_object() if 'pk' in kwargs else None
                if not self.check_operation_permission(operation, obj):
                    from rest_framework.response import Response
                    from rest_framework import status
                    return Response(
                        {'detail': f'没有{operation}权限'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            return view_func(self, request, *args, **kwargs)
        return wrapper
    return decorator


# ============================================================
# 便捷函数
# ============================================================

def filter_queryset_by_permission(queryset, user):
    """
    对查询集应用数据权限过滤
    
    使用示例：
        projects = Project.objects.all()
        projects = filter_queryset_by_permission(projects, request.user)
    """
    if not user or not user.is_authenticated:
        return queryset.none()
    
    if user.is_superuser:
        return queryset
    
    model = queryset.model
    module_name = model._meta.app_label
    model_name = model._meta.model_name
    
    filter_q = build_view_filter(user, module_name, model_name, model)
    
    if filter_q is None:
        return queryset
    
    if str(filter_q) == "(AND: ('pk__isnull', True), ('pk__isnull', False))":
        return queryset.none()
    
    return queryset.filter(filter_q).distinct()


def can_user_view(obj, user) -> bool:
    """
    检查用户是否可以查看某个对象
    """
    if not user or not user.is_authenticated:
        return False
    
    if user.is_superuser:
        return True
    
    module_name = obj._meta.app_label
    model_name = obj._meta.model_name
    
    scope = get_user_view_scope(user, module_name, model_name)
    
    if scope == 'all':
        return True
    
    if scope == 'none':
        return False
    
    if scope == 'self':
        if hasattr(obj, 'created_by') and obj.created_by == user:
            return True
        if hasattr(obj, 'user') and obj.user == user:
            return True
        return False
    
    if scope == 'department':
        if user.department and hasattr(obj, 'created_by') and obj.created_by:
            return obj.created_by.department == user.department
        return False
    
    if scope == 'related':
        # 检查关联规则
        rules = get_related_rules(module_name, model_name)
        for rule in rules:
            try:
                field = rule['field']
                value = obj
                for part in field.split('__'):
                    value = getattr(value, part, None)
                    if value is None:
                        break
                    if hasattr(value, 'all'):
                        value = list(value.all())
                
                if value is None:
                    continue
                
                if isinstance(value, list):
                    if user in value:
                        return True
                elif value == user:
                    return True
            except Exception:
                continue
        
        # 创建人总是可以看
        if hasattr(obj, 'created_by') and obj.created_by == user:
            return True
    
    return False
