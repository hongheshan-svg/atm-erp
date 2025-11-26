"""
RFQ (Request for Quotation) models
"""
from django.db import models
from apps.core.models import BaseModel
from apps.masterdata.models import Supplier, Item
from apps.projects.models import Project


class RFQ(BaseModel):
    """Request for Quotation - 询价单"""
    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('SENT', '已发送'),
        ('QUOTED', '已报价'),
        ('ACCEPTED', '已接受'),
        ('REJECTED', '已拒绝'),
        ('CANCELLED', '已取消'),
    ]
    
    rfq_no = models.CharField(max_length=50, unique=True, verbose_name='询价单号')
    project = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='rfqs',
        verbose_name='项目'
    )
    request_date = models.DateField(auto_now_add=True, verbose_name='询价日期')
    response_deadline = models.DateField(verbose_name='报价截止日期')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', verbose_name='状态')
    notes = models.TextField(null=True, blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'rfq'
        verbose_name = '询价单'
        verbose_name_plural = verbose_name
        ordering = ['-request_date']
    
    def __str__(self):
        return self.rfq_no
    
    def save(self, *args, **kwargs):
        if not self.rfq_no:
            from django.utils import timezone
            date_str = timezone.now().strftime('%Y%m%d')
            last_rfq = RFQ.objects.filter(rfq_no__startswith=f'RFQ{date_str}').order_by('-rfq_no').first()
            if last_rfq:
                last_seq = int(last_rfq.rfq_no[-4:])
                new_seq = last_seq + 1
            else:
                new_seq = 1
            self.rfq_no = f'RFQ{date_str}{new_seq:04d}'
        super().save(*args, **kwargs)


class RFQLine(BaseModel):
    """RFQ line items"""
    rfq = models.ForeignKey(
        RFQ,
        on_delete=models.CASCADE,
        related_name='lines',
        verbose_name='询价单'
    )
    item = models.ForeignKey(
        Item,
        on_delete=models.PROTECT,
        related_name='rfq_lines',
        verbose_name='物料'
    )
    qty = models.DecimalField(max_digits=12, decimal_places=3, verbose_name='数量')
    required_date = models.DateField(verbose_name='需求日期')
    specifications = models.TextField(null=True, blank=True, verbose_name='规格说明')
    
    class Meta:
        db_table = 'rfq_line'
        verbose_name = '询价单明细'
        verbose_name_plural = verbose_name
    
    def __str__(self):
        return f"{self.rfq.rfq_no} - {self.item.name}"


class RFQSupplier(BaseModel):
    """RFQ sent to suppliers"""
    rfq = models.ForeignKey(
        RFQ,
        on_delete=models.CASCADE,
        related_name='supplier_rfqs',
        verbose_name='询价单'
    )
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name='rfqs',
        verbose_name='供应商'
    )
    sent_date = models.DateTimeField(null=True, blank=True, verbose_name='发送日期')
    is_responded = models.BooleanField(default=False, verbose_name='是否已响应')
    
    class Meta:
        db_table = 'rfq_supplier'
        verbose_name = 'RFQ供应商'
        verbose_name_plural = verbose_name
        unique_together = ['rfq', 'supplier']
    
    def __str__(self):
        return f"{self.rfq.rfq_no} - {self.supplier.name}"


class SupplierQuotation(BaseModel):
    """Supplier quotation response to RFQ"""
    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('SUBMITTED', '已提交'),
        ('ACCEPTED', '已接受'),
        ('REJECTED', '已拒绝'),
    ]
    
    quotation_no = models.CharField(max_length=50, unique=True, verbose_name='报价单号')
    rfq_supplier = models.ForeignKey(
        RFQSupplier,
        on_delete=models.CASCADE,
        related_name='quotations',
        verbose_name='RFQ供应商'
    )
    quotation_date = models.DateField(auto_now_add=True, verbose_name='报价日期')
    valid_until = models.DateField(verbose_name='有效期至')
    payment_terms = models.CharField(max_length=200, verbose_name='付款条款')
    delivery_terms = models.CharField(max_length=200, verbose_name='交货条款')
    total_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name='总金额'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', verbose_name='状态')
    notes = models.TextField(null=True, blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'supplier_quotation'
        verbose_name = '供应商报价'
        verbose_name_plural = verbose_name
        ordering = ['-quotation_date']
    
    def __str__(self):
        return self.quotation_no
    
    def save(self, *args, **kwargs):
        if not self.quotation_no:
            from django.utils import timezone
            date_str = timezone.now().strftime('%Y%m%d')
            last_quot = SupplierQuotation.objects.filter(
                quotation_no__startswith=f'QUOT{date_str}'
            ).order_by('-quotation_no').first()
            if last_quot:
                last_seq = int(last_quot.quotation_no[-4:])
                new_seq = last_seq + 1
            else:
                new_seq = 1
            self.quotation_no = f'QUOT{date_str}{new_seq:04d}'
        super().save(*args, **kwargs)


class SupplierQuotationLine(BaseModel):
    """Supplier quotation line items"""
    quotation = models.ForeignKey(
        SupplierQuotation,
        on_delete=models.CASCADE,
        related_name='lines',
        verbose_name='供应商报价'
    )
    rfq_line = models.ForeignKey(
        RFQLine,
        on_delete=models.PROTECT,
        related_name='quotation_lines',
        verbose_name='RFQ明细'
    )
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='单价')
    qty = models.DecimalField(max_digits=12, decimal_places=3, verbose_name='数量')
    lead_time_days = models.IntegerField(verbose_name='交货周期（天）')
    line_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='行金额'
    )
    notes = models.TextField(null=True, blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'supplier_quotation_line'
        verbose_name = '供应商报价明细'
        verbose_name_plural = verbose_name
    
    def __str__(self):
        return f"{self.quotation.quotation_no} - {self.rfq_line.item.name}"
    
    def save(self, *args, **kwargs):
        self.line_amount = self.unit_price * self.qty
        super().save(*args, **kwargs)

