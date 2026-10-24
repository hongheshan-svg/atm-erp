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

    def test_sales_bucket_hides_closed_cancelled_and_removed_orders(self):
        from apps.business.models import SalesOrder
        from apps.core.models import AuditLog

        live = SalesOrder.objects.get(project=self.project)
        SalesOrder.objects.filter(pk=live.pk).update(manager=self.users['sales_manager'])
        closed_project = Project.objects.create(
            code='CLOSED', name='已结项', customer=self.customer, manager=self.users['manager'], status='closed'
        )
        cancelled_project = Project.objects.create(
            code='CANC', name='已取消', customer=self.customer, manager=self.users['manager'], status='cancelled'
        )
        closed = SalesOrder.objects.create(
            code='SO-C',
            name='结项单',
            customer=self.customer,
            project=closed_project,
            manager=self.users['sales_manager'],
        )
        cancelled = SalesOrder.objects.create(
            code='SO-X',
            name='取消项目单',
            customer=self.customer,
            project=cancelled_project,
            manager=self.users['sales_manager'],
        )
        removed = SalesOrder.objects.create(
            code='SO-R', name='已删除单', customer=self.customer, manager=self.users['sales_manager']
        )
        AuditLog.objects.create(
            actor=self.users['admin'], operation='record.delete', resource=f'salesorder:{removed.pk}', detail={}
        )
        open_quote = SalesOrder.objects.create(
            code='SO-Q', name='报价中', customer=self.customer, manager=self.users['sales_manager']
        )
        sales = self.get('sales_manager')['sales']
        ids = {row['id'] for row in sales['results']}
        self.assertIn(live.pk, ids)
        self.assertIn(open_quote.pk, ids)
        self.assertFalse(ids & {closed.pk, cancelled.pk, removed.pk})
        self.assertEqual(sales['count'], 2)

    def own_submitted_purchase(self, creator, submitter=None):
        from apps.core.models import AuditLog

        purchase = PurchaseOrder.objects.create(
            code=f'PO-{creator.username}',
            project=self.project,
            supplier=self.supplier,
            due_date=timezone.localdate(),
            status='submitted',
            created_by=creator,
        )
        AuditLog.objects.create(
            actor=submitter or creator, operation='purchase.submit', resource=f'purchaseorder:{purchase.pk}', detail={}
        )
        return purchase

    def test_approvals_exclude_own_requests_but_admin_sees_flagged_exception(self):
        from apps.core.models import AuditLog

        mine = self.own_submitted_purchase(self.users['manager'])
        by_purchaser = self.own_submitted_purchase(self.users['purchaser'])
        # 创建人是别人，但最近一次提交人是经理：经理同样不能审批。
        resubmitted = self.own_submitted_purchase(self.users['finance'], submitter=self.users['manager'])
        approvals = self.get('manager')['approvals']
        ids = {row['id'] for row in approvals['results']}
        self.assertEqual(ids, {by_purchaser.pk})
        self.assertEqual(approvals['count'], 1)
        self.post('manager', f'purchases/{by_purchaser.pk}/approve/')
        rows = {row['id']: row for row in self.get('admin')['approvals']['results']}
        self.assertEqual(set(rows), {mine.pk, resubmitted.pk})
        self.assertTrue(all(row['self_requested'] is False for row in rows.values()))
        AuditLog.objects.create(
            actor=self.users['admin'], operation='purchase.submit', resource=f'purchaseorder:{mine.pk}', detail={}
        )
        rows = {row['id']: row for row in self.get('admin')['approvals']['results']}
        self.assertTrue(rows[mine.pk]['self_requested'])
        self.assertFalse(rows[resubmitted.pk]['self_requested'])

    def test_prepayments_exclude_own_applications(self):
        from apps.business.models import Reconciliation

        entry = self.purchase(self.project).entry
        statement = self.post(
            'finance',
            'reconciliations/',
            {
                'entry': entry.pk,
                'kind': 'prepayment',
                'counterparty_balance': '500',
                'approved_amount': '100',
                'basis': '合同预付20%',
                'reason': '预付核准',
            },
            status=201,
        )['id']
        self.assertEqual(self.get('manager')['prepayments']['count'], 1)
        Reconciliation.objects.filter(pk=statement).update(created_by=self.users['manager'])
        self.assertNotIn('prepayments', self.get('manager'))
