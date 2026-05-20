"""
初始化系统数据
创建基础角色、部门和示例数据
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.accounts.models import Department, Role
from apps.core.permission_models_new import DataScope

User = get_user_model()

SCOPE_MAP = {
    'ALL': 'all',
    'DEPARTMENT': 'dept_tree',
    'SELF': 'self',
}


class Command(BaseCommand):
    help = '初始化系统基础数据'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('开始初始化数据...'))

        # 1. 创建部门
        self.stdout.write('创建部门...')
        departments = [
            {'name': '总经办', 'code': 'GM', 'description': '总经理办公室'},
            {'name': '销售部', 'code': 'SALES', 'description': '负责销售业务'},
            {'name': '采购部', 'code': 'PURCHASE', 'description': '负责采购业务'},
            {'name': '仓储部', 'code': 'WAREHOUSE', 'description': '负责仓储管理'},
            {'name': 'IT部', 'code': 'IT', 'description': '信息技术部'},
            {'name': '财务部', 'code': 'FINANCE', 'description': '财务管理'},
            {'name': '项目部', 'code': 'PROJECT', 'description': '项目管理'},
        ]

        dept_objs = {}
        for dept_data in departments:
            dept, created = Department.objects.get_or_create(
                code=dept_data['code'], defaults={'name': dept_data['name'], 'description': dept_data['description']}
            )
            dept_objs[dept_data['code']] = dept
            if created:
                self.stdout.write(self.style.SUCCESS(f'  ✓ 创建部门: {dept.name}'))
            else:
                self.stdout.write(f'  - 部门已存在: {dept.name}')

        # 2. 创建角色
        self.stdout.write('创建角色...')
        roles = [
            {'name': '系统管理员', 'code': 'admin', 'description': '系统超级管理员，拥有所有权限', 'data_scope': 'ALL'},
            {'name': '总经理', 'code': 'general_manager', 'description': '总经理，查看所有数据', 'data_scope': 'ALL'},
            {'name': '销售经理', 'code': 'sales_manager', 'description': '销售部门经理', 'data_scope': 'DEPARTMENT'},
            {'name': '销售人员', 'code': 'salesperson', 'description': '销售人员', 'data_scope': 'SELF'},
            {'name': '采购经理', 'code': 'purchase_manager', 'description': '采购部门经理', 'data_scope': 'DEPARTMENT'},
            {'name': '采购人员', 'code': 'purchaser', 'description': '采购人员', 'data_scope': 'SELF'},
            {
                'name': '仓库管理员',
                'code': 'warehouse_keeper',
                'description': '仓库管理人员',
                'data_scope': 'DEPARTMENT',
            },
            {'name': '项目经理', 'code': 'project_manager', 'description': '项目管理人员', 'data_scope': 'SELF'},
            {'name': '财务人员', 'code': 'accountant', 'description': '财务管理人员', 'data_scope': 'ALL'},
            {'name': '普通员工', 'code': 'employee', 'description': '基础权限员工', 'data_scope': 'SELF'},
        ]

        role_objs = {}
        for role_data in roles:
            created = False
            role = Role.objects.filter(code=role_data['code']).first()
            if role:
                role.name = role_data['name']
                role.description = role_data['description']
                role.permissions = {}
                role.is_active = True
                role.save(update_fields=['name', 'description', 'permissions', 'is_active', 'updated_at'])
            else:
                role = Role.objects.filter(name=role_data['name']).first()
                if role:
                    role.code = role_data['code']
                    role.description = role_data['description']
                    role.permissions = {}
                    role.is_active = True
                    role.save(update_fields=['code', 'description', 'permissions', 'is_active', 'updated_at'])
                else:
                    role = Role.objects.create(
                        code=role_data['code'],
                        name=role_data['name'],
                        description=role_data['description'],
                        permissions={},
                        is_active=True,
                    )
                    created = True
            DataScope.objects.filter(role=role, module='__default__').delete()
            scope, _ = DataScope.objects.update_or_create(
                role=role, module='', defaults={'scope_type': SCOPE_MAP.get(role_data['data_scope'], 'self')}
            )
            scope.custom_departments.clear()
            role_objs[role_data['code']] = role
            if created:
                self.stdout.write(self.style.SUCCESS(f'  ✓ 创建角色: {role.name}'))
            else:
                self.stdout.write(f'  - 角色已存在: {role.name}')

        # 3. 更新admin用户
        self.stdout.write('更新admin用户...')
        try:
            admin = User.objects.get(username='admin')
            if not admin.department:
                admin.department = dept_objs['GM']
                admin.employee_id = 'EMP001'
                admin.save()
                self.stdout.write(self.style.SUCCESS('  ✓ 更新admin用户信息'))

            # 为admin分配系统管理员角色
            if not admin.role or admin.role.code != 'admin':
                admin.role = role_objs['admin']
                admin.save()
                self.stdout.write(self.style.SUCCESS('  ✓ 为admin分配系统管理员角色'))
            admin.roles.set([role_objs['admin']])
        except User.DoesNotExist:
            self.stdout.write(self.style.WARNING('  ! admin用户不存在'))

        # 4. 创建示例用户
        self.stdout.write('创建示例用户...')
        sample_users = [
            {
                'username': 'sales_manager',
                'email': 'sales.manager@erp.com',
                'first_name': '张',
                'last_name': '销售经理',
                'employee_id': 'EMP002',
                'department': 'SALES',
                'role': 'sales_manager',
                'password': 'erp123456',
            },
            {
                'username': 'sales01',
                'email': 'sales01@erp.com',
                'first_name': '李',
                'last_name': '销售人员',
                'employee_id': 'EMP003',
                'department': 'SALES',
                'role': 'salesperson',
                'password': 'erp123456',
            },
            {
                'username': 'purchase_manager',
                'email': 'purchase.manager@erp.com',
                'first_name': '王',
                'last_name': '采购经理',
                'employee_id': 'EMP004',
                'department': 'PURCHASE',
                'role': 'purchase_manager',
                'password': 'erp123456',
            },
            {
                'username': 'purchase01',
                'email': 'purchase01@erp.com',
                'first_name': '赵',
                'last_name': '采购人员',
                'employee_id': 'EMP005',
                'department': 'PURCHASE',
                'role': 'purchaser',
                'password': 'erp123456',
            },
            {
                'username': 'finance01',
                'email': 'finance01@erp.com',
                'first_name': '钱',
                'last_name': '财务人员',
                'employee_id': 'EMP006',
                'department': 'FINANCE',
                'role': 'accountant',
                'password': 'erp123456',
            },
            {
                'username': 'employee01',
                'email': 'employee01@erp.com',
                'first_name': '孙',
                'last_name': '普通员工',
                'employee_id': 'EMP007',
                'department': 'IT',
                'role': 'employee',
                'password': 'erp123456',
            },
        ]

        for user_data in sample_users:
            user, created = User.objects.get_or_create(
                username=user_data['username'],
                defaults={
                    'email': user_data['email'],
                    'first_name': user_data['first_name'],
                    'last_name': user_data['last_name'],
                    'employee_id': user_data['employee_id'],
                    'department': dept_objs[user_data['department']],
                    'role': role_objs[user_data['role']],
                    'is_active': True,
                },
            )
            user.email = user_data['email']
            user.first_name = user_data['first_name']
            user.last_name = user_data['last_name']
            user.employee_id = user_data['employee_id']
            user.department = dept_objs[user_data['department']]
            user.role = role_objs[user_data['role']]
            user.is_active = True
            user.set_password(user_data['password'])
            user.save()
            user.roles.set([role_objs[user_data['role']]])
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'  ✓ 创建用户: {user.username} ({user.first_name}{user.last_name})')
                )
            else:
                self.stdout.write(f'  - 用户已更新: {user.username}')

        self.stdout.write(self.style.SUCCESS('\n数据初始化完成！'))
        self.stdout.write(self.style.SUCCESS('\n可用的测试账号：'))
        self.stdout.write('  admin / admin123 (系统管理员)')
        self.stdout.write('  sales_manager / erp123456 (销售经理)')
        self.stdout.write('  sales01 / erp123456 (销售员)')
        self.stdout.write('  purchase_manager / erp123456 (采购经理)')
        self.stdout.write('  purchase01 / erp123456 (采购员)')
        self.stdout.write('  finance01 / erp123456 (财务人员)')
        self.stdout.write('  employee01 / erp123456 (普通员工)')
