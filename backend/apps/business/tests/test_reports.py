from datetime import timedelta

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.business.models import Entry, Payment, Project
from apps.business.services import budgets, reports

from .test_commercial_chain import BusinessFixtures


class ReportTests(BusinessFixtures, TestCase):
    def setUp(self):
        self.setup_business()
        self.project = self.active_project()

    def report(self, **params):
        response = self.clients['admin'].get('/api/business/reports/', params)
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def test_role_boundaries(self):
        for role in ['manager', 'finance', 'purchaser', 'warehouse', 'member']:
            self.assertEqual(self.clients[role].get('/api/business/reports/').status_code, 403)
        self.users['manager'].management_reports = True
        self.users['manager'].save()
        self.assertEqual(self.clients['manager'].get('/api/business/reports/').status_code, 200)

    def test_cost_commitments_balances_and_overdue_use_existing_facts(self):
        self.purchase(self.project)
        self.post(
            'manager',
            f'projects/{self.project.pk}/budget/',
            {'materials': '300', 'labor': '0', 'expenses': '50', 'reason': '预算', 'expected_revision': 0},
        )
        expense = Entry.objects.create(
            project=self.project,
            kind='expense',
            title='差旅',
            amount=50,
            due_date=timezone.localdate() - timedelta(days=1),
        )
        Payment.objects.create(entry=expense, amount=20, date=timezone.localdate(), reason='支付')
        self.project.due_date = timezone.localdate() - timedelta(days=1)
        self.project.save(update_fields=['due_date'])
        result = self.report()
        self.assertEqual(result['summary']['contract_amount'], '10000.00')
        self.assertEqual(result['summary']['actual_cost'], '50.00')
        self.assertEqual(result['summary']['committed_cost'], '500.00')
        self.assertEqual(result['summary']['payable'], '530.00')
        self.assertEqual(result['summary']['overdue_payable'], '30.00')
        self.assertEqual((result['summary']['over_budget'], result['summary']['overdue']), (1, 1))
        self.project.refresh_from_db()
        analysis = budgets.analysis(self.project)
        self.assertEqual(result['results'][0]['warnings'], analysis['warnings'])
        self.assertEqual(result['results'][0]['occupied_cost'], analysis['occupied_total'])
        Payment.objects.create(
            entry=expense, amount=-20, date=timezone.localdate(), reason='冲销', reversal_of=expense.payments.get()
        )
        self.assertEqual(self.report()['summary']['actual_cost'], '50.00')
        self.assertEqual(self.report()['summary']['payable'], '550.00')

    def test_cancelled_project_refunds_are_not_netted_against_other_balances(self):
        entry = self.project.entries.get()
        Payment.objects.create(entry=entry, amount=50, date=timezone.localdate(), reason='预收')
        self.post('manager', f'projects/{self.project.pk}/cancel/', {'reason': '取消'})
        result = self.report(status='cancelled')['summary']
        self.assertEqual(result['receivable'], '0.00')
        self.assertEqual(result['refund_out'], '50.00')
        Payment.objects.create(entry=entry, amount=-50, date=timezone.localdate(), reason='退回')
        self.assertEqual(self.report()['summary']['refund_out'], '0.00')

    def test_filters_empty_pagination_and_bounded_queries(self):
        for i in range(24):
            Project.objects.create(
                code=f'R{i}', name=f'筛选 {i}', customer=self.customer, manager=self.users['manager']
            )
        with CaptureQueriesContext(connection) as queries:
            result = reports.summary({'page': 2})
        self.assertLessEqual(len(queries), 8)
        self.assertEqual((result['count'], len(result['results']), result['summary']['projects']), (25, 5, 25))
        sized = self.report(page=2, page_size=10)
        self.assertEqual((sized['page_size'], len(sized['results'])), (10, 10))
        self.assertEqual(sized['summary'], result['summary'])
        self.assertEqual(self.report(status='draft')['count'], 24)
        self.assertEqual(self.report(search='R23')['count'], 1)
        self.assertEqual(self.report(risk='over_budget')['count'], 0)
        self.assertEqual(self.report(risk='unbudgeted')['count'], 25)
        empty = self.report(search='没有此项目')
        self.assertEqual(empty['summary']['actual_cost'], '0.00')
        self.assertEqual(empty['results'], [])
        for params in [{'page': 0}, {'page_size': 0}, {'page_size': 201}, {'status': 'unknown'}, {'risk': 'unknown'}]:
            self.assertEqual(self.clients['admin'].get('/api/business/reports/', params).status_code, 400)
        self.project.soft_delete(self.users['admin'])
        self.assertEqual(self.report()['summary']['contract_amount'], '0.00')
