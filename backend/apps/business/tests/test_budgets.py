import uuid
from decimal import Decimal

from django.test import TestCase

from apps.business.models import Entry, Project, StockMove, Task, TimeEntry
from apps.core.models import ActionReceipt, AuditLog

from .test_commercial_chain import TODAY, BusinessFixtures


class BudgetTests(BusinessFixtures, TestCase):
    def setUp(self):
        self.setup_business()
        self.project = self.active_project()

    def budget(self, materials='500.00', labor='100.00', expenses='50.00', revision=0, role='manager', status=200):
        return self.post(
            role,
            f'projects/{self.project.pk}/budget/',
            {
                'materials': materials,
                'labor': labor,
                'expenses': expenses,
                'reason': '确认项目预算',
                'expected_revision': revision,
            },
            status=status,
        )

    def report(self, role='manager', status=200):
        response = self.clients[role].get(f'/api/business/projects/{self.project.pk}/cost-analysis/')
        self.assertEqual(response.status_code, status)
        return response.data

    def check(self, purchase):
        response = self.clients['manager'].get(f'/api/business/purchases/{purchase.pk}/budget-check/')
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def test_budget_versions_permissions_and_no_leak(self):
        self.assertFalse(self.report()['configured'])
        for role in ['purchaser', 'warehouse', 'member']:
            self.report(role, 403)
        for role in ['finance', 'purchaser', 'warehouse', 'member']:
            self.budget(role=role, status=403)
        self.budget()
        self.budget(materials='600', revision=0, status=409)
        self.budget(materials='-1', revision=1, status=400)
        self.budget(materials='NaN', revision=1, status=400)
        self.project.refresh_from_db()
        self.assertEqual(self.project.budget_materials, Decimal('500'))
        self.assertEqual(self.project.budget_revision, 1)
        self.assertEqual(AuditLog.objects.filter(operation='project.budget').count(), 1)
        self.assertEqual(self.report('finance')['budget_total'], '650.00')
        for role in ['purchaser', 'warehouse', 'member']:
            response = self.clients[role].get(f'/api/business/projects/{self.project.pk}/')
            self.assertNotIn('budget_materials', response.data)

    def test_unset_budget_is_distinct_from_zero_and_override_is_audited(self):
        first = self.purchase(self.project, qty='1')
        self.budget('0', '0', '0')
        purchase = self.purchase(self.project, qty='1', approve=False)
        key = str(uuid.uuid4())
        self.post('manager', f'purchases/{purchase.pk}/approve/', key=key, status=409)
        self.assertFalse(ActionReceipt.objects.filter(key=key).exists())
        self.assertFalse(Entry.objects.filter(purchase=purchase).exists())
        check = self.check(purchase)
        self.assertTrue(check['over_budget'])
        payload = {'reason': '客户交期确认，承担超额', 'confirmed': True, 'expected_snapshot': check['snapshot']}
        self.post('purchaser', f'purchases/{purchase.pk}/approve-over-budget/', payload, status=403)
        self.post(
            'manager', f'purchases/{purchase.pk}/approve-over-budget/', {**payload, 'confirmed': False}, status=400
        )
        self.post('manager', f'purchases/{purchase.pk}/approve-over-budget/', {**payload, 'reason': ''}, status=400)
        key = str(uuid.uuid4())
        self.post('manager', f'purchases/{purchase.pk}/approve-over-budget/', payload, status=403)
        self.post('admin', f'purchases/{purchase.pk}/approve-over-budget/', payload, key=key)
        self.post('admin', f'purchases/{purchase.pk}/approve-over-budget/', payload, key=key)
        self.assertEqual(Entry.objects.filter(purchase=purchase).count(), 1)
        self.assertEqual(Entry.objects.filter(purchase=first).count(), 1)
        self.assertEqual(self.report()['committed_total'], '200.00')
        log = AuditLog.objects.filter(operation='purchase.approve', resource=f'purchaseorder:{purchase.pk}').first()
        self.assertTrue(log.detail['over_budget'])
        self.assertEqual(log.detail['budget_check']['snapshot'], check['snapshot'])

    def test_commitments_receipt_cancellation_return_and_cash_do_not_double_count(self):
        self.budget()
        purchase = self.purchase(self.project)
        line = purchase.lines.get()
        self.assertEqual(self.report()['committed_total'], '500.00')
        entry = Entry.objects.get(purchase=purchase)
        self.post('finance', f'entries/{entry.pk}/pay/', {'amount': '500', 'date': TODAY, 'reason': '预付'})
        self.assertEqual(self.report()['committed_total'], '500.00')
        self.post(
            'warehouse',
            f'purchases/{purchase.pk}/receive/',
            {'location': '主仓', 'reason': '分批收货', 'lines': [{'line': line.pk, 'quantity': '2'}]},
        )
        report = self.report()
        self.assertEqual(report['committed_total'], '300.00')
        self.assertEqual(report['purchase_net'], '500.00')

        second = self.purchase(self.project, qty='1', approve=False)
        self.assertTrue(self.check(second)['over_budget'])
        self.post('manager', f'purchases/{second.pk}/approve/', status=409)
        self.post('purchaser', f'purchases/{purchase.pk}/cancel-remainder/', {'reason': '取消剩余'})
        self.assertEqual(self.report()['purchase_net'], '200.00')
        self.assertEqual(self.report()['committed_total'], '0.00')
        move = StockMove.objects.get(purchase_line=line, kind='receipt')
        self.post('warehouse', f'moves/{move.pk}/return-purchase/', {'quantity': '2', 'reason': '全部退货'})
        self.assertEqual(self.report()['purchase_net'], '0.00')
        self.assertEqual(self.report()['actual_total'], '0.00')

    def test_stale_over_budget_preview_and_closed_budget_edit_are_rejected(self):
        self.budget('10')
        purchase = self.purchase(self.project, qty='1', approve=False)
        check = self.check(purchase)
        self.budget('20', revision=1)
        self.post(
            'manager',
            f'purchases/{purchase.pk}/approve-over-budget/',
            {'reason': '批准', 'confirmed': True, 'expected_snapshot': check['snapshot']},
            status=409,
        )
        self.assertFalse(Entry.objects.filter(purchase=purchase).exists())
        Project.objects.filter(pk=self.project.pk).update(status='closed')
        self.budget('30', revision=2, status=409)

    def test_expenses_are_actual_even_unpaid_and_cancellation_releases_them(self):
        self.budget()
        expense = self.post(
            'finance',
            'entries/expense/',
            {'project': self.project.pk, 'title': '差旅', 'amount': '60', 'due_date': TODAY},
            status=201,
        )
        report = self.report()
        self.assertEqual(report['rows'][2]['actual'], '60.00')
        self.assertEqual(report['rows'][2]['committed'], '0.00')
        self.assertTrue(report['over_budget'])
        self.post('finance', f'entries/{expense["id"]}/cancel-expense/', {'reason': '取消差旅'})
        self.assertFalse(self.report()['over_budget'])

    def test_actual_material_and_labor_reuse_ledgers_without_counting_receipts_twice(self):
        self.budget()
        self.post(
            'manager',
            f'projects/{self.project.pk}/revise-bom/',
            {
                'expected_revision': self.bom_version(self.project.pk),
                'lines': [{'item': self.item.pk, 'quantity': '5'}],
            },
        )
        purchase = self.purchase(self.project)
        line = purchase.lines.get()
        self.post(
            'warehouse',
            f'purchases/{purchase.pk}/receive/',
            {'location': '主仓', 'reason': '收货', 'lines': [{'line': line.pk, 'quantity': '2'}]},
        )
        move = StockMove.objects.get(purchase_line=line, kind='receipt')
        self.post(
            'warehouse',
            'stocks/issue/',
            {'project': self.project.pk, 'stock': move.stock_id, 'quantity': '1', 'reason': '生产领料'},
        )
        report = self.report()
        self.assertEqual(report['rows'][0]['actual'], '100.00')
        self.assertEqual(report['rows'][0]['committed'], '300.00')
        self.assertEqual(report['rows'][0]['occupied'], '400.00')
        self.assertEqual(report['purchase_net'], '500.00')
        task = Task.objects.create(
            project=self.project, title='设计', kind='design', assignee=self.users['member'], due_date=TODAY
        )
        TimeEntry.objects.create(
            task=task,
            user=self.users['member'],
            date=TODAY,
            hours='2',
            hourly_cost='50',
            cost='100',
            reason='已记工时快照',
        )
        self.users['member'].hourly_cost = Decimal('999')
        self.users['member'].save(update_fields=['hourly_cost'])
        self.assertEqual(self.report()['rows'][1]['actual'], '100.00')

    def test_budget_replay_does_not_reset_later_revision(self):
        key = str(uuid.uuid4())
        payload = {'materials': '500', 'labor': '100', 'expenses': '50', 'reason': '初始预算', 'expected_revision': 0}
        self.post('manager', f'projects/{self.project.pk}/budget/', payload, key=key)
        self.budget(materials='600', revision=1)
        self.post('manager', f'projects/{self.project.pk}/budget/', payload, key=key)
        self.assertEqual(self.report()['budget_revision'], 2)
        self.assertEqual(self.report()['rows'][0]['budget'], '600.00')
