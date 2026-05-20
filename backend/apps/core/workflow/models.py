"""
Workflow models for approval processes.
"""

from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class WorkflowDefinition(BaseModel):
    """
    Workflow definition - defines the approval process template.
    """

    BUSINESS_TYPE_CHOICES = [
        # 采购管理
        ('PURCHASE_REQUEST', '采购申请'),
        ('PURCHASE_ORDER', '采购订单'),
        # 销售管理
        ('QUOTATION', '销售报价'),
        ('SALES_ORDER', '销售订单'),
        ('SALES_CONTRACT', '销售合同'),
        ('DELIVERY_ORDER', '发货单'),
        # 财务管理
        ('EXPENSE', '费用报销'),
        ('PAYMENT', '付款申请'),
        # 项目管理
        ('PROJECT', '项目立项'),
        ('ECN', '工程变更'),
        # 库存管理
        ('STOCK_ADJUSTMENT', '库存调整'),
        # OA办公
        ('LEAVE_REQUEST', '请假申请'),
        ('OVERTIME_REQUEST', '加班申请'),
        ('VEHICLE_REQUEST', '用车申请'),
        ('ASSET_BORROW', '资产借用'),
    ]

    name = models.CharField(max_length=100, verbose_name='流程名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='流程编码')
    business_type = models.CharField(max_length=30, choices=BUSINESS_TYPE_CHOICES, verbose_name='业务类型')
    description = models.TextField(blank=True, verbose_name='描述')
    is_active = models.BooleanField(default=True, verbose_name='启用')

    # Conditions for auto-selecting this workflow
    amount_threshold = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='金额阈值',
        help_text='超过此金额时使用此流程',
    )

    class Meta:
        db_table = 'workflow_definition'
        verbose_name = '审批流程定义'
        verbose_name_plural = verbose_name
        ordering = ['business_type', 'amount_threshold']

    def __str__(self):
        return f'{self.name} ({self.get_business_type_display()})'


class WorkflowStep(BaseModel):
    """
    Workflow step - defines each approval step in the workflow.
    """

    APPROVER_TYPE_CHOICES = [
        ('USER', '指定用户'),
        ('ROLE', '指定角色'),
        ('DEPARTMENT_MANAGER', '部门经理'),
        ('PROJECT_MANAGER', '项目经理'),
        ('SUPERIOR', '直属上级'),
    ]

    ACTION_TYPE_CHOICES = [
        ('APPROVE', '审批'),
        ('REVIEW', '审核'),
        ('COUNTERSIGN', '会签'),
    ]

    workflow = models.ForeignKey(
        WorkflowDefinition, on_delete=models.CASCADE, related_name='steps', verbose_name='所属流程'
    )
    step_order = models.IntegerField(verbose_name='步骤顺序')
    name = models.CharField(max_length=100, verbose_name='步骤名称')

    approver_type = models.CharField(
        max_length=30, choices=APPROVER_TYPE_CHOICES, default='USER', verbose_name='审批人类型'
    )

    # For USER type
    approver_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='workflow_steps',
        verbose_name='审批人',
    )

    # For ROLE type
    approver_role = models.ForeignKey(
        'accounts.Role',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='workflow_steps',
        verbose_name='审批角色',
    )

    action_type = models.CharField(
        max_length=20, choices=ACTION_TYPE_CHOICES, default='APPROVE', verbose_name='操作类型'
    )

    # Timeout settings
    timeout_hours = models.IntegerField(default=24, verbose_name='超时时间(小时)')

    # Can skip if amount is below threshold
    skip_amount_threshold = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='跳过金额阈值',
        help_text='低于此金额时跳过此步骤',
    )

    # CC recipients - users to be notified when this step is completed
    cc_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name='workflow_step_cc', verbose_name='抄送人'
    )

    # CC roles - all users with these roles will be notified
    cc_roles = models.ManyToManyField(
        'accounts.Role', blank=True, related_name='workflow_step_cc', verbose_name='抄送角色'
    )

    # Whether approver can reject
    can_reject = models.BooleanField(default=True, verbose_name='允许拒绝')

    class Meta:
        db_table = 'workflow_step'
        verbose_name = '审批步骤'
        verbose_name_plural = verbose_name
        ordering = ['workflow', 'step_order']
        unique_together = ['workflow', 'step_order']

    def __str__(self):
        return f'{self.workflow.name} - Step {self.step_order}: {self.name}'


class WorkflowInstance(BaseModel):
    """
    Workflow instance - a running instance of a workflow for a specific business object.
    """

    STATUS_CHOICES = [
        ('PENDING', '审批中'),
        ('APPROVED', '已通过'),
        ('REJECTED', '已拒绝'),
        ('CANCELLED', '已取消'),
        ('WITHDRAWN', '已撤回'),
    ]

    workflow = models.ForeignKey(
        WorkflowDefinition, on_delete=models.PROTECT, related_name='instances', verbose_name='流程定义'
    )

    # Generic relation to business object
    business_type = models.CharField(max_length=30, verbose_name='业务类型')
    business_id = models.IntegerField(verbose_name='业务ID')
    business_no = models.CharField(max_length=50, blank=True, verbose_name='业务单号')

    # Submitter info
    submitter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='submitted_workflows', verbose_name='提交人'
    )
    submit_time = models.DateTimeField(auto_now_add=True, verbose_name='提交时间')

    # Current status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', verbose_name='状态')
    current_step = models.IntegerField(default=1, verbose_name='当前步骤')

    # Amount for threshold checking
    amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name='金额')

    # Completion info
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='完成时间')

    class Meta:
        db_table = 'workflow_instance'
        verbose_name = '审批实例'
        verbose_name_plural = verbose_name
        ordering = ['-submit_time']
        indexes = [
            models.Index(fields=['business_type', 'business_id']),
            models.Index(fields=['status', 'submitter']),
        ]

    def __str__(self):
        return f'{self.workflow.name} - {self.business_no or self.business_id}'


class WorkflowTask(BaseModel):
    """
    Workflow task - individual approval task for each step.
    """

    STATUS_CHOICES = [
        ('PENDING', '待处理'),
        ('APPROVED', '已通过'),
        ('REJECTED', '已拒绝'),
        ('SKIPPED', '已跳过'),
        ('TIMEOUT', '已超时'),
    ]

    instance = models.ForeignKey(
        WorkflowInstance, on_delete=models.CASCADE, related_name='tasks', verbose_name='审批实例'
    )
    step = models.ForeignKey(WorkflowStep, on_delete=models.PROTECT, related_name='tasks', verbose_name='审批步骤')

    # Assignee
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='workflow_tasks', verbose_name='处理人'
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', verbose_name='状态')

    # Action info
    action_time = models.DateTimeField(null=True, blank=True, verbose_name='处理时间')
    comment = models.TextField(blank=True, verbose_name='审批意见')

    # Deadline
    deadline = models.DateTimeField(null=True, blank=True, verbose_name='截止时间')

    class Meta:
        db_table = 'workflow_task'
        verbose_name = '审批任务'
        verbose_name_plural = verbose_name
        ordering = ['instance', 'step__step_order']
        indexes = [
            models.Index(fields=['assignee', 'status']),
        ]

    def __str__(self):
        return f'{self.instance} - {self.step.name} - {self.assignee}'
