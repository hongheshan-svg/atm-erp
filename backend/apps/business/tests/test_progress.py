from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.business.models import (
    Delivery,
    Entry,
    Payment,
    Project,
    PurchaseLine,
    PurchaseOrder,
    Reconciliation,
    Stock,
    StockMove,
    Task,
)
from apps.core.models import AuditLog

from .test_commercial_chain import BusinessFixtures


class ProgressTests(BusinessFixtures, TestCase):
    def setUp(self):
        self.setup_business()
        self.project = self.active_project()
        self.project.members.add(self.users['mechanical_engineer'], self.users['production_manager'])
        self.today = timezone.localdate()
        self.purchase = PurchaseOrder.objects.create(
            project=self.project,
            supplier=self.supplier,
            code='PROGRESS-PO',
            status='submitted',
            due_date=self.today - timedelta(days=1),
            created_by=self.users['purchaser'],
            note='内部价格9988',
        )
        self.line = PurchaseLine.objects.create(purchase=self.purchase, item=self.item, quantity=5, unit_price=9988)
        self.task = Task.objects.create(
            project=self.project,
            title='安装设备',
            kind='install',
            assignee=self.users['member'],
            due_date=self.today - timedelta(days=1),
            description='内部说明',
        )
        self.users['member'].display_name = '张师傅'
        self.users['member'].save()

    def get(self, role='member', category='tasks', status=200, **params):
        response = self.clients[role].get(
            f'/api/business/projects/{self.project.pk}/progress/', {'category': category, **params}
        )
        self.assertEqual(response.status_code, status, response.data)
        return response.data

    def test_participants_can_follow_other_departments_without_original_record_access(self):
        for role in ['member', 'mechanical_engineer', 'production_manager']:
            with self.subTest(role=role):
                result = self.get(role, 'purchases')
                self.assertEqual(result['results'][0]['status_label'], '待批准')
                self.assertIsNone(result['results'][0]['path'])
                self.assertEqual(
                    self.clients[role].get(f'/api/business/purchases/{self.purchase.pk}/').status_code, 403
                )
                body = str(result)
                for secret in ['unit_price', 'amount', 'hourly_cost', '9988', '内部说明', 'note', 'snapshot']:
                    self.assertNotIn(secret, body)

    def test_project_scope_and_membership_revocation(self):
        self.get('electrical_engineer', status=404)
        self.project.members.remove(self.users['member'])
        self.get('member', status=404)
        self.get('purchaser', 'purchases')  # existing cross-project operational scope remains available
        self.assertIsNotNone(self.get('purchaser', 'purchases')['results'][0]['path'])

    def test_sales_owner_reads_projection_only_and_not_supplier_payment_status(self):
        sale = self.project.sale
        sale.manager = self.users['sales_manager']
        sale.save()
        Entry.objects.create(
            project=self.project,
            purchase=self.purchase,
            kind='payable',
            title='机密供应商账款',
            amount=100,
            due_date=self.today,
        )
        result = self.get('sales_manager', 'entries')
        self.assertEqual(result['count'], 1)
        self.assertIsNone(result['results'][0]['path'])
        self.assertNotIn('机密供应商账款', str(result))
        self.assertEqual(
            self.clients['sales_manager'].get(f'/api/business/projects/{self.project.pk}/').status_code, 403
        )
        progress = self.clients['sales_manager'].get(f'/api/business/sales/{sale.pk}/progress/').data
        self.assertEqual(progress['progress_project'], self.project.pk)
        sale.manager = self.users['manager']
        sale.save()
        self.get('sales_manager', status=404)

    def test_candidate_approvers_respect_scope_roles_active_state_and_applicant_separation(self):
        submitter = self.users['purchase_manager']
        AuditLog.objects.create(
            actor=submitter, operation='purchase.submit', resource=f'purchaseorder:{self.purchase.pk}'
        )
        self.users['purchaser'].additional_roles = ['purchase_manager']
        self.users['purchaser'].save()
        extra = User.objects.create_user(username='extra', role='member', additional_roles=['purchase_manager'])
        inactive = User.objects.create_user(username='inactive', role='purchase_manager', is_active=False)
        outsider = User.objects.create_user(username='outside-manager', role='manager')
        row = self.get(category='purchases')['results'][0]
        ids = {person['id'] for person in row['handlers']}
        self.assertTrue({extra.pk, self.users['manager'].pk, self.users['admin'].pk} <= ids)
        self.assertFalse({submitter.pk, self.users['purchaser'].pk, inactive.pk, outsider.pk} & ids)
        self.assertEqual(row['handler_label'], '可审批人员')

    def test_task_names_deadlines_and_completion_are_live(self):
        row = self.get()['results'][0]
        self.assertEqual(row['handlers'][0]['name'], '张师傅')
        self.assertTrue(row['overdue'])
        self.task.status = 'done'
        self.task.save()
        self.assertEqual(self.get()['count'], 0)
        completed = self.get(state='all')['results'][0]
        self.assertFalse(completed['overdue'])
        self.assertEqual(completed['record'], {'status': 'done'})
        self.users['member'].is_active = False
        self.users['member'].save()
        self.assertFalse(self.get('manager', state='all')['results'][0]['handlers'][0]['active'])

    def test_duplicate_approver_names_are_disambiguated(self):
        for username in ['li-a', 'li-b']:
            User.objects.create_user(username=username, display_name='李经理', role='purchase_manager')
        names = [person['name'] for person in self.get(category='purchases')['results'][0]['handlers']]
        self.assertIn('李经理（账号：li-a）', names)
        self.assertIn('李经理（账号：li-b）', names)

    def test_quarantine_has_warehouse_contacts_and_no_false_delivery_overdue(self):
        self.purchase.status = 'approved'
        self.purchase.save()
        self.line.pending_quantity = 5
        self.line.save()
        row = self.get(category='purchases')['results'][0]
        self.assertEqual(row['status_label'], '已到货待检')
        self.assertEqual(row['handler_label'], '待检处理岗位')
        self.assertIn(self.users['warehouse'].pk, [person['id'] for person in row['handlers']])
        self.assertFalse(row['overdue'])

    def test_partial_quarantine_keeps_both_purchasing_and_warehouse_followup(self):
        self.purchase.status = 'approved'
        self.purchase.save()
        self.line.pending_quantity = 2
        self.line.save()
        row = self.get(category='purchases')['results'][0]
        self.assertEqual(row['handler_label'], '采购 / 待检跟进')
        ids = {person['id'] for person in row['handlers']}
        self.assertTrue({self.users['purchaser'].pk, self.users['warehouse'].pk} <= ids)
        self.assertTrue(row['overdue'])
        self.assertIn('另有未到货物料', row['hint'])

    def test_payment_dates_do_not_invent_maturity_before_receipt(self):
        entry = Entry.objects.create(
            project=self.project,
            purchase=self.purchase,
            kind='payable',
            title='机密款项',
            amount=100,
            due_date=self.today - timedelta(days=1),
        )
        row = next(row for row in self.get(category='entries')['results'] if row['id'] == entry.pk)
        self.assertEqual(row['status_label'], '待起算付款')
        self.assertIsNone(row['due_date'])
        self.assertFalse(row['overdue'])
        self.assertEqual(row['agreed_date'], entry.due_date)
        for secret in ['100.00', '机密款项', 'amount', 'balance', 'account']:
            self.assertNotIn(secret, str(row))

    def test_prepayment_approval_is_distinct_from_finance_and_excludes_applicant(self):
        entry = Entry.objects.create(
            project=self.project, purchase=self.purchase, kind='payable', title='采购', amount=100, due_date=self.today
        )
        Reconciliation.objects.create(
            entry=entry,
            kind='prepayment',
            status='draft',
            code='PRE-1',
            approved_amount=30,
            created_by=self.users['manager'],
        )
        row = next(row for row in self.get(category='entries')['results'] if row['id'] == entry.pk)
        self.assertEqual(row['status_label'], '预付款待核准')
        self.assertNotIn(self.users['manager'].pk, [person['id'] for person in row['handlers']])
        self.assertNotIn(self.users['purchase_manager'].pk, [person['id'] for person in row['handlers']])

    def test_received_payment_maturity_uses_receipts_and_net_payments(self):
        self.purchase.payment_term = 'cash'
        self.purchase.save()
        entry = Entry.objects.create(
            project=self.project,
            purchase=self.purchase,
            kind='payable',
            title='采购',
            amount=100,
            due_date=self.today + timedelta(days=30),
        )
        stock = Stock.objects.create(item=self.item, location='测试仓')
        received = self.today - timedelta(days=1)
        StockMove.objects.create(
            stock=stock,
            project=self.project,
            purchase_line=self.line,
            kind='receipt',
            quantity=1,
            value=40,
            received_date=received,
            reason='合格收货',
        )
        row = next(row for row in self.get(category='entries')['results'] if row['id'] == entry.pk)
        self.assertEqual(row['due_date'], received)
        self.assertTrue(row['overdue'])
        Payment.objects.create(entry=entry, amount=40, date=self.today)
        row = next(row for row in self.get(category='entries')['results'] if row['id'] == entry.pk)
        self.assertFalse(row['overdue'])
        self.assertEqual(row['status_label'], '待起算付款')
        self.assertIsNone(row['due_date'])

    def test_settled_and_refund_status_derive_from_original_payments(self):
        entry = self.project.entries.get(kind='receivable')
        Payment.objects.create(entry=entry, amount=entry.amount, date=self.today)
        self.assertEqual(self.get(category='entries')['count'], 0)
        row = self.get(category='entries', state='all')['results'][0]
        self.assertEqual(row['status_label'], '已结清')
        Payment.objects.create(entry=entry, amount=1, date=self.today)
        row = self.get(category='entries')['results'][0]
        self.assertEqual(row['record']['progress_status'], 'refund')

    def test_multiple_prepayment_applicants_can_review_each_others_requests(self):
        entry = self.project.entries.get(kind='receivable')
        for index, role in enumerate(['admin', 'manager']):
            Reconciliation.objects.create(
                entry=entry,
                code=f'PRE-MULTI-{index}',
                kind='prepayment',
                status='draft',
                approved_amount=30,
                created_by=self.users[role],
            )
        handlers = self.get(category='entries')['results'][0]['handlers']
        self.assertEqual({person['id'] for person in handlers}, {self.users['admin'].pk, self.users['manager'].pk})

    def test_delivery_uses_install_then_acceptance_assignee(self):
        delivery = Delivery.objects.create(
            project=self.project, code='PROGRESS-DEL', quantity=1, shipped_date=self.today
        )
        self.task.delivery = delivery
        self.task.save()
        Task.objects.create(
            project=self.project,
            delivery=delivery,
            kind='acceptance',
            title='验收',
            assignee=self.users['manager'],
            due_date=self.today + timedelta(days=1),
        )
        row = self.get(category='deliveries')['results'][0]
        self.assertEqual(row['handlers'][0]['name'], '张师傅')
        self.assertEqual(row['status_label'], '安装中')
        self.task.status = 'done'
        self.task.save()
        row = self.get(category='deliveries')['results'][0]
        self.assertEqual(row['handlers'][0]['id'], self.users['manager'].pk)
        self.assertEqual(row['status_label'], '待客户验收')

    def test_pagination_readonly_and_archived_rows(self):
        for index in range(3):
            Task.objects.create(
                project=self.project, title=f'任务{index}', kind='design', assignee=self.users['member']
            )
        before = AuditLog.objects.count()
        result = self.get(page_size=2, page=2)
        self.assertEqual(result['count'], 4)
        self.assertEqual(len(result['results']), 2)
        self.assertEqual(AuditLog.objects.count(), before)
        AuditLog.objects.create(actor=self.users['admin'], operation='record.delete', resource=f'task:{self.task.pk}')
        self.assertEqual(self.get()['count'], 3)
        self.get(category='unknown', status=400)
        self.get(page_size=1000, status=400)
        self.get(page='wrong', status=400)
        self.get(state='wrong', status=400)
        response = self.clients['member'].post(f'/api/business/projects/{self.project.pk}/progress/', {}, format='json')
        self.assertEqual(response.status_code, 403)
        response = self.clients['admin'].post(f'/api/business/projects/{self.project.pk}/progress/', {}, format='json')
        self.assertEqual(response.status_code, 405)
        self.assertEqual(APIClient().get(f'/api/business/projects/{self.project.pk}/progress/').status_code, 403)

    def test_closed_project_does_not_display_false_overdue(self):
        Project.objects.filter(pk=self.project.pk).update(status='closed')
        row = self.get()['results'][0]
        self.assertFalse(row['overdue'])
        self.assertIn('已结项', row['hint'])
