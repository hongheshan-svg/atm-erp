"""P1 财务修复回归测试。

覆盖三项 P1 修复 + 一项 P0 回归守卫:
1. AR/AP 单号并发安全生成(走 CodeRule 锁定计数行,格式保持不变)。
2. 收款记录(CollectionRecord)按"仅已确认"口径回算节点/计划,支持反确认/删除反向核销。
3. 会计期间关闭时把期末余额结转为下期期初(按余额方向取号)。
4. (P0 回归)Payment.soft_delete 仍能反核销 AR/AP 的已收(付)金额并回退状态。

风格对齐 apps/finance/tests/test_payable_ledger.py(TestCase + override_settings 关 ES 同步)。
"""

from decimal import Decimal

from django.test import TestCase, override_settings


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class ArApNumberConcurrencySafeTest(TestCase):
    """Item 1:AR/AP 单号生成改走 CodeRule 锁定计数行,连续创建产出不同的同形单号。"""

    def _make_customer(self, code='CN1'):
        from apps.masterdata.models import Customer

        return Customer.objects.create(code=code, name=f'客户{code}')

    def _make_supplier(self, code='SN1'):
        from apps.masterdata.models import Supplier

        return Supplier.objects.create(code=code, name=f'供应商{code}')

    def test_two_sequential_receivables_get_distinct_wellformed_numbers(self):
        from apps.core.code_rule_models import CodeRule
        from apps.finance.models import AccountReceivable

        cust = self._make_customer()
        ar1 = AccountReceivable.objects.create(
            customer=cust, invoice_date='2026-06-01', due_date='2026-07-01', amount_due=Decimal('1000.00')
        )
        ar2 = AccountReceivable.objects.create(
            customer=cust, invoice_date='2026-06-01', due_date='2026-07-01', amount_due=Decimal('2000.00')
        )

        # 格式保持不变:AR + YYYYMMDD(8) + 4 位日流水
        self.assertRegex(ar1.ar_no, r'^AR\d{12}$')
        self.assertRegex(ar2.ar_no, r'^AR\d{12}$')
        # 并发/连续创建互不相同(旧的 max+1 无锁写法在并发下会撞同号)
        self.assertNotEqual(ar1.ar_no, ar2.ar_no)
        # 走了锁定计数行的 CodeRule 路径(而非临时 max+1)
        self.assertTrue(CodeRule.objects.filter(rule_type='ACCOUNT_RECEIVABLE').exists())

    def test_two_sequential_payables_get_distinct_wellformed_numbers(self):
        from apps.core.code_rule_models import CodeRule
        from apps.finance.models import AccountPayable

        sup = self._make_supplier()
        ap1 = AccountPayable.objects.create(
            supplier=sup, invoice_date='2026-06-01', due_date='2026-07-01', amount_due=Decimal('1000.00')
        )
        ap2 = AccountPayable.objects.create(
            supplier=sup, invoice_date='2026-06-01', due_date='2026-07-01', amount_due=Decimal('2000.00')
        )

        self.assertRegex(ap1.ap_no, r'^AP\d{12}$')
        self.assertRegex(ap2.ap_no, r'^AP\d{12}$')
        self.assertNotEqual(ap1.ap_no, ap2.ap_no)
        self.assertTrue(CodeRule.objects.filter(rule_type='ACCOUNT_PAYABLE').exists())

    def test_explicit_number_is_respected(self):
        """显式给定单号时不覆盖(向后兼容既有直接赋号的调用方)。"""
        from apps.finance.models import AccountReceivable

        cust = self._make_customer(code='CN2')
        ar = AccountReceivable.objects.create(
            ar_no='AR-CUSTOM-001', customer=cust, invoice_date='2026-06-01',
            due_date='2026-07-01', amount_due=Decimal('10.00'),
        )
        self.assertEqual(ar.ar_no, 'AR-CUSTOM-001')


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class CollectionRecordConfirmedWritebackTest(TestCase):
    """Item 2:节点/计划已收金额仅统计已确认记录,反确认/删除可反向核销。"""

    def _setup_plan(self):
        from apps.finance.collection_models import CollectionMilestone, CollectionPlan
        from apps.masterdata.models import Customer

        cust = Customer.objects.create(code='COLC1', name='回款客户')
        plan = CollectionPlan.objects.create(name='回款计划', customer=cust, total_amount=Decimal('1000.00'))
        milestone = CollectionMilestone.objects.create(
            plan=plan, milestone_type='ADVANCE', name='预付款',
            planned_amount=Decimal('500.00'), planned_date='2026-07-01',
        )
        return plan, milestone

    def test_unconfirmed_record_not_counted(self):
        from apps.finance.collection_models import CollectionRecord

        plan, milestone = self._setup_plan()
        CollectionRecord.objects.create(
            milestone=milestone, collection_date='2026-07-05', amount=Decimal('300.00'), confirmed=False
        )
        milestone.refresh_from_db()
        plan.refresh_from_db()
        # 未确认收款不应计入已收(修复"草稿收款被当作已收")
        self.assertEqual(milestone.collected_amount, Decimal('0'))
        self.assertEqual(milestone.status, 'PENDING')
        self.assertEqual(plan.collected_amount, Decimal('0'))

    def test_confirm_writes_back_then_unconfirm_reverses(self):
        from apps.finance.collection_models import CollectionRecord

        plan, milestone = self._setup_plan()
        rec = CollectionRecord.objects.create(
            milestone=milestone, collection_date='2026-07-05', amount=Decimal('300.00'), confirmed=False
        )

        # 确认后计入
        rec.confirmed = True
        rec.save()
        milestone.refresh_from_db()
        plan.refresh_from_db()
        self.assertEqual(milestone.collected_amount, Decimal('300.00'))
        self.assertEqual(milestone.status, 'PARTIAL')
        self.assertEqual(plan.collected_amount, Decimal('300.00'))
        self.assertEqual(plan.status, 'IN_PROGRESS')

        # 反确认后回退(反向核销,幂等重算)
        rec.confirmed = False
        rec.save()
        milestone.refresh_from_db()
        plan.refresh_from_db()
        self.assertEqual(milestone.collected_amount, Decimal('0'))
        self.assertEqual(milestone.status, 'PENDING')
        self.assertEqual(plan.collected_amount, Decimal('0'))

    def test_reaching_planned_sets_collected_and_actual_date(self):
        from apps.finance.collection_models import CollectionRecord

        plan, milestone = self._setup_plan()
        CollectionRecord.objects.create(
            milestone=milestone, collection_date='2026-07-05', amount=Decimal('300.00'), confirmed=True
        )
        CollectionRecord.objects.create(
            milestone=milestone, collection_date='2026-07-06', amount=Decimal('250.00'), confirmed=True
        )
        milestone.refresh_from_db()
        plan.refresh_from_db()
        # 550 >= 500 -> COLLECTED
        self.assertEqual(milestone.collected_amount, Decimal('550.00'))
        self.assertEqual(milestone.status, 'COLLECTED')
        self.assertIsNotNone(milestone.actual_date)

    def test_soft_delete_reverses_writeback(self):
        from apps.finance.collection_models import CollectionRecord

        plan, milestone = self._setup_plan()
        rec = CollectionRecord.objects.create(
            milestone=milestone, collection_date='2026-07-05', amount=Decimal('300.00'), confirmed=True
        )
        milestone.refresh_from_db()
        self.assertEqual(milestone.collected_amount, Decimal('300.00'))

        rec.soft_delete()
        milestone.refresh_from_db()
        plan.refresh_from_db()
        self.assertEqual(milestone.collected_amount, Decimal('0'))
        self.assertEqual(milestone.status, 'PENDING')
        self.assertEqual(plan.collected_amount, Decimal('0'))

    def test_hard_delete_reverses_writeback(self):
        from apps.finance.collection_models import CollectionRecord

        plan, milestone = self._setup_plan()
        keep = CollectionRecord.objects.create(
            milestone=milestone, collection_date='2026-07-05', amount=Decimal('200.00'), confirmed=True
        )
        drop = CollectionRecord.objects.create(
            milestone=milestone, collection_date='2026-07-06', amount=Decimal('300.00'), confirmed=True
        )
        milestone.refresh_from_db()
        self.assertEqual(milestone.collected_amount, Decimal('500.00'))

        drop.delete()
        milestone.refresh_from_db()
        self.assertEqual(milestone.collected_amount, Decimal('200.00'))
        self.assertEqual(milestone.status, 'PARTIAL')
        self.assertTrue(keep.pk is not None)


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class PeriodCloseCarryForwardTest(TestCase):
    """Item 3:期间关闭时把期末余额按余额方向结转为下期期初。"""

    def setUp(self):
        from rest_framework.test import APIClient

        from apps.accounts.models import User
        from apps.finance.accounting import AccountCategory

        self.user = User.objects.create(username='closeadmin', employee_id='CLZ1', is_staff=True, is_superuser=True)
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.category = AccountCategory.objects.create(name='资产', code='CAT1', category_type='ASSET')

    def _account(self, code, direction):
        from apps.finance.accounting import ChartOfAccount

        return ChartOfAccount.objects.create(
            code=code, name=f'科目{code}', category=self.category, balance_direction=direction
        )

    def _period(self, year, period):
        from datetime import date

        from apps.finance.accounting import FiscalPeriod

        start = date(year, period, 1)
        end = date(year, period, 28)
        return FiscalPeriod.objects.create(year=year, period=period, start_date=start, end_date=end, status='OPEN')

    def _balance(self, account, period, **amounts):
        from apps.finance.accounting import AccountBalance

        return AccountBalance.objects.create(
            account=account, fiscal_period=period, created_by=self.user, **amounts
        )

    def test_close_carries_forward_opening_balances_by_direction(self):
        from apps.finance.accounting import AccountBalance

        p1 = self._period(2026, 7)
        p2 = self._period(2026, 8)

        acc_dr = self._account('1001', 'DEBIT')
        acc_cr = self._account('2001', 'CREDIT')
        acc_contra = self._account('1002', 'DEBIT')  # 借方科目跑出贷方净额

        # 借方科目:net = (1000-0)+(500-200) = 1300 -> 期初借 1300
        self._balance(
            acc_dr, p1,
            opening_debit=Decimal('1000.00'), opening_credit=Decimal('0'),
            period_debit=Decimal('500.00'), period_credit=Decimal('200.00'),
        )
        # 贷方科目:net = (800-0)+(300-100) = 1000 -> 期初贷 1000
        self._balance(
            acc_cr, p1,
            opening_debit=Decimal('0'), opening_credit=Decimal('800.00'),
            period_debit=Decimal('100.00'), period_credit=Decimal('300.00'),
        )
        # 借方科目反向:net = (100-0)+(0-400) = -300 -> 落到贷方 期初贷 300
        self._balance(
            acc_contra, p1,
            opening_debit=Decimal('100.00'), opening_credit=Decimal('0'),
            period_debit=Decimal('0'), period_credit=Decimal('400.00'),
        )

        resp = self.client.post(f'/api/finance/fiscal-periods/{p1.pk}/close/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        p1.refresh_from_db()
        self.assertEqual(p1.status, 'CLOSED')

        nb_dr = AccountBalance.objects.get(account=acc_dr, fiscal_period=p2)
        self.assertEqual(nb_dr.opening_debit, Decimal('1300.00'))
        self.assertEqual(nb_dr.opening_credit, Decimal('0'))
        self.assertEqual(nb_dr.closing_debit, Decimal('1300.00'))  # opening + 本期(0)

        nb_cr = AccountBalance.objects.get(account=acc_cr, fiscal_period=p2)
        self.assertEqual(nb_cr.opening_credit, Decimal('1000.00'))
        self.assertEqual(nb_cr.opening_debit, Decimal('0'))

        nb_contra = AccountBalance.objects.get(account=acc_contra, fiscal_period=p2)
        self.assertEqual(nb_contra.opening_credit, Decimal('300.00'))
        self.assertEqual(nb_contra.opening_debit, Decimal('0'))

    def test_close_without_next_period_is_safe(self):
        """下期不存在时不应报错,也不凭空建期间(仅跳过结转)。"""
        from apps.finance.accounting import AccountBalance

        p1 = self._period(2026, 7)  # 未创建 2026-08
        acc = self._account('1001', 'DEBIT')
        self._balance(acc, p1, opening_debit=Decimal('500.00'), period_debit=Decimal('100.00'))

        resp = self.client.post(f'/api/finance/fiscal-periods/{p1.pk}/close/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        p1.refresh_from_db()
        self.assertEqual(p1.status, 'CLOSED')
        # 未创建下期,不应产生任何新的余额行
        self.assertEqual(AccountBalance.objects.exclude(fiscal_period=p1).count(), 0)


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class PaymentSoftDeleteReversesArApTest(TestCase):
    """P0 回归守卫:Payment.soft_delete 仍反核销 AR/AP 的已收(付)金额并回退状态。"""

    def test_soft_delete_reverses_ar(self):
        from apps.finance.models import AccountReceivable, Payment
        from apps.masterdata.models import Customer

        cust = Customer.objects.create(code='PDR1', name='应收客户')
        ar = AccountReceivable.objects.create(
            customer=cust, invoice_date='2026-06-01', due_date='2026-07-01', amount_due=Decimal('1000.00')
        )
        pay = Payment.objects.create(
            payment_type='AR', ar=ar, payment_date='2026-07-05',
            payment_method='BANK_TRANSFER', amount=Decimal('400.00'),
        )
        ar.refresh_from_db()
        self.assertEqual(ar.amount_paid, Decimal('400.00'))
        self.assertEqual(ar.status, 'PARTIAL')

        pay.soft_delete()
        ar.refresh_from_db()
        self.assertEqual(ar.amount_paid, Decimal('0'))
        self.assertEqual(ar.status, 'PENDING')

    def test_soft_delete_reverses_ap(self):
        from apps.finance.models import AccountPayable, Payment
        from apps.masterdata.models import Supplier

        sup = Supplier.objects.create(code='PDP1', name='应付供应商')
        ap = AccountPayable.objects.create(
            supplier=sup, invoice_date='2026-06-01', due_date='2026-07-01', amount_due=Decimal('1000.00')
        )
        pay = Payment.objects.create(
            payment_type='AP', ap=ap, payment_date='2026-07-05',
            payment_method='BANK_TRANSFER', amount=Decimal('600.00'),
        )
        ap.refresh_from_db()
        self.assertEqual(ap.amount_paid, Decimal('600.00'))
        self.assertEqual(ap.status, 'PARTIAL')

        pay.soft_delete()
        ap.refresh_from_db()
        self.assertEqual(ap.amount_paid, Decimal('0'))
        self.assertEqual(ap.status, 'PENDING')

    def test_soft_delete_is_idempotent(self):
        from apps.finance.models import AccountReceivable, Payment
        from apps.masterdata.models import Customer

        cust = Customer.objects.create(code='PDR2', name='应收客户2')
        ar = AccountReceivable.objects.create(
            customer=cust, invoice_date='2026-06-01', due_date='2026-07-01', amount_due=Decimal('1000.00')
        )
        pay = Payment.objects.create(
            payment_type='AR', ar=ar, payment_date='2026-07-05',
            payment_method='BANK_TRANSFER', amount=Decimal('400.00'),
        )
        pay.soft_delete()
        pay.soft_delete()  # 二次软删除应为 no-op,不重复回退
        ar.refresh_from_db()
        self.assertEqual(ar.amount_paid, Decimal('0'))
