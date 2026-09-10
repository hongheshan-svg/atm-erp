from decimal import Decimal

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from apps.business.models import BankRecord, Document, Entry
from apps.business.services.finance import balance

from .test_commercial_chain import TODAY, BusinessFixtures


class SystemReliabilityTests(BusinessFixtures, TestCase):
    def setUp(self):
        self.setup_business()
        self.project = self.active_project(amount='100')

    def test_forecast_allows_budget_check_and_both_approval_paths(self):
        self.post(
            'manager',
            f'projects/{self.project.pk}/forecast/',
            {
                'remaining_materials': '0',
                'remaining_labor': '0',
                'remaining_expenses': '0',
                'expected_revision': 0,
                'reason': '估算',
            },
        )
        purchase = self.purchase(self.project, qty='1', approve=False)
        path = f'/api/business/purchases/{purchase.pk}/budget-check/'
        first = self.clients['manager'].get(path)
        second = self.clients['manager'].get(path)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.data['snapshot'], second.data['snapshot'])
        self.post('manager', f'purchases/{purchase.pk}/approve/')
        self.post(
            'manager',
            f'projects/{self.project.pk}/budget/',
            {
                'materials': '0',
                'labor': '0',
                'expenses': '0',
                'expected_revision': 0,
                'reason': '零预算',
            },
        )
        purchase = self.purchase(self.project, qty='1', approve=False)
        check = self.clients['manager'].get(f'/api/business/purchases/{purchase.pk}/budget-check/').data
        self.assertTrue(check['over_budget'])
        self.post(
            'admin',
            f'purchases/{purchase.pk}/approve-over-budget/',
            {
                'confirmed': True,
                'expected_snapshot': check['snapshot'],
                'reason': '批准例外',
            },
        )

    def test_amended_credit_survives_repeated_cancel_reopen_and_partial_payment(self):
        sale = self.project.sale
        entry = Entry.objects.get(project=self.project)
        doc = Document.objects.create(
            project=self.project,
            category='contract',
            file='protected/test',
            original_name='test.pdf',
            size=0,
            sha256='0' * 64,
        )
        self.post(
            'manager',
            f'sales/{sale.pk}/amend/',
            {
                'expected_updated_at': sale.updated_at.isoformat(),
                'reason': '减额',
                'date': TODAY,
                'document': doc.pk,
                'amount': '80',
                'equipment_quantity': 1,
                'warranty_months': 12,
                'credits': [{'entry': entry.pk, 'amount': '20'}],
            },
        )
        self.post('finance', f'entries/{entry.pk}/pay/', {'amount': '30', 'date': TODAY, 'reason': '部分到账'})
        for _ in range(2):
            self.post('manager', f'projects/{self.project.pk}/cancel/', {'reason': '取消'})
            entry.refresh_from_db()
            self.assertEqual(balance(entry), Decimal('-30'))
            self.post('manager', f'projects/{self.project.pk}/reopen/', {'reason': '重开'})
            entry.refresh_from_db()
            self.assertEqual(balance(entry), Decimal('50'))
            self.assertEqual(entry.credit_amount, Decimal('20'))
        self.post('finance', f'entries/{entry.pk}/pay/', {'amount': '51', 'date': TODAY, 'reason': '超额'}, status=409)

    def test_bank_list_query_count_is_bounded(self):
        BankRecord.objects.bulk_create(
            [
                BankRecord(date=TODAY, amount='10', account='audit', reference=str(i), counterparty='test')
                for i in range(100)
            ]
        )
        with CaptureQueriesContext(connection) as queries:
            response = self.clients['finance'].get('/api/business/bank-records/?page_size=100')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 100)
        self.assertLessEqual(len(queries), 6)
        self.assertEqual(response.data['results'][0]['matches'], [])
        self.assertEqual(response.data['results'][0]['returns'], [])
