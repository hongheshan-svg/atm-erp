from decimal import Decimal
from django.test import TestCase, override_settings
from apps.finance.payable_models import PayableItem
from apps.finance.models import Payment
from apps.finance.payable_adapters import PayableSource, register_source, PAYABLE_SOURCES


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class PayableItemModelTest(TestCase):
    def test_remaining_and_recalc_status(self):
        item = PayableItem.objects.create(
            source_type='ap', source_id=1, source_no='AP001',
            category='采购', payee_name='供应商A',
            amount_due=Decimal('1000.00'),
        )
        self.assertEqual(item.status, PayableItem.STATUS_PENDING)
        self.assertEqual(item.remaining, Decimal('1000.00'))

        item.amount_paid = Decimal('400.00')
        item.recalc_status()
        self.assertEqual(item.status, PayableItem.STATUS_PARTIAL)

        item.amount_paid = Decimal('1000.00')
        item.recalc_status()
        self.assertEqual(item.status, PayableItem.STATUS_PAID)

    def test_unique_source(self):
        PayableItem.objects.create(source_type='ap', source_id=1, source_no='AP001',
                                   category='采购', payee_name='A', amount_due=Decimal('1'))
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            PayableItem.objects.create(source_type='ap', source_id=1, source_no='AP001',
                                       category='采购', payee_name='A', amount_due=Decimal('1'))


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class PaymentBackfillPayableTest(TestCase):
    def test_payment_backfills_payable_amount_paid(self):
        item = PayableItem.objects.create(source_type='expense', source_id=9, source_no='EXP9',
                                          category='报销', payee_name='张三', amount_due=Decimal('300.00'))
        Payment.objects.create(
            payment_type='PAYABLE', payable_item=item,
            payment_date='2026-07-02', payment_method='BANK_TRANSFER',
            amount=Decimal('120.00'),
        )
        item.refresh_from_db()
        self.assertEqual(item.amount_paid, Decimal('120.00'))
        self.assertEqual(item.status, PayableItem.STATUS_PARTIAL)


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class AdapterRegistryTest(TestCase):
    def test_register_source_populates_registry(self):
        @register_source
        class _S(PayableSource):
            source_type = 'demo'
            category = '演示'
            def to_payable(self, obj):
                return {}
            def write_back(self, obj, item):
                pass
        self.addCleanup(lambda: PAYABLE_SOURCES.pop('demo', None))
        self.assertIn('demo', PAYABLE_SOURCES)
        self.assertEqual(PAYABLE_SOURCES['demo'].category, '演示')


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class APAdapterTest(TestCase):
    def _make_ap(self):
        from apps.masterdata.models import Supplier
        from apps.finance.models import AccountPayable
        sup = Supplier.objects.create(code='S1', name='供应商甲')
        return AccountPayable.objects.create(
            supplier=sup, invoice_date='2026-06-01', due_date='2026-07-01',
            amount_due=Decimal('1000.00'),
        )

    def test_ap_register_and_writeback(self):
        from apps.finance.payable_adapters import register_payable
        from apps.finance.payable_models import PayableItem
        ap = self._make_ap()
        item = register_payable(ap, 'ap')
        self.assertEqual(item.payee_name, '供应商甲')
        self.assertEqual(item.supplier_id, ap.supplier_id)
        self.assertEqual(item.amount_due, Decimal('1000.00'))
        self.assertEqual(item.source_no, ap.ap_no)

        item.amount_paid = Decimal('1000.00'); item.recalc_status(); item.save()
        PAYABLE_SOURCES['ap'].write_back(ap, item)
        ap.refresh_from_db()
        self.assertEqual(ap.amount_paid, Decimal('1000.00'))
        self.assertEqual(ap.status, 'PAID')


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class ExpenseAdapterTest(TestCase):
    def test_expense_register_and_full_writeback(self):
        from apps.accounts.models import User
        from apps.finance.models import Expense
        from apps.finance.payable_adapters import register_payable, PAYABLE_SOURCES

        # apps.accounts.models.User 无 real_name 字段;姓名由 first_name/last_name
        # 经 get_full_name() 拼接('张'+'三' -> '张三'),该方法自身在为空时回退到 username。
        u = User.objects.create(username='zs', employee_id='E9', first_name='三', last_name='张')
        exp = Expense.objects.create(expense_no='EXP200', user=u, expense_date='2026-07-01',
                                     category='TRAVEL', amount=Decimal('800.00'), status='APPROVED')
        item = register_payable(exp, 'expense')
        self.assertIsNone(item.supplier_id)
        self.assertEqual(item.amount_due, Decimal('800.00'))
        self.assertEqual(item.source_no, 'EXP200')
        self.assertEqual(item.payee_name, '张三')

        item.amount_paid = Decimal('800.00'); item.recalc_status(); item.save()
        PAYABLE_SOURCES['expense'].write_back(exp, item)
        exp.refresh_from_db()
        self.assertEqual(exp.status, 'PAID')
        self.assertIsNotNone(exp.reimbursement_date)


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class ContractPaymentAdapterTest(TestCase):
    def _make_payment_record(self):
        from apps.masterdata.models import Supplier
        from apps.purchase.models import PurchaseContract, PurchaseOrder
        from apps.purchase.contract_execution import ContractExecution, PaymentRecord
        sup = Supplier.objects.create(code='S3', name='外协丙')
        # PurchaseContract 必填 po(FK→PurchaseOrder,PROTECT)与 contract_date(无默认值);
        # PurchaseOrder 必填 supplier 与 delivery_date(无默认值)。均按真实模型补齐。
        po = PurchaseOrder.objects.create(supplier=sup, delivery_date='2026-07-20')
        contract = PurchaseContract.objects.create(
            po=po, supplier=sup, contract_no='PC001', title='外协合同',
            contract_date='2026-06-01', total_amount=Decimal('5000'),
        )
        ex = ContractExecution.objects.create(contract=contract, contract_amount=Decimal('5000'))
        return PaymentRecord.objects.create(execution=ex, payment_no='CPR001',
                                            planned_date='2026-07-10', amount=Decimal('2000.00'), status='APPROVED')

    def test_contract_payment_register_and_writeback(self):
        from apps.finance.payable_adapters import register_payable, PAYABLE_SOURCES
        pr = self._make_payment_record()
        item = register_payable(pr, 'contract_payment')
        self.assertEqual(item.payee_name, '外协丙')
        self.assertEqual(item.supplier_id, pr.execution.contract.supplier_id)
        self.assertEqual(item.amount_due, Decimal('2000.00'))
        self.assertEqual(item.source_no, 'CPR001')
        self.assertIsNone(item.currency_id)
        self.assertIsNone(item.project_id)

        item.amount_paid = Decimal('2000.00'); item.recalc_status(); item.save()
        PAYABLE_SOURCES['contract_payment'].write_back(pr, item)
        pr.refresh_from_db(); pr.execution.refresh_from_db()
        self.assertEqual(pr.status, 'PAID')
        self.assertIsNotNone(pr.actual_date)
        self.assertEqual(pr.execution.paid_amount, Decimal('2000.00'))

        # 幂等:对已 PAID 的记录再次 write_back 不应重复累加 execution.paid_amount
        PAYABLE_SOURCES['contract_payment'].write_back(pr, item)
        pr.execution.refresh_from_db()
        self.assertEqual(pr.execution.paid_amount, Decimal('2000.00'))


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class MatchCandidatesTest(TestCase):
    def test_scores_supplier_and_amount(self):
        from apps.finance.models import BankStatement
        from apps.finance.payable_models import PayableItem
        from apps.finance.payable_service import match_candidates

        good = PayableItem.objects.create(
            source_type='ap', source_id=1, source_no='AP1', category='采购',
            payee_name='考泰斯(长春)塑料技术有限公司', amount_due=Decimal('1000.00'),
        )
        PayableItem.objects.create(
            source_type='ap', source_id=2, source_no='AP2', category='采购',
            payee_name='无关公司', amount_due=Decimal('50.00'),
        )
        bs = BankStatement(
            transaction_type='DEBIT', debit_amount=Decimal('1000.00'),
            counterparty_name='考泰斯（长春）塑料技术有限公司', transaction_time='2026-07-02 00:00:00+00',
        )
        bs.save()

        cands = match_candidates(bs)

        self.assertEqual(cands[0]['payable_item'].pk, good.pk)
        self.assertGreaterEqual(cands[0]['score'], 90)
        # 无关公司名称与金额均不匹配,不应进入候选列表
        self.assertEqual(len(cands), 1)

    def test_excludes_paid_and_cancelled_and_respects_limit(self):
        from apps.finance.models import BankStatement
        from apps.finance.payable_models import PayableItem
        from apps.finance.payable_service import match_candidates

        paid = PayableItem.objects.create(
            source_type='ap', source_id=11, source_no='AP11', category='采购',
            payee_name='已付公司', amount_due=Decimal('1000.00'), amount_paid=Decimal('1000.00'),
            status=PayableItem.STATUS_PAID,
        )
        cancelled = PayableItem.objects.create(
            source_type='ap', source_id=12, source_no='AP12', category='采购',
            payee_name='已付公司', amount_due=Decimal('1000.00'), status=PayableItem.STATUS_CANCELLED,
        )
        for i in range(3):
            PayableItem.objects.create(
                source_type='ap', source_id=100 + i, source_no=f'AP1{i}', category='采购',
                payee_name='已付公司', amount_due=Decimal('1000.00'),
            )
        bs = BankStatement(
            transaction_type='DEBIT', debit_amount=Decimal('1000.00'),
            counterparty_name='已付公司', transaction_time='2026-07-02 00:00:00+00',
        )
        bs.save()

        cands = match_candidates(bs, limit=2)

        self.assertEqual(len(cands), 2)
        matched_pks = {c['payable_item'].pk for c in cands}
        self.assertNotIn(paid.pk, matched_pks)
        self.assertNotIn(cancelled.pk, matched_pks)
        for c in cands:
            self.assertGreaterEqual(c['score'], 90)
            self.assertIn('收款方一致', c['reasons'])
            self.assertIn('金额等于剩余', c['reasons'])

    def test_partial_amount_and_due_date_scoring(self):
        from apps.finance.models import BankStatement
        from apps.finance.payable_models import PayableItem
        from apps.finance.payable_service import match_candidates

        item = PayableItem.objects.create(
            source_type='ap', source_id=21, source_no='AP21', category='采购',
            payee_name='部分匹配公司', amount_due=Decimal('1000.00'), amount_paid=Decimal('200.00'),
            status=PayableItem.STATUS_PARTIAL, due_date='2026-07-05',
        )
        bs = BankStatement(
            transaction_type='DEBIT', debit_amount=Decimal('500.00'),
            counterparty_name='部分匹配公司', transaction_time='2026-07-02 00:00:00+00',
        )
        bs.save()

        cands = match_candidates(bs)

        self.assertEqual(len(cands), 1)
        cand = cands[0]
        self.assertEqual(cand['payable_item'].pk, item.pk)
        # 收款方一致(+50) + 金额不超剩余(+15) + 应付日期临近(+10) = 75
        self.assertEqual(cand['score'], 75)
        self.assertIn('收款方一致', cand['reasons'])
        self.assertIn('金额不超剩余', cand['reasons'])
        self.assertIn('应付日期临近', cand['reasons'])

    def test_unrelated_item_not_included(self):
        from apps.finance.models import BankStatement
        from apps.finance.payable_models import PayableItem
        from apps.finance.payable_service import match_candidates

        # 名称不匹配、金额远超剩余(不满足"等于"也不满足"不超过")、应付日期相差远超 7 天,
        # 三项打分规则均不命中,score 应为 0 而被排除在候选之外。
        PayableItem.objects.create(
            source_type='ap', source_id=31, source_no='AP31', category='采购',
            payee_name='完全无关的公司', amount_due=Decimal('10.00'), due_date='2020-01-01',
        )
        bs = BankStatement(
            transaction_type='DEBIT', debit_amount=Decimal('1000.00'),
            counterparty_name='考泰斯(长春)塑料技术有限公司', transaction_time='2026-07-02 00:00:00+00',
        )
        bs.save()

        cands = match_candidates(bs)

        self.assertEqual(cands, [])


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class SettleTest(TestCase):
    def _bs(self, amt):
        from apps.finance.models import BankStatement
        bs = BankStatement(transaction_type='DEBIT', debit_amount=amt,
                           counterparty_name='供应商甲', transaction_time='2026-07-02 00:00:00+00')
        bs.save(); return bs

    def test_full_settlement_marks_matched_and_writes_back_ap(self):
        from apps.masterdata.models import Supplier
        from apps.finance.models import AccountPayable
        from apps.finance.payable_adapters import register_payable
        from apps.finance.payable_service import settle
        from apps.accounts.models import User
        u = User.objects.create(username='op', employee_id='OP1')
        sup = Supplier.objects.create(code='S1', name='供应商甲')
        ap = AccountPayable.objects.create(supplier=sup, invoice_date='2026-06-01',
                                           due_date='2026-07-01', amount_due=Decimal('1000.00'))
        item = register_payable(ap, 'ap')
        bs = self._bs(Decimal('1000.00'))
        settle(bs, [{'payable_item_id': item.pk, 'amount': Decimal('1000.00')}], u)
        item.refresh_from_db(); ap.refresh_from_db(); bs.refresh_from_db()
        self.assertEqual(item.status, 'PAID')
        self.assertEqual(ap.amount_paid, Decimal('1000.00'))
        self.assertEqual(ap.status, 'PAID')
        self.assertEqual(bs.status, 'MATCHED')

    def test_over_allocation_rejected(self):
        from apps.finance.payable_models import PayableItem
        from apps.finance.payable_service import settle
        from apps.accounts.models import User
        u = User.objects.create(username='op2', employee_id='OP2')
        item = PayableItem.objects.create(source_type='ap', source_id=99, source_no='AP99',
                                          category='采购', payee_name='甲', amount_due=Decimal('100.00'))
        bs = self._bs(Decimal('500.00'))
        with self.assertRaises(ValueError):
            settle(bs, [{'payable_item_id': item.pk, 'amount': Decimal('300.00')}], u)


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class UnsettleTest(TestCase):
    def test_unsettle_reverts_ledger_and_ap(self):
        from apps.masterdata.models import Supplier
        from apps.finance.models import AccountPayable
        from apps.finance.payable_adapters import register_payable
        from apps.finance.payable_service import settle, unsettle
        from apps.finance.models import BankStatement
        from apps.accounts.models import User
        u = User.objects.create(username='op3', employee_id='OP3')
        sup = Supplier.objects.create(code='S1', name='供应商甲')
        ap = AccountPayable.objects.create(supplier=sup, invoice_date='2026-06-01',
                                           due_date='2026-07-01', amount_due=Decimal('1000.00'))
        item = register_payable(ap, 'ap')
        bs = BankStatement(transaction_type='DEBIT', debit_amount=Decimal('1000.00'),
                           counterparty_name='供应商甲', transaction_time='2026-07-02 00:00:00+00')
        bs.save()
        s = settle(bs, [{'payable_item_id': item.pk, 'amount': Decimal('1000.00')}], u)[0]

        unsettle(s, u)
        item.refresh_from_db(); ap.refresh_from_db(); bs.refresh_from_db()
        self.assertEqual(item.amount_paid, Decimal('0'))
        self.assertEqual(item.status, 'PENDING')
        self.assertEqual(ap.amount_paid, Decimal('0'))
        self.assertEqual(ap.status, 'PENDING')
        self.assertEqual(bs.status, 'PENDING')


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class ExpenseUnsettleTest(TestCase):
    def test_unsettle_reverts_expense_status(self):
        from apps.accounts.models import User
        from apps.finance.models import BankStatement, Expense
        from apps.finance.payable_adapters import register_payable
        from apps.finance.payable_service import settle, unsettle
        u = User.objects.create(username='eu', employee_id='EU1')
        exp = Expense.objects.create(expense_no='EXPU1', user=u, expense_date='2026-07-01',
                                     category='TRAVEL', amount=Decimal('500.00'), status='APPROVED')
        item = register_payable(exp, 'expense')
        bs = BankStatement(transaction_type='DEBIT', debit_amount=Decimal('500.00'),
                           counterparty_name='报销', transaction_time='2026-07-02 00:00:00+00')
        bs.save()
        s = settle(bs, [{'payable_item_id': item.pk, 'amount': Decimal('500.00')}], u)[0]
        exp.refresh_from_db()
        self.assertEqual(exp.status, 'PAID')
        unsettle(s, u)
        exp.refresh_from_db()
        self.assertEqual(exp.status, 'APPROVED')
        self.assertIsNone(exp.reimbursement_date)


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class ContractUnsettleTest(TestCase):
    def test_unsettle_reverts_contract_payment_and_execution(self):
        from apps.accounts.models import User
        from apps.finance.models import BankStatement
        from apps.finance.payable_adapters import register_payable
        from apps.finance.payable_service import settle, unsettle
        from apps.masterdata.models import Supplier
        from apps.purchase.contract_execution import ContractExecution, PaymentRecord
        from apps.purchase.models import PurchaseContract, PurchaseOrder
        u = User.objects.create(username='cu', employee_id='CU1')
        sup = Supplier.objects.create(code='SC', name='外协')
        po = PurchaseOrder.objects.create(supplier=sup, delivery_date='2026-07-20')
        contract = PurchaseContract.objects.create(po=po, supplier=sup, contract_no='PCU1',
                                                   title='c', contract_date='2026-06-01', total_amount=Decimal('3000'))
        ex = ContractExecution.objects.create(contract=contract, contract_amount=Decimal('3000'))
        pr = PaymentRecord.objects.create(execution=ex, payment_no='CPRU1', planned_date='2026-07-10',
                                          amount=Decimal('3000.00'), status='APPROVED')
        item = register_payable(pr, 'contract_payment')
        bs = BankStatement(transaction_type='DEBIT', debit_amount=Decimal('3000.00'),
                           counterparty_name='外协', transaction_time='2026-07-02 00:00:00+00')
        bs.save()
        s = settle(bs, [{'payable_item_id': item.pk, 'amount': Decimal('3000.00')}], u)[0]
        pr.refresh_from_db(); ex.refresh_from_db()
        self.assertEqual(pr.status, 'PAID')
        self.assertEqual(ex.paid_amount, Decimal('3000.00'))
        unsettle(s, u)
        pr.refresh_from_db(); ex.refresh_from_db()
        self.assertEqual(pr.status, 'APPROVED')
        self.assertIsNone(pr.actual_date)
        self.assertEqual(ex.paid_amount, Decimal('0'))


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class PayableApiTest(TestCase):
    def setUp(self):
        from rest_framework.test import APIClient
        from apps.accounts.models import User
        self.user = User.objects.create(username='apiadmin', employee_id='API1',
                                        is_staff=True, is_superuser=True)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _make_ap_and_bs(self):
        from apps.masterdata.models import Supplier
        from apps.finance.models import AccountPayable, BankStatement
        from apps.finance.payable_adapters import register_payable
        sup = Supplier.objects.create(code='S1', name='供应商甲')
        ap = AccountPayable.objects.create(supplier=sup, invoice_date='2026-06-01',
                                           due_date='2026-07-01', amount_due=Decimal('1000.00'))
        item = register_payable(ap, 'ap')
        bs = BankStatement(transaction_type='DEBIT', debit_amount=Decimal('1000.00'),
                           counterparty_name='供应商甲', transaction_time='2026-07-02 00:00:00+00')
        bs.save()
        return ap, item, bs

    def test_payable_items_list(self):
        self._make_ap_and_bs()
        resp = self.client.get('/api/finance/payable-items/')
        self.assertEqual(resp.status_code, 200)
        results = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        self.assertGreaterEqual(len(results), 1)

    def test_candidates_endpoint(self):
        ap, item, bs = self._make_ap_and_bs()
        resp = self.client.get(f'/api/finance/bank-statements/{bs.id}/payable-candidates/')
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['payable_item_id'], item.pk)
        self.assertGreater(resp.data[0]['score'], 0)

    def test_settle_and_unsettle_endpoints(self):
        ap, item, bs = self._make_ap_and_bs()
        resp = self.client.post('/api/finance/payable-reconcile/settle/', {
            'bank_statement_id': bs.id,
            'allocations': [{'payable_item_id': item.pk, 'amount': '1000.00'}],
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        item.refresh_from_db(); bs.refresh_from_db()
        self.assertEqual(item.status, 'PAID')
        self.assertEqual(bs.status, 'MATCHED')
        settlement_id = resp.data['settlement_ids'][0]
        resp2 = self.client.post('/api/finance/payable-reconcile/unsettle/', {
            'settlement_id': settlement_id,
        }, format='json')
        self.assertEqual(resp2.status_code, 200, resp2.data)
        item.refresh_from_db(); bs.refresh_from_db()
        self.assertEqual(item.status, 'PENDING')
        self.assertEqual(bs.status, 'PENDING')

    def test_settle_over_allocation_returns_400(self):
        ap, item, bs = self._make_ap_and_bs()
        resp = self.client.post('/api/finance/payable-reconcile/settle/', {
            'bank_statement_id': bs.id,
            'allocations': [{'payable_item_id': item.pk, 'amount': '9999.00'}],
        }, format='json')
        self.assertEqual(resp.status_code, 400)


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class BackfillTest(TestCase):
    def test_backfill_creates_payable_for_open_ap(self):
        from django.core.management import call_command
        from apps.masterdata.models import Supplier
        from apps.finance.models import AccountPayable
        sup = Supplier.objects.create(code='S1', name='供应商甲')
        ap = AccountPayable.objects.create(supplier=sup, invoice_date='2026-06-01', due_date='2026-07-01',
                                           amount_due=Decimal('1000.00'), amount_paid=Decimal('300.00'))
        # 已结清的 AP 不应回填
        paid = AccountPayable.objects.create(supplier=sup, invoice_date='2026-06-01', due_date='2026-07-01',
                                             amount_due=Decimal('500.00'), amount_paid=Decimal('500.00'))
        call_command('backfill_payables')
        item = PayableItem.objects.get(source_type='ap', source_id=ap.pk)
        self.assertEqual(item.amount_due, Decimal('1000.00'))
        self.assertEqual(item.amount_paid, Decimal('300.00'))
        self.assertEqual(item.status, 'PARTIAL')
        self.assertFalse(PayableItem.objects.filter(source_type='ap', source_id=paid.pk).exists())

    def test_backfill_is_idempotent(self):
        from django.core.management import call_command
        from apps.masterdata.models import Supplier
        from apps.finance.models import AccountPayable
        sup = Supplier.objects.create(code='S2', name='供应商乙')
        ap = AccountPayable.objects.create(supplier=sup, invoice_date='2026-06-01', due_date='2026-07-01',
                                           amount_due=Decimal('800.00'))
        call_command('backfill_payables')
        call_command('backfill_payables')
        self.assertEqual(PayableItem.objects.filter(source_type='ap', source_id=ap.pk).count(), 1)


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class ContractPaymentSignalTest(TestCase):
    def _make_execution(self, name='外协甲', code='SG1', amount='5000'):
        from apps.masterdata.models import Supplier
        from apps.purchase.contract_execution import ContractExecution
        from apps.purchase.models import PurchaseContract, PurchaseOrder
        sup = Supplier.objects.create(code=code, name=name)
        po = PurchaseOrder.objects.create(supplier=sup, delivery_date='2026-07-20')
        contract = PurchaseContract.objects.create(po=po, supplier=sup, contract_no=f'PC{code}',
                                                   title='c', contract_date='2026-06-01',
                                                   total_amount=Decimal(amount))
        return ContractExecution.objects.create(contract=contract, contract_amount=Decimal(amount))

    def test_signal_registers_on_create_approved(self):
        from apps.purchase.contract_execution import PaymentRecord
        ex = self._make_execution()
        pr = PaymentRecord.objects.create(execution=ex, payment_no='SIGP1', planned_date='2026-07-10',
                                          amount=Decimal('2000.00'), status='APPROVED')
        item = PayableItem.objects.get(source_type='contract_payment', source_id=pr.pk)
        self.assertEqual(item.amount_due, Decimal('2000.00'))
        self.assertEqual(item.payee_name, '外协甲')
        self.assertEqual(item.status, PayableItem.STATUS_PENDING)

    def test_signal_registers_on_transition_to_approved(self):
        from apps.purchase.contract_execution import PaymentRecord
        ex = self._make_execution(name='外协乙', code='SG2')
        pr = PaymentRecord.objects.create(execution=ex, payment_no='SIGP2', planned_date='2026-07-10',
                                          amount=Decimal('1500.00'), status='PENDING')
        self.assertFalse(PayableItem.objects.filter(source_type='contract_payment', source_id=pr.pk).exists())
        pr.status = 'APPROVED'
        pr.save()
        self.assertTrue(PayableItem.objects.filter(source_type='contract_payment', source_id=pr.pk).exists())

    def test_signal_cancels_on_cancelled(self):
        from apps.purchase.contract_execution import PaymentRecord
        ex = self._make_execution(name='外协丙', code='SG3')
        pr = PaymentRecord.objects.create(execution=ex, payment_no='SIGP3', planned_date='2026-07-10',
                                          amount=Decimal('800.00'), status='APPROVED')
        pr.status = 'CANCELLED'
        pr.save()
        item = PayableItem.objects.get(source_type='contract_payment', source_id=pr.pk)
        self.assertEqual(item.status, PayableItem.STATUS_CANCELLED)

    def test_approve_action_registers(self):
        from rest_framework.test import APIClient
        from apps.accounts.models import User
        from apps.purchase.contract_execution import PaymentRecord
        ex = self._make_execution(name='外协丁', code='SG4')
        pr = PaymentRecord.objects.create(execution=ex, payment_no='SIGP4', planned_date='2026-07-10',
                                          amount=Decimal('1200.00'), status='PENDING')
        # 以 PENDING 创建,信号不登记;approve 后才应出现台账项。
        self.assertFalse(PayableItem.objects.filter(source_type='contract_payment', source_id=pr.pk).exists())
        user = User.objects.create(username='pradmin', employee_id='PRA1', is_staff=True, is_superuser=True)
        client = APIClient(); client.force_authenticate(user)
        resp = client.post(f'/api/purchase/payment-records/{pr.pk}/approve/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        pr.refresh_from_db()
        self.assertEqual(pr.status, 'APPROVED')
        self.assertTrue(PayableItem.objects.filter(source_type='contract_payment', source_id=pr.pk).exists())


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class ContractPayRetiredTest(TestCase):
    def test_pay_endpoint_retired_returns_409_and_no_side_effect(self):
        from rest_framework.test import APIClient
        from apps.accounts.models import User
        from apps.masterdata.models import Supplier
        from apps.purchase.contract_execution import ContractExecution, PaymentRecord
        from apps.purchase.models import PurchaseContract, PurchaseOrder
        sup = Supplier.objects.create(code='PR1', name='外协戊')
        po = PurchaseOrder.objects.create(supplier=sup, delivery_date='2026-07-20')
        contract = PurchaseContract.objects.create(po=po, supplier=sup, contract_no='PCPR1',
                                                   title='c', contract_date='2026-06-01', total_amount=Decimal('3000'))
        ex = ContractExecution.objects.create(contract=contract, contract_amount=Decimal('3000'))
        pr = PaymentRecord.objects.create(execution=ex, payment_no='PAYR1', planned_date='2026-07-10',
                                          amount=Decimal('3000.00'), status='APPROVED')
        user = User.objects.create(username='payadmin', employee_id='PAY1', is_staff=True, is_superuser=True)
        client = APIClient(); client.force_authenticate(user)
        resp = client.post(f'/api/purchase/payment-records/{pr.pk}/pay/', {}, format='json')
        self.assertEqual(resp.status_code, 409)
        pr.refresh_from_db(); ex.refresh_from_db()
        self.assertEqual(pr.status, 'APPROVED')          # 未被标 PAID
        self.assertEqual(ex.paid_amount, Decimal('0'))   # execution.paid_amount 未被改


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class ContractBackfillTest(TestCase):
    def _make_pr(self, no, status, code):
        from apps.masterdata.models import Supplier
        from apps.purchase.contract_execution import ContractExecution, PaymentRecord
        from apps.purchase.models import PurchaseContract, PurchaseOrder
        sup = Supplier.objects.create(code=code, name=f'外协{code}')
        po = PurchaseOrder.objects.create(supplier=sup, delivery_date='2026-07-20')
        contract = PurchaseContract.objects.create(po=po, supplier=sup, contract_no=f'PC{code}',
                                                   title='c', contract_date='2026-06-01', total_amount=Decimal('3000'))
        ex = ContractExecution.objects.create(contract=contract, contract_amount=Decimal('3000'))
        return PaymentRecord.objects.create(execution=ex, payment_no=no, planned_date='2026-07-10',
                                            amount=Decimal('1000.00'), status=status)

    def test_backfill_registers_only_approved(self):
        from django.core.management import call_command
        approved = self._make_pr('BF1', 'APPROVED', 'BFA')
        paid = self._make_pr('BF2', 'PAID', 'BFP')
        # 清掉信号在 create 时可能登记的项,模拟"存量未登记"
        PayableItem.objects.all().delete()
        call_command('backfill_contract_payables')
        self.assertTrue(PayableItem.objects.filter(source_type='contract_payment', source_id=approved.pk).exists())
        self.assertFalse(PayableItem.objects.filter(source_type='contract_payment', source_id=paid.pk).exists())

    def test_backfill_is_idempotent(self):
        from django.core.management import call_command
        approved = self._make_pr('BF3', 'APPROVED', 'BFI')
        PayableItem.objects.all().delete()
        call_command('backfill_contract_payables')
        call_command('backfill_contract_payables')
        self.assertEqual(
            PayableItem.objects.filter(source_type='contract_payment', source_id=approved.pk).count(), 1)


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class ContractPayPatchBypassTest(TestCase):
    def setUp(self):
        from rest_framework.test import APIClient
        from apps.accounts.models import User
        self.user = User.objects.create(username='pbadmin', employee_id='PB1', is_staff=True, is_superuser=True)
        self.client = APIClient(); self.client.force_authenticate(self.user)

    def _make(self):
        from apps.masterdata.models import Supplier
        from apps.purchase.contract_execution import ContractExecution, PaymentRecord
        from apps.purchase.models import PurchaseContract, PurchaseOrder
        sup = Supplier.objects.create(code='PB', name='外协PB')
        po = PurchaseOrder.objects.create(supplier=sup, delivery_date='2026-07-20')
        contract = PurchaseContract.objects.create(po=po, supplier=sup, contract_no='PCPB',
                                                   title='c', contract_date='2026-06-01', total_amount=Decimal('3000'))
        ex = ContractExecution.objects.create(contract=contract, contract_amount=Decimal('3000'))
        pr = PaymentRecord.objects.create(execution=ex, payment_no='PBP1', planned_date='2026-07-10',
                                          amount=Decimal('3000.00'), status='APPROVED')
        return ex, pr

    def test_patch_cannot_set_payment_status_paid(self):
        ex, pr = self._make()
        resp = self.client.patch(f'/api/purchase/payment-records/{pr.pk}/', {'status': 'PAID'}, format='json')
        self.assertIn(resp.status_code, (200, 202))
        pr.refresh_from_db()
        self.assertEqual(pr.status, 'APPROVED')  # 未被 PATCH 改成 PAID

    def test_patch_cannot_set_execution_paid_amount(self):
        ex, pr = self._make()
        resp = self.client.patch(f'/api/purchase/contract-executions/{ex.pk}/', {'paid_amount': '9999.00'}, format='json')
        self.assertIn(resp.status_code, (200, 202))
        ex.refresh_from_db()
        self.assertEqual(ex.paid_amount, Decimal('0'))  # 未被 PATCH 改


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class OutsourceAdapterTest(TestCase):
    """委外加工:OutsourceOrder.status 是收货/加工进度机,无付款语义,write_back 为
    no-op(付款事实由统一台账维护)。这里断言 register 取数正确,以及 write_back 无论
    正向核销/反核销都不改动源单据既有的进度状态(不破坏其状态机)。"""

    def _make_order(self):
        from apps.masterdata.models import Supplier
        from apps.purchase.outsource_models import OutsourceOrder
        sup = Supplier.objects.create(code='OS1', name='外协商甲')
        return OutsourceOrder.objects.create(
            supplier=sup, required_date='2026-07-20', status='CONFIRMED',
            total_amount=Decimal('4000.00'), tax_amount=Decimal('520.00'),
            total_with_tax=Decimal('4520.00'),
        )

    def test_outsource_register_and_writeback_is_noop(self):
        from apps.finance.payable_adapters import PAYABLE_SOURCES, register_payable
        order = self._make_order()
        item = register_payable(order, 'outsource')
        self.assertEqual(item.payee_name, '外协商甲')
        self.assertEqual(item.supplier_id, order.supplier_id)
        self.assertEqual(item.amount_due, Decimal('4520.00'))
        self.assertEqual(item.source_no, order.order_no)

        item.amount_paid = Decimal('4520.00')
        item.recalc_status()
        item.save()
        PAYABLE_SOURCES['outsource'].write_back(order, item)
        order.refresh_from_db()
        self.assertEqual(order.status, 'CONFIRMED')  # no-op:进度状态机不受付款影响

        # 反核销(台账退回未结清),no-op 仍不应改动源单据状态。
        item.amount_paid = Decimal('0')
        item.recalc_status()
        item.save()
        PAYABLE_SOURCES['outsource'].write_back(order, item)
        order.refresh_from_db()
        self.assertEqual(order.status, 'CONFIRMED')


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class SharedExpenseAdapterTest(TestCase):
    """公共费用:SharedExpense.status 是分摊进度机(allocate() 依赖 status=='ALLOCATED'
    拒绝重复分摊),无付款语义,write_back 为 no-op,同上断言不破坏其状态机。"""

    def _make_expense(self):
        from apps.finance.models import SharedExpense
        return SharedExpense.objects.create(
            expense_no='SE001', name='办公室房租-2026年7月', category='RENT',
            expense_date='2026-07-01', period_start='2026-07-01', period_end='2026-07-31',
            amount=Decimal('6000.00'), status='ALLOCATED',
        )

    def test_shared_expense_register_and_writeback_is_noop(self):
        from apps.finance.payable_adapters import PAYABLE_SOURCES, register_payable
        exp = self._make_expense()
        item = register_payable(exp, 'shared_expense')
        self.assertIsNone(item.supplier_id)
        self.assertEqual(item.amount_due, Decimal('6000.00'))
        self.assertEqual(item.source_no, 'SE001')
        self.assertEqual(item.payee_name, '办公室房租-2026年7月')

        item.amount_paid = Decimal('6000.00')
        item.recalc_status()
        item.save()
        PAYABLE_SOURCES['shared_expense'].write_back(exp, item)
        exp.refresh_from_db()
        self.assertEqual(exp.status, 'ALLOCATED')  # no-op:分摊状态机不受付款影响

        item.amount_paid = Decimal('0')
        item.recalc_status()
        item.save()
        PAYABLE_SOURCES['shared_expense'].write_back(exp, item)
        exp.refresh_from_db()
        self.assertEqual(exp.status, 'ALLOCATED')


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class TaxAdapterTest(TestCase):
    def _make_declaration(self):
        from apps.finance.tax_management import TaxDeclaration, TaxPeriod, TaxType
        tt = TaxType.objects.create(code='VAT', name='增值税')
        tp = TaxPeriod.objects.create(period_type='MONTHLY', year=2026, period=7,
                                      start_date='2026-07-01', end_date='2026-07-31',
                                      declare_deadline='2026-08-15')
        # TaxDeclaration.save() 每次都会用 payable_amount = tax_amount - deductible_amount
        # 重新计算并覆盖显式传入的 payable_amount,所以这里通过 tax_amount 间接控制应缴税额。
        return TaxDeclaration.objects.create(
            declaration_no='TD001', tax_period=tp, tax_type=tt,
            declaration_type='VAT', status='DECLARED', tax_amount=Decimal('1500.00'),
        )

    def test_tax_register_and_full_writeback(self):
        from apps.finance.payable_adapters import PAYABLE_SOURCES, register_payable
        td = self._make_declaration()
        item = register_payable(td, 'tax')
        self.assertIsNone(item.supplier_id)
        self.assertEqual(item.payee_name, '税务局')
        self.assertEqual(item.amount_due, Decimal('1500.00'))
        self.assertEqual(item.source_no, 'TD001')
        # register_payable 返回的是 update_or_create 的内存态对象,DateField 赋的原始
        # 字符串不会像从数据库读回那样被反序列化(同 match_candidates 里 transaction_time
        # 的既有量),需 refresh_from_db 后才能拿到真正的 date 对象。
        item.refresh_from_db()
        self.assertEqual(item.due_date.isoformat(), '2026-08-15')

        item.amount_paid = Decimal('1500.00')
        item.recalc_status()
        item.save()
        PAYABLE_SOURCES['tax'].write_back(td, item)
        td.refresh_from_db()
        self.assertEqual(td.status, 'PAID')
        self.assertEqual(td.paid_amount, Decimal('1500.00'))
        self.assertIsNotNone(td.paid_at)

        # 幂等:对已 PAID 的申报单再次 write_back,不应重复改写缴款时间。
        first_paid_at = td.paid_at
        PAYABLE_SOURCES['tax'].write_back(td, item)
        td.refresh_from_db()
        self.assertEqual(td.paid_at, first_paid_at)

    def test_tax_writeback_reverses_on_unsettle(self):
        from apps.accounts.models import User
        from apps.finance.models import BankStatement
        from apps.finance.payable_adapters import register_payable
        from apps.finance.payable_service import settle, unsettle
        u = User.objects.create(username='taxop', employee_id='TAX1')
        td = self._make_declaration()
        item = register_payable(td, 'tax')
        bs = BankStatement(transaction_type='DEBIT', debit_amount=Decimal('1500.00'),
                           counterparty_name='税务局', transaction_time='2026-07-02 00:00:00+00')
        bs.save()
        s = settle(bs, [{'payable_item_id': item.pk, 'amount': Decimal('1500.00')}], u)[0]
        td.refresh_from_db()
        self.assertEqual(td.status, 'PAID')

        unsettle(s, u)
        td.refresh_from_db()
        self.assertEqual(td.status, 'DECLARED')
        self.assertEqual(td.paid_amount, Decimal('0'))
        self.assertIsNone(td.paid_at)


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class PaymentRequestAdapterTest(TestCase):
    def _make_request(self):
        from apps.accounts.models import User
        from apps.finance.models import PaymentRequest
        from apps.masterdata.models import Supplier
        sup = Supplier.objects.create(code='PRQ1', name='供应商丁')
        applicant = User.objects.create(username='pra1', employee_id='PRA10')
        return PaymentRequest.objects.create(
            request_no='PRQ001', title='进度款申请', supplier=sup, amount=Decimal('3000.00'),
            expected_date='2026-07-15', reason='项目进度款', applicant=applicant, status='APPROVED',
        )

    def test_payment_request_register_and_full_writeback(self):
        from apps.finance.payable_adapters import PAYABLE_SOURCES, register_payable
        pr = self._make_request()
        item = register_payable(pr, 'payment_request')
        self.assertEqual(item.payee_name, '供应商丁')
        self.assertEqual(item.supplier_id, pr.supplier_id)
        self.assertEqual(item.amount_due, Decimal('3000.00'))
        self.assertEqual(item.source_no, 'PRQ001')

        item.amount_paid = Decimal('3000.00')
        item.recalc_status()
        item.save()
        PAYABLE_SOURCES['payment_request'].write_back(pr, item)
        pr.refresh_from_db()
        self.assertEqual(pr.status, 'PAID')
        self.assertIsNotNone(pr.paid_at)

    def test_payment_request_writeback_reverses_on_unsettle(self):
        from apps.accounts.models import User
        from apps.finance.models import BankStatement
        from apps.finance.payable_adapters import register_payable
        from apps.finance.payable_service import settle, unsettle
        u = User.objects.create(username='prqop', employee_id='PRQOP1')
        pr = self._make_request()
        item = register_payable(pr, 'payment_request')
        bs = BankStatement(transaction_type='DEBIT', debit_amount=Decimal('3000.00'),
                           counterparty_name='供应商丁', transaction_time='2026-07-02 00:00:00+00')
        bs.save()
        s = settle(bs, [{'payable_item_id': item.pk, 'amount': Decimal('3000.00')}], u)[0]
        pr.refresh_from_db()
        self.assertEqual(pr.status, 'PAID')
        self.assertIsNotNone(pr.payment_id)

        unsettle(s, u)
        pr.refresh_from_db()
        self.assertEqual(pr.status, 'APPROVED')
        self.assertIsNone(pr.paid_at)
        self.assertIsNone(pr.payment_id)
