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
    
    request_no = models.CharField(max_length=50, unique=True, verbose_name='申请单号')
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='purchase_requests',
        verbose_name='关联项目'
    )
    requestor = models.ForeignKey(
        'accounts.User',
        on_delete=models.PROTECT,
        related_name='created_prs',
        verbose_name='申请人'
    )
    request_date = models.DateField(auto_now_add=True, verbose_name='申请日期')
    required_date = models.DateField(verbose_name='需求日期')
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='DRAFT',
        verbose_name='状态'
    )
    total_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name='总金额'
    )
    notes = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'purchase_request'
        verbose_name = '采购申请'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.request_no}"
    
    def save(self, *args, **kwargs):
        if not self.request_no:
            self.request_no = generate_code('PR')
        super().save(*args, **kwargs)


class PurchaseRequestLine(BaseModel):
    """
    Purchase Request Line - 采购申请明细
    """
    pr = models.ForeignKey(
        PurchaseRequest,
        on_delete=models.CASCADE,
        related_name='lines',
        verbose_name='采购申请'
    )
    item = models.ForeignKey(
        'masterdata.Item',
        on_delete=models.PROTECT,
        related_name='pr_lines',
        verbose_name='物料'
    )
    qty = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='数量')
    estimated_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name='预估单价'
    )
    line_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name='行金额'
    )
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pr_lines',
        verbose_name='关联项目'
    )
    notes = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'purchase_request_line'
        verbose_name = '采购申请明细'
        verbose_name_plural = verbose_name
        ordering = ['id']
    
    def __str__(self):
        return f"{self.pr.request_no} - {self.item.sku}"
    
    def save(self, *args, **kwargs):
        self.line_amount = self.qty * self.estimated_price
        super().save(*args, **kwargs)


class PurchaseOrder(BaseModel):
    """
    Purchase Order (PO) - 采购订单
    """
    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('CONFIRMED', '已确认'),
        ('PARTIAL', '部分收货'),
        ('COMPLETED', '完成'),
        ('CANCELLED', '已取消'),
    ]
    
    order_no = models.CharField(max_length=50, unique=True, verbose_name='订单号')
    supplier = models.ForeignKey(
        'masterdata.Supplier',
        on_delete=models.PROTECT,
        related_name='purchase_orders',
        verbose_name='供应商'
    )
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='purchase_orders',
        verbose_name='关联项目'
    )
    order_date = models.DateField(auto_now_add=True, verbose_name='订单日期')
    delivery_date = models.DateField(verbose_name='交货日期')
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='DRAFT',
        verbose_name='状态'
    )
    total_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name='总金额'
    )
    payment_terms = models.CharField(max_length=200, blank=True, verbose_name='付款条款')
    notes = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'purchase_order'
        verbose_name = '采购订单'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.order_no}"
    
    def save(self, *args, **kwargs):
        if not self.order_no:
            self.order_no = generate_code('PO')
        super().save(*args, **kwargs)


class PurchaseOrderLine(BaseModel):
    """
    Purchase Order Line - 采购订单明细
    """
    po = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.CASCADE,
        related_name='lines',
        verbose_name='采购订单'
    )
    item = models.ForeignKey(
        'masterdata.Item',
        on_delete=models.PROTECT,
        related_name='po_lines',
        verbose_name='物料'
    )
    qty = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='订购数量')
    unit_price = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='单价')
    line_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name='行金额'
    )
    received_qty = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name='已收货数量'
    )
    notes = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'purchase_order_line'
        verbose_name = '采购订单明细'
        verbose_name_plural = verbose_name
        ordering = ['id']
    
    def __str__(self):
        return f"{self.po.order_no} - {self.item.sku}"
    
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
    po = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.PROTECT,
        related_name='receipts',
        verbose_name='采购订单'
    )
    warehouse = models.ForeignKey(
        'masterdata.Warehouse',
        on_delete=models.PROTECT,
        related_name='goods_receipts',
        verbose_name='收货仓库'
    )
    receipt_date = models.DateField(verbose_name='收货日期')
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='DRAFT',
        verbose_name='状态'
    )
    notes = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'goods_receipt'
        verbose_name = '收货单'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.receipt_no}"
    
    def save(self, *args, **kwargs):
        if not self.receipt_no:
            self.receipt_no = generate_code('GR')
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
    
    receipt = models.ForeignKey(
        GoodsReceipt,
        on_delete=models.CASCADE,
        related_name='lines',
        verbose_name='收货单'
    )
    po_line = models.ForeignKey(
        PurchaseOrderLine,
        on_delete=models.PROTECT,
        related_name='receipt_lines',
        verbose_name='采购订单明细'
    )
    item = models.ForeignKey(
        'masterdata.Item',
        on_delete=models.PROTECT,
        related_name='receipt_lines',
        verbose_name='物料'
    )
    qty = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='收货数量')
    quality_status = models.CharField(
        max_length=20,
        choices=QUALITY_STATUS_CHOICES,
        default='PENDING',
        verbose_name='质检状态'
    )
    notes = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'goods_receipt_line'
        verbose_name = '收货明细'
        verbose_name_plural = verbose_name
        ordering = ['id']
    
    def __str__(self):
        return f"{self.receipt.receipt_no} - {self.item.sku}"

