"""
初始化权限树数据
幂等操作：按 code 创建或更新权限节点

权限码规范：
- 菜单权限：与前端 router menuId 一致（如 purchase:orders）
- 操作权限：module:resource:action（如 purchase:purchase_order:create）
  其中 resource 与 ViewSet 的 permission_resource 一致
- 字段权限：module:resource:field_name（如 purchase:purchase_order:unit_price）
"""

from django.core.management.base import BaseCommand

from apps.core.permission_models_new import Permission


# 标准 CRUD 操作
CRUD_ACTIONS = [
    ('view', '查看', 1),
    ('create', '新增', 2),
    ('edit', '编辑', 3),
    ('delete', '删除', 4),
]

CRUD_APPROVE = CRUD_ACTIONS + [('approve', '审批', 5)]


def menu(code, name, sort_order, icon=None, route_path=None, parent_code=None):
    d = {'code': code, 'name': name, 'type': 'menu', 'sort_order': sort_order}
    if icon:
        d['icon'] = icon
    if route_path:
        d['route_path'] = route_path
    if parent_code:
        d['parent_code'] = parent_code
    return d


# 说明（审计 C2）：以下 ops()/field_perm() 是为“操作级 / 字段级”细粒度权限预留的脚手架，
# 但 build_permission_tree() 目前【有意】只调用 menu()，从不调用它们——本系统按
# “菜单级粒度”授权：持有某菜单码即可对该模块下资源做任意 view/create/edit/delete
# （后端经 PermissionMixin._has_module_menu_access 兜底，前端经 hasPermission 的祖先通配）。
# 因此数据库中没有 type='operation'/'field' 的权限记录，has_permission('x:y:create')
# 对非超管恒走菜单兜底、字段脱敏（get_hidden_fields）恒为空。
# 这两个函数【保留】是为将来若需启用真正的操作/字段级 RBAC 时可直接接入（见 README/审计报告 C2）。
# 切勿误以为细粒度权限“已生效”——启用前必须在 build_permission_tree 中实际调用它们并重跑
# init_permissions + init_roles，且需同步评估前端与 13 角色测试套件。
def ops(parent_code, resource, actions=None):
    if actions is None:
        actions = CRUD_ACTIONS
    results = []
    action_names = {
        'view': '查看', 'create': '新增', 'edit': '编辑',
        'delete': '删除', 'approve': '审批', 'export': '导出',
        'import': '导入', 'print': '打印',
    }
    for act, label, sort in actions:
        results.append({
            'code': f'{parent_code}:{act}',
            'name': f'{action_names.get(act, act)}',
            'type': 'operation',
            'parent_code': parent_code,
            'resource': resource,
            'sort_order': sort,
        })
    return results


def field_perm(parent_code, resource, field_name, name, sort_order=10):
    return {
        'code': f'{parent_code}:{field_name}',
        'name': name,
        'type': 'field',
        'parent_code': parent_code,
        'resource': resource,
        'field_name': field_name,
        'sort_order': sort_order,
    }


# ===================================================================
# 操作级 / 字段级权限（审计 C2 整改）
#
# 操作权限码规范 = {module}:{resource}:{action}，其中 module/resource 与对应 ViewSet 的
# permission_module / permission_resource 完全一致（PermissionMixin 据此判断操作级限制）。
# parent_menu 仅用于后台 RBAC 权限树的展示归类，不参与鉴权判定。
#
# 向后兼容的关键：这些操作权限被“可选启用（opt-in）”地执行——只有当某角色对某 resource
# 已被授予部分 CRUD 却缺失某个 action 时才拒绝该 action；未被授予任何操作权限的角色回落到
# 菜单级兜底，保持全 CRUD。为保证开箱即用行为不变，本命令随后会把每个 resource 的“全部
# CRUD”一并授予“当前已能通过菜单访问该模块”的角色（见 Command._grant_defaults_to_roles）。
# ===================================================================

# (module, resource, parent_menu_code) —— 覆盖各模块关键 ViewSet
OPERATION_RESOURCES = [
    ('projects', 'project', 'projects:list', '项目'),
    ('projects', 'task', 'projects:task', '任务'),
    ('sales', 'quotation', 'sales:quotation', '技术报价'),
    ('sales', 'order', 'sales:order', '销售订单'),
    ('sales', 'contract', 'sales:contract', '销售合同'),
    ('sales', 'delivery', 'sales:delivery', '发货单'),
    ('masterdata', 'item', 'supply:stock', '物料'),
    ('masterdata', 'customer', 'sales:customer', '客户'),
    ('masterdata', 'supplier', 'supply:order', '供应商'),
    ('inventory', 'stock', 'supply:stock', '库存'),
    ('inventory', 'stock_move', 'supply:move', '库存移动'),
    ('purchase', 'request', 'supply:request', '采购申请'),
    ('purchase', 'purchase_order', 'supply:order', '采购订单'),
    ('purchase', 'goods_receipt', 'supply:receipt', '到货验收'),
    ('purchase', 'inspection', 'supply:receipt', '来料检验'),
    ('finance', 'fixed_asset', 'finance:asset', '固定资产'),
    ('finance', 'collection_plan', 'finance:collection', '收款计划'),
    ('finance', 'journal_voucher', 'finance', '记账凭证'),
    ('accounts', 'user', 'system:user', '用户'),
    ('accounts', 'role', 'system:role', '角色'),
    ('accounts', 'department', 'system:department', '部门'),
]

# 敏感字段（成本/价格/信用额度）—— 字段名均取自各模型真实字段。
# (module, resource, parent_menu_code, [(field_name, label), ...])
SENSITIVE_FIELDS = [
    ('masterdata', 'item', 'supply:stock', [
        ('standard_cost', '标准成本'),
        ('purchase_price', '采购单价'),
        ('last_purchase_price', '最近采购价'),
        ('sale_price', '销售单价'),
    ]),
    ('masterdata', 'customer', 'sales:customer', [
        ('credit_limit', '信用额度'),
    ]),
    ('inventory', 'stock', 'supply:stock', [
        ('weighted_avg_cost', '加权平均成本'),
    ]),
    ('inventory', 'stock_move', 'supply:move', [
        ('unit_cost', '移动单价'),
    ]),
]


def build_operation_and_field_perms():
    """构建操作级 + 字段级权限节点列表（供 build_permission_tree 追加）。"""
    perms = []
    for module, resource, parent_menu, label in OPERATION_RESOURCES:
        prefix = f'{module}:{resource}'
        for act, act_label, sort in CRUD_ACTIONS:
            perms.append({
                'code': f'{prefix}:{act}',
                'name': f'{label}-{act_label}',
                'type': 'operation',
                'parent_code': parent_menu,
                'resource': resource,
                'sort_order': 100 + sort,
            })
    for module, resource, parent_menu, fields in SENSITIVE_FIELDS:
        prefix = f'{module}:{resource}'
        for i, (field_name, field_label) in enumerate(fields, start=1):
            perms.append({
                # code 用 :field: 段与操作码区分，get_hidden_fields 按 code 前缀 + field_name 匹配
                'code': f'{prefix}:field:{field_name}',
                'name': f'{field_label}(可见)',
                'type': 'field',
                'parent_code': parent_menu,
                'resource': resource,
                'field_name': field_name,
                'sort_order': 200 + i,
            })
    return perms


def build_permission_tree():
    """构建完整权限树 — 9大类菜单结构"""
    tree = []

    # ===================== 工作台 =====================
    tree.append(menu('dashboard', '工作台', 1, icon='Odometer', route_path='/dashboard'))

    # ===================== 项目中心 =====================
    tree.append(menu('projects', '项目中心', 10, icon='Briefcase', route_path='/projects'))
    tree.append(menu('projects:list', '项目总览', 1, route_path='/projects', parent_code='projects'))
    tree.append(menu('projects:task', '任务管理', 2, route_path='/projects/tasks', parent_code='projects'))
    tree.append(menu('projects:bom', 'BOM管理', 3, route_path='/projects/bom', parent_code='projects'))
    tree.append(menu('projects:gantt', '甘特图', 4, route_path='/projects/gantt', parent_code='projects'))
    tree.append(menu('projects:timelog', '工时记录', 5, route_path='/projects/time-logs', parent_code='projects'))
    tree.append(menu('projects:milestone', '里程碑', 6, route_path='/projects/milestones', parent_code='projects'))
    tree.append(menu('projects:installation', '安装调试', 7, route_path='/projects/installation-tasks', parent_code='projects'))
    tree.append(menu('projects:acceptance', '验收管理', 8, route_path='/projects/acceptances', parent_code='projects'))
    tree.append(menu('projects:service', '售后工单', 9, icon='Headset', route_path='/projects/service-orders', parent_code='projects'))
    tree.append(menu('projects:cost', '项目成本', 10, route_path='/projects/cost-dashboard', parent_code='projects'))

    # ===================== 营销管理 =====================
    tree.append(menu('sales', '营销管理', 20, icon='TrendCharts', route_path='/sales'))
    tree.append(menu('sales:customer', '客户管理', 1, route_path='/masterdata/customers', parent_code='sales'))
    tree.append(menu('sales:lead', '商机线索', 2, route_path='/sales/leads', parent_code='sales'))
    tree.append(menu('sales:quotation', '技术报价', 3, route_path='/sales/quotations', parent_code='sales'))
    tree.append(menu('sales:order', '销售订单', 4, route_path='/sales/orders', parent_code='sales'))
    tree.append(menu('sales:contract', '销售合同', 5, route_path='/sales/contracts', parent_code='sales'))
    tree.append(menu('sales:delivery', '发货管理', 6, route_path='/sales/delivery-orders', parent_code='sales'))
    tree.append(menu('sales:analysis', '销售分析', 7, route_path='/sales/analysis', parent_code='sales'))

    # ===================== 研发设计 =====================
    tree.append(menu('design', '研发设计', 30, icon='Edit', route_path='/design'))
    tree.append(menu('design:ecn', '设计变更', 1, route_path='/projects/ecn', parent_code='design'))
    tree.append(menu('design:drawing', '图纸管理', 2, route_path='/projects/drawings', parent_code='design'))
    tree.append(menu('design:document', '技术文档', 3, route_path='/projects/tech-documents', parent_code='design'))
    tree.append(menu('design:bom_compare', 'BOM对比', 4, route_path='/plm/bom-compare', parent_code='design'))
    tree.append(menu('design:cad_import', 'CAD-BOM导入', 5, route_path='/plm/cad-bom-import', parent_code='design'))
    tree.append(menu('design:knowledge', '知识库', 6, route_path='/knowledge/articles', parent_code='design'))

    # ===================== 供应链 =====================
    tree.append(menu('supply', '供应链', 40, icon='Connection', route_path='/supply'))
    tree.append(menu('supply:request', '采购申请', 1, route_path='/purchase/requests', parent_code='supply'))
    tree.append(menu('supply:order', '采购订单', 2, route_path='/purchase/orders', parent_code='supply'))
    tree.append(menu('supply:receipt', '到货验收', 3, route_path='/purchase/goods-receipts', parent_code='supply'))
    tree.append(menu('supply:rfq', '询价比价', 4, route_path='/purchase/comparisons', parent_code='supply'))
    tree.append(menu('supply:outsource', '外协加工', 5, route_path='/purchase/outsource', parent_code='supply'))
    tree.append(menu('supply:stock', '库存查询', 6, route_path='/inventory/stocks', parent_code='supply'))
    tree.append(menu('supply:move', '出入库', 7, route_path='/inventory/moves', parent_code='supply'))
    tree.append(menu('supply:mrp', 'MRP运算', 8, route_path='/inventory/mrp', parent_code='supply'))
    tree.append(menu('supply:spare', '备件管理', 9, route_path='/inventory/spare-parts', parent_code='supply'))

    # ===================== 生产制造 =====================
    tree.append(menu('manufacturing', '生产制造', 50, icon='SetUp', route_path='/manufacturing'))
    tree.append(menu('manufacturing:plan', '生产计划', 1, route_path='/production/plans', parent_code='manufacturing'))
    tree.append(menu('manufacturing:routing', '工艺路线', 2, route_path='/production/routing-templates', parent_code='manufacturing'))
    tree.append(menu('manufacturing:aps', 'APS排程', 3, route_path='/mes/scheduling', parent_code='manufacturing'))
    tree.append(menu('manufacturing:kanban', '生产看板', 4, route_path='/mes/kanban', parent_code='manufacturing'))
    tree.append(menu('manufacturing:inspection', '质量检验', 5, route_path='/production/inspections', parent_code='manufacturing'))
    tree.append(menu('manufacturing:equipment', '设备管理', 6, route_path='/equipment/list', parent_code='manufacturing'))
    tree.append(menu('manufacturing:assembly', '装配指导', 7, route_path='/production/assembly-guides', parent_code='manufacturing'))
    tree.append(menu('manufacturing:sn', '序列号追溯', 8, route_path='/production/serial-numbers', parent_code='manufacturing'))
    tree.append(menu('manufacturing:debug', '调试记录', 9, route_path='/production/debug-records', parent_code='manufacturing'))

    # ===================== 财务管理 =====================
    tree.append(menu('finance', '财务管理', 60, icon='Wallet', route_path='/finance'))
    tree.append(menu('finance:receivable', '应收管理', 1, route_path='/finance/ar', parent_code='finance'))
    tree.append(menu('finance:payable', '应付管理', 2, route_path='/finance/ap', parent_code='finance'))
    tree.append(menu('finance:bank_statement', '银行流水', 3, route_path='/finance/bank-statements', parent_code='finance'))
    tree.append(menu('finance:invoice', '发票管理', 4, route_path='/finance/invoices', parent_code='finance'))
    tree.append(menu('finance:expense', '费用管理', 5, route_path='/finance/expenses', parent_code='finance'))
    tree.append(menu('finance:asset', '固定资产', 6, route_path='/finance/assets', parent_code='finance'))
    tree.append(menu('finance:collection', '收款计划', 7, route_path='/finance/collection-plans', parent_code='finance'))
    tree.append(menu('finance:reconciliation', '对账管理', 8, route_path='/finance/purchase-reconciliation', parent_code='finance'))
    tree.append(menu('finance:payment_reconciliation', '付款核销工作台', 9, route_path='/finance/payment-reconciliation', parent_code='finance'))
    tree.extend(ops('finance:payment_reconciliation', 'payable_item'))

    # ===================== 办公协同 =====================
    tree.append(menu('oa', '办公协同', 70, icon='ChatDotSquare', route_path='/oa'))
    tree.append(menu('oa:workflow', '审批中心', 1, route_path='/workflow/tasks', parent_code='oa'))
    tree.append(menu('oa:attendance', '考勤管理', 2, route_path='/oa/attendance', parent_code='oa'))
    tree.append(menu('oa:meeting', '会议日程', 3, route_path='/oa/meeting', parent_code='oa'))
    tree.append(menu('oa:announcement', '公告通知', 4, route_path='/oa/announcement', parent_code='oa'))
    tree.append(menu('oa:vehicle', '车辆管理', 5, route_path='/oa/vehicles', parent_code='oa'))
    tree.append(menu('oa:asset', '资产管理', 6, route_path='/oa/assets', parent_code='oa'))

    # ===================== 系统管理 =====================
    tree.append(menu('system', '系统管理', 999, icon='Setting', route_path='/system'))
    tree.append(menu('system:user', '用户管理', 1, route_path='/system/users', parent_code='system'))
    tree.append(menu('system:role', '角色权限', 2, route_path='/system/roles', parent_code='system'))
    tree.append(menu('system:department', '部门管理', 3, route_path='/system/departments', parent_code='system'))
    tree.append(menu('system:report', '报表中心', 4, route_path='/reports/profitability', parent_code='system'))
    tree.append(menu('system:dict', '数据字典', 5, route_path='/system/data-dictionary', parent_code='system'))
    tree.append(menu('system:config', '系统配置', 6, route_path='/system/config', parent_code='system'))
    tree.append(menu('system:audit', '审计日志', 7, route_path='/system/audit-log', parent_code='system'))
    # 注:软件升级不再作为独立菜单/页面，已收进左上角版本徽标(VersionBadge)。
    # 升级权限沿用 hasPermission 的祖先通配:超管('*')或持有 'system' 菜单者即可在徽标里升级/回滚。

    # 追加操作级 + 字段级权限节点（审计 C2 整改）
    tree.extend(build_operation_and_field_perms())

    return tree


class Command(BaseCommand):
    help = '初始化权限树数据（幂等，可重复执行）'

    def handle(self, *args, **options):
        permissions_data = build_permission_tree()

        created_count = 0
        updated_count = 0
        parent_map = {}

        for perm_data in permissions_data:
            parent_code = perm_data.pop('parent_code', None)
            code = perm_data['code']

            defaults = {k: v for k, v in perm_data.items() if k != 'code'}
            defaults.setdefault('is_active', True)
            defaults['is_deleted'] = False
            perm, created = Permission.objects.update_or_create(code=code, defaults=defaults)

            if created:
                created_count += 1
            else:
                updated_count += 1

            if parent_code:
                parent_map[code] = parent_code

        for code, parent_code in parent_map.items():
            try:
                perm = Permission.objects.get(code=code)
                parent = Permission.objects.get(code=parent_code)
                if perm.parent_id != parent.id:
                    perm.parent = parent
                    perm.save(update_fields=['parent'])
            except Permission.DoesNotExist:
                self.stdout.write(self.style.WARNING(f'警告: 找不到 {code} 或父节点 {parent_code}'))

        self.stdout.write(self.style.SUCCESS(
            f'权限树初始化完成: 创建 {created_count} 条，更新 {updated_count} 条，总计 {created_count + updated_count} 条'
        ))

        granted = self._grant_defaults_to_roles()
        self.stdout.write(self.style.SUCCESS(
            f'操作级/字段级权限默认授予完成: 新增角色-权限关联 {granted} 条（幂等）'
        ))

    def _grant_defaults_to_roles(self):
        """
        把每个 resource 的“全部 CRUD 操作权限 + 全部敏感字段权限”授予“当前已能通过菜单
        访问该 module 的角色”，从而保证开箱即用行为不变（default = unchanged）：

        - 仅授予“已可访问”的角色 —— 复用 PermissionMixin 运行期的两条放行路径
          （菜单祖先通配 + MODULE_MENU_MAP 前缀），确保不产生任何越权（不会给无关角色发放
          能触发 _has_module_menu_access 的权限码）。
        - 对某 resource 一次性授予整套 CRUD/字段权限，绝不产生“部分授予”，因此操作级校验
          对默认角色恒为放行；字段级脱敏对默认角色恒为不屏蔽。
        - 幂等：使用 RolePermission.get_or_create，仅新增缺失关联，从不删除既有授权。

        注意执行顺序：bootstrap 中 init_permissions 先于 init_roles 运行；首次全新初始化时
        角色尚不存在，本步骤为空。init_roles 之后（或再次运行本命令）本步骤即补齐授权。
        """
        # 延迟导入，避免管理命令模块级依赖 accounts/mixin
        from apps.accounts.models import Role
        from apps.core.permission_mixin import MODULE_MENU_MAP
        from apps.core.permission_models_new import RolePermission
        from apps.core.permission_service import on_role_permission_change

        def role_can_access(menu_codes, module, resource):
            """镜像 PermissionMixin 的放行判定（基于角色所持菜单码）。"""
            # (A) 菜单祖先通配：持有 module 或 module:resource
            if module in menu_codes or f'{module}:{resource}' in menu_codes:
                return True
            # (B) MODULE_MENU_MAP 前缀映射
            for prefix in MODULE_MENU_MAP.get(module, []):
                for code in menu_codes:
                    if code == prefix or code.startswith(prefix + ':'):
                        return True
            return False

        # 预取所有已种子化的操作/字段权限对象，按 (module, resource) 归组
        by_resource = {}
        for module, resource, _parent, _label in OPERATION_RESOURCES:
            by_resource.setdefault((module, resource), [])
        for module, resource, _parent, _fields in SENSITIVE_FIELDS:
            by_resource.setdefault((module, resource), [])

        for (module, resource) in list(by_resource.keys()):
            prefix = f'{module}:{resource}:'
            perms = list(
                Permission.objects.filter(
                    type__in=('operation', 'field'),
                    is_active=True,
                    is_deleted=False,
                    code__startswith=prefix,
                )
            )
            by_resource[(module, resource)] = perms

        granted_count = 0
        for role in Role.objects.all():
            # 角色当前所持“菜单码”集合（只看 type='menu'，避免用操作/字段码自我扩张）
            menu_codes = set(
                role.permissions_new.filter(type='menu').values_list('code', flat=True)
            )
            if not menu_codes:
                continue
            touched = False
            for (module, resource), perms in by_resource.items():
                if not perms:
                    continue
                if not role_can_access(menu_codes, module, resource):
                    continue
                for perm in perms:
                    _, created = RolePermission.objects.get_or_create(role=role, permission=perm)
                    if created:
                        granted_count += 1
                        touched = True
            if touched:
                on_role_permission_change(role)

        return granted_count
