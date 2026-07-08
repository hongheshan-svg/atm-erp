"""
回款计划管理模型
Collection Plan Management Models

非标自动化行业典型收款节点：
- 预付款（合同签订后）
- 发货款（设备发货后）
- 验收款（客户验收后）
- 质保款（质保期结束）
"""

from django.db import models

from apps.core.models import BaseModel


class CollectionPlan(BaseModel):
    """
    回款计划 - 项目/合同级别的收款规划
    """

    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('CONFIRMED', '已确认'),
        ('IN_PROGRESS', '执行中'),
        ('COMPLETED', '已完成'),
        ('CANCELLED', '已取消'),
    ]

    plan_no = models.CharField(max_length=50, unique=True, verbose_name='计划编号')
    name = models.CharField(max_length=200, verbose_name='计划名称')

    # 关联
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='collection_plans',
        verbose_name='项目',
    )
    sales_order = models.ForeignKey(
        'sales.SalesOrder',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='collection_plans',
        verbose_name='销售订单',
    )
    contract = models.ForeignKey(
        'sales.SalesContract',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='collection_plans',
        verbose_name='销售合同',
    )
    customer = models.ForeignKey(
        'masterdata.Customer', on_delete=models.PROTECT, related_name='collection_plans', verbose_name='客户'
    )

    # 金额
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, verbose_name='合同总金额')
    planned_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name='计划回款金额')
    collected_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name='已回款金额')

    # 状态
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', verbose_name='状态')

    # 负责人
    owner = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, related_name='collection_plans', verbose_name='负责人'
    )

    notes = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'collection_plan'
        verbose_name = '回款计划'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.plan_no} - {self.name}'

    def save(self, *args, **kwargs):
        if not self.plan_no:
            from apps.core.code_rule_models import CodeRule

            self.plan_no = CodeRule.generate_code('COLLECTION_PLAN')
        super().save(*args, **kwargs)

    @property
    def collection_rate(self):
        """回款率"""
        if self.total_amount > 0:
            return float(self.collected_amount / self.total_amount * 100)
        return 0

    @property
    def remaining_amount(self):
        """剩余应收"""
        return self.total_amount - self.collected_amount


class CollectionMilestone(BaseModel):
    """
    回款节点 - 具体的收款时间点
    """

    MILESTONE_TYPE = [
        ('ADVANCE', '预付款'),
        ('DELIVERY', '发货款'),
        ('INSTALLATION', '安装款'),
        ('ACCEPTANCE', '验收款'),
        ('WARRANTY', '质保款'),
        ('FINAL', '尾款'),
        ('OTHER', '其他'),
    ]

    STATUS_CHOICES = [
        ('PENDING', '待收款'),
        ('PARTIAL', '部分收款'),
        ('COLLECTED', '已收款'),
        ('OVERDUE', '已逾期'),
        ('CANCELLED', '已取消'),
    ]

    plan = models.ForeignKey(
        CollectionPlan, on_delete=models.CASCADE, related_name='milestones', verbose_name='回款计划'
    )

    # 节点信息
    milestone_type = models.CharField(max_length=20, choices=MILESTONE_TYPE, verbose_name='节点类型')
    name = models.CharField(max_length=100, verbose_name='节点名称')
    description = models.TextField(blank=True, verbose_name='描述')

    # 金额
    percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='占比%')
    planned_amount = models.DecimalField(max_digits=14, decimal_places=2, verbose_name='计划金额')
    collected_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name='已收金额')

    # 时间
    planned_date = models.DateField(verbose_name='计划收款日期')
    actual_date = models.DateField(null=True, blank=True, verbose_name='实际收款日期')

    # 触发条件
    trigger_condition = models.CharField(max_length=200, blank=True, verbose_name='触发条件')
    is_triggered = models.BooleanField(default=False, verbose_name='条件已触发')
    triggered_at = models.DateTimeField(null=True, blank=True, verbose_name='触发时间')

    # 状态
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', verbose_name='状态')

    # 提醒
    reminder_days = models.IntegerField(default=7, verbose_name='提前提醒天数')
    last_reminder = models.DateTimeField(null=True, blank=True, verbose_name='上次提醒时间')

    notes = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'collection_milestone'
        verbose_name = '回款节点'
        verbose_name_plural = verbose_name
        ordering = ['planned_date']

    def __str__(self):
        return f'{self.plan.plan_no} - {self.name}'

    @property
    def is_overdue(self):
        """是否逾期"""
        from django.utils import timezone

        if self.status in ['COLLECTED', 'CANCELLED']:
            return False
        return timezone.now().date() > self.planned_date

    @property
    def overdue_days(self):
        """逾期天数"""
        if not self.is_overdue:
            return 0
        from django.utils import timezone

        return (timezone.now().date() - self.planned_date).days


class CollectionRecord(BaseModel):
    """
    收款记录 - 实际收到的款项
    """

    PAYMENT_METHOD = [
        ('BANK', '银行转账'),
        ('CHECK', '支票'),
        ('CASH', '现金'),
        ('ACCEPTANCE', '承兑汇票'),
        ('OTHER', '其他'),
    ]

    milestone = models.ForeignKey(
        CollectionMilestone, on_delete=models.PROTECT, related_name='records', verbose_name='回款节点'
    )

    # 收款信息
    collection_date = models.DateField(verbose_name='收款日期')
    amount = models.DecimalField(max_digits=14, decimal_places=2, verbose_name='收款金额')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD, default='BANK', verbose_name='付款方式')

    # 银行信息
    bank_name = models.CharField(max_length=100, blank=True, verbose_name='付款银行')
    bank_account = models.CharField(max_length=50, blank=True, verbose_name='付款账号')
    transaction_no = models.CharField(max_length=100, blank=True, verbose_name='交易流水号')

    # 关联发票
    invoice = models.ForeignKey(
        'Invoice',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='collection_records',
        verbose_name='关联发票',
    )

    # 确认
    confirmed = models.BooleanField(default=False, verbose_name='已确认')
    confirmed_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='confirmed_collections',
        verbose_name='确认人',
    )
    confirmed_at = models.DateTimeField(null=True, blank=True, verbose_name='确认时间')

    notes = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'collection_record'
        verbose_name = '收款记录'
        verbose_name_plural = verbose_name
        ordering = ['-collection_date']

    def __str__(self):
        return f'{self.milestone.plan.plan_no} - {self.collection_date} - {self.amount}'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self._recompute_milestone_and_plan(self.milestone)

    def soft_delete(self):
        """软删除收款记录后,按"仅已确认"口径回算节点/计划已收金额(反向核销)。

        幂等:已软删除的记录不会再次被计入聚合,重复调用安全。
        """
        if self.is_deleted:
            return
        milestone = self.milestone
        super().soft_delete()
        self._recompute_milestone_and_plan(milestone)

    def delete(self, *args, **kwargs):
        """硬删除同样触发回算,保证节点/计划已收金额与剩余记录一致。"""
        milestone = self.milestone
        result = super().delete(*args, **kwargs)
        self._recompute_milestone_and_plan(milestone)
        return result

    @staticmethod
    def _recompute_milestone_and_plan(milestone):
        """按"仅 confirmed=True 且未软删"的收款记录整体重算节点与计划的已收金额与状态。

        - 只统计已确认记录:修复"未确认(草稿)收款被当作已收"导致三条应收口径漂移。
        - 幂等:每次都从聚合值整体重算(而非增量累加),重复保存 / 反确认 / 删除都能自愈,
          不会重复计入,天然满足"reverse on delete/unconfirm"。
        - 默认管理器已过滤 is_deleted=False,软删除记录自动被排除。
        """
        from decimal import Decimal

        # 节点级:仅统计已确认记录
        milestone_collected = (
            milestone.records.filter(confirmed=True).aggregate(total=models.Sum('amount'))['total'] or Decimal('0')
        )
        milestone.collected_amount = milestone_collected

        if milestone.planned_amount and milestone_collected >= milestone.planned_amount:
            milestone.status = 'COLLECTED'
            if not milestone.actual_date:
                latest = milestone.records.filter(confirmed=True).order_by('-collection_date').first()
                if latest:
                    milestone.actual_date = latest.collection_date
        elif milestone_collected > 0:
            milestone.status = 'PARTIAL'
        elif milestone.status != 'CANCELLED':
            # 已确认金额回落到 0(反确认 / 删除):从收款派生状态退回待收款,
            # 不影响 CANCELLED 等非收款派生状态。
            milestone.status = 'PENDING'

        milestone.save()

        # 计划级:同样仅统计已确认记录
        plan = milestone.plan
        plan_collected = (
            CollectionRecord.objects.filter(milestone__plan=plan, confirmed=True).aggregate(
                total=models.Sum('amount')
            )['total']
            or Decimal('0')
        )
        plan.collected_amount = plan_collected

        if plan.total_amount and plan_collected >= plan.total_amount:
            plan.status = 'COMPLETED'
        elif plan_collected > 0:
            if plan.status in ('DRAFT', 'COMPLETED'):
                plan.status = 'IN_PROGRESS'
        elif plan.status in ('IN_PROGRESS', 'COMPLETED'):
            # 已确认金额回落到 0:从执行/完成态退回草稿,保留 CONFIRMED/CANCELLED。
            plan.status = 'DRAFT'

        plan.save()


class CollectionReminder(BaseModel):
    """
    回款提醒
    """

    REMINDER_TYPE = [
        ('UPCOMING', '即将到期'),
        ('DUE', '到期提醒'),
        ('OVERDUE', '逾期提醒'),
    ]

    milestone = models.ForeignKey(
        CollectionMilestone, on_delete=models.CASCADE, related_name='reminders', verbose_name='回款节点'
    )

    reminder_type = models.CharField(max_length=20, choices=REMINDER_TYPE, verbose_name='提醒类型')
    reminder_date = models.DateTimeField(verbose_name='提醒时间')

    # 接收人
    recipients = models.ManyToManyField('accounts.User', related_name='collection_reminders', verbose_name='接收人')

    # 发送状态
    sent = models.BooleanField(default=False, verbose_name='已发送')
    sent_at = models.DateTimeField(null=True, blank=True, verbose_name='发送时间')

    message = models.TextField(blank=True, verbose_name='提醒内容')

    class Meta:
        db_table = 'collection_reminder'
        verbose_name = '回款提醒'
        verbose_name_plural = verbose_name
        ordering = ['reminder_date']

    def __str__(self):
        return f'{self.milestone.name} - {self.get_reminder_type_display()}'
