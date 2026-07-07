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
