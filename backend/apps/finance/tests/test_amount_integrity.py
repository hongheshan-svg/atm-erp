from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.finance.accounting import (
    FiscalPeriod,
    JournalVoucherSerializer,
)
from apps.finance.models import AccountReceivable, Invoice, Payment
from apps.finance.posting import seed_standard_accounts
from apps.finance.serializers import PaymentSerializer
from apps.masterdata.models import Customer


class FinanceAmountIntegrityTest(TestCase):
    def setUp(self):
        seed_standard_accounts()
        FiscalPeriod.objects.create(
            year=2026,
            period=7,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 31),
            status='OPEN',
        )
        self.customer = Customer.objects.create(code='FIN-AMOUNT-CUSTOMER', name='金额审计客户')

    def test_zero_tax_invoice_recalculates_total(self):
        invoice = Invoice.objects.create(
            invoice_type='OUTPUT',
            invoice_no='INV-ZERO-TAX',
            invoice_date='2026-07-10T00:00:00Z',
            party_name='金额审计客户',
            amount_before_tax=Decimal('100.00'),
            tax_amount=Decimal('13.00'),
            total_amount=Decimal('113.00'),
        )

        invoice.tax_amount = Decimal('0')
        invoice.save()

        invoice.refresh_from_db()
        self.assertEqual(invoice.total_amount, Decimal('100.00'))

    def test_payment_serializer_rejects_non_positive_and_over_collection(self):
        ar = AccountReceivable.objects.create(
            customer=self.customer,
            invoice_date=date(2026, 7, 10),
            due_date=date(2026, 8, 10),
            amount_due=Decimal('100.00'),
        )
        base = {
            'payment_type': 'AR',
            'ar': ar.id,
            'payment_date': '2026-07-15',
            'payment_method': 'BANK_TRANSFER',
        }

        negative = PaymentSerializer(data={**base, 'amount': '-1.00'})
        self.assertFalse(negative.is_valid())
        self.assertIn('amount', negative.errors)

        over = PaymentSerializer(data={**base, 'amount': '100.01'})
        self.assertFalse(over.is_valid())
        self.assertIn('amount', over.errors)

    def test_confirmed_payment_financial_fields_are_immutable(self):
        ar = AccountReceivable.objects.create(
            customer=self.customer,
            invoice_date=date(2026, 7, 10),
            due_date=date(2026, 8, 10),
            amount_due=Decimal('100.00'),
        )
        payment = Payment.objects.create(
            payment_type='AR',
            ar=ar,
            payment_date=date(2026, 7, 15),
            payment_method='BANK_TRANSFER',
            amount=Decimal('40.00'),
        )

        serializer = PaymentSerializer(payment, data={'amount': '50.00'}, partial=True)

        self.assertFalse(serializer.is_valid())
        self.assertIn('non_field_errors', serializer.errors)

    def test_posted_voucher_cannot_be_patched_back_to_approved(self):
        ar = AccountReceivable.objects.create(
            customer=self.customer,
            invoice_date=date(2026, 7, 10),
            due_date=date(2026, 8, 10),
            amount_due=Decimal('100.00'),
        )
        from apps.finance.accounting import JournalVoucher

        posted = JournalVoucher.objects.get(source_type='AR_INVOICE', source_id=ar.pk)
        serializer = JournalVoucherSerializer(posted, data={'status': 'APPROVED'}, partial=True)

        self.assertFalse(serializer.is_valid())
        self.assertIn('non_field_errors', serializer.errors)
