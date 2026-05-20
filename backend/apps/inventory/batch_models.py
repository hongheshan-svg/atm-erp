"""
批次追溯管理 (可选功能)
Batch and Lot Tracking Models

此功能为可选，非标自动化行业使用建议：
- 需要追溯的关键物料（如安全件、认证件）可启用批次管理
- 有保质期的物料（润滑油、密封件等）建议启用
- 一般定制件无需批次追溯

如不需要，可在物料主数据中关闭批次管理选项
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


class InventoryLot(BaseModel):
    """
    Inventory Lot for FIFO costing.
    Each purchase creates a new lot with its own cost.
    """
    lot_no = models.CharField(max_length=50, unique=True, verbose_name='批次号')
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name='inventory_lots',
        verbose_name='仓库'
    )
    item = models.ForeignKey(
        Item,
        on_delete=models.PROTECT,
        related_name='inventory_lots',
        verbose_name='物料'
    )

    # Quantity tracking
    initial_qty = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='初始数量'
    )
    remaining_qty = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='剩余数量'
    )

    # Cost
    unit_cost = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='单位成本'
    )

    # Receipt info
    receipt_date = models.DateField(auto_now_add=True, verbose_name='入库日期', db_index=True)
    reference_type = models.CharField(max_length=50, blank=True, verbose_name='参考类型')
    reference_id = models.IntegerField(null=True, blank=True, verbose_name='参考ID')

    notes = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'inventory_lot'
        verbose_name = 'FIFO库存批次'
        verbose_name_plural = verbose_name
        ordering = ['item', 'warehouse', 'receipt_date']
        indexes = [
            models.Index(fields=['item', 'warehouse', 'receipt_date']),
            models.Index(fields=['remaining_qty']),
        ]

    def __str__(self):
        return f"{self.lot_no} - {self.item.sku} ({self.remaining_qty}/{self.initial_qty})"

    def save(self, *args, **kwargs):
        if not self.lot_no:
            from apps.core.utils import generate_code
            self.lot_no = generate_code('LOT')
        super().save(*args, **kwargs)

    @property
    def total_value(self):
        """Current value of remaining inventory."""
        return self.remaining_qty * self.unit_cost

    @property
    def consumed_qty(self):
        """Quantity that has been consumed."""
        return self.initial_qty - self.remaining_qty


class LotConsumption(BaseModel):
    """
    Record of inventory consumption from a specific lot.
    Used for FIFO cost tracking.
    """
    lot = models.ForeignKey(
        InventoryLot,
        on_delete=models.PROTECT,
        related_name='consumptions',
        verbose_name='库存批次'
    )
    qty = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='消耗数量'
    )
    unit_cost = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='单位成本'
    )
    total_cost = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='总成本'
    )

    # Optional project for cost allocation
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='lot_consumptions',
        verbose_name='项目'
    )

    consumption_date = models.DateTimeField(auto_now_add=True, verbose_name='消耗时间')

    class Meta:
        db_table = 'lot_consumption'
        verbose_name = '批次消耗记录'
        verbose_name_plural = verbose_name
        ordering = ['-consumption_date']

    def __str__(self):
        return f"{self.lot.lot_no} - {self.qty} @ {self.unit_cost}"


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

