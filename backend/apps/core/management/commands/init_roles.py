"""
初始化默认角色和权限数据

运行方式：
    python manage.py init_roles
    python manage.py init_roles --force  # 强制重置所有角色
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import Role
from apps.core.permission_config import DEFAULT_ROLES
from apps.core.permission_models_new import DataScope, Permission
from apps.core.permission_service import on_role_permission_change

SCOPE_MAP = {
    'ALL': 'all',
    'all': 'all',
    'DEPARTMENT': 'dept_tree',
    'department': 'dept',
    'department_and_below': 'dept_tree',
    'dept': 'dept',
    'dept_tree': 'dept_tree',
    'SELF': 'self',
    'self': 'self',
    'CUSTOM': 'custom',
    'custom': 'custom',
}


class Command(BaseCommand):
    help = '初始化默认角色和权限数据'

    def _normalize_scope_type(self, scope_type):
        return SCOPE_MAP.get(scope_type, scope_type or 'self')

    def _sync_default_scope(self, role, scope_type):
        DataScope.objects.filter(role=role, module='__default__').delete()
        scope, _ = DataScope.objects.update_or_create(
            role=role,
            module='',
            defaults={'scope_type': self._normalize_scope_type(scope_type)},
        )
        scope.custom_departments.clear()

    def _collect_permission_ids(self, selected_codes):
        if not selected_codes:
            return []

        permissions = list(Permission.active.select_related('parent'))
        permissions_by_code = {permission.code: permission for permission in permissions}
        permissions_by_id = {permission.id: permission for permission in permissions}
        children_by_parent = {}

        for permission in permissions:
            children_by_parent.setdefault(permission.parent_id, []).append(permission)

        selected_ids = set()
        stack = [permissions_by_code[code] for code in selected_codes if code in permissions_by_code]

        while stack:
            permission = stack.pop()
            if permission.id in selected_ids:
                continue

            selected_ids.add(permission.id)

            if permission.parent_id and permission.parent_id in permissions_by_id:
                stack.append(permissions_by_id[permission.parent_id])

            stack.extend(children_by_parent.get(permission.id, []))

        return list(selected_ids)

    def _sync_permissions(self, role, role_config):
        selected_codes = role_config.get('permission_codes') or role_config.get('menu_ids') or []
        if not selected_codes:
            return

        permission_ids = self._collect_permission_ids(selected_codes)
        role.permissions_new.set(Permission.active.filter(id__in=permission_ids))
        on_role_permission_change(role)

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='强制更新所有角色配置（覆盖现有配置）',
        )

    def handle(self, *args, **options):
        force = options.get('force', False)

        self.stdout.write(self.style.NOTICE('开始初始化角色...'))

        created_count = 0
        updated_count = 0
        skipped_count = 0

        with transaction.atomic():
            for role_config in DEFAULT_ROLES:
                code = role_config['code']

                try:
                    role = Role.objects.get(code=code)

                    if force:
                        # 强制更新
                        role.name = role_config['name']
                        role.description = role_config.get('description', '')
                        role.permissions = {}
                        role.is_active = True
                        role.sort_order = DEFAULT_ROLES.index(role_config) * 10
                        role.save(update_fields=['name', 'description', 'permissions', 'is_active', 'sort_order', 'updated_at'])
                        self._sync_default_scope(role, role_config.get('data_scope', 'self'))
                        self._sync_permissions(role, role_config)
                        updated_count += 1
                        self.stdout.write(f'  更新角色: {code} ({role_config["name"]})')
                    else:
                        skipped_count += 1
                        self.stdout.write(f'  跳过已存在: {code}')

                except Role.DoesNotExist:
                    # 检查是否有同名角色
                    existing_by_name = Role.objects.filter(name=role_config['name']).first()
                    if existing_by_name:
                        # 更新现有角色的code
                        existing_by_name.code = code
                        existing_by_name.description = role_config.get('description', '')
                        existing_by_name.permissions = {}
                        existing_by_name.is_active = True
                        existing_by_name.sort_order = DEFAULT_ROLES.index(role_config) * 10
                        existing_by_name.save(update_fields=['code', 'description', 'permissions', 'is_active', 'sort_order', 'updated_at'])
                        self._sync_default_scope(existing_by_name, role_config.get('data_scope', 'self'))
                        self._sync_permissions(existing_by_name, role_config)
                        updated_count += 1
                        self.stdout.write(f'  更新角色(按名称): {code} ({role_config["name"]})')
                    else:
                        # 创建新角色
                        role = Role.objects.create(
                            code=code,
                            name=role_config['name'],
                            description=role_config.get('description', ''),
                            permissions={},
                            is_active=True,
                            sort_order=DEFAULT_ROLES.index(role_config) * 10
                        )
                        self._sync_default_scope(role, role_config.get('data_scope', 'self'))
                        self._sync_permissions(role, role_config)
                        created_count += 1
                        self.stdout.write(self.style.SUCCESS(f'  创建角色: {code} ({role_config["name"]})'))

        # 输出统计
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 50))
        self.stdout.write(f'创建: {created_count} 个角色')
        self.stdout.write(f'更新: {updated_count} 个角色')
        self.stdout.write(f'跳过: {skipped_count} 个角色')
        self.stdout.write(self.style.SUCCESS('角色初始化完成！'))

        # 显示权限说明
        self.stdout.write('')
        self.stdout.write(self.style.NOTICE('权限配置说明：'))
        self.stdout.write('  - 项目/生产/库存数据：全员可查看')
        self.stdout.write('  - 采购/销售数据：相关人员可查看')
        self.stdout.write('  - 财务数据：仅财务人员和管理层可查看')
        self.stdout.write('')
        self.stdout.write('  可在 apps/core/permission_config.py 中修改权限配置')
