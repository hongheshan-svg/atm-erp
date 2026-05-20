"""
Integration tests for the sales flow.

Covers:
- Creating a SalesQuotation via API → status DRAFT
- Confirming a SalesOrder via API → status CONFIRMED
- Verifying SalesOrder ↔ Project FK linkage
"""

import datetime

import pytest

pytestmark = pytest.mark.django_db

QUOTATIONS_URL = '/api/sales/quotations/'
ORDERS_URL = '/api/sales/orders/'


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _today_plus(days: int) -> str:
    return (datetime.date.today() + datetime.timedelta(days=days)).isoformat()


# ---------------------------------------------------------------------------
# Test 1 – create a quotation via API
# ---------------------------------------------------------------------------

def test_create_quotation_api(api_client_admin, make_customer):
    """POST /api/sales/quotations/ creates a quotation in DRAFT status."""
    customer = make_customer()

    payload = {
        'customer': customer.id,
        'valid_until': _today_plus(30),
        'tax_rate': 13,
        'notes': 'CI test quotation',
    }

    resp = api_client_admin.post(QUOTATIONS_URL, payload, format='json')
    assert resp.status_code == 201, f"Expected 201 but got {resp.status_code}: {resp.data}"
    data = resp.data
    assert data['status'] == 'DRAFT'
    assert data['customer'] == customer.id
    assert data['id']


# ---------------------------------------------------------------------------
# Test 2 – confirm a sales order
# ---------------------------------------------------------------------------

def test_confirm_sales_order(api_client_admin, make_customer):
    """POST /api/sales/orders/{id}/confirm/ changes status to CONFIRMED."""
    customer = make_customer()

    # Create SO in DRAFT state via API
    payload = {
        'customer': customer.id,
        'delivery_date': _today_plus(60),
        'tax_rate': 13,
        'payment_terms': 'FULL_PREPAY',
    }
    create_resp = api_client_admin.post(ORDERS_URL, payload, format='json')
    assert create_resp.status_code == 201, (
        f"Failed to create SO: {create_resp.status_code}: {create_resp.data}"
    )
    so_id = create_resp.data['id']
    assert create_resp.data['status'] == 'DRAFT'

    # Confirm the SO
    confirm_resp = api_client_admin.post(f'{ORDERS_URL}{so_id}/confirm/', {}, format='json')
    assert confirm_resp.status_code == 200, (
        f"Confirm failed: {confirm_resp.status_code}: {confirm_resp.data}"
    )
    assert confirm_resp.data['status'] == 'CONFIRMED'


# ---------------------------------------------------------------------------
# Test 3 – sales order links to project
# ---------------------------------------------------------------------------

def test_sales_order_links_project(api_client_admin, make_customer, make_project):
    """Creating a SO with a project FK preserves the linkage."""
    customer = make_customer()
    project = make_project(customer=customer)

    payload = {
        'customer': customer.id,
        'project': project.id,
        'delivery_date': _today_plus(90),
        'tax_rate': 13,
        'payment_terms': 'NET30',
    }
    resp = api_client_admin.post(ORDERS_URL, payload, format='json')
    assert resp.status_code == 201, f"Expected 201 but got {resp.status_code}: {resp.data}"
    data = resp.data
    assert data['project'] == project.id

    # Verify via GET
    get_resp = api_client_admin.get(f"{ORDERS_URL}{data['id']}/")
    assert get_resp.status_code == 200
    assert get_resp.data['project'] == project.id
