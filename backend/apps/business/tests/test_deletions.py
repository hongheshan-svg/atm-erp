import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Event
from unittest.mock import patch

from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.business.models import (
    BankMatch,
    BankRecord,
    BOMLine,
    Delivery,
    Document,
    Entry,
    Item,
    Partner,
    Payment,
    PurchaseLine,
    PurchaseOrder,
    Reconciliation,
    SalesOrder,
    Stock,
    StockMove,
    Task,
    TimeEntry,
)
from apps.business.services.finance import balance, costs
from apps.core.models import ActionReceipt, AuditLog, Company

from .test_commercial_chain import BusinessFixtures


class DeletionTests(BusinessFixtures, TestCase):
    def setUp(self):
        self.setup_business()
        self.project = self.active_project()

    def remove(self, resource, ids, *, role='admin', reason='清理误建记录', status=200, key=None):
        return self.post(
            role, 'record-deletions/', {'resource': resource, 'ids': ids, 'reason': reason}, status=status, key=key
        )

    def listed(self, resource, role='admin'):
        response = self.clients[role].get(f'/api/business/{resource}/')
        self.assertEqual(response.status_code, 200, response.data)
        return {row['id'] for row in response.data['results']}

    def history(self, resource, **params):
        response = self.clients['admin'].get('/api/business/record-deletions/', {'resource': resource, **params})
        self.assertEqual(response.status_code, 200, response.data)
        return response.data['results']

    def assert_batch_rejected(self, resource, ids, *fragments):
        before = AuditLog.objects.filter(operation='record.delete').count()
        key = str(uuid.uuid4())
        detail = str(self.remove(resource, ids, status=409, key=key))
        for fragment in (*fragments, '整批未删除'):
            self.assertIn(fragment, detail)
        self.assertEqual(AuditLog.objects.filter(operation='record.delete').count(), before)
        self.assertFalse(ActionReceipt.objects.filter(key=key).exists())
        self.assertTrue(set(ids) <= self.listed(resource), '整批拒绝后已勾选记录仍在列表中')

    def settled_entry(self, title='已结清费用', amount='100'):
        entry = Entry.objects.create(
            project=self.project, kind='expense', title=title, amount=amount, due_date=timezone.localdate()
        )
        payment = Payment.objects.create(entry=entry, amount=amount, date=timezone.localdate(), reason='付清')
        return entry, payment

    def bank(self, reference, amount='10', **extra):
        return BankRecord.objects.create(
            project=self.project,
            amount=amount,
            date=timezone.localdate(),
            account='银行',
            reference=reference,
            counterparty='客户',
            reason='到账',
            **extra,
        )

    def test_batch_soft_delete_preserves_records_and_snapshots(self):
        second = Item.objects.create(code='I2', name='气缸')
        result = self.remove('items', [self.item.pk, second.pk])
        self.assertEqual(result['count'], 2)
        self.assertFalse(Item.objects.filter(pk__in=[self.item.pk, second.pk]).exists())
        self.assertEqual(Item.all_objects.filter(is_deleted=True).count(), 2)
        history = self.history('items')
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]['detail']['reason'], '清理误建记录')
        self.assertEqual(history[0]['detail']['record']['name'], '气缸')
        self.assertEqual(history[0]['actor_name'], 'admin')

    def test_reference_failure_rolls_back_whole_batch_and_receipt(self):
        unused = Partner.objects.create(code='EMPTY', name='未使用客户', kind='customer')
        # Sorting makes the unused row run before the referenced one.
        used = Partner.objects.create(code='USED', name='使用中客户', kind='customer')
        SalesOrder.objects.create(code='SO-USED', name='报价', customer=used, manager=self.users['manager'])
        key = str(uuid.uuid4())
        self.remove('partners', [unused.pk, used.pk], status=409, key=key)
        self.assertTrue(Partner.objects.filter(pk=unused.pk).exists())
        self.assertFalse(AuditLog.objects.filter(operation='record.delete').exists())
        self.assertFalse(ActionReceipt.objects.filter(key=key).exists())

    def test_permission_union_replay_and_role_revocation(self):
        self.remove('items', [self.item.pk], role='manager', status=403)
        actor = self.users['manager']
        actor.additional_roles = ['admin']
        actor.save()
        key = str(uuid.uuid4())
        first = self.remove('items', [self.item.pk], role='manager', key=key)
        self.assertEqual(self.remove('items', [self.item.pk], role='manager', key=key), first)
        self.assertEqual(len(self.history('items')), 1)
        actor.additional_roles = []
        actor.save()
        self.remove('items', [self.item.pk], role='manager', key=key, status=403)

    def test_permissions_and_payload_boundaries(self):
        for role in ['finance', 'warehouse', 'member', 'production_manager', 'purchase_manager']:
            with self.subTest(role=role):
                self.remove('items', [self.item.pk], role=role, status=403)
                response = self.clients[role].get('/api/business/record-deletions/', {'resource': 'items'})
                self.assertEqual(response.status_code, 403)
        for resource, ids, reason in [
            ('audit', [1], '原因'),
            ('items', [], '原因'),
            ('items', [True], '原因'),
            ('items', [self.item.pk] * 2, '原因'),
            ('items', list(range(1, 202)), '原因'),
            ('items', [self.item.pk], '  '),
        ]:
            with self.subTest(resource=resource, ids=len(ids)):
                self.remove(resource, ids, reason=reason, status=400)
        self.remove('items', [999999], status=409)

    def test_payment_entry_and_time_removal_never_changes_balances_or_costs(self):
        entry = Entry.objects.filter(project=self.project).first()
        # Only settled money can be archived; paying the whole balance keeps the ledger facts under test.
        payment = Payment.objects.create(entry=entry, amount=balance(entry), date=timezone.localdate(), reason='收款')
        task = Task.objects.create(project=self.project, title='装配', kind='assembly', assignee=self.users['member'])
        hours = TimeEntry.objects.create(
            task=task,
            user=self.users['member'],
            date=timezone.localdate(),
            hours='2',
            hourly_cost='30',
            cost='60',
            reason='装配',
        )
        before_balance, before_costs = balance(entry), costs([self.project.pk])
        for resource, obj in [('payments', payment), ('time', hours), ('entries', entry)]:
            self.remove(resource, [obj.pk])
            obj.refresh_from_db()
            self.assertFalse(obj.is_deleted)
            self.assertNotIn(obj.pk, self.listed(resource))
            self.assertEqual(len(self.history(resource, project=self.project.pk)), 1)
            self.assertEqual(self.clients['admin'].get(f'/api/business/{resource}/{obj.pk}/').status_code, 200)
        self.assertEqual(balance(entry), before_balance)
        self.assertEqual(costs([self.project.pk]), before_costs)
        summary = self.clients['admin'].get('/api/business/entries/summary/')
        self.assertEqual(summary.status_code, 200)
        self.assertTrue(Payment.objects.filter(pk=payment.pk).exists())

    def test_stock_moves_retained_zero_rows_reappear_after_new_stock(self):
        stock = Stock.objects.create(item=self.item, quantity='3', value='60')
        move = StockMove.objects.create(stock=stock, kind='opening', quantity='3', value='60', reason='期初')
        self.remove('stocks', [stock.pk], status=409)
        self.remove('moves', [move.pk])
        self.assertNotIn(move.pk, self.listed('moves'))
        stock.refresh_from_db()
        self.assertEqual(stock.quantity, Decimal('3'))
        self.assertTrue(StockMove.objects.filter(pk=move.pk).exists())
        empty = Stock.objects.create(item=self.item, location='备用仓')
        self.remove('stocks', [empty.pk])
        self.assertNotIn(empty.pk, self.listed('stocks'))
        empty.quantity, empty.value = Decimal('1'), Decimal('5')
        empty.save()
        self.assertIn(empty.pk, self.listed('stocks'))

    def test_purchase_draft_deletes_owned_lines_but_approved_requires_processing(self):
        purchase = PurchaseOrder.objects.create(
            code='PO-DRAFT', project=self.project, supplier=self.supplier, due_date=timezone.localdate()
        )
        line = PurchaseLine.objects.create(purchase=purchase, item=self.item, quantity=2, unit_price=5)
        self.remove('purchases', [purchase.pk])
        line.refresh_from_db()
        self.assertTrue(line.is_deleted)
        self.assertEqual(len(self.history('purchases')[0]['detail']['record']['lines']), 1)
        active = PurchaseOrder.objects.create(
            code='PO-ACTIVE',
            project=self.project,
            supplier=self.supplier,
            due_date=timezone.localdate(),
            status='approved',
        )
        self.remove('purchases', [active.pk], status=409)

    def test_project_and_signed_sale_protected_until_ended_then_archived(self):
        self.remove('projects', [self.project.pk], status=409)
        self.remove('sales', [self.project.sale.pk], status=409)
        self.project.status = 'closed'
        self.project.save()
        self.remove('projects', [self.project.pk])
        self.remove('sales', [self.project.sale.pk])
        self.project.refresh_from_db()
        self.assertFalse(self.project.is_deleted)
        self.assertTrue(Entry.objects.filter(project=self.project).exists())

    def test_bom_removal_obeys_existing_demand_rules(self):
        line = BOMLine.objects.create(project=self.project, item=self.item, quantity=2)
        self.remove('bom', [line.pk])
        line.refresh_from_db()
        self.assertTrue(line.is_deleted)
        self.assertTrue(AuditLog.objects.filter(operation='bom.remove').exists())

    def test_closed_bom_hidden_in_demand_but_original_fact_retained(self):
        from apps.business.services import bom

        line = BOMLine.objects.create(project=self.project, item=self.item, quantity=2)
        self.project.status = 'closed'
        self.project.save()
        self.remove('bom', [line.pk])
        self.assertTrue(BOMLine.objects.filter(pk=line.pk).exists())
        self.assertTrue(bom.demand(self.project))
        response = self.clients['admin'].get(f'/api/business/projects/{self.project.pk}/demand/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['lines'], [])

    def test_completed_tasks_and_deliveries_preserve_execution_facts(self):
        task = Task.objects.create(
            project=self.project, title='设计', kind='design', status='done', assignee=self.users['member']
        )
        old = timezone.localdate() - timedelta(days=400)
        delivery = Delivery.objects.create(
            code='DL1',
            project=self.project,
            quantity=1,
            shipped_date=old,
            accepted_date=old,
            warranty_until=timezone.localdate() - timedelta(days=1),
        )
        for resource, obj in [('tasks', task), ('deliveries', delivery)]:
            self.remove(resource, [obj.pk])
            obj.refresh_from_db()
            self.assertFalse(obj.is_deleted)

    def test_bank_and_reconciliation_history_preserves_all_facts(self):
        entry = Entry.objects.filter(project=self.project).first()
        bank = BankRecord.objects.create(
            project=self.project,
            amount=10,
            date=timezone.localdate(),
            account='银行',
            reference='BK1',
            counterparty='客户',
            reason='到账',
        )
        rec = Reconciliation.objects.create(
            code='RC1',
            entry=entry,
            kind='settlement',
            status='confirmed',
            approved_amount=10,
            snapshot={'balance': '100'},
            reason='核对',
        )
        payment = Payment.objects.create(
            entry=entry, reconciliation=rec, amount=10, date=timezone.localdate(), reason='收款'
        )
        match = BankMatch.objects.create(bank=bank, payment=payment, amount=10, reason='匹配')
        for resource, obj in [('bank-records', bank), ('reconciliations', rec), ('bank-matches', match)]:
            self.remove(resource, [obj.pk])
            self.assertTrue(type(obj).objects.filter(pk=obj.pk).exists())
            self.assertEqual(len(self.history(resource)), 1)

    def test_user_deletion_disables_login_and_preserves_identity_not_passwords(self):
        member = self.users['member']
        self.remove('users', [self.users['admin'].pk], status=409)
        self.remove('users', [member.pk])
        member.refresh_from_db()
        self.assertFalse(member.is_active)
        record = self.history('users')[0]['detail']['record']
        self.assertNotIn('password', record)
        self.assertEqual(record['username'], 'member')
        response = self.clients['admin'].get('/api/auth/users/')
        self.assertNotIn(member.pk, {row['id'] for row in response.data['results']})

    def restore(self, user_id, *, role='admin', resource='users', reason='误删账号，核对后恢复', status=200, key=None):
        return self.post(
            role,
            'record-deletions/restore/',
            {'resource': resource, 'id': user_id, 'reason': reason},
            status=status,
            key=key,
        )

    def user_rows(self):
        response = self.clients['admin'].get('/api/auth/users/')
        self.assertEqual(response.status_code, 200, response.data)
        return {row['id']: row for row in response.data['results']}

    def test_user_restore_reappears_disabled_with_audit_until_admin_enables(self):
        member = self.users['member']
        self.project.members.add(member)
        url = f'/api/auth/users/{member.pk}/'
        self.remove('users', [member.pk], reason='误删')
        deletion = AuditLog.objects.get(operation='record.delete', resource=f'user:{member.pk}')
        self.assertFalse(self.history('users')[0]['restored'])
        # 仍处于已删除状态的账号，普通编辑不能启用。
        self.assertEqual(self.clients['admin'].patch(url, {'is_active': True}, format='json').status_code, 404)
        result = self.restore(member.pk)
        self.assertEqual(result['id'], member.pk)
        self.assertEqual(result['deletion'], deletion.pk)
        self.assertFalse(result['is_active'])
        member.refresh_from_db()
        self.assertFalse(member.is_active)
        self.assertEqual(member.username, 'member')
        restored = AuditLog.objects.get(operation='record.restore', resource=f'user:{member.pk}')
        self.assertEqual(restored.actor, self.users['admin'])
        self.assertEqual(restored.detail['resource'], 'users')
        self.assertEqual(restored.detail['reason'], '误删账号，核对后恢复')
        self.assertEqual(restored.detail['deletion'], deletion.pk)
        self.assertEqual(restored.detail['record']['username'], 'member')
        self.assertFalse(restored.detail['record']['is_active'])
        self.assertNotIn('password', restored.detail['record'])
        self.assertTrue(AuditLog.objects.filter(pk=deletion.pk, detail__reason='误删').exists())
        self.assertFalse(self.user_rows()[member.pk]['is_active'])
        [history] = self.history('users')
        self.assertEqual(history['id'], deletion.pk)
        self.assertTrue(history['restored'])
        self.assertEqual(history['restored_by'], 'admin')
        self.assertIsNotNone(history['restored_at'])
        self.assertIn(member, self.project.members.all())
        response = self.clients['admin'].patch(url, {'is_active': True}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        member.refresh_from_db()
        self.assertTrue(member.is_active)
        # 用户名仍归该账号所有，不能新建同名账号。
        response = self.clients['admin'].post(
            '/api/auth/users/', {'username': 'member', 'password': 'temporary', 'role': 'member'}, format='json'
        )
        self.assertEqual(response.status_code, 400, response.data)

    def test_user_restore_rejects_live_accounts_and_replays_receipt(self):
        member = self.users['member']
        self.assertIn('未处于已删除状态', str(self.restore(member.pk, status=409)))
        self.remove('users', [member.pk])
        key = str(uuid.uuid4())
        first = self.restore(member.pk, key=key)
        self.assertEqual(self.restore(member.pk, key=key), first)
        self.assertEqual(AuditLog.objects.filter(operation='record.restore').count(), 1)
        self.assertIn('未处于已删除状态', str(self.restore(member.pk, status=409)))
        self.restore(member.pk, key=key, reason='更换原因', status=409)
        self.restore(999999, status=404)
        self.assertEqual(AuditLog.objects.filter(operation='record.restore').count(), 1)

    def test_user_restore_requires_admin_users_resource_reason_and_key(self):
        member = self.users['member']
        self.remove('users', [member.pk])
        for role in ['finance', 'warehouse', 'manager', 'production_manager', 'purchase_manager']:
            with self.subTest(role=role):
                self.restore(member.pk, role=role, status=403)
        self.assertIn('本轮仅支持恢复用户账号', str(self.restore(self.item.pk, resource='items', status=400)))
        self.assertIn('本轮仅支持恢复用户账号', str(self.restore(member.pk, resource='audit', status=400)))
        for reason in ['  ', 'x' * 501]:
            self.restore(member.pk, reason=reason, status=400)
        for value in [True, 'abc', 0, None]:
            self.restore(value, status=400)
        self.post('admin', 'record-deletions/restore/', {'resource': 'users', 'id': member.pk}, status=400)
        self.post(
            'admin',
            'record-deletions/restore/',
            {'resource': 'users', 'id': member.pk, 'reason': '恢复', 'ids': [member.pk]},
            status=400,
        )
        response = self.clients['admin'].post(
            '/api/business/record-deletions/restore/',
            {'resource': 'users', 'id': member.pk, 'reason': '恢复'},
            format='json',
        )
        self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(AuditLog.objects.filter(operation='record.restore').exists())
        actor = self.users['manager']
        actor.additional_roles = ['admin']
        actor.save()
        key = str(uuid.uuid4())
        first = self.restore(member.pk, role='manager', key=key)
        self.assertEqual(self.restore(member.pk, role='manager', key=key), first)
        actor.additional_roles = []
        actor.save()
        self.restore(member.pk, role='manager', key=key, status=403)
        self.assertEqual(AuditLog.objects.filter(operation='record.restore').count(), 1)

    def test_restored_user_can_be_deleted_and_restored_again(self):
        member = self.users['member']
        url = f'/api/auth/users/{member.pk}/'
        self.remove('users', [member.pk])
        with CaptureQueriesContext(connection) as single:
            self.history('users')
        self.restore(member.pk)
        self.remove('users', [member.pk], reason='再次删除')
        self.assertNotIn(member.pk, self.user_rows())
        self.assertEqual(self.clients['admin'].patch(url, {'is_active': True}, format='json').status_code, 404)
        self.assertEqual([row['restored'] for row in self.history('users')], [False, True])
        self.restore(member.pk, reason='再次恢复')
        self.assertIn(member.pk, self.user_rows())
        self.assertEqual([row['restored'] for row in self.history('users')], [True, True])
        with CaptureQueriesContext(connection) as both:
            self.history('users')
        self.assertEqual(len(both), len(single), '已删除记录的恢复状态不能逐条查询')
        removals = AuditLog.objects.filter(operation='record.delete', resource=f'user:{member.pk}').order_by('pk')
        restores = AuditLog.objects.filter(operation='record.restore', resource=f'user:{member.pk}').order_by('pk')
        self.assertEqual([log.detail['deletion'] for log in restores], [log.pk for log in removals])
        self.assertEqual(self.clients['admin'].patch(url, {'is_active': True}, format='json').status_code, 200)

    def test_unused_attachment_preserves_file_reference(self):
        doc = Document.objects.create(
            project=self.project,
            category='drawing',
            file='protected/test.pdf',
            original_name='测试图纸.pdf',
            sha256='a' * 64,
            size=10,
        )
        self.remove('documents', [doc.pk])
        doc.refresh_from_db()
        self.assertTrue(doc.is_deleted)
        self.assertEqual(doc.file.name, 'protected/test.pdf')

    def test_duplicate_new_request_rejected_and_archiving_locked_ledger_does_not_mutate_it(self):
        entry, _ = self.settled_entry()
        Company.objects.update_or_create(pk=1, defaults={'locked_through': timezone.localdate()})
        self.remove('entries', [entry.pk])
        self.remove('entries', [entry.pk], status=409)
        self.assertFalse(Entry.objects.get(pk=entry.pk).is_deleted)

    def test_missing_key_and_changed_payload_do_not_delete_extra_records(self):
        data = {'resource': 'items', 'ids': [self.item.pk], 'reason': '清理'}
        response = self.clients['admin'].post('/api/business/record-deletions/', data, format='json')
        self.assertEqual(response.status_code, 400)
        key = str(uuid.uuid4())
        self.remove('items', [self.item.pk], key=key)
        other = Item.objects.create(code='OTHER', name='其他物料')
        self.remove('items', [other.pk], key=key, status=409)
        self.assertTrue(Item.objects.filter(pk=other.pk).exists())

    def test_received_purchase_retains_its_lines_and_payable(self):
        purchase = self.purchase(self.project, qty='2', price='30')
        line = purchase.lines.get()
        self.post(
            'warehouse',
            f'purchases/{purchase.pk}/receive/',
            {
                'lines': [{'line': line.pk, 'quantity': '2'}],
                'location': '主仓',
                'reason': '到货',
            },
        )
        payable = Entry.objects.get(purchase=purchase)
        before = balance(payable)
        self.remove('purchases', [purchase.pk])
        self.assertTrue(PurchaseOrder.objects.filter(pk=purchase.pk).exists())
        self.assertTrue(PurchaseLine.objects.filter(pk=line.pk).exists())
        self.assertEqual(balance(payable), before)
        self.assertNotIn(purchase.pk, self.listed('purchases'))

    def test_bom_batch_rolls_back_when_later_line_has_incoming_purchase(self):
        unused = BOMLine.objects.create(project=self.project, item=self.item, assembly_unit='A', quantity=2)
        protected = BOMLine.objects.create(project=self.project, item=self.item, assembly_unit='B', quantity=2)
        purchase = PurchaseOrder.objects.create(
            code='PO-BOM',
            project=self.project,
            supplier=self.supplier,
            status='approved',
            due_date=timezone.localdate(),
        )
        PurchaseLine.objects.create(purchase=purchase, item=self.item, bom_line=protected, quantity=1, unit_price=10)
        key = str(uuid.uuid4())
        self.remove('bom', [unused.pk, protected.pk], status=409, key=key)
        self.assertEqual(BOMLine.objects.filter(pk__in=[unused.pk, protected.pk]).count(), 2)
        self.assertFalse(AuditLog.objects.filter(operation__in=['record.delete', 'bom.remove']).exists())
        self.assertFalse(ActionReceipt.objects.filter(key=key).exists())

    def test_referenced_document_remains_available_and_hidden_from_list(self):
        doc = Document.objects.create(
            project=self.project,
            category='receipt',
            file='protected/evidence.pdf',
            original_name='付款凭证.pdf',
            sha256='b' * 64,
            size=10,
        )
        entry = Entry.objects.filter(project=self.project).first()
        payment = Payment.objects.create(entry=entry, amount=10, date=timezone.localdate(), reason='收款')
        payment.evidence.create(document=doc, reason='补录凭证')
        self.remove('documents', [doc.pk])
        self.assertTrue(Document.objects.filter(pk=doc.pk).exists())
        self.assertNotIn(doc.pk, self.listed('documents'))
        self.assertTrue(payment.evidence.filter(document=doc).exists())

    def test_archive_is_excluded_from_list_export_but_not_financial_summary(self):
        # Open receivables can no longer be archived; a settled entry keeps the list/export/summary contract.
        entry, _ = self.settled_entry('已结清安装费')
        client = self.clients['admin']
        before = client.get('/api/business/entries/summary/').data
        self.assertNotEqual(before['receivable'], '0.00')
        self.remove('entries', [entry.pk])
        self.assertEqual(client.get('/api/business/entries/summary/').data, before)
        self.assertNotIn(entry.pk, self.listed('entries'))
        response = client.get('/api/business/entries/export/?file_format=csv')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(entry.title, response.content.decode('utf-8-sig'))

    def test_open_entries_rejected_until_settled_or_cancelled(self):
        today = timezone.localdate()
        settled, _ = self.settled_entry()
        cancelled = Entry.objects.create(
            project=self.project,
            kind='expense',
            title='已取消费用',
            amount='80',
            credit_amount='80',
            cancelled=True,
            due_date=today,
        )
        refund = Entry.objects.create(
            project=self.project,
            kind='expense',
            title='待退款费用',
            amount='60',
            credit_amount='60',
            cancelled=True,
            due_date=today,
        )
        Payment.objects.create(entry=refund, amount='60', date=today, reason='已付款后取消')
        drafted, _ = self.settled_entry('待对账费用')
        Reconciliation.objects.create(
            code='RC-DRAFT', entry=drafted, kind='settlement', approved_amount=10, reason='核对'
        )
        open_entry = Entry.objects.create(
            project=self.project, kind='expense', title='未付费用', amount='50', due_date=today
        )
        receivable = Entry.objects.get(project=self.project, kind='receivable')
        before = self.clients['admin'].get('/api/business/entries/summary/').data
        for obj, fragments in [
            (receivable, ('余额 10000.00 元', '结清')),
            (refund, ('待退款 60.00 元', '退款对账')),
            (drafted, ('待确认的对账单', '确认或作废')),
            (open_entry, ('余额 50.00 元',)),
        ]:
            with self.subTest(entry=obj.title):
                self.assert_batch_rejected('entries', [settled.pk, cancelled.pk, obj.pk], *fragments)
        self.assertEqual(self.clients['admin'].get('/api/business/entries/summary/').data, before)
        self.remove('entries', [settled.pk, cancelled.pk])
        self.assertFalse({settled.pk, cancelled.pk} & self.listed('entries'))

    def test_payment_rejected_while_its_entry_is_open(self):
        _, settled_payment = self.settled_entry()
        receivable = Entry.objects.get(project=self.project, kind='receivable')
        open_payment = Payment.objects.create(entry=receivable, amount='100', date=timezone.localdate(), reason='收款')
        self.assert_batch_rejected('payments', [settled_payment.pk, open_payment.pk], '9900.00 元', '冲销')
        self.remove('payments', [settled_payment.pk])
        self.assertNotIn(settled_payment.pk, self.listed('payments'))

    def test_reconciliation_rejected_while_draft_or_allowance_remains(self):
        entry = Entry.objects.create(
            project=self.project, kind='expense', title='对账费用', amount='100', due_date=timezone.localdate()
        )

        def statement(code, amount=100, **extra):
            return Reconciliation.objects.create(
                code=code,
                entry=entry,
                kind='settlement',
                approved_amount=amount,
                snapshot={'balance': '100'},
                reason='核对',
                **extra,
            )

        used = statement('RC-USED', status='confirmed')
        Payment.objects.create(entry=entry, reconciliation=used, amount='100', date=timezone.localdate(), reason='付清')
        voided = statement('RC-VOID', 50, status='void', void_reason='重复生成')
        draft = statement('RC-WAIT')
        left = statement('RC-LEFT', 30, status='confirmed')
        self.assert_batch_rejected('reconciliations', [used.pk, voided.pk, draft.pk], '待确认', '确认或作废')
        self.assert_batch_rejected('reconciliations', [used.pk, voided.pk, left.pk], '30.00 元', '作废')
        self.remove('reconciliations', [used.pk, voided.pk])
        self.assertFalse({used.pk, voided.pk} & self.listed('reconciliations'))

    def test_bank_records_and_matches_rejected_while_unmatched_or_under_review(self):
        receivable = Entry.objects.get(project=self.project, kind='receivable')
        payment = Payment.objects.create(entry=receivable, amount='30', date=timezone.localdate(), reason='收款')
        matched = self.bank('BK-FULL')
        full_match = BankMatch.objects.create(bank=matched, payment=payment, amount=10, reason='匹配')
        voided = self.bank('BK-VOID', void_reason='重复登记')
        partial = self.bank('BK-PART')
        partial_match = BankMatch.objects.create(bank=partial, payment=payment, amount=4, reason='部分匹配')
        review = self.bank('BK-REVIEW', needs_review=True)
        BankMatch.objects.create(bank=review, payment=payment, amount=10, reason='匹配')
        unclaimed = self.bank('BK-OPEN', amount='-8')
        for obj, fragments in [(partial, ('6.00 元', '认领')), (review, ('户名',)), (unclaimed, ('8.00 元',))]:
            with self.subTest(bank=obj.reference):
                self.assert_batch_rejected('bank-records', [matched.pk, voided.pk, obj.pk], *fragments)
        before = AuditLog.objects.filter(operation='record.delete').count()
        key = str(uuid.uuid4())
        detail = str(self.remove('bank-matches', [full_match.pk, partial_match.pk], status=409, key=key))
        self.assertIn('6.00 元', detail)
        self.assertEqual(AuditLog.objects.filter(operation='record.delete').count(), before)
        self.assertFalse(ActionReceipt.objects.filter(key=key).exists())
        self.remove('bank-records', [matched.pk, voided.pk])
        self.remove('bank-matches', [full_match.pk])
        self.assertFalse({matched.pk, voided.pk} & self.listed('bank-records'))

    def test_delivery_rejected_until_accepted_and_warranty_ends(self):
        today = timezone.localdate()
        old = today - timedelta(days=400)

        def delivery(code, **extra):
            return Delivery.objects.create(code=code, project=self.project, quantity=1, shipped_date=old, **extra)

        expired = delivery('DL-EXP', accepted_date=old, warranty_until=today - timedelta(days=1))
        waiting = delivery('DL-WAIT')
        # The last warranty day still allows free service against this batch.
        warranty = delivery('DL-WARR', accepted_date=old, warranty_until=today)
        self.assert_batch_rejected('deliveries', [expired.pk, waiting.pk], '尚未验收', '完成验收')
        self.assert_batch_rejected('deliveries', [expired.pk, warranty.pk], f'质保期内（至 {today}）', '售后')
        self.remove('deliveries', [expired.pk])
        self.assertNotIn(expired.pk, self.listed('deliveries'))
        # Ended projects can tidy their remaining batches.
        self.project.status = 'cancelled'
        self.project.save()
        self.remove('deliveries', [waiting.pk, warranty.pk])
        self.assertFalse({waiting.pk, warranty.pk} & self.listed('deliveries'))

    def test_accepted_project_bom_rejection_explains_lock(self):
        line = BOMLine.objects.create(project=self.project, item=self.item, quantity=2)
        self.project.status = 'warranty'
        self.project.save()
        detail = str(self.remove('bom', [line.pk], status=409))
        self.assertIn('项目已验收，BOM 已锁定', detail)
        self.assertIn('变更流程', detail)
        self.assertNotIn('当前状态不允许', detail)
        self.assertFalse(AuditLog.objects.filter(operation__in=['record.delete', 'bom.remove']).exists())


class DeletionConcurrencyTests(BusinessFixtures, TransactionTestCase):
    def setUp(self):
        self.setup_business()

    def test_reference_creation_waits_for_deletion_then_revalidates_live_customer(self):
        from apps.business.services import deletions

        checking, writer_started, writer_done = Event(), Event(), Event()
        original = deletions.references

        def held_references(obj, **kwargs):
            checking.set()
            self.assertTrue(writer_started.wait(5))
            self.assertFalse(writer_done.wait(0.2), '关联写入必须等待删除事务完成')
            return original(obj, **kwargs)

        def remove():
            close_old_connections()
            try:
                return self.post(
                    'admin',
                    'record-deletions/',
                    {
                        'resource': 'partners',
                        'ids': [self.customer.pk],
                        'reason': '并发验收',
                    },
                )
            finally:
                close_old_connections()

        def create_sale():
            close_old_connections()
            try:
                self.assertTrue(checking.wait(5))
                writer_started.set()
                return self.post(
                    'manager',
                    'sales/',
                    {
                        'name': '并发销售',
                        'customer': self.customer.pk,
                        'manager': self.users['manager'].pk,
                    },
                    status=404,
                )
            finally:
                writer_done.set()
                close_old_connections()

        with patch.object(deletions, 'references', held_references), ThreadPoolExecutor(max_workers=2) as pool:
            removal = pool.submit(remove)
            writer = pool.submit(create_sale)
            self.assertEqual(removal.result(timeout=10)['count'], 1)
            writer.result(timeout=10)
        self.assertFalse(SalesOrder.objects.exists())
        self.assertFalse(Partner.objects.filter(pk=self.customer.pk).exists())
        self.assertEqual(AuditLog.objects.filter(operation='record.delete').count(), 1)
