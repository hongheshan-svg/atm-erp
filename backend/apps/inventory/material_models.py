"""
生产领料/退料管理模型

支持两种场景：
1. 项目领料/退料 - 与项目关联
2. 售后领料/退料 - 与售后工单关联
"""

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import BaseModel


class MaterialRequisition(BaseModel):
    """
    领料单 - 生产领料申请
    """

    TYPE_CHOICES = [
        ('PROJECT', '项目领料'),
        ('AFTERSALES', '售后领料'),
    ]

    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('SUBMITTED', '待审批'),  # 申请物料 - 提交后待审批
        ('APPROVED', '已批准'),  # 申请物料 - 审批通过
        ('PENDING', '待备料'),  # 备料确认 - 等待仓库备料
        ('PREPARING', '备料中'),  # 备料确认 - 仓库正在备料
        ('READY', '备料完成'),  # 备料确认 - 备料完成待出库
        ('ISSUED', '已出库'),
        ('PARTIAL', '部分出库'),
        ('REJECTED', '已拒绝'),  # 申请物料 - 审批拒绝
        ('CANCELLED', '已取消'),
    ]

    requisition_no = models.CharField(max_length=50, unique=True, verbose_name='领料单号')
    requisition_type = models.CharField(max_length=20, choices=TYPE_CHOICES, verbose_name='领料类型')

    # 项目领料时关联
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='material_requisitions',
        verbose_name='关联项目',
    )

    # 售后领料时关联
    aftersales_order = models.ForeignKey(
        'projects.AfterSalesOrder',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='material_requisitions',
        verbose_name='售后工单',
    )

    # 出库仓库
    warehouse = models.ForeignKey(
        'masterdata.Warehouse', on_delete=models.PROTECT, related_name='material_requisitions', verbose_name='出库仓库'
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', verbose_name='状态')

    # 申请人和日期
    requestor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='material_requisitions', verbose_name='申请人'
    )
    request_date = models.DateField(default=timezone.localdate, verbose_name='申请日期')
    required_date = models.DateField(null=True, blank=True, verbose_name='需求日期')

    # 仓库处理
    warehouse_operator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='handled_requisitions',
        verbose_name='仓库操作员',
    )
    issue_date = models.DateTimeField(null=True, blank=True, verbose_name='出库时间')

    notes = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'material_requisition'
        verbose_name = '领料单'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.requisition_no} - {self.get_requisition_type_display()}'

    def save(self, *args, **kwargs):
        if not self.requisition_no:
            from apps.core.utils import generate_code

            self.requisition_no = generate_code('MR', rule_type='MATERIAL_REQUISITION')
        super().save(*args, **kwargs)

    @property
    def total_qty(self):
        """领料总数量"""
        return sum(line.qty for line in self.lines.all())

    @property
    def issued_qty(self):
        """已出库总数量"""
        return sum(line.issued_qty for line in self.lines.all())


class MaterialRequisitionLine(BaseModel):
    """
    领料单明细
    """

    requisition = models.ForeignKey(
        MaterialRequisition, on_delete=models.CASCADE, related_name='lines', verbose_name='领料单'
    )
    item = models.ForeignKey(
        'masterdata.Item', on_delete=models.PROTECT, related_name='requisition_lines', verbose_name='物料'
    )
    qty = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='申请数量')
    issued_qty = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='已出库数量')
    unit_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='单位成本')
    notes = models.CharField(max_length=200, blank=True, verbose_name='备注')

    class Meta:
        db_table = 'material_requisition_line'
        verbose_name = '领料单明细'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'{self.requisition.requisition_no} - {self.item.sku}'

    @property
    def pending_qty(self):
        """待出库数量"""
        return self.qty - self.issued_qty

    @property
    def line_amount(self):
        """行金额"""
        return self.issued_qty * self.unit_cost


class MaterialReturn(BaseModel):
    """
    退料单 - 生产退料申请
    """

    TYPE_CHOICES = [
        ('PROJECT', '项目退料'),
        ('AFTERSALES', '售后退料'),
    ]

    REASON_CHOICES = [
        ('SURPLUS', '物料剩余'),
        ('REPLACEMENT', '物料更换'),
        ('SCRAP', '物料报废'),
        ('DEFECTIVE', '物料不良'),
        ('OTHER', '其他'),
    ]

    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('PENDING', '待入库'),
        ('INSPECTING', '检验中'),
        ('COMPLETED', '已入库'),
        ('PARTIAL', '部分入库'),
        ('REJECTED', '已拒绝'),
        ('CANCELLED', '已取消'),
    ]

    return_no = models.CharField(max_length=50, unique=True, verbose_name='退料单号')
    return_type = models.CharField(max_length=20, choices=TYPE_CHOICES, verbose_name='退料类型')
    return_reason = models.CharField(max_length=20, choices=REASON_CHOICES, default='SURPLUS', verbose_name='退料原因')

    # 项目退料时关联
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='material_returns',
        verbose_name='关联项目',
    )

    # 售后退料时关联
    aftersales_order = models.ForeignKey(
        'projects.AfterSalesOrder',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='material_returns',
        verbose_name='售后工单',
    )

    # 入库仓库
    warehouse = models.ForeignKey(
        'masterdata.Warehouse', on_delete=models.PROTECT, related_name='material_returns', verbose_name='入库仓库'
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', verbose_name='状态')

    # 申请人和日期
    requestor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='material_returns', verbose_name='申请人'
    )
    request_date = models.DateField(default=timezone.localdate, verbose_name='申请日期')

    # 仓库处理
    warehouse_operator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='handled_returns',
        verbose_name='仓库操作员',
    )
    receive_date = models.DateTimeField(null=True, blank=True, verbose_name='入库时间')

    notes = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'material_return'
        verbose_name = '退料单'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.return_no} - {self.get_return_type_display()}'

    def save(self, *args, **kwargs):
        if not self.return_no:
            from apps.core.utils import generate_code

            self.return_no = generate_code('MRT', rule_type='MATERIAL_RETURN')
        super().save(*args, **kwargs)

    @property
    def total_qty(self):
        """退料总数量"""
        return sum(line.qty for line in self.lines.all())

    @property
    def received_qty(self):
        """已入库总数量"""
        return sum(line.received_qty for line in self.lines.all())


class MaterialReturnLine(BaseModel):
    """
    退料单明细
    """

    CONDITION_CHOICES = [
        ('GOOD', '良品'),
        ('DAMAGED', '损坏'),
        ('SCRAP', '报废'),
    ]

    material_return = models.ForeignKey(
        MaterialReturn, on_delete=models.CASCADE, related_name='lines', verbose_name='退料单'
    )
    item = models.ForeignKey(
        'masterdata.Item', on_delete=models.PROTECT, related_name='return_lines', verbose_name='物料'
    )
    qty = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='退料数量')
    received_qty = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='已入库数量')
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, default='GOOD', verbose_name='物料状态')
    unit_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='单位成本')
    notes = models.CharField(max_length=200, blank=True, verbose_name='备注')

    class Meta:
        db_table = 'material_return_line'
        verbose_name = '退料单明细'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'{self.material_return.return_no} - {self.item.sku}'

    @property
    def pending_qty(self):
        """待入库数量"""
        return self.qty - self.received_qty

    @property
    def line_amount(self):
        """行金额"""
        return self.received_qty * self.unit_cost
