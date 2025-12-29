"""
Inventory management models - Stock, StockMove, Adjustment.
"""
from django.db import models
from django.db.models import Sum, F
from apps.core.models import BaseModel
from apps.core.utils import generate_code


class Stock(models.Model):
    """
    Stock - Real-time inventory levels.
    This is a computed/aggregated view, updated by StockMove.
    """
    warehouse = models.ForeignKey(
        'masterdata.Warehouse',
        on_delete=models.CASCADE,
        related_name='stocks',
        verbose_name='仓库'
    )
    item = models.ForeignKey(
        'masterdata.Item',
        on_delete=models.CASCADE,
        related_name='stocks',
        verbose_name='物料'
    )
    qty_on_hand = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name='账面库存'
    )
    qty_reserved = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name='预留数量'
    )
    # Computed field
    @property
    def qty_available(self):
        """Available quantity = on_hand - reserved."""
        return self.qty_on_hand - self.qty_reserved
    
    # Weighted average cost
    weighted_avg_cost = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name='加权平均成本'
    )
    
    last_updated = models.DateTimeField(auto_now=True, verbose_name='最后更新时间')
    
    class Meta:
        db_table = 'stock'
        verbose_name = '库存'
        verbose_name_plural = verbose_name
        unique_together = ['warehouse', 'item']
        ordering = ['warehouse', 'item']
    
    def __str__(self):
        return f"{self.warehouse.code} - {self.item.sku}: {self.qty_on_hand}"


class StockMove(BaseModel):
    """
    Stock Move - All inventory transactions.
    This is the source of truth for all stock movements.
    """
    MOVE_TYPE_CHOICES = [
        ('IN_PURCHASE', '采购入库'),
        ('OUT_SALES', '销售出库'),
        ('OUT_PROJECT', '项目领料'),
        ('TRANSFER', '调拨'),
        ('ADJUSTMENT', '调整'),
    ]
    
    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('COMPLETED', '完成'),
        ('CANCELLED', '已取消'),
    ]
    
    move_no = models.CharField(max_length=50, unique=True, verbose_name='移动单号')
    item = models.ForeignKey(
        'masterdata.Item',
        on_delete=models.PROTECT,
        related_name='stock_moves',
        verbose_name='物料'
    )
    warehouse_from = models.ForeignKey(
        'masterdata.Warehouse',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='stock_moves_out',
        verbose_name='来源仓库'
    )
    warehouse_to = models.ForeignKey(
        'masterdata.Warehouse',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='stock_moves_in',
        verbose_name='目标仓库'
    )
    qty = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='数量')
    unit_cost = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='单位成本'
    )
    move_type = models.CharField(
        max_length=20,
        choices=MOVE_TYPE_CHOICES,
        verbose_name='移动类型'
    )
    reference_type = models.CharField(max_length=50, blank=True, verbose_name='参考类型')
    reference_id = models.IntegerField(null=True, blank=True, verbose_name='参考ID')
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stock_moves',
        verbose_name='关联项目'
    )
    move_date = models.DateField(verbose_name='移动日期')
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='DRAFT',
        verbose_name='状态'
    )
    notes = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'stock_move'
        verbose_name = '库存移动'
        verbose_name_plural = verbose_name
        ordering = ['-move_date', '-created_at']
    
    def __str__(self):
        return f"{self.move_no} - {self.item.sku}"
    
    def save(self, *args, **kwargs):
        if not self.move_no:
            self.move_no = generate_code('SM')
        
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        # Auto-update stock when status is COMPLETED
        if self.status == 'COMPLETED' and is_new:
            self._update_stock()
    
    def _update_stock(self):
        """Update stock levels based on move type."""
        if self.move_type == 'IN_PURCHASE':
            # Incoming stock
            self._update_stock_in(self.warehouse_to, self.qty, self.unit_cost)
        
        elif self.move_type in ['OUT_SALES', 'OUT_PROJECT']:
            # Outgoing stock
            self._update_stock_out(self.warehouse_from, self.qty)
        
        elif self.move_type == 'TRANSFER':
            # Transfer between warehouses
            self._update_stock_out(self.warehouse_from, self.qty)
            self._update_stock_in(self.warehouse_to, self.qty, self.unit_cost)
        
        elif self.move_type == 'ADJUSTMENT':
            # Adjustment can be positive or negative
            if self.qty > 0:
                self._update_stock_in(self.warehouse_to, self.qty, self.unit_cost)
            else:
                self._update_stock_out(self.warehouse_from, abs(self.qty))
    
    def _update_stock_in(self, warehouse, qty, cost):
        """Update stock for incoming movement (weighted average)."""
        stock, created = Stock.objects.get_or_create(
            warehouse=warehouse,
            item=self.item,
            defaults={'qty_on_hand': 0, 'weighted_avg_cost': 0}
        )
        
        # Calculate weighted average cost
        old_value = stock.qty_on_hand * stock.weighted_avg_cost
        new_value = qty * cost
        new_qty = stock.qty_on_hand + qty
        
        if new_qty > 0:
            stock.weighted_avg_cost = (old_value + new_value) / new_qty
        else:
            stock.weighted_avg_cost = cost
        
        stock.qty_on_hand = new_qty
        stock.save()
    
    def _update_stock_out(self, warehouse, qty):
        """Update stock for outgoing movement."""
        try:
            stock = Stock.objects.get(warehouse=warehouse, item=self.item)
            stock.qty_on_hand -= qty
            stock.save()
        except Stock.DoesNotExist:
            # This shouldn't happen, but handle gracefully
            pass


class StockAdjustment(BaseModel):
    """
    Stock Adjustment - for cycle counting and corrections.
    """
    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('CONFIRMED', '已确认'),
    ]
    
    adjustment_no = models.CharField(max_length=50, unique=True, verbose_name='调整单号')
    warehouse = models.ForeignKey(
        'masterdata.Warehouse',
        on_delete=models.PROTECT,
        related_name='adjustments',
        verbose_name='仓库'
    )
    adjustment_date = models.DateField(verbose_name='调整日期')
    reason = models.TextField(verbose_name='调整原因')
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='DRAFT',
        verbose_name='状态'
    )
    notes = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'stock_adjustment'
        verbose_name = '库存调整'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.adjustment_no}"
    
    def save(self, *args, **kwargs):
        if not self.adjustment_no:
            self.adjustment_no = generate_code('ADJ')
        super().save(*args, **kwargs)


class StockAdjustmentLine(BaseModel):
    """
    Stock Adjustment Line - detailed adjustments.
    """
    adjustment = models.ForeignKey(
        StockAdjustment,
        on_delete=models.CASCADE,
        related_name='lines',
        verbose_name='调整单'
    )
    item = models.ForeignKey(
        'masterdata.Item',
        on_delete=models.PROTECT,
        related_name='adjustment_lines',
        verbose_name='物料'
    )
    qty_system = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='账面数量'
    )
    qty_actual = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='实际数量'
    )
    qty_diff = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='差异数量'
    )
    cost_impact = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name='成本影响'
    )
    notes = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'stock_adjustment_line'
        verbose_name = '库存调整明细'
        verbose_name_plural = verbose_name
        ordering = ['id']
    
    def __str__(self):
        return f"{self.adjustment.adjustment_no} - {self.item.sku}"
    
    def save(self, *args, **kwargs):
        self.qty_diff = self.qty_actual - self.qty_system
        super().save(*args, **kwargs)


# 导入领料/退料模型，使其可被迁移系统发现
from .material_models import (
    MaterialRequisition, MaterialRequisitionLine,
    MaterialReturn, MaterialReturnLine
)
