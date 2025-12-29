"""
基于业务关联的多维度数据权限系统

设计理念：
1. 功能权限（能否访问菜单/API）与数据权限（能看到哪些数据）分离
2. 数据权限基于业务关联，而非简单的创建人
3. 多条件OR：满足任一条件即可访问
4. 可配置、可扩展，无需硬编码

使用示例：
    class SalesOrderViewSet(DataPermissionMixin, viewsets.ModelViewSet):
        # 配置数据权限规则
        permission_rules = [
            {'field': 'created_by', 'type': 'user'},           # 我创建的
            {'field': 'salesperson', 'type': 'user'},          # 我是销售员
            {'field': 'project__members', 'type': 'user'},     # 我是项目成员
            {'field': 'customer__salesperson', 'type': 'user'}, # 我负责的客户
        ]
"""
from django.db.models import Q
from django.conf import settings


class DataPermissionConfig:
    """
    数据权限配置
    可以在数据库中配置，或者在代码中定义
    """
    
    # 模块默认权限规则
    # key: app_label, value: 权限规则列表
    MODULE_RULES = {
        'sales': [
            {'field': 'created_by', 'type': 'user', 'desc': '创建人'},
            {'field': 'salesperson', 'type': 'user', 'desc': '销售员'},
            {'field': 'project__manager', 'type': 'user', 'desc': '项目经理'},
            {'field': 'project__members__user', 'type': 'user', 'desc': '项目成员'},
        ],
        'purchase': [
            {'field': 'created_by', 'type': 'user', 'desc': '创建人'},
            {'field': 'project__manager', 'type': 'user', 'desc': '项目经理'},
            {'field': 'project__members__user', 'type': 'user', 'desc': '项目成员'},
        ],
        'projects': [
            {'field': 'created_by', 'type': 'user', 'desc': '创建人'},
            {'field': 'manager', 'type': 'user', 'desc': '项目经理'},
            {'field': 'members__user', 'type': 'user', 'desc': '项目成员'},
            {'field': 'sales_order__salesperson', 'type': 'user', 'desc': '关联销售员'},
        ],
        'inventory': [
            # 库存通常需要更开放的权限
            {'field': 'created_by', 'type': 'user', 'desc': '创建人'},
            # 可通过角色配置 department 或 all 权限
        ],
        'finance': [
            {'field': 'created_by', 'type': 'user', 'desc': '创建人'},
            {'field': 'user', 'type': 'user', 'desc': '报销人'},
            {'field': 'project__manager', 'type': 'user', 'desc': '项目经理'},
        ],
    }
    
    # 角色特殊权限配置
    # 某些角色对某些模块有特殊权限
    ROLE_OVERRIDES = {
        # 角色code: {模块: 权限类型}
        'admin': {'*': 'all'},  # 管理员所有模块全权限
        'finance_manager': {
            'finance': 'all',
            'sales': 'view_all',    # 只能查看，不能改
            'purchase': 'view_all',
        },
        'warehouse_manager': {
            'inventory': 'all',
            'purchase': 'view_all',  # 查看采购单用于收货
        },
        'sales_manager': {
            'sales': 'department',   # 查看部门销售数据
            'projects': 'related',   # 只看关联项目
        },
        'purchase_manager': {
            'purchase': 'department',
            'inventory': 'view_all',
        },
    }


def build_permission_query(user, rules, include_department=False, include_all=False):
    """
    根据规则构建权限查询条件
    
    Args:
        user: 当前用户
        rules: 权限规则列表
        include_department: 是否包含部门数据
        include_all: 是否包含所有数据
    
    Returns:
        Q对象，用于filter
    """
    if include_all:
        return Q()  # 空Q表示不过滤
    
    # 构建多条件OR查询
    q_objects = Q()
    
    for rule in rules:
        field = rule.get('field')
        rule_type = rule.get('type', 'user')
        
        if not field:
            continue
        
        try:
            if rule_type == 'user':
                # 字段关联到用户
                q_objects |= Q(**{field: user})
            elif rule_type == 'department':
                # 字段关联到部门
                if user.department:
                    q_objects |= Q(**{field: user.department})
            elif rule_type == 'value':
                # 固定值匹配
                value = rule.get('value')
                if value:
                    q_objects |= Q(**{field: value})
        except Exception:
            # 字段可能不存在，忽略该规则
            continue
    
    # 如果包含部门权限
    if include_department and user.department:
        # 尝试添加部门条件（假设有created_by字段）
        try:
            q_objects |= Q(created_by__department=user.department)
        except Exception:
            pass
    
    return q_objects


def get_module_rules_from_db(module_name):
    """从数据库获取模块权限规则"""
    try:
        from .permission_models import ModulePermissionRule
        rules = ModulePermissionRule.objects.filter(
            module=module_name,
            is_active=True
        ).order_by('sort_order')
        
        if rules.exists():
            return [rule.to_rule_dict() for rule in rules]
    except Exception:
        pass  # 数据库表可能不存在
    
    return None


def get_role_module_permission_from_db(role, module_name):
    """从数据库获取角色模块权限"""
    try:
        from .permission_models import RoleModulePermission
        perm = RoleModulePermission.objects.filter(
            role=role,
            module=module_name,
            is_active=True
        ).first()
        
        if perm:
            return perm.permission_type
    except Exception:
        pass  # 数据库表可能不存在
    
    return None


def get_user_data_scope(user, module_name):
    """
    获取用户对指定模块的数据权限范围
    
    Returns:
        tuple: (scope_type, rules)
        scope_type: 'all' | 'department' | 'rules' | 'none'
        rules: 当scope_type为'rules'时的规则列表
    """
    # 超级管理员
    if user.is_superuser:
        return ('all', [])
    
    # 检查用户角色
    if not hasattr(user, 'role') or not user.role:
        return ('none', [])
    
    role = user.role
    role_code = role.code if hasattr(role, 'code') else ''
    
    # 1. 优先从数据库获取角色模块权限配置
    db_permission = get_role_module_permission_from_db(role, module_name)
    if db_permission:
        if db_permission in ('all', 'view_all'):
            return ('all', [])
        elif db_permission == 'department':
            rules = get_module_rules_from_db(module_name) or \
                    DataPermissionConfig.MODULE_RULES.get(module_name, [])
            return ('department', rules)
        elif db_permission == 'self':
            rules = get_module_rules_from_db(module_name) or \
                    DataPermissionConfig.MODULE_RULES.get(module_name, [])
            return ('rules', rules)
    
    # 2. 检查代码中的角色特殊配置（向后兼容）
    if role_code in DataPermissionConfig.ROLE_OVERRIDES:
        overrides = DataPermissionConfig.ROLE_OVERRIDES[role_code]
        
        # 检查通配符
        if '*' in overrides:
            return (overrides['*'], [])
        
        # 检查具体模块
        if module_name in overrides:
            scope = overrides[module_name]
            if scope in ('all', 'view_all'):
                return ('all', [])
            elif scope == 'department':
                return ('department', [])
    
    # 3. 使用角色默认的data_scope
    data_scope = getattr(role, 'data_scope', 'SELF')
    
    # 获取模块规则（优先数据库，其次代码配置）
    rules = get_module_rules_from_db(module_name) or \
            DataPermissionConfig.MODULE_RULES.get(module_name, [])
    
    if data_scope == 'ALL':
        return ('all', [])
    elif data_scope == 'DEPARTMENT':
        return ('department', rules)
    else:  # SELF
        return ('rules', rules)


class DataPermissionMixin:
    """
    数据权限Mixin - 替代原有的DataScopeMixin
    
    支持：
    1. 基于业务关联的多维度权限
    2. 角色特殊配置
    3. 可在ViewSet中自定义规则
    """
    
    # 可在ViewSet中覆盖
    permission_rules = None  # 自定义规则，None则使用模块默认规则
    module_name = None       # 模块名，None则自动检测
    
    def get_data_permission_module(self):
        """获取当前模块名"""
        if self.module_name:
            return self.module_name
        
        # 从model获取app_label
        if hasattr(self, 'queryset') and self.queryset is not None:
            return self.queryset.model._meta.app_label
        
        return None
    
    def get_permission_rules(self):
        """获取权限规则"""
        if self.permission_rules:
            return self.permission_rules
        
        module = self.get_data_permission_module()
        return DataPermissionConfig.MODULE_RULES.get(module, [
            {'field': 'created_by', 'type': 'user', 'desc': '创建人'}
        ])
    
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        if not user.is_authenticated:
            return queryset.none()
        
        module = self.get_data_permission_module()
        scope_type, rules = get_user_data_scope(user, module)
        
        if scope_type == 'all':
            return queryset
        elif scope_type == 'none':
            return queryset.none()
        elif scope_type == 'department':
            # 部门权限 + 业务关联规则
            rules = rules or self.get_permission_rules()
            q = build_permission_query(user, rules, include_department=True)
            if q:
                return queryset.filter(q).distinct()
            return queryset
        else:  # rules
            rules = rules or self.get_permission_rules()
            q = build_permission_query(user, rules)
            if q:
                return queryset.filter(q).distinct()
            # 如果没有规则匹配，至少返回自己创建的
            if hasattr(queryset.model, 'created_by'):
                return queryset.filter(created_by=user)
            return queryset.none()


# ============ 便捷函数 ============

def filter_by_permission(queryset, user, rules=None):
    """
    便捷函数：对任意queryset应用数据权限过滤
    
    使用示例：
        orders = SalesOrder.objects.all()
        orders = filter_by_permission(orders, request.user)
    """
    if user.is_superuser:
        return queryset
    
    module = queryset.model._meta.app_label
    scope_type, default_rules = get_user_data_scope(user, module)
    
    if scope_type == 'all':
        return queryset
    elif scope_type == 'none':
        return queryset.none()
    
    use_rules = rules or default_rules or [
        {'field': 'created_by', 'type': 'user'}
    ]
    
    include_dept = (scope_type == 'department')
    q = build_permission_query(user, use_rules, include_department=include_dept)
    
    if q:
        return queryset.filter(q).distinct()
    return queryset


def can_access_object(obj, user, rules=None):
    """
    检查用户是否有权访问某个对象
    
    使用示例：
        if can_access_object(order, request.user):
            ...
    """
    if user.is_superuser:
        return True
    
    module = obj._meta.app_label
    scope_type, default_rules = get_user_data_scope(user, module)
    
    if scope_type == 'all':
        return True
    elif scope_type == 'none':
        return False
    
    use_rules = rules or default_rules or [
        {'field': 'created_by', 'type': 'user'}
    ]
    
    # 检查每个规则
    for rule in use_rules:
        field = rule.get('field')
        rule_type = rule.get('type', 'user')
        
        if not field:
            continue
        
        # 处理关联字段 (如 project__manager)
        try:
            value = obj
            for part in field.split('__'):
                value = getattr(value, part, None)
                if value is None:
                    break
                # 处理多对多关系
                if hasattr(value, 'all'):
                    value = list(value.all())
            
            if value is None:
                continue
            
            # 比较
            if rule_type == 'user':
                if isinstance(value, list):
                    if user in value:
                        return True
                elif value == user:
                    return True
            elif rule_type == 'department':
                if user.department and value == user.department:
                    return True
        except Exception:
            continue
    
    # 检查部门权限
    if scope_type == 'department' and user.department:
        if hasattr(obj, 'created_by') and obj.created_by:
            if obj.created_by.department == user.department:
                return True
    
    return False

