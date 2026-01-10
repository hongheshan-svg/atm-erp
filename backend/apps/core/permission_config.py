"""
非标自动化行业ERP权限配置

设计原则：
1. 项目数据全员可查看 - 促进团队协作
2. 财务敏感数据严格控制 - 保护商业机密
3. 操作权限按角色分配 - 确保流程规范
4. 查看权限和操作权限分离

权限类型：
- view_all: 查看所有数据
- view_related: 查看关联数据（项目成员、负责人等）
- view_department: 查看部门数据
- view_self: 仅查看自己的数据
- edit: 编辑权限
- delete: 删除权限
- approve: 审批权限
"""

# ============================================================
# 模块权限配置 - 定义各模块的默认查看权限
# ============================================================

MODULE_VIEW_POLICY = {
    # ========== 全员可查看的模块 ==========
    # 项目相关 - 促进团队协作
    'projects': {
        'default_view': 'view_all',  # 全员可查看所有项目
        'description': '项目数据全员可见，促进团队协作',
        'models': {
            'project': 'view_all',
            'task': 'view_all',
            'projectmember': 'view_all',
            'projectbom': 'view_all',
            'timeentry': 'view_all',
            'ecnchange': 'view_all',
            'drawing': 'view_all',
            'bug': 'view_all',
        }
    },
    
    # 生产相关 - 全员可查看生产进度
    'production': {
        'default_view': 'view_all',
        'description': '生产数据全员可见，便于跟踪进度',
        'models': {
            'productionprocess': 'view_all',
            'productionplan': 'view_all',
            'productionlog': 'view_all',
            'debugrecord': 'view_all',
            'qualityinspection': 'view_all',
        }
    },
    
    # 基础数据 - 全员可查看
    'masterdata': {
        'default_view': 'view_all',
        'description': '基础数据全员可见',
        'models': {
            'item': 'view_all',
            'customer': 'view_all',
            'supplier': 'view_all',
            'warehouse': 'view_all',
            'location': 'view_all',
        }
    },
    
    # 库存相关 - 全员可查看库存状态
    'inventory': {
        'default_view': 'view_all',
        'description': '库存数据全员可见，便于物料查询',
        'models': {
            'inventory': 'view_all',
            'inventorybatch': 'view_all',
            'inventorytransaction': 'view_all',
            'inventorytransfer': 'view_all',
            'inventorycount': 'view_all',
            'materialrequisition': 'view_all',
            'materialreturn': 'view_all',
        }
    },
    
    # ========== 部门/关联人员可查看的模块 ==========
    # 采购相关 - 相关人员可查看
    'purchase': {
        'default_view': 'view_related',
        'description': '采购数据相关人员可见',
        'models': {
            'purchaserequest': 'view_related',  # 申请人、项目成员可见
            'supplierquotation': 'view_related',
            'purchaseorder': 'view_related',
            'outsourceorder': 'view_related',
            'arrivalinspection': 'view_related',
        }
    },
    
    # 销售相关 - 相关人员可查看
    'sales': {
        'default_view': 'view_related',
        'description': '销售数据相关人员可见',
        'models': {
            'salesquotation': 'view_related',
            'salesorder': 'view_related',
            'salescontract': 'view_related',
            'deliveryorder': 'view_related',
        }
    },
    
    # 售后相关 - 相关人员可查看
    'aftersales': {
        'default_view': 'view_related',
        'description': '售后数据相关人员可见',
    },
    
    # ========== 敏感数据 - 严格控制 ==========
    # 财务相关 - 仅财务人员和管理层可查看
    'finance': {
        'default_view': 'restricted',
        'description': '财务数据受限，仅财务人员和管理层可见',
        'sensitive': True,
        'allowed_roles': ['admin', 'general_manager', 'finance_manager', 'finance_staff', 'accountant'],
        'models': {
            'expensereimbursement': 'view_self',  # 自己的报销单可见
            'publicexpenseallocation': 'restricted',
            'accountsreceivable': 'restricted',
            'accountspayable': 'restricted',
            'invoice': 'restricted',
            'projectcost': 'restricted',
        }
    },
    
    # 系统管理 - 仅管理员可查看
    'accounts': {
        'default_view': 'admin_only',
        'description': '用户管理仅管理员可操作',
    },
    
    'core': {
        'default_view': 'admin_only',
        'description': '系统配置仅管理员可操作',
    },
}


# ============================================================
# 敏感字段配置 - 即使有查看权限也隐藏的字段
# ============================================================

SENSITIVE_FIELDS = {
    # 财务敏感字段
    'finance': {
        'all': ['bank_account', 'bank_name', 'tax_id'],  # 所有模型隐藏
    },
    'masterdata': {
        'customer': ['credit_limit', 'payment_terms', 'bank_account', 'bank_name'],
        'supplier': ['credit_rating', 'bank_account', 'bank_name'],
    },
    'sales': {
        'salesorder': ['profit_margin', 'cost_amount'],
        'salesquotation': ['cost_amount', 'profit_margin'],
        'salescontract': ['profit_analysis'],
    },
    'purchase': {
        'purchaseorder': [],  # 采购价格对项目成员可见，便于成本控制
    },
    'projects': {
        'project': ['budget_amount', 'actual_cost'],  # 项目预算敏感
    },
}

# 可以查看敏感字段的角色
SENSITIVE_FIELD_ALLOWED_ROLES = [
    'admin',
    'general_manager', 
    'finance_manager',
    'finance_staff',
    'project_manager',  # 项目经理可以看自己项目的成本
]


# ============================================================
# 操作权限配置 - 定义谁可以执行什么操作
# ============================================================

OPERATION_PERMISSIONS = {
    # 项目管理
    'projects': {
        'project': {
            'create': ['admin', 'general_manager', 'sales_manager', 'project_manager'],
            'edit': ['admin', 'general_manager', 'project_manager', 'owner'],  # owner = 项目经理
            'delete': ['admin', 'general_manager'],
            'change_status': ['admin', 'general_manager', 'project_manager', 'owner'],
        },
        'task': {
            'create': ['admin', 'project_manager', 'owner', 'member'],  # member = 项目成员
            'edit': ['admin', 'project_manager', 'owner', 'assignee'],
            'delete': ['admin', 'project_manager', 'owner'],
        },
        'projectbom': {
            'create': ['admin', 'project_manager', 'owner', 'member', 'engineer'],
            'edit': ['admin', 'project_manager', 'owner', 'engineer'],
            'delete': ['admin', 'project_manager'],
        },
    },
    
    # 采购管理
    'purchase': {
        'purchaserequest': {
            'create': ['admin', 'project_manager', 'engineer', 'purchaser', 'member'],
            'edit': ['admin', 'purchaser', 'owner'],
            'delete': ['admin', 'owner'],
            'submit': ['admin', 'owner'],
            'approve': ['admin', 'purchase_manager', 'general_manager'],
        },
        'purchaseorder': {
            'create': ['admin', 'purchaser', 'purchase_manager'],
            'edit': ['admin', 'purchaser', 'owner'],
            'delete': ['admin'],
            'confirm': ['admin', 'purchase_manager'],
        },
    },
    
    # 销售管理
    'sales': {
        'salesquotation': {
            'create': ['admin', 'salesperson', 'sales_manager'],
            'edit': ['admin', 'owner', 'sales_manager'],
            'delete': ['admin', 'sales_manager'],
            'submit': ['admin', 'owner'],
            'approve': ['admin', 'sales_manager', 'general_manager'],
        },
        'salesorder': {
            'create': ['admin', 'salesperson', 'sales_manager'],
            'edit': ['admin', 'owner', 'sales_manager'],
            'delete': ['admin'],
            'confirm': ['admin', 'sales_manager', 'general_manager'],
        },
    },
    
    # 生产管理
    'production': {
        'productionplan': {
            'create': ['admin', 'production_manager', 'project_manager'],
            'edit': ['admin', 'production_manager', 'owner'],
            'delete': ['admin'],
            'start': ['admin', 'production_manager', 'owner'],
            'complete': ['admin', 'production_manager', 'owner'],
        },
        'debugrecord': {
            'create': ['admin', 'engineer', 'debug_engineer', 'project_manager'],
            'edit': ['admin', 'owner', 'debug_engineer'],
            'complete': ['admin', 'owner', 'debug_engineer'],
        },
        'qualityinspection': {
            'create': ['admin', 'qa_engineer', 'production_manager'],
            'edit': ['admin', 'owner', 'qa_engineer'],
            'complete': ['admin', 'owner', 'qa_engineer'],
        },
    },
    
    # 库存管理
    'inventory': {
        'materialrequisition': {
            'create': ['admin', 'project_manager', 'engineer', 'member', 'production_staff'],
            'edit': ['admin', 'owner', 'warehouse_manager'],
            'approve': ['admin', 'warehouse_manager', 'project_manager'],
            'issue': ['admin', 'warehouse_staff', 'warehouse_manager'],
        },
        'inventorytransfer': {
            'create': ['admin', 'warehouse_staff', 'warehouse_manager'],
            'edit': ['admin', 'owner', 'warehouse_manager'],
            'complete': ['admin', 'warehouse_staff', 'warehouse_manager'],
        },
    },
    
    # 财务管理
    'finance': {
        'expensereimbursement': {
            'create': ['*'],  # 所有人可以创建报销单
            'edit': ['admin', 'owner'],
            'delete': ['admin', 'owner'],
            'submit': ['admin', 'owner'],
            'approve': ['admin', 'finance_manager', 'general_manager'],
        },
        'invoice': {
            'create': ['admin', 'finance_staff', 'finance_manager'],
            'edit': ['admin', 'finance_staff', 'finance_manager'],
            'delete': ['admin', 'finance_manager'],
        },
        'accountsreceivable': {
            'create': ['admin', 'finance_staff', 'finance_manager'],
            'edit': ['admin', 'finance_staff', 'finance_manager'],
            'confirm_payment': ['admin', 'finance_manager'],
        },
        'accountspayable': {
            'create': ['admin', 'finance_staff', 'finance_manager'],
            'edit': ['admin', 'finance_staff', 'finance_manager'],
            'confirm_payment': ['admin', 'finance_manager'],
        },
    },
}


# ============================================================
# 默认角色配置 - 系统初始化时创建
# ============================================================

DEFAULT_ROLES = [
    {
        'code': 'admin',
        'name': '系统管理员',
        'description': '拥有系统所有权限',
        'data_scope': 'ALL',
        'permissions': {'is_admin': True}
    },
    {
        'code': 'general_manager',
        'name': '总经理',
        'description': '公司最高管理层，可查看所有数据',
        'data_scope': 'ALL',
        'permissions': {'can_view_finance': True, 'can_approve_all': True}
    },
    {
        'code': 'project_manager',
        'name': '项目经理',
        'description': '负责项目整体管理，可查看项目相关所有数据',
        'data_scope': 'ALL',  # 项目数据全员可见，项目经理有编辑权
        'permissions': {'can_view_project_cost': True}
    },
    {
        'code': 'engineer',
        'name': '工程师',
        'description': '技术人员，参与项目设计和开发',
        'data_scope': 'ALL',
        'permissions': {}
    },
    {
        'code': 'debug_engineer',
        'name': '调试工程师',
        'description': '负责设备调试和测试',
        'data_scope': 'ALL',
        'permissions': {}
    },
    {
        'code': 'sales_manager',
        'name': '销售经理',
        'description': '负责销售团队管理',
        'data_scope': 'DEPARTMENT',
        'permissions': {'can_view_sales_all': True, 'can_approve_quotation': True}
    },
    {
        'code': 'salesperson',
        'name': '销售员',
        'description': '负责客户开发和订单跟进',
        'data_scope': 'SELF',
        'permissions': {}
    },
    {
        'code': 'purchase_manager',
        'name': '采购经理',
        'description': '负责采购团队管理',
        'data_scope': 'DEPARTMENT',
        'permissions': {'can_view_purchase_all': True, 'can_approve_po': True}
    },
    {
        'code': 'purchaser',
        'name': '采购员',
        'description': '负责物料采购',
        'data_scope': 'SELF',
        'permissions': {}
    },
    {
        'code': 'finance_manager',
        'name': '财务经理',
        'description': '负责财务管理，可查看所有财务数据',
        'data_scope': 'ALL',
        'permissions': {'can_view_finance': True, 'can_approve_payment': True}
    },
    {
        'code': 'finance_staff',
        'name': '财务专员',
        'description': '财务日常工作处理',
        'data_scope': 'ALL',
        'permissions': {'can_view_finance': True}
    },
    {
        'code': 'warehouse_manager',
        'name': '仓库主管',
        'description': '负责仓库管理',
        'data_scope': 'ALL',
        'permissions': {'can_approve_material': True}
    },
    {
        'code': 'warehouse_staff',
        'name': '仓管员',
        'description': '负责出入库操作',
        'data_scope': 'ALL',
        'permissions': {}
    },
    {
        'code': 'production_manager',
        'name': '生产主管',
        'description': '负责生产计划和进度管理',
        'data_scope': 'ALL',
        'permissions': {}
    },
    {
        'code': 'production_staff',
        'name': '生产人员',
        'description': '一线生产人员',
        'data_scope': 'ALL',
        'permissions': {}
    },
    {
        'code': 'qa_engineer',
        'name': '质量工程师',
        'description': '负责质量检验和管理',
        'data_scope': 'ALL',
        'permissions': {}
    },
    {
        'code': 'viewer',
        'name': '查看者',
        'description': '只读权限，可查看项目和生产数据',
        'data_scope': 'ALL',
        'permissions': {'readonly': True}
    },
]


# ============================================================
# 辅助函数
# ============================================================

def get_module_view_policy(module_name: str, model_name: str = None) -> str:
    """获取模块/模型的查看策略"""
    policy = MODULE_VIEW_POLICY.get(module_name, {})
    
    if model_name and 'models' in policy:
        return policy['models'].get(model_name.lower(), policy.get('default_view', 'view_related'))
    
    return policy.get('default_view', 'view_related')


def is_finance_allowed(user) -> bool:
    """检查用户是否可以查看财务数据"""
    if user.is_superuser:
        return True
    
    if not hasattr(user, 'role') or not user.role:
        return False
    
    role_code = getattr(user.role, 'code', '')
    allowed_roles = MODULE_VIEW_POLICY.get('finance', {}).get('allowed_roles', [])
    
    if role_code in allowed_roles:
        return True
    
    # 检查权限配置
    permissions = getattr(user.role, 'permissions', {}) or {}
    return permissions.get('can_view_finance', False)


def can_view_sensitive_fields(user, module_name: str, model_name: str = None) -> bool:
    """检查用户是否可以查看敏感字段"""
    if user.is_superuser:
        return True
    
    if not hasattr(user, 'role') or not user.role:
        return False
    
    role_code = getattr(user.role, 'code', '')
    return role_code in SENSITIVE_FIELD_ALLOWED_ROLES


def get_hidden_fields(user, module_name: str, model_name: str) -> list:
    """获取需要对用户隐藏的字段列表"""
    if can_view_sensitive_fields(user, module_name, model_name):
        return []
    
    hidden = []
    
    # 模块级隐藏字段
    module_sensitive = SENSITIVE_FIELDS.get(module_name, {})
    hidden.extend(module_sensitive.get('all', []))
    
    # 模型级隐藏字段
    if model_name:
        hidden.extend(module_sensitive.get(model_name.lower(), []))
    
    return list(set(hidden))


def has_operation_permission(user, module_name: str, model_name: str, operation: str) -> bool:
    """检查用户是否有操作权限"""
    if user.is_superuser:
        return True
    
    if not hasattr(user, 'role') or not user.role:
        return False
    
    role_code = getattr(user.role, 'code', '')
    
    # 只读角色
    permissions = getattr(user.role, 'permissions', {}) or {}
    if permissions.get('readonly'):
        return False
    
    # 获取操作权限配置
    module_perms = OPERATION_PERMISSIONS.get(module_name, {})
    model_perms = module_perms.get(model_name.lower(), {})
    allowed_roles = model_perms.get(operation, [])
    
    # 检查通配符
    if '*' in allowed_roles:
        return True
    
    # 检查角色
    if role_code in allowed_roles:
        return True
    
    # admin角色总是有权限
    if 'admin' in allowed_roles and role_code == 'admin':
        return True
    
    return False
