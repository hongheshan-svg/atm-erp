"""成本引擎回归测试（P1：成本账登记 + FIFO 分层消耗）。

覆盖审计 P1 缺陷的修复:
- ItemCostRecord 成本账此前无任何写入点(死代码)。现由 StockMove 完成时统一登记
  (_record_cost_ledger),仅当存在启用的 InventoryCostConfig 时生效。
- FIFOCostingService.consume_stock 此前无调用者且缺量只告警不抛错。现:领料出库按
  FIFO 分层实耗成本计价,批次不足抛 ValueError 回滚,update_stock=False 避免与
  StockMove 双重扣减 Stock。
"""

from datetime import date
from decimal import Decimal

from django.test import TestCase, override_settings

from apps.inventory.batch_models import InventoryLot, LotConsumption
from apps.inventory.cost_accounting import InventoryCostConfig, ItemCostRecord
from apps.inventory.cost_methods import FIFOCostingService
from apps.inventory.models import Stock, StockMove
from apps.masterdata.models import Item, Warehouse


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class CostLedgerRecordingTest(TestCase):
    """StockMove 完成时按是否启用成本核算登记 ItemCostRecord。"""

    def setUp(self):
        self.wh = Warehouse.objects.create(code='WH_CE', name='成本仓')
        self.item = Item.objects.create(sku='SKU_CE', name='成本物料')

    def _inbound(self, qty, unit_cost):
        return StockMove.objects.create(
            item=self.item, warehouse_to=self.wh,
            qty=Decimal(str(qty)), unit_cost=Decimal(str(unit_cost)),
            move_type='IN_PURCHASE', move_date=date.today(), status='COMPLETED',
        )

    def test_inbound_records_cost_ledger_when_config_active(self):
        InventoryCostConfig.objects.create(
            name='默认', costing_method='WEIGHTED_AVG', is_active=True, is_default=True,
        )
        self._inbound(10, 5)
        rec = ItemCostRecord.objects.filter(item=self.item, warehouse=self.wh).first()
        self.assertIsNotNone(rec, '入库应登记一条成本账')
        self.assertEqual(rec.transaction_type, 'PURCHASE_IN')
        self.assertEqual(rec.quantity, Decimal('10.0000'))
        self.assertEqual(rec.balance_qty, Decimal('10.0000'))
        self.assertEqual(rec.balance_unit_cost, Decimal('5.0000'))

    def test_no_cost_ledger_without_active_config(self):
        # 未启用成本核算时不得凭空写账(不影响未配置环境/既有测试)
        self._inbound(10, 5)
        self.assertFalse(ItemCostRecord.objects.filter(item=self.item).exists())
        # 但库存数量照常更新
        stock = Stock.objects.get(warehouse=self.wh, item=self.item)
        self.assertEqual(stock.qty_on_hand, Decimal('10'))

    def test_outbound_derives_weighted_cost_when_move_uncosted(self):
        # OUT_SALES 移动 unit_cost=0 时,成本账出库单价应按结存加权成本派生,而非记为 0
        InventoryCostConfig.objects.create(name='默认', costing_method='WEIGHTED_AVG', is_active=True)
        self._inbound(10, 8)
        StockMove.objects.create(
            item=self.item, warehouse_from=self.wh, qty=Decimal('4'), unit_cost=Decimal('0'),
            move_type='OUT_SALES', move_date=date.today(), status='COMPLETED',
        )
        out_rec = ItemCostRecord.objects.filter(
            item=self.item, transaction_type='SALES_OUT'
        ).order_by('-created_at').first()
        self.assertIsNotNone(out_rec)
        self.assertEqual(out_rec.unit_cost, Decimal('8.0000'))  # 结存加权成本,非 0


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class FIFOConsumptionTest(TestCase):
    """FIFO 按批次先进先出消耗,返回分层实耗成本;缺量抛错回滚。"""

    def setUp(self):
        self.wh = Warehouse.objects.create(code='WH_FI', name='FIFO仓')
        self.item = Item.objects.create(sku='SKU_FI', name='FIFO物料')

    def _lot(self, lot_no, qty, unit_cost):
        return InventoryLot.objects.create(
            lot_no=lot_no, warehouse=self.wh, item=self.item,
            initial_qty=Decimal(str(qty)), remaining_qty=Decimal(str(qty)),
            unit_cost=Decimal(str(unit_cost)),
        )

    def test_consume_oldest_first_layered_cost(self):
        self._lot('LOT_A', 10, 3)   # 先建 -> 先进先出先消耗
        self._lot('LOT_B', 10, 5)
        total_cost, consumptions = FIFOCostingService.consume_stock(
            warehouse=self.wh, item=self.item, qty=Decimal('15'), update_stock=False,
        )
        # 10@3 + 5@5 = 55
        self.assertEqual(total_cost, Decimal('55'))
        self.assertEqual(len(consumptions), 2)
        a = InventoryLot.objects.get(lot_no='LOT_A')
        b = InventoryLot.objects.get(lot_no='LOT_B')
        self.assertEqual(a.remaining_qty, Decimal('0'))     # 老批次先耗尽
        self.assertEqual(b.remaining_qty, Decimal('5'))
        self.assertEqual(LotConsumption.objects.filter(lot__item=self.item).count(), 2)

    def test_shortage_raises_and_rolls_back(self):
        self._lot('LOT_C', 10, 3)
        with self.assertRaises(ValueError):
            FIFOCostingService.consume_stock(
                warehouse=self.wh, item=self.item, qty=Decimal('15'), update_stock=False,
            )
        # 回滚:批次余量不变,无消耗记录残留
        self.assertEqual(InventoryLot.objects.get(lot_no='LOT_C').remaining_qty, Decimal('10'))
        self.assertEqual(LotConsumption.objects.filter(lot__item=self.item).count(), 0)

    def test_consume_does_not_touch_stock_when_update_stock_false(self):
        # Stock 数量由 StockMove 独占维护;FIFO 消耗仅更新批次账,不得改 Stock
        Stock.objects.create(warehouse=self.wh, item=self.item, qty_on_hand=Decimal('10'))
        self._lot('LOT_D', 10, 4)
        FIFOCostingService.consume_stock(
            warehouse=self.wh, item=self.item, qty=Decimal('6'),
            update_stock=False,
        )
        stock = Stock.objects.get(warehouse=self.wh, item=self.item)
        self.assertEqual(stock.qty_on_hand, Decimal('10'))  # 未被 FIFO 消耗改动
