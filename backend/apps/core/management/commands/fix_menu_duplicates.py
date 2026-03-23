"""
清理重复菜单项并修复路由路径
"""
from django.core.management.base import BaseCommand
from apps.core.permission_models_new import Permission


class Command(BaseCommand):
    help = '清理重复菜单项并修复路由路径'

    def handle(self, *args, **options):
        # 1. 处理重复菜单：停用旧的，保留新的
        duplicates = [
            # (旧code, 新code)
            ('projects:project', 'projects:list'),
            ('system:user', 'system:users'),
            ('system:role', 'system:roles'),
            ('system:dept', 'system:departments'),
        ]

        for old_code, new_code in duplicates:
            old = Permission.objects.filter(code=old_code).first()
            new = Permission.objects.filter(code=new_code).first()
            if old and new:
                # 迁移子权限到新节点
                moved = Permission.objects.filter(parent=old).update(parent=new)
                old.is_active = False
                old.save(update_fields=['is_active'])
                self.stdout.write(f'停用 {old_code}，迁移 {moved} 个子权限到 {new_code}')

        # 2. 修复路由路径（旧的同步脚本生成了不带前缀的路径）
        route_fixes = {
            'masterdata': '/masterdata/items',
            'masterdata:items': '/masterdata/items',
            'masterdata:customers': '/masterdata/customers',
            'masterdata:suppliers': '/masterdata/suppliers',
            'masterdata:warehouses': '/masterdata/warehouses',
            'masterdata:locations': '/masterdata/locations',
            'system:users': '/system/users',
            'system:roles': '/system/roles',
            'system:departments': '/system/departments',
            'system:code-rules': '/system/code-rules',
            'system': '/system/users',
            'accounts:attendance': '/oa/attendance',
        }

        for code, route in route_fixes.items():
            updated = Permission.objects.filter(code=code).update(route_path=route)
            if updated:
                self.stdout.write(f'修复路由 {code} -> {route}')

        # 3. 修复排序：让子菜单有合理的排序
        sort_fixes = {
            # 项目管理子菜单
            'projects:list': 10,
            'projects:dashboard': 20,
            'projects:tasks': 30,
            'projects:members': 40,
            'projects:bom': 50,
            'projects:drawings': 60,
            'projects:gantt': 70,
            'projects:milestones': 80,
            'projects:time-logs': 90,
            'projects:work-orders': 100,
            'projects:bugs': 110,
            'projects:alerts': 120,
            'projects:acceptances': 130,
            'projects:archives': 140,
            'projects:cost': 150,
            'projects:monitoring': 160,
            'projects:service': 170,
            'projects:equipment-archives': 180,
            'projects:documents': 190,
            'projects:batch-drawing': 200,
            'projects:drawing-bom-link': 210,
            # 系统管理子菜单
            'system:users': 10,
            'system:roles': 20,
            'system:departments': 30,
            'system:code-rules': 40,
            'system:notifications': 50,
            'system:audit-log': 60,
            'system:login-logs': 70,
            'system:config': 80,
            'system:dashboard-config': 90,
            'system:webhooks': 100,
            'system:monitor': 110,
            'system:backup': 120,
            'system:data-dictionary': 130,
            'system:email-templates': 140,
            'system:custom-fields': 150,
            'system:audit-analytics': 160,
            'system:announcements': 170,
            # 一级菜单排序
            'dashboard': 0,
            'sales': 10,
            'projects': 20,
            'purchase': 30,
            'inventory': 40,
            'production': 50,
            'finance': 60,
            'masterdata': 70,
            'reports': 80,
            'analytics': 85,
            'workflow': 90,
            'oa': 95,
            'system': 999,
        }

        for code, order in sort_fixes.items():
            Permission.objects.filter(code=code).update(sort_order=order)

        # 4. 停用重复的库存预警（inventory:alert 和 inventory:alerts 重复）
        alert_old = Permission.objects.filter(code='inventory:alert').first()
        alert_new = Permission.objects.filter(code='inventory:alerts').first()
        if alert_old and alert_new:
            alert_old.is_active = False
            alert_old.save(update_fields=['is_active'])
            self.stdout.write('停用重复的 inventory:alert（保留 inventory:alerts）')

        # 5. 停用旧的 finance:expense（保留 finance:expenses）
        fe_old = Permission.objects.filter(code='finance:expense').first()
        fe_new = Permission.objects.filter(code='finance:expenses').first()
        if fe_old and fe_new:
            Permission.objects.filter(parent=fe_old).update(parent=fe_new)
            fe_old.is_active = False
            fe_old.save(update_fields=['is_active'])
            self.stdout.write('停用重复的 finance:expense（保留 finance:expenses）')

        # 6. 停用旧的 purchase:order（保留 purchase:orders）
        po_old = Permission.objects.filter(code='purchase:order').first()
        po_new = Permission.objects.filter(code='purchase:orders').first()
        if po_old and po_new:
            Permission.objects.filter(parent=po_old).update(parent=po_new)
            po_old.is_active = False
            po_old.save(update_fields=['is_active'])
            self.stdout.write('停用重复的 purchase:order（保留 purchase:orders）')

        self.stdout.write(self.style.SUCCESS('\n菜单清理完成！'))
