"""
Purchase management models - PR, PO, Goods Receipt.
"""

from django.db import models

from apps.core.models import BaseModel
from apps.core.utils import generate_code


class PurchaseRequest(BaseModel):
    """
    Purchase Request (PR) - 采购申请单
    """

    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('SUBMITTED', '已提交'),
        ('APPROVED', '已批准'),
        ('REJECTED', '已拒绝'),
        ('CONVERTED', '已转采购订单'),
    ]

    TAX_RATE_CHOICES = [
        (0, '0% (免税)'),
        (1, '1%'),
        (3, '3%'),
        (6, '6%'),
        (9, '9%'),
        (13, '13%'),
    ]

    request_no = models.CharField(max_length=50, unique=True, verbose_name='申请单号')
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='purchase_requests',
        verbose_name='关联项目',
    )
    supplier = models.ForeignKey(
        'masterdata.Supplier',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='purchase_requests',
        verbose_name='供应商',
    )
    requestor = models.ForeignKey(
        'accounts.User', on_delete=models.PROTECT, related_name='created_prs', verbose_name='申请人'
    )
    request_date = models.DateField(auto_now_add=True, verbose_name='申请日期')
    required_date = models.DateField(verbose_name='需求日期')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', verbose_name='状态')

    # 税率相关
    tax_rate = models.IntegerField(choices=TAX_RATE_CHOICES, default=13, verbose_name='增值税税率(%)')
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='不含税金额')
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='税额')
    total_with_tax = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='含税总额')
    notes = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'purchase_request'
        verbose_name = '采购申请'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.request_no}'

    def save(self, *args, **kwargs):
        if not self.request_no:
            self.request_no = generate_code('PR', rule_type='PURCHASE_REQUEST')
        super().save(*args, **kwargs)


class PurchaseRequestLine(BaseModel):
    """
    Purchase Request Line - 采购申请明细
    支持从BOM生成采购申请
    """

    pr = models.ForeignKey(PurchaseRequest, on_delete=models.CASCADE, related_name='lines', verbose_name='采购申请')
    item = models.ForeignKey('masterdata.Item', on_delete=models.PROTECT, related_name='pr_lines', verbose_name='物料')
    qty = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='数量')
    estimated_price = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='预估单价')
    line_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='行金额')
    required_date = models.DateField(null=True, blank=True, verbose_name='交期')
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pr_lines',
        verbose_name='关联项目',
    )

    # ===== BOM关联字段(非标自动化行业) =====
    bom_item = models.ForeignKey(
        'projects.ProjectBOM',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pr_lines',
        verbose_name='BOM项',
        help_text='从BOM生成的采购申请关联',
    )
    # 是否关键件(从BOM继承)
    is_critical = models.BooleanField(default=False, verbose_name='关键件')
    # 是否长周期件(从BOM继承)
    is_long_lead = models.BooleanField(default=False, verbose_name='长周期件')
    # 功能模块(从BOM继承)
    function_module = models.CharField(max_length=100, blank=True, verbose_name='功能模块')

    notes = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'purchase_request_line'
        verbose_name = '采购申请明细'
        verbose_name_plural = verbose_name
        ordering = ['id']
        indexes = [
            models.Index(fields=['is_critical', 'is_long_lead']),
        ]

    def __str__(self):
        return f'{self.pr.request_no} - {self.item.sku}'

    def save(self, *args, **kwargs):
        self.line_amount = self.qty * self.estimated_price
        super().save(*args, **kwargs)


class PurchaseOrder(BaseModel):
    """
    Purchase Order (PO) - 采购订单
    """

    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('PENDING', '待审批'),
        ('APPROVED', '已审批'),
        ('REJECTED', '已拒绝'),
        ('CONFIRMED', '已确认'),
        ('PARTIAL', '部分收货'),
        ('COMPLETED', '完成'),
        ('CANCELLED', '已取消'),
    ]

    TAX_RATE_CHOICES = [
        (0, '0% (免税)'),
        (1, '1%'),
        (3, '3%'),
        (6, '6%'),
        (9, '9%'),
        (13, '13%'),
    ]

    # 付款条款选项 - 账期
    PAYMENT_TERMS_CHOICES = [
        ('PREPAY', '预付款'),
        ('COD', '货到付款'),
        ('NET15', '月结15天'),
        ('NET30', '月结30天'),
        ('NET45', '月结45天'),
        ('NET60', '月结60天'),
        ('NET90', '月结90天'),
        ('NET120', '月结120天'),
        ('MILESTONE', '分期付款'),
        ('OTHER', '其他'),
    ]

    # 付款方式选项
    PAYMENT_METHOD_CHOICES = [
        ('WIRE', '电汇'),
        ('ACCEPTANCE', '承兑汇票'),
        ('CHECK', '支票'),
        ('CASH', '现金'),
        ('LC', '信用证'),
        ('OTHER', '其他'),
    ]

    order_no = models.CharField(max_length=50, unique=True, verbose_name='订单号')
    supplier = models.ForeignKey(
        'masterdata.Supplier', on_delete=models.PROTECT, related_name='purchase_orders', verbose_name='供应商'
    )
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='purchase_orders',
        verbose_name='关联项目',
    )
    order_date = models.DateField(auto_now_add=True, verbose_name='订单日期')
    delivery_date = models.DateField(verbose_name='交货日期')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', verbose_name='状态')

    # 税率相关
    tax_rate = models.IntegerField(choices=TAX_RATE_CHOICES, default=13, verbose_name='增值税税率(%)')
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='不含税金额')
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='税额')
    total_with_tax = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='含税总额')

    # 付款条款与方式
    payment_terms = models.CharField(
        max_length=20, choices=PAYMENT_TERMS_CHOICES, default='NET30', verbose_name='付款条款'
    )
    payment_method = models.CharField(
        max_length=20, choices=PAYMENT_METHOD_CHOICES, default='WIRE', verbose_name='付款方式'
    )
    payment_terms_detail = models.CharField(max_length=200, blank=True, verbose_name='付款条款说明')
    notes = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'purchase_order'
        verbose_name = '采购订单'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.order_no}'

    def save(self, *args, **kwargs):
        if not self.order_no:
            self.order_no = generate_code('PO', rule_type='PURCHASE_ORDER')
        super().save(*args, **kwargs)


class PurchaseOrderLine(BaseModel):
    """
    Purchase Order Line - 采购订单明细
    支持从BOM生成采购订单
    """

    po = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='lines', verbose_name='采购订单')
    item = models.ForeignKey('masterdata.Item', on_delete=models.PROTECT, related_name='po_lines', verbose_name='物料')
    qty = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='订购数量')
    unit_price = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='单价')
    line_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='行金额')
    received_qty = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='已收货数量')

    # ===== BOM关联字段(非标自动化行业) =====
    bom_item = models.ForeignKey(
        'projects.ProjectBOM',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='po_lines',
        verbose_name='BOM项',
        help_text='从BOM生成的采购订单关联',
    )
    # 是否关键件(从BOM继承)
    is_critical = models.BooleanField(default=False, verbose_name='关键件')
    # 是否长周期件(从BOM继承)
    is_long_lead = models.BooleanField(default=False, verbose_name='长周期件')
    # 功能模块(从BOM继承)
    function_module = models.CharField(max_length=100, blank=True, verbose_name='功能模块')
    # 图纸号(从BOM继承)
    drawing_no = models.CharField(max_length=100, blank=True, verbose_name='图纸号')
    # 技术要求(从BOM继承)
    technical_requirement = models.TextField(blank=True, verbose_name='技术要求')

    notes = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'purchase_order_line'
        verbose_name = '采购订单明细'
        verbose_name_plural = verbose_name
        ordering = ['id']
        indexes = [
            models.Index(fields=['bom_item']),
            models.Index(fields=['is_critical', 'is_long_lead']),
        ]

    def __str__(self):
        return f'{self.po.order_no} - {self.item.sku}'

    def save(self, *args, **kwargs):
        self.line_amount = self.qty * self.unit_price
        super().save(*args, **kwargs)


class GoodsReceipt(BaseModel):
    """
    Goods Receipt - 收货单
    """

    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('CONFIRMED', '已确认'),
        ('COMPLETED', '完成'),
    ]

    receipt_no = models.CharField(max_length=50, unique=True, verbose_name='收货单号')
    po = models.ForeignKey(PurchaseOrder, on_delete=models.PROTECT, related_name='receipts', verbose_name='采购订单')
    warehouse = models.ForeignKey(
        'masterdata.Warehouse', on_delete=models.PROTECT, related_name='goods_receipts', verbose_name='收货仓库'
    )
    receipt_date = models.DateField(verbose_name='收货日期')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', verbose_name='状态')
    notes = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'goods_receipt'
        verbose_name = '收货单'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.receipt_no}'

    def save(self, *args, **kwargs):
        if not self.receipt_no:
            self.receipt_no = generate_code('GR', rule_type='GOODS_RECEIPT')
        super().save(*args, **kwargs)


class GoodsReceiptLine(BaseModel):
    """
    Goods Receipt Line - 收货明细
    """

    QUALITY_STATUS_CHOICES = [
        ('PENDING', '待检'),
        ('PASSED', '合格'),
        ('FAILED', '不合格'),
    ]

    receipt = models.ForeignKey(GoodsReceipt, on_delete=models.CASCADE, related_name='lines', verbose_name='收货单')
    po_line = models.ForeignKey(
        PurchaseOrderLine, on_delete=models.PROTECT, related_name='receipt_lines', verbose_name='采购订单明细'
    )
    item = models.ForeignKey(
        'masterdata.Item', on_delete=models.PROTECT, related_name='receipt_lines', verbose_name='物料'
    )
    qty = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='收货数量')
    quality_status = models.CharField(
        max_length=20, choices=QUALITY_STATUS_CHOICES, default='PENDING', verbose_name='质检状态'
    )
    notes = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'goods_receipt_line'
        verbose_name = '收货明细'
        verbose_name_plural = verbose_name
        ordering = ['id']

    def __str__(self):
        return f'{self.receipt.receipt_no} - {self.item.sku}'


class PurchaseContract(BaseModel):
    """
    Purchase Contract - 采购合同
    """

    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('PENDING', '待审批'),
        ('APPROVED', '已审批'),
        ('SIGNED', '已签署'),
        ('COMPLETED', '已完成'),
        ('CANCELLED', '已取消'),
    ]

    contract_no = models.CharField(max_length=50, unique=True, verbose_name='合同编号')
    po = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='contracts', verbose_name='采购订单')
    supplier = models.ForeignKey(
        'masterdata.Supplier', on_delete=models.PROTECT, related_name='purchase_contracts', verbose_name='供应商'
    )
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='purchase_contracts',
        verbose_name='关联项目',
    )

    # 合同信息
    title = models.CharField(max_length=200, verbose_name='合同标题')
    contract_date = models.DateField(verbose_name='合同日期')
    effective_date = models.DateField(null=True, blank=True, verbose_name='生效日期')
    expiry_date = models.DateField(null=True, blank=True, verbose_name='到期日期')

    # 金额
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='合同金额')
    tax_rate = models.IntegerField(default=13, verbose_name='税率(%)')
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='税额')
    total_with_tax = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='含税总额')

    # 付款条款
    payment_terms = models.TextField(blank=True, verbose_name='付款条款')
    delivery_terms = models.TextField(blank=True, verbose_name='交货条款')
    quality_terms = models.TextField(blank=True, verbose_name='质量条款')
    warranty_terms = models.TextField(blank=True, verbose_name='质保条款')

    # 签署信息
    buyer_signer = models.CharField(max_length=100, blank=True, verbose_name='甲方签署人')
    seller_signer = models.CharField(max_length=100, blank=True, verbose_name='乙方签署人')
    signed_date = models.DateField(null=True, blank=True, verbose_name='签署日期')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', verbose_name='状态')
    notes = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'purchase_contract'
        verbose_name = '采购合同'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.contract_no}'

    def save(self, *args, **kwargs):
        if not self.contract_no:
            self.contract_no = generate_code('PC', rule_type='PURCHASE_CONTRACT')
        super().save(*args, **kwargs)


# Import models from supplier_portal


# Import new improvement module models
from .outsource_tracking import OutsourceInspection  # noqa: E402, F401
from .supply_chain_collaboration import RFQCollaboration  # noqa: E402, F401
