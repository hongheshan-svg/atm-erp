from django.db import models
from django.core.exceptions import ValidationError
from apps.core.models import BaseModel


class Permission(BaseModel):
    """
    权限模型 - 树形结构
    支持菜单权限、操作权限、字段权限三级体系
    """
    PERMISSION_TYPE_CHOICES = [
        ('menu', '菜单权限'),
        ('operation', '操作权限'),
        ('field', '字段权限'),
    ]

    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        verbose_name='父权限'
    )
    code = models.CharField(
        max_length=100,
        unique=True,
        verbose_name='权限编码',
        help_text='唯一标识，如 system:user:create'
    )
    name = models.CharField(
        max_length=100,
        verbose_name='权限名称'
    )
    type = models.CharField(
        max_length=20,
        choices=PERMISSION_TYPE_CHOICES,
        verbose_name='权限类型'
    )
    resource = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='资源标识',
        help_text='对应的资源类型，如 user, role'
    )
    field_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='字段名称',
        help_text='字段权限对应的字段名'
    )
    route_path = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='路由路径',
        help_text='前端路由路径'
    )
    icon = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='图标'
    )
    sort_order = models.IntegerField(
        default=0,
        verbose_name='排序'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='是否启用'
    )

    class Meta:
        db_table = 'core_permission'
        verbose_name = '权限'
        verbose_name_plural = verbose_name
        ordering = ['sort_order', 'id']
        indexes = [
            models.Index(fields=['code'], name='core_perm_code_idx'),
            models.Index(fields=['type', 'is_active'], name='core_perm_type_active_idx'),
            models.Index(fields=['parent', 'sort_order'], name='core_perm_parent_sort_idx'),
            models.Index(fields=['resource'], name='core_perm_resource_idx'),
        ]

    def __str__(self):
        return f'{self.name} ({self.code})'

    def clean(self):
        """Validate permission fields based on type"""
        super().clean()

        # Field permissions must have field_name
        if self.type == 'field' and not self.field_name:
            raise ValidationError({
                'field_name': 'Field permissions must have a field_name specified.'
            })

        # Operation permissions must have resource
        if self.type == 'operation' and not self.resource:
            raise ValidationError({
                'resource': 'Operation permissions must have a resource specified.'
            })

        # Prevent self-referencing parent (circular reference)
        if self.parent and self.parent.id == self.id:
            raise ValidationError({
                'parent': 'A permission cannot be its own parent.'
            })


class RolePermission(models.Model):
    """
    角色权限关联表
    不继承 BaseModel，避免软删除带来的复杂性
    """
    role = models.ForeignKey(
        'accounts.Role',
        on_delete=models.CASCADE,
        related_name='role_permissions',
        verbose_name='角色'
    )
    permission = models.ForeignKey(
        Permission,
        on_delete=models.CASCADE,
        related_name='role_permissions',
        verbose_name='权限'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='创建时间'
    )

    class Meta:
        db_table = 'core_role_permission'
        verbose_name = '角色权限'
        verbose_name_plural = verbose_name
        unique_together = [['role', 'permission']]
        indexes = [
            models.Index(fields=['role'], name='core_roleperm_role_idx'),
            models.Index(fields=['permission'], name='core_roleperm_perm_idx'),
        ]

    def __str__(self):
        return f'{self.role.name} - {self.permission.name}'


class DataScope(models.Model):
    """
    数据权限范围
    不继承 BaseModel，避免软删除带来的复杂性
    """
    SCOPE_TYPE_CHOICES = [
        ('global', '全局数据'),
        ('department', '本部门数据'),
        ('department_and_below', '本部门及下级部门数据'),
        ('self', '仅本人数据'),
        ('custom', '自定义部门数据'),
    ]

    role = models.ForeignKey(
        'accounts.Role',
        on_delete=models.CASCADE,
        related_name='data_scopes',
        verbose_name='角色'
    )
    module = models.CharField(
        max_length=50,
        verbose_name='模块',
        help_text='如 projects, sales, purchase'
    )
    scope_type = models.CharField(
        max_length=30,
        choices=SCOPE_TYPE_CHOICES,
        verbose_name='范围类型'
    )
    departments = models.ManyToManyField(
        'accounts.Department',
        blank=True,
        related_name='data_scopes',
        verbose_name='自定义部门',
        help_text='仅当 scope_type 为 custom 时使用'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='创建时间'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='更新时间'
    )

    class Meta:
        db_table = 'core_data_scope'
        verbose_name = '数据权限范围'
        verbose_name_plural = verbose_name
        unique_together = [['role', 'module']]
        indexes = [
            models.Index(fields=['role', 'module'], name='core_datascope_role_mod_idx'),
            models.Index(fields=['scope_type'], name='core_datascope_type_idx'),
        ]

    def __str__(self):
        return f'{self.role.name} - {self.module} ({self.get_scope_type_display()})'

