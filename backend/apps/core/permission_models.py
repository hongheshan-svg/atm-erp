"""
数据权限配置模型

支持在后台配置：
1. 模块权限规则
2. 角色模块权限
"""

from django.db import models

from .models import TimeStampedModel


class ModulePermissionRule(TimeStampedModel):
    """
    模块权限规则配置
    定义每个模块的数据权限过滤规则
    """

    MODULE_CHOICES = [
        ('sales', '销售管理'),
        ('purchase', '采购管理'),
        ('projects', '项目管理'),
        ('inventory', '库存管理'),
        ('finance', '财务管理'),
        ('masterdata', '基础数据'),
        ('accounts', '用户管理'),
    ]

    RULE_TYPE_CHOICES = [
        ('user', '关联用户'),
        ('department', '关联部门'),
        ('value', '固定值'),
    ]

    module = models.CharField(max_length=50, choices=MODULE_CHOICES, verbose_name='模块')
    field_path = models.CharField(
        max_length=200, help_text='字段路径，支持关联查询如: project__manager', verbose_name='字段路径'
    )
    rule_type = models.CharField(max_length=20, choices=RULE_TYPE_CHOICES, default='user', verbose_name='规则类型')
    description = models.CharField(max_length=100, blank=True, verbose_name='规则描述')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    sort_order = models.IntegerField(default=0, verbose_name='排序')

    class Meta:
        db_table = 'module_permission_rule'
        verbose_name = '模块权限规则'
        verbose_name_plural = verbose_name
        ordering = ['module', 'sort_order']
        unique_together = ['module', 'field_path']

    def __str__(self):
        return f'{self.get_module_display()} - {self.description or self.field_path}'

    def to_rule_dict(self):
        """转换为规则字典格式"""
        return {
            'field': self.field_path,
            'type': self.rule_type,
            'desc': self.description,
        }


class RoleModulePermission(TimeStampedModel):
    """
    角色模块权限配置
    定义角色对特定模块的特殊权限
    """

    PERMISSION_TYPE_CHOICES = [
        ('all', '全部数据'),
        ('view_all', '只读全部'),
        ('department', '部门数据'),
        ('self', '仅本人'),
        ('rules', '按规则'),
    ]

    role = models.ForeignKey(
        'accounts.Role', on_delete=models.CASCADE, related_name='module_permissions', verbose_name='角色'
    )
    module = models.CharField(max_length=50, choices=ModulePermissionRule.MODULE_CHOICES, verbose_name='模块')
    permission_type = models.CharField(
        max_length=20, choices=PERMISSION_TYPE_CHOICES, default='rules', verbose_name='权限类型'
    )
    is_active = models.BooleanField(default=True, verbose_name='是否启用')

    class Meta:
        db_table = 'role_module_permission'
        verbose_name = '角色模块权限'
        verbose_name_plural = verbose_name
        unique_together = ['role', 'module']

    def __str__(self):
        return f'{self.role.name} - {self.get_module_display()} - {self.get_permission_type_display()}'
