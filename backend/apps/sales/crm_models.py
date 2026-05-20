"""
CRM - 商机/线索管理模型
Customer Relationship Management - Lead & Opportunity Models

非标自动化行业销售流程：
线索 → 商机 → 报价 → 合同 → 项目
"""
from django.db import models

from apps.core.models import BaseModel


class LeadSource(BaseModel):
    """
    线索来源
    """
    code = models.CharField(max_length=20, unique=True, verbose_name='来源编码')
    name = models.CharField(max_length=50, verbose_name='来源名称')
    description = models.TextField(blank=True, verbose_name='描述')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    sort_order = models.IntegerField(default=0, verbose_name='排序')

    class Meta:
        db_table = 'lead_source'
        verbose_name = '线索来源'
        verbose_name_plural = verbose_name
        ordering = ['sort_order', 'code']

    def __str__(self):
        return self.name


class Lead(BaseModel):
    """
    销售线索 - 潜在客户初次接触
    """
    STATUS_CHOICES = [
        ('NEW', '新线索'),
        ('CONTACTED', '已联系'),
        ('QUALIFIED', '已确认'),
        ('CONVERTED', '已转化'),
        ('DISQUALIFIED', '已作废'),
    ]

    # 线索编号
    lead_no = models.CharField(max_length=50, unique=True, verbose_name='线索编号')

    # 潜在客户信息
    company_name = models.CharField(max_length=200, verbose_name='公司名称')
    contact_name = models.CharField(max_length=50, verbose_name='联系人')
    contact_phone = models.CharField(max_length=20, blank=True, verbose_name='联系电话')
    contact_email = models.CharField(max_length=100, blank=True, verbose_name='邮箱')
    contact_position = models.CharField(max_length=50, blank=True, verbose_name='职位')

    # 公司信息
    industry = models.CharField(max_length=50, blank=True, verbose_name='所属行业')
    company_size = models.CharField(max_length=50, blank=True, verbose_name='公司规模')
    address = models.TextField(blank=True, verbose_name='地址')
    website = models.CharField(max_length=200, blank=True, verbose_name='网站')

    # 需求信息
    requirement = models.TextField(blank=True, verbose_name='需求描述')
    product_interest = models.CharField(max_length=200, blank=True, verbose_name='感兴趣产品')
    budget_range = models.CharField(max_length=50, blank=True, verbose_name='预算范围')
    expected_date = models.DateField(null=True, blank=True, verbose_name='预期交期')

    # 来源和状态
    source = models.ForeignKey(
        LeadSource,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='线索来源'
    )
    source_detail = models.CharField(max_length=200, blank=True, verbose_name='来源详情')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='NEW', verbose_name='状态')

    # 负责人
    owner = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='owned_leads',
        verbose_name='负责人'
    )

    # 转化信息
    converted_customer = models.ForeignKey(
        'masterdata.Customer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='from_leads',
        verbose_name='转化客户'
    )
    converted_opportunity = models.ForeignKey(
        'Opportunity',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='from_leads',
        verbose_name='转化商机'
    )
    converted_at = models.DateTimeField(null=True, blank=True, verbose_name='转化时间')

    # 评分
    score = models.IntegerField(default=0, verbose_name='线索评分')

    notes = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'lead'
        verbose_name = '销售线索'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.lead_no} - {self.company_name}"

    def save(self, *args, **kwargs):
        if not self.lead_no:
            from apps.core.models import CodeRule
            self.lead_no = CodeRule.generate_code('LEAD')
        super().save(*args, **kwargs)


class Opportunity(BaseModel):
    """
    销售商机 - 确认的销售机会
    """
    STAGE_CHOICES = [
        ('QUALIFICATION', '需求确认'),
        ('NEEDS_ANALYSIS', '需求分析'),
        ('PROPOSAL', '方案报价'),
        ('NEGOTIATION', '商务谈判'),
        ('CLOSED_WON', '赢单'),
        ('CLOSED_LOST', '丢单'),
    ]

    PRIORITY_CHOICES = [
        ('LOW', '低'),
        ('MEDIUM', '中'),
        ('HIGH', '高'),
        ('CRITICAL', '紧急'),
    ]

    # 商机编号
    opportunity_no = models.CharField(max_length=50, unique=True, verbose_name='商机编号')
    name = models.CharField(max_length=200, verbose_name='商机名称')

    # 客户信息
    customer = models.ForeignKey(
        'masterdata.Customer',
        on_delete=models.PROTECT,
        related_name='opportunities',
        verbose_name='客户'
    )
    contact_name = models.CharField(max_length=50, blank=True, verbose_name='联系人')
    contact_phone = models.CharField(max_length=20, blank=True, verbose_name='联系电话')

    # 商机信息
    stage = models.CharField(max_length=20, choices=STAGE_CHOICES, default='QUALIFICATION', verbose_name='阶段')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='MEDIUM', verbose_name='优先级')
    probability = models.IntegerField(default=20, verbose_name='成功概率%')

    # 金额
    estimated_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name='预估金额')
    weighted_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name='加权金额')

    # 产品需求
    product_type = models.CharField(max_length=100, blank=True, verbose_name='产品类型')
    requirement = models.TextField(blank=True, verbose_name='需求描述')
    technical_requirements = models.TextField(blank=True, verbose_name='技术要求')

    # 时间
    expected_close_date = models.DateField(null=True, blank=True, verbose_name='预计成交日期')
    expected_delivery_date = models.DateField(null=True, blank=True, verbose_name='预期交货日期')
    actual_close_date = models.DateField(null=True, blank=True, verbose_name='实际成交日期')

    # 负责人和团队
    owner = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='owned_opportunities',
        verbose_name='负责人'
    )
    sales_team = models.ManyToManyField(
        'accounts.User',
        blank=True,
        related_name='team_opportunities',
        verbose_name='销售团队'
    )

    # 竞争信息
    competitors = models.TextField(blank=True, verbose_name='竞争对手')
    competitive_advantage = models.TextField(blank=True, verbose_name='竞争优势')

    # 转化结果
    won_quotation = models.ForeignKey(
        'SalesQuotation',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='won_opportunities',
        verbose_name='成交报价'
    )
    won_order = models.ForeignKey(
        'SalesOrder',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='won_opportunities',
        verbose_name='成交订单'
    )
    lost_reason = models.TextField(blank=True, verbose_name='丢单原因')

    notes = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'opportunity'
        verbose_name = '销售商机'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.opportunity_no} - {self.name}"

    def save(self, *args, **kwargs):
        if not self.opportunity_no:
            from apps.core.models import CodeRule
            self.opportunity_no = CodeRule.generate_code('OPPORTUNITY')

        # 计算加权金额
        self.weighted_amount = self.estimated_amount * self.probability / 100

        super().save(*args, **kwargs)


class OpportunityActivity(BaseModel):
    """
    商机跟进活动
    """
    ACTIVITY_TYPE = [
        ('CALL', '电话'),
        ('EMAIL', '邮件'),
        ('MEETING', '会议'),
        ('VISIT', '拜访'),
        ('DEMO', '演示'),
        ('PROPOSAL', '方案'),
        ('NEGOTIATION', '谈判'),
        ('OTHER', '其他'),
    ]

    opportunity = models.ForeignKey(
        Opportunity,
        on_delete=models.CASCADE,
        related_name='activities',
        verbose_name='商机'
    )

    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPE, verbose_name='活动类型')
    subject = models.CharField(max_length=200, verbose_name='主题')
    content = models.TextField(verbose_name='内容')

    # 时间
    activity_date = models.DateTimeField(verbose_name='活动时间')
    duration_minutes = models.IntegerField(default=0, verbose_name='时长(分钟)')

    # 参与人
    participants = models.TextField(blank=True, verbose_name='参与人')

    # 下一步
    next_action = models.TextField(blank=True, verbose_name='下一步行动')
    next_action_date = models.DateField(null=True, blank=True, verbose_name='下一步日期')

    # 附件
    attachments = models.JSONField(default=list, blank=True, verbose_name='附件')

    # 记录人
    recorded_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        verbose_name='记录人'
    )

    class Meta:
        db_table = 'opportunity_activity'
        verbose_name = '商机活动'
        verbose_name_plural = verbose_name
        ordering = ['-activity_date']

    def __str__(self):
        return f"{self.opportunity.opportunity_no} - {self.subject}"


class SalesForecast(BaseModel):
    """
    销售预测 - 按月汇总
    """
    year = models.IntegerField(verbose_name='年份')
    month = models.IntegerField(verbose_name='月份')

    owner = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='sales_forecasts',
        verbose_name='销售人员'
    )

    # 预测金额
    forecast_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name='预测金额')
    weighted_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name='加权金额')

    # 实际金额
    actual_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name='实际金额')

    # 商机数量
    opportunity_count = models.IntegerField(default=0, verbose_name='商机数')
    won_count = models.IntegerField(default=0, verbose_name='赢单数')
    lost_count = models.IntegerField(default=0, verbose_name='丢单数')

    # 达成率
    achievement_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='达成率%')

    notes = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'sales_forecast'
        verbose_name = '销售预测'
        verbose_name_plural = verbose_name
        unique_together = ['year', 'month', 'owner']
        ordering = ['-year', '-month']

    def __str__(self):
        return f"{self.year}年{self.month}月 - {self.owner}"
