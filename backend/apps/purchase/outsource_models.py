"""
外协加工管理模型
Outsource Processing Management Models
"""
from django.db import models
from django.db.models import Sum
from apps.core.models import BaseModel
from apps.core.utils import generate_code


class OutsourceOrder(BaseModel):
    """
    外协加工订单 - 发外加工单
    """
    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('CONFIRMED', '已确认'),
        ('PROCESSING', '加工中'),
        ('PARTIAL', '部分完成'),
        ('COMPLETED', '已完成'),
        ('CANCELLED', '已取消'),
    ]
    
    order_no = models.CharField(max_length=50, unique=True, verbose_name='外协单号')
    supplier = models.ForeignKey(
        'masterdata.Supplier',
        on_delete=models.PROTECT,
        related_name='outsource_orders',
        verbose_name='外协供应商'
    )
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='outsource_orders',
        verbose_name='关联项目'
    )
    
    order_date = models.DateField(auto_now_add=True, verbose_name='下单日期')
    required_date = models.DateField(verbose_name='要求完成日期')
    
    # 金额
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='加工费总额')
    tax_rate = models.IntegerField(default=13, verbose_name='税率(%)')
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='税额')
    total_with_tax = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='含税总额')
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', verbose_name='状态')
    
    # 联系信息
    contact_person = models.CharField(max_length=50, blank=True, verbose_name='联系人')
    contact_phone = models.CharField(max_length=50, blank=True, verbose_name='联系电话')
    delivery_address = models.CharField(max_length=200, blank=True, verbose_name='送货地址')
    
    notes = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'outsource_order'
        verbose_name = '外协加工单'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.order_no}"
    
    def save(self, *args, **kwargs):
        if not self.order_no:
            self.order_no = generate_code('OS')
        super().save(*args, **kwargs)
    
    def update_totals(self):
        """更新合计金额"""
        total = self.lines.filter(is_deleted=False).aggregate(
            total=Sum('process_amount')
        )['total'] or 0
        self.total_amount = total
        self.tax_amount = total * self.tax_rate / 100
        self.total_with_tax = total + self.tax_amount
        self.save(update_fields=['total_amount', 'tax_amount', 'total_with_tax'])


class OutsourceOrderLine(BaseModel):
    """
    外协加工单明细 - 每个加工件
    """
    PROCESS_TYPE_CHOICES = [
        ('TURNING', '车削'),
        ('MILLING', '铣削'),
        ('GRINDING', '磨削'),
        ('DRILLING', '钻孔'),
        ('WIRE_CUT', '线切割'),
        ('EDM', '电火花'),
        ('LASER_CUT', '激光切割'),
        ('BENDING', '折弯'),
        ('WELDING', '焊接'),
        ('SURFACE', '表面处理'),
        ('HEAT_TREAT', '热处理'),
        ('ASSEMBLY', '组装'),
        ('OTHER', '其他'),
    ]
    
    outsource_order = models.ForeignKey(
        OutsourceOrder,
        on_delete=models.CASCADE,
        related_name='lines',
        verbose_name='外协单'
    )
    item = models.ForeignKey(
        'masterdata.Item',
        on_delete=models.PROTECT,
        related_name='outsource_lines',
        verbose_name='加工物料'
    )
    
    # 加工信息
    process_type = models.CharField(
        max_length=20,
        choices=PROCESS_TYPE_CHOICES,
        default='OTHER',
        verbose_name='加工类型'
    )
    process_content = models.CharField(max_length=500, verbose_name='加工内容')
    drawing_no = models.CharField(max_length=100, blank=True, verbose_name='图纸号')
    
    # 数量
    qty = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='加工数量')
    unit_price = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='单价')
    process_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='加工费')
    
    # 材料信息
    material_provided = models.BooleanField(default=True, verbose_name='我方提供材料')
    material_weight = models.DecimalField(max_digits=15, decimal_places=3, default=0, verbose_name='材料重量(kg)')
    
    # 进度
    sent_qty = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='已发料数量')
    received_qty = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='已收货数量')
    
    required_date = models.DateField(null=True, blank=True, verbose_name='要求完成日期')
    notes = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'outsource_order_line'
        verbose_name = '外协加工单明细'
        verbose_name_plural = verbose_name
        ordering = ['id']
    
    def __str__(self):
        return f"{self.outsource_order.order_no} - {self.item.name}"
    
    def save(self, *args, **kwargs):
        self.process_amount = self.qty * self.unit_price
        super().save(*args, **kwargs)


class OutsourceMaterialIssue(BaseModel):
    """
    外协发料单 - 发料给外协供应商
    """
    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('CONFIRMED', '已确认'),
    ]
    
    issue_no = models.CharField(max_length=50, unique=True, verbose_name='发料单号')
    outsource_order = models.ForeignKey(
        OutsourceOrder,
        on_delete=models.PROTECT,
        related_name='material_issues',
        verbose_name='外协单'
    )
    warehouse = models.ForeignKey(
        'masterdata.Warehouse',
        on_delete=models.PROTECT,
        related_name='outsource_issues',
        verbose_name='发料仓库'
    )
    
    issue_date = models.DateField(verbose_name='发料日期')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', verbose_name='状态')
    
    # 物流信息
    logistics_company = models.CharField(max_length=100, blank=True, verbose_name='物流公司')
    tracking_number = models.CharField(max_length=100, blank=True, verbose_name='运单号')
    
    notes = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'outsource_material_issue'
        verbose_name = '外协发料单'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.issue_no}"
    
    def save(self, *args, **kwargs):
        if not self.issue_no:
            self.issue_no = generate_code('OMI')
        super().save(*args, **kwargs)


class OutsourceMaterialIssueLine(BaseModel):
    """
    外协发料单明细
    """
    issue = models.ForeignKey(
        OutsourceMaterialIssue,
        on_delete=models.CASCADE,
        related_name='lines',
        verbose_name='发料单'
    )
    outsource_line = models.ForeignKey(
        OutsourceOrderLine,
        on_delete=models.PROTECT,
        related_name='issue_lines',
        verbose_name='外协单明细'
    )
    item = models.ForeignKey(
        'masterdata.Item',
        on_delete=models.PROTECT,
        related_name='outsource_issue_lines',
        verbose_name='物料'
    )
    
    qty = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='发料数量')
    weight = models.DecimalField(max_digits=15, decimal_places=3, default=0, verbose_name='重量(kg)')
    
    notes = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'outsource_material_issue_line'
        verbose_name = '外协发料单明细'
        verbose_name_plural = verbose_name
        ordering = ['id']


class OutsourceReceipt(BaseModel):
    """
    外协收货单 - 加工件入库
    """
    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('INSPECTING', '质检中'),
        ('CONFIRMED', '已确认'),
    ]
    
    QUALITY_CHOICES = [
        ('PENDING', '待检'),
        ('PASSED', '合格'),
        ('FAILED', '不合格'),
        ('PARTIAL', '部分合格'),
    ]
    
    receipt_no = models.CharField(max_length=50, unique=True, verbose_name='收货单号')
    outsource_order = models.ForeignKey(
        OutsourceOrder,
        on_delete=models.PROTECT,
        related_name='receipts',
        verbose_name='外协单'
    )
    warehouse = models.ForeignKey(
        'masterdata.Warehouse',
        on_delete=models.PROTECT,
        related_name='outsource_receipts',
        verbose_name='入库仓库'
    )
    
    receipt_date = models.DateField(verbose_name='收货日期')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', verbose_name='状态')
    quality_status = models.CharField(max_length=20, choices=QUALITY_CHOICES, default='PENDING', verbose_name='质检状态')
    
    inspector = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inspected_outsource_receipts',
        verbose_name='质检员'
    )
    inspect_date = models.DateField(null=True, blank=True, verbose_name='质检日期')
    inspect_notes = models.TextField(blank=True, verbose_name='质检备注')
    
    notes = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'outsource_receipt'
        verbose_name = '外协收货单'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.receipt_no}"
    
    def save(self, *args, **kwargs):
        if not self.receipt_no:
            self.receipt_no = generate_code('OR')
        super().save(*args, **kwargs)


class OutsourceReceiptLine(BaseModel):
    """
    外协收货单明细
    """
    QUALITY_CHOICES = [
        ('PENDING', '待检'),
        ('PASSED', '合格'),
        ('FAILED', '不合格'),
    ]
    
    receipt = models.ForeignKey(
        OutsourceReceipt,
        on_delete=models.CASCADE,
        related_name='lines',
        verbose_name='收货单'
    )
    outsource_line = models.ForeignKey(
        OutsourceOrderLine,
        on_delete=models.PROTECT,
        related_name='receipt_lines',
        verbose_name='外协单明细'
    )
    item = models.ForeignKey(
        'masterdata.Item',
        on_delete=models.PROTECT,
        related_name='outsource_receipt_lines',
        verbose_name='物料'
    )
    
    qty = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='收货数量')
    qualified_qty = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='合格数量')
    rejected_qty = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='不合格数量')
    
    quality_status = models.CharField(max_length=20, choices=QUALITY_CHOICES, default='PENDING', verbose_name='质检状态')
    quality_notes = models.TextField(blank=True, verbose_name='质检备注')
    
    notes = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'outsource_receipt_line'
        verbose_name = '外协收货单明细'
        verbose_name_plural = verbose_name
        ordering = ['id']

