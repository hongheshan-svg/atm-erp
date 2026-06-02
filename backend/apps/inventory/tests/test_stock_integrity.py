"""
库存移动事务一致性回归测试（审计 high）。

StockMove.save 原先先 super().save() 持久化本行(status=COMPLETED)，再 _update_stock；
出库不足时 _update_stock_out 抛 ValueError，但本行已提交 → 残留 status=COMPLETED 的
假移动记录而库存未扣减、账实不符。修复:本行写入与库存更新置于同一 transaction.atomic。
"""

from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.inventory.data_accuracy import InventoryDataValidator
from apps.inventory.models import Stock, StockMove
from apps.masterdata.models import Item, Warehouse


class StockMoveAtomicTest(TestCase):
    def setUp(self):
        self.wh = Warehouse.objects.create(code='WH_T', name='测试仓')
        self.item = Item.objects.create(sku='SKU_T', name='测试物料')
        self.stock = Stock.objects.create(warehouse=self.wh, item=self.item, qty_on_hand=Decimal('5'))

    def _make_out(self, qty):
        return StockMove.objects.create(
            item=self.item,
            warehouse_from=self.wh,
            qty=Decimal(qty),
            unit_cost=Decimal('1'),
            move_type='OUT_SALES',
            move_date=date.today(),
            status='COMPLETED',
        )

    def test_insufficient_stock_rolls_back_move(self):
        # 出库 10 > 库存 5 → ValueError，且不应残留 StockMove 记录、库存不变
        with self.assertRaises(ValueError):
            self._make_out('10')
        self.assertEqual(StockMove.objects.filter(item=self.item).count(), 0)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.qty_on_hand, Decimal('5'))

    def test_sufficient_stock_completes_and_decrements(self):
        self.stock.qty_on_hand = Decimal('20')
        self.stock.save()
        move = self._make_out('10')
        self.assertEqual(StockMove.objects.filter(pk=move.pk).count(), 1)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.qty_on_hand, Decimal('10'))


class InOutBalanceOpeningTest(TestCase):
    """check_in_out_balance 期初结存应取自期初前移动净额，而非硬编码 0（审计 medium 假阳性）。"""

    def setUp(self):
        self.wh = Warehouse.objects.create(code='WH_B', name='平衡仓')
        self.item = Item.objects.create(sku='SKU_B', name='平衡物料')
        # 期初前入库 10（move_date < 期初）→ 期初结存应为 10
        StockMove.objects.create(
            item=self.item, warehouse_to=self.wh, qty=Decimal('10'), unit_cost=Decimal('1'),
            move_type='IN_PURCHASE', move_date=date(2026, 5, 1), status='COMPLETED',
        )
        # 期间内入库 5
        StockMove.objects.create(
            item=self.item, warehouse_to=self.wh, qty=Decimal('5'), unit_cost=Decimal('1'),
            move_type='IN_PURCHASE', move_date=date(2026, 6, 5), status='COMPLETED',
        )
        # 此时 Stock.qty_on_hand 由移动自动维护为 15

    def _imbalance_for_item(self):
        results = InventoryDataValidator.check_in_out_balance(start_date=date(2026, 6, 1), end_date=date(2026, 6, 30))
        return [r for r in results if r['item_id'] == self.item.id]

    def test_consistent_item_no_false_imbalance(self):
        # 期初(10)+本期入(5)-出(0)=15=账面 → 不应报不平衡（修复前期初=0→误报差异10）
        self.assertEqual(self._imbalance_for_item(), [])

    def test_real_imbalance_still_detected(self):
        # 人为篡改账面(绕过移动)→ 仍应检出，确认校验未因修复而失效
        Stock.objects.filter(item=self.item, warehouse=self.wh).update(qty_on_hand=Decimal('99'))
        self.assertEqual(len(self._imbalance_for_item()), 1)
