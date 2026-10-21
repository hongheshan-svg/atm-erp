"""Focused BP/SP audit regressions; independent from the full commercial chain."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from decimal import Decimal
from threading import Barrier

from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient

from apps.business.models import (
    BOMLine,
    Delivery,
    Document,
    Entry,
    Item,
    PurchaseOrder,
    SalesOrder,
    Stock,
    StockMove,
    Task,
)
from apps.business.services.bom import revision
from apps.core.models import ActionReceipt, AuditLog

from .test_commercial_chain import TODAY, BusinessFixtures


class AuditBusinessFixtures(BusinessFixtures):
    def setUp(self):
        self.setup_business()
        self.project = self.active_project()

    def multi_purchase(self, *, approve=True):
        other = Item.objects.create(code='AUDIT-2', name='气缸')
        order = self.post(
            'purchaser',
            'purchases/',
            {
                'project': self.project.pk,
                'supplier': self.supplier.pk,
                'due_date': TODAY,
                'lines': [
                    {'item': self.item.pk, 'quantity': '5', 'unit_price': '10'},
                    {'item': other.pk, 'quantity': '3', 'unit_price': '20'},
                ],
            },
            status=201,
        )
        order = PurchaseOrder.objects.get(pk=order['id'])
        if approve:
            self.post('purchaser', f'purchases/{order.pk}/submit/')
            self.post('manager', f'purchases/{order.pk}/approve/')
        order.refresh_from_db()
        return order, list(order.lines.order_by('id'))

    def amendment(self):
        sale = self.project.sale
        doc = Document.objects.create(
            project=self.project, category='contract', original_name='协议.pdf', file='audit.pdf', size=1
        )
        return sale, {
            'expected_updated_at': sale.updated_at.isoformat(),
            'reason': '补充协议',
            'date': TODAY,
            'document': doc.pk,
            'amount': '10100',
            'equipment_quantity': 1,
            'warranty_months': 12,
            'milestones': [{'title': '补充协议款', 'amount': '100', 'due_date': '2026-09-01'}],
        }

    def service_payload(self):
        self.project.status = 'warranty'
        self.project.save()
        delivery = Delivery.objects.create(
            project=self.project,
            code='AUDIT-D1',
            quantity=1,
            shipped_date='2026-09-01',
            accepted_date='2026-09-02',
            warranty_until='2026-09-03',
        )
        return {
            'delivery': delivery.pk,
            'date': TODAY,
            'title': '维修',
            'assignee': self.users['member'].pk,
            'fee': '300',
            'due_date': '2026-09-10',
            'fee_due_date': '2026-10-10',
        }


class AuditBusinessTests(AuditBusinessFixtures, TestCase):
    def test_partial_cancel_leaves_other_lines_and_quarantine_intact_and_replays_once(self):
        order, (first, other) = self.multi_purchase()
        url = f'purchases/{order.pk}/'
        self.post(
            'warehouse',
            url + 'receive/',
            {
                'reason': '分批到货',
                'lines': [
                    {'line': first.pk, 'quantity': '1'},
                    {'line': other.pk, 'quantity': '0', 'pending_quantity': '2'},
                ],
            },
        )
        key = str(uuid.uuid4())
        payload = {'reason': '部分缺货', 'lines': [{'line': first.pk, 'quantity': '2'}]}
        result = self.post('purchaser', url + 'cancel-remainder/', payload, key=key)
        self.assertEqual(result, self.post('purchaser', url + 'cancel-remainder/', payload, key=key))
        first.refresh_from_db()
        other.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual((first.received_quantity, first.cancelled_quantity), (1, 2))
        self.assertEqual((other.received_quantity, other.cancelled_quantity, other.pending_quantity), (0, 0, 2))
        self.assertEqual(order.status, 'partial')
        self.assertEqual(Entry.objects.get(purchase=order).credit_amount, 20)
        self.assertEqual(Stock.objects.get().quantity, 1)
        self.assertEqual(StockMove.objects.count(), 1)
        audit = AuditLog.objects.get(operation='purchase.cancel_remainder')
        self.assertEqual(audit.detail['lines'], [{'line': first.pk, 'quantity': '2.000'}])
        self.post('warehouse', url + 'receive/', {'reason': '继续履约', 'lines': [{'line': first.pk, 'quantity': '2'}]})
        first.refresh_from_db()
        self.assertEqual(first.received_quantity, 3)

    def test_partial_then_legacy_cancel_credits_only_new_remainder(self):
        order, (first, other) = self.multi_purchase()
        url = f'purchases/{order.pk}/cancel-remainder/'
        self.post('purchaser', url, {'reason': '首批取消', 'lines': [{'line': first.pk, 'quantity': '2'}]})
        order.refresh_from_db()
        self.assertEqual(order.status, 'approved')
        self.post('purchaser', url, {'reason': '其余不再补货'})
        order.refresh_from_db()
        first.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual((first.cancelled_quantity, other.cancelled_quantity), (5, 3))
        self.assertEqual(order.status, 'cancelled')
        self.assertEqual(Entry.objects.get(purchase=order).credit_amount, 110)

    def test_selected_line_without_quantity_cancels_only_that_line(self):
        order, (first, other) = self.multi_purchase()
        self.post(
            'purchaser',
            f'purchases/{order.pk}/cancel-remainder/',
            {
                'reason': '此项不再补货',
                'lines': [{'line': first.pk}],
            },
        )
        first.refresh_from_db()
        other.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual((first.cancelled_quantity, other.cancelled_quantity), (5, 0))
        self.assertEqual(order.status, 'approved')
        self.post(
            'warehouse',
            f'purchases/{order.pk}/receive/',
            {
                'reason': '其余到货',
                'lines': [{'line': other.pk, 'quantity': '3'}],
            },
        )
        order.refresh_from_db()
        self.assertEqual(order.status, 'received')
        self.assertEqual(Entry.objects.get(purchase=order).credit_amount, 50)

    def test_partial_cancellation_rounding_telescopes_with_receipts(self):
        order = self.purchase(self.project, qty='1.005', price='1')
        line = order.lines.get()
        url = f'purchases/{order.pk}/'
        for qty in ['0.001', '0.002']:
            self.post(
                'purchaser',
                url + 'cancel-remainder/',
                {
                    'reason': '逐次取消',
                    'lines': [{'line': line.pk, 'quantity': qty}],
                },
            )
        for qty in ['0.500', '0.502']:
            self.post(
                'warehouse', url + 'receive/', {'reason': '分次到货', 'lines': [{'line': line.pk, 'quantity': qty}]}
            )
        line.refresh_from_db()
        order.refresh_from_db()
        entry = Entry.objects.get(purchase=order)
        self.assertEqual((line.received_quantity, line.cancelled_quantity), (Decimal('1.002'), Decimal('0.003')))
        self.assertEqual((entry.amount, entry.credit_amount), (Decimal('1.01'), Decimal('0.01')))
        self.assertEqual(sum(StockMove.objects.values_list('value', flat=True)), entry.amount - entry.credit_amount)
        self.assertEqual(order.status, 'received')

        contract = self.clients['purchaser'].get(f'/api/business/purchases/{order.pk}/contract-preview/')
        self.assertEqual(contract.status_code, 200, contract.data)
        self.assertEqual(Decimal(contract.data['cancelled_amount']), entry.credit_amount)

    def test_invalid_cancellation_rolls_back_without_receipt_or_ledger_changes(self):
        order, (first, other) = self.multi_purchase()
        foreign = self.purchase(self.project).lines.get()
        self.post(
            'warehouse',
            f'purchases/{order.pk}/receive/',
            {
                'reason': '隔离待处理',
                'lines': [{'line': other.pk, 'quantity': '0', 'pending_quantity': '1'}],
            },
        )
        counts = (ActionReceipt.objects.count(), AuditLog.objects.count())
        cases = [
            ([], 400),
            ([{'line': foreign.pk, 'quantity': '1'}], 400),
            ([{'line': first.pk, 'quantity': '0'}], 400),
            ([{'line': first.pk, 'quantity': '-1'}], 400),
            ([{'line': first.pk, 'quantity': '6'}], 409),
            ([{'line': first.pk, 'quantity': '1'}, {'line': first.pk, 'quantity': '1'}], 400),
            ([{'line': first.pk, 'quantity': '1'}, {'line': other.pk, 'quantity': '1'}], 409),
        ]
        for lines, status in cases:
            with self.subTest(lines=lines):
                self.post(
                    'purchaser',
                    f'purchases/{order.pk}/cancel-remainder/',
                    {
                        'reason': '无效取消',
                        'lines': lines,
                    },
                    status=status,
                )
                self.assertEqual((ActionReceipt.objects.count(), AuditLog.objects.count()), counts)
                self.assertTrue(all(line.cancelled_quantity == 0 for line in order.lines.all()))
                self.assertEqual(Entry.objects.get(purchase=order).credit_amount, 0)
        self.post('warehouse', f'purchases/{order.pk}/cancel-remainder/', {'reason': '越权'}, status=403)
        self.post('purchaser', f'purchases/{order.pk}/cancel-remainder/', {'reason': '整单仍有隔离'}, status=409)

    def test_draft_cancellation_stays_whole_order_without_approval_amount_ambiguity(self):
        order, (first, _) = self.multi_purchase(approve=False)
        url = f'purchases/{order.pk}/cancel-remainder/'
        self.post('purchaser', url, {'reason': '未批准', 'lines': [{'line': first.pk, 'quantity': '1'}]}, status=400)
        self.post('purchaser', url, {'reason': '作废草稿'})
        order.refresh_from_db()
        self.assertEqual(order.status, 'cancelled')
        self.assertFalse(Entry.objects.filter(purchase=order).exists())

    def test_zero_receipt_row_does_not_hide_duplicate_line(self):
        order = self.purchase(self.project)
        line = order.lines.get()
        self.post(
            'warehouse',
            f'purchases/{order.pk}/receive/',
            {
                'reason': '重复行',
                'lines': [
                    {'line': line.pk, 'quantity': '0'},
                    {'line': line.pk, 'quantity': '1'},
                ],
            },
            status=400,
        )
        self.assertFalse(StockMove.objects.exists())
        line.refresh_from_db()
        self.assertEqual(line.received_quantity, 0)

    def test_quantity_errors_locate_purchase_create_edit_and_bom_rows(self):
        other = Item.objects.create(code='AUDIT-Q', name='数量错误物料')
        data = {
            'project': self.project.pk,
            'supplier': self.supplier.pk,
            'due_date': TODAY,
            'lines': [
                {'item': self.item.pk, 'quantity': '1', 'unit_price': '1'},
                {'item': other.pk, 'quantity': '0', 'unit_price': '1'},
            ],
        }
        response = self.post('purchaser', 'purchases/', data, status=400)
        self.assertIn('quantity', response['lines'][1])
        self.assertFalse(PurchaseOrder.objects.exists())
        response = self.post(
            'manager',
            f'projects/{self.project.pk}/revise-bom/',
            {
                'expected_revision': revision(self.project),
                'lines': [{'item': self.item.pk, 'quantity': '1'}, {'item': other.pk, 'quantity': '0'}],
            },
            status=400,
        )
        self.assertIn('quantity', response['lines'][1])
        self.assertFalse(BOMLine.objects.exists())
        order, lines = self.multi_purchase(approve=False)
        response = self.post(
            'purchaser',
            f'purchases/{order.pk}/edit/',
            {
                'expected_updated_at': order.updated_at.isoformat(),
                'reason': '修正',
                'due_date': TODAY,
                'lines': [
                    {'id': line.pk, 'quantity': '0' if i else '2', 'unit_price': '1', 'due_date': TODAY}
                    for i, line in enumerate(lines)
                ],
            },
            status=400,
        )
        self.assertIn('quantity', response['lines'][1])
        self.assertEqual(list(order.lines.order_by('id').values_list('quantity', flat=True)), [5, 3])

    def test_bom_without_id_and_omitted_unit_updates_unique_existing_row(self):
        line = BOMLine.objects.create(project=self.project, item=self.item, quantity=2, assembly_unit='上料')
        self.post(
            'manager',
            f'projects/{self.project.pk}/revise-bom/',
            {
                'expected_revision': revision(self.project),
                'lines': [{'item': self.item.pk, 'quantity': '3', 'change_note': '只修改用量'}],
            },
        )
        line.refresh_from_db()
        self.assertEqual((line.quantity, line.assembly_unit), (3, '上料'))
        self.assertEqual(BOMLine.objects.count(), 1)

    def test_amendment_version_missing_or_invalid_is_400_stale_is_409(self):
        sale, payload = self.amendment()
        counts = (ActionReceipt.objects.count(), AuditLog.objects.count(), Entry.objects.count())
        for version in [None, '', 'invalid', 123, '2026-99-99T00:00:00Z']:
            with self.subTest(version=version):
                data = {**payload, 'expected_updated_at': version}
                if version is None:
                    data.pop('expected_updated_at')
                result = self.post('manager', f'sales/{sale.pk}/amend/', data, status=400)
                self.assertIn('expected_updated_at', result)
        self.post(
            'manager',
            f'sales/{sale.pk}/amend/',
            {
                **payload,
                'expected_updated_at': (sale.updated_at - timedelta(seconds=1)).isoformat(),
            },
            status=409,
        )
        self.assertEqual((ActionReceipt.objects.count(), AuditLog.objects.count(), Entry.objects.count()), counts)
        self.assertFalse(sale.amendments.exists())

    def test_contract_and_amendment_due_dates_can_precede_signing_date(self):
        sale = SalesOrder.objects.create(
            code='SO-AUDIT',
            name='预付款项目',
            customer=self.customer,
            manager=self.users['manager'],
            status='quoted',
            quote_amount=100,
        )
        self.post(
            'manager',
            f'sales/{sale.pk}/sign/',
            {
                'date': TODAY,
                'milestones': [{'title': '先期款', 'amount': '100', 'due_date': '2026-09-01'}],
            },
        )
        sale.refresh_from_db()
        self.assertEqual(sale.project.entries.get().due_date, date(2026, 9, 1))
        sale, payload = self.amendment()
        self.post('manager', f'sales/{sale.pk}/amend/', payload)
        self.assertEqual(Entry.objects.get(project=self.project, title='补充协议款').due_date, date(2026, 9, 1))

    def test_service_keeps_full_title_and_separate_customer_deadline_and_replays_once(self):
        data = {**self.service_payload(), 'title': '维' * 150}
        key = str(uuid.uuid4())
        url = f'projects/{self.project.pk}/service/'
        result = self.post('manager', url, data, key=key)
        self.assertEqual(result, self.post('manager', url, data, key=key))
        task = Task.objects.get(pk=result['id'])
        entry = Entry.objects.get(task=task)
        self.assertEqual((task.title, task.due_date), ('维' * 150, date(2026, 9, 10)))
        self.assertEqual(entry.due_date, date(2026, 10, 10))
        self.assertEqual((len(entry.title), entry.amount), (150, 300))
        self.assertEqual(Task.objects.filter(kind='service').count(), 1)
        self.assertEqual(Entry.objects.filter(task=task).count(), 1)

    def test_legacy_service_default_is_service_date_not_repair_deadline(self):
        data = self.service_payload()
        data.pop('fee_due_date')
        result = self.post('manager', f'projects/{self.project.pk}/service/', data)
        self.assertEqual(Entry.objects.get(task_id=result['id']).due_date, date.fromisoformat(TODAY))

    def test_invalid_payment_deadline_rolls_back_and_free_service_creates_no_entry(self):
        data = self.service_payload()
        counts = (ActionReceipt.objects.count(), AuditLog.objects.count(), Task.objects.count(), Entry.objects.count())
        result = self.post(
            'manager',
            f'projects/{self.project.pk}/service/',
            {
                **data,
                'fee_due_date': '2026-99-99',
            },
            status=400,
        )
        self.assertIn('fee_due_date', result)
        self.assertEqual(
            (ActionReceipt.objects.count(), AuditLog.objects.count(), Task.objects.count(), Entry.objects.count()),
            counts,
        )
        result = self.post(
            'manager',
            f'projects/{self.project.pk}/service/',
            {
                **data,
                'fee': '0',
                'free_reason': '商务赠送',
            },
        )
        self.assertFalse(Entry.objects.filter(task_id=result['id']).exists())
        self.project.members.add(self.users['production_manager'])
        self.post('production_manager', f'projects/{self.project.pk}/service/', data, status=403)


class AuditCancellationConcurrencyTests(AuditBusinessFixtures, TransactionTestCase):
    def together(self, requests):
        barrier = Barrier(len(requests))

        def run(request):
            role, path, payload = request
            close_old_connections()
            try:
                client = APIClient()
                client.force_authenticate(self.users[role])
                barrier.wait(timeout=10)
                result = client.post(
                    '/api/business/' + path, payload, format='json', HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4())
                )
                return result.status_code, result.data
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=len(requests)) as pool:
            return list(pool.map(run, requests))

    def test_parallel_cancel_and_receive_cannot_consume_same_remainder(self):
        order = self.purchase(self.project, qty='5', price='1')
        line = order.lines.get()
        url = f'purchases/{order.pk}/'
        result = self.together(
            [
                (
                    'purchaser',
                    url + 'cancel-remainder/',
                    {'reason': '取消', 'lines': [{'line': line.pk, 'quantity': '4'}]},
                ),
                ('warehouse', url + 'receive/', {'reason': '收货', 'lines': [{'line': line.pk, 'quantity': '4'}]}),
            ]
        )
        self.assertEqual(sorted(status for status, _ in result), [200, 409], result)
        line.refresh_from_db()
        self.assertEqual(line.received_quantity + line.cancelled_quantity, 4)
        self.assertEqual(Entry.objects.get(purchase=order).credit_amount, line.cancelled_quantity)
        self.assertEqual(sum(StockMove.objects.values_list('quantity', flat=True)), line.received_quantity)

    def test_parallel_cancellations_cannot_double_credit(self):
        order = self.purchase(self.project, qty='5', price='1')
        line = order.lines.get()
        request = (
            'purchaser',
            f'purchases/{order.pk}/cancel-remainder/',
            {
                'reason': '并发取消',
                'lines': [{'line': line.pk, 'quantity': '4'}],
            },
        )
        result = self.together([request, request])
        self.assertEqual(sorted(status for status, _ in result), [200, 409], result)
        line.refresh_from_db()
        self.assertEqual(line.cancelled_quantity, 4)
        self.assertEqual(Entry.objects.get(purchase=order).credit_amount, 4)
        self.assertEqual(AuditLog.objects.filter(operation='purchase.cancel_remainder').count(), 1)


class AuditConfirmedRulesTests(AuditBusinessFixtures, TestCase):
    def historical_receipt(self, order, *, pending=False):
        from django.utils import timezone

        previous = timezone.localdate(order.created_at) - timedelta(days=1)
        return {
            'received_date': previous.isoformat(),
            'reason': '实际到货',
            'lines': [
                {
                    'line': order.lines.get().pk,
                    'quantity': '0' if pending else '1',
                    'pending_quantity': '1' if pending else '0',
                }
            ],
        }

    def test_historical_receipt_requires_backfill_reason_before_any_write(self):
        order = self.purchase(self.project)
        payload = self.historical_receipt(order)
        counts = (ActionReceipt.objects.count(), AuditLog.objects.count())
        for extra in [{}, {'backfill_reason': ''}, {'backfill_reason': '   '}]:
            result = self.post('warehouse', f'purchases/{order.pk}/receive/', {**payload, **extra}, status=400)
            self.assertIn('backfill_reason', result)
            self.assertEqual((ActionReceipt.objects.count(), AuditLog.objects.count()), counts)
            self.assertFalse(StockMove.objects.exists())
            self.assertFalse(Stock.objects.exists())
            order.refresh_from_db()
            self.assertEqual(order.status, 'approved')
            self.assertEqual(order.lines.get().received_quantity, 0)

    def test_historical_receipt_preserves_date_reason_and_idempotency(self):
        order = self.purchase(self.project)
        payload = {**self.historical_receipt(order), 'backfill_reason': '纸质送货单漏录，已核对原单日期'}
        key = str(uuid.uuid4())
        url = f'purchases/{order.pk}/receive/'
        self.post('warehouse', url, payload, key=key)
        self.post('warehouse', url, payload, key=key)
        self.assertEqual(StockMove.objects.count(), 1)
        self.assertEqual(str(StockMove.objects.get().received_date), payload['received_date'])
        self.assertEqual(Stock.objects.get().quantity, 1)
        audit = AuditLog.objects.get(operation='purchase.receive')
        self.assertEqual(audit.detail['backfill_reason'], payload['backfill_reason'])
        self.assertEqual(audit.detail['received_date'], payload['received_date'])
        self.assertIn(payload['backfill_reason'], audit.detail['reason'])
        self.post('warehouse', url, {**payload, 'backfill_reason': '不同补录原因'}, key=key, status=409)

    def test_lock_blocks_qualified_and_quarantine_only_historical_arrivals(self):
        from apps.core.models import Company

        order = self.purchase(self.project)
        payload = self.historical_receipt(order)
        Company.objects.update_or_create(pk=1, defaults={'locked_through': payload['received_date']})
        counts = (ActionReceipt.objects.count(), AuditLog.objects.count())
        for pending in [False, True]:
            data = {**self.historical_receipt(order, pending=pending), 'backfill_reason': '历史漏单'}
            self.post('warehouse', f'purchases/{order.pk}/receive/', data, status=409)
        self.assertEqual((ActionReceipt.objects.count(), AuditLog.objects.count()), counts)
        self.assertFalse(StockMove.objects.exists())
        self.assertFalse(Stock.objects.exists())
        self.assertEqual(order.lines.get().pending_quantity, 0)

    def test_quarantine_only_arrival_remains_zero_stock_until_qualified(self):
        from apps.business.services.payment_terms import schedule

        order = self.purchase(self.project)
        payload = {
            'reason': '全部待检',
            'lines': [{'line': order.lines.get().pk, 'quantity': '0', 'pending_quantity': '5'}],
        }
        key = str(uuid.uuid4())
        url = f'purchases/{order.pk}/'
        self.post('warehouse', url + 'receive/', payload, key=key)
        self.post('warehouse', url + 'receive/', payload, key=key)
        order.refresh_from_db()
        line = order.lines.get()
        self.assertEqual((order.status, line.received_quantity, line.pending_quantity), ('partial', 0, 5))
        self.assertFalse(Stock.objects.exists())
        self.assertFalse(StockMove.objects.exists())
        self.assertEqual(schedule(Entry.objects.get(purchase=order)), [])
        self.post(
            'warehouse', url + 'quality-accept/', {'reason': '复检合格', 'lines': [{'line': line.pk, 'quantity': '2'}]}
        )
        line.refresh_from_db()
        self.assertEqual((line.received_quantity, line.pending_quantity), (2, 3))
        self.assertEqual(Stock.objects.get().quantity, 2)

    def legacy_project(self, status='quoted'):
        from apps.business.models import Project

        project = Project.objects.create(
            code='LEGACY-' + str(uuid.uuid4())[:8],
            name='历史未签约项目',
            customer=self.customer,
            manager=self.users['manager'],
            status=status,
        )
        sale = SalesOrder.objects.create(
            code='OLD-' + str(uuid.uuid4())[:8],
            name=project.name,
            customer=self.customer,
            manager=self.users['manager'],
            project=project,
            status=status,
            quote_amount=100 if status == 'quoted' else 0,
        )
        return project, sale

    def test_legacy_project_requirement_edit_invalidates_quote_once_and_requires_requote(self):
        project, sale = self.legacy_project()
        key = str(uuid.uuid4())
        payload = {'requirements': '更改设备精度', 'reason': '双方需求变更'}
        url = f'projects/{project.pk}/edit/'
        self.post('manager', url, payload, key=key)
        project.refresh_from_db()
        sale.refresh_from_db()
        self.assertEqual((project.status, sale.status, sale.quote_amount), ('draft', 'draft', 0))
        self.assertEqual(project.quote_amount, 0)
        project_detail = self.clients['manager'].get(f'/api/business/projects/{project.pk}/')
        sale_detail = self.clients['manager'].get(f'/api/business/sales/{sale.pk}/')
        self.assertEqual((project_detail.status_code, sale_detail.status_code), (200, 200))
        self.assertEqual((project_detail.data['quote_amount'], sale_detail.data['quote_amount']), ('0.00', '0.00'))
        self.assertEqual(sale.requirements, payload['requirements'])
        self.assertEqual(AuditLog.objects.filter(operation='sale.invalidate_quote').count(), 1)
        self.post(
            'manager',
            f'sales/{sale.pk}/sign/',
            {
                'date': TODAY,
                'milestones': [{'title': '合同款', 'amount': '100', 'due_date': TODAY}],
            },
            status=409,
        )
        self.post('manager', f'sales/{sale.pk}/quote/', {'amount': '120', 'reason': '重新报价'})
        self.post('manager', url, payload, key=key)
        sale.refresh_from_db()
        project.refresh_from_db()
        self.assertEqual((sale.status, sale.quote_amount), ('quoted', 120))
        self.assertEqual(project.quote_amount, 120)
        self.assertEqual(
            self.clients['manager'].get(f'/api/business/projects/{project.pk}/').data['quote_amount'], '120.00'
        )
        self.assertFalse(Entry.objects.filter(project=project).exists())

    def test_legacy_noop_edit_keeps_quote_and_invalid_edit_rolls_back(self):
        project, sale = self.legacy_project()
        self.post('manager', f'projects/{project.pk}/edit/', {'name': project.name, 'reason': '核对未变'})
        sale.refresh_from_db()
        self.assertEqual((sale.status, sale.quote_amount), ('quoted', 100))
        counts = (ActionReceipt.objects.count(), AuditLog.objects.count())
        self.post(
            'manager',
            f'projects/{project.pk}/edit/',
            {
                'requirements': '不应保存',
                'equipment_quantity': 0,
                'reason': '错误数量',
            },
            status=400,
        )
        sale.refresh_from_db()
        project.refresh_from_db()
        self.assertEqual((sale.status, sale.quote_amount, project.requirements), ('quoted', 100, ''))
        self.assertEqual((ActionReceipt.objects.count(), AuditLog.objects.count()), counts)
        self.post('warehouse', f'projects/{project.pk}/edit/', {'requirements': '越权', 'reason': '无权限'}, status=403)

    def test_legacy_cancel_reopen_preserves_draft_or_quoted_without_receivable(self):
        for status in ['draft', 'quoted']:
            with self.subTest(status=status):
                project, sale = self.legacy_project(status)
                self.post('manager', f'projects/{project.pk}/cancel/', {'reason': '暂缓'})
                key = str(uuid.uuid4())
                payload = {'reason': '继续跟进，尚未签约'}
                self.post('manager', f'projects/{project.pk}/reopen/', payload, key=key)
                self.post('manager', f'projects/{project.pk}/reopen/', payload, key=key)
                project.refresh_from_db()
                sale.refresh_from_db()
                self.assertEqual((project.status, sale.status), (status, status))
                self.assertIsNone(sale.contract_date)
                self.assertFalse(Entry.objects.filter(project=project).exists())
                self.post('manager', f'projects/{project.pk}/reopen/', payload, status=409)

    def test_standalone_and_signed_execution_projects_reopen_active(self):
        from apps.business.models import Project

        standalone = Project.objects.create(
            code='STANDALONE-AUDIT',
            name='直接执行项目',
            customer=self.customer,
            manager=self.users['manager'],
            status='active',
        )
        for project in [standalone, self.project]:
            self.post('manager', f'projects/{project.pk}/cancel/', {'reason': '暂缓执行'})
            self.post('manager', f'projects/{project.pk}/reopen/', {'reason': '继续执行'})
            project.refresh_from_db()
            self.assertEqual(project.status, 'active')
        self.assertFalse(Entry.objects.filter(project=standalone).exists())
        self.assertFalse(Entry.objects.get(project=self.project).cancelled)
