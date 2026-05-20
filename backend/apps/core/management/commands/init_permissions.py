"""
初始化权限树数据
幂等操作：按 code 创建或更新权限节点
"""

from django.core.management.base import BaseCommand

from apps.core.permission_models_new import Permission


class Command(BaseCommand):
    help = '初始化权限树数据'

    def handle(self, *args, **options):
        permissions_data = [
            # 系统管理 - 排在最后，仅管理员可见
            {
                'code': 'system',
                'name': '系统管理',
                'type': 'menu',
                'icon': 'Setting',
                'route_path': '/system/users',
                'sort_order': 999,
            },
            {
                'code': 'system:user',
                'name': '用户管理',
                'type': 'menu',
                'parent_code': 'system',
                'route_path': '/system/users',
                'sort_order': 1,
            },
            {
                'code': 'system:user:view',
                'name': '查看用户',
                'type': 'operation',
                'parent_code': 'system:user',
                'resource': 'user',
                'sort_order': 1,
            },
            {
                'code': 'system:user:create',
                'name': '新增用户',
                'type': 'operation',
                'parent_code': 'system:user',
                'resource': 'user',
                'sort_order': 2,
            },
            {
                'code': 'system:user:edit',
                'name': '编辑用户',
                'type': 'operation',
                'parent_code': 'system:user',
                'resource': 'user',
                'sort_order': 3,
            },
            {
                'code': 'system:user:delete',
                'name': '删除用户',
                'type': 'operation',
                'parent_code': 'system:user',
                'resource': 'user',
                'sort_order': 4,
            },
            {
                'code': 'system:role',
                'name': '角色管理',
                'type': 'menu',
                'parent_code': 'system',
                'route_path': '/system/roles',
                'sort_order': 2,
            },
            {
                'code': 'system:role:view',
                'name': '查看角色',
                'type': 'operation',
                'parent_code': 'system:role',
                'resource': 'role',
                'sort_order': 1,
            },
            {
                'code': 'system:role:create',
                'name': '新增角色',
                'type': 'operation',
                'parent_code': 'system:role',
                'resource': 'role',
                'sort_order': 2,
            },
            {
                'code': 'system:role:edit',
                'name': '编辑角色',
                'type': 'operation',
                'parent_code': 'system:role',
                'resource': 'role',
                'sort_order': 3,
            },
            {
                'code': 'system:role:delete',
                'name': '删除角色',
                'type': 'operation',
                'parent_code': 'system:role',
                'resource': 'role',
                'sort_order': 4,
            },
            {
                'code': 'system:dept',
                'name': '部门管理',
                'type': 'menu',
                'parent_code': 'system',
                'route_path': '/system/departments',
                'sort_order': 3,
            },
            {
                'code': 'system:dept:view',
                'name': '查看部门',
                'type': 'operation',
                'parent_code': 'system:dept',
                'resource': 'department',
                'sort_order': 1,
            },
            {
                'code': 'system:dept:create',
                'name': '新增部门',
                'type': 'operation',
                'parent_code': 'system:dept',
                'resource': 'department',
                'sort_order': 2,
            },
            {
                'code': 'system:dept:edit',
                'name': '编辑部门',
                'type': 'operation',
                'parent_code': 'system:dept',
                'resource': 'department',
                'sort_order': 3,
            },
            {
                'code': 'system:dept:delete',
                'name': '删除部门',
                'type': 'operation',
                'parent_code': 'system:dept',
                'resource': 'department',
                'sort_order': 4,
            },
            # 项目管理
            {
                'code': 'projects',
                'name': '项目管理',
                'type': 'menu',
                'icon': 'Folder',
                'route_path': '/projects',
                'sort_order': 10,
            },
            {
                'code': 'projects:project',
                'name': '项目列表',
                'type': 'menu',
                'parent_code': 'projects',
                'route_path': '/projects/list',
                'sort_order': 1,
            },
            {
                'code': 'projects:project:view',
                'name': '查看项目',
                'type': 'operation',
                'parent_code': 'projects:project',
                'resource': 'project',
                'sort_order': 1,
            },
            {
                'code': 'projects:project:create',
                'name': '创建项目',
                'type': 'operation',
                'parent_code': 'projects:project',
                'resource': 'project',
                'sort_order': 2,
            },
            {
                'code': 'projects:project:edit',
                'name': '编辑项目',
                'type': 'operation',
                'parent_code': 'projects:project',
                'resource': 'project',
                'sort_order': 3,
            },
            {
                'code': 'projects:project:delete',
                'name': '删除项目',
                'type': 'operation',
                'parent_code': 'projects:project',
                'resource': 'project',
                'sort_order': 4,
            },
            {
                'code': 'projects:bom',
                'name': 'BOM管理',
                'type': 'menu',
                'parent_code': 'projects',
                'route_path': '/projects/bom',
                'sort_order': 2,
            },
            {
                'code': 'projects:bom:view',
                'name': '查看BOM',
                'type': 'operation',
                'parent_code': 'projects:bom',
                'resource': 'bom',
                'sort_order': 1,
            },
            {
                'code': 'projects:bom:create',
                'name': '创建BOM',
                'type': 'operation',
                'parent_code': 'projects:bom',
                'resource': 'bom',
                'sort_order': 2,
            },
            {
                'code': 'projects:bom:edit',
                'name': '编辑BOM',
                'type': 'operation',
                'parent_code': 'projects:bom',
                'resource': 'bom',
                'sort_order': 3,
            },
            {
                'code': 'projects:bom:view_price',
                'name': '查看BOM单价',
                'type': 'field',
                'parent_code': 'projects:bom',
                'resource': 'bom',
                'field_name': 'unit_price',
                'sort_order': 10,
            },
            # 采购管理
            {
                'code': 'purchase',
                'name': '采购管理',
                'type': 'menu',
                'icon': 'ShoppingCart',
                'route_path': '/purchase',
                'sort_order': 20,
            },
            {
                'code': 'purchase:order',
                'name': '采购订单',
                'type': 'menu',
                'parent_code': 'purchase',
                'route_path': '/purchase/orders',
                'sort_order': 1,
            },
            {
                'code': 'purchase:order:view',
                'name': '查看采购单',
                'type': 'operation',
                'parent_code': 'purchase:order',
                'resource': 'purchase_order',
                'sort_order': 1,
            },
            {
                'code': 'purchase:order:create',
                'name': '创建采购单',
                'type': 'operation',
                'parent_code': 'purchase:order',
                'resource': 'purchase_order',
                'sort_order': 2,
            },
            {
                'code': 'purchase:order:edit',
                'name': '编辑采购单',
                'type': 'operation',
                'parent_code': 'purchase:order',
                'resource': 'purchase_order',
                'sort_order': 3,
            },
            {
                'code': 'purchase:order:delete',
                'name': '删除采购单',
                'type': 'operation',
                'parent_code': 'purchase:order',
                'resource': 'purchase_order',
                'sort_order': 4,
            },
            {
                'code': 'purchase:order:approve',
                'name': '审批采购单',
                'type': 'operation',
                'parent_code': 'purchase:order',
                'resource': 'purchase_order',
                'sort_order': 5,
            },
            {
                'code': 'purchase:order:view_price',
                'name': '查看采购单价',
                'type': 'field',
                'parent_code': 'purchase:order',
                'resource': 'purchase_order',
                'field_name': 'unit_price',
                'sort_order': 10,
            },
            # 财务管理
            {
                'code': 'finance',
                'name': '财务管理',
                'type': 'menu',
                'icon': 'Money',
                'route_path': '/finance',
                'sort_order': 30,
            },
            {
                'code': 'finance:expense',
                'name': '费用管理',
                'type': 'menu',
                'parent_code': 'finance',
                'route_path': '/finance/expenses',
                'sort_order': 1,
            },
            {
                'code': 'finance:expense:view',
                'name': '查看费用',
                'type': 'operation',
                'parent_code': 'finance:expense',
                'resource': 'expense',
                'sort_order': 1,
            },
            {
                'code': 'finance:expense:create',
                'name': '创建费用',
                'type': 'operation',
                'parent_code': 'finance:expense',
                'resource': 'expense',
                'sort_order': 2,
            },
            {
                'code': 'finance:expense:approve',
                'name': '审批费用',
                'type': 'operation',
                'parent_code': 'finance:expense',
                'resource': 'expense',
                'sort_order': 3,
            },
            {
                'code': 'finance:expense:view_amount',
                'name': '查看费用金额',
                'type': 'field',
                'parent_code': 'finance:expense',
                'resource': 'expense',
                'field_name': 'amount',
                'sort_order': 10,
            },
        ]

        created_count = 0
        updated_count = 0
        parent_map = {}

        # 第一遍：创建或更新所有节点（不设置 parent）
        for perm_data in permissions_data:
            parent_code = perm_data.pop('parent_code', None)
            code = perm_data['code']

            perm, created = Permission.objects.update_or_create(code=code, defaults=perm_data)

            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'创建权限: {code} - {perm_data["name"]}'))
            else:
                updated_count += 1
                self.stdout.write(f'更新权限: {code} - {perm_data["name"]}')

            if parent_code:
                parent_map[code] = parent_code

        # 第二遍：设置父节点关系
        for code, parent_code in parent_map.items():
            try:
                perm = Permission.objects.get(code=code)
                parent = Permission.objects.get(code=parent_code)
                perm.parent = parent
                perm.save()
            except Permission.DoesNotExist:
                self.stdout.write(self.style.WARNING(f'警告: 找不到权限节点 {code} 或其父节点 {parent_code}'))

        self.stdout.write(self.style.SUCCESS(f'\n完成! 创建 {created_count} 个权限，更新 {updated_count} 个权限'))
