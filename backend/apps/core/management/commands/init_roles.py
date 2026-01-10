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


class Command(BaseCommand):
    help = '初始化默认角色和权限数据'
    
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
                        role.data_scope = role_config.get('data_scope', 'SELF')
                        role.permissions = role_config.get('permissions', {})
                        role.is_active = True
                        role.save()
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
                        existing_by_name.data_scope = role_config.get('data_scope', 'SELF')
                        existing_by_name.permissions = role_config.get('permissions', {})
                        existing_by_name.is_active = True
                        existing_by_name.save()
                        updated_count += 1
                        self.stdout.write(f'  更新角色(按名称): {code} ({role_config["name"]})')
                    else:
                        # 创建新角色
                        role = Role.objects.create(
                            code=code,
                            name=role_config['name'],
                            description=role_config.get('description', ''),
                            data_scope=role_config.get('data_scope', 'SELF'),
                            permissions=role_config.get('permissions', {}),
                            is_active=True,
                            sort_order=DEFAULT_ROLES.index(role_config) * 10
                        )
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
