from django.db import models
from django.conf import settings


class TimeStampedModel(models.Model):
    """
    Abstract base model with created_at and updated_at timestamps
    """
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        abstract = True


class SoftDeleteModel(models.Model):
    """
    Abstract model for soft delete functionality
    """
    is_deleted = models.BooleanField(default=False, verbose_name='已删除')
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name='删除时间')

    class Meta:
        abstract = True
    
    def soft_delete(self):
        """Soft delete the instance by setting is_deleted to True."""
        from django.utils import timezone
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=['is_deleted', 'deleted_at'])


class BaseModel(TimeStampedModel, SoftDeleteModel):
    """
    Base model combining timestamps and soft delete
    """
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_created',
        verbose_name='创建人'
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_updated',
        verbose_name='更新人'
    )

    class Meta:
        abstract = True


class AuditLog(models.Model):
    """
    Audit trail for all system changes
    """
    ACTION_CHOICES = [
        ('CREATE', '创建'),
        ('UPDATE', '更新'),
        ('DELETE', '删除'),
        ('LOGIN', '登录'),
        ('LOGOUT', '登出'),
        ('APPROVE', '审批'),
        ('REJECT', '拒绝'),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='audit_logs',
        verbose_name='操作用户'
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, verbose_name='操作类型')
    model_name = models.CharField(max_length=100, verbose_name='模型名称')
    object_id = models.CharField(max_length=100, null=True, blank=True, verbose_name='对象ID')
    object_repr = models.CharField(max_length=200, verbose_name='对象描述')
    changes = models.JSONField(null=True, blank=True, verbose_name='变更内容')
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP地址')
    user_agent = models.TextField(null=True, blank=True, verbose_name='用户代理')
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name='操作时间', db_index=True)
    
    class Meta:
        db_table = 'audit_log'
        verbose_name = '审计日志'
        verbose_name_plural = verbose_name
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp', 'user']),
            models.Index(fields=['model_name', 'object_id']),
        ]
    
    def __str__(self):
        return f"{self.user} - {self.action} - {self.model_name} - {self.timestamp}"


class Attachment(models.Model):
    """
    通用附件模型，可关联到任何业务对象
    """
    CATEGORY_CHOICES = [
        ('CONTRACT', '合同文件'),
        ('INVOICE', '发票'),
        ('RECEIPT', '收据'),
        ('CERTIFICATE', '证书/资质'),
        ('REPORT', '报告'),
        ('IMAGE', '图片'),
        ('VIDEO', '视频'),
        ('FAULT_IMAGE', '故障图片'),
        ('FAULT_VIDEO', '故障视频'),
        ('OTHER', '其他'),
    ]
    
    # 关联信息 - 使用通用外键方式
    related_model = models.CharField(max_length=100, verbose_name='关联模型', db_index=True)
    related_id = models.IntegerField(verbose_name='关联ID', db_index=True)
    
    # 文件信息
    file = models.FileField(upload_to='attachments/%Y/%m/', verbose_name='文件')
    original_name = models.CharField(max_length=255, verbose_name='原始文件名')
    file_size = models.IntegerField(default=0, verbose_name='文件大小(字节)')
    file_type = models.CharField(max_length=100, blank=True, verbose_name='文件类型')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='OTHER', verbose_name='分类')
    
    # 描述信息
    description = models.TextField(blank=True, verbose_name='描述')
    
    # 时间戳
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_attachments',
        verbose_name='上传人'
    )
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name='上传时间')
    
    class Meta:
        db_table = 'attachment'
        verbose_name = '附件'
        verbose_name_plural = verbose_name
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['related_model', 'related_id']),
        ]
    
    def __str__(self):
        return f"{self.original_name} ({self.related_model}:{self.related_id})"
    
    def save(self, *args, **kwargs):
        if self.file and not self.file_size:
            self.file_size = self.file.size
        if self.file and not self.file_type:
            import mimetypes
            self.file_type = mimetypes.guess_type(self.file.name)[0] or 'application/octet-stream'
        super().save(*args, **kwargs)


class SystemNotification(models.Model):
    """
    System notifications for users
    """
    TYPE_CHOICES = [
        ('INFO', '信息'),
        ('WARNING', '警告'),
        ('ERROR', '错误'),
        ('SUCCESS', '成功'),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name='接收用户'
    )
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='INFO', verbose_name='类型')
    title = models.CharField(max_length=200, verbose_name='标题')
    message = models.TextField(verbose_name='消息内容')
    is_read = models.BooleanField(default=False, verbose_name='已读')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    read_at = models.DateTimeField(null=True, blank=True, verbose_name='阅读时间')
    
    class Meta:
        db_table = 'system_notification'
        verbose_name = '系统通知'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user} - {self.title}"


# 导入权限配置模型，使其可被迁移系统发现
from .permission_models import ModulePermissionRule, RoleModulePermission
