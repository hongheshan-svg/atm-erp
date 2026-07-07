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
