"""
Project management models.
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.core.models import BaseModel


class Project(BaseModel):
    """
    Project model - central hub for business operations.
    """
    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('PLANNING', '规划中'),
        ('ACTIVE', '进行中'),
        ('PAUSED', '暂停'),
        ('COMPLETED', '已完成'),
        ('CANCELLED', '已取消'),
        ('ARCHIVED', '已归档'),
    ]
    
    code = models.CharField(max_length=50, unique=True, verbose_name='项目编号')
    name = models.CharField(max_length=200, verbose_name='项目名称')
    customer = models.ForeignKey(
        'masterdata.Customer',
        on_delete=models.PROTECT,
        related_name='projects',
        verbose_name='客户'
    )
    sales_order = models.ForeignKey(
        'sales.SalesOrder',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='linked_projects',
        verbose_name='关联销售订单'
    )
    manager = models.ForeignKey(
        'accounts.User',
        on_delete=models.PROTECT,
        related_name='managed_projects',
        verbose_name='项目经理'
    )
    start_date = models.DateField(verbose_name='开始日期')
    end_date = models.DateField(verbose_name='结束日期')
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='DRAFT',
        verbose_name='状态'
    )
    
    # Budget fields
    budget_total = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name='总预算'
    )
    budget_material = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name='材料预算'
    )
    budget_labor = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name='人工预算'
    )
    budget_expense = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name='费用预算'
    )
    
    description = models.TextField(blank=True, verbose_name='项目描述')
    notes = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'project'
        verbose_name = '项目'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    def get_actual_material_cost(self):
        """Get actual material cost from stock moves."""
        from apps.inventory.models import StockMove
        from django.db.models import Sum, F
        
        result = StockMove.objects.filter(
            project=self,
            move_type='OUT_PROJECT',
            status='COMPLETED'
        ).aggregate(
            total=Sum(F('qty') * F('unit_cost'))
        )
        return result['total'] or 0
    
    def get_actual_labor_cost(self):
        """Get actual labor cost from project tasks."""
        from django.db.models import Sum, F
        
        result = ProjectMember.objects.filter(
            project=self
        ).aggregate(
            total=Sum(F('actual_hours') * F('hourly_rate'))
        )
        return result['total'] or 0
    
    def get_actual_expense_cost(self):
        """Get actual expense cost."""
        from apps.finance.models import Expense
        from django.db.models import Sum
        
        result = Expense.objects.filter(
            project=self,
            status='APPROVED'
        ).aggregate(total=Sum('amount'))
        return result['total'] or 0


class ProjectMember(BaseModel):
    """
    Project team member with hourly rate.
    """
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='members',
        verbose_name='项目'
    )
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='project_memberships',
        verbose_name='成员'
    )
    role = models.CharField(max_length=100, blank=True, verbose_name='项目角色')
    hourly_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name='时薪'
    )
    allocated_hours = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name='分配工时'
    )
    actual_hours = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name='实际工时'
    )
    is_active = models.BooleanField(default=True, verbose_name='激活状态')
    
    class Meta:
        db_table = 'project_member'
        verbose_name = '项目成员'
        verbose_name_plural = verbose_name
        unique_together = ['project', 'user']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.project.code} - {self.user.get_full_name()}"


class ProjectTask(BaseModel):
    """
    Project task with WBS (Work Breakdown Structure) support.
    """
    STATUS_CHOICES = [
        ('TODO', '待办'),
        ('IN_PROGRESS', '进行中'),
        ('COMPLETED', '已完成'),
        ('CANCELLED', '已取消'),
    ]
    
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='tasks',
        verbose_name='项目'
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='subtasks',
        verbose_name='父任务'
    )
    code = models.CharField(max_length=50, verbose_name='任务编号')
    name = models.CharField(max_length=200, verbose_name='任务名称')
    assignee = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_tasks',
        verbose_name='负责人'
    )
    planned_hours = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name='计划工时'
    )
    actual_hours = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name='实际工时'
    )
    progress_percent = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='完成进度(%)'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='TODO',
        verbose_name='状态'
    )
    start_date = models.DateField(null=True, blank=True, verbose_name='开始日期')
    end_date = models.DateField(null=True, blank=True, verbose_name='结束日期')
    description = models.TextField(blank=True, verbose_name='描述')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    
    class Meta:
        db_table = 'project_task'
        verbose_name = '项目任务'
        verbose_name_plural = verbose_name
        unique_together = ['project', 'code']
        ordering = ['project', 'sort_order', 'code']
    
    def __str__(self):
        return f"{self.project.code} - {self.code} - {self.name}"


class ProjectBOM(BaseModel):
    """
    Project Bill of Materials - planning material requirements.
    """
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='bom_items',
        verbose_name='项目'
    )
    item = models.ForeignKey(
        'masterdata.Item',
        on_delete=models.PROTECT,
        related_name='project_boms',
        verbose_name='物料'
    )
    planned_qty = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name='计划数量'
    )
    actual_qty = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name='实际使用数量'
    )
    estimated_cost = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name='预估成本'
    )
    notes = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'project_bom'
        verbose_name = '项目BOM'
        verbose_name_plural = verbose_name
        unique_together = ['project', 'item']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.project.code} - {self.item.sku}"


class TimeLog(BaseModel):
    """
    Time logging for project tasks.
    """
    STATUS_CHOICES = [
        ('PENDING', '待审核'),
        ('APPROVED', '已通过'),
        ('REJECTED', '已驳回'),
    ]
    
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='time_logs',
        verbose_name='项目'
    )
    task = models.ForeignKey(
        ProjectTask,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='time_logs',
        verbose_name='任务'
    )
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='time_logs',
        verbose_name='用户'
    )
    date = models.DateField(verbose_name='日期')
    hours = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name='工时'
    )
    description = models.TextField(blank=True, verbose_name='工作内容')
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
        verbose_name='状态'
    )
    
    class Meta:
        db_table = 'project_time_log'
        verbose_name = '工时记录'
        verbose_name_plural = verbose_name
        ordering = ['-date', '-created_at']
    
    def __str__(self):
        return f"{self.project.code} - {self.user.username} - {self.date} - {self.hours}h"


class ECN(BaseModel):
    """
    Engineering Change Notice - 工程变更通知
    """
    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('PENDING', '待评审'),
        ('REVIEWING', '评审中'),
        ('APPROVED', '已批准'),
        ('REJECTED', '已拒绝'),
        ('IMPLEMENTING', '实施中'),
        ('COMPLETED', '已完成'),
        ('CANCELLED', '已取消'),
    ]
    
    CHANGE_TYPE_CHOICES = [
        ('DESIGN', '设计变更'),
        ('PROCESS', '工艺变更'),
        ('MATERIAL', '材料替换'),
        ('SPEC', '规格变更'),
        ('DRAWING', '图纸变更'),
        ('OTHER', '其他变更'),
    ]
    
    PRIORITY_CHOICES = [
        ('URGENT', '紧急'),
        ('HIGH', '高'),
        ('MEDIUM', '中'),
        ('LOW', '低'),
    ]
    
    ecn_no = models.CharField(max_length=50, unique=True, verbose_name='变更编号')
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='ecns',
        verbose_name='项目'
    )
    title = models.CharField(max_length=200, verbose_name='变更标题')
    change_type = models.CharField(
        max_length=20,
        choices=CHANGE_TYPE_CHOICES,
        default='DESIGN',
        verbose_name='变更类型'
    )
    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default='MEDIUM',
        verbose_name='优先级'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='DRAFT',
        verbose_name='状态'
    )
    reason = models.TextField(verbose_name='变更原因')
    description = models.TextField(verbose_name='变更描述')
    impact_analysis = models.TextField(blank=True, verbose_name='影响分析')
    cost_impact = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name='成本影响'
    )
    schedule_impact = models.CharField(max_length=200, blank=True, verbose_name='进度影响')
    
    # 申请信息
    requested_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.PROTECT,
        related_name='requested_ecns',
        verbose_name='申请人'
    )
    requested_date = models.DateField(verbose_name='申请日期')
    
    # 批准信息
    approved_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_ecns',
        verbose_name='批准人'
    )
    approved_date = models.DateField(null=True, blank=True, verbose_name='批准日期')
    
    # 实施信息
    implemented_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='implemented_ecns',
        verbose_name='实施人'
    )
    implemented_date = models.DateField(null=True, blank=True, verbose_name='实施日期')
    implementation_notes = models.TextField(blank=True, verbose_name='实施说明')
    
    class Meta:
        db_table = 'project_ecn'
        verbose_name = '工程变更通知'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.ecn_no} - {self.title}"
    
    def save(self, *args, **kwargs):
        if not self.ecn_no:
            # 自动生成ECN编号
            from django.utils import timezone
            today = timezone.now()
            prefix = f"ECN{today.strftime('%Y%m%d')}"
            last_ecn = ECN.objects.filter(ecn_no__startswith=prefix).order_by('-ecn_no').first()
            if last_ecn:
                last_num = int(last_ecn.ecn_no[-4:])
                self.ecn_no = f"{prefix}{last_num + 1:04d}"
            else:
                self.ecn_no = f"{prefix}0001"
        super().save(*args, **kwargs)


class ECNItem(BaseModel):
    """
    ECN变更明细 - 记录具体的变更内容
    """
    ITEM_CHANGE_TYPE_CHOICES = [
        ('ADD', '新增'),
        ('DELETE', '删除'),
        ('MODIFY', '修改'),
        ('REPLACE', '替换'),
    ]
    
    ecn = models.ForeignKey(
        ECN,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='ECN'
    )
    bom_item = models.ForeignKey(
        ProjectBOM,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ecn_items',
        verbose_name='BOM条目'
    )
    item = models.ForeignKey(
        'masterdata.Item',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='ecn_items',
        verbose_name='物料'
    )
    new_item = models.ForeignKey(
        'masterdata.Item',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='ecn_new_items',
        verbose_name='新物料（替换时使用）'
    )
    change_type = models.CharField(
        max_length=20,
        choices=ITEM_CHANGE_TYPE_CHOICES,
        default='MODIFY',
        verbose_name='变更类型'
    )
    field_name = models.CharField(max_length=100, blank=True, verbose_name='变更字段')
    old_value = models.TextField(blank=True, verbose_name='原值')
    new_value = models.TextField(blank=True, verbose_name='新值')
    old_qty = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='原数量'
    )
    new_qty = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='新数量'
    )
    notes = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'project_ecn_item'
        verbose_name = 'ECN变更明细'
        verbose_name_plural = verbose_name
        ordering = ['id']
    
    def __str__(self):
        return f"{self.ecn.ecn_no} - {self.get_change_type_display()}"


class ECNApproval(BaseModel):
    """
    ECN审批记录
    """
    ACTION_CHOICES = [
        ('SUBMIT', '提交评审'),
        ('APPROVE', '批准'),
        ('REJECT', '拒绝'),
        ('RETURN', '退回修改'),
        ('IMPLEMENT', '开始实施'),
        ('COMPLETE', '完成实施'),
        ('CANCEL', '取消'),
    ]
    
    ecn = models.ForeignKey(
        ECN,
        on_delete=models.CASCADE,
        related_name='approvals',
        verbose_name='ECN'
    )
    approver = models.ForeignKey(
        'accounts.User',
        on_delete=models.PROTECT,
        related_name='ecn_approvals',
        verbose_name='操作人'
    )
    action = models.CharField(
        max_length=20,
        choices=ACTION_CHOICES,
        verbose_name='操作'
    )
    comment = models.TextField(blank=True, verbose_name='审批意见')
    
    class Meta:
        db_table = 'project_ecn_approval'
        verbose_name = 'ECN审批记录'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.ecn.ecn_no} - {self.approver.username} - {self.get_action_display()}"

