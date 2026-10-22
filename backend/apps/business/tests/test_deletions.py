import uuid
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Event
from unittest.mock import patch

from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase
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
        payment = Payment.objects.create(entry=entry, amount='100', date=timezone.localdate(), reason='收款')
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
        delivery = Delivery.objects.create(
            code='DL1', project=self.project, quantity=1, shipped_date=timezone.localdate()
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
            code='RC1', entry=entry, kind='settlement', approved_amount=10, snapshot={'balance': '100'}, reason='核对'
        )
        payment = Payment.objects.create(entry=entry, amount=10, date=timezone.localdate(), reason='收款')
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
        Company.objects.update_or_create(pk=1, defaults={'locked_through': timezone.localdate()})
        entry = Entry.objects.filter(project=self.project).first()
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
        entry = Entry.objects.filter(project=self.project).first()
        client = self.clients['admin']
        before = client.get('/api/business/entries/summary/').data
        self.remove('entries', [entry.pk])
        self.assertEqual(client.get('/api/business/entries/summary/').data, before)
        response = client.get('/api/business/entries/export/?file_format=csv')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(entry.title, response.content.decode('utf-8-sig'))


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
