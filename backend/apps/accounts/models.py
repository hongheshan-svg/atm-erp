"""
User, Role, and Department models for RBAC system.
"""
from django.contrib.auth.models import AbstractUser
from django.db import models
from apps.core.models import TimeStampedModel, SoftDeleteModel


class Department(TimeStampedModel, SoftDeleteModel):
    """
    Department model with hierarchical support.
    """
    name = models.CharField(max_length=100, verbose_name='部门名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='部门编码')
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children',
        verbose_name='上级部门'
    )
    manager = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_departments',
        verbose_name='部门经理'
    )
    description = models.TextField(blank=True, verbose_name='描述')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    
    class Meta:
        db_table = 'department'
        verbose_name = '部门'
        verbose_name_plural = verbose_name
        ordering = ['sort_order', 'code']
    
    def __str__(self):
        return self.name


class Role(TimeStampedModel, SoftDeleteModel):
    """
    Role model for RBAC.
    """
    DATA_SCOPE_CHOICES = [
        ('ALL', '全部数据'),
        ('DEPARTMENT', '部门数据'),
        ('SELF', '仅本人数据'),
    ]
    
    name = models.CharField(max_length=100, unique=True, verbose_name='角色名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='角色编码')
    description = models.TextField(blank=True, verbose_name='描述')
    data_scope = models.CharField(
        max_length=20,
        choices=DATA_SCOPE_CHOICES,
        default='SELF',
        verbose_name='数据权限范围'
    )
    # Store menu permissions as JSON: {"menu_ids": [1,2,3], "permissions": ["user:add", "user:edit"]}
    permissions = models.JSONField(default=dict, blank=True, verbose_name='权限配置')
    is_active = models.BooleanField(default=True, verbose_name='激活状态')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    
    class Meta:
        db_table = 'role'
        verbose_name = '角色'
        verbose_name_plural = verbose_name
        ordering = ['sort_order', 'code']
    
    def __str__(self):
        return self.name


class User(AbstractUser, SoftDeleteModel):
    """
    Custom User model extending Django's AbstractUser.
    """
    GENDER_CHOICES = [
        ('M', '男'),
        ('F', '女'),
        ('O', '其他'),
    ]
    
    employee_id = models.CharField(max_length=50, unique=True, verbose_name='工号')
    phone = models.CharField(max_length=20, blank=True, verbose_name='手机号')
    avatar = models.ImageField(upload_to='avatars/', blank=True, verbose_name='头像')
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True, verbose_name='性别')
    birth_date = models.DateField(null=True, blank=True, verbose_name='出生日期')
    
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
        verbose_name='所属部门'
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
        verbose_name='角色'
    )
    
    position = models.CharField(max_length=100, blank=True, verbose_name='职位')
    hire_date = models.DateField(null=True, blank=True, verbose_name='入职日期')
    
    # Timestamp fields
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        db_table = 'user'
        verbose_name = '用户'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.username} ({self.get_full_name() or self.employee_id})"
    
    def has_permission(self, permission_code):
        """Check if user has a specific permission."""
        if self.is_superuser:
            return True
        if not self.role or not self.role.is_active:
            return False
        permissions = self.role.permissions.get('permissions', [])
        return permission_code in permissions

