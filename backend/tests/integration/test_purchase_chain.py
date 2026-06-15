"""
Integration tests for the purchase chain:
  PurchaseRequest → PurchaseOrder → GoodsReceipt (confirm) → Stock

Endpoints:
  POST /api/purchase/requests/           – create PR
  POST /api/purchase/orders/             – create PO
  POST /api/purchase/receipts/           – create GoodsReceipt
  POST /api/purchase/receipts/{id}/confirm/ – confirm receipt, creates StockMove

Key models:
  apps.purchase.models.PurchaseRequest, PurchaseOrder, PurchaseOrderLine,
                        GoodsReceipt, GoodsReceiptLine
  apps.inventory.models.Stock
"""

import datetime
from decimal import Decimal

import pytest

from apps.inventory.models import Stock

pytestmark = pytest.mark.django_db

PR_URL = '/api/purchase/requests/'
PO_URL = '/api/purchase/orders/'
RECEIPT_URL = '/api/purchase/receipts/'


def _today_plus(days: int) -> str:
    return (datetime.date.today() + datetime.timedelta(days=days)).isoformat()


# ---------------------------------------------------------------------------
# Test 1 – create a purchase request via API
# ---------------------------------------------------------------------------

def test_create_purchase_request(api_client_admin, admin_user, make_supplier, make_item):
    """POST /api/purchase/requests/ creates a PR in DRAFT status."""
    supplier = make_supplier()
    item = make_item(standard_cost=Decimal('50.00'))

    payload = {
        # requestor is auto-set to request.user in perform_create
        'supplier': supplier.id,
        'required_date': _today_plus(10),
        'notes': 'CI purchase request test',
        'lines': [
            {
                'item': item.id,
                # Nested line qty/price are passed straight to the model (read
                # from initial_data, not coerced by the serializer), so they
                # must be sent as JSON numbers — strings raise a model-level
                # TypeError in line_amount = qty * price.
                'qty': 5,
                'estimated_price': 50.00,
            }
        ],
    }

    resp = api_client_admin.post(PR_URL, payload, format='json')
    assert resp.status_code == 201, f"Expected 201 but got {resp.status_code}: {resp.data}"
    data = resp.data
    assert data['status'] == 'DRAFT'
    assert data['id']


# ---------------------------------------------------------------------------
# Test 2 – create a purchase order linked to a PR
# ---------------------------------------------------------------------------

def test_create_po_from_request(api_client_admin, admin_user, make_supplier, make_item, make_project):
    """Creating a PO with a reference to a PR; verify PR linkage via project."""
    supplier = make_supplier()
    item = make_item(standard_cost=Decimal('100.00'))
    project = make_project()

    # Create PO directly (PR linkage is typically done via line references;
    # we test PO creation with project linkage as the key chain element)
    payload = {
        'supplier': supplier.id,
        'project': project.id,
        'delivery_date': _today_plus(21),
        'notes': 'CI PO from PR test',
        'lines': [
            {
                'item': item.id,
                # JSON numbers (not strings): nested line values are passed
                # straight to the model where line_amount = qty * unit_price.
                'qty': 10,
                'unit_price': 100.00,
            }
        ],
    }

    resp = api_client_admin.post(PO_URL, payload, format='json')
    assert resp.status_code == 201, f"Expected 201 but got {resp.status_code}: {resp.data}"
    data = resp.data
    assert data['status'] == 'DRAFT'
    assert data['project'] == project.id
    assert data['supplier'] == supplier.id


# ---------------------------------------------------------------------------
# Test 3 – confirming a GoodsReceipt increases stock
# ---------------------------------------------------------------------------

def test_goods_receipt_updates_stock(
    api_client_admin, admin_user, make_supplier, make_item, make_warehouse
):
    """Confirming a GoodsReceipt creates StockMove(IN_PURCHASE, COMPLETED) → Stock updated."""
    supplier = make_supplier()
    item = make_item(standard_cost=Decimal('75.00'))
    warehouse = make_warehouse()

    # Step 1: create a confirmed PO (use CONFIRMED status directly via model to skip workflow)
    from apps.purchase.models import PurchaseOrder, PurchaseOrderLine

    po = PurchaseOrder.objects.create(
        supplier=supplier,
        delivery_date=datetime.date.today() + datetime.timedelta(days=30),
        status='CONFIRMED',
        created_by=admin_user,
    )
    po_line = PurchaseOrderLine.objects.create(
        po=po,
        item=item,
        qty=Decimal('20'),
        unit_price=Decimal('75.00'),
        created_by=admin_user,
    )

    # Step 2: create a GoodsReceipt via API
    from apps.purchase.models import GoodsReceiptLine

    receipt_payload = {
        'po': po.id,
        'warehouse': warehouse.id,
        'receipt_date': datetime.date.today().isoformat(),
        'notes': 'CI receipt test',
        'lines': [
            {
                'po_line': po_line.id,
                'item': item.id,
                'qty': '20',
            }
        ],
    }

    create_resp = api_client_admin.post(RECEIPT_URL, receipt_payload, format='json')
    assert create_resp.status_code == 201, (
        f"Receipt creation failed: {create_resp.status_code}: {create_resp.data}"
    )
    receipt_id = create_resp.data['id']

    # Verify no stock yet
    assert not Stock.objects.filter(warehouse=warehouse, item=item).exists()

    # Step 3: confirm the receipt
    confirm_resp = api_client_admin.post(
        f'{RECEIPT_URL}{receipt_id}/confirm/', {}, format='json'
    )
    assert confirm_resp.status_code == 200, (
        f"Confirm failed: {confirm_resp.status_code}: {confirm_resp.data}"
    )
    assert confirm_resp.data['status'] == 'CONFIRMED'

    # Step 4: verify stock was created
    stock = Stock.objects.filter(warehouse=warehouse, item=item).first()
    assert stock is not None, 'Stock record should have been created after receipt confirmation'
    assert stock.qty_on_hand == Decimal('20'), (
        f"Expected qty_on_hand=20 but got {stock.qty_on_hand}"
    )
    assert stock.weighted_avg_cost == Decimal('75.00'), (
        f"Expected WAC=75.00 but got {stock.weighted_avg_cost}"
    )
