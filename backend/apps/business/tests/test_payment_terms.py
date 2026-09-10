import uuid
from datetime import date
from unittest.mock import patch

from django.test import TestCase

from apps.business.models import PurchaseOrder, StockMove
from apps.business.services import payment_terms, reports

from .test_commercial_chain import TODAY, BusinessFixtures


class PaymentTermsTests(BusinessFixtures, TestCase):
    def setUp(self):
        self.setup_business()
        self.project = self.active_project()

    def supplier_terms(self, term, days=30, status=200):
        result = self.clients['purchaser'].patch(
            f'/api/business/partners/{self.supplier.pk}/',
            {'payment_term': term, 'payment_days': days},
            format='json',
            HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
        )
        self.assertEqual(result.status_code, status, result.data)

    def receive(self, purchase, qty, received, **extra):
        self.post(
            'warehouse',
            f'purchases/{purchase.pk}/receive/',
            {
                'received_date': received,
                'lines': [{'line': purchase.lines.get().pk, 'quantity': qty, **extra}],
                'reason': '按实际日期收货',
            },
        )

    def detail(self, entry):
        response = self.clients['finance'].get(f'/api/business/entries/{entry.pk}/')
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def assert_workbench_maturity(self, entry, expected, today):
        with patch('django.utils.timezone.localdate', return_value=today):
            response = self.clients['finance'].get('/api/business/workbench/')
        self.assertEqual(response.status_code, 200, response.data)
        ids = {r['id'] for r in response.data['settlements']['results']}
        self.assertEqual(entry.pk in ids, expected)

    def test_month_end_calendar_including_leap_year_and_year_boundary(self):
        for start, days, end in [
            ('2026-09-01', 30, '2026-10-30'),
            ('2026-09-30', 60, '2026-11-29'),
            ('2024-02-03', 30, '2024-03-30'),
            ('2026-12-01', 90, '2027-03-31'),
        ]:
            self.assertEqual(str(payment_terms.due_date(date.fromisoformat(start), 'custom', days)), end)
        self.assertEqual(payment_terms.due_date(date(2026, 9, 5), 'cash', 0), date(2026, 9, 5))

    def test_supplier_default_is_frozen_and_unreceived_amount_has_no_maturity(self):
        self.supplier_terms('month30')
        purchase = self.purchase(self.project)
        self.assertEqual(purchase.payment_term, 'month30')
        self.supplier_terms('month90')
        purchase.refresh_from_db()
        self.assertEqual(purchase.payment_days, 30)
        detail = self.detail(purchase.entry)
        self.assertIsNone(detail['due_date'])
        self.assertEqual(detail['payment_schedule'], [])
        self.assertEqual(detail['balance'], '500.00')
        self.assert_workbench_maturity(purchase.entry, False, date(2026, 9, 1))
        self.receive(purchase, '2', '2026-07-10')
        detail = self.detail(purchase.entry)
        self.assertEqual(str(detail['due_date']), '2026-08-30')
        self.assertEqual(detail['payment_schedule'][0]['amount'], '200.00')
        self.assert_workbench_maturity(purchase.entry, False, date(2026, 8, 29))
        self.assert_workbench_maturity(purchase.entry, True, date(2026, 8, 30))

    def test_cross_month_partial_payment_return_and_reversal_reuse_source_facts(self):
        self.supplier_terms('month30')
        purchase = self.purchase(self.project)
        self.receive(purchase, '2', '2026-07-10')
        original = StockMove.objects.get(kind='receipt')
        self.receive(purchase, '3', '2026-08-10')
        entry = purchase.entry
        with patch('django.utils.timezone.localdate', return_value=date(2026, 9, 1)):
            detail = self.detail(entry)
            self.assertEqual([str(r['due_date']) for r in detail['payment_schedule']], ['2026-08-30', '2026-09-30'])
            self.assertEqual(detail['due_amount'], '200.00')
            result = reports.summary({})
            self.assertEqual(result['summary']['overdue_payable'], '200.00')
        statement = self.reconciliation_data(entry)
        payment = self.post(
            'finance',
            f'entries/{entry.pk}/pay/',
            {'amount': '250', 'date': TODAY, 'reason': '先抵扣较早到期', **statement},
        )
        detail = self.detail(entry)
        self.assertEqual(str(detail['due_date']), '2026-09-30')
        self.assertEqual(detail['payment_schedule'][0]['amount'], '250.00')
        self.assert_workbench_maturity(entry, False, date(2026, 9, 1))
        self.post('warehouse', f'moves/{original.pk}/return-purchase/', {'quantity': '1', 'reason': '原批次退货'})
        self.assertEqual(self.detail(entry)['payment_schedule'][0]['amount'], '150.00')
        self.post('finance', f'payments/{payment["id"]}/reverse/', {'date': TODAY, 'reason': '付款录入有误'})
        self.assertEqual([r['amount'] for r in self.detail(entry)['payment_schedule']], ['100.00', '300.00'])
        self.assert_workbench_maturity(entry, True, date(2026, 9, 1))

    def test_cash_and_quarantine_only_start_on_qualified_receipt(self):
        self.supplier_terms('cash')
        purchase = self.purchase(self.project)
        self.receive(purchase, '0', '2026-07-10', pending_quantity='5')
        self.assertIsNone(self.detail(purchase.entry)['due_date'])
        self.post(
            'warehouse',
            f'purchases/{purchase.pk}/quality-accept/',
            {
                'received_date': '2026-08-01',
                'lines': [{'line': purchase.lines.get().pk, 'quantity': '5'}],
                'reason': '合格确认',
            },
        )
        self.assertEqual(str(self.detail(purchase.entry)['due_date']), '2026-08-01')

    def test_validation_manual_compatibility_and_order_override(self):
        self.supplier_terms('custom', 366, 400)
        self.supplier_terms('custom', '30.5', 400)
        self.supplier_terms('unknown', 30, 400)
        self.supplier_terms('month60')
        data = {
            'project': self.project.pk,
            'supplier': self.supplier.pk,
            'due_date': TODAY,
            'payment_term': 'manual',
            'payment_due_date': '2026-12-15',
            'lines': [{'item': self.item.pk, 'quantity': '1', 'unit_price': '100'}],
        }
        result = self.post('purchaser', 'purchases/', data, status=201)
        purchase = PurchaseOrder.objects.get(pk=result['id'])
        self.assertEqual(purchase.payment_term, 'manual')
        self.assertEqual(str(purchase.payment_due_date), '2026-12-15')
        self.post('purchaser', 'purchases/', {**data, 'payment_term': 'month60'}, status=400)
