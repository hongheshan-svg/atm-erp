"""Bank evidence and business payments must consume the same actual funds exactly once."""

import io
import uuid

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from openpyxl import load_workbook

from apps.business.models import BankMatch, BankOffset, BankRecord, Entry, Payment
from apps.business.services import banking, finance
from apps.core.models import ActionReceipt

from .test_bank_import import file, huaxia
from .test_commercial_chain import TODAY, BusinessFixtures


class BankIdentityTests(BusinessFixtures, TestCase):
    def setUp(self):
        self.setup_business()
        self.project = self.active_project(amount='1000')
        self.entry = self.project.entries.get()

    def bank(self, amount, reference, account='A'):
        data = self.post(
            'finance',
            'bank-records/',
            {
                'amount': amount,
                'reference': reference,
                'account': account,
                'date': TODAY,
                'counterparty': '客户',
                'reason': '银行实际记录',
            },
            status=201,
        )
        return BankRecord.objects.get(pk=data['id'])

    def pay(self, reference, amount='100', account='A', date=TODAY, entry=None, status=200):
        entry = entry or self.entry
        data = self.post(
            'finance',
            f'entries/{entry.pk}/pay/',
            {
                'amount': amount,
                'reference': reference,
                'account': account,
                'date': date,
                'method': 'bank',
                'reason': '手工登记实际收付款',
            },
            status=status,
        )
        return Payment.objects.get(pk=data['id']) if status == 200 else data

    def imported(self, upload=None):
        response = self.clients['finance'].post(
            '/api/business/bank-records/import-file/', {'file': upload or huaxia()}, format='multipart'
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data['can_import'], response.data)
        self.post('finance', 'bank-records/import-confirm/', {'token': response.data['token']})
        return BankRecord.objects.order_by('-pk').first()

    def match(self, bank, payment, status=200):
        return self.post(
            'finance',
            f'bank-records/{bank.pk}/match/',
            {'payment': payment.pk, 'reason': '核对实际收付'},
            status=status,
        )

    def offset(self, source, returned, amount='100', status=200):
        return self.post(
            'finance',
            f'bank-records/{source.pk}/return-unclaimed/',
            {'returned': returned.pk, 'amount': amount, 'reason': '退回未使用部分'},
            status=status,
        )

    def test_huaxia_import_matches_raw_manual_reference_without_second_payment(self):
        payment = self.pay('000123', account='123456789012', date='2026-01-01')
        bank = self.imported()
        self.assertEqual(bank.reference, '2026-01-01:000123')
        receipts = ActionReceipt.objects.count()
        self.post(
            'finance',
            f'bank-records/{bank.pk}/allocate/',
            {'entry': self.entry.pk, 'amount': '100', 'reason': '重复认领'},
            status=409,
        )
        self.assertEqual(ActionReceipt.objects.count(), receipts)
        self.assertEqual(Payment.objects.count(), 1)
        self.match(bank, payment)
        self.assertEqual(banking.remaining(bank), 0)
        self.assertEqual(finance.balance(self.entry), 900)
        payment.refresh_from_db()
        self.assertEqual(payment.reference, '000123')

    def test_import_first_checks_raw_and_prefixed_manual_aliases_against_same_bank(self):
        bank = self.imported()
        payment = self.pay('000123', account=bank.account, date='2026-01-01')
        other = self.active_project().entries.get()
        self.pay(bank.reference, account=bank.account, date='2026-01-01', entry=other, status=409)
        self.pay('000123', account=bank.account, date='2026-01-01', status=409)
        self.match(bank, payment)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(finance.balance(other), 10000)

    def test_huaxia_core_reference_is_scoped_to_date_and_account(self):
        first = self.imported()
        first_payment = self.pay('000123', account=first.account, date='2026-01-01')
        # The same core number may be reused on another date, even before that day's bank import.
        second_payment = self.pay('000123', account=first.account, date='2026-01-02')
        book = load_workbook(huaxia())
        book.active['B9'] = '2026-01-02'
        stream = io.BytesIO()
        book.save(stream)
        book.close()
        second = self.imported(SimpleUploadedFile('另一天.xlsx', stream.getvalue()))
        self.match(first, second_payment, status=409)
        self.match(second, first_payment, status=409)
        self.match(first, first_payment)
        self.match(second, second_payment)
        other_account = self.pay('000123', account='其他账户', date='2026-01-01')
        self.match(first, other_account, status=409)
        self.assertEqual(BankMatch.objects.count(), 2)
        self.assertEqual(finance.balance(self.entry), 700)

    def test_prefixed_bank_reference_cannot_be_recorded_with_another_date(self):
        bank = self.imported()
        self.pay(bank.reference, account=bank.account, date='2026-01-02', status=409)
        self.assertFalse(Payment.objects.exists())

    def test_icbc_repeated_voucher_is_not_treated_as_unique_transaction_alias(self):
        self.pay('000000000', account='123456789012', date='2026-01-01')
        self.imported(file())
        bank = BankRecord.objects.get(amount__gt=0)
        self.post(
            'finance',
            f'bank-records/{bank.pk}/allocate/',
            {'entry': self.entry.pk, 'amount': '100', 'reason': '另一笔有独立银行凭据的到账'},
        )
        self.assertEqual(banking.remaining(bank), 0)

    def test_unclaimed_return_rejects_manually_registered_source_without_partial_writes(self):
        source, returned = self.bank('100', 'IN'), self.bank('-100', 'OUT')
        payment = self.pay('IN')
        receipts = ActionReceipt.objects.count()
        self.offset(source, returned, status=409)
        self.assertEqual(ActionReceipt.objects.count(), receipts)
        self.assertFalse(BankOffset.objects.exists())
        self.assertEqual(banking.remaining(source), 100)
        self.assertEqual(banking.remaining(returned), 100)
        self.assertEqual(finance.balance(self.entry), 900)
        self.match(source, payment)

    def test_unclaimed_return_can_use_unreserved_remainder_and_then_match_manual_payment(self):
        source, returned = self.bank('300', 'IN'), self.bank('-200', 'OUT')
        payment = self.pay('IN')
        self.offset(source, returned, '200')
        self.match(source, payment)
        self.assertEqual(banking.remaining(source), 0)
        self.assertEqual(banking.remaining(returned), 0)
        self.assertEqual(Payment.objects.count(), 1)

    def test_unclaimed_return_also_respects_manual_outgoing_payments(self):
        source, returned = self.bank('200', 'IN'), self.bank('-200', 'OUT')
        expense = self.post(
            'finance',
            'entries/expense/',
            {'project': self.project.pk, 'title': '费用', 'amount': '100', 'due_date': TODAY},
            status=201,
        )
        payment = self.pay('OUT', entry=Entry.objects.get(pk=expense['id']))
        self.offset(source, returned, '200', status=409)
        self.offset(source, returned, '100')
        self.match(returned, payment)
        self.assertEqual(banking.remaining(source), 100)
        self.assertEqual(banking.remaining(returned), 0)

    def test_huaxia_aliases_are_checked_before_unclaimed_return(self):
        self.pay('000123', account='123456789012', date='2026-01-01')
        source = self.imported()
        returned = self.bank('-100', 'OUT', account=source.account)
        self.offset(source, returned, status=409)
        self.assertFalse(BankOffset.objects.exists())

    def test_reversal_releases_reservation_and_return_replay_keeps_one_offset(self):
        source, returned = self.bank('100', 'IN'), self.bank('-100', 'OUT')
        payment = self.pay('IN')
        self.post('finance', f'payments/{payment.pk}/reverse/', {'date': TODAY, 'reason': '原登记有误'})
        key = str(uuid.uuid4())
        data = {'returned': returned.pk, 'amount': '100', 'reason': '退款'}
        first = self.post('finance', f'bank-records/{source.pk}/return-unclaimed/', data, key=key)
        self.assertEqual(self.post('finance', f'bank-records/{source.pk}/return-unclaimed/', data, key=key), first)
        self.assertEqual(BankOffset.objects.count(), 1)
        self.assertEqual(finance.balance(self.entry), 1000)

    def test_matching_unidentified_payment_cannot_consume_other_manual_reservation(self):
        source = self.bank('100', 'IN')
        identified = self.pay('IN')
        unidentified = self.pay('')
        self.match(source, unidentified, status=409)
        self.match(source, identified)
        self.assertEqual(BankMatch.objects.count(), 1)
