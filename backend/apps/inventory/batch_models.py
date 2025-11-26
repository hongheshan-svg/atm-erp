"""
Batch and Lot tracking models
"""
from django.db import models
from apps.core.models import BaseModel
from apps.masterdata.models import Item, Warehouse


class Batch(BaseModel):
    """
    Batch/Lot tracking for inventory
    """
    batch_no = models.CharField(max_length=50, verbose_name='批次号')
    item = models.ForeignKey(
        Item,
        on_delete=models.PROTECT,
        related_name='batches',
        verbose_name='物料'
    )
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name='batches',
        verbose_name='仓库'
    )
    manufacture_date = models.DateField(null=True, blank=True, verbose_name='生产日期')
    expiry_date = models.DateField(null=True, blank=True, verbose_name='到期日期')
    qty_on_hand = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=0,
        verbose_name='现有数量'
    )
    unit_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name='单位成本'
    )
    supplier_batch_no = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name='供应商批次号'
    )
    quality_status = models.CharField(
        max_length=20,
        choices=[
            ('PENDING', '待检'),
            ('PASSED', '合格'),
            ('FAILED', '不合格'),
            ('QUARANTINE', '隔离'),
        ],
        default='PENDING',
        verbose_name='质量状态'
    )
    notes = models.TextField(null=True, blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'batch'
        verbose_name = '批次'
        verbose_name_plural = verbose_name
        unique_together = ['batch_no', 'item', 'warehouse']
        ordering = ['expiry_date', '-manufacture_date']
        indexes = [
            models.Index(fields=['item', 'warehouse']),
            models.Index(fields=['expiry_date']),
        ]
    
    def __str__(self):
        return f"{self.batch_no} - {self.item.sku}"
    
    @property
    def is_expired(self):
        """Check if batch is expired"""
        if not self.expiry_date:
            return False
        from django.utils import timezone
        return self.expiry_date < timezone.now().date()
    
    @property
    def days_to_expiry(self):
        """Calculate days until expiry"""
        if not self.expiry_date:
            return None
        from django.utils import timezone
        delta = self.expiry_date - timezone.now().date()
        return delta.days


class BatchMove(BaseModel):
    """
    Batch movement history
    """
    batch = models.ForeignKey(
        Batch,
        on_delete=models.PROTECT,
        related_name='moves',
        verbose_name='批次'
    )
    move_type = models.CharField(
        max_length=20,
        choices=[
            ('IN', '入库'),
            ('OUT', '出库'),
            ('ADJUST', '调整'),
            ('TRANSFER', '调拨'),
        ],
        verbose_name='移动类型'
    )
    qty = models.DecimalField(max_digits=12, decimal_places=3, verbose_name='数量')
    reference_type = models.CharField(max_length=50, verbose_name='参考类型')
    reference_id = models.IntegerField(verbose_name='参考ID')
    move_date = models.DateTimeField(auto_now_add=True, verbose_name='移动时间')
    notes = models.TextField(null=True, blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'batch_move'
        verbose_name = '批次移动'
        verbose_name_plural = verbose_name
        ordering = ['-move_date']
    
    def __str__(self):
        return f"{self.batch.batch_no} - {self.get_move_type_display()} - {self.qty}"

