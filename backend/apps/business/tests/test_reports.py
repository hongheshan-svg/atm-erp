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

    def test_entry_summary_shares_the_report_rule_and_the_entry_reader_boundary(self):
        self.purchase(self.project)
        Entry.objects.filter(project=self.project, kind='payable').update(
            due_date=timezone.localdate() - timedelta(days=1)
        )
        report = self.report()['summary']
        totals = self.clients['finance'].get('/api/business/entries/summary/')
        self.assertEqual(totals.status_code, 200, totals.data)
        for key in ['receivable', 'payable', 'overdue_receivable', 'overdue_payable', 'refund_out', 'refund_in']:
            self.assertEqual(totals.data[key], report[key], key)
        # 财务拿不到经营报表，收付款页头的余额卡片只能来自这个接口。
        self.assertEqual(self.clients['finance'].get('/api/business/reports/').status_code, 403)
        for role in ['purchaser', 'warehouse', 'member']:
            self.assertEqual(self.clients[role].get('/api/business/entries/summary/').status_code, 403)
        # 汇总跟着列表同一套筛选走，页头和表格看到的是同一批款项。
        filtered = self.clients['finance'].get(
            '/api/business/entries/summary/', {'project': self.project.pk, 'kind': 'payable'}
        )
        self.assertEqual(filtered.data['receivable'], '0.00')
        self.assertEqual(filtered.data['payable'], report['payable'])

    def test_entry_rows_carry_partner_and_settlement_status(self):
        purchase = self.purchase(self.project)
        Entry.objects.filter(project=self.project, kind='payable').update(
            due_date=timezone.localdate() - timedelta(days=1)
        )
        rows = self.clients['finance'].get('/api/business/entries/', {'project': self.project.pk}).data['results']
        payable = next(row for row in rows if row['kind'] == 'payable')
        self.assertEqual(payable['partner_name'], self.supplier.name)
        # 未到货的货款付不出去，过了约定日期也不算逾期；合格收货后该部分才逾期。
        self.assertEqual(payable['status'], 'open')
        self.post(
            'warehouse',
            f'purchases/{purchase.pk}/receive/',
            {'lines': [{'line': purchase.lines.get().pk, 'quantity': '1'}], 'reason': '到货'},
        )
        rows = self.clients['finance'].get('/api/business/entries/', {'project': self.project.pk}).data['results']
        payable = next(row for row in rows if row['kind'] == 'payable')
        self.assertEqual(payable['status'], 'overdue')
        receivable = next(row for row in rows if row['kind'] == 'receivable')
        self.assertEqual(receivable['partner_name'], self.project.customer.name)
        settled = Entry.objects.create(
            project=self.project,
            kind='expense',
            title='已结清费用',
            amount=10,
            credit_amount=10,
            due_date=timezone.localdate(),
        )
        detail = self.clients['finance'].get(f'/api/business/entries/{settled.pk}/').data
        self.assertEqual(detail['status'], 'closed')
        self.assertEqual(detail['partner_name'], '')

    def test_cost_commitments_balances_and_overdue_use_existing_facts(self):
        self.purchase(self.project)
        # Keep the payable due today: the shared fixture uses a fixed historical date.
        Entry.objects.filter(project=self.project, kind='payable').update(due_date=timezone.localdate())
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
