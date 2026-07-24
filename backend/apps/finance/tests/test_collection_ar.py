"""回款记录经"单一写口"回写应收的回归测试。

审计 P1:三套收款体系不统一,CollectionRecord 不回写 AR。
本用例守护的行为:确认收款记录后,经 Payment 唯一写口(Payment.save/soft_delete)
回写 AR.amount_paid 并重算状态;反确认/软删/硬删记录时经 Payment.soft_delete 反核销;
无 SO / 无唯一应收时只做聚合、不建 Payment、不崩溃;已建单幂等去重、不重复回写。

风格对齐 apps/finance/tests/test_p1_finance_fixes.py(TestCase + override_settings 关 ES 同步)。
"""

from decimal import Decimal

from django.test import TestCase, override_settings


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class CollectionRecordWritesBackToArTest(TestCase):
    """确认收款记录 -> 经单一写口回写应收;反确认/删除 -> 反核销。"""

    def _make_customer(self, code='CAR1'):
        from apps.masterdata.models import Customer

        return Customer.objects.create(code=code, name=f'客户{code}')

    def _make_so(self, customer):
        from apps.sales.models import SalesOrder

        return SalesOrder.objects.create(customer=customer, delivery_date='2026-08-01')

    def _make_ar(self, customer, so, amount='1000.00'):
        from apps.finance.models import AccountReceivable

        return AccountReceivable.objects.create(
            customer=customer,
            so=so,
            invoice_date='2026-06-01',
            due_date='2026-07-01',
            amount_due=Decimal(amount),
        )

    def _setup(self, with_so=True, ar_count=1):
        """构造 计划(可选挂 SO)+ 节点,并按需在该 SO 上建 ar_count 条应收。"""
        from apps.finance.collection_models import CollectionMilestone, CollectionPlan

        cust = self._make_customer()
        so = self._make_so(cust) if with_so else None
        ars = []
        if so is not None:
            for i in range(ar_count):
                ars.append(self._make_ar(cust, so, amount='1000.00'))

        plan = CollectionPlan.objects.create(
            name='回款计划', customer=cust, sales_order=so, total_amount=Decimal('1000.00')
        )
        milestone = CollectionMilestone.objects.create(
            plan=plan, milestone_type='ADVANCE', name='预付款',
            planned_amount=Decimal('500.00'), planned_date='2026-07-01',
        )
        return cust, so, ars, plan, milestone

    # ---- 正向:确认后经单一写口回写应收 ----

    def test_confirm_after_create_writes_back_to_ar(self):
        from apps.finance.collection_models import CollectionRecord
        from apps.finance.models import Payment

        cust, so, ars, plan, milestone = self._setup()
        ar = ars[0]

        rec = CollectionRecord.objects.create(
            milestone=milestone, collection_date='2026-07-05',
            amount=Decimal('300.00'), payment_method='BANK', confirmed=False,
        )
        # 未确认:不建 Payment,AR 不动
        self.assertIsNone(rec.payment_id)
        ar.refresh_from_db()
        self.assertEqual(ar.amount_paid, Decimal('0'))

        # 确认:经单一写口建一张 Payment,AR 已收增加、状态 PARTIAL
        rec.confirmed = True
        rec.save()

        payments = Payment.objects.filter(ar=ar, payment_type='AR')
        self.assertEqual(payments.count(), 1)
        pay = payments.first()
        self.assertEqual(pay.amount, Decimal('300.00'))
        self.assertEqual(pay.payment_method, 'BANK_TRANSFER')

        rec.refresh_from_db()
        self.assertEqual(rec.payment_id, pay.pk)

        ar.refresh_from_db()
        self.assertEqual(ar.amount_paid, Decimal('300.00'))
        self.assertEqual(ar.status, 'PARTIAL')

        # 节点/计划聚合仍按"仅已确认"口径保持
        milestone.refresh_from_db()
        self.assertEqual(milestone.collected_amount, Decimal('300.00'))
        self.assertEqual(milestone.status, 'PARTIAL')

    def test_confirmed_at_create_writes_back_to_ar(self):
        from apps.finance.collection_models import CollectionRecord
        from apps.finance.models import Payment

        cust, so, ars, plan, milestone = self._setup()
        ar = ars[0]

        rec = CollectionRecord.objects.create(
            milestone=milestone, collection_date='2026-07-05',
            amount=Decimal('400.00'), payment_method='CASH', confirmed=True,
        )

        self.assertEqual(Payment.objects.filter(ar=ar, payment_type='AR').count(), 1)
        rec.refresh_from_db()
        self.assertIsNotNone(rec.payment_id)
        ar.refresh_from_db()
        self.assertEqual(ar.amount_paid, Decimal('400.00'))
        self.assertEqual(ar.status, 'PARTIAL')

    # ---- 反向:反确认 / 软删 / 硬删 均经 Payment.soft_delete 反核销 ----

    def test_unconfirm_reverses_ar(self):
        from apps.finance.collection_models import CollectionRecord
        from apps.finance.models import Payment

        cust, so, ars, plan, milestone = self._setup()
        ar = ars[0]

        rec = CollectionRecord.objects.create(
            milestone=milestone, collection_date='2026-07-05',
            amount=Decimal('300.00'), confirmed=True,
        )
        ar.refresh_from_db()
        self.assertEqual(ar.amount_paid, Decimal('300.00'))
        pay_pk = rec.payment_id
        self.assertIsNotNone(pay_pk)

        # 反确认:所联 Payment 被软删,AR 回退到 0 / PENDING
        rec.confirmed = False
        rec.save()

        pay = Payment.all_objects.get(pk=pay_pk)
        self.assertTrue(pay.is_deleted)
        ar.refresh_from_db()
        self.assertEqual(ar.amount_paid, Decimal('0'))
        self.assertEqual(ar.status, 'PENDING')

    def test_soft_delete_record_reverses_ar(self):
        from apps.finance.collection_models import CollectionRecord
        from apps.finance.models import Payment

        cust, so, ars, plan, milestone = self._setup()
        ar = ars[0]

        rec = CollectionRecord.objects.create(
            milestone=milestone, collection_date='2026-07-05',
            amount=Decimal('300.00'), confirmed=True,
        )
        pay_pk = rec.payment_id
        ar.refresh_from_db()
        self.assertEqual(ar.amount_paid, Decimal('300.00'))

        rec.soft_delete()

        pay = Payment.all_objects.get(pk=pay_pk)
        self.assertTrue(pay.is_deleted)
        ar.refresh_from_db()
        self.assertEqual(ar.amount_paid, Decimal('0'))
        self.assertEqual(ar.status, 'PENDING')

    def test_hard_delete_record_reverses_ar(self):
        from apps.finance.collection_models import CollectionRecord
        from apps.finance.models import Payment

        cust, so, ars, plan, milestone = self._setup()
        ar = ars[0]

        rec = CollectionRecord.objects.create(
            milestone=milestone, collection_date='2026-07-05',
            amount=Decimal('300.00'), confirmed=True,
        )
        pay_pk = rec.payment_id
        ar.refresh_from_db()
        self.assertEqual(ar.amount_paid, Decimal('300.00'))

        rec.delete()

        pay = Payment.all_objects.get(pk=pay_pk)
        self.assertTrue(pay.is_deleted)
        ar.refresh_from_db()
        self.assertEqual(ar.amount_paid, Decimal('0'))
        self.assertEqual(ar.status, 'PENDING')

    # ---- 幂等:重复保存不重复回写 ----

    def test_idempotent_no_duplicate_payment_on_resave(self):
        from apps.finance.collection_models import CollectionRecord
        from apps.finance.models import Payment

        cust, so, ars, plan, milestone = self._setup()
        ar = ars[0]

        rec = CollectionRecord.objects.create(
            milestone=milestone, collection_date='2026-07-05',
            amount=Decimal('300.00'), confirmed=True,
        )
        first_pay_pk = rec.payment_id

        # 再次保存(仍已确认):不应重复建单 / 不应重复回写
        rec.notes = '补充备注'
        rec.save()
        rec.save()

        self.assertEqual(Payment.objects.filter(ar=ar, payment_type='AR').count(), 1)
        rec.refresh_from_db()
        self.assertEqual(rec.payment_id, first_pay_pk)
        ar.refresh_from_db()
        self.assertEqual(ar.amount_paid, Decimal('300.00'))

    def test_reconfirm_after_unconfirm_reapplies_ar(self):
        from apps.finance.collection_models import CollectionRecord
        from apps.finance.models import Payment

        cust, so, ars, plan, milestone = self._setup()
        ar = ars[0]

        rec = CollectionRecord.objects.create(
            milestone=milestone, collection_date='2026-07-05',
            amount=Decimal('300.00'), confirmed=True,
        )
        rec.confirmed = False
        rec.save()
        ar.refresh_from_db()
        self.assertEqual(ar.amount_paid, Decimal('0'))

        # 再次确认:老单已软删,应重新建一张有效 Payment 再回写
        rec.confirmed = True
        rec.save()

        ar.refresh_from_db()
        self.assertEqual(ar.amount_paid, Decimal('300.00'))
        self.assertEqual(ar.status, 'PARTIAL')
        self.assertEqual(Payment.objects.filter(ar=ar, payment_type='AR').count(), 1)

    # ---- 防御:无 SO / 歧义应收 只聚合不建单 ----

    def test_plan_without_so_no_payment(self):
        from apps.finance.collection_models import CollectionRecord
        from apps.finance.models import Payment

        cust, so, ars, plan, milestone = self._setup(with_so=False)

        rec = CollectionRecord.objects.create(
            milestone=milestone, collection_date='2026-07-05',
            amount=Decimal('300.00'), confirmed=True,
        )

        # 无 SO:不建 Payment、不崩溃,聚合照常
        self.assertIsNone(rec.payment_id)
        self.assertEqual(Payment.objects.count(), 0)
        milestone.refresh_from_db()
        self.assertEqual(milestone.collected_amount, Decimal('300.00'))
        self.assertEqual(milestone.status, 'PARTIAL')

    def test_ambiguous_ar_no_payment(self):
        from apps.finance.collection_models import CollectionRecord
        from apps.finance.models import Payment

        # 同一 SO 上两条应收 -> 歧义 -> 不建 Payment
        cust, so, ars, plan, milestone = self._setup(ar_count=2)

        rec = CollectionRecord.objects.create(
            milestone=milestone, collection_date='2026-07-05',
            amount=Decimal('300.00'), confirmed=True,
        )

        self.assertIsNone(rec.payment_id)
        self.assertEqual(Payment.objects.count(), 0)
        for ar in ars:
            ar.refresh_from_db()
            self.assertEqual(ar.amount_paid, Decimal('0'))
        # 聚合仍生效
        milestone.refresh_from_db()
        self.assertEqual(milestone.collected_amount, Decimal('300.00'))
