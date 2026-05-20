"""
Integration tests for inventory stock moves and weighted-average costing.

Uses model-level operations because the StockMove model itself applies stock
updates in its save() method when status='COMPLETED', making it easy to test
without navigating multi-step receipt approval flows.

Key facts:
- StockMove with status='COMPLETED' and move_type='IN_PURCHASE' calls
  _update_stock_in() which applies weighted-average cost to Stock.
- StockMove with move_type in ['OUT_SALES', 'OUT_PROJECT'] calls
  _update_stock_out() which reduces qty_on_hand.
"""

import datetime
from decimal import Decimal

import pytest

from apps.inventory.models import Stock, StockMove

pytestmark = pytest.mark.django_db


def _completed_in(item, warehouse, qty, unit_cost, admin_user):
    """Create a completed IN_PURCHASE stock move, returns the StockMove."""
    return StockMove.objects.create(
        item=item,
        warehouse_to=warehouse,
        qty=Decimal(str(qty)),
        unit_cost=Decimal(str(unit_cost)),
        move_type='IN_PURCHASE',
        move_date=datetime.date.today(),
        status='COMPLETED',
        created_by=admin_user,
    )


def _completed_out(item, warehouse, qty, admin_user):
    """Create a completed OUT_SALES stock move, returns the StockMove."""
    return StockMove.objects.create(
        item=item,
        warehouse_from=warehouse,
        qty=Decimal(str(qty)),
        unit_cost=Decimal('0'),
        move_type='OUT_SALES',
        move_date=datetime.date.today(),
        status='COMPLETED',
        created_by=admin_user,
    )


# ---------------------------------------------------------------------------
# Test 1 – inbound move creates / updates a Stock record
# ---------------------------------------------------------------------------

def test_inbound_creates_stock(make_item, make_warehouse, admin_user):
    """A COMPLETED IN_PURCHASE move creates the Stock row with correct qty."""
    item = make_item(standard_cost=Decimal('100.00'))
    warehouse = make_warehouse()

    _completed_in(item, warehouse, qty=10, unit_cost='200.00', admin_user=admin_user)

    stock = Stock.objects.get(warehouse=warehouse, item=item)
    assert stock.qty_on_hand == Decimal('10')
    assert stock.weighted_avg_cost == Decimal('200.00')


# ---------------------------------------------------------------------------
# Test 2 – outbound move reduces stock quantity
# ---------------------------------------------------------------------------

def test_outbound_reduces_stock(make_item, make_warehouse, admin_user):
    """A COMPLETED OUT_SALES move reduces qty_on_hand on the Stock row."""
    item = make_item(standard_cost=Decimal('100.00'))
    warehouse = make_warehouse()

    # First bring stock in
    _completed_in(item, warehouse, qty=20, unit_cost='100.00', admin_user=admin_user)

    # Then move some out
    _completed_out(item, warehouse, qty=5, admin_user=admin_user)

    stock = Stock.objects.get(warehouse=warehouse, item=item)
    assert stock.qty_on_hand == Decimal('15')


# ---------------------------------------------------------------------------
# Test 3 – weighted average cost is recalculated correctly
# ---------------------------------------------------------------------------

def test_weighted_average_cost(make_item, make_warehouse, admin_user):
    """Two inbounds at different prices produce the correct weighted average.

    Batch 1: 10 units @ 100  → total value = 1000
    Batch 2: 10 units @ 200  → total value = 2000
    Combined: 20 units, value 3000 → WAC = 150
    """
    item = make_item(standard_cost=Decimal('0'))
    warehouse = make_warehouse()

    _completed_in(item, warehouse, qty=10, unit_cost='100.00', admin_user=admin_user)
    _completed_in(item, warehouse, qty=10, unit_cost='200.00', admin_user=admin_user)

    stock = Stock.objects.get(warehouse=warehouse, item=item)
    assert stock.qty_on_hand == Decimal('20')
    assert stock.weighted_avg_cost == Decimal('150.00'), (
        f"Expected WAC=150.00 but got {stock.weighted_avg_cost}"
    )
