"""
初始化角色和权限数据（合并原 init_roles + init_industry_roles）

运行方式：
    python manage.py init_roles
    python manage.py init_roles --force  # 强制重置所有角色权限
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import Role
from apps.core.permission_models_new import DataScope, Permission
from apps.core.permission_service import collect_permission_ids, normalize_scope_type, on_role_permission_change


ROLES = [
    {
        'code': 'admin',
        'name': '系统管理员',
        'description': '系统管理员，拥有全部权限',
        'data_scope': 'all',
        'menu_codes': ['*'],  # All permissions
        'sort_order': 0,
    },
    {
        'code': 'general_manager',
        'name': '总经理',
        'description': '公司管理层，查看全部数据',
        'data_scope': 'all',
        'menu_codes': [
            'dashboard', 'projects', 'design', 'sales', 'supply',
            'manufacturing', 'finance', 'oa', 'system:report',
        ],
        'sort_order': 1,
    },
    {
        'code': 'project_manager',
        'name': '项目经理',
        'description': '负责项目全生命周期管理',
        'data_scope': 'all',
        'menu_codes': [
            'dashboard', 'projects', 'design',
            'sales:quotation', 'sales:order',
            'supply:request', 'supply:order', 'supply:receipt',
            'supply:stock', 'supply:move',
            'manufacturing:plan', 'manufacturing:routing',
            'manufacturing:inspection', 'manufacturing:debug',
            'system:report',
        ],
        'sort_order': 2,
    },
    {
        'code': 'engineer',
        'name': '技术工程师',
        'description': '负责设计、BOM和技术文档',
        'data_scope': 'all',
        'menu_codes': [
            'dashboard', 'projects:list', 'projects:task', 'projects:bom',
            'projects:cost', 'design', 'supply:stock', 'manufacturing:routing',
        ],
        'sort_order': 3,
    },
    {
        'code': 'sales_manager',
        'name': '销售经理',
        'description': '管理销售团队和客户关系',
        'data_scope': 'all',
        'menu_codes': [
            'dashboard', 'sales', 'projects:list',
            'finance:receivable', 'finance:collection', 'finance:reconciliation',
            'system:report',
        ],
        'sort_order': 4,
    },
    {
        'code': 'salesperson',
        'name': '销售员',
        'description': '负责客户开发和订单跟进',
        'data_scope': 'self',
        'menu_codes': [
            'dashboard', 'sales:lead', 'sales:quotation', 'sales:order',
            'sales:contract', 'sales:delivery', 'sales:customer',
            'projects:list',
        ],
        'sort_order': 5,
    },
    {
        'code': 'purchase_manager',
        'name': '采购经理',
        'description': '管理采购流程和供应商',
        'data_scope': 'all',
        'menu_codes': [
            'dashboard', 'supply',
            'finance:payable', 'finance:reconciliation',
            'system:report',
        ],
        'sort_order': 6,
    },
    {
        'code': 'purchaser',
        'name': '采购员',
        'description': '执行采购操作',
        'data_scope': 'self',
        'menu_codes': [
            'dashboard', 'supply:request', 'supply:order', 'supply:receipt',
            'supply:rfq', 'supply:outsource', 'supply:stock',
        ],
        'sort_order': 7,
    },
    {
        'code': 'warehouse_manager',
        'name': '仓库主管',
        'description': '管理仓库和库存',
        'data_scope': 'all',
        'menu_codes': [
            'dashboard', 'supply:stock', 'supply:move', 'supply:mrp',
            'supply:spare', 'supply:receipt', 'system:report',
        ],
        'sort_order': 8,
    },
    {
        'code': 'warehouse_keeper',
        'name': '仓管员',
        'description': '执行出入库操作',
        'data_scope': 'self',
        'menu_codes': [
            'dashboard', 'supply:stock', 'supply:move',
        ],
        'sort_order': 9,
    },
    {
        'code': 'production_manager',
        'name': '生产经理',
        'description': '管理生产计划和执行',
        'data_scope': 'all',
        'menu_codes': [
            'dashboard', 'manufacturing', 'supply:stock', 'supply:move',
            'projects:list', 'projects:bom', 'system:report',
        ],
        'sort_order': 10,
    },
    {
        'code': 'production_operator',
        'name': '生产操作员',
        'description': '执行生产任务',
        'data_scope': 'self',
        'menu_codes': [
            'dashboard', 'manufacturing:plan', 'manufacturing:inspection',
            'manufacturing:debug', 'manufacturing:assembly',
            'manufacturing:kanban', 'supply:move',
        ],
        'sort_order': 11,
    },
    {
        'code': 'quality_engineer',
        'name': '质量工程师',
        'description': '负责质量检验和控制',
        'data_scope': 'all',
        'menu_codes': [
            'dashboard', 'manufacturing:inspection', 'manufacturing:debug',
            'supply:receipt', 'projects:service', 'design:knowledge',
        ],
        'sort_order': 12,
    },
    {
        'code': 'finance_manager',
        'name': '财务经理',
        'description': '管理财务和会计工作',
        'data_scope': 'all',
        'menu_codes': [
            'dashboard', 'finance', 'system:report',
        ],
        'sort_order': 13,
    },
    {
        'code': 'accountant',
        'name': '会计',
        'description': '处理日常财务事务',
        'data_scope': 'self',
        'menu_codes': [
            'dashboard', 'finance:expense', 'finance:receivable', 'finance:payable',
            'finance:invoice', 'finance:collection', 'finance:asset',
            'finance:reconciliation', 'finance:bank_statement',
        ],
        'sort_order': 14,
    },
    {
        'code': 'hr_admin',
        'name': '人事行政',
        'description': '管理人事和行政事务',
        'data_scope': 'all',
        'menu_codes': [
            'dashboard', 'oa', 'system:user', 'system:department',
        ],
        'sort_order': 15,
    },
    {
        'code': 'employee',
        'name': '普通员工',
        'description': '基础权限，可查看项目和提交申请',
        'data_scope': 'self',
        'menu_codes': [
            'dashboard', 'projects:list', 'projects:task',
            'oa:announcement', 'oa:meeting', 'oa:attendance',
            'oa:workflow',
        ],
        'sort_order': 16,
    },
]



class Command(BaseCommand):
    help = '初始化角色和权限数据（含行业预设角色）'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='强制更新已存在的角色权限配置',
        )

    def _sync_role_scope(self, role, scope_type):
        """Set the default DataScope for a role."""
        # Remove legacy __default__ entries
        DataScope.objects.filter(role=role, module='__default__').delete()
        scope, _ = DataScope.objects.update_or_create(
            role=role,
            module='',
            defaults={'scope_type': normalize_scope_type(scope_type)},
        )
        scope.custom_departments.clear()

    def _sync_role_permissions(self, role, menu_codes):
        """Set permissions_new M2M from menu_codes."""
        permission_ids = collect_permission_ids(menu_codes)
        role.permissions_new.set(Permission.active.filter(id__in=permission_ids))
        on_role_permission_change(role)

    def handle(self, *args, **options):
        force = options.get('force', False)
        created_count = 0
        updated_count = 0
        skipped_count = 0

        self.stdout.write(self.style.NOTICE('开始初始化角色...'))
        self.stdout.write('')

        with transaction.atomic():
            for role_data in ROLES:
                code = role_data['code']
                name = role_data['name']

                role = Role.objects.filter(code=code).first()
                if not role:
                    role = Role.objects.filter(name=name).first()
                    if role and role.code != code:
                        role.code = code

                if role:
                    if not force:
                        skipped_count += 1
                        self.stdout.write(f'  [跳过] {name} ({code}) - 已存在')
                        continue

                    # Handle name conflicts: if another role holds this name, rename it
                    name_conflict = Role.objects.filter(name=name).exclude(pk=role.pk).first()
                    if name_conflict:
                        name_conflict.name = f'{name_conflict.name}_{name_conflict.code}'
                        name_conflict.save(update_fields=['name', 'updated_at'])

                    role.name = name
                    role.code = code
                    role.description = role_data['description']
                    role.permissions = {}
                    role.sort_order = role_data['sort_order']
                    role.is_active = True
                    # Self-heal: if a canonical role was previously soft-deleted,
                    # restore it so users assigned to it actually get its permissions.
                    role.is_deleted = False
                    role.deleted_at = None
                    role.save(update_fields=[
                        'name', 'code', 'description', 'permissions',
                        'sort_order', 'is_active', 'is_deleted', 'deleted_at',
                        'updated_at',
                    ])
                    self._sync_role_scope(role, role_data['data_scope'])
                    self._sync_role_permissions(role, role_data['menu_codes'])
                    updated_count += 1
                    self.stdout.write(f'  [更新] {name} ({code})')
                else:
                    role = Role.objects.create(
                        name=name,
                        code=code,
                        description=role_data['description'],
                        permissions={},
                        sort_order=role_data['sort_order'],
                        is_active=True,
                    )
                    self._sync_role_scope(role, role_data['data_scope'])
                    self._sync_role_permissions(role, role_data['menu_codes'])
                    created_count += 1
                    self.stdout.write(self.style.SUCCESS(f'  [创建] {name} ({code})'))

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'完成！创建: {created_count}, 更新: {updated_count}, 跳过: {skipped_count}'
        ))
