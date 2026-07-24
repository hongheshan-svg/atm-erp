"""
Integration tests for project BOM Excel import endpoint.

Endpoint: POST /api/projects/bom/import_excel/

Regression focus: non-string column headers (numeric / date / NaN from merged
cells or a shifted title row) used to crash the view with an uncaught
TypeError (`argument of type 'int' is not iterable`) and surface as HTTP 500.
The view now normalises headers to strings, so those cases must return a clean
4xx instead of 500. Also covers happy path and the standard validation errors.
"""

import io

import openpyxl
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

pytestmark = pytest.mark.django_db

IMPORT_URL = '/api/projects/bom/import_excel/'

# The columns the view treats as required for a valid data row.
REQUIRED_HEADERS = ['物料编码', '数量', '单位', '需求日期', '申请人']


def _make_xlsx(rows_by_row: dict[int, list]) -> bytes:
    """Build an in-memory xlsx workbook.

    rows_by_row maps 1-based row numbers to lists of cell values.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    for row_num, values in rows_by_row.items():
        for col_num, value in enumerate(values, start=1):
            ws.cell(row=row_num, column=col_num, value=value)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _upload(client, xlsx_bytes, project_id, filename='bom.xlsx', **extra):
    uploaded = SimpleUploadedFile(
        filename,
        xlsx_bytes,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    payload = {'file': uploaded, 'project': project_id}
    payload.update(extra)
    return client.post(IMPORT_URL, payload, format='multipart')


# ---------------------------------------------------------------------------
# Regression: non-string headers must not 500
# ---------------------------------------------------------------------------

def test_numeric_headers_do_not_500(api_client_admin, make_project):
    """Numeric column headers (shifted/no header row) must be a clean 4xx, not 500."""
    project = make_project()
    # Header row is all numbers — before the fix, `'物料编码' in 1001` raised TypeError.
    xlsx = _make_xlsx({1: [1001, 2002, 3003], 2: ['A', 5, '个']})
    resp = _upload(api_client_admin, xlsx, project.id)

    assert resp.status_code != 500, resp.content
    # No SKU column can be detected → view reports missing 物料编码 column.
    assert resp.status_code == 400
    assert '物料编码' in str(resp.json())


def test_nan_headers_from_merged_cells_do_not_500(api_client_admin, make_project):
    """A blank/merged header cell yields a NaN column name; must not 500."""
    project = make_project()
    # First header cell left blank (NaN after read_excel), rest missing required cols.
    xlsx = _make_xlsx({1: [None, '备注'], 2: ['X', 'note']})
    resp = _upload(api_client_admin, xlsx, project.id)

    assert resp.status_code != 500, resp.content
    assert resp.status_code == 400


def test_datetime_headers_do_not_500(api_client_admin, make_project):
    """A datetime header cell must be normalised to str, not crash."""
    import datetime

    project = make_project()
    xlsx = _make_xlsx({1: [datetime.datetime(2024, 1, 1), '数量'], 2: ['X', 1]})
    resp = _upload(api_client_admin, xlsx, project.id)

    assert resp.status_code != 500, resp.content
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_valid_import_creates_bom(api_client_admin, make_project, make_item):
    """A well-formed file with an existing SKU imports one BOM row."""
    project = make_project()
    item = make_item()
    xlsx = _make_xlsx({
        1: ['物料编码', '数量', '单位', '需求日期', '申请人'],
        2: [item.sku, 3, '个', '2026-08-01', 'ci_admin'],
    })
    resp = _upload(api_client_admin, xlsx, project.id)

    assert resp.status_code == 200, resp.content
    data = resp.json()
    assert data['created'] == 1
    assert project.bom_items.filter(item=item, is_deleted=False).exists()


# ---------------------------------------------------------------------------
# Standard validation errors
# ---------------------------------------------------------------------------

def test_missing_file_returns_400(api_client_admin, make_project):
    project = make_project()
    resp = api_client_admin.post(IMPORT_URL, {'project': project.id}, format='multipart')
    assert resp.status_code == 400
    assert '文件' in str(resp.json())


def test_missing_project_returns_400(api_client_admin):
    xlsx = _make_xlsx({1: ['物料编码', '数量'], 2: ['A', 1]})
    uploaded = SimpleUploadedFile(
        'bom.xlsx', xlsx,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    resp = api_client_admin.post(IMPORT_URL, {'file': uploaded}, format='multipart')
    assert resp.status_code == 400
    assert '项目' in str(resp.json())


def test_missing_qty_column_returns_400(api_client_admin, make_project):
    """SKU column present but no quantity column → 400 with clear message."""
    project = make_project()
    xlsx = _make_xlsx({1: ['物料编码', '单位'], 2: ['A', '个']})
    resp = _upload(api_client_admin, xlsx, project.id)
    assert resp.status_code == 400
    assert '数量' in str(resp.json())


def test_unknown_sku_without_auto_create_reports_error(api_client_admin, make_project):
    """A SKU not in item master (auto_create off) is rejected, not a 500."""
    project = make_project()
    xlsx = _make_xlsx({
        1: ['物料编码', '数量', '单位', '需求日期', '申请人'],
        2: ['NOPE-SKU-9999', 1, '个', '2026-08-01', 'ci_admin'],
    })
    resp = _upload(api_client_admin, xlsx, project.id)

    assert resp.status_code != 500, resp.content
    # Precheck collects the error and rejects the whole import with 400.
    assert resp.status_code == 400
    body = str(resp.json())
    assert 'NOPE-SKU-9999' in body or '不存在' in body
