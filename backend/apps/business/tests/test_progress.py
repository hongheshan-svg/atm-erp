from datetime import timedelta

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
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
    TimeEntry,
)
from apps.business.services import reconciliation as statements
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

    def draft(self, entry, code, created_by, kind='prepayment'):
        # 真实草稿总带有生成时的原业务快照；空快照等同于原业务已变化。
        statement = Reconciliation(
            entry=Entry.objects.get(pk=entry.pk),
            kind=kind,
            status='draft',
            code=code,
            approved_amount=30,
            basis='合同约定',
            reason='核对原始业务',
            created_by=created_by,
        )
        statement.snapshot = statements.snapshot(statement)
        statement.save()
        return statement

    def entry_row(self, entry, role='member'):
        return next(row for row in self.get(role, 'entries')['results'] if row['id'] == entry.pk)

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

    def test_candidate_approvers_exclude_draft_amount_editors(self):
        # 草稿阶段改过数量或单价的人与审批动作同口径计入申请人，不能列为本单可审批人员。
        editor = User.objects.create_user(username='price-editor', role='purchase_manager')
        line = self.line
        AuditLog.objects.create(
            actor=editor,
            operation='purchase.edit',
            resource=f'purchaseorder:{self.purchase.pk}',
            detail={
                'before': [{'id': line.pk, 'quantity': '1', 'unit_price': '10'}],
                'after': {'lines': [{'id': line.pk, 'quantity': '1', 'unit_price': '95'}]},
            },
        )
        note_only = User.objects.create_user(username='note-editor', role='purchase_manager')
        AuditLog.objects.create(
            actor=note_only,
            operation='purchase.edit',
            resource=f'purchaseorder:{self.purchase.pk}',
            detail={
                'before': [{'id': line.pk, 'quantity': '1', 'unit_price': '10'}],
                'after': {'lines': [{'id': line.pk, 'quantity': '1.0', 'unit_price': '10.00'}]},
            },
        )
        ids = {person['id'] for person in self.get(category='purchases')['results'][0]['handlers']}
        self.assertNotIn(editor.pk, ids)
        self.assertIn(note_only.pk, ids)

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
        self.draft(entry, 'PRE-1', self.users['manager'])
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

    def entry_group(self, result):
        return next(group for group in result['groups'] if group['key'] == 'entries')

    def test_cancelled_project_receipt_stays_pending_refund_until_finance_returns_it(self):
        PurchaseOrder.objects.filter(pk=self.purchase.pk).update(status='cancelled')
        entry = self.project.entries.get(kind='receivable')
        self.post(
            'finance', f'entries/{entry.pk}/pay/', {'amount': '500.00', 'date': str(self.today), 'reason': '定金'}
        )
        self.post('manager', f'projects/{self.project.pk}/cancel/', {'reason': '客户终止'})
        entry.refresh_from_db()
        self.assertTrue(entry.cancelled)
        result = self.get('manager', 'entries')
        self.assertEqual((self.entry_group(result)['open'], result['count']), (1, 1))
        row = result['results'][0]
        self.assertEqual((row['status_label'], row['pending']), ('待退款', True))
        self.assertEqual(row['record']['progress_status'], 'refund')
        self.assertEqual(row['handler_label'], '财务跟进人员')
        self.assertIn(self.users['finance'].pk, [person['id'] for person in row['handlers']])
        self.assertIn('由财务办理退款', row['hint'])
        self.assertNotIn('重开', row['hint'])
        listed = self.clients['finance'].get(f'/api/business/entries/{entry.pk}/').data
        self.assertEqual((listed['status'], listed['balance']), ('refund', '-500.00'))

        # 退款只拦已结项；退回后余额为零，按已取消结束，不再计入待跟进。
        self.post(
            'finance',
            f'entries/{entry.pk}/refund/',
            {'amount': '500.00', 'date': str(self.today), 'reason': '退回定金', **self.reconciliation_data(entry)},
        )
        result = self.get('manager', 'entries', state='all')
        self.assertEqual(self.entry_group(result)['open'], 0)
        row = result['results'][0]
        self.assertEqual((row['status_label'], row['pending']), ('已取消', False))
        self.assertEqual(self.clients['finance'].get(f'/api/business/entries/{entry.pk}/').data['status'], 'cancelled')

    def test_cancelled_expense_with_payment_is_refund_not_finished(self):
        expense = self.post(
            'finance',
            'entries/expense/',
            {'project': self.project.pk, 'title': '差旅', 'amount': '500.00', 'due_date': str(self.today)},
            status=201,
        )
        self.post(
            'finance', f'entries/{expense["id"]}/pay/', {'amount': '200.00', 'date': str(self.today), 'reason': '付'}
        )
        self.post('finance', f'entries/{expense["id"]}/cancel-expense/', {'reason': '误报'})
        listed = self.clients['finance'].get(f'/api/business/entries/{expense["id"]}/').data
        self.assertEqual((listed['status'], listed['balance']), ('refund', '-200.00'))
        unpaid = self.post(
            'finance',
            'entries/expense/',
            {'project': self.project.pk, 'title': '未付费用', 'amount': '80.00', 'due_date': str(self.today)},
            status=201,
        )
        self.post('finance', f'entries/{unpaid["id"]}/cancel-expense/', {'reason': '误报'})
        self.assertEqual(
            self.clients['finance'].get(f'/api/business/entries/{unpaid["id"]}/').data['status'], 'cancelled'
        )

    def test_multiple_prepayment_applicants_can_review_each_others_requests(self):
        entry = self.project.entries.get(kind='receivable')
        for index, role in enumerate(['admin', 'manager']):
            self.draft(entry, f'PRE-MULTI-{index}', self.users[role])
        handlers = self.get(category='entries')['results'][0]['handlers']
        self.assertEqual({person['id'] for person in handlers}, {self.users['admin'].pk, self.users['manager'].pk})

    def test_stale_prepayment_draft_is_routed_to_finance_to_void_and_rebuild(self):
        purchase = BusinessFixtures.purchase(self, self.project)
        entry = Entry.objects.get(purchase=purchase)
        statement = self.post(
            'finance',
            'reconciliations/',
            {
                'entry': entry.pk,
                'kind': 'prepayment',
                'counterparty_balance': '500.00',
                'approved_amount': '150.00',
                'basis': '合同30%预付',
                'reason': '预付',
            },
            status=201,
        )
        row = self.entry_row(entry)
        self.assertEqual((row['status_label'], row['handler_label']), ('预付款待核准', '可核准人员'))
        self.assertIn(self.users['manager'].pk, [person['id'] for person in row['handlers']])

        self.post(
            'warehouse',
            f'purchases/{purchase.pk}/receive/',
            {
                'lines': [{'line': purchase.lines.get().pk, 'quantity': '1'}],
                'reason': '到一件',
            },
        )
        row = self.entry_row(entry)
        self.assertEqual(row['status_label'], '原业务已变化，待财务作废重建')
        self.assertEqual(row['handler_label'], '财务跟进人员')
        ids = {person['id'] for person in row['handlers']}
        self.assertIn(self.users['finance'].pk, ids)
        self.assertNotIn(self.users['manager'].pk, ids)
        self.assertIn('作废', row['hint'])
        # 经理此时确实无法核准，进度不能再把经理列为可核准人员。
        response = self.clients['manager'].post(
            f'/api/business/reconciliations/{statement["id"]}/confirm/',
            {'reason': '核准'},
            format='json',
            HTTP_IDEMPOTENCY_KEY='stale-prepayment-confirm',
        )
        self.assertEqual(response.status_code, 409)

        stale_settlement = self.draft(entry, 'SET-STALE', self.users['finance'], kind='settlement')
        Reconciliation.objects.filter(pk=stale_settlement.pk).update(snapshot={})
        self.post('finance', f'reconciliations/{statement["id"]}/void/', {'reason': '收货后重建'})
        row = self.entry_row(entry)
        self.assertEqual(row['status_label'], '原业务已变化，待财务作废重建')
        self.post('finance', f'reconciliations/{stale_settlement.pk}/void/', {'reason': '收货后重建'})
        self.assertNotIn('原业务已变化', self.entry_row(entry)['status_label'])

    def entry_queries(self, extra):
        for index in range(extra):
            entry = Entry.objects.create(
                project=self.project, kind='receivable', title=f'节点{extra}-{index}', amount=100, due_date=self.today
            )
            self.draft(entry, f'PRE-Q-{extra}-{index}', self.users['admin'])
        with CaptureQueriesContext(connection) as captured:
            result = self.get('manager', 'entries', page_size=50)
        self.assertTrue(all(row['status_label'] == '预付款待核准' for row in result['results'][1:]))
        return len(captured)

    def test_entry_draft_validity_is_checked_without_per_row_queries(self):
        self.get('manager', 'entries')
        self.assertEqual(self.entry_queries(3), self.entry_queries(9))

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

    def test_stopped_project_only_asks_to_reopen_for_unfinished_rows(self):
        done = Task.objects.create(
            project=self.project, title='已完成设计', kind='design', assignee=self.users['member'], status='done'
        )
        for status, label in [('closed', '已结项'), ('cancelled', '已取消')]:
            with self.subTest(status=status):
                Project.objects.filter(pk=self.project.pk).update(status=status)
                rows = {row['id']: row for row in self.get(state='all')['results']}
                self.assertIn(f'项目{label}', rows[self.task.pk]['hint'])
                self.assertIn('重开', rows[self.task.pk]['hint'])
                self.assertEqual(rows[done.pk]['hint'], '任务已结束，完成或取消记录保留。')

    def purchase_queries(self, total):
        for index in range(PurchaseOrder.objects.filter(project=self.project).count(), total):
            purchase = PurchaseOrder.objects.create(
                project=self.project,
                supplier=self.supplier,
                code=f'PROGRESS-PO-{index}',
                status='submitted',
                due_date=self.today,
                created_by=self.users['purchaser'],
            )
            PurchaseLine.objects.create(purchase=purchase, item=self.item, quantity=1, unit_price=1)
            for actor in ['manager', 'purchase_manager']:  # 以最近一次提交人为准
                AuditLog.objects.create(
                    actor=self.users[actor], operation='purchase.submit', resource=f'purchaseorder:{purchase.pk}'
                )
        with CaptureQueriesContext(connection) as captured:
            result = self.get('manager', 'purchases', page_size=50)
        self.assertEqual(len(result['results']), total)
        for row in result['results']:
            ids = {person['id'] for person in row['handlers']}
            self.assertEqual(self.users['purchase_manager'].pk in ids, row['id'] == self.purchase.pk)
        return len(captured)

    def test_purchase_submitters_are_loaded_once_per_page(self):
        self.get('manager', 'purchases')
        self.assertEqual(self.purchase_queries(20), self.purchase_queries(50))

    def test_same_or_blank_names_show_account_in_progress_and_lists(self):
        twin = User.objects.create_user(username='zhang-2', display_name='张师傅', role='member')
        self.project.members.add(twin)
        nameless = User.objects.create_user(username='nameless', role='member')
        self.project.members.add(nameless)
        Task.objects.create(project=self.project, title='调试', kind='design', assignee=twin)
        Task.objects.create(project=self.project, title='无名', kind='design', assignee=nameless)
        TimeEntry.objects.create(
            task=self.task, user=twin, date=self.today, hours=1, hourly_cost=0, cost=0, reason='工时'
        )
        expected = {'安装设备': '张师傅（账号：member）', '调试': '张师傅（账号：zhang-2）', '无名': 'nameless'}
        for active in (True, False):
            with self.subTest(twin_active=active):
                # 导入同样把停用人员计入重名，导出的姓名必须仍可唯一匹配。
                User.objects.filter(pk=twin.pk).update(is_active=active)
                result = self.get('manager', state='all')
                self.assertEqual(result['project']['manager']['name'], 'manager')
                names = {row['title'].split(' · ')[1]: row['handlers'][0]['name'] for row in result['results']}
                self.assertEqual(names, expected)
                listed = self.clients['manager'].get('/api/business/tasks/', {'project': self.project.pk}).data
                self.assertEqual({row['title']: row['assignee_name'] for row in listed['results']}, expected)
                project = self.clients['manager'].get(f'/api/business/projects/{self.project.pk}/').data
                self.assertEqual(project['manager_name'], 'manager')
                time = self.clients['manager'].get('/api/business/time/').data['results']
                self.assertEqual([row['user_name'] for row in time], ['张师傅（账号：zhang-2）'])
        User.objects.filter(pk=twin.pk).update(display_name='张工')
        listed = self.clients['manager'].get('/api/business/tasks/', {'project': self.project.pk}).data
        self.assertIn('张师傅', [row['assignee_name'] for row in listed['results']])

    def test_person_names_do_not_add_queries_per_row(self):
        def queries(extra):
            for index in range(extra):
                Task.objects.create(
                    project=self.project, title=f'任务{extra}-{index}', kind='design', assignee=self.users['member']
                )
            with CaptureQueriesContext(connection) as captured:
                response = self.clients['manager'].get('/api/business/tasks/', {'project': self.project.pk})
            self.assertEqual(response.status_code, 200)
            return len(captured)

        User.objects.create_user(username='zhang-2', display_name='张师傅', role='member')
        queries(0)
        self.assertEqual(queries(3), queries(9))

    def test_entry_rows_are_named_by_milestone_not_record_id(self):
        entry = self.project.entries.get(kind='receivable')
        self.assertTrue(entry.title)
        payable = Entry.objects.create(
            project=self.project,
            purchase=self.purchase,
            kind='payable',
            title='机密款项',
            amount=1,
            due_date=self.today,
        )
        rows = {row['id']: row['title'] for row in self.get('member', 'entries')['results']}
        self.assertEqual(rows[entry.pk], entry.title)
        self.assertEqual(rows[payable.pk], '采购 PROGRESS-PO')
        Entry.objects.filter(pk=entry.pk).update(title='')
        self.assertEqual(self.entry_row(entry)['title'], f'客户收款节点（到期日 {entry.due_date}）')

    def test_role_holders_are_listed_before_admin_only_candidates(self):
        admin = self.users['admin']
        row = self.get(category='purchases')['results'][0]
        ids = [person['id'] for person in row['handlers']]
        self.assertEqual(ids[-1], admin.pk)
        self.assertTrue({self.users['manager'].pk, self.users['purchase_manager'].pk} <= set(ids[:-1]))
        entry = self.project.entries.get(kind='receivable')
        ids = [person['id'] for person in self.entry_row(entry)['handlers']]
        self.assertEqual(ids, [self.users['finance'].pk, admin.pk])
        # 管理员兼任财务时按财务岗位人员排序，不再排在最后。
        admin.additional_roles = ['finance']
        admin.save()
        late = User.objects.create_user(username='finance-2', role='finance')
        ids = [person['id'] for person in self.entry_row(entry)['handlers']]
        self.assertEqual(ids, [admin.pk, self.users['finance'].pk, late.pk])
