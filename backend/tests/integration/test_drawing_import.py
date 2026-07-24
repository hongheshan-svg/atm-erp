"""
Integration tests for project Drawing Excel import endpoint.

Endpoint: POST /api/projects/drawings/import_excel/

Regression focus: same root cause as the BOM import — non-string column
headers (numeric / date / NaN from merged cells or a shifted title row) used
to crash the `find_column` helper (`kw in col`) with an uncaught TypeError and
surface as HTTP 500. Headers are now normalised to strings, so those cases
must return a clean 4xx instead of 500. Also covers happy path and the
standard validation errors.

Note: unlike the BOM import (which rejects the whole batch with 400 on any
row error), the drawing import reports per-row errors inside a 200 response's
``errors`` array.
"""

import io

import openpyxl
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

pytestmark = pytest.mark.django_db

IMPORT_URL = '/api/projects/drawings/import_excel/'


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


def _upload(client, xlsx_bytes, project_id, filename='drawings.xlsx', **extra):
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
    # Header row is all numbers — before the fix, `'图纸号' in 1001` raised TypeError.
    xlsx = _make_xlsx({1: [1001, 2002, 3003], 2: ['A', 'B', 'C']})
    resp = _upload(api_client_admin, xlsx, project.id)

    assert resp.status_code != 500, resp.content
    # No 图纸号/图纸名称 column detected → view reports missing required columns.
    assert resp.status_code == 400
    assert '缺少必需列' in str(resp.json())


def test_nan_headers_from_merged_cells_do_not_500(api_client_admin, make_project):
    """A blank/merged header cell yields a NaN column name; must not 500."""
    project = make_project()
    # First header cell left blank (NaN after read_excel), no required cols present.
    xlsx = _make_xlsx({1: [None, '备注'], 2: ['X', 'note']})
    resp = _upload(api_client_admin, xlsx, project.id)

    assert resp.status_code != 500, resp.content
    assert resp.status_code == 400


def test_datetime_headers_do_not_500(api_client_admin, make_project):
    """A datetime header cell must be normalised to str, not crash."""
    import datetime

    project = make_project()
    xlsx = _make_xlsx({1: [datetime.datetime(2024, 1, 1), '备注'], 2: ['X', 'note']})
    resp = _upload(api_client_admin, xlsx, project.id)

    assert resp.status_code != 500, resp.content
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_valid_import_creates_drawing(api_client_admin, make_project):
    """A well-formed file creates one drawing (name + drawing_no are enough)."""
    project = make_project()
    xlsx = _make_xlsx({
        1: ['图纸号', '图纸名称', '版本', '文件类型'],
        2: ['DRW-TEST-001', '底座装配图', 'A1', 'PDF'],
    })
    resp = _upload(api_client_admin, xlsx, project.id)

    assert resp.status_code == 200, resp.content
    data = resp.json()
    assert data['created'] == 1
    assert project.drawings.filter(drawing_no='DRW-TEST-001', is_deleted=False).exists()


def test_valid_import_links_item_when_sku_matches(api_client_admin, make_project, make_item):
    """关联物料 column with a known SKU links the drawing to that item."""
    project = make_project()
    item = make_item()
    xlsx = _make_xlsx({
        1: ['图纸号', '图纸名称', '关联物料'],
        2: ['DRW-TEST-002', '定位板零件图', item.sku],
    })
    resp = _upload(api_client_admin, xlsx, project.id)

    assert resp.status_code == 200, resp.content
    assert resp.json()['created'] == 1
    drawing = project.drawings.get(drawing_no='DRW-TEST-002', is_deleted=False)
    assert drawing.item_id == item.id


# ---------------------------------------------------------------------------
# Standard validation errors
# ---------------------------------------------------------------------------

def test_missing_file_returns_400(api_client_admin, make_project):
    project = make_project()
    resp = api_client_admin.post(IMPORT_URL, {'project': project.id}, format='multipart')
    assert resp.status_code == 400
    assert '文件' in str(resp.json())


def test_missing_project_returns_400(api_client_admin):
    xlsx = _make_xlsx({1: ['图纸号', '图纸名称'], 2: ['DRW-X', 'n']})
    uploaded = SimpleUploadedFile(
        'drawings.xlsx', xlsx,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    resp = api_client_admin.post(IMPORT_URL, {'file': uploaded}, format='multipart')
    assert resp.status_code == 400
    assert '项目' in str(resp.json())


def test_missing_name_column_returns_400(api_client_admin, make_project):
    """图纸号 present but no 图纸名称/名称 column → 400 缺少必需列."""
    project = make_project()
    xlsx = _make_xlsx({1: ['图纸号', '备注'], 2: ['DRW-Y', 'note']})
    resp = _upload(api_client_admin, xlsx, project.id)
    assert resp.status_code == 400
    assert '缺少必需列' in str(resp.json())


def test_empty_name_row_reported_in_errors_not_500(api_client_admin, make_project):
    """A row whose 图纸名称 is blank is reported per-row (200 + errors), not a 500."""
    project = make_project()
    xlsx = _make_xlsx({
        1: ['图纸号', '图纸名称'],
        2: ['DRW-TEST-003', None],  # blank name
    })
    resp = _upload(api_client_admin, xlsx, project.id)

    assert resp.status_code != 500, resp.content
    assert resp.status_code == 200
    data = resp.json()
    assert data['created'] == 0
    assert any('图纸名称为空' in e.get('error', '') for e in data['errors'])
