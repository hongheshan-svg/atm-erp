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

    def test_payable_items_list_filters_by_amount_and_due_date_range(self):
        self._make_ap_and_bs()  # amount_due=1000.00, due_date=2026-07-01
        resp_in_range = self.client.get('/api/finance/payable-items/', {
            'amount_due__gte': '500', 'amount_due__lte': '1500',
            'due_date__gte': '2026-06-01', 'due_date__lte': '2026-07-31',
        })
        self.assertEqual(resp_in_range.status_code, 200)
        results_in = resp_in_range.data['results'] if isinstance(resp_in_range.data, dict) else resp_in_range.data
        self.assertGreaterEqual(len(results_in), 1)

        resp_out_of_range = self.client.get('/api/finance/payable-items/', {'amount_due__gte': '2000'})
        self.assertEqual(resp_out_of_range.status_code, 200)
        results_out = resp_out_of_range.data['results'] if isinstance(resp_out_of_range.data, dict) else resp_out_of_range.data
        self.assertEqual(len(results_out), 0)

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
        self.assertEqual(len(resp.data['payment_nos']), 1)
        self.assertTrue(resp.data['payment_nos'][0])
        resp2 = self.client.post('/api/finance/payable-reconcile/unsettle/', {
            'settlement_id': settlement_id,
        }, format='json')
        self.assertEqual(resp2.status_code, 200, resp2.data)
        item.refresh_from_db(); bs.refresh_from_db()
        self.assertEqual(item.status, 'PENDING')
        self.assertEqual(bs.status, 'PENDING')

    def test_settlements_endpoint_lists_and_excludes_unsettled(self):
        ap, item, bs = self._make_ap_and_bs()
        resp = self.client.post('/api/finance/payable-reconcile/settle/', {
            'bank_statement_id': bs.id,
            'allocations': [{'payable_item_id': item.pk, 'amount': '1000.00'}],
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        settlement_id = resp.data['settlement_ids'][0]

        list_resp = self.client.get(f'/api/finance/bank-statements/{bs.id}/settlements/')
        self.assertEqual(list_resp.status_code, 200)
        self.assertEqual(len(list_resp.data), 1)
        row = list_resp.data[0]
        self.assertEqual(row['settlement_id'], settlement_id)
        self.assertEqual(row['payable_item']['id'], item.pk)
        self.assertEqual(row['payable_item']['source_type'], 'ap')
        self.assertEqual(Decimal(str(row['amount'])), Decimal('1000.00'))
        self.assertTrue(row['payment_no'])

        self.client.post('/api/finance/payable-reconcile/unsettle/', {'settlement_id': settlement_id}, format='json')
        list_resp2 = self.client.get(f'/api/finance/bank-statements/{bs.id}/settlements/')
        self.assertEqual(list_resp2.status_code, 200)
        self.assertEqual(len(list_resp2.data), 0)

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


# ---------------------------------------------------------------------------
# Item 1: AP(应付账款) Payment.ap 旧付款路径收口 —— 第一批(登记 + 只读守卫 + 双记
# bug 修复)。是否退役 record_payment / bank-statements match / payment-requests
# pay 这三条"直接创建 Payment(payment_type=AP)"的旧入口,设计文档已列为待用户拍板
# 事项(见 docs/superpowers/specs/2026-07-07-ap-payment-consolidation-design.md),
# 本批只覆盖已确认无争议的部分。
# ---------------------------------------------------------------------------


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class APPayableSignalTest(TestCase):
    def _make_ap(self, code, status=None, amount_paid=Decimal('0')):
        from apps.masterdata.models import Supplier
        from apps.finance.models import AccountPayable
        sup = Supplier.objects.create(code=code, name=f'供应商{code}')
        kwargs = dict(supplier=sup, invoice_date='2026-06-01', due_date='2026-07-01',
                     amount_due=Decimal('1000.00'), amount_paid=amount_paid)
        if status:
            kwargs['status'] = status
        return AccountPayable.objects.create(**kwargs)

    def test_create_registers_payable_item(self):
        ap = self._make_ap('SA1')
        item = PayableItem.objects.get(source_type='ap', source_id=ap.pk)
        self.assertEqual(item.amount_due, Decimal('1000.00'))
        self.assertEqual(item.payee_name, ap.supplier.name)
        self.assertEqual(item.status, PayableItem.STATUS_PENDING)

    def test_paid_ap_not_registered(self):
        # amount_paid>=amount_due 时 AccountPayable.save() 自动把 status 推成 PAID,
        # 已结清无需核销,不应污染核销候选(同合同付款"已付跳过"口径)。
        ap = self._make_ap('SA2', amount_paid=Decimal('1000.00'))
        self.assertEqual(ap.status, 'PAID')
        self.assertFalse(PayableItem.objects.filter(source_type='ap', source_id=ap.pk).exists())

    def test_cancelled_ap_cancels_existing_item(self):
        ap = self._make_ap('SA3')
        self.assertTrue(PayableItem.objects.filter(source_type='ap', source_id=ap.pk).exists())
        ap.status = 'CANCELLED'
        ap.save()
        item = PayableItem.objects.get(source_type='ap', source_id=ap.pk)
        self.assertEqual(item.status, PayableItem.STATUS_CANCELLED)

    def test_resave_is_idempotent_and_keeps_settlement_progress(self):
        ap = self._make_ap('SA4')
        item = PayableItem.objects.get(source_type='ap', source_id=ap.pk)
        item.amount_paid = Decimal('300.00')
        item.recalc_status()
        item.save(update_fields=['amount_paid', 'status', 'updated_at'])

        ap.due_date = '2026-08-01'
        ap.save()  # 重入信号:defaults 不含 amount_paid/status,不应覆盖上面手工核销的进度

        self.assertEqual(PayableItem.objects.filter(source_type='ap', source_id=ap.pk).count(), 1)
        item.refresh_from_db()
        self.assertEqual(item.amount_paid, Decimal('300.00'))
        self.assertEqual(item.due_date.isoformat(), '2026-08-01')


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class APStatusPatchBypassTest(TestCase):
    def setUp(self):
        from rest_framework.test import APIClient
        from apps.accounts.models import User
        self.user = User.objects.create(username='apstatus', employee_id='APS1', is_staff=True, is_superuser=True)
        self.client = APIClient(); self.client.force_authenticate(self.user)

    def test_patch_cannot_set_status_paid(self):
        from apps.masterdata.models import Supplier
        from apps.finance.models import AccountPayable
        sup = Supplier.objects.create(code='APS', name='供应商APS')
        ap = AccountPayable.objects.create(supplier=sup, invoice_date='2026-06-01',
                                           due_date='2026-07-01', amount_due=Decimal('1000.00'))
        resp = self.client.patch(f'/api/finance/payables/{ap.pk}/', {'status': 'PAID'}, format='json')
        self.assertIn(resp.status_code, (200, 202))
        ap.refresh_from_db()
        self.assertEqual(ap.status, 'PENDING')  # 未被 PATCH 改成 PAID
        self.assertEqual(ap.amount_paid, Decimal('0'))  # amount_paid 早已只读,一并回归

    def test_patch_cannot_set_amount_paid(self):
        from apps.masterdata.models import Supplier
        from apps.finance.models import AccountPayable
        sup = Supplier.objects.create(code='APS2', name='供应商APS2')
        ap = AccountPayable.objects.create(supplier=sup, invoice_date='2026-06-01',
                                           due_date='2026-07-01', amount_due=Decimal('1000.00'))
        resp = self.client.patch(f'/api/finance/payables/{ap.pk}/', {'amount_paid': '999.00'}, format='json')
        self.assertIn(resp.status_code, (200, 202))
        ap.refresh_from_db()
        self.assertEqual(ap.amount_paid, Decimal('0'))


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class PaymentApDirectCreateBlockedTest(TestCase):
    """通用 /api/finance/payments/ 不再允许直接创建 payment_type='AP' 的付款记录,
    防止绕过待付款项台账核销、重演 Payment.ap 双轨记账。"""

    def setUp(self):
        from rest_framework.test import APIClient
        from apps.accounts.models import User
        self.user = User.objects.create(username='payblk', employee_id='PBK1', is_staff=True, is_superuser=True)
        self.client = APIClient(); self.client.force_authenticate(self.user)

    def test_generic_payment_create_rejects_ap_type(self):
        from apps.masterdata.models import Supplier
        from apps.finance.models import AccountPayable
        sup = Supplier.objects.create(code='PBK', name='供应商PBK')
        ap = AccountPayable.objects.create(supplier=sup, invoice_date='2026-06-01',
                                           due_date='2026-07-01', amount_due=Decimal('1000.00'))
        resp = self.client.post('/api/finance/payments/', {
            'payment_type': 'AP', 'ap': ap.pk, 'amount': '500.00',
            'payment_date': '2026-07-05', 'payment_method': 'BANK_TRANSFER',
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        ap.refresh_from_db()
        self.assertEqual(ap.amount_paid, Decimal('0'))  # 未被这条本应拒绝的请求污染
        self.assertFalse(Payment.objects.filter(ap=ap).exists())

    def test_generic_payment_create_still_allows_payable_type(self):
        # 台账内部核销走 ORM 直连不经此序列化器,但也确认本次校验没有误伤
        # payment_type='PAYABLE' 这条正常类型的通用创建(如有其它合法调用方)。
        item = PayableItem.objects.create(source_type='expense', source_id=777, source_no='EXP777',
                                          category='报销', payee_name='张三', amount_due=Decimal('200.00'))
        resp = self.client.post('/api/finance/payments/', {
            'payment_type': 'PAYABLE', 'payable_item': item.pk, 'amount': '50.00',
            'payment_date': '2026-07-05', 'payment_method': 'BANK_TRANSFER',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class PaymentRequestPayNoDoubleCountTest(TestCase):
    """回归:PaymentRequestViewSet.pay() 历史上在 Payment.save() 已做 F() 递增之后,
    又对同一笔付款额外做了一次 F() 递增,导致 ap.amount_paid 被双记。"""

    def test_pay_increments_ap_amount_paid_exactly_once(self):
        from rest_framework.test import APIClient
        from apps.accounts.models import User
        from apps.masterdata.models import Supplier
        from apps.finance.models import AccountPayable, PaymentRequest
        sup = Supplier.objects.create(code='PRQ', name='供应商PRQ')
        ap = AccountPayable.objects.create(supplier=sup, invoice_date='2026-06-01',
                                           due_date='2026-07-01', amount_due=Decimal('1000.00'))
        applicant = User.objects.create(username='prqapplicant', employee_id='PRQA1')
        pr = PaymentRequest.objects.create(
            title='付款申请PRQ', supplier=sup, ap=ap, amount=Decimal('400.00'),
            reason='测试', applicant=applicant, status='APPROVED',
        )
        approver = User.objects.create(username='prqapprover', employee_id='PRQP1',
                                       is_staff=True, is_superuser=True)
        client = APIClient(); client.force_authenticate(approver)
        resp = client.post(f'/api/finance/payment-requests/{pr.pk}/pay/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        ap.refresh_from_db()
        self.assertEqual(ap.amount_paid, Decimal('400.00'))  # 而非曾经的双记 800
        self.assertEqual(ap.status, 'PARTIAL')


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class PaymentReconciliationPermissionSeedTest(TestCase):
    def test_init_permissions_creates_payment_reconciliation_menu(self):
        from django.core.management import call_command
        from apps.core.permission_models_new import Permission
        call_command('init_permissions')
        perm = Permission.objects.get(code='finance:payment_reconciliation')
        self.assertEqual(perm.name, '付款核销工作台')
        self.assertEqual(perm.type, 'menu')
        self.assertEqual(perm.route_path, '/finance/payment-reconciliation')
        self.assertEqual(perm.sort_order, 9)
        parent = perm.parent
        self.assertIsNotNone(parent)
        self.assertEqual(parent.code, 'finance')


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class ContractPaymentSignalFailureAlertTest(TestCase):
    """问题 I-2:register_payable 抛异常时,信号不能让 PaymentRecord.save() 失败,
    且要留下可观测的告警(SystemNotification),而不是仅静默 logger.error。"""

    def _make_execution(self, code='SGF1'):
        from apps.masterdata.models import Supplier
        from apps.purchase.contract_execution import ContractExecution
        from apps.purchase.models import PurchaseContract, PurchaseOrder
        sup = Supplier.objects.create(code=code, name=f'外协{code}')
        po = PurchaseOrder.objects.create(supplier=sup, delivery_date='2026-07-20')
        contract = PurchaseContract.objects.create(po=po, supplier=sup, contract_no=f'PC{code}',
                                                   title='c', contract_date='2026-06-01',
                                                   total_amount=Decimal('3000'))
        return ContractExecution.objects.create(contract=contract, contract_amount=Decimal('3000'))

    def test_register_payable_failure_creates_alert_and_does_not_raise(self):
        from unittest.mock import patch
        from apps.accounts.models import User
        from apps.core.models import SystemNotification
        from apps.purchase.contract_execution import PaymentRecord

        admin = User.objects.create(username='fadmin1', employee_id='FADM1', is_superuser=True, is_active=True)
        ex = self._make_execution()

        with patch('apps.finance.payable_adapters.register_payable', side_effect=RuntimeError('boom')):
            # 不应抛异常冒泡到调用方,PaymentRecord 必须能正常保存成功。
            pr = PaymentRecord.objects.create(
                execution=ex, payment_no='SIGF1', planned_date='2026-07-10',
                amount=Decimal('2000.00'), status='APPROVED',
            )

        pr.refresh_from_db()
        self.assertEqual(pr.status, 'APPROVED')
        # 台账项因 mock 未真正登记
        self.assertFalse(PayableItem.objects.filter(source_type='contract_payment', source_id=pr.pk).exists())
        # 但应留下告警通知给财务管理员(超管)
        notif = SystemNotification.objects.filter(user=admin, type='ERROR', title='合同付款台账同步失败').first()
        self.assertIsNotNone(notif)
        self.assertIn('SIGF1', notif.message)

    def test_cancel_payable_failure_creates_alert_and_does_not_raise(self):
        from unittest.mock import patch
        from apps.accounts.models import User
        from apps.core.models import SystemNotification
        from apps.purchase.contract_execution import PaymentRecord

        admin = User.objects.create(username='fadmin2', employee_id='FADM2', is_superuser=True, is_active=True)
        ex = self._make_execution(code='SGF2')
        pr = PaymentRecord.objects.create(
            execution=ex, payment_no='SIGF2', planned_date='2026-07-10',
            amount=Decimal('900.00'), status='APPROVED',
        )
        SystemNotification.objects.all().delete()

        with patch('apps.finance.payable_adapters.cancel_payable', side_effect=RuntimeError('boom')):
            pr.status = 'CANCELLED'
            pr.save()

        pr.refresh_from_db()
        self.assertEqual(pr.status, 'CANCELLED')
        notif = SystemNotification.objects.filter(user=admin, type='ERROR', title='合同付款台账同步失败').first()
        self.assertIsNotNone(notif)


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class BackfillPayablesSafetyNetTaskTest(TestCase):
    """问题 I-2 定时兜底:celery 任务应重跑两条 backfill 命令,补齐信号静默失败漏登记的台账项。"""

    def test_task_calls_both_backfill_commands(self):
        from unittest.mock import patch
        from apps.finance.tasks import backfill_payables_safety_net

        with patch('apps.finance.tasks.call_command') as mock_call:
            result = backfill_payables_safety_net()

        mock_call.assert_any_call('backfill_payables')
        mock_call.assert_any_call('backfill_contract_payables')
        self.assertEqual(mock_call.call_count, 2)
        self.assertIn('backfill', result)

    def test_task_backfills_payable_missed_by_failed_signal(self):
        from unittest.mock import patch
        from apps.masterdata.models import Supplier
        from apps.purchase.contract_execution import ContractExecution, PaymentRecord
        from apps.purchase.models import PurchaseContract, PurchaseOrder
        from apps.finance.tasks import backfill_payables_safety_net

        sup = Supplier.objects.create(code='SGF3', name='外协SGF3')
        po = PurchaseOrder.objects.create(supplier=sup, delivery_date='2026-07-20')
        contract = PurchaseContract.objects.create(po=po, supplier=sup, contract_no='PCSGF3',
                                                   title='c', contract_date='2026-06-01',
                                                   total_amount=Decimal('3000'))
        ex = ContractExecution.objects.create(contract=contract, contract_amount=Decimal('3000'))

        # 模拟信号静默失败:register_payable 抛异常,PaymentRecord 仍落 APPROVED,但无台账项。
        with patch('apps.finance.payable_adapters.register_payable', side_effect=RuntimeError('boom')):
            pr = PaymentRecord.objects.create(
                execution=ex, payment_no='SIGF3', planned_date='2026-07-10',
                amount=Decimal('700.00'), status='APPROVED',
            )
        self.assertFalse(PayableItem.objects.filter(source_type='contract_payment', source_id=pr.pk).exists())

        # 定时兜底任务重跑后应补齐台账项。
        backfill_payables_safety_net()
        self.assertTrue(PayableItem.objects.filter(source_type='contract_payment', source_id=pr.pk).exists())


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class ContractPaymentWithdrawRecoverTest(TestCase):
    """工作流"撤回"把 PaymentRecord 从 APPROVED 打回 PENDING 时,已登记的台账项
    应被回收(作废),避免继续留在核销候选池里被误核销;若撤回后又重新审批通过,
    台账项应从 CANCELLED 复活回 PENDING,而不是永久卡死在已作废状态。
    """

    def _make_execution(self, code='WD1'):
        from apps.masterdata.models import Supplier
        from apps.purchase.contract_execution import ContractExecution
        from apps.purchase.models import PurchaseContract, PurchaseOrder
        sup = Supplier.objects.create(code=code, name=f'外协{code}')
        po = PurchaseOrder.objects.create(supplier=sup, delivery_date='2026-07-20')
        contract = PurchaseContract.objects.create(po=po, supplier=sup, contract_no=f'PC{code}',
                                                   title='c', contract_date='2026-06-01',
                                                   total_amount=Decimal('3000'))
        return ContractExecution.objects.create(contract=contract, contract_amount=Decimal('3000'))

    def test_withdraw_cancels_registered_payable_item(self):
        from apps.purchase.contract_execution import PaymentRecord
        ex = self._make_execution(code='WD1')
        pr = PaymentRecord.objects.create(execution=ex, payment_no='WDP1', planned_date='2026-07-10',
                                          amount=Decimal('1000.00'), status='APPROVED')
        item = PayableItem.objects.get(source_type='contract_payment', source_id=pr.pk)
        self.assertEqual(item.status, PayableItem.STATUS_PENDING)

        # 模拟工作流"撤回":WITHDRAWN → PaymentRecord.status = 'PENDING'
        pr.status = 'PENDING'
        pr.save()

        item.refresh_from_db()
        self.assertEqual(item.status, PayableItem.STATUS_CANCELLED)

    def test_withdraw_then_reapprove_revives_payable_item(self):
        from apps.purchase.contract_execution import PaymentRecord
        ex = self._make_execution(code='WD2')
        pr = PaymentRecord.objects.create(execution=ex, payment_no='WDP2', planned_date='2026-07-10',
                                          amount=Decimal('1000.00'), status='APPROVED')
        item = PayableItem.objects.get(source_type='contract_payment', source_id=pr.pk)

        pr.status = 'PENDING'
        pr.save()
        item.refresh_from_db()
        self.assertEqual(item.status, PayableItem.STATUS_CANCELLED)

        # 重新审批通过:台账项应从 CANCELLED 复活回 PENDING,而不是保持作废
        pr.status = 'APPROVED'
        pr.save()
        item.refresh_from_db()
        self.assertEqual(item.status, PayableItem.STATUS_PENDING)
        self.assertEqual(item.amount_paid, Decimal('0'))

    def test_withdraw_is_noop_when_new_and_unsubmitted(self):
        """PENDING 同时也是"新建未提交"的初始态:此时尚无台账项,撤回分支的
        cancel_payable 调用应是安全的 no-op,不应报错也不应凭空创建台账项。"""
        from apps.purchase.contract_execution import PaymentRecord
        ex = self._make_execution(code='WD3')
        pr = PaymentRecord.objects.create(execution=ex, payment_no='WDP3', planned_date='2026-07-10',
                                          amount=Decimal('1000.00'), status='PENDING')
        pr.status = 'PENDING'
        pr.save()
        self.assertFalse(PayableItem.objects.filter(source_type='contract_payment', source_id=pr.pk).exists())

    def test_withdraw_does_not_touch_settled_payable_item(self):
        """若台账项已被核销(amount_paid>0),撤回不应作废它——cancel_payable 本身
        只对 amount_paid==0 的项生效,这里显式验证该不变量在撤回路径上也成立。"""
        from apps.purchase.contract_execution import PaymentRecord
        ex = self._make_execution(code='WD4')
        pr = PaymentRecord.objects.create(execution=ex, payment_no='WDP4', planned_date='2026-07-10',
                                          amount=Decimal('1000.00'), status='APPROVED')
        item = PayableItem.objects.get(source_type='contract_payment', source_id=pr.pk)
        item.amount_paid = Decimal('1000.00')
        item.recalc_status()
        item.save()
        self.assertEqual(item.status, PayableItem.STATUS_PAID)

        pr.status = 'PENDING'
        pr.save()
        item.refresh_from_db()
        self.assertEqual(item.status, PayableItem.STATUS_PAID)  # 未被误作废


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class ContractPaymentSubmitAutoApproveTest(TestCase):
    """submit action 在未配置审批工作流时应自动批准(WorkflowEnforcementMixin.
    start_workflow_or_auto_approve),端到端覆盖"审批到达路径三"之一:
    经 submit → 自动批准 → 信号登记台账。"""

    def test_submit_auto_approves_and_registers_payable(self):
        from rest_framework.test import APIClient
        from apps.accounts.models import User
        from apps.masterdata.models import Supplier
        from apps.purchase.contract_execution import ContractExecution, PaymentRecord
        from apps.purchase.models import PurchaseContract, PurchaseOrder

        sup = Supplier.objects.create(code='SUB1', name='外协提交测试')
        po = PurchaseOrder.objects.create(supplier=sup, delivery_date='2026-07-20')
        contract = PurchaseContract.objects.create(po=po, supplier=sup, contract_no='PCSUB1',
                                                   title='c', contract_date='2026-06-01',
                                                   total_amount=Decimal('3000'))
        ex = ContractExecution.objects.create(contract=contract, contract_amount=Decimal('3000'))
        pr = PaymentRecord.objects.create(execution=ex, payment_no='SUBP1', planned_date='2026-07-10',
                                          amount=Decimal('900.00'), status='PENDING')
        self.assertFalse(PayableItem.objects.filter(source_type='contract_payment', source_id=pr.pk).exists())

        user = User.objects.create(username='subadmin', employee_id='SUB1', is_staff=True, is_superuser=True)
        client = APIClient(); client.force_authenticate(user)
        resp = client.post(f'/api/purchase/payment-records/{pr.pk}/submit/', {}, format='json')

        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data.get('workflow_started') is False)
        pr.refresh_from_db()
        self.assertEqual(pr.status, 'APPROVED')
        item = PayableItem.objects.get(source_type='contract_payment', source_id=pr.pk)
        self.assertEqual(item.status, PayableItem.STATUS_PENDING)
        self.assertEqual(item.amount_due, Decimal('900.00'))


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


# ---------------------------------------------------------------------------
# R1: AP(应付账款)旧付款入口退役——用户已拍板方案 A:record_payment 与
# BankStatementViewSet.match 的 AP 分支全部改受控 409,AP 付款自此只经
# 「付款核销工作台」(payable-reconcile/settle)完成。AR 一侧(record_payment(AR)、
# match 的 AR 分支)不在本次范围内,须验证其继续正常工作。
# ---------------------------------------------------------------------------


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class APRecordPaymentRetiredTest(TestCase):
    """AccountPayableViewSet.record_payment 已停用,不再创建 Payment / 改动 AP。"""

    def setUp(self):
        from rest_framework.test import APIClient

        from apps.accounts.models import User

        self.user = User.objects.create(username='apretire', employee_id='APR1', is_staff=True, is_superuser=True)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_record_payment_returns_409_and_no_side_effect(self):
        from apps.finance.models import AccountPayable
        from apps.masterdata.models import Supplier

        sup = Supplier.objects.create(code='APR', name='供应商APR')
        ap = AccountPayable.objects.create(
            supplier=sup, invoice_date='2026-06-01', due_date='2026-07-01', amount_due=Decimal('1000.00')
        )
        resp = self.client.post(
            f'/api/finance/payables/{ap.pk}/record_payment/',
            {
                'amount': '500.00',
                'payment_date': '2026-07-05',
                'payment_method': 'BANK',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 409)
        ap.refresh_from_db()
        self.assertEqual(ap.amount_paid, Decimal('0'))  # 未被这条已停用的请求改动
        self.assertEqual(ap.status, 'PENDING')
        self.assertFalse(Payment.objects.filter(ap=ap).exists())


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class APBankStatementMatchRetiredTest(TestCase):
    """BankStatementViewSet.match 的 AP 分支已停用(409);AR 分支保留原逻辑不受影响。"""

    def setUp(self):
        from rest_framework.test import APIClient

        from apps.accounts.models import User

        self.user = User.objects.create(username='apmatchretire', employee_id='APM1', is_staff=True, is_superuser=True)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_match_ap_returns_409_and_no_side_effect(self):
        from apps.finance.models import AccountPayable, BankStatement
        from apps.masterdata.models import Supplier

        sup = Supplier.objects.create(code='APM', name='供应商APM')
        ap = AccountPayable.objects.create(
            supplier=sup, invoice_date='2026-06-01', due_date='2026-07-01', amount_due=Decimal('1000.00')
        )
        bs = BankStatement(
            transaction_type='DEBIT',
            debit_amount=Decimal('1000.00'),
            counterparty_name='供应商APM',
            transaction_time='2026-07-02 00:00:00+00',
        )
        bs.save()
        resp = self.client.post(
            f'/api/finance/bank-statements/{bs.pk}/match/',
            {
                'match_type': 'AP',
                'supplier_id': sup.pk,
                'ap_id': ap.pk,
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 409)
        ap.refresh_from_db()
        bs.refresh_from_db()
        self.assertEqual(ap.amount_paid, Decimal('0'))
        self.assertEqual(ap.status, 'PENDING')
        self.assertEqual(bs.status, 'PENDING')  # 未被标记 MATCHED
        self.assertIsNone(bs.related_ap_id)  # 未被关联
        self.assertFalse(Payment.objects.filter(ap=ap).exists())

    def test_match_ar_still_works(self):
        from apps.finance.models import AccountReceivable, BankStatement
        from apps.masterdata.models import Customer

        cust = Customer.objects.create(code='ARM', name='客户ARM')
        ar = AccountReceivable.objects.create(
            customer=cust, invoice_date='2026-06-01', due_date='2026-07-01', amount_due=Decimal('800.00')
        )
        bs = BankStatement(
            transaction_type='CREDIT',
            credit_amount=Decimal('800.00'),
            counterparty_name='客户ARM',
            transaction_time='2026-07-02 00:00:00+00',
        )
        bs.save()
        resp = self.client.post(
            f'/api/finance/bank-statements/{bs.pk}/match/',
            {
                'match_type': 'AR',
                'customer_id': cust.pk,
                'ar_id': ar.pk,
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        ar.refresh_from_db()
        bs.refresh_from_db()
        self.assertEqual(ar.amount_paid, Decimal('800.00'))
        self.assertEqual(ar.status, 'PAID')
        self.assertEqual(bs.status, 'MATCHED')
        self.assertTrue(Payment.objects.filter(ar=ar).exists())


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class SharedExpenseSignalTest(TestCase):
    """R2:公共费用分摊完成(ALLOCATED)自动登记台账;撤销分摊回收未核销台账项。"""

    def _make_expense(self, code='SESIG1', status='PENDING'):
        from apps.finance.models import SharedExpense
        return SharedExpense.objects.create(
            expense_no=code, name=f'办公费用-{code}', category='ADMIN',
            expense_date='2026-07-01', period_start='2026-07-01', period_end='2026-07-31',
            amount=Decimal('2400.00'), status=status,
        )

    def test_allocate_transition_registers_payable_item(self):
        exp = self._make_expense()
        self.assertFalse(PayableItem.objects.filter(source_type='shared_expense', source_id=exp.pk).exists())
        exp.status = 'ALLOCATED'
        exp.allocated_at = None
        exp.save()
        item = PayableItem.objects.get(source_type='shared_expense', source_id=exp.pk)
        self.assertEqual(item.amount_due, Decimal('2400.00'))
        self.assertEqual(item.payee_name, exp.name)
        self.assertEqual(item.status, PayableItem.STATUS_PENDING)

    def test_cancel_allocation_reverts_to_pending_cancels_item(self):
        exp = self._make_expense(code='SESIG2', status='ALLOCATED')
        item = PayableItem.objects.get(source_type='shared_expense', source_id=exp.pk)
        self.assertEqual(item.status, PayableItem.STATUS_PENDING)

        exp.status = 'PENDING'
        exp.save()
        item.refresh_from_db()
        self.assertEqual(item.status, PayableItem.STATUS_CANCELLED)

    def test_allocate_action_registers_via_api(self):
        from rest_framework.test import APIClient
        from apps.accounts.models import User
        from apps.masterdata.models import Customer
        from apps.projects.models import Project

        exp = self._make_expense(code='SESIG3')
        customer = Customer.objects.create(code='CUSESIG3', name='分摊测试客户')
        user = User.objects.create(username='seadmin', employee_id='SEA1', is_staff=True, is_superuser=True)
        project = Project.objects.create(code='PJSESIG3', name='分摊测试项目', customer=customer,
                                         manager=user, start_date='2026-07-01', end_date='2026-12-31')
        client = APIClient(); client.force_authenticate(user)
        resp = client.post(f'/api/finance/shared-expenses/{exp.pk}/allocate/',
                           {'project_ids': [project.pk]}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        exp.refresh_from_db()
        self.assertEqual(exp.status, 'ALLOCATED')
        self.assertTrue(PayableItem.objects.filter(source_type='shared_expense', source_id=exp.pk).exists())


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class TaxDeclarationSignalTest(TestCase):
    """R2:税务申报确认申报(DECLARED)自动登记台账。"""

    def _make_declaration(self, code='TDSIG1', status='APPROVED', tax_amount='2000.00'):
        from apps.finance.tax_management import TaxDeclaration, TaxPeriod, TaxType
        tt, _ = TaxType.objects.get_or_create(code='VATSIG', defaults={'name': '增值税(信号测试)'})
        tp = TaxPeriod.objects.create(period_type='MONTHLY', year=2026, period=8,
                                      start_date='2026-08-01', end_date='2026-08-31',
                                      declare_deadline='2026-09-15')
        return TaxDeclaration.objects.create(
            declaration_no=code, tax_period=tp, tax_type=tt,
            declaration_type='VAT', status=status, tax_amount=Decimal(tax_amount),
        )

    def test_declare_transition_registers_payable_item(self):
        td = self._make_declaration()
        self.assertFalse(PayableItem.objects.filter(source_type='tax', source_id=td.pk).exists())
        td.status = 'DECLARED'
        td.save()
        item = PayableItem.objects.get(source_type='tax', source_id=td.pk)
        self.assertEqual(item.amount_due, Decimal('2000.00'))
        self.assertEqual(item.payee_name, '税务局')
        self.assertEqual(item.status, PayableItem.STATUS_PENDING)

    def test_declare_action_registers_via_api(self):
        from rest_framework.test import APIClient
        from apps.accounts.models import User

        td = self._make_declaration(code='TDSIG2')
        user = User.objects.create(username='taxadmin', employee_id='TXA1', is_staff=True, is_superuser=True)
        client = APIClient(); client.force_authenticate(user)
        resp = client.post(f'/api/finance/tax-declarations/{td.pk}/declare/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        td.refresh_from_db()
        self.assertEqual(td.status, 'DECLARED')
        self.assertTrue(PayableItem.objects.filter(source_type='tax', source_id=td.pk).exists())

    def test_cancelled_transition_cancels_payable_item(self):
        """G5:register_tax_payable 目前没有实际操作入口能把 DECLARED 变成
        CANCELLED(TaxDeclaration.STATUS_CHOICES 里也没有这个取值),但信号本身要
        为将来预留的 CANCELLED 分支做好——直接置状态验证信号行为,不依赖视图。"""
        td = self._make_declaration(code='TDSIG3', status='DECLARED')
        item = PayableItem.objects.get(source_type='tax', source_id=td.pk)
        self.assertEqual(item.status, PayableItem.STATUS_PENDING)

        td.status = 'CANCELLED'
        td.save()
        item.refresh_from_db()
        self.assertEqual(item.status, PayableItem.STATUS_CANCELLED)

    def test_cancelled_transition_does_not_touch_paid_item(self):
        """已核销(amount_paid>0)的台账项不应被误冲——与 cancel_payable 的通用守卫
        语义一致。"""
        td = self._make_declaration(code='TDSIG4', status='DECLARED')
        item = PayableItem.objects.get(source_type='tax', source_id=td.pk)
        item.amount_paid = item.amount_due
        item.recalc_status()
        item.save()

        td.status = 'CANCELLED'
        td.save()
        item.refresh_from_db()
        self.assertEqual(item.status, PayableItem.STATUS_PAID)


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class PaymentRequestSignalTest(TestCase):
    """R2:独立付款申请(无挂靠 AP)审批通过(APPROVED)自动登记台账;取消则作废。
    有挂靠 AP 的付款申请跳过登记,避免与该 AP 的 source_type='ap' 台账项双记。"""

    def _make_request(self, code='PRSIG1', status='PENDING', ap=None, amount='1800.00'):
        from apps.accounts.models import User
        from apps.finance.models import PaymentRequest
        from apps.masterdata.models import Supplier
        sup = Supplier.objects.create(code=code, name=f'供应商{code}')
        applicant = User.objects.create(username=f'app{code}'.lower(), employee_id=f'APP{code}')
        return PaymentRequest.objects.create(
            request_no=code, title='预付款申请', supplier=sup, amount=Decimal(amount),
            expected_date='2026-08-01', reason='测试', applicant=applicant, status=status, ap=ap,
        )

    def test_approve_transition_registers_when_no_ap(self):
        pr = self._make_request()
        self.assertFalse(PayableItem.objects.filter(source_type='payment_request', source_id=pr.pk).exists())
        pr.status = 'APPROVED'
        pr.save()
        item = PayableItem.objects.get(source_type='payment_request', source_id=pr.pk)
        self.assertEqual(item.amount_due, Decimal('1800.00'))
        self.assertEqual(item.status, PayableItem.STATUS_PENDING)

    def test_approve_skips_registration_when_ap_linked(self):
        # 通过挂靠一张已存在的 AP 来验证不重复登记(该 AP 自身经 register_ap_payable
        # 已登记为 source_type='ap')。
        from apps.masterdata.models import Supplier
        from apps.finance.models import AccountPayable
        sup = Supplier.objects.create(code='PRSIG2AP', name='供应商PRSIG2AP')
        ap = AccountPayable.objects.create(supplier=sup, invoice_date='2026-07-01',
                                           due_date='2026-08-01', amount_due=Decimal('1800.00'))
        self.assertTrue(PayableItem.objects.filter(source_type='ap', source_id=ap.pk).exists())

        pr = self._make_request(code='PRSIG2', ap=ap)
        pr.status = 'APPROVED'
        pr.save()
        self.assertFalse(PayableItem.objects.filter(source_type='payment_request', source_id=pr.pk).exists())

    def test_cancel_cancels_item(self):
        pr = self._make_request(code='PRSIG3', status='APPROVED')
        item = PayableItem.objects.get(source_type='payment_request', source_id=pr.pk)
        self.assertEqual(item.status, PayableItem.STATUS_PENDING)

        pr.status = 'CANCELLED'
        pr.save()
        item.refresh_from_db()
        self.assertEqual(item.status, PayableItem.STATUS_CANCELLED)


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class AssetMaintenanceAdapterTest(TestCase):
    """资产维护:AssetMaintenance.status 是处理进度机(PENDING/IN_PROGRESS/COMPLETED/
    CANCELLED),无付款语义,write_back 为 no-op(付款事实由统一台账维护),同 Outsource/
    SharedExpense 断言不破坏其状态机。"""

    def _make_maintenance(self):
        from apps.accounts.models import User
        from apps.oa.asset import Asset, AssetMaintenance
        reporter = User.objects.create(username='amrep', employee_id='AMREP1')
        asset = Asset.objects.create(asset_no='AST-AM1', name='测试台架', status='REPAIR')
        return AssetMaintenance.objects.create(
            maintenance_no='AM001', asset=asset, maintenance_type='REPAIR',
            reporter=reporter, fault_description='电机异响',
            start_date='2026-07-01', end_date='2026-07-03',
            cost=Decimal('800.00'), status='COMPLETED',
        )

    def test_asset_maintenance_register_and_writeback_is_noop(self):
        from apps.finance.payable_adapters import PAYABLE_SOURCES, register_payable
        m = self._make_maintenance()
        item = register_payable(m, 'asset_maintenance')
        self.assertIsNone(item.supplier_id)
        self.assertEqual(item.payee_name, '')
        self.assertEqual(item.amount_due, Decimal('800.00'))
        self.assertEqual(item.source_no, 'AM001')

        item.amount_paid = Decimal('800.00')
        item.recalc_status()
        item.save()
        PAYABLE_SOURCES['asset_maintenance'].write_back(m, item)
        m.refresh_from_db()
        self.assertEqual(m.status, 'COMPLETED')  # no-op:处理进度机不受付款影响

        # 反核销(台账退回未结清),no-op 仍不应改动源单据状态。
        item.amount_paid = Decimal('0')
        item.recalc_status()
        item.save()
        PAYABLE_SOURCES['asset_maintenance'].write_back(m, item)
        m.refresh_from_db()
        self.assertEqual(m.status, 'COMPLETED')


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class VehicleMaintenanceAdapterTest(TestCase):
    """车辆维护:VehicleMaintenance 无 status/付款字段,write_back 为 no-op(付款事实由
    统一台账维护);payee_name 取服务商 vendor,source_no 用 VM<pk>。"""

    def _make_maintenance(self):
        from apps.oa.vehicle import Vehicle, VehicleMaintenance
        vehicle = Vehicle.objects.create(plate_number='沪A12345', brand='测试品牌', model='X1')
        return VehicleMaintenance.objects.create(
            vehicle=vehicle, maintenance_type='REPAIR', maintenance_date='2026-07-02',
            description='更换刹车片', cost=Decimal('1200.00'), vendor='城东4S店',
        )

    def test_vehicle_maintenance_register_and_writeback_is_noop(self):
        from apps.finance.payable_adapters import PAYABLE_SOURCES, register_payable
        m = self._make_maintenance()
        item = register_payable(m, 'vehicle_maintenance')
        self.assertIsNone(item.supplier_id)
        self.assertEqual(item.payee_name, '城东4S店')
        self.assertEqual(item.amount_due, Decimal('1200.00'))
        self.assertEqual(item.source_no, f'VM{m.pk}')

        # write_back no-op:不改动源单据、不报错。
        item.amount_paid = Decimal('1200.00')
        item.recalc_status()
        item.save()
        PAYABLE_SOURCES['vehicle_maintenance'].write_back(m, item)
        m.refresh_from_db()
        self.assertEqual(m.cost, Decimal('1200.00'))
        self.assertEqual(m.vendor, '城东4S店')


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class Phase2BackfillCommandTest(TestCase):
    """测试 backfill_phase2_payables 命令:
    1. tax/shared_expense 全量应付状态回填
    2. payment_request 仅回填独立申请(ap=null)
    3. outsource 不回填(其应付已随AP回填)
    4. 幂等性:重复运行不重复建项
    """

    def setUp(self):
        from apps.masterdata.models import Supplier
        from apps.accounts.models import User
        self.supplier = Supplier.objects.create(code='BKFILL', name='回填供应商')
        self.user = User.objects.create(username='bkfill_op', employee_id='BKFILL1')

    def _run_backfill_command(self):
        from django.core.management import call_command
        call_command('backfill_phase2_payables')

    # --------- SharedExpense (公共费用) ---------

    def test_backfill_shared_expense_only_allocated(self):
        """回填 ALLOCATED 的公共费用，跳过 DRAFT/PENDING/CANCELLED"""
        from apps.finance.models import SharedExpense
        from apps.finance.payable_models import PayableItem

        # 应付:ALLOCATED
        allocated = SharedExpense.objects.create(
            name='房租-2026年7月', category='RENT',
            expense_date='2026-07-01', period_start='2026-07-01', period_end='2026-07-31',
            amount=Decimal('10000'), status='ALLOCATED',
        )

        # 不应付:DRAFT/PENDING/CANCELLED
        draft = SharedExpense.objects.create(
            name='水电-2026年7月', category='UTILITIES',
            expense_date='2026-07-01', period_start='2026-07-01', period_end='2026-07-31',
            amount=Decimal('5000'), status='DRAFT',
        )
        pending = SharedExpense.objects.create(
            name='物业-2026年7月', category='ADMIN',
            expense_date='2026-07-01', period_start='2026-07-01', period_end='2026-07-31',
            amount=Decimal('3000'), status='PENDING',
        )
        cancelled = SharedExpense.objects.create(
            name='维修-2026年7月', category='OTHER',
            expense_date='2026-07-01', period_start='2026-07-01', period_end='2026-07-31',
            amount=Decimal('2000'), status='CANCELLED',
        )

        self._run_backfill_command()

        # 应付的应被回填
        self.assertEqual(
            PayableItem.objects.filter(source_type='shared_expense', source_id=allocated.pk).count(), 1
        )

        # 不应付的不应被回填
        self.assertEqual(
            PayableItem.objects.filter(source_type='shared_expense', source_id=draft.pk).count(), 0
        )
        self.assertEqual(
            PayableItem.objects.filter(source_type='shared_expense', source_id=pending.pk).count(), 0
        )
        self.assertEqual(
            PayableItem.objects.filter(source_type='shared_expense', source_id=cancelled.pk).count(), 0
        )

    def test_backfill_shared_expense_idempotent(self):
        """回填命令幂等性:重复运行同一费用只生成1条台账项"""
        from apps.finance.models import SharedExpense
        from apps.finance.payable_models import PayableItem

        exp = SharedExpense.objects.create(
            name='房租-2026年7月', category='RENT',
            expense_date='2026-07-01', period_start='2026-07-01', period_end='2026-07-31',
            amount=Decimal('10000'), status='ALLOCATED',
        )

        self._run_backfill_command()
        count_after_first = PayableItem.objects.filter(source_type='shared_expense', source_id=exp.pk).count()
        self.assertEqual(count_after_first, 1)

        # 再运行一次
        self._run_backfill_command()
        count_after_second = PayableItem.objects.filter(source_type='shared_expense', source_id=exp.pk).count()
        self.assertEqual(count_after_second, 1)

    # --------- TaxDeclaration (缴税) ---------

    def test_backfill_tax_only_declared(self):
        """回填 DECLARED 的申报单，跳过 DRAFT/SUBMITTED/PAID/REJECTED"""
        from apps.finance.tax_management import TaxDeclaration, TaxPeriod, TaxType
        from apps.finance.payable_models import PayableItem

        tt = TaxType.objects.create(code='VAT', name='增值税')
        tp = TaxPeriod.objects.create(
            period_type='MONTHLY', year=2026, period=7,
            start_date='2026-07-01', end_date='2026-07-31',
            declare_deadline='2026-08-15',
        )

        # 应付:DECLARED
        declared = TaxDeclaration.objects.create(
            tax_period=tp, tax_type=tt, declaration_type='VAT',
            status='DECLARED', tax_amount=Decimal('5000'),
        )

        # 不应付:DRAFT/SUBMITTED/PAID/REJECTED
        draft = TaxDeclaration.objects.create(
            tax_period=tp, tax_type=tt, declaration_type='VAT',
            status='DRAFT', tax_amount=Decimal('2000'),
        )
        submitted = TaxDeclaration.objects.create(
            tax_period=tp, tax_type=tt, declaration_type='VAT',
            status='SUBMITTED', tax_amount=Decimal('1500'),
        )
        paid = TaxDeclaration.objects.create(
            tax_period=tp, tax_type=tt, declaration_type='VAT',
            status='PAID', tax_amount=Decimal('3000'),
        )
        rejected = TaxDeclaration.objects.create(
            tax_period=tp, tax_type=tt, declaration_type='VAT',
            status='REJECTED', tax_amount=Decimal('1000'),
        )

        self._run_backfill_command()

        # 应付的应被回填
        self.assertEqual(
            PayableItem.objects.filter(source_type='tax', source_id=declared.pk).count(), 1
        )

        # 不应付的不应被回填
        self.assertEqual(
            PayableItem.objects.filter(source_type='tax', source_id=draft.pk).count(), 0
        )
        self.assertEqual(
            PayableItem.objects.filter(source_type='tax', source_id=submitted.pk).count(), 0
        )
        self.assertEqual(
            PayableItem.objects.filter(source_type='tax', source_id=paid.pk).count(), 0
        )
        self.assertEqual(
            PayableItem.objects.filter(source_type='tax', source_id=rejected.pk).count(), 0
        )

    def test_backfill_tax_idempotent(self):
        """回填命令幂等性:重复运行同一申报单只生成1条台账项"""
        from apps.finance.tax_management import TaxDeclaration, TaxPeriod, TaxType
        from apps.finance.payable_models import PayableItem

        tt = TaxType.objects.create(code='VAT', name='增值税')
        tp = TaxPeriod.objects.create(
            period_type='MONTHLY', year=2026, period=7,
            start_date='2026-07-01', end_date='2026-07-31',
            declare_deadline='2026-08-15',
        )
        td = TaxDeclaration.objects.create(
            tax_period=tp, tax_type=tt, declaration_type='VAT',
            status='DECLARED', tax_amount=Decimal('5000'),
        )

        self._run_backfill_command()
        count_after_first = PayableItem.objects.filter(source_type='tax', source_id=td.pk).count()
        self.assertEqual(count_after_first, 1)

        # 再运行一次
        self._run_backfill_command()
        count_after_second = PayableItem.objects.filter(source_type='tax', source_id=td.pk).count()
        self.assertEqual(count_after_second, 1)

    # --------- PaymentRequest (付款申请) ---------

    def test_backfill_payment_request_only_independent_approved(self):
        """仅回填 APPROVED 且 ap=null 的独立申请，跳过:
        1. 其他状态(DRAFT/PENDING/PAID/等)
        2. 关联 AP 的申请(ap 不为null)
        """
        from apps.finance.models import PaymentRequest, AccountPayable
        from apps.finance.payable_models import PayableItem
        from apps.accounts.models import User
        from apps.masterdata.models import Supplier

        applicant = User.objects.create(username='applicant', employee_id='APP1')
        supplier2 = Supplier.objects.create(code='S2', name='供应商2')

        # 独立申请 APPROVED (应回填)
        independent_approved = PaymentRequest.objects.create(
            title='原料采购款', supplier=self.supplier, amount=Decimal('50000'),
            expected_date='2026-07-20', reason='原料', applicant=applicant,
            status='APPROVED', ap=None,
        )

        # 关联 AP 的申请 APPROVED (不回填，该AP已被backfill_payables覆盖)
        ap = AccountPayable.objects.create(
            supplier=supplier2, invoice_date='2026-07-01', due_date='2026-08-01',
            amount_due=Decimal('30000'),
        )
        related_approved = PaymentRequest.objects.create(
            title='进度款', supplier=supplier2, amount=Decimal('30000'),
            expected_date='2026-07-20', reason='进度', applicant=applicant,
            status='APPROVED', ap=ap,
        )

        # 独立申请 DRAFT (不回填，非应付状态)
        independent_draft = PaymentRequest.objects.create(
            title='运费', supplier=self.supplier, amount=Decimal('10000'),
            expected_date='2026-07-20', reason='运输', applicant=applicant,
            status='DRAFT', ap=None,
        )

        # 独立申请 PAID (不回填，已支付)
        independent_paid = PaymentRequest.objects.create(
            title='设备款', supplier=self.supplier, amount=Decimal('20000'),
            expected_date='2026-07-20', reason='设备', applicant=applicant,
            status='PAID', ap=None,
        )

        self._run_backfill_command()

        # 仅独立APPROVED应被回填
        self.assertEqual(
            PayableItem.objects.filter(source_type='payment_request', source_id=independent_approved.pk).count(), 1
        )

        # 其他都不应被回填
        self.assertEqual(
            PayableItem.objects.filter(source_type='payment_request', source_id=related_approved.pk).count(), 0,
            '关联AP的申请不应回填'
        )
        self.assertEqual(
            PayableItem.objects.filter(source_type='payment_request', source_id=independent_draft.pk).count(), 0
        )
        self.assertEqual(
            PayableItem.objects.filter(source_type='payment_request', source_id=independent_paid.pk).count(), 0
        )

    def test_backfill_payment_request_idempotent(self):
        """回填命令幂等性:重复运行同一请求只生成1条台账项"""
        from apps.finance.models import PaymentRequest
        from apps.finance.payable_models import PayableItem
        from apps.accounts.models import User

        applicant = User.objects.create(username='applicant2', employee_id='APP2')
        pr = PaymentRequest.objects.create(
            title='采购款', supplier=self.supplier, amount=Decimal('50000'),
            expected_date='2026-07-20', reason='原料采购', applicant=applicant,
            status='APPROVED', ap=None,
        )

        self._run_backfill_command()
        count_after_first = PayableItem.objects.filter(source_type='payment_request', source_id=pr.pk).count()
        self.assertEqual(count_after_first, 1)

        # 再运行一次
        self._run_backfill_command()
        count_after_second = PayableItem.objects.filter(source_type='payment_request', source_id=pr.pk).count()
        self.assertEqual(count_after_second, 1)

    def test_backfill_three_sources_together(self):
        """综合测试:三来源(shared_expense/tax/独立payment_request)混合回填"""
        from apps.finance.models import SharedExpense, PaymentRequest
        from apps.finance.tax_management import TaxDeclaration, TaxPeriod, TaxType
        from apps.finance.payable_models import PayableItem
        from apps.accounts.models import User

        # 创建各来源的应付单据
        exp = SharedExpense.objects.create(
            name='房租', category='RENT',
            expense_date='2026-07-01', period_start='2026-07-01', period_end='2026-07-31',
            amount=Decimal('10000'), status='ALLOCATED',
        )
        tt = TaxType.objects.create(code='VAT3', name='增值税')
        tp = TaxPeriod.objects.create(
            period_type='MONTHLY', year=2026, period=7,
            start_date='2026-07-01', end_date='2026-07-31',
            declare_deadline='2026-08-15',
        )
        td = TaxDeclaration.objects.create(
            tax_period=tp, tax_type=tt, declaration_type='VAT',
            status='DECLARED', tax_amount=Decimal('5000'),
        )
        applicant = User.objects.create(username='app', employee_id='APPX')
        pr = PaymentRequest.objects.create(
            title='采购', supplier=self.supplier, amount=Decimal('50000'),
            expected_date='2026-07-20', reason='采购款', applicant=applicant,
            status='APPROVED', ap=None,  # 独立申请
        )

        self._run_backfill_command()

        # 验证三个来源都被回填
        self.assertEqual(
            PayableItem.objects.filter(source_type='shared_expense', source_id=exp.pk).count(), 1
        )
        self.assertEqual(
            PayableItem.objects.filter(source_type='tax', source_id=td.pk).count(), 1
        )
        self.assertEqual(
            PayableItem.objects.filter(source_type='payment_request', source_id=pr.pk).count(), 1
        )

        # 验证总共3条台账项
        self.assertEqual(PayableItem.objects.count(), 3)


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class ExpenseSignalTest(TestCase):
    """G1:员工费用报销审批通过(APPROVED)自动登记台账;驳回(REJECTED)/工作流撤回
    退回草稿(DRAFT)作废未核销台账项。Expense 无供应商、不创建 AccountPayable,
    不存在与 register_ap_payable 双记的问题,可直接登记。"""

    def _make_expense(self, code, status='SUBMITTED', amount='600.00'):
        from apps.accounts.models import User
        from apps.finance.models import Expense
        user = User.objects.create(username=f'u{code}'.lower(), employee_id=f'U{code}')
        return Expense.objects.create(
            expense_no=code, user=user, expense_date='2026-07-01',
            category='TRAVEL', amount=Decimal(amount), status=status,
        )

    def test_approve_transition_registers_payable_item(self):
        exp = self._make_expense('EXPSIG1', status='SUBMITTED')
        self.assertFalse(PayableItem.objects.filter(source_type='expense', source_id=exp.pk).exists())

        exp.status = 'APPROVED'
        exp.save()

        item = PayableItem.objects.get(source_type='expense', source_id=exp.pk)
        self.assertEqual(item.amount_due, Decimal('600.00'))
        self.assertEqual(item.status, PayableItem.STATUS_PENDING)

    def test_reject_cancels_unsettled_item(self):
        exp = self._make_expense('EXPSIG2', status='APPROVED')
        item = PayableItem.objects.get(source_type='expense', source_id=exp.pk)
        self.assertEqual(item.status, PayableItem.STATUS_PENDING)

        exp.status = 'REJECTED'
        exp.save()
        item.refresh_from_db()
        self.assertEqual(item.status, PayableItem.STATUS_CANCELLED)

    def test_withdraw_to_draft_cancels_unsettled_item(self):
        """`WorkflowService.withdraw_workflow` 会把 EXPENSE 从 APPROVED 退回 DRAFT
        (见 apps.core.workflow.services._on_workflow_complete),此时应回收台账项。"""
        exp = self._make_expense('EXPSIG3', status='APPROVED')
        item = PayableItem.objects.get(source_type='expense', source_id=exp.pk)

        exp.status = 'DRAFT'
        exp.save()
        item.refresh_from_db()
        self.assertEqual(item.status, PayableItem.STATUS_CANCELLED)

    def test_cancel_does_not_touch_settled_item(self):
        exp = self._make_expense('EXPSIG4', status='APPROVED')
        item = PayableItem.objects.get(source_type='expense', source_id=exp.pk)
        item.amount_paid = item.amount_due
        item.recalc_status()
        item.save()
        self.assertEqual(item.status, PayableItem.STATUS_PAID)

        exp.status = 'REJECTED'
        exp.save()
        item.refresh_from_db()
        self.assertEqual(item.status, PayableItem.STATUS_PAID)

    def test_approve_action_registers_via_api(self):
        from rest_framework.test import APIClient
        from apps.accounts.models import User

        exp = self._make_expense('EXPSIG5', status='SUBMITTED')
        admin = User.objects.create(username='expsigadmin', employee_id='EXPSIGA1',
                                    is_staff=True, is_superuser=True)
        client = APIClient(); client.force_authenticate(admin)
        resp = client.post(f'/api/finance/expenses/{exp.pk}/approve/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        exp.refresh_from_db()
        self.assertEqual(exp.status, 'APPROVED')
        self.assertTrue(PayableItem.objects.filter(source_type='expense', source_id=exp.pk).exists())


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class ExpenseBackfillCommandTest(TestCase):
    """测试 backfill_expense_payables 命令:只回填 APPROVED,幂等。"""

    def _run_backfill_command(self):
        from django.core.management import call_command
        call_command('backfill_expense_payables')

    def test_backfill_only_approved(self):
        from apps.accounts.models import User
        from apps.finance.models import Expense

        user = User.objects.create(username='expbkfuser', employee_id='EXPBKF0')
        approved = Expense.objects.create(expense_no='EXPBKF1', user=user, expense_date='2026-07-01',
                                          category='TRAVEL', amount=Decimal('900.00'), status='APPROVED')
        draft = Expense.objects.create(expense_no='EXPBKF2', user=user, expense_date='2026-07-01',
                                       category='MEAL', amount=Decimal('100.00'), status='DRAFT')
        submitted = Expense.objects.create(expense_no='EXPBKF3', user=user, expense_date='2026-07-01',
                                           category='OFFICE', amount=Decimal('200.00'), status='SUBMITTED')
        rejected = Expense.objects.create(expense_no='EXPBKF4', user=user, expense_date='2026-07-01',
                                          category='OTHER', amount=Decimal('300.00'), status='REJECTED')
        paid = Expense.objects.create(expense_no='EXPBKF5', user=user, expense_date='2026-07-01',
                                      category='OTHER', amount=Decimal('400.00'), status='PAID')

        self._run_backfill_command()

        self.assertEqual(PayableItem.objects.filter(source_type='expense', source_id=approved.pk).count(), 1)
        self.assertEqual(PayableItem.objects.filter(source_type='expense', source_id=draft.pk).count(), 0)
        self.assertEqual(PayableItem.objects.filter(source_type='expense', source_id=submitted.pk).count(), 0)
        self.assertEqual(PayableItem.objects.filter(source_type='expense', source_id=rejected.pk).count(), 0)
        self.assertEqual(PayableItem.objects.filter(source_type='expense', source_id=paid.pk).count(), 0)

    def test_backfill_idempotent(self):
        from apps.accounts.models import User
        from apps.finance.models import Expense

        user = User.objects.create(username='expbkfuser2', employee_id='EXPBKF01')
        exp = Expense.objects.create(expense_no='EXPBKF6', user=user, expense_date='2026-07-01',
                                     category='TRAVEL', amount=Decimal('500.00'), status='APPROVED')

        self._run_backfill_command()
        count_after_first = PayableItem.objects.filter(source_type='expense', source_id=exp.pk).count()
        self.assertEqual(count_after_first, 1)

        self._run_backfill_command()
        count_after_second = PayableItem.objects.filter(source_type='expense', source_id=exp.pk).count()
        self.assertEqual(count_after_second, 1)
