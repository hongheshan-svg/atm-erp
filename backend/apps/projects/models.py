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
        ('PENDING', '审批中'),
        ('REJECTED', '已拒绝'),
        ('IN_PROGRESS', '进行中'),
        ('ACTIVE', '进行中'),  # 保留兼容
        ('PAUSED', '暂停'),
        ('COMPLETED', '已完成'),
        ('CANCELLED', '已取消'),
        ('ARCHIVED', '已归档'),
    ]
    
    code = models.CharField(max_length=50, unique=True, blank=True, verbose_name='项目编号')
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
    
    def save(self, *args, **kwargs):
        # 自动生成项目编号
        if not self.code:
            from apps.core.utils import generate_code
            self.code = generate_code('PRJ', rule_type='PROJECT')
        super().save(*args, **kwargs)
    
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

    def get_total_receivables(self):
        """Get total receivables amount for this project."""
        from apps.finance.models import AccountReceivable
        from django.db.models import Sum
        
        result = AccountReceivable.objects.filter(
            project=self,
            is_deleted=False
        ).aggregate(total=Sum('amount_due'))
        return result['total'] or 0
    
    def get_total_payables(self):
        """Get total payables amount for this project."""
        from apps.finance.models import AccountPayable
        from django.db.models import Sum
        
        result = AccountPayable.objects.filter(
            project=self,
            is_deleted=False
        ).aggregate(total=Sum('amount_due'))
        return result['total'] or 0
    
    def get_invoice_summary(self):
        """Get invoice summary for this project (input vs output)."""
        from apps.finance.models import Invoice
        from django.db.models import Sum, Count, Q
        
        result = Invoice.objects.filter(
            project=self,
            is_deleted=False
        ).aggregate(
            input_count=Count('id', filter=Q(invoice_type='INPUT')),
            input_amount=Sum('total_amount', filter=Q(invoice_type='INPUT')),
            output_count=Count('id', filter=Q(invoice_type='OUTPUT')),
            output_amount=Sum('total_amount', filter=Q(invoice_type='OUTPUT')),
        )
        return {
            'input_count': result['input_count'] or 0,
            'input_amount': result['input_amount'] or 0,
            'output_count': result['output_count'] or 0,
            'output_amount': result['output_amount'] or 0,
        }
    
    def get_bank_statement_summary(self):
        """Get bank statement summary for this project."""
        from apps.finance.bank_statement_models import BankStatement
        from django.db.models import Sum, Count, Q
        
        result = BankStatement.objects.filter(
            project=self,
            is_deleted=False
        ).aggregate(
            income_count=Count('id', filter=Q(transaction_type='CREDIT')),
            income_amount=Sum('credit_amount', filter=Q(transaction_type='CREDIT')),
            expense_count=Count('id', filter=Q(transaction_type='DEBIT')),
            expense_amount=Sum('debit_amount', filter=Q(transaction_type='DEBIT')),
        )
        return {
            'income_count': result['income_count'] or 0,
            'income_amount': result['income_amount'] or 0,
            'expense_count': result['expense_count'] or 0,
            'expense_amount': result['expense_amount'] or 0,
        }


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
    针对非标自动化行业优化，支持工位装配、需求追溯、成本管理等
    """
    # ==================== 图纸状态 ====================
    HAS_DRAWING_CHOICES = [
        ('YES', '有图'),
        ('NO', '无图'),
        ('PENDING', '待定'),
        ('DESIGNING', '设计中'),
    ]
    
    # ==================== 下单/采购状态 ====================
    ORDER_STATUS_CHOICES = [
        ('NOT_ORDERED', '未下单'),         # 初始状态
        ('PR_PENDING', '采购申请中'),      # 已创建采购申请（草稿/待审批）
        ('PR_APPROVED', '申请已批准'),     # 采购申请已批准，待转订单
        ('PARTIAL', '部分下单'),           # 部分数量已下单
        ('ORDERED', '已下单'),             # 全部数量已下单
        ('IN_TRANSIT', '在途'),            # 供应商已发货
        ('PARTIAL_RECEIVED', '部分收货'),  # 部分数量已收货
        ('RECEIVED', '已收货'),            # 全部数量已收货
        ('RETURNED', '已退货'),            # 退货
        ('CANCELLED', '已取消'),           # 采购取消
    ]
    
    # ==================== 物料属性(可覆盖Item默认值) ====================
    ITEM_PROPERTY_CHOICES = [
        ('', '继承物料属性'),
        ('STANDARD', '标准件'),
        ('PURCHASED', '外购件'),
        ('OUTSOURCED', '外协件'),
        ('SELF_MADE', '自制件'),
        ('CONSUMABLE', '易耗品'),
        ('VIRTUAL', '虚拟件'),
        ('ASSEMBLY', '组件'),
    ]
    
    # ==================== 优先级 ====================
    PRIORITY_CHOICES = [
        ('LOW', '低'),
        ('NORMAL', '普通'),
        ('HIGH', '高'),
        ('URGENT', '紧急'),
    ]
    
    # ==================== 状态 ====================
    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('CONFIRMED', '已确认'),
        ('RELEASED', '已下发'),
        ('COMPLETED', '已完成'),
        ('CANCELLED', '已取消'),
    ]
    
    # ==================== 基础信息 ====================
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
    
    # 项目内物料编码(可自定义)
    item_code = models.CharField(max_length=50, blank=True, verbose_name='项目物料编码')
    
    # 物料属性覆盖
    item_property = models.CharField(
        max_length=20,
        choices=ITEM_PROPERTY_CHOICES,
        blank=True,
        default='',
        verbose_name='物料属性',
        help_text='留空则继承物料主数据的属性'
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='DRAFT',
        verbose_name='状态'
    )
    
    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default='NORMAL',
        verbose_name='优先级'
    )
    
    # ==================== 数量信息 ====================
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
    
    # 单位用量（子件对父件的用量）
    unit_qty = models.DecimalField(
        max_digits=15,
        decimal_places=4,
        default=1,
        verbose_name='单位用量'
    )
    
    # 损耗率(百分比)
    scrap_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name='损耗率(%)'
    )
    
    # ==================== 成本信息 ====================
    estimated_cost = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name='预估单价'
    )
    target_cost = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='目标成本',
        help_text='该物料的目标采购成本'
    )
    actual_cost = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name='实际成本'
    )
    total_cost = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0,
        verbose_name='总成本',
        help_text='实际成本 × 实际数量'
    )
    
    # ==================== 图纸与技术资料 ====================
    version_brand = models.CharField(max_length=100, blank=True, verbose_name='版本/品牌')
    has_drawing = models.CharField(
        max_length=10,
        choices=HAS_DRAWING_CHOICES,
        default='PENDING',
        verbose_name='有图/无图'
    )
    
    # 图纸关联
    drawing = models.ForeignKey(
        'projects.Drawing',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bom_items',
        verbose_name='关联图纸'
    )
    drawing_no = models.CharField(max_length=100, blank=True, verbose_name='图纸号')
    drawing_version = models.CharField(max_length=50, blank=True, verbose_name='图纸版本')
    
    # 技术规格覆盖
    material_spec = models.CharField(max_length=200, blank=True, verbose_name='材质规格',
                                     help_text='可覆盖物料主数据中的材质要求')
    surface_treatment = models.CharField(max_length=100, blank=True, verbose_name='表面处理')
    technical_requirement = models.TextField(blank=True, verbose_name='技术要求')
    
    # ==================== 装配与工艺(非标自动化专用) ====================
    work_center = models.ForeignKey(
        'production.WorkCenter',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='project_bom_items',
        verbose_name='装配工位'
    )
    process = models.ForeignKey(
        'production.ProductionProcess',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='project_bom_items',
        verbose_name='工序'
    )
    assembly_sequence = models.IntegerField(default=0, verbose_name='装配顺序',
                                            help_text='在工位上的装配先后顺序')
    
    # 装配说明
    assembly_instruction = models.TextField(blank=True, verbose_name='装配说明')
    
    # ==================== 需求追溯 ====================
    requirement_id_ref = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='关联需求ID',
        help_text='该物料对应的客户需求ID'
    )
    
    # 功能模块标识
    function_module = models.CharField(max_length=100, blank=True, verbose_name='功能模块',
                                       help_text='如：上料机构、定位机构、检测模块')
    
    # ==================== 日期与时间 ====================
    required_date = models.DateField(null=True, blank=True, verbose_name='需求日期')
    latest_order_date = models.DateField(null=True, blank=True, verbose_name='最晚下单日期',
                                         help_text='根据需求日期和采购周期自动计算')
    
    requester = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='requested_boms',
        verbose_name='申请人'
    )
    
    description = models.TextField(blank=True, verbose_name='说明')
    notes = models.TextField(blank=True, verbose_name='备注')
    
    # ==================== 采购与库存跟踪 ====================
    order_status = models.CharField(
        max_length=20,
        choices=ORDER_STATUS_CHOICES,
        default='NOT_ORDERED',
        verbose_name='下单状态'
    )
    supplier = models.ForeignKey(
        'masterdata.Supplier',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bom_items',
        verbose_name='供应商'
    )
    delivery_date = models.DateField(null=True, blank=True, verbose_name='预计交期')
    actual_delivery_date = models.DateField(null=True, blank=True, verbose_name='实际到货日期')
    
    ordered_qty = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name='已下单数量'
    )
    received_qty = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name='已入库数量'
    )
    issued_qty = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name='已出库数量'
    )
    reserved_qty = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name='预留数量',
        help_text='从库存预留的数量'
    )
    
    # 采购申请关联
    purchase_request = models.ForeignKey(
        'purchase.PurchaseRequest',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bom_items',
        verbose_name='采购申请'
    )
    pr_qty = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name='采购申请数量',
        help_text='已创建采购申请的数量'
    )
    
    # 采购订单关联
    purchase_order = models.ForeignKey(
        'purchase.PurchaseOrder',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bom_items',
        verbose_name='采购订单'
    )
    
    # 发货和退货数量
    shipped_qty = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name='已发货数量',
        help_text='供应商已发货的数量（在途）'
    )
    returned_qty = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name='退货数量'
    )
    
    # ==================== 质量与检验 ====================
    inspection_required = models.BooleanField(default=True, verbose_name='需要检验')
    inspection_passed = models.BooleanField(null=True, blank=True, verbose_name='检验通过')
    inspection_notes = models.TextField(blank=True, verbose_name='检验备注')
    
    # ==================== 多级BOM结构 ====================
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        verbose_name='父级物料'
    )
    level = models.IntegerField(default=0, verbose_name='BOM层级')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    
    # 关键件标识
    is_critical = models.BooleanField(default=False, verbose_name='关键件',
                                      help_text='影响项目关键路径的物料')
    is_long_lead = models.BooleanField(default=False, verbose_name='长周期件',
                                       help_text='采购周期较长需要提前采购')
    
    # ==================== 询价信息 ====================
    QUOTE_STATUS_CHOICES = [
        ('NOT_QUOTED', '未询价'),
        ('QUOTING', '询价中'),
        ('QUOTED', '已询价'),
    ]
    
    quote_status = models.CharField(
        max_length=20,
        choices=QUOTE_STATUS_CHOICES,
        default='NOT_QUOTED',
        verbose_name='询价状态'
    )
    quote_supplier = models.ForeignKey(
        'masterdata.Supplier',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='quoted_bom_items',
        verbose_name='询价供应商'
    )
    price_with_tax = models.DecimalField(
        max_digits=15,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name='含税单价'
    )
    price_without_tax = models.DecimalField(
        max_digits=15,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name='未税单价'
    )
    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='税率(%)',
        help_text='如13表示13%'
    )
    quote_delivery_days = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='报价交期(天)'
    )
    quote_date = models.DateField(
        null=True,
        blank=True,
        verbose_name='询价日期'
    )
    quote_notes = models.TextField(blank=True, verbose_name='询价备注')
    
    # ==================== 扩展字段 ====================
    extra_fields = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='扩展字段',
        help_text='用户自定义的扩展字段'
    )
    
    class Meta:
        db_table = 'project_bom'
        verbose_name = '项目BOM'
        verbose_name_plural = verbose_name
        ordering = ['project', 'level', 'sort_order', '-created_at']
        indexes = [
            models.Index(fields=['project', 'status']),
            models.Index(fields=['order_status']),
            models.Index(fields=['is_critical']),
            models.Index(fields=['required_date']),
            models.Index(fields=['function_module']),
        ]
    
    def __str__(self):
        return f"{self.project.code} - {self.item.sku}"
    
    @property
    def effective_item_property(self):
        """获取有效的物料属性(优先使用BOM上的覆盖值)"""
        return self.item_property or self.item.item_property
    
    @property
    def shortage_qty(self):
        """缺料数量"""
        return max(0, self.planned_qty - self.received_qty - self.reserved_qty)
    
    @property
    def is_overdue(self):
        """是否延期"""
        from datetime import date
        if self.required_date and self.order_status not in ['RECEIVED', 'COMPLETED']:
            return date.today() > self.required_date
        return False
    
    def calculate_latest_order_date(self):
        """计算最晚下单日期"""
        from datetime import timedelta
        if self.required_date and self.item:
            lead_time = self.item.lead_time or 0
            self.latest_order_date = self.required_date - timedelta(days=lead_time)
            return self.latest_order_date
        return None
    
    def update_total_cost(self):
        """更新总成本"""
        self.total_cost = self.actual_cost * self.actual_qty
        return self.total_cost


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


# ==================== 售后管理模型 ====================

class AfterSalesOrder(BaseModel):
    """
    售后工单模型 - 用于跟踪项目交付后的售后服务请求
    """
    TYPE_CHOICES = [
        ('WARRANTY', '保修服务'),
        ('REPAIR', '维修服务'),
        ('MAINTENANCE', '保养维护'),
        ('UPGRADE', '升级改造'),
        ('TRAINING', '培训服务'),
        ('INSPECTION', '巡检服务'),
        ('COMPLAINT', '客户投诉'),
        ('OTHER', '其他'),
    ]
    
    PRIORITY_CHOICES = [
        ('LOW', '低'),
        ('MEDIUM', '中'),
        ('HIGH', '高'),
        ('URGENT', '紧急'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', '待处理'),
        ('ASSIGNED', '已派单'),
        ('IN_PROGRESS', '处理中'),
        ('ON_SITE', '现场服务'),
        ('WAITING_PARTS', '等待备件'),
        ('RESOLVED', '已解决'),
        ('CLOSED', '已关闭'),
        ('CANCELLED', '已取消'),
    ]
    
    order_no = models.CharField(max_length=50, unique=True, verbose_name='工单编号')
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='aftersales_orders',
        verbose_name='关联项目'
    )
    customer = models.ForeignKey(
        'masterdata.Customer',
        on_delete=models.PROTECT,
        related_name='aftersales_orders',
        verbose_name='客户'
    )
    order_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default='REPAIR',
        verbose_name='工单类型'
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
        default='PENDING',
        verbose_name='状态'
    )
    
    # 问题描述
    title = models.CharField(max_length=200, verbose_name='问题标题')
    description = models.TextField(verbose_name='问题描述')
    equipment_info = models.CharField(max_length=500, blank=True, verbose_name='设备信息')
    fault_code = models.CharField(max_length=50, blank=True, verbose_name='故障代码')
    
    # 联系信息
    contact_person = models.CharField(max_length=50, verbose_name='联系人')
    contact_phone = models.CharField(max_length=20, verbose_name='联系电话')
    site_address = models.CharField(max_length=500, blank=True, verbose_name='现场地址')
    
    # 时间信息
    reported_at = models.DateTimeField(auto_now_add=True, verbose_name='报修时间')
    expected_date = models.DateField(null=True, blank=True, verbose_name='期望完成日期')
    resolved_at = models.DateTimeField(null=True, blank=True, verbose_name='解决时间')
    closed_at = models.DateTimeField(null=True, blank=True, verbose_name='关闭时间')
    
    # 责任人
    assigned_to = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_aftersales',
        verbose_name='负责人'
    )
    
    # 费用信息
    is_warranty = models.BooleanField(default=True, verbose_name='是否保修期内')
    labor_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='人工费用')
    travel_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='差旅费用')
    parts_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='备件费用')
    other_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='其他费用')
    
    # 解决方案
    solution = models.TextField(blank=True, verbose_name='解决方案')
    root_cause = models.TextField(blank=True, verbose_name='根本原因')
    preventive_action = models.TextField(blank=True, verbose_name='预防措施')
    
    # 客户满意度
    satisfaction_score = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name='满意度评分(1-5)'
    )
    customer_feedback = models.TextField(blank=True, verbose_name='客户反馈')
    
    class Meta:
        db_table = 'aftersales_order'
        verbose_name = '售后工单'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.order_no} - {self.title}"
    
    @property
    def total_cost(self):
        """计算总成本"""
        return self.labor_cost + self.travel_cost + self.parts_cost + self.other_cost


class ServiceRecord(BaseModel):
    """
    服务记录模型 - 记录每次服务的详细信息
    """
    SERVICE_TYPE_CHOICES = [
        ('REMOTE', '远程支持'),
        ('ON_SITE', '现场服务'),
        ('PHONE', '电话支持'),
        ('VIDEO', '视频会议'),
    ]
    
    aftersales_order = models.ForeignKey(
        AfterSalesOrder,
        on_delete=models.CASCADE,
        related_name='service_records',
        verbose_name='售后工单'
    )
    service_type = models.CharField(
        max_length=20,
        choices=SERVICE_TYPE_CHOICES,
        default='ON_SITE',
        verbose_name='服务类型'
    )
    technician = models.ForeignKey(
        'accounts.User',
        on_delete=models.PROTECT,
        related_name='service_records',
        verbose_name='服务人员'
    )
    
    # 时间记录
    service_date = models.DateField(verbose_name='服务日期')
    start_time = models.TimeField(null=True, blank=True, verbose_name='开始时间')
    end_time = models.TimeField(null=True, blank=True, verbose_name='结束时间')
    work_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='工时(小时)')
    
    # 服务内容
    work_content = models.TextField(verbose_name='工作内容')
    findings = models.TextField(blank=True, verbose_name='现场发现')
    actions_taken = models.TextField(blank=True, verbose_name='采取措施')
    result = models.TextField(blank=True, verbose_name='服务结果')
    next_steps = models.TextField(blank=True, verbose_name='后续计划')
    
    # 费用
    labor_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='人工费用')
    travel_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='差旅费用')
    
    # 客户签字
    customer_signature = models.CharField(max_length=100, blank=True, verbose_name='客户签字')
    signed_at = models.DateTimeField(null=True, blank=True, verbose_name='签字时间')
    
    class Meta:
        db_table = 'aftersales_service_record'
        verbose_name = '服务记录'
        verbose_name_plural = verbose_name
        ordering = ['-service_date', '-start_time']
    
    def __str__(self):
        return f"{self.aftersales_order.order_no} - {self.service_date}"


class SparePartUsage(BaseModel):
    """
    备件使用记录 - 跟踪售后服务中的备件消耗
    """
    aftersales_order = models.ForeignKey(
        AfterSalesOrder,
        on_delete=models.CASCADE,
        related_name='spare_parts',
        verbose_name='售后工单'
    )
    service_record = models.ForeignKey(
        ServiceRecord,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='spare_parts',
        verbose_name='服务记录'
    )
    item = models.ForeignKey(
        'masterdata.Item',
        on_delete=models.PROTECT,
        related_name='spare_part_usages',
        verbose_name='备件'
    )
    
    qty = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='数量')
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='单价')
    is_warranty = models.BooleanField(default=True, verbose_name='保修范围')
    is_replaced = models.BooleanField(default=True, verbose_name='是否更换')
    serial_no = models.CharField(max_length=100, blank=True, verbose_name='序列号')
    notes = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'aftersales_spare_part_usage'
        verbose_name = '备件使用记录'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.aftersales_order.order_no} - {self.item.name}"
    
    @property
    def total_cost(self):
        return self.qty * self.unit_cost


class Drawing(BaseModel):
    """
    图纸管理 - 管理项目和物料相关的图纸文件
    """
    FILE_TYPE_CHOICES = [
        ('PDF', 'PDF文件'),
        ('DWG', 'AutoCAD图纸'),
        ('DXF', 'DXF文件'),
        ('STEP', 'STEP 3D文件'),
        ('STP', 'STP 3D文件'),
        ('IGES', 'IGES文件'),
        ('STL', 'STL文件'),
        ('SOLIDWORKS', 'SolidWorks文件'),
        ('OTHER', '其他'),
    ]
    
    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('REVIEWING', '审核中'),
        ('APPROVED', '已批准'),
        ('RELEASED', '已发布'),
        ('OBSOLETE', '已废弃'),
    ]
    
    drawing_no = models.CharField(max_length=100, verbose_name='图纸号')
    name = models.CharField(max_length=200, verbose_name='图纸名称')
    version = models.CharField(max_length=20, default='A0', verbose_name='版本')
    revision = models.IntegerField(default=1, verbose_name='修订号')
    
    # 关联
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='drawings',
        verbose_name='所属项目'
    )
    item = models.ForeignKey(
        'masterdata.Item',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='drawings',
        verbose_name='关联物料'
    )
    bom_item = models.ForeignKey(
        'projects.ProjectBOM',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='drawings',
        verbose_name='关联BOM项'
    )
    
    # 文件信息
    file_type = models.CharField(
        max_length=20,
        choices=FILE_TYPE_CHOICES,
        default='PDF',
        verbose_name='文件类型'
    )
    file_path = models.CharField(max_length=500, verbose_name='文件路径')
    file_size = models.BigIntegerField(default=0, verbose_name='文件大小(bytes)')
    
    # 公共盘存储路径
    public_share_path = models.CharField(max_length=500, blank=True, verbose_name='公共盘路径')
    
    # 状态
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='DRAFT',
        verbose_name='状态'
    )
    
    # 审批信息
    designer = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='designed_drawings',
        verbose_name='设计者'
    )
    reviewer = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_drawings',
        verbose_name='审核人'
    )
    approver = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_drawings',
        verbose_name='批准人'
    )
    
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name='批准时间')
    released_at = models.DateTimeField(null=True, blank=True, verbose_name='发布时间')
    
    # 变更信息
    change_description = models.TextField(blank=True, verbose_name='变更说明')
    
    notes = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'project_drawing'
        verbose_name = '图纸'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
        unique_together = [['drawing_no', 'version', 'revision']]
    
    def __str__(self):
        return f"{self.drawing_no} v{self.version}.{self.revision}"


class DrawingChangeNotice(BaseModel):
    """
    图纸变更通知 - 记录图纸变更并发送邮件提醒
    """
    CHANGE_TYPE_CHOICES = [
        ('NEW', '新增'),
        ('REVISION', '修订'),
        ('OBSOLETE', '废弃'),
    ]
    
    drawing = models.ForeignKey(
        Drawing,
        on_delete=models.CASCADE,
        related_name='change_notices',
        verbose_name='图纸'
    )
    change_type = models.CharField(
        max_length=20,
        choices=CHANGE_TYPE_CHOICES,
        default='NEW',
        verbose_name='变更类型'
    )
    old_version = models.CharField(max_length=20, blank=True, verbose_name='原版本')
    new_version = models.CharField(max_length=20, blank=True, verbose_name='新版本')
    change_description = models.TextField(verbose_name='变更说明')
    
    # 通知
    notified_users = models.ManyToManyField(
        'accounts.User',
        related_name='drawing_notifications',
        blank=True,
        verbose_name='通知人员'
    )
    email_sent = models.BooleanField(default=False, verbose_name='邮件已发送')
    email_sent_at = models.DateTimeField(null=True, blank=True, verbose_name='发送时间')
    
    class Meta:
        db_table = 'project_drawing_change_notice'
        verbose_name = '图纸变更通知'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.drawing.drawing_no} - {self.get_change_type_display()}"


# 导入设备和工装模型，使其成为 projects app 的一部分
from .equipment_models import (
    Equipment, EquipmentShipment, EquipmentInstallation,
    InstallationLog, EquipmentAcceptance, MaintenanceSchedule, TrainingRecord
)
from .fixture_models import (
    FixtureCategory, Fixture, FixtureUsageRecord,
    FixtureCalibration, FixtureMaintenance
)


# Import models from requirement_review
from .requirement_review import (
    ReviewTemplate, ReviewCheckItem, RequirementReview,
    ReviewParticipant, ReviewItemResult, ReviewActionItem
)

# Import models from bom_advanced
from .bom_advanced import BOMSubstitute, BOMVersion, BOMComparison

# Import models from cad_integration
from .cad_integration import (
    CADSoftware, CADSession, CADFile,
    CADBOMImport, CADBOMItem, CADPropertyMapping
)
