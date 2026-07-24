"""
Inventory costing methods: FIFO, Weighted Average.
"""

import logging
from decimal import Decimal

from django.db import transaction
from django.db.models import F, Sum

logger = logging.getLogger(__name__)


class FIFOCostingService:
    """
    FIFO (First In, First Out) costing method.

    Tracks inventory by batches/lots and uses the oldest stock first.
    """

    @classmethod
    def record_purchase(cls, warehouse, item, qty, unit_cost, reference_type=None, reference_id=None):
        """
        Record a purchase (incoming stock) using FIFO.
        Creates a new inventory lot.

        Args:
            warehouse: Warehouse instance
            item: Item instance
            qty: Quantity received
            unit_cost: Cost per unit
            reference_type: Type of reference document (e.g., 'GoodsReceipt')
            reference_id: ID of reference document

        Returns:
            InventoryLot instance
        """
        from .batch_models import InventoryLot

        lot = InventoryLot.objects.create(
            warehouse=warehouse,
            item=item,
            initial_qty=qty,
            remaining_qty=qty,
            unit_cost=unit_cost,
            reference_type=reference_type,
            reference_id=reference_id,
        )

        # Update stock record
        cls._update_stock(warehouse, item)

        return lot

    @classmethod
    def consume_stock(cls, warehouse, item, qty, project=None, update_stock=True, raise_on_shortage=True):
        """
        Consume stock using FIFO method.
        Uses oldest lots first.

        Args:
            warehouse: Warehouse instance
            item: Item instance
            qty: Quantity to consume
            project: Optional project for cost tracking
            update_stock: 消耗后是否按批次结存回写 Stock。领料出库场景下 Stock 数量由
                StockMove 独占维护（P0：StockMove 为库存数量唯一真源），此时应传
                update_stock=False，仅更新批次账 + 返回分层成本，避免与 _update_stock_out
                双重扣减 Stock。
            raise_on_shortage: 批次余量不足时是否抛 ValueError（默认 True）。抛出会使外层
                事务回滚，杜绝“少消耗批次却照常出库”造成的负批次/账实不符。

        Returns:
            tuple: (total_cost, list of consumption details)
        """
        from .batch_models import InventoryLot, LotConsumption

        remaining_qty = Decimal(str(qty))
        total_cost = Decimal('0')
        consumptions = []

        with transaction.atomic():
            # Get available lots ordered by receipt date (oldest first)。
            # select_for_update 锁定批次行，防止并发出库对同一批次重复消耗（惰性求值，
            # 在本 atomic 块内迭代时执行，锁生效）。
            lots = (
                InventoryLot.objects.select_for_update()
                .filter(warehouse=warehouse, item=item, remaining_qty__gt=0, is_deleted=False)
                .order_by('receipt_date', 'id')
            )

            for lot in lots:
                if remaining_qty <= 0:
                    break

                # Calculate how much to take from this lot
                consume_qty = min(lot.remaining_qty, remaining_qty)
                consume_cost = consume_qty * lot.unit_cost

                # Record consumption
                LotConsumption.objects.create(
                    lot=lot, qty=consume_qty, unit_cost=lot.unit_cost, total_cost=consume_cost, project=project
                )

                # Update lot remaining quantity
                lot.remaining_qty -= consume_qty
                lot.save()

                total_cost += consume_cost
                remaining_qty -= consume_qty

                consumptions.append(
                    {
                        'lot_id': lot.id,
                        'lot_no': lot.lot_no,
                        'qty': float(consume_qty),
                        'unit_cost': float(lot.unit_cost),
                        'total_cost': float(consume_cost),
                    }
                )

            if remaining_qty > 0:
                msg = (
                    f'FIFO 批次库存不足: item={item.sku}, warehouse={warehouse.code}, '
                    f'requested={qty}, shortage={remaining_qty}'
                )
                if raise_on_shortage:
                    raise ValueError(msg)
                logger.warning(msg)

            # Update stock record（仅当调用方要求；见 update_stock 参数说明）
            if update_stock:
                cls._update_stock(warehouse, item)

        return total_cost, consumptions

    @classmethod
    def get_fifo_cost(cls, warehouse, item, qty):
        """
        Calculate the FIFO cost for a given quantity without consuming.
        Useful for cost estimation.

        Args:
            warehouse: Warehouse instance
            item: Item instance
            qty: Quantity to calculate cost for

        Returns:
            tuple: (total_cost, average_unit_cost, details)
        """
        from .batch_models import InventoryLot

        lots = InventoryLot.objects.filter(
            warehouse=warehouse, item=item, remaining_qty__gt=0, is_deleted=False
        ).order_by('receipt_date', 'id')

        remaining_qty = Decimal(str(qty))
        total_cost = Decimal('0')
        details = []

        for lot in lots:
            if remaining_qty <= 0:
                break

            consume_qty = min(lot.remaining_qty, remaining_qty)
            consume_cost = consume_qty * lot.unit_cost

            total_cost += consume_cost
            remaining_qty -= consume_qty

            details.append(
                {
                    'lot_no': lot.lot_no,
                    'qty': float(consume_qty),
                    'unit_cost': float(lot.unit_cost),
                    'total_cost': float(consume_cost),
                }
            )

        actual_qty = Decimal(str(qty)) - remaining_qty
        avg_cost = total_cost / actual_qty if actual_qty > 0 else Decimal('0')

        return total_cost, avg_cost, details

    @classmethod
    def _update_stock(cls, warehouse, item):
        """
        Update the Stock record based on current lots.
        """
        from .batch_models import InventoryLot
        from .models import Stock

        # Calculate totals from lots
        lot_data = InventoryLot.objects.filter(
            warehouse=warehouse, item=item, remaining_qty__gt=0, is_deleted=False
        ).aggregate(total_qty=Sum('remaining_qty'), total_value=Sum(F('remaining_qty') * F('unit_cost')))

        total_qty = lot_data['total_qty'] or Decimal('0')
        total_value = lot_data['total_value'] or Decimal('0')

        # Calculate weighted average cost from FIFO lots
        avg_cost = total_value / total_qty if total_qty > 0 else Decimal('0')

        # Update or create stock record
        stock, created = Stock.objects.get_or_create(
            warehouse=warehouse, item=item, defaults={'qty_on_hand': total_qty, 'weighted_avg_cost': avg_cost}
        )

        if not created:
            stock.qty_on_hand = total_qty
            stock.weighted_avg_cost = avg_cost
            stock.save()

    @classmethod
    def get_lot_inventory(cls, warehouse=None, item=None):
        """
        Get current lot inventory with FIFO details.

        Args:
            warehouse: Optional warehouse filter
            item: Optional item filter

        Returns:
            QuerySet of InventoryLot
        """
        from .batch_models import InventoryLot

        queryset = InventoryLot.objects.filter(remaining_qty__gt=0, is_deleted=False).select_related(
            'warehouse', 'item'
        )

        if warehouse:
            queryset = queryset.filter(warehouse=warehouse)
        if item:
            queryset = queryset.filter(item=item)

        return queryset.order_by('item', 'warehouse', 'receipt_date')


class WeightedAverageCostingService:
    """
    Weighted Average costing method.

    Calculates average cost based on all available inventory.
    """

    @classmethod
    def record_purchase(cls, warehouse, item, qty, unit_cost):
        """
        Record a purchase using weighted average method.
        Updates the weighted average cost.

        Args:
            warehouse: Warehouse instance
            item: Item instance
            qty: Quantity received
            unit_cost: Cost per unit

        Returns:
            Stock instance
        """
        from .models import Stock

        stock, created = Stock.objects.get_or_create(
            warehouse=warehouse, item=item, defaults={'qty_on_hand': 0, 'weighted_avg_cost': 0}
        )

        # Calculate new weighted average
        old_value = stock.qty_on_hand * stock.weighted_avg_cost
        new_value = Decimal(str(qty)) * Decimal(str(unit_cost))
        new_qty = stock.qty_on_hand + Decimal(str(qty))

        if new_qty > 0:
            stock.weighted_avg_cost = (old_value + new_value) / new_qty
        else:
            stock.weighted_avg_cost = Decimal(str(unit_cost))

        stock.qty_on_hand = new_qty
        stock.save()

        return stock

    @classmethod
    def consume_stock(cls, warehouse, item, qty):
        """
        Consume stock using weighted average cost.

        Args:
            warehouse: Warehouse instance
            item: Item instance
            qty: Quantity to consume

        Returns:
            tuple: (total_cost, unit_cost)
        """
        from .models import Stock

        try:
            stock = Stock.objects.get(warehouse=warehouse, item=item)
        except Stock.DoesNotExist:
            return Decimal('0'), Decimal('0')

        unit_cost = stock.weighted_avg_cost
        total_cost = Decimal(str(qty)) * unit_cost

        stock.qty_on_hand -= Decimal(str(qty))
        stock.save()

        return total_cost, unit_cost

    @classmethod
    def get_cost(cls, warehouse, item, qty):
        """
        Get the weighted average cost for a quantity.

        Args:
            warehouse: Warehouse instance
            item: Item instance
            qty: Quantity

        Returns:
            tuple: (total_cost, unit_cost)
        """
        from .models import Stock

        try:
            stock = Stock.objects.get(warehouse=warehouse, item=item)
            unit_cost = stock.weighted_avg_cost
            total_cost = Decimal(str(qty)) * unit_cost
            return total_cost, unit_cost
        except Stock.DoesNotExist:
            return Decimal('0'), Decimal('0')


class CostingMethodFactory:
    """
    Factory for selecting costing method.
    """

    METHODS = {
        'FIFO': FIFOCostingService,
        'WEIGHTED_AVG': WeightedAverageCostingService,
    }

    @classmethod
    def get_service(cls, method='WEIGHTED_AVG'):
        """
        Get the costing service for the specified method.

        Args:
            method: 'FIFO' or 'WEIGHTED_AVG'

        Returns:
            Costing service class
        """
        return cls.METHODS.get(method, WeightedAverageCostingService)

    @classmethod
    def get_default_method(cls):
        """
        Get the default costing method from settings.
        """
        from django.conf import settings

        return getattr(settings, 'INVENTORY_COSTING_METHOD', 'WEIGHTED_AVG')
