"""总账自动过账引擎 + 三大报表 回归测试。

覆盖:
1. 科目表种子 seed_standard_accounts 幂等(重复调用不重复插入)。
2. 应收账款新建 -> 恰好一张借贷平衡的 POSTED 凭证(借 1122 / 贷 6001),科目余额同步更新。
3. 收款(Payment 挂 AR)-> 收款凭证(借 1002 / 贷 1122)。
4. 应付账款(无 PO)新建 -> 费用凭证(借 6602 / 贷 2202)。
5. 过账后资产负债表平衡(资产 == 负债 + 权益)。
6. 利润表净利润 == 收入 - 费用。
7. 幂等:重复保存应收/重复调用 post_document 不重复过账。
8. 价税分离:来源单据带 tax_amount 时拆出 2221 应交税费分录。
9. 无匹配会计期间时静默跳过,绝不打断业务单据保存。

风格对齐 apps/finance/tests/test_p1_finance_fixes.py(TestCase + override_settings 关 ES 同步)。
"""

from datetime import date
from decimal import Decimal

from django.test import TestCase, override_settings


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class GLAutoPostingTest(TestCase):
    def setUp(self):
        from apps.finance.accounting import FiscalPeriod
        from apps.finance.posting import seed_standard_accounts
        from apps.masterdata.models import Customer, Supplier

        seed_standard_accounts()
        self.period = FiscalPeriod.objects.create(
            year=2026, period=7, start_date=date(2026, 7, 1), end_date=date(2026, 7, 31), status='OPEN'
        )
        self.customer = Customer.objects.create(code='GLC1', name='总账客户')
        self.supplier = Supplier.objects.create(code='GLS1', name='总账供应商')

    # ---- helpers -----------------------------------------------------------
    def _make_ar(self, amount, invoice_date='2026-07-10'):
        from apps.finance.models import AccountReceivable

        return AccountReceivable.objects.create(
            customer=self.customer, invoice_date=invoice_date, due_date='2026-08-10', amount_due=amount
        )

    def _make_ap(self, amount, invoice_date='2026-07-10'):
        from apps.finance.models import AccountPayable

        return AccountPayable.objects.create(
            supplier=self.supplier, invoice_date=invoice_date, due_date='2026-08-10', amount_due=amount
        )

    def _voucher(self, source_type, source_id):
        from apps.finance.accounting import JournalVoucher

        return JournalVoucher.objects.get(source_type=source_type, source_id=source_id, is_deleted=False)

    def _lines_by_code(self, voucher):
        return {ln.account.code: ln for ln in voucher.lines.filter(is_deleted=False)}

    # ---- tests -------------------------------------------------------------
    def test_seed_standard_accounts_is_idempotent(self):
        from apps.finance.accounting import AccountCategory, ChartOfAccount
        from apps.finance.posting import seed_standard_accounts

        # setUp already seeded once; a second call must not duplicate anything.
        result = seed_standard_accounts()
        self.assertEqual(result, {'categories': 0, 'accounts': 0})
        self.assertEqual(ChartOfAccount.objects.filter(is_deleted=False).count(), 8)
        self.assertEqual(ChartOfAccount.objects.filter(code='1122').count(), 1)
        # 5 个标准科目类别
        self.assertEqual(AccountCategory.objects.filter(is_deleted=False).count(), 5)

    def test_ar_invoice_creates_single_balanced_posted_voucher(self):
        ar = self._make_ar(Decimal('1000.00'))

        from apps.finance.accounting import AccountBalance, JournalVoucher

        self.assertEqual(
            JournalVoucher.objects.filter(source_type='AR_INVOICE', source_id=ar.pk).count(), 1
        )
        v = self._voucher('AR_INVOICE', ar.pk)
        self.assertEqual(v.status, 'POSTED')
        self.assertTrue(v.is_balanced)
        self.assertEqual(v.debit_total, Decimal('1000.00'))
        self.assertEqual(v.credit_total, Decimal('1000.00'))

        lines = self._lines_by_code(v)
        self.assertEqual(lines['1122'].debit_amount, Decimal('1000.00'))  # 借 应收账款
        self.assertEqual(lines['6001'].credit_amount, Decimal('1000.00'))  # 贷 主营业务收入
        self.assertNotIn('2221', lines)  # AR 无 tax_amount 字段 -> 不拆销项税
        # 辅助核算:客户挂在应收分录上
        self.assertEqual(lines['1122'].customer_id, self.customer.pk)

        # 科目余额已同步(1122 期末借方 = 1000)
        bal = AccountBalance.objects.get(account__code='1122', fiscal_period=self.period)
        self.assertEqual(bal.closing_debit, Decimal('1000.00'))

    def test_ar_receipt_payment_creates_receipt_voucher(self):
        from apps.finance.models import Payment

        ar = self._make_ar(Decimal('1000.00'))
        pay = Payment.objects.create(
            payment_type='AR', ar=ar, payment_date='2026-07-15',
            payment_method='BANK_TRANSFER', amount=Decimal('400.00'),
        )
        v = self._voucher('AR_RECEIPT', pay.pk)
        self.assertEqual(v.status, 'POSTED')
        self.assertTrue(v.is_balanced)
        lines = self._lines_by_code(v)
        self.assertEqual(lines['1002'].debit_amount, Decimal('400.00'))   # 借 银行存款
        self.assertEqual(lines['1122'].credit_amount, Decimal('400.00'))  # 贷 应收账款

        # AR 台账已收金额照常累加(自动过账不干扰业务字段)
        ar.refresh_from_db()
        self.assertEqual(ar.amount_paid, Decimal('400.00'))
        self.assertEqual(ar.status, 'PARTIAL')

    def test_ap_invoice_without_po_uses_expense_account(self):
        ap = self._make_ap(Decimal('500.00'))
        v = self._voucher('AP_INVOICE', ap.pk)
        self.assertEqual(v.status, 'POSTED')
        self.assertTrue(v.is_balanced)
        lines = self._lines_by_code(v)
        self.assertIn('6602', lines)  # 无 PO -> 管理费用
        self.assertNotIn('1405', lines)
        self.assertEqual(lines['6602'].debit_amount, Decimal('500.00'))
        self.assertEqual(lines['2202'].credit_amount, Decimal('500.00'))
        self.assertEqual(lines['2202'].supplier_id, self.supplier.pk)

    def test_balance_sheet_balances_after_posting(self):
        from apps.finance.financial_statements import balance_sheet

        self._make_ar(Decimal('1000.00'))  # 借 1122 / 贷 6001
        self._make_ap(Decimal('300.00'))   # 借 6602 / 贷 2202

        bs = balance_sheet(self.period)
        self.assertTrue(bs['is_balanced'])
        self.assertEqual(bs['assets_total'], Decimal('1000.00'))
        self.assertEqual(bs['liabilities_total'], Decimal('300.00'))
        # 未结转损益(1000-300=700)并入权益
        self.assertEqual(bs['equity_total'], Decimal('700.00'))
        self.assertEqual(bs['assets_total'], bs['liabilities_and_equity_total'])

    def test_income_statement_net_equals_revenue_minus_expense(self):
        from apps.finance.financial_statements import income_statement

        self._make_ar(Decimal('1000.00'))  # revenue 6001
        self._make_ap(Decimal('300.00'))   # expense 6602

        inc = income_statement(period=self.period)
        self.assertEqual(inc['revenue_total'], Decimal('1000.00'))
        self.assertEqual(inc['expense_total'], Decimal('300.00'))
        self.assertEqual(inc['net_profit'], Decimal('700.00'))

    def test_cash_flow_reflects_receipt(self):
        from apps.finance.financial_statements import cash_flow
        from apps.finance.models import Payment

        ar = self._make_ar(Decimal('1000.00'))
        Payment.objects.create(
            payment_type='AR', ar=ar, payment_date='2026-07-15',
            payment_method='BANK_TRANSFER', amount=Decimal('400.00'),
        )
        cf = cash_flow('2026-07-01', '2026-07-31')
        self.assertEqual(cf['operating_inflow'], Decimal('400.00'))
        self.assertEqual(cf['net_cash_flow'], Decimal('400.00'))
        self.assertEqual(cf['closing_cash'], Decimal('400.00'))

    def test_reposting_is_idempotent(self):
        from apps.finance.accounting import JournalVoucher
        from apps.finance.posting import post_document

        ar = self._make_ar(Decimal('1000.00'))
        # 重复保存(created=False)不应再生成凭证
        ar.save()
        self.assertEqual(
            JournalVoucher.objects.filter(source_type='AR_INVOICE', source_id=ar.pk).count(), 1
        )
        # 直接再调用 post_document 返回已存在凭证,不新建
        existing = self._voucher('AR_INVOICE', ar.pk)
        again = post_document('AR_INVOICE', ar)
        self.assertEqual(again.pk, existing.pk)
        self.assertEqual(
            JournalVoucher.objects.filter(source_type='AR_INVOICE', source_id=ar.pk).count(), 1
        )

    def test_tax_amount_source_splits_2221_line(self):
        """来源单据带 tax_amount 时价税分离,拆出 2221 应交税费分录。

        AR/AP 现无 tax_amount 字段,用一个鸭子对象直接验证 _build_lines 的拆税分支。
        """
        import types

        from apps.finance.posting import _build_lines

        obj = types.SimpleNamespace(
            amount_due=Decimal('113.00'), tax_amount=Decimal('13.00'), customer=None, project=None, pk=999
        )
        lines = _build_lines('AR_INVOICE', obj)
        by_code = {ln['account'].code: ln for ln in lines}
        self.assertEqual(by_code['1122']['debit'], Decimal('113.00'))   # 价税合计
        self.assertEqual(by_code['6001']['credit'], Decimal('100.00'))  # 不含税收入
        self.assertEqual(by_code['2221']['credit'], Decimal('13.00'))   # 销项税
        # 借贷平衡:1122 借 == 6001 贷 + 2221 贷
        self.assertEqual(
            by_code['1122']['debit'], by_code['6001']['credit'] + by_code['2221']['credit']
        )

    def test_no_matching_period_skips_without_breaking_document(self):
        from apps.finance.accounting import JournalVoucher
        from apps.finance.models import AccountReceivable

        # 2030 没有任何会计期间 -> 不生成凭证,但应收单本身照常保存(自动过账绝不打断业务)。
        ar = AccountReceivable.objects.create(
            customer=self.customer, invoice_date='2030-01-01', due_date='2030-02-01', amount_due=Decimal('50.00')
        )
        self.assertTrue(AccountReceivable.objects.filter(pk=ar.pk).exists())
        self.assertFalse(
            JournalVoucher.objects.filter(source_type='AR_INVOICE', source_id=ar.pk).exists()
        )
