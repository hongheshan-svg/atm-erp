"""
Inventory management models - Stock, StockMove, Adjustment.
"""
from django.db import models

from apps.core.models import BaseModel
from apps.core.utils import generate_code


class Stock(BaseModel):
    """
    Stock - Real-time inventory levels.
    This is a computed/aggregated view, updated by StockMove.
    """
    warehouse = models.ForeignKey(
        'masterdata.Warehouse',
        on_delete=models.PROTECT,
        related_name='stocks',
        verbose_name='仓库'
    )
    item = models.ForeignKey(
        'masterdata.Item',
        on_delete=models.PROTECT,
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
    
    
    class Meta:
        db_table = 'stock'
        verbose_name = '库存'
        verbose_name_plural = verbose_name
        ordering = ['warehouse', 'item']
        constraints = [
            models.UniqueConstraint(
                fields=['warehouse', 'item'],
                condition=models.Q(is_deleted=False),
                name='stock_unique_active'
            ),
            models.CheckConstraint(
                check=models.Q(qty_on_hand__gte=0),
                name='stock_qty_non_negative'
            ),
        ]
    
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
        # 热表:库存流水按日期排序、按状态/类型/来源单据高频过滤(审计 P1 索引缺失)
        indexes = [
            models.Index(fields=['-move_date']),
            models.Index(fields=['status', 'move_type']),
            models.Index(fields=['reference_type', 'reference_id']),
            models.Index(fields=['item', '-move_date']),
        ]
    
    def __str__(self):
        return f"{self.move_no} - {self.item.sku}"
    
    def save(self, *args, **kwargs):
        from django.db import transaction

        if not self.move_no:
            self.move_no = generate_code('SM', rule_type='STOCK_MOVE')

        is_new = self.pk is None
        was_completed = False
        if not is_new:
            was_completed = StockMove.objects.filter(pk=self.pk, status='COMPLETED').exists()

        # 本行写入与库存更新置于同一事务：否则出库不足时 _update_stock 抛错而本行已提交，
        # 会残留 status=COMPLETED 的假移动记录、库存未扣减、账实不符（审计 high 数据一致性）。
        # 内层 _update_stock_* 自带 atomic，此处作为外层事务/savepoint，嵌套安全。
        with transaction.atomic():
            super().save(*args, **kwargs)
            # Auto-update stock when transitioning to COMPLETED
            if self.status == 'COMPLETED' and not was_completed:
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
            # Transfer between warehouses (atomic to prevent partial updates)
            from django.db import transaction
            with transaction.atomic():
                self._update_stock_out(self.warehouse_from, self.qty)
                self._update_stock_in(self.warehouse_to, self.qty, self.unit_cost)
        
        elif self.move_type == 'ADJUSTMENT':
            # qty 恒为正(apply_adjustment 写入 abs(qty_diff))，盘盈/盘亏方向由仓库字段决定：
            # warehouse_to 有值=盘盈入库；warehouse_from 有值=盘亏出库。
            # 原按 self.qty>0 判方向恒成立 → 盘亏被误当盘盈入库到 None 仓，账实损坏。
            if self.warehouse_to:
                self._update_stock_in(self.warehouse_to, self.qty, self.unit_cost)
            elif self.warehouse_from:
                self._update_stock_out(self.warehouse_from, self.qty)
    
    def _update_stock_in(self, warehouse, qty, cost):
        """Update stock for incoming movement (weighted average)."""
        from django.db import transaction
        with transaction.atomic():
            stock, created = Stock.objects.select_for_update().get_or_create(
                warehouse=warehouse,
                item=self.item,
                defaults={'qty_on_hand': 0, 'weighted_avg_cost': 0}
            )

            old_value = stock.qty_on_hand * stock.weighted_avg_cost
            new_value = qty * cost
            new_qty = stock.qty_on_hand + qty

            if new_qty > 0:
                stock.weighted_avg_cost = (old_value + new_value) / new_qty
            else:
                stock.weighted_avg_cost = cost

            stock.qty_on_hand = new_qty
            stock.save(update_fields=['qty_on_hand', 'weighted_avg_cost'])

            # 同步登记物料成本账（入库）——与 Stock 更新同事务，见 _record_cost_ledger。
            self._record_cost_ledger(warehouse, qty, cost, 'IN')

    def _update_stock_out(self, warehouse, qty):
        """Update stock for outgoing movement."""
        from django.db import transaction
        with transaction.atomic():
            try:
                stock = Stock.objects.select_for_update().get(warehouse=warehouse, item=self.item)
                if stock.qty_on_hand < qty:
                    raise ValueError(
                        f'库存不足: {stock.item} 在 {stock.warehouse} 当前库存 {stock.qty_on_hand}, 需要 {qty}'
                    )
                stock.qty_on_hand -= qty
                stock.save(update_fields=['qty_on_hand'])
                # 同步登记物料成本账（出库）——出库单价用本移动的 unit_cost
                # （加权平均时=Stock 加权成本；FIFO 时=领料环节写入的分层实耗成本）。
                self._record_cost_ledger(warehouse, qty, self.unit_cost, 'OUT')
            except Stock.DoesNotExist:
                pass

    # move_type + 方向 -> ItemCostRecord.transaction_type（成本账交易类型）
    _COST_TXN_TYPE = {
        ('IN_PURCHASE', 'IN'): 'PURCHASE_IN',
        ('OUT_SALES', 'OUT'): 'SALES_OUT',
        ('OUT_PROJECT', 'OUT'): 'PRODUCTION_OUT',
        ('TRANSFER', 'IN'): 'TRANSFER_IN',
        ('TRANSFER', 'OUT'): 'TRANSFER_OUT',
        ('ADJUSTMENT', 'IN'): 'ADJUST_IN',
        ('ADJUSTMENT', 'OUT'): 'ADJUST_OUT',
    }

    def _record_cost_ledger(self, warehouse, qty, unit_cost, direction):
        """在库存移动完成时同步登记物料成本账 (ItemCostRecord)。

        这是成本账的唯一写入点：入库(_update_stock_in)/出库(_update_stock_out) 各调用一次，
        保证每笔移动只登记一次、且与 Stock 数量更新处于同一 transaction.atomic（外层 save()
        以 was_completed 去重，转 COMPLETED 仅触发一次）。TRANSFER 会入/出各记一笔，构成对偶。

        仅当已配置启用的库存成本核算(InventoryCostConfig)时才登记，否则静默跳过——避免在
        未启用成本核算的环境凭空写账、以及首笔落库与历史 Stock 结存不一致。任何异常都不应
        破坏库存移动主流程本身。
        """
        if warehouse is None:
            return
        import logging

        from django.db import transaction

        from .cost_accounting import CostCalculationService, InventoryCostConfig

        try:
            if not InventoryCostConfig.objects.filter(is_active=True, is_deleted=False).exists():
                return

            txn_type = self._COST_TXN_TYPE.get((self.move_type, direction))
            if not txn_type:
                txn_type = 'ADJUST_IN' if direction == 'IN' else 'ADJUST_OUT'

            service = CostCalculationService()
            actor = self.updated_by or self.created_by
            # 成本账是派生副作用:置于独立 savepoint,登记失败仅回滚本次登记(不使外层事务进入
            # aborted 状态),绝不破坏库存移动主流程本身(兑现上文 docstring 承诺)。
            with transaction.atomic():
                if direction == 'IN':
                    service.process_inbound(
                        item_id=self.item_id,
                        warehouse_id=warehouse.id,
                        quantity=qty,
                        unit_cost=unit_cost,
                        transaction_type=txn_type,
                        reference_no=self.move_no,
                        reference_id=self.reference_id,
                        transaction_date=self.move_date,
                        user=actor,
                    )
                else:
                    # 出库单价:仅在本移动带有真实单价时显式传入(FIFO 分层实耗成本 / 已计价移动);
                    # 为 0/未计价的普通出库(如 OUT_SALES 发货)传 None,由成本账按结存加权成本派生,
                    # 避免把出库成本错记为 0。
                    out_unit_cost = unit_cost if (unit_cost and unit_cost > 0) else None
                    service.process_outbound(
                        item_id=self.item_id,
                        warehouse_id=warehouse.id,
                        quantity=qty,
                        transaction_type=txn_type,
                        reference_no=self.move_no,
                        reference_id=self.reference_id,
                        transaction_date=self.move_date,
                        user=actor,
                        unit_cost=out_unit_cost,
                    )
        except Exception as exc:
            logging.getLogger(__name__).warning(
                '成本账登记失败(move_no=%s, dir=%s),已跳过,不影响库存移动: %s',
                self.move_no, direction, exc,
            )


class StockAdjustment(BaseModel):
    """
    Stock Adjustment - for cycle counting and corrections.
    
    库存调整审批流程由审批中心的流程配置决定。
    """
    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('PENDING', '审批中'),
        ('APPROVED', '已审批'),
        ('REJECTED', '已拒绝'),
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
            self.adjustment_no = generate_code('ADJ', rule_type='STOCK_ADJUSTMENT')
        super().save(*args, **kwargs)
    
    def apply_adjustment(self):
        """执行库存调整，创建库存变动记录"""
        from django.db import transaction as db_transaction
        
        with db_transaction.atomic():
            for line in self.lines.filter(is_deleted=False):
                if line.qty_diff != 0:
                    # Create stock move for adjustment
                    warehouse_to = self.warehouse if line.qty_diff > 0 else None
                    warehouse_from = self.warehouse if line.qty_diff < 0 else None
                    
                    # Get current weighted average cost
                    try:
                        stock = Stock.objects.get(
                            warehouse=self.warehouse,
                            item=line.item
                        )
                        unit_cost = stock.weighted_avg_cost
                    except Stock.DoesNotExist:
                        unit_cost = 0
                    
                    StockMove.objects.create(
                        item=line.item,
                        warehouse_from=warehouse_from,
                        warehouse_to=warehouse_to,
                        qty=abs(line.qty_diff),
                        unit_cost=unit_cost,
                        move_type='ADJUSTMENT',
                        reference_type='StockAdjustment',
                        reference_id=self.id,
                        move_date=self.adjustment_date,
                        status='COMPLETED',
                        created_by=self.created_by
                    )
            
            self.status = 'CONFIRMED'
            self.save()


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


# 导入领料/退料模型，使其可被迁移系统发现（注册 + 供 models.py 再导出）
from .material_models import (  # noqa: E402, F401
    MaterialRequisition,
    MaterialRequisitionLine,
    MaterialReturn,
    MaterialReturnLine,
)
from .mrp import MRPLine, MRPPlan  # noqa: E402, F401

# Import new improvement module models
from .spare_parts import (  # noqa: E402, F401
    SparePart,
    SparePartAlert,
    SparePartCategory,
    SparePartConsumption,
    SparePartEquipmentRelation,
    SparePartForecast,
)
from .spare_parts_prediction import PurchaseSuggestion, SparePartLifecyclePrediction  # noqa: E402, F401
