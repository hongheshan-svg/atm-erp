import io
from concurrent.futures import ThreadPoolExecutor

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase
from openpyxl import Workbook

from apps.business.models import BankRecord, Payment
from apps.business.services import bank_import
from apps.core.models import AuditLog

from .test_commercial_chain import BusinessFixtures


def file(rows=None, name='bank.xlsx', missing=False, income='100.00'):
    book = Workbook()
    sheet = book.active
    rows = rows or [
        ['[HISTORYDETAIL]'],
        bank_import.ICBC,
        [
            '000000000',
            '001234567890',
            '2026-01-01 12:00:00',
            '贷',
            '' if missing else '客户',
            '',
            '货款',
            '',
            '',
            '业务发生账号:123456789012',
            income,
            '',
            '',
            '1000.00',
        ],
        [
            '000000000',
            '009876543210',
            '2026-01-02 12:00:00',
            '借',
            '员工',
            '',
            '备用金',
            '',
            '',
            '',
            '',
            '20.00',
            '',
            '980.00',
        ],
    ]
    for row in rows:
        sheet.append(row)
    stream = io.BytesIO()
    book.save(stream)
    return SimpleUploadedFile(name, stream.getvalue())


class BankImportTests(BusinessFixtures, TestCase):
    def setUp(self):
        self.setup_business()

    def preview(self, upload=None, role='finance', status=200):
        result = self.clients[role].post(
            '/api/business/bank-records/import-file/', {'file': upload or file()}, format='multipart'
        )
        self.assertEqual(result.status_code, status, result.data)
        return result.data

    def confirm(self, token, role='finance', status=200):
        return self.post(role, 'bank-records/import-confirm/', {'token': token}, status=status)

    def test_native_preview_commit_repeat_and_reexport(self):
        preview = self.preview()
        self.assertEqual(BankRecord.objects.count(), 0)
        self.assertEqual(preview['summary']['income'], '100.00')
        self.assertEqual(preview['summary']['expense'], '20.00')
        self.assertTrue(preview['can_import'])
        self.assertEqual(
            [column['label'] for column in preview['columns']],
            ['银行日期', '账户', '流水号 / 导入标识', '对方户名', '收入 / 支出', '说明'],
        )
        self.assertEqual(preview['row_count'], 2)
        self.assertEqual(preview['rows'][1]['data']['amount'], '-20.00')
        self.assertEqual(self.confirm(preview['token']), {'count': 2, 'skipped': 0})
        self.assertEqual(self.confirm(preview['token']), {'count': 2, 'skipped': 0})
        # New filename, preview and user still deduplicate by transaction, not batch nonce.
        another = self.preview(file(name='renamed.xlsx'), role='admin')
        self.assertEqual(self.confirm(another['token'], role='admin'), {'count': 0, 'skipped': 2})
        self.assertEqual(BankRecord.objects.count(), 2)
        self.assertEqual(Payment.objects.count(), 0)
        self.assertEqual(BankRecord.objects.first().source['original_reference'], '000000000')
        self.assertEqual(len(set(BankRecord.objects.values_list('reference', flat=True))), 2)

    def test_missing_name_preserved_and_review_required(self):
        preview = self.preview(file(missing=True))
        self.confirm(preview['token'])
        bank = BankRecord.objects.get(needs_review=True)
        self.assertEqual(bank.source['counterparty'], '')
        from apps.business.services.banking import check_review
        from apps.core.api import Conflict

        with self.assertRaises(Conflict):
            check_review(bank)
        self.post('finance', f'bank-records/{bank.pk}/review/', {'counterparty': '核实客户', 'reason': '银行回单核对'})
        bank.refresh_from_db()
        self.assertFalse(bank.needs_review)
        self.assertEqual(bank.source['counterparty'], '')
        self.assertTrue(AuditLog.objects.filter(operation='bank.review').exists())
        self.confirm(self.preview(file(missing=True))['token'])
        bank.refresh_from_db()
        self.assertEqual(bank.counterparty, '核实客户')
        self.assertFalse(bank.needs_review)

    def test_legacy_import_is_enriched_without_duplicate_money(self):
        preview = self.preview()
        record = preview['rows'][0]
        self.post('finance', 'bank-records/', {**record['data'], 'reference': record['legacy_reference']}, status=201)
        self.assertEqual(self.confirm(preview['token']), {'count': 1, 'skipped': 1})
        self.assertEqual(BankRecord.objects.count(), 2)
        self.assertEqual(BankRecord.objects.filter(import_fingerprint__isnull=True).count(), 0)

    def test_permissions_token_binding_and_tamper(self):
        self.preview(role='member', status=403)
        preview = self.preview()
        self.confirm(preview['token'], role='admin', status=400)
        self.confirm(preview['token'] + 'x', status=400)
        self.confirm(preview['token'], role='member', status=403)
        self.assertEqual(BankRecord.objects.count(), 0)

    def test_bad_money_formula_and_file_rejected(self):
        self.assertFalse(self.preview(file(income='100.001'))['can_import'])
        self.preview(file(income='=10+20'), status=400)
        self.preview(SimpleUploadedFile('bad.xls', b'not excel'), status=400)
        self.assertEqual(BankRecord.objects.count(), 0)

    def test_huaxia_header_mismatch_blocks_import(self):
        rows = [
            ['账号：', '123456789012'],
            ['币种：', '人民币'],
            [],
            [],
            [],
            ['收入总金额：', '101', '收入总笔数：', '1'],
            ['支出总金额：', '0', '支出总笔数：', '0'],
            bank_import.HXB,
            ['1', '2026-01-01', '12:00:00', '', '100', '100', '001234567890', '客户', '银行', '000123', '货款'],
        ]
        preview = self.preview(file(rows))
        self.assertFalse(preview['can_import'])
        self.assertIsNone(preview['token'])
        rows[5][1] = '100'
        valid = self.preview(file(rows))
        self.assertTrue(valid['can_import'])
        self.assertEqual(valid['rows'][0]['source']['original_reference'], '000123')

    def test_conflict_at_confirmation_rolls_back_whole_batch(self):
        preview = self.preview()
        last = preview['rows'][1]
        self.post('finance', 'bank-records/', {**last['data'], 'amount': '-99'}, status=201)
        self.confirm(preview['token'], status=400)
        self.assertEqual(BankRecord.objects.count(), 1)
        self.assertEqual(Payment.objects.count(), 0)

    def test_matching_pending_name_rejected_before_payment(self):
        project = self.active_project()
        entry = project.entries.get(kind='receivable')
        self.confirm(self.preview(file(missing=True))['token'])
        bank = BankRecord.objects.get(needs_review=True)
        self.post(
            'finance',
            f'bank-records/{bank.pk}/allocate/',
            {'entry': entry.pk, 'amount': '100', 'reason': '试图认领'},
            status=409,
        )
        self.assertEqual(Payment.objects.count(), 0)


class BankImportConcurrencyTests(BusinessFixtures, TransactionTestCase):
    def setUp(self):
        self.setup_business()

    def test_two_users_import_same_transactions_concurrently(self):
        jobs = [
            (self.users[role], bank_import.preview(self.users[role], file())['token']) for role in ['admin', 'finance']
        ]

        def run(job):
            close_old_connections()
            try:
                return bank_import.confirm(*job)
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(run, jobs))
        self.assertEqual(sum(result['count'] for result in results), 2)
        self.assertEqual(sum(result['skipped'] for result in results), 2)
        self.assertEqual(BankRecord.objects.count(), 2)
