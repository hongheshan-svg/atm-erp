"""
项目归档与知识库模型
Project Archive & Knowledge Base Models

用于非标自动化行业的经验积累：
- 项目归档报告
- 技术难点记录
- 解决方案库
- 标准部件库
- 经验教训总结
"""
from django.db import models
from apps.core.models import BaseModel


class KnowledgeCategory(BaseModel):
    """
    知识分类
    """
    code = models.CharField(max_length=20, unique=True, verbose_name='分类编码')
    name = models.CharField(max_length=50, verbose_name='分类名称')
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children',
        verbose_name='上级分类'
    )
    description = models.TextField(blank=True, verbose_name='描述')
    icon = models.CharField(max_length=50, blank=True, verbose_name='图标')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    
    class Meta:
        db_table = 'knowledge_category'
        verbose_name = '知识分类'
        verbose_name_plural = verbose_name
        ordering = ['sort_order', 'code']
    
    def __str__(self):
        return self.name


class KnowledgeArticle(BaseModel):
    """
    知识文章 - 通用知识文档
    """
    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('PUBLISHED', '已发布'),
        ('ARCHIVED', '已归档'),
    ]
    
    TYPE_CHOICES = [
        ('SOLUTION', '解决方案'),
        ('STANDARD', '标准规范'),
        ('TUTORIAL', '教程指南'),
        ('FAQ', '常见问题'),
        ('CASE', '案例分享'),
        ('LESSON', '经验教训'),
        ('OTHER', '其他'),
    ]
    
    # 基本信息
    title = models.CharField(max_length=200, verbose_name='标题')
    category = models.ForeignKey(
        KnowledgeCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='articles',
        verbose_name='分类'
    )
    article_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='SOLUTION', verbose_name='类型')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', verbose_name='状态')
    
    # 内容
    summary = models.TextField(blank=True, verbose_name='摘要')
    content = models.TextField(verbose_name='内容')
    
    # 标签
    tags = models.JSONField(default=list, blank=True, verbose_name='标签')
    
    # 关联
    project = models.ForeignKey(
        'Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='knowledge_articles',
        verbose_name='关联项目'
    )
    
    # 作者
    author = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='authored_articles',
        verbose_name='作者'
    )
    
    # 统计
    view_count = models.IntegerField(default=0, verbose_name='浏览次数')
    like_count = models.IntegerField(default=0, verbose_name='点赞数')
    
    # 发布
    published_at = models.DateTimeField(null=True, blank=True, verbose_name='发布时间')
    
    # 附件
    attachments = models.JSONField(default=list, blank=True, verbose_name='附件')
    
    class Meta:
        db_table = 'knowledge_article'
        verbose_name = '知识文章'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title


class ProjectArchive(BaseModel):
    """
    项目归档报告 - 项目结项时的总结
    """
    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('REVIEW', '审核中'),
        ('APPROVED', '已通过'),
        ('REJECTED', '已驳回'),
    ]
    
    project = models.OneToOneField(
        'Project',
        on_delete=models.PROTECT,
        related_name='archive',
        verbose_name='项目'
    )
    
    # 基本信息
    archive_date = models.DateField(verbose_name='归档日期')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', verbose_name='状态')
    
    # 项目概况
    project_summary = models.TextField(verbose_name='项目概况')
    scope_description = models.TextField(blank=True, verbose_name='项目范围描述')
    deliverables = models.TextField(blank=True, verbose_name='交付成果')
    
    # 进度回顾
    original_start = models.DateField(null=True, blank=True, verbose_name='原计划开始')
    original_end = models.DateField(null=True, blank=True, verbose_name='原计划结束')
    actual_start = models.DateField(null=True, blank=True, verbose_name='实际开始')
    actual_end = models.DateField(null=True, blank=True, verbose_name='实际结束')
    schedule_variance = models.TextField(blank=True, verbose_name='进度偏差分析')
    
    # 成本回顾
    budget_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name='预算金额')
    actual_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name='实际成本')
    cost_variance = models.TextField(blank=True, verbose_name='成本偏差分析')
    
    # 质量回顾
    quality_summary = models.TextField(blank=True, verbose_name='质量总结')
    defect_count = models.IntegerField(default=0, verbose_name='缺陷数量')
    customer_satisfaction = models.IntegerField(default=0, verbose_name='客户满意度(1-10)')
    
    # 技术总结
    technical_challenges = models.TextField(blank=True, verbose_name='技术难点')
    solutions_applied = models.TextField(blank=True, verbose_name='解决方案')
    innovations = models.TextField(blank=True, verbose_name='技术创新点')
    
    # 经验教训
    lessons_learned = models.TextField(blank=True, verbose_name='经验教训')
    success_factors = models.TextField(blank=True, verbose_name='成功因素')
    improvement_suggestions = models.TextField(blank=True, verbose_name='改进建议')
    
    # 团队评价
    team_performance = models.TextField(blank=True, verbose_name='团队表现')
    key_contributors = models.JSONField(default=list, blank=True, verbose_name='核心贡献者')
    
    # 后续事项
    follow_up_items = models.TextField(blank=True, verbose_name='后续跟进事项')
    warranty_info = models.TextField(blank=True, verbose_name='质保信息')
    
    # 评审
    reviewer = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_archives',
        verbose_name='评审人'
    )
    review_comments = models.TextField(blank=True, verbose_name='评审意见')
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name='评审时间')
    
    # 附件
    attachments = models.JSONField(default=list, blank=True, verbose_name='附件')
    
    class Meta:
        db_table = 'project_archive'
        verbose_name = '项目归档报告'
        verbose_name_plural = verbose_name
        ordering = ['-archive_date']
    
    def __str__(self):
        return f"{self.project.name} - 归档报告"


class TechnicalIssue(BaseModel):
    """
    技术问题记录 - 项目中遇到的技术难点
    """
    SEVERITY_CHOICES = [
        ('LOW', '低'),
        ('MEDIUM', '中'),
        ('HIGH', '高'),
        ('CRITICAL', '严重'),
    ]
    
    STATUS_CHOICES = [
        ('OPEN', '待解决'),
        ('IN_PROGRESS', '处理中'),
        ('RESOLVED', '已解决'),
        ('CLOSED', '已关闭'),
    ]
    
    # 基本信息
    title = models.CharField(max_length=200, verbose_name='标题')
    project = models.ForeignKey(
        'Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='technical_issues',
        verbose_name='关联项目'
    )
    category = models.ForeignKey(
        KnowledgeCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='技术分类'
    )
    
    # 问题描述
    description = models.TextField(verbose_name='问题描述')
    symptoms = models.TextField(blank=True, verbose_name='问题现象')
    root_cause = models.TextField(blank=True, verbose_name='根本原因')
    
    # 状态
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='MEDIUM', verbose_name='严重程度')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OPEN', verbose_name='状态')
    
    # 解决方案
    solution = models.TextField(blank=True, verbose_name='解决方案')
    prevention = models.TextField(blank=True, verbose_name='预防措施')
    
    # 时间
    occurred_at = models.DateTimeField(null=True, blank=True, verbose_name='发生时间')
    resolved_at = models.DateTimeField(null=True, blank=True, verbose_name='解决时间')
    resolution_hours = models.DecimalField(max_digits=6, decimal_places=1, default=0, verbose_name='解决耗时(小时)')
    
    # 人员
    reported_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='reported_issues',
        verbose_name='报告人'
    )
    resolved_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_issues',
        verbose_name='解决人'
    )
    
    # 标签
    tags = models.JSONField(default=list, blank=True, verbose_name='标签')
    
    # 转知识库
    knowledge_article = models.ForeignKey(
        KnowledgeArticle,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='source_issues',
        verbose_name='关联知识文章'
    )
    
    # 附件
    attachments = models.JSONField(default=list, blank=True, verbose_name='附件')
    
    class Meta:
        db_table = 'technical_issue'
        verbose_name = '技术问题记录'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title


class StandardComponent(BaseModel):
    """
    标准部件库 - 可复用的标准部件/模块
    """
    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('ACTIVE', '可用'),
        ('DEPRECATED', '已废弃'),
    ]
    
    # 基本信息
    code = models.CharField(max_length=50, unique=True, verbose_name='部件编码')
    name = models.CharField(max_length=200, verbose_name='部件名称')
    category = models.ForeignKey(
        KnowledgeCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='分类'
    )
    version = models.CharField(max_length=20, default='1.0', verbose_name='版本')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', verbose_name='状态')
    
    # 描述
    description = models.TextField(blank=True, verbose_name='描述')
    specifications = models.JSONField(default=dict, blank=True, verbose_name='技术规格')
    
    # 应用场景
    application = models.TextField(blank=True, verbose_name='应用场景')
    limitations = models.TextField(blank=True, verbose_name='使用限制')
    
    # BOM
    bom_items = models.JSONField(default=list, blank=True, verbose_name='BOM清单')
    estimated_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='估算成本')
    
    # 图纸
    drawings = models.JSONField(default=list, blank=True, verbose_name='相关图纸')
    
    # 使用统计
    usage_count = models.IntegerField(default=0, verbose_name='使用次数')
    last_used = models.DateTimeField(null=True, blank=True, verbose_name='上次使用时间')
    
    # 维护
    maintainer = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='maintained_components',
        verbose_name='维护人'
    )
    
    # 标签
    tags = models.JSONField(default=list, blank=True, verbose_name='标签')
    
    class Meta:
        db_table = 'standard_component'
        verbose_name = '标准部件'
        verbose_name_plural = verbose_name
        ordering = ['code']
    
    def __str__(self):
        return f"{self.code} - {self.name}"
