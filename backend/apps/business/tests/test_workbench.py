from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.business.models import Entry, Payment, Project, PurchaseOrder, Task

from .test_commercial_chain import BusinessFixtures


class WorkbenchTests(BusinessFixtures, TestCase):
    def setUp(self):
        self.setup_business()
        self.project = self.active_project()

    def get(self, role):
        response = self.clients[role].get('/api/business/workbench/')
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def test_personal_tasks_respect_scope_and_limit(self):
        for index in range(25):
            Task.objects.create(
                project=self.project, assignee=self.users['member'], kind='design', title=f'设计 {index}'
            )
        hidden = Project.objects.create(
            code='HIDDEN', name='未参与项目', customer=self.customer, manager=self.users['manager']
        )
        Task.objects.create(project=hidden, assignee=self.users['member'], kind='design', title='不能泄露')
        result = self.get('member')
        self.assertEqual(set(result), {'tasks'})
        self.assertEqual(result['tasks']['count'], 25)
        self.assertEqual(len(result['tasks']['results']), 20)
        self.assertTrue(all(task['project'] == self.project.pk for task in result['tasks']['results']))

    def test_approvals_receipts_and_own_drafts_are_role_specific(self):
        purchase = self.purchase(self.project, approve=False)
        PurchaseOrder.objects.create(
            code='D1',
            project=self.project,
            supplier=self.supplier,
            due_date=timezone.localdate(),
            created_by=self.users['purchaser'],
        )
        PurchaseOrder.objects.create(
            code='D2',
            project=self.project,
            supplier=self.supplier,
            due_date=timezone.localdate(),
            created_by=self.users['manager'],
        )
        self.assertEqual(self.get('manager')['approvals']['count'], 1)
        self.assertEqual(self.get('purchaser')['drafts']['count'], 1)
        self.assertEqual(self.get('warehouse')['receipts']['count'], 0)
        self.post('manager', f'purchases/{purchase.pk}/approve/')
        result = self.get('warehouse')
        self.assertEqual(result['receipts']['count'], 1)
        self.assertNotIn('unit_price', result['receipts']['results'][0]['lines'][0])
        self.assertNotIn('settlements', result)

    def test_due_balances_and_refunds_are_derived_from_payments(self):
        Entry.objects.all().update(due_date=timezone.localdate() + timedelta(days=30))
        entry = Entry.objects.create(
            project=self.project, kind='expense', title='待付', amount=100, due_date=timezone.localdate()
        )
        refund = Entry.objects.create(
            project=self.project,
            kind='expense',
            title='待退',
            amount=50,
            credit_amount=50,
            cancelled=True,
            due_date=timezone.localdate() + timedelta(days=30),
        )
        Payment.objects.create(entry=refund, amount=50, date=timezone.localdate(), reason='原付款')
        rows = self.get('finance')['settlements']
        self.assertEqual(rows['count'], 2)
        self.assertEqual({row['id'] for row in rows['results']}, {entry.pk, refund.pk})
        Payment.objects.create(entry=entry, amount=100, date=timezone.localdate(), reason='完成付款')
        Payment.objects.create(entry=refund, amount=-50, date=timezone.localdate(), reason='退款到账')
        self.assertEqual(self.get('finance')['settlements']['count'], 0)

    def test_cancelled_project_refund_remains_actionable(self):
        entry = self.project.entries.get()
        Payment.objects.create(entry=entry, amount=50, date=timezone.localdate(), reason='预收')
        self.post('manager', f'projects/{self.project.pk}/cancel/', {'reason': '客户取消'})
        result = self.get('finance')['settlements']
        self.assertEqual(result['count'], 1)
        self.assertEqual(result['results'][0]['balance'], '-50.00')
