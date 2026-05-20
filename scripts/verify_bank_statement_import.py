"""
Verify bank_statement import_excel after the header-detection fix.

Run inside the backend container:
    docker compose exec -T backend python - < scripts/verify_bank_statement_import.py
"""
import io
import os
import sys
import time
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

import openpyxl
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.finance.bank_statement_models import BankStatement

IMPORT_URL = '/api/finance/bank-statements/import_excel/'


def build_excel(header_row_index):
    """Build an in-memory xlsx whose header lives at the given 1-based row."""
    wb = openpyxl.Workbook()
    ws = wb.active

    for _ in range(header_row_index - 1):
        ws.append([''] * 14)

    ws.append([
        '凭证号', '对方账号', '交易时间', '借贷标志', '对方单位', '对方行号',
        '用途', '摘要', '附言', '回单个性化信息',
        '转入金额', '转出金额', '支付凭证种类', '余额',
    ])
    # Real business inflow.
    ws.append([
        'V001', '4000091111500819999', '2026-01-15 10:00:00', '贷',
        '上海测试客户有限公司', '102100099996', '货款',
        '货款收入', '', '', 50000.00, 0, '电汇', 1657000.00,
    ])
    # Fee row — should be skipped by is_internal_transaction (contains 手续费).
    ws.append([
        '000000000', '4000091111500819054', '2026-01-01 21:50:21', '借',
        '', '', '工行异地汇款手续费', '', '', '', 0, 15.00, '', 1657399.33,
    ])
    # Real business outflow.
    ws.append([
        'V002', '4000091111500818000', '2026-01-16 11:30:00', '借',
        '深圳测试供应商有限公司', '', '采购付款',
        '采购货款', '', '', 0, 30000.00, '电汇', 1627000.00,
    ])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()


def make_client():
    User = get_user_model()
    user = User.objects.filter(is_superuser=True).first() or User.objects.first()
    if not user:
        print('!! no user in DB to act as request.user')
        sys.exit(2)
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return client, user


def post_excel(client, file_bytes, label):
    buf = io.BytesIO(file_bytes)
    buf.name = f'{label}.xlsx'
    return client.post(
        IMPORT_URL,
        {'file': buf},
        format='multipart',
    )


def show(label, response):
    print(f'\n=== {label} ===')
    print(f'status_code = {response.status_code}')
    data = response.data if hasattr(response, 'data') else {}
    for k, v in data.items():
        if k == 'errors' and not v:
            continue
        print(f'  {k}: {v}')


def cleanup():
    BankStatement.objects.filter(
        voucher_no__in=['V001', 'V002'], is_deleted=False
    ).delete()
    # batch_no uses second-level timestamps; wait so the next import gets a new one
    time.sleep(1.1)


def main():
    client, user = make_client()
    print(f'authenticated as: {user.username} (id={user.id})')

    cleanup()
    print('\n--- Test 1: header at row 1 (matches the user-provided sample) ---')
    resp1 = post_excel(client, build_excel(1), 'header_row_1')
    show('header_row=1', resp1)
    assert resp1.status_code == 200, f'import should succeed; got {resp1.status_code}: {resp1.data}'
    assert resp1.data['header_row'] == 1, f"expected header_row=1, got {resp1.data.get('header_row')}"
    assert resp1.data['success_count'] == 2, f"expected 2 success, got {resp1.data['success_count']}"
    assert resp1.data['skipped_count'] == 1, f"expected 1 skipped, got {resp1.data['skipped_count']}"

    cleanup()
    print('\n--- Test 2: header at row 3 (bank prefix info) ---')
    resp2 = post_excel(client, build_excel(3), 'header_row_3')
    show('header_row=3', resp2)
    assert resp2.status_code == 200, f'import should succeed; got {resp2.status_code}: {resp2.data}'
    assert resp2.data['header_row'] == 3, f"expected header_row=3, got {resp2.data.get('header_row')}"
    assert resp2.data['success_count'] == 2

    cleanup()
    print('\n--- Test 3: garbage file (no recognizable header) ---')
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(['random', 'columns', 'no', 'match'])
    ws.append(['a', 'b', 'c', 'd'])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    resp3 = post_excel(client, buf.read(), 'garbage')
    show('garbage', resp3)
    assert resp3.status_code == 400, f'garbage should be rejected with 400; got {resp3.status_code}'
    assert '表头' in resp3.data.get('error', ''), f"expected header-failure message, got {resp3.data}"

    # Export round-trip
    print('\n--- Test 4: export_excel returns xlsx ---')
    # Re-import test 1 so there is data to export
    cleanup()
    resp_seed = post_excel(client, build_excel(1), 'seed_for_export')
    assert resp_seed.status_code == 200
    resp_exp = client.get('/api/finance/bank-statements/export_excel/')
    print(f'export status_code = {resp_exp.status_code}')
    print(f'export Content-Type = {resp_exp["Content-Type"]}')
    print(f'export Content-Disposition = {resp_exp.get("Content-Disposition", "")}')
    assert resp_exp.status_code == 200
    assert 'spreadsheetml.sheet' in resp_exp['Content-Type']
    # confirm the bytes are a valid xlsx (zip header PK\x03\x04)
    body = b''.join(resp_exp.streaming_content) if hasattr(resp_exp, 'streaming_content') else resp_exp.content
    assert body[:4] == b'PK\x03\x04', 'export body should be a valid xlsx (zip) file'
    print(f'export body size: {len(body)} bytes — valid xlsx signature OK')

    cleanup()
    print('\nALL VERIFICATIONS PASSED.')


if __name__ == '__main__':
    main()
