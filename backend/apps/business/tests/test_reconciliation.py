import uuid

from django.test import TestCase

from apps.business.models import BankMatch, BankRecord, Entry, Payment, Reconciliation
from apps.business.services import banking, finance
from apps.core.api import Conflict

from .test_commercial_chain import TODAY, BusinessFixtures


class ReconciliationTests(BusinessFixtures, TestCase):
    def setUp(self):
        self.setup_business()
        self.project = self.active_project()

    def request(self, role, path, data, status=200, key=None):
        response = self.clients[role].post(
            '/api/business/' + path, data, format='json', HTTP_IDEMPOTENCY_KEY=key or str(uuid.uuid4())
        )
        self.assertEqual(response.status_code, status, response.data)
        return response.data

    def purchase_entry(self, receive=True):
        purchase = self.purchase(self.project)
        if receive:
            self.post(
                'warehouse',
                f'purchases/{purchase.pk}/receive/',
                {'lines': [{'line': purchase.lines.get().pk, 'quantity': '5'}], 'reason': '收货核对'},
            )
        return purchase.entry

    def statement(self, entry, amount='500', kind='settlement', counterparty=None, confirm=True):
        result = self.request(
            'finance',
            'reconciliations/',
            {
                'entry': entry.pk,
                'kind': kind,
                'approved_amount': amount,
                'counterparty_balance': counterparty if counterparty is not None else str(finance.balance(entry)),
                'basis': 'HT-001 合同约定预付额度',
                'reason': '双方核对',
            },
            201,
        )
        if confirm:
            self.request(
                'manager' if kind == 'prepayment' else 'finance',
                f'reconciliations/{result["id"]}/confirm/',
                {'reason': '逐项核准'},
            )
        return result['id']

    def pay(self, entry, amount='500', statement=None, refund=False, status=200, key=None):
        return self.request(
            'finance',
            f'entries/{entry.pk}/{"refund" if refund else "pay"}/',
            {
                'amount': amount,
                'date': TODAY,
                'reason': '实际收付',
                **({'reconciliation': statement} if statement else {}),
            },
            status,
            key,
        )

    def bank(self, amount='500', project=True):
        return self.request(
            'finance',
            'bank-records/',
            {
                'amount': amount,
                'date': TODAY,
                'account': 'BANK-A',
                'reference': str(uuid.uuid4()),
                'counterparty': '客户银行户名',
                'reason': '银行实际记录',
                **({'project': self.project.pk} if project else {}),
            },
            201,
        )['id']

    def test_gate_difference_partial_payments_and_replay(self):
        entry = self.purchase_entry()
        self.pay(entry, status=409)
        bad = self.statement(entry, counterparty='501', confirm=False)
        self.request('finance', f'reconciliations/{bad}/confirm/', {'reason': '有差异'}, 409)
        self.request('finance', f'reconciliations/{bad}/void/', {'reason': '更正对方账单'})
        statement = self.statement(entry)
        key = str(uuid.uuid4())
        first = self.pay(entry, '300', statement, key=key)
        self.assertEqual(self.pay(entry, '300', statement, key=key), first)
        self.pay(entry, '250', statement, status=409)
        self.pay(entry, '200', statement)
        self.assertEqual(entry.payments.count(), 2)
        detail = self.clients['finance'].get(f'/api/business/reconciliations/{statement}/').data
        self.assertTrue(detail['valid'])
        self.assertEqual(detail['remaining_amount'], '0.00')
        self.assertEqual(finance.balance(entry), 0)

    def test_prepayment_requires_contract_basis_and_manager_confirmation(self):
        entry = self.purchase_entry(receive=False)
        ordinary = self.statement(entry, confirm=False)
        self.request('finance', f'reconciliations/{ordinary}/confirm/', {'reason': '未收货'}, 409)
        self.request(
            'finance',
            'reconciliations/',
            {
                'entry': entry.pk,
                'kind': 'prepayment',
                'approved_amount': '200',
                'counterparty_balance': '500',
                'reason': '缺条款',
            },
            400,
        )
        statement = self.statement(entry, amount='200', kind='prepayment', confirm=False)
        self.request('finance', f'reconciliations/{statement}/confirm/', {'reason': '财务不能核准预付款'}, 403)
        self.request('manager', f'reconciliations/{statement}/confirm/', {'reason': '合同约定预付40%'})
        self.pay(entry, '201', statement, status=409)
        self.pay(entry, '200', statement)

    def test_receipt_change_invalidates_confirmed_authorization(self):
        entry = self.purchase_entry(receive=False)
        statement = self.statement(entry, kind='prepayment')
        purchase = entry.purchase
        self.post(
            'warehouse',
            f'purchases/{purchase.pk}/receive/',
            {'lines': [{'line': purchase.lines.get().pk, 'quantity': '1'}], 'reason': '新增收货'},
        )
        self.pay(entry, '100', statement, status=409)
        self.assertFalse(Payment.objects.exists())

    def test_refund_requires_current_reconciliation_and_keeps_original(self):
        entry = self.purchase_entry(receive=False)
        self.pay(entry, statement=self.statement(entry, kind='prepayment'))
        self.post('purchaser', f'purchases/{entry.purchase_id}/cancel-remainder/', {'reason': '停止采购'})
        entry.refresh_from_db()
        self.pay(entry, '100', refund=True, status=409)
        statement = self.statement(entry, kind='refund')
        self.pay(entry, '100', statement, refund=True)
        self.pay(entry, '400', statement, refund=True)
        self.assertEqual(list(entry.payments.order_by('id').values_list('amount', flat=True)), [500, -100, -400])
        self.assertEqual(finance.balance(entry), 0)

    def test_bank_allocation_is_partial_idempotent_and_does_not_double_cash(self):
        entry = self.project.entries.get(kind='receivable')
        bank = self.bank(project=False)
        payload = {'entry': entry.pk, 'amount': '200', 'reason': '认领合同款'}
        key = str(uuid.uuid4())
        first = self.request('finance', f'bank-records/{bank}/allocate/', payload, key=key)
        self.assertEqual(self.request('finance', f'bank-records/{bank}/allocate/', payload, key=key), first)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(BankMatch.objects.count(), 1)
        self.assertEqual(banking.remaining(BankRecord.objects.get(pk=bank)), 300)
        self.assertEqual(finance.balance(entry), 9800)
        self.request('finance', f'bank-records/{bank}/allocate/', {**payload, 'amount': '301'}, 409)
        self.assertEqual(Payment.objects.count(), 1)
        with self.assertRaises(Conflict):
            banking.check_close(self.project)
        self.request('finance', f'bank-records/{bank}/allocate/', {**payload, 'amount': '300'})
        self.assertEqual(banking.remaining(BankRecord.objects.get(pk=bank)), 0)

    def test_bank_match_does_not_create_payment_and_unmatch_preserves_history(self):
        entry = self.project.entries.get(kind='receivable')
        bank_id = self.bank()
        bank = BankRecord.objects.get(pk=bank_id)
        payment = self.request(
            'finance',
            f'entries/{entry.pk}/pay/',
            {
                'amount': '500',
                'date': TODAY,
                'reason': '先登记到账',
                'method': 'bank',
                'account': bank.account,
                'reference': bank.reference,
            },
        )['id']
        match = self.request('finance', f'bank-records/{bank_id}/match/', {'payment': payment, 'reason': '核对银行'})[
            'id'
        ]
        self.assertEqual(Payment.objects.count(), 1)
        self.request('finance', f'bank-records/{bank_id}/match/', {'payment': payment, 'reason': '重复匹配'}, 409)
        self.request('finance', f'payments/{payment}/reverse/', {'date': TODAY, 'reason': '先解除匹配'}, 409)
        self.request('finance', f'bank-records/{bank_id}/unmatch/', {'match': match, 'reason': '认领项目有误'})
        self.request('finance', f'payments/{payment}/reverse/', {'date': TODAY, 'reason': '纠错原收款'})
        self.assertEqual(BankMatch.objects.count(), 2)
        self.assertEqual(Payment.objects.count(), 2)
        self.assertEqual(banking.remaining(bank), 500)
        self.assertEqual(finance.balance(entry), 10000)

    def test_bank_direction_account_scope_and_permissions(self):
        bank = self.bank('-500')
        entry = self.project.entries.get(kind='receivable')
        self.request(
            'finance',
            f'bank-records/{bank}/allocate/',
            {'entry': entry.pk, 'amount': '100', 'reason': '支出不能认领成收入'},
            409,
        )
        for role in ['manager', 'sales_manager', 'purchaser', 'warehouse', 'member']:
            self.assertEqual(self.clients[role].get('/api/business/bank-records/').status_code, 403)
        for role in ['sales_manager', 'purchaser', 'warehouse', 'member']:
            self.assertEqual(self.clients[role].get('/api/business/reconciliations/').status_code, 403)
        other = self.active_project()
        other_entry = other.entries.get()
        self.request(
            'finance',
            f'bank-records/{self.bank()}/allocate/',
            {'entry': other_entry.pk, 'amount': '100', 'reason': '错项目'},
            409,
        )
        self.assertFalse(Payment.objects.exists())

    def test_changed_role_cannot_replay_payment_or_confirmation(self):
        entry = self.purchase_entry()
        statement = self.statement(entry)
        key = str(uuid.uuid4())
        self.pay(entry, statement=statement, key=key)
        self.users['finance'].role = 'member'
        self.users['finance'].save()
        self.pay(entry, statement=statement, key=key, status=403)

    def test_customer_receipt_is_not_blocked_by_unconfirmed_statement(self):
        entry = self.project.entries.get()
        self.statement(entry, amount='100', counterparty='9999', confirm=False)
        self.pay(entry, '100')
        self.assertEqual(finance.balance(entry), 9900)
        with self.assertRaises(Conflict):
            banking.check_close(self.project)

    def test_void_bank_and_reenter_corrected_record_preserves_original(self):
        bank = BankRecord.objects.get(pk=self.bank())
        payload = {
            'amount': '450',
            'date': TODAY,
            'account': bank.account,
            'reference': bank.reference,
            'counterparty': bank.counterparty,
            'reason': '金额录入更正',
        }
        self.request('finance', 'bank-records/', payload, 400)
        self.request('finance', f'bank-records/{bank.pk}/void/', {'reason': '录入金额有误'})
        self.request('finance', 'bank-records/', payload, 201)
        self.assertEqual(BankRecord.objects.count(), 2)
        self.assertEqual(Reconciliation.objects.count(), 0)

    def test_unclaimed_overpayment_can_be_returned_without_fake_business_entry(self):
        incoming, outgoing = self.bank('500'), self.bank('-100')
        entry = self.project.entries.get(kind='receivable')
        self.request(
            'finance',
            f'bank-records/{incoming}/allocate/',
            {'entry': entry.pk, 'amount': '400', 'reason': '实际合同回款'},
        )
        payload = {'returned': outgoing, 'amount': '100', 'reason': '多汇部分实际退回'}
        key = str(uuid.uuid4())
        result = self.request('finance', f'bank-records/{incoming}/return-unclaimed/', payload, key=key)
        self.assertEqual(
            self.request('finance', f'bank-records/{incoming}/return-unclaimed/', payload, key=key), result
        )
        for bank_id in [incoming, outgoing]:
            detail = self.clients['finance'].get(f'/api/business/bank-records/{bank_id}/').data
            self.assertEqual(detail['remaining_amount'], '0.00')
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(Entry.objects.count(), 1)
        self.assertEqual(finance.balance(entry), 9600)
        self.request('finance', f'bank-records/{incoming}/return-unclaimed/', payload, 409)
        self.request(
            'finance', f'bank-records/{incoming}/reverse-return/', {'offset': result['id'], 'reason': '关联错了'}
        )
        self.assertEqual(banking.remaining(BankRecord.objects.get(pk=incoming)), 100)
        self.assertEqual(banking.remaining(BankRecord.objects.get(pk=outgoing)), 100)
        self.assertEqual(Payment.objects.count(), 1)

    def test_payment_import_cannot_bypass_gate_or_consume_limit_during_preview(self):
        import csv
        import io

        from django.core.files.uploadedfile import SimpleUploadedFile

        from apps.business.services.transfers import SCHEMAS

        entry = self.purchase_entry()

        def preview(statement=''):
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow([label for label, _ in SCHEMAS['payments'][1]])
            writer.writerow([entry.pk, '500', TODAY, '批量付款', '', '', '', '', statement])
            return self.clients['finance'].post(
                '/api/business/payments/import-file/',
                {'file': SimpleUploadedFile('payments.csv', output.getvalue().encode())},
                format='multipart',
            )

        denied = preview()
        self.assertEqual(denied.status_code, 200)
        self.assertFalse(denied.data['can_import'])
        statement = self.statement(entry)
        valid = preview(statement)
        self.assertTrue(valid.data['can_import'], valid.data)
        self.assertFalse(Payment.objects.exists())
        self.request('finance', 'payments/import-confirm/', {'token': valid.data['token']})
        self.assertEqual(Payment.objects.get().reconciliation_id, statement)
