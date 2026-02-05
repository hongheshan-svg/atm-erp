"""
初始化非标自动化行业预设角色和权限配置

非标自动化行业特点：
1. 项目驱动：每个订单都是一个项目，需要技术方案、BOM、图纸等
2. 多部门协作：销售→技术→采购→生产→质量→售后
3. 长周期：项目周期长，里程碑跟踪重要
4. 成本控制：项目成本核算是关键
5. 技术密集：需要大量技术文档管理
"""
from django.core.management.base import BaseCommand
from apps.accounts.models import Role


# 非标自动化行业预设角色权限配置
INDUSTRY_ROLES = [
    {
        'name': '总经理',
        'code': 'general_manager',
        'description': '公司最高管理层，拥有全部权限，可查看所有数据和报表',
        'data_scope': 'ALL',
        'menu_ids': [
            # 仪表盘
            'dashboard',
            # 全部模块权限
            'projects', 'plm', 'sales', 'purchase', 'inventory', 'production',
            'mes', 'equipment', 'finance', 'reports', 'analytics', 'oa',
            'workflow', 'masterdata', 'knowledge', 'aftersales', 'accounts',
            # 报表分析（重点）
            'reports:profitability', 'reports:cost-analysis', 'reports:cash-flow',
            'reports:inventory-turnover', 'reports:aging', 'reports:industry',
            'analytics:project', 'analytics:inventory',
        ],
        'sort_order': 1
    },
    {
        'name': '项目经理',
        'code': 'project_manager',
        'description': '负责项目全生命周期管理，包括进度、成本、质量、团队协调',
        'data_scope': 'DEPARTMENT',
        'menu_ids': [
            'dashboard',
            # 项目管理（核心）
            'projects', 'projects:list', 'projects:dashboard', 'projects:tasks',
            'projects:members', 'projects:bom', 'projects:time-logs', 'projects:gantt',
            'projects:milestones', 'projects:alerts', 'projects:equipment-archives',
            'projects:acceptances', 'projects:archives', 'projects:cost',
            'projects:monitoring', 'projects:work-orders',
            # PLM产品研发
            'plm', 'plm:requirements', 'plm:proposals', 'plm:agreements',
            # 技术文档
            'projects:drawings', 'projects:documents', 'projects:ecn',
            'plm:cad-bom', 'plm:bom-compare',
            # 知识库
            'knowledge', 'knowledge:articles', 'knowledge:issues', 'knowledge:components',
            # 报表
            'reports', 'reports:profitability', 'reports:cost-analysis', 'reports:timelog',
            # 审批
            'workflow', 'workflow:tasks', 'workflow:my-submissions',
            # OA
            'oa', 'oa:schedule', 'oa:meeting',
        ],
        'sort_order': 2
    },
    {
        'name': '技术工程师',
        'code': 'engineer',
        'description': '负责技术方案设计、BOM编制、图纸管理、技术文档',
        'data_scope': 'DEPARTMENT',
        'menu_ids': [
            'dashboard',
            # PLM产品研发（核心）
            'plm', 'plm:requirements', 'plm:proposals', 'plm:configurator',
            'plm:agreements', 'plm:model-viewer', 'plm:cad-bom', 'plm:bom-compare',
            # 项目相关
            'projects', 'projects:list', 'projects:tasks', 'projects:bom',
            'projects:drawings', 'projects:documents', 'projects:ecn',
            'projects:bugs', 'projects:time-logs', 'projects:batch-drawing',
            'projects:drawing-bom-link',
            # 知识库
            'knowledge', 'knowledge:articles', 'knowledge:issues', 'knowledge:components',
            # 基础数据（物料查询）
            'masterdata', 'masterdata:items',
            # 审批
            'workflow', 'workflow:tasks', 'workflow:my-submissions',
            # OA
            'oa', 'oa:schedule', 'oa:leave', 'accounts:attendance',
        ],
        'sort_order': 3
    },
    {
        'name': '销售经理',
        'code': 'sales_manager',
        'description': '负责销售团队管理、客户关系、报价审批、销售分析',
        'data_scope': 'DEPARTMENT',
        'menu_ids': [
            'dashboard',
            # CRM客户管理（核心）
            'sales', 'sales:crm-dashboard', 'sales:leads', 'sales:opportunities',
            'sales:quotations', 'sales:quote-estimation', 'sales:orders',
            'sales:contracts', 'sales:delivery-orders', 'sales:quote-templates',
            'sales:contract-templates', 'sales:performance', 'sales:analysis',
            'sales:quote',
            # 客户管理
            'masterdata', 'masterdata:customers', 'masterdata:customer-contacts',
            'masterdata:customer-followups', 'masterdata:credit',
            # 售后
            'aftersales', 'aftersales:orders',
            # 财务相关
            'finance', 'finance:ar', 'finance:sales-reconciliation', 'finance:collection',
            # 报表
            'reports', 'reports:profitability', 'reports:aging', 'reports:cash-flow',
            # 审批
            'workflow', 'workflow:tasks', 'workflow:my-submissions',
            # OA
            'oa', 'oa:schedule', 'oa:meeting', 'accounts:attendance',
        ],
        'sort_order': 4
    },
    {
        'name': '销售人员',
        'code': 'salesperson',
        'description': '负责客户开发、跟进、报价、订单处理',
        'data_scope': 'SELF',
        'menu_ids': [
            'dashboard',
            # CRM（核心）
            'sales', 'sales:leads', 'sales:opportunities', 'sales:quotations',
            'sales:orders', 'sales:contracts', 'sales:delivery-orders',
            'sales:quote-estimation', 'sales:quote',
            # 客户管理
            'masterdata', 'masterdata:customers', 'masterdata:customer-contacts',
            'masterdata:customer-followups',
            # 售后
            'aftersales', 'aftersales:orders',
            # 审批
            'workflow', 'workflow:tasks', 'workflow:my-submissions',
            # OA
            'oa', 'oa:schedule', 'accounts:attendance',
        ],
        'sort_order': 5
    },
    {
        'name': '采购经理',
        'code': 'purchase_manager',
        'description': '负责采购团队管理、供应商管理、采购审批、成本控制',
        'data_scope': 'DEPARTMENT',
        'menu_ids': [
            'dashboard',
            # 采购管理（核心）
            'purchase', 'purchase:requests', 'purchase:comparisons', 'purchase:orders',
            'purchase:goods-receipts', 'purchase:outsource', 'purchase:evaluations',
            'purchase:blacklist', 'purchase:budgets', 'purchase:collaboration',
            'purchase:portal',
            # 供应商管理
            'masterdata', 'masterdata:suppliers',
            # MRP
            'inventory', 'inventory:mrp',
            # 财务相关
            'finance', 'finance:ap', 'finance:purchase-reconciliation',
            # 报表
            'reports', 'reports:purchase-price-trend', 'reports:slow-moving',
            # 审批
            'workflow', 'workflow:tasks', 'workflow:my-submissions',
            # OA
            'oa', 'oa:schedule', 'accounts:attendance',
        ],
        'sort_order': 6
    },
    {
        'name': '采购人员',
        'code': 'purchaser',
        'description': '负责采购询价、下单、跟踪、到货处理',
        'data_scope': 'SELF',
        'menu_ids': [
            'dashboard',
            # 采购（核心）
            'purchase', 'purchase:requests', 'purchase:comparisons', 'purchase:orders',
            'purchase:goods-receipts', 'purchase:outsource',
            # 供应商
            'masterdata', 'masterdata:suppliers',
            # MRP
            'inventory', 'inventory:mrp',
            # 审批
            'workflow', 'workflow:tasks', 'workflow:my-submissions',
            # OA
            'oa', 'oa:schedule', 'accounts:attendance',
        ],
        'sort_order': 7
    },
    {
        'name': '仓库主管',
        'code': 'warehouse_manager',
        'description': '负责仓库管理、库存控制、物料调配',
        'data_scope': 'DEPARTMENT',
        'menu_ids': [
            'dashboard',
            # 库存管理（核心）
            'inventory', 'inventory:stocks', 'inventory:batches', 'inventory:moves',
            'inventory:transfer', 'inventory:adjustment', 'inventory:alert',
            'inventory:alerts', 'inventory:requisitions', 'inventory:returns',
            'inventory:cost-accounting', 'inventory:spare-parts', 'inventory:data-accuracy',
            # 基础数据
            'masterdata', 'masterdata:items', 'masterdata:warehouses', 'masterdata:locations',
            # 到货
            'purchase', 'purchase:goods-receipts',
            # 报表
            'reports', 'reports:inventory-turnover', 'reports:slow-moving',
            # 审批
            'workflow', 'workflow:tasks', 'workflow:my-submissions',
            # OA
            'oa', 'accounts:attendance',
        ],
        'sort_order': 8
    },
    {
        'name': '仓库管理员',
        'code': 'warehouse_keeper',
        'description': '负责日常出入库、盘点、领料退料',
        'data_scope': 'SELF',
        'menu_ids': [
            'dashboard',
            # 库存操作（核心）
            'inventory', 'inventory:stocks', 'inventory:batches', 'inventory:moves',
            'inventory:transfer', 'inventory:adjustment', 'inventory:requisitions',
            'inventory:returns',
            # 到货
            'purchase', 'purchase:goods-receipts',
            # 基础数据
            'masterdata', 'masterdata:items',
            # 审批
            'workflow', 'workflow:my-submissions',
            # OA
            'oa', 'accounts:attendance',
        ],
        'sort_order': 9
    },
    {
        'name': '生产主管',
        'code': 'production_manager',
        'description': '负责生产计划、排程、工单管理、产能调度',
        'data_scope': 'DEPARTMENT',
        'menu_ids': [
            'dashboard',
            # 生产管理（核心）
            'production', 'production:processes', 'production:plans',
            'production:debug-records', 'production:inspections',
            'production:serial-numbers', 'production:routing', 'production:assembly',
            'production:scheduling', 'production:capacity',
            # MES
            'mes', 'mes:scheduling', 'mes:kanban', 'mes:traceability',
            'mes:spc', 'mes:andon', 'mes:data-acquisition',
            # 工单
            'projects', 'projects:work-orders',
            # 设备
            'equipment', 'equipment:list', 'equipment:fixtures', 'equipment:inspection',
            'equipment:maintenance', 'equipment:oee',
            # 领料
            'inventory', 'inventory:requisitions', 'inventory:returns',
            # 审批
            'workflow', 'workflow:tasks', 'workflow:my-submissions',
            # OA
            'oa', 'accounts:attendance',
        ],
        'sort_order': 10
    },
    {
        'name': '生产操作员',
        'code': 'production_operator',
        'description': '负责生产执行、报工、领料',
        'data_scope': 'SELF',
        'menu_ids': [
            'dashboard',
            # 生产执行
            'production', 'production:processes', 'production:debug-records',
            # MES
            'mes', 'mes:kanban', 'mes:andon',
            # 工单
            'projects', 'projects:work-orders',
            # 领料
            'inventory', 'inventory:requisitions', 'inventory:returns',
            # OA
            'oa', 'accounts:attendance',
        ],
        'sort_order': 11
    },
    {
        'name': '质量工程师',
        'code': 'quality_engineer',
        'description': '负责质量检验、SPC分析、问题追溯',
        'data_scope': 'DEPARTMENT',
        'menu_ids': [
            'dashboard',
            # 质量管理（核心）
            'production', 'production:inspections',
            'mes', 'mes:traceability', 'mes:spc',
            # 采购质检
            'purchase', 'purchase:goods-receipts',
            # 项目验收
            'projects', 'projects:acceptances', 'projects:bugs',
            # 知识库
            'knowledge', 'knowledge:issues',
            # 审批
            'workflow', 'workflow:tasks', 'workflow:my-submissions',
            # OA
            'oa', 'accounts:attendance',
        ],
        'sort_order': 12
    },
    {
        'name': '财务经理',
        'code': 'finance_manager',
        'description': '负责财务管理、成本核算、报表分析',
        'data_scope': 'ALL',
        'menu_ids': [
            'dashboard',
            # 财务管理（核心）
            'finance', 'finance:expenses', 'finance:shared-expenses',
            'finance:ar', 'finance:ap', 'finance:invoices', 'finance:project-costs',
            'finance:collection', 'finance:assets', 'finance:sales-reconciliation',
            'finance:purchase-reconciliation',
            # 库存成本
            'inventory', 'inventory:cost-accounting',
            # 报表
            'reports', 'reports:profitability', 'reports:cost-analysis',
            'reports:aging', 'reports:cash-flow', 'reports:inventory-turnover',
            # 数据分析
            'analytics', 'analytics:project', 'analytics:inventory',
            # 审批
            'workflow', 'workflow:tasks', 'workflow:my-submissions',
            # OA
            'oa', 'oa:schedule', 'accounts:attendance',
        ],
        'sort_order': 13
    },
    {
        'name': '财务人员',
        'code': 'accountant',
        'description': '负责日常财务处理、发票管理、费用报销',
        'data_scope': 'SELF',
        'menu_ids': [
            'dashboard',
            # 财务操作
            'finance', 'finance:expenses', 'finance:ar', 'finance:ap',
            'finance:invoices', 'finance:collection',
            # 审批
            'workflow', 'workflow:tasks', 'workflow:my-submissions',
            # OA
            'oa', 'accounts:attendance',
        ],
        'sort_order': 14
    },
    {
        'name': '售后工程师',
        'code': 'service_engineer',
        'description': '负责设备安装调试、现场服务、售后维护',
        'data_scope': 'SELF',
        'menu_ids': [
            'dashboard',
            # 售后服务（核心）
            'aftersales', 'aftersales:orders',
            'sales', 'sales:service',
            'projects', 'projects:service',
            # 设备档案
            'projects:equipment-archives', 'projects:acceptances',
            # 技术文档
            'projects:drawings', 'projects:documents',
            # 知识库
            'knowledge', 'knowledge:articles', 'knowledge:issues',
            # 审批
            'workflow', 'workflow:tasks', 'workflow:my-submissions',
            # OA
            'oa', 'oa:schedule', 'accounts:attendance',
        ],
        'sort_order': 15
    },
    {
        'name': '行政人事',
        'code': 'hr_admin',
        'description': '负责人事管理、考勤、行政事务',
        'data_scope': 'ALL',
        'menu_ids': [
            'dashboard',
            # OA（核心）
            'oa', 'oa:schedule', 'oa:meeting', 'oa:leave', 'oa:announcement',
            'oa:vehicles', 'oa:vehicle-request', 'oa:assets', 'oa:im',
            'oa:attendance', 'oa:attendance-import',
            # 考勤
            'accounts', 'accounts:attendance',
            # 审批
            'workflow', 'workflow:tasks', 'workflow:my-submissions', 'workflow:config',
        ],
        'sort_order': 16
    },
    {
        'name': '普通员工',
        'code': 'employee',
        'description': '基础权限，可查看工作台、提交审批、考勤打卡',
        'data_scope': 'SELF',
        'menu_ids': [
            'dashboard',
            # 审批
            'workflow', 'workflow:tasks', 'workflow:my-submissions',
            # OA
            'oa', 'oa:schedule', 'oa:leave', 'oa:meeting', 'oa:announcement',
            'oa:vehicle-request', 'accounts:attendance',
        ],
        'sort_order': 17
    },
]


class Command(BaseCommand):
    help = '初始化非标自动化行业预设角色和权限配置'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='强制更新已存在的角色',
        )

    def handle(self, *args, **options):
        force = options.get('force', False)
        created_count = 0
        updated_count = 0
        skipped_count = 0

        self.stdout.write(self.style.NOTICE('开始初始化非标自动化行业预设角色...'))
        self.stdout.write('')

        for role_data in INDUSTRY_ROLES:
            code = role_data['code']
            name = role_data['name']
            
            # 构建权限配置
            permissions = {
                'menu_ids': role_data['menu_ids'],
                'permissions': self._generate_permissions(role_data['menu_ids'])
            }
            
            try:
                role = Role.objects.get(code=code)
                if force:
                    role.name = name
                    role.description = role_data['description']
                    role.data_scope = role_data['data_scope']
                    role.permissions = permissions
                    role.sort_order = role_data['sort_order']
                    role.save()
                    updated_count += 1
                    self.stdout.write(f'  [更新] {name} ({code})')
                else:
                    skipped_count += 1
                    self.stdout.write(f'  [跳过] {name} ({code}) - 已存在')
            except Role.DoesNotExist:
                Role.objects.create(
                    name=name,
                    code=code,
                    description=role_data['description'],
                    data_scope=role_data['data_scope'],
                    permissions=permissions,
                    sort_order=role_data['sort_order'],
                    is_active=True
                )
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'  [创建] {name} ({code})'))

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'完成！创建: {created_count}, 更新: {updated_count}, 跳过: {skipped_count}'
        ))
        
        # 输出角色权限摘要
        self.stdout.write('')
        self.stdout.write(self.style.NOTICE('=== 非标自动化行业角色权限摘要 ==='))
        self.stdout.write('')
        
        summaries = [
            ('总经理', '全部权限 + 报表分析'),
            ('项目经理', '项目全局 + PLM + 技术文档 + 成本'),
            ('技术工程师', 'PLM + BOM + 图纸 + 知识库'),
            ('销售经理', 'CRM + 报价 + 合同 + 客户 + 销售报表'),
            ('销售人员', 'CRM + 报价 + 订单 + 客户'),
            ('采购经理', '采购全流程 + 供应商 + MRP + 采购报表'),
            ('采购人员', '采购申请 + 订单 + 到货'),
            ('仓库主管', '库存全流程 + 库存报表'),
            ('仓库管理员', '出入库 + 盘点 + 领退料'),
            ('生产主管', '生产计划 + MES + 设备 + 工单'),
            ('生产操作员', '报工 + 看板 + 领料'),
            ('质量工程师', '质检 + SPC + 追溯'),
            ('财务经理', '财务全流程 + 成本 + 财务报表'),
            ('财务人员', '应收应付 + 发票 + 报销'),
            ('售后工程师', '售后工单 + 设备档案 + 技术文档'),
            ('行政人事', 'OA + 考勤 + 审批配置'),
            ('普通员工', '工作台 + 审批 + 考勤'),
        ]
        
        for name, desc in summaries:
            self.stdout.write(f'  {name}: {desc}')

    def _generate_permissions(self, menu_ids):
        """根据 menu_ids 生成详细权限列表"""
        permissions = []
        for menu_id in menu_ids:
            if ':' in menu_id:
                # 子菜单，生成 CRUD 权限
                permissions.extend([
                    f'{menu_id}:view',
                    f'{menu_id}:add',
                    f'{menu_id}:edit',
                    f'{menu_id}:delete',
                ])
            else:
                # 模块级权限
                permissions.append(f'{menu_id}:view')
        return permissions
