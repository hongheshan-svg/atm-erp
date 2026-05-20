"""
非标自动化行业ERP权限配置

行业特点：
- 公司规模通常50-200人，团队小、协作紧密
- 以项目为核心：销售→设计→BOM→采购→生产→调试→交付
- 跨部门协作频繁：工程师、采购、项目经理需要相互了解进度
- 数据透明度高：除核心财务数据外，业务数据应尽量开放

设计原则：
1. 项目/生产/库存/采购/销售 - 全员可查看，促进协作
2. 财务核心数据（账款、发票、税务、总账）- 仅财务和管理层可见
3. 财务业务数据（对账、付款计划、报销）- 相关业务人员也可使用
4. 操作权限和查看权限分离 - 能看不代表能改
5. 菜单权限控制页面入口，数据权限控制数据范围

权限类型：
- view_all: 查看所有数据（全员可见）
- view_related: 查看关联数据（项目成员、负责人等）
- view_department: 查看部门数据
- view_self: 仅查看自己的数据
- restricted: 仅特定角色可查看
- admin_only: 仅管理员可查看
"""

from apps.core.permission_service import get_user_permissions, has_permission

# ============================================================
# 模块权限配置 - 定义各模块的默认查看权限
# ============================================================

MODULE_VIEW_POLICY = {
    # ========== 全员可查看的模块 ==========

    # 项目相关 - 促进团队协作
    'projects': {
        'default_view': 'view_all',
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
            'aftersalesorder': 'view_all',  # 售后工单全员可见
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
            'creditlevel': 'view_all',
            'customercredit': 'view_all',
            'creditadjustment': 'view_all',
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

    # 采购相关 - 全员可查看（非标自动化行业项目制，需要跨部门跟踪采购进度）
    # 注意：采购价格对项目成员可见，便于成本控制（见SENSITIVE_FIELDS配置）
    'purchase': {
        'default_view': 'view_all',
        'description': '采购数据全员可见（非标行业项目制需要跨部门跟踪采购进度）',
        'models': {
            'purchaserequest': 'view_all',
            'purchaseorder': 'view_all',
            'goodsreceipt': 'view_all',
            'purchasecontract': 'view_all',
            'outsourceorder': 'view_all',
            'outsourceorderline': 'view_all',
            'outsourcereceipt': 'view_all',
            'rfq': 'view_all',
            'supplierquotation': 'view_all',
            'quotationcomparison': 'view_all',
            'supplierevaluation': 'view_all',
            'supplierblacklist': 'view_all',
            'supplierqualification': 'view_all',
            'contractexecution': 'view_all',
            'reconciliationcollaboration': 'view_all',
        }
    },

    # 销售相关 - 全员可查看（非标行业项目从销售开始，全程需要跟踪）
    # 注意：利润率等敏感字段通过SENSITIVE_FIELDS控制
    'sales': {
        'default_view': 'view_all',
        'description': '销售数据全员可见（非标行业项目从销售开始，全程跟踪）',
        'models': {
            'salesquotation': 'view_all',
            'salesorder': 'view_all',
            'salescontract': 'view_all',
            'deliveryorder': 'view_all',
        }
    },

    # 售后相关 - 全员可查看（售后问题需要多部门协作解决）
    'aftersales': {
        'default_view': 'view_all',
        'description': '售后数据全员可见，便于多部门协作解决客户问题',
    },

    # OA协同 - 全员可查看（公告、日程等协同数据）
    'oa': {
        'default_view': 'view_all',
        'description': 'OA协同数据全员可见',
    },

    # ========== 敏感数据 - 严格控制 ==========

    # 财务相关 - 核心财务数据受限，业务协作数据开放
    'finance': {
        'default_view': 'restricted',
        'description': '财务核心数据受限，业务协作数据按需开放',
        'sensitive': True,
        'allowed_roles': [
            'admin', 'general_manager',
            'finance_manager', 'finance_staff', 'accountant',
            # 采购/销售经理需要查看部分财务数据（应付/应收）
            'purchase_manager', 'sales_manager',
        ],
        'models': {
            # === 全员可用的财务功能 ===
            'expense': 'view_self',              # 费用报销 - 自己的可见
            'expensereimbursement': 'view_self',  # 报销单 - 自己的可见
            'currency': 'view_all',               # 币种 - 参考数据，全员可见

            # === 业务协作数据 - 相关团队需要使用 ===
            # 对账模块 - 采购/销售团队日常工作需要
            'purchasereconciliation': 'view_all',
            'purchasereconciliationline': 'view_all',
            'salesreconciliation': 'view_all',
            'salesreconciliationline': 'view_all',
            'invoicereconciliation': 'view_all',
            'invoicereconciliationline': 'view_all',
            # 付款计划 - 采购/项目团队需要跟踪付款节点
            'paymentschedule': 'view_all',
            'purchasepaymentschedule': 'view_all',
            # 付款申请 - 各部门都可能发起
            'paymentrequest': 'view_all',
            # 回款计划 - 销售/项目团队需要跟踪回款
            'collectionplan': 'view_all',
            'collectionmilestone': 'view_all',
            'collectionrecord': 'view_all',
            'collectionreminder': 'view_all',

            # === 核心财务数据 - 仅财务和管理层 ===
            'accountsreceivable': 'restricted',   # 应收账款
            'accountspayable': 'restricted',       # 应付账款
            'invoice': 'restricted',               # 发票管理
            'payment': 'restricted',               # 付款记录
            'projectcost': 'restricted',           # 项目成本
            'publicexpenseallocation': 'restricted', # 公共费用分摊
            'sharedexpense': 'restricted',         # 共享费用
            'sharedexpenseallocation': 'restricted',
            # 银行流水 - 高度敏感
            'bankstatement': 'restricted',
            'bankstatementimportlog': 'restricted',
            # 固定资产 - 财务管理
            'fixedasset': 'restricted',
            'assetcategory': 'view_all',           # 资产分类 - 参考数据
            'assetdepreciation': 'restricted',
            'assettransfer': 'restricted',
            'assetdisposal': 'restricted',
            # 总账管理 - 高度敏感
            'chartofaccount': 'restricted',
            'accountcategory': 'restricted',
            'fiscalperiod': 'restricted',
            'journalvoucher': 'restricted',
            'accountbalance': 'restricted',
            # 税务管理 - 高度敏感
            'taxtype': 'restricted',
            'taxrate': 'restricted',
            'taxperiod': 'restricted',
            'taxdeclaration': 'restricted',
            'taxinvoice': 'restricted',
        }
    },

    # 系统管理 - 仅管理员可查看
    'accounts': {
        'default_view': 'admin_only',
        'description': '用户管理仅管理员可操作',
        'models': {
            # 考勤记录 - 自己可见，管理员可见全部
            'attendancerecord': 'view_self',
            'leaverequest': 'view_self',
            'overtimerequest': 'view_self',
        }
    },

    'core': {
        'default_view': 'admin_only',
        'description': '系统配置仅管理员可操作',
        'models': {
            # 工作流任务 - 全员可见自己的待办
            'workflowinstance': 'view_all',
            'workflowtask': 'view_all',
        }
    },
}


# ============================================================
# 敏感字段配置 - 即使有查看权限也隐藏的字段
#
# 设计思路：
# - 采购价格是核心商业机密，仅采购/财务/管理层可见
# - 销售利润率仅销售经理/财务/管理层可见
# - 银行账户信息仅财务可见
# - 项目预算仅项目经理/财务/管理层可见
# ============================================================

SENSITIVE_FIELDS = {
    # 财务敏感字段 - 银行账户等信息
    'finance': {
        'all': ['bank_account', 'bank_name', 'tax_id'],
    },

    # 基础数据敏感字段
    'masterdata': {
        'customer': ['credit_limit', 'payment_terms', 'bank_account', 'bank_name'],
        'supplier': ['credit_rating', 'bank_account', 'bank_name'],
        # 物料主数据中的价格信息
        'item': ['purchase_price', 'standard_cost', 'last_purchase_price', 'sale_price'],
    },

    # 销售敏感字段 - 利润率是高度机密
    'sales': {
        'salesorder': ['profit_margin', 'cost_amount'],
        'salesquotation': ['cost_amount', 'profit_margin'],
        'salescontract': ['profit_analysis'],
    },

    # ========== 采购价格敏感字段（核心保护对象）==========
    'purchase': {
        # 采购申请 - 预估价格
        'purchaserequest': ['total_amount', 'tax_amount', 'total_with_tax'],
        'purchaserequestline': ['estimated_price', 'line_amount'],
        # 采购订单 - 实际采购价格（最敏感）
        'purchaseorder': ['total_amount', 'tax_amount', 'total_with_tax'],
        'purchaseorderline': ['unit_price', 'line_amount'],
        # 采购合同
        'purchasecontract': ['total_amount', 'tax_amount', 'total_with_tax'],
        # 询价单 - 目标价格和历史价格
        'rfqline': ['target_price', 'last_price'],
        # 供应商报价 - 高度敏感
        'supplierquotation': [
            'total_amount', 'tax_amount', 'total_with_tax',
            'last_purchase_price', 'price_change_rate',
        ],
        'supplierquotationline': [
            'unit_price', 'unit_price_with_tax', 'line_amount',
            'line_amount_with_tax', 'sample_unit_price',
            'last_unit_price', 'price_change_rate',
        ],
        # 比价分析 - 包含竞价信息
        'quotationcomparison': ['min_price', 'max_price', 'avg_price', 'weight_price'],
        'quotationscore': ['score_price', 'price_rank'],
        # 价格历史
        'itempricehistory': ['unit_price'],
        # 外协加工
        'outsourceorder': ['total_amount', 'tax_amount', 'total_with_tax'],
        'outsourceorderline': ['unit_price', 'process_amount'],
    },

    # 库存成本敏感字段
    'inventory': {
        'stock': ['weighted_avg_cost'],
        'stockmove': ['unit_cost'],
        'stockadjustmentline': ['cost_impact'],
        'batch': ['unit_cost'],
        'inventorylot': ['unit_cost'],
        'lotconsumption': ['unit_cost', 'total_cost'],
        'materialrequisitionline': ['unit_cost'],
        'materialreturnline': ['unit_cost'],
    },

    # 项目敏感字段
    'projects': {
        'project': ['budget_amount', 'actual_cost'],
    },
}

# ============================================================
# 可以查看敏感字段的角色
# 非标自动化行业：采购价格对采购团队、项目经理、财务、管理层可见
# 生产/仓库/普通员工不可见
# ============================================================

SENSITIVE_FIELD_ALLOWED_ROLES = [
    'admin',
    'general_manager',
    # 财务团队 - 对账、核算需要
    'finance_manager',
    'finance_staff',
    'accountant',
    # 采购团队 - 核心使用者
    'purchase_manager',
    'purchaser',
    # 销售经理 - 报价定价需要了解成本
    'sales_manager',
    # 项目经理 - 项目成本控制需要
    'project_manager',
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
# 非标自动化行业特点：团队小、协作紧密，数据范围不宜过度限制
# ============================================================

DEFAULT_ROLES = [
    {
        'code': 'admin',
        'name': '系统管理员',
        'description': '拥有系统所有权限',
        'data_scope': 'all',
        'permissions': {'is_admin': True}
    },
    {
        'code': 'general_manager',
        'name': '总经理',
        'description': '公司最高管理层，可查看所有数据包括财务',
        'data_scope': 'all',
        'permissions': {'can_view_finance': True, 'can_approve_all': True}
    },
    {
        'code': 'project_manager',
        'name': '项目经理',
        'description': '负责项目整体管理，跟踪采购、生产、交付全流程',
        'data_scope': 'all',
        'permissions': {'can_view_project_cost': True}
    },
    {
        'code': 'engineer',
        'name': '工程师',
        'description': '技术人员，参与项目设计和开发',
        'data_scope': 'all',
        'permissions': {}
    },
    {
        'code': 'debug_engineer',
        'name': '调试工程师',
        'description': '负责设备调试和测试',
        'data_scope': 'all',
        'permissions': {}
    },
    {
        'code': 'sales_manager',
        'name': '销售经理',
        'description': '负责销售团队管理，可查看应收账款',
        'data_scope': 'all',
        'permissions': {'can_view_sales_all': True, 'can_approve_quotation': True, 'can_view_finance': True}
    },
    {
        'code': 'salesperson',
        'name': '销售人员',
        'description': '负责客户开发和订单跟进',
        'data_scope': 'dept_tree',
        'permissions': {}
    },
    {
        'code': 'purchase_manager',
        'name': '采购经理',
        'description': '负责采购团队管理，可查看应付账款',
        'data_scope': 'all',
        'permissions': {'can_view_purchase_all': True, 'can_approve_po': True, 'can_view_finance': True}
    },
    {
        'code': 'purchaser',
        'name': '采购人员',
        'description': '负责物料采购和供应商协调',
        'data_scope': 'all',
        'permissions': {}
    },
    {
        'code': 'finance_manager',
        'name': '财务经理',
        'description': '负责财务管理，可查看所有财务数据',
        'data_scope': 'all',
        'permissions': {'can_view_finance': True, 'can_approve_payment': True}
    },
    {
        'code': 'finance_staff',
        'name': '财务专员',
        'description': '财务日常工作处理',
        'data_scope': 'all',
        'permissions': {'can_view_finance': True}
    },
    {
        'code': 'accountant',
        'name': '财务人员',
        'description': '负责记账、对账、报税与日常财务处理',
        'data_scope': 'all',
        'permissions': {'can_view_finance': True}
    },
    {
        'code': 'warehouse_manager',
        'name': '仓库主管',
        'description': '负责仓库管理和出入库审批',
        'data_scope': 'all',
        'permissions': {'can_approve_material': True}
    },
    {
        'code': 'warehouse_staff',
        'name': '仓管员',
        'description': '负责出入库操作',
        'data_scope': 'all',
        'permissions': {}
    },
    {
        'code': 'production_manager',
        'name': '生产主管',
        'description': '负责生产计划和进度管理',
        'data_scope': 'all',
        'permissions': {}
    },
    {
        'code': 'production_staff',
        'name': '生产人员',
        'description': '一线生产人员',
        'data_scope': 'all',
        'permissions': {}
    },
    {
        'code': 'qa_engineer',
        'name': '质量工程师',
        'description': '负责来料检验和出厂质检',
        'data_scope': 'all',
        'permissions': {}
    },
    {
        'code': 'viewer',
        'name': '查看者',
        'description': '只读权限，可查看项目和生产数据',
        'data_scope': 'all',
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
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    user_permissions = get_user_permissions(user)
    return any(code == 'finance' or code.startswith('finance:') for code in user_permissions)


def can_view_sensitive_fields(user, module_name: str, model_name: str = None) -> bool:
    """检查用户是否可以查看敏感字段"""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    user_permissions = get_user_permissions(user)
    required_codes = {
        f'{module_name}:{model_name}:*' if model_name else None,
        f'{module_name}:*',
    }
    return any(code and has_permission(user, code) for code in required_codes)


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
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    return has_permission(user, f'{module_name}:{model_name}:{operation}')
