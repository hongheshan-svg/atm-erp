"""
Sales management models - Quotation, SO, Delivery Order.
"""
from django.db import models
from apps.core.models import BaseModel
from apps.core.utils import generate_code


class SalesQuotation(BaseModel):
    """
    Sales Quotation - 销售报价单
    """
    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('SENT', '已发送'),
        ('ACCEPTED', '已接受'),
        ('REJECTED', '已拒绝'),
        ('EXPIRED', '已过期'),
    ]
    
    quote_no = models.CharField(max_length=50, unique=True, verbose_name='报价单号')
    customer = models.ForeignKey(
        'masterdata.Customer',
        on_delete=models.PROTECT,
        related_name='quotations',
        verbose_name='客户'
    )
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='quotations',
        verbose_name='关联项目'
    )
    quote_date = models.DateField(auto_now_add=True, verbose_name='报价日期')
    valid_until = models.DateField(verbose_name='有效期至')
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='DRAFT',
        verbose_name='状态'
    )
    version = models.IntegerField(default=1, verbose_name='版本号')
    total_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name='总金额'
    )
    notes = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'sales_quotation'
        verbose_name = '销售报价'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.quote_no}"
    
    def save(self, *args, **kwargs):
        if not self.quote_no:
            self.quote_no = generate_code('QT')
        super().save(*args, **kwargs)


class SalesQuotationLine(BaseModel):
    """
    Sales Quotation Line - 销售报价明细
    """
    quotation = models.ForeignKey(
        SalesQuotation,
        on_delete=models.CASCADE,
        related_name='lines',
        verbose_name='销售报价'
    )
    item = models.ForeignKey(
        'masterdata.Item',
        on_delete=models.PROTECT,
        related_name='quotation_lines',
        verbose_name='物料'
    )
    qty = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='数量')
    unit_price = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='单价')
    line_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name='行金额'
    )
    notes = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'sales_quotation_line'
        verbose_name = '销售报价明细'
        verbose_name_plural = verbose_name
        ordering = ['id']
    
    def __str__(self):
        return f"{self.quotation.quote_no} - {self.item.sku}"
    
    def save(self, *args, **kwargs):
        self.line_amount = self.qty * self.unit_price
        super().save(*args, **kwargs)


class SalesOrder(BaseModel):
    """
    Sales Order (SO) - 销售订单
    NOTE: project is OPTIONAL - some orders are placed before project creation (e.g. custom orders)
    """
    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('CONFIRMED', '已确认'),
        ('PARTIAL', '部分发货'),
        ('COMPLETED', '完成'),
        ('CANCELLED', '已取消'),
    ]
    
    order_no = models.CharField(max_length=50, unique=True, verbose_name='订单号')
    customer = models.ForeignKey(
        'masterdata.Customer',
        on_delete=models.PROTECT,
        related_name='sales_orders',
        verbose_name='客户'
    )
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.PROTECT,
        related_name='sales_orders',
        verbose_name='关联项目',
        null=True,
        blank=True
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
        db_table = 'sales_order'
        verbose_name = '销售订单'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.order_no}"
    
    def save(self, *args, **kwargs):
        if not self.order_no:
            self.order_no = generate_code('SO')
        super().save(*args, **kwargs)


class SalesOrderLine(BaseModel):
    """
    Sales Order Line - 销售订单明细
    """
    so = models.ForeignKey(
        SalesOrder,
        on_delete=models.CASCADE,
        related_name='lines',
        verbose_name='销售订单'
    )
    item = models.ForeignKey(
        'masterdata.Item',
        on_delete=models.PROTECT,
        related_name='so_lines',
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
    delivered_qty = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name='已发货数量'
    )
    notes = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'sales_order_line'
        verbose_name = '销售订单明细'
        verbose_name_plural = verbose_name
        ordering = ['id']
    
    def __str__(self):
        return f"{self.so.order_no} - {self.item.sku}"
    
    def save(self, *args, **kwargs):
        self.line_amount = self.qty * self.unit_price
        super().save(*args, **kwargs)


class DeliveryOrder(BaseModel):
    """
    Delivery Order (DO) - 发货单
    """
    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('CONFIRMED', '已确认'),
        ('COMPLETED', '完成'),
    ]
    
    delivery_no = models.CharField(max_length=50, unique=True, verbose_name='发货单号')
    so = models.ForeignKey(
        SalesOrder,
        on_delete=models.PROTECT,
        related_name='deliveries',
        verbose_name='销售订单'
    )
    warehouse = models.ForeignKey(
        'masterdata.Warehouse',
        on_delete=models.PROTECT,
        related_name='deliveries',
        verbose_name='发货仓库'
    )
    delivery_date = models.DateField(verbose_name='发货日期')
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='DRAFT',
        verbose_name='状态'
    )
    notes = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'delivery_order'
        verbose_name = '发货单'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.delivery_no}"
    
    def save(self, *args, **kwargs):
        if not self.delivery_no:
            self.delivery_no = generate_code('DO')
        super().save(*args, **kwargs)


class DeliveryOrderLine(BaseModel):
    """
    Delivery Order Line - 发货明细
    """
    delivery = models.ForeignKey(
        DeliveryOrder,
        on_delete=models.CASCADE,
        related_name='lines',
        verbose_name='发货单'
    )
    so_line = models.ForeignKey(
        SalesOrderLine,
        on_delete=models.PROTECT,
        related_name='delivery_lines',
        verbose_name='销售订单明细'
    )
    item = models.ForeignKey(
        'masterdata.Item',
        on_delete=models.PROTECT,
        related_name='delivery_lines',
        verbose_name='物料'
    )
    qty = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='发货数量')
    notes = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'delivery_order_line'
        verbose_name = '发货明细'
        verbose_name_plural = verbose_name
        ordering = ['id']
    
    def __str__(self):
        return f"{self.delivery.delivery_no} - {self.item.sku}"

