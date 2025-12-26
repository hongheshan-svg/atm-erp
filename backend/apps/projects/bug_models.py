"""
Bug跟踪系统模型
"""
from django.db import models
from django.conf import settings
from apps.core.models import BaseModel


class Bug(BaseModel):
    """
    Bug模型
    """
    # 严重程度选项
    SEVERITY_CHOICES = [
        ('CRITICAL', '致命'),
        ('MAJOR', '严重'),
        ('NORMAL', '一般'),
        ('MINOR', '轻微'),
        ('SUGGESTION', '建议'),
    ]
    
    # 优先级选项
    PRIORITY_CHOICES = [
        ('P0', 'P0-紧急'),
        ('P1', 'P1-高'),
        ('P2', 'P2-中'),
        ('P3', 'P3-低'),
    ]
    
    # 状态选项
    STATUS_CHOICES = [
        ('NEW', '新建'),
        ('CONFIRMED', '已确认'),
        ('IN_PROGRESS', '处理中'),
        ('RESOLVED', '已解决'),
        ('CLOSED', '已关闭'),
        ('REOPENED', '重新打开'),
        ('SUSPENDED', '挂起'),
        ('CANNOT_REPRODUCE', '无法复现'),
        ('BY_DESIGN', '设计如此'),
        ('DUPLICATE', '重复'),
    ]
    
    # Bug类型选项
    TYPE_CHOICES = [
        ('FUNCTION', '功能问题'),
        ('PERFORMANCE', '性能问题'),
        ('UI', '界面问题'),
        ('SECURITY', '安全问题'),
        ('DATA', '数据问题'),
        ('COMPATIBILITY', '兼容性问题'),
        ('OTHER', '其他'),
    ]
    
    # 解决方式选项
    RESOLUTION_CHOICES = [
        ('FIXED', '已修复'),
        ('WONT_FIX', '不予修复'),
        ('DUPLICATE', '重复问题'),
        ('INVALID', '无效问题'),
        ('CANNOT_REPRODUCE', '无法复现'),
        ('BY_DESIGN', '设计如此'),
    ]
    
    # 基本信息
    bug_number = models.CharField(max_length=50, unique=True, verbose_name='Bug编号')
    title = models.CharField(max_length=200, verbose_name='标题')
    description = models.TextField(verbose_name='详细描述')
    
    # 关联
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='bugs',
        verbose_name='所属项目'
    )
    task = models.ForeignKey(
        'projects.ProjectTask',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bugs',
        verbose_name='关联任务'
    )
    module = models.CharField(max_length=100, blank=True, verbose_name='模块/组件')
    
    # 分类
    severity = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES,
        default='NORMAL',
        verbose_name='严重程度'
    )
    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default='P2',
        verbose_name='优先级'
    )
    bug_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default='FUNCTION',
        verbose_name='Bug类型'
    )
    
    # 状态
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='NEW',
        verbose_name='状态'
    )
    
    # 人员
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='reported_bugs',
        verbose_name='报告人'
    )
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_bugs',
        verbose_name='处理人'
    )
    
    # 解决方案
    resolution = models.CharField(
        max_length=20,
        choices=RESOLUTION_CHOICES,
        blank=True,
        verbose_name='解决方式'
    )
    solution = models.TextField(blank=True, verbose_name='解决说明')
    
    # 时间
    resolved_at = models.DateTimeField(null=True, blank=True, verbose_name='解决时间')
    closed_at = models.DateTimeField(null=True, blank=True, verbose_name='关闭时间')
    
    # 环境信息
    environment = models.CharField(max_length=50, blank=True, verbose_name='环境')
    version = models.CharField(max_length=50, blank=True, verbose_name='版本')
    
    # 关联Bug（用于标记重复）
    duplicate_of = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='duplicates',
        verbose_name='重复于'
    )
    
    class Meta:
        db_table = 'bug'
        verbose_name = 'Bug'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.bug_number}: {self.title}"
    
    def save(self, *args, **kwargs):
        # 自动生成Bug编号
        if not self.bug_number:
            from apps.core.code_rule_services import CodeRuleService
            try:
                self.bug_number = CodeRuleService.generate_code('BUG')
            except:
                # 如果编码规则不存在，使用简单编号
                import datetime
                year = datetime.datetime.now().year
                last_bug = Bug.objects.filter(
                    bug_number__startswith=f'BUG{year}'
                ).order_by('-bug_number').first()
                if last_bug:
                    try:
                        seq = int(last_bug.bug_number[-6:]) + 1
                    except:
                        seq = 1
                else:
                    seq = 1
                self.bug_number = f'BUG{year}{seq:06d}'
        
        super().save(*args, **kwargs)


class BugComment(BaseModel):
    """
    Bug评论
    """
    bug = models.ForeignKey(
        Bug,
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name='Bug'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='bug_comments',
        verbose_name='评论人'
    )
    content = models.TextField(verbose_name='评论内容')
    
    class Meta:
        db_table = 'bug_comment'
        verbose_name = 'Bug评论'
        verbose_name_plural = verbose_name
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.bug.bug_number} - {self.user.username}"


class BugAttachment(BaseModel):
    """
    Bug附件
    """
    bug = models.ForeignKey(
        Bug,
        on_delete=models.CASCADE,
        related_name='attachments',
        verbose_name='Bug'
    )
    file = models.FileField(upload_to='bugs/%Y/%m/', verbose_name='文件')
    filename = models.CharField(max_length=255, verbose_name='文件名')
    file_size = models.IntegerField(default=0, verbose_name='文件大小')
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='bug_attachments',
        verbose_name='上传人'
    )
    
    class Meta:
        db_table = 'bug_attachment'
        verbose_name = 'Bug附件'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.bug.bug_number} - {self.filename}"


class BugHistory(BaseModel):
    """
    Bug变更历史
    """
    bug = models.ForeignKey(
        Bug,
        on_delete=models.CASCADE,
        related_name='histories',
        verbose_name='Bug'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='bug_histories',
        verbose_name='操作人'
    )
    field_name = models.CharField(max_length=50, verbose_name='变更字段')
    field_label = models.CharField(max_length=50, verbose_name='字段名称')
    old_value = models.TextField(blank=True, verbose_name='原值')
    new_value = models.TextField(blank=True, verbose_name='新值')
    
    class Meta:
        db_table = 'bug_history'
        verbose_name = 'Bug变更历史'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.bug.bug_number} - {self.field_label}"

