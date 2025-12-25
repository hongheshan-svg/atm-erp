"""
初始化系统数据
创建基础角色、部门和示例数据
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.accounts.models import Department, Role

User = get_user_model()

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
                code=dept_data['code'],
                defaults={
                    'name': dept_data['name'],
                    'description': dept_data['description']
                }
            )
            dept_objs[dept_data['code']] = dept
            if created:
                self.stdout.write(self.style.SUCCESS(f'  ✓ 创建部门: {dept.name}'))
            else:
                self.stdout.write(f'  - 部门已存在: {dept.name}')
        
        # 2. 创建角色
        self.stdout.write('创建角色...')
        roles = [
            {
                'name': '系统管理员',
                'code': 'ADMIN',
                'description': '系统超级管理员，拥有所有权限',
                'data_scope': 'ALL'
            },
            {
                'name': '总经理',
                'code': 'GM',
                'description': '总经理，查看所有数据',
                'data_scope': 'ALL'
            },
            {
                'name': '销售经理',
                'code': 'SALES_MANAGER',
                'description': '销售部门经理',
                'data_scope': 'DEPARTMENT'
            },
            {
                'name': '销售员',
                'code': 'SALES',
                'description': '销售人员',
                'data_scope': 'SELF'
            },
            {
                'name': '采购经理',
                'code': 'PURCHASE_MANAGER',
                'description': '采购部门经理',
                'data_scope': 'DEPARTMENT'
            },
            {
                'name': '采购员',
                'code': 'PURCHASE',
                'description': '采购人员',
                'data_scope': 'SELF'
            },
            {
                'name': '仓库管理员',
                'code': 'WAREHOUSE_ADMIN',
                'description': '仓库管理人员',
                'data_scope': 'DEPARTMENT'
            },
            {
                'name': '项目经理',
                'code': 'PROJECT_MANAGER',
                'description': '项目管理人员',
                'data_scope': 'SELF'
            },
            {
                'name': '财务人员',
                'code': 'FINANCE',
                'description': '财务管理人员',
                'data_scope': 'ALL'
            },
        ]
        
        role_objs = {}
        for role_data in roles:
            role, created = Role.objects.get_or_create(
                code=role_data['code'],
                defaults={
                    'name': role_data['name'],
                    'description': role_data['description'],
                    'data_scope': role_data['data_scope']
                }
            )
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
            if not admin.role or admin.role.code != 'ADMIN':
                admin.role = role_objs['ADMIN']
                admin.save()
                self.stdout.write(self.style.SUCCESS('  ✓ 为admin分配系统管理员角色'))
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
                'role': 'SALES_MANAGER',
                'password': 'erp123456'
            },
            {
                'username': 'sales01',
                'email': 'sales01@erp.com',
                'first_name': '李',
                'last_name': '销售员',
                'employee_id': 'EMP003',
                'department': 'SALES',
                'role': 'SALES',
                'password': 'erp123456'
            },
            {
                'username': 'purchase_manager',
                'email': 'purchase.manager@erp.com',
                'first_name': '王',
                'last_name': '采购经理',
                'employee_id': 'EMP004',
                'department': 'PURCHASE',
                'role': 'PURCHASE_MANAGER',
                'password': 'erp123456'
            },
            {
                'username': 'purchase01',
                'email': 'purchase01@erp.com',
                'first_name': '赵',
                'last_name': '采购员',
                'employee_id': 'EMP005',
                'department': 'PURCHASE',
                'role': 'PURCHASE',
                'password': 'erp123456'
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
                    'is_active': True
                }
            )
            if created:
                user.set_password(user_data['password'])
                user.save()
                self.stdout.write(self.style.SUCCESS(
                    f'  ✓ 创建用户: {user.username} ({user.first_name}{user.last_name})'
                ))
            else:
                self.stdout.write(f'  - 用户已存在: {user.username}')
        
        self.stdout.write(self.style.SUCCESS('\n数据初始化完成！'))
        self.stdout.write(self.style.SUCCESS('\n可用的测试账号：'))
        self.stdout.write('  admin / admin (系统管理员)')
        self.stdout.write('  sales_manager / erp123456 (销售经理)')
        self.stdout.write('  sales01 / erp123456 (销售员)')
        self.stdout.write('  purchase_manager / erp123456 (采购经理)')
        self.stdout.write('  purchase01 / erp123456 (采购员)')

