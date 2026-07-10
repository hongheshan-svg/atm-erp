"""单据编号条件唯一约束(condition=Q(is_deleted=False))回归测试。

审计 P1/P2:关键单据编号原为全局 ``unique=True``,与软删除冲突——软删一行后,
其单号被永久占用,无法在新行中复用。整改将其改为部分唯一索引(仅未软删行内唯一),
使编号在软删后可被复用,同时仍禁止两条“活跃”行使用相同编号。

覆盖:
1. AccountReceivable.ar_no:软删旧行后,新行复用同一 ar_no -> 成功(无 IntegrityError)。
2. AccountReceivable.ar_no:两条活跃行使用相同 ar_no -> 仍被拒绝(IntegrityError)。
3. Payment.payment_no:软删后复用成功 + 两条活跃行重复被拒绝。

风格对齐 apps/finance/tests/test_gl_posting.py(TestCase + override_settings 关 ES 同步)。
无匹配会计期间时 GL 自动过账静默跳过,故本用例无需 seed 科目/会计期间。
"""

from datetime import date
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings


@override_settings(ELASTICSEARCH_DSL_AUTOSYNC=False)
class DocumentNumberReuseTest(TestCase):
    def setUp(self):
        from apps.masterdata.models import Customer

        self.customer = Customer.objects.create(code='NRC1', name='编号复用客户')

    # ---- helpers -----------------------------------------------------------
    def _make_ar(self, ar_no, amount=Decimal('100.00')):
        from apps.finance.models import AccountReceivable

        # 显式传入 ar_no,save() 只在为空时自动生成,故此处保持传入值不被覆盖。
        return AccountReceivable.objects.create(
            ar_no=ar_no,
            customer=self.customer,
            invoice_date=date(2026, 7, 10),
            due_date=date(2026, 8, 10),
            amount_due=amount,
        )

    def _make_payment(self, payment_no, ar, amount=Decimal('50.00')):
        from apps.finance.models import Payment

        return Payment.objects.create(
            payment_no=payment_no,
            payment_type='AR',
            ar=ar,
            payment_date=date(2026, 7, 15),
            payment_method='BANK_TRANSFER',
            amount=amount,
        )

    # ---- AccountReceivable.ar_no ------------------------------------------
    def test_ar_no_reusable_after_soft_delete(self):
        from apps.finance.models import AccountReceivable

        ar1 = self._make_ar('AR-REUSE-001')
        ar1.soft_delete()
        self.assertTrue(ar1.is_deleted)

        # 复用同一 ar_no 创建新的活跃行,不应抛 IntegrityError。
        ar2 = self._make_ar('AR-REUSE-001')
        self.assertFalse(ar2.is_deleted)
        self.assertNotEqual(ar1.pk, ar2.pk)

        # 默认管理器(过滤软删)下,该编号只对应新行。
        active = AccountReceivable.objects.filter(ar_no='AR-REUSE-001')
        self.assertEqual(active.count(), 1)
        self.assertEqual(active.first().pk, ar2.pk)

    def test_two_active_ar_no_still_rejected(self):
        self._make_ar('AR-DUP-001')
        # 两条活跃行使用相同 ar_no 仍必须被部分唯一索引拒绝。
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._make_ar('AR-DUP-001')

    # ---- Payment.payment_no -----------------------------------------------
    def test_payment_no_reusable_after_soft_delete(self):
        from apps.finance.models import Payment

        ar = self._make_ar('AR-PAY-001')
        pay1 = self._make_payment('PAY-REUSE-001', ar)
        pay1.soft_delete()
        self.assertTrue(pay1.is_deleted)

        pay2 = self._make_payment('PAY-REUSE-001', ar)
        self.assertFalse(pay2.is_deleted)
        self.assertNotEqual(pay1.pk, pay2.pk)

        active = Payment.objects.filter(payment_no='PAY-REUSE-001')
        self.assertEqual(active.count(), 1)
        self.assertEqual(active.first().pk, pay2.pk)

    def test_two_active_payment_no_still_rejected(self):
        ar = self._make_ar('AR-PAY-002')
        self._make_payment('PAY-DUP-001', ar)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._make_payment('PAY-DUP-001', ar)
