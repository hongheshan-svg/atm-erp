import uuid
from decimal import Decimal

from django.db import connection
from django.test import TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.business.models import Entry, PurchaseLine, PurchaseOrder, StockMove
from apps.business.services.purchase_changes import REQUEST, REVIEW, pending_requests
from apps.core.models import ActionReceipt, AuditLog

from .test_commercial_chain import TODAY, BusinessFixtures, ConcurrencyHelpers


class PurchaseChangeFixtures(BusinessFixtures):
    def setUp(self):
        self.setup_business()
        self.project = self.active_project()
        self.order = self.purchase(self.project, approve=False)
        self.url = f'purchases/{self.order.pk}/'

    def request_change(self, role='purchaser', **kwargs):
        self.post(role, self.url + 'request-change/', {'reason': '第1项数量应为3'}, **kwargs)
        self.order.refresh_from_db()
        return pending_requests([self.order])[self.order.pk]['id']

    def review(self, request_id, decision='approve', role='manager', **kwargs):
        return self.post(
            role,
            self.url + 'review-change/',
            {'request_id': request_id, 'decision': decision, 'reason': '已核实供应商确认记录'},
            **kwargs,
        )

    def detail(self, role='purchaser'):
        response = self.clients[role].get('/api/business/' + self.url)
        self.assertEqual(response.status_code, 200, response.data)
        return response.data


class PurchaseChangeTests(PurchaseChangeFixtures, TestCase):
    def test_request_review_edit_resubmit_preserves_approval_and_payable(self):
        before = list(self.order.lines.values('quantity', 'unit_price'))
        request_id = self.request_change()
        self.assertEqual(self.order.status, 'submitted')
        self.assertEqual(list(self.order.lines.values('quantity', 'unit_price')), before)
        self.assertEqual(self.detail()['change_request']['reason'], '第1项数量应为3')
        self.assertFalse(self.detail()['can_review_change'])
        self.assertTrue(self.detail('manager')['can_review_change'])
        for action, data in [('approve/', {}), ('approve-over-budget/', {}), ('reject/', {'reason': '绕过申请'})]:
            self.post('manager', self.url + action, data, status=409)
        self.assertFalse(Entry.objects.filter(purchase=self.order).exists())
        self.review(request_id)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'draft')
        self.assertIsNone(self.detail()['change_request'])
        self.assertFalse(Entry.objects.filter(purchase=self.order).exists())
        line = self.order.lines.get()
        self.post(
            'purchaser',
            self.url + 'edit/',
            {
                'expected_updated_at': self.order.updated_at.isoformat(),
                'reason': '更正数量',
                'due_date': TODAY,
                'lines': [{'id': line.pk, 'quantity': '3', 'unit_price': '80', 'due_date': TODAY}],
            },
        )
        self.post('purchaser', self.url + 'submit/')
        self.assertIsNone(self.detail()['change_request'])
        self.post('manager', self.url + 'approve/')
        self.assertEqual(Entry.objects.get(purchase=self.order).amount, 240)
        self.assertFalse(StockMove.objects.exists())
        history = self.clients['purchaser'].get('/api/business/' + self.url + 'handling-history/').data['results']
        review = next(row for row in history if row['operation'] == REVIEW)
        self.assertEqual(review['request_id'], request_id)
        self.assertEqual(review['decision'], 'approve')

    def test_decline_keeps_original_and_stale_review_cannot_resolve_new_request(self):
        request_id = self.request_change()
        self.review(request_id, 'reject')
        self.assertEqual(self.detail()['status'], 'submitted')
        self.assertIsNone(self.detail()['change_request'])
        self.assertEqual(self.order.lines.get().quantity, 5)
        new_id = self.request_change()
        self.assertNotEqual(new_id, request_id)
        self.review(request_id, status=409)
        self.assertEqual(self.detail()['change_request']['id'], new_id)
        self.review(new_id, 'reject')
        self.post('manager', self.url + 'approve/')
        self.assertEqual(Entry.objects.get(purchase=self.order).amount, 500)

    def test_submitted_can_be_voided_like_draft_unless_a_change_request_is_pending(self):
        request_id = self.request_change()
        for role in ['purchaser', 'purchase_manager', 'admin']:
            response = self.post(role, self.url + 'cancel-remainder/', {'reason': '供应商选错'}, status=409)
            self.assertIn('待处理的修改申请', str(response))
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'submitted')
        self.assertEqual(pending_requests([self.order])[self.order.pk]['id'], request_id)
        self.review(request_id, 'reject')
        line = self.order.lines.get()
        self.post('purchaser', self.url + 'cancel-remainder/', {}, status=400)
        self.post('purchaser', self.url + 'cancel-remainder/', {'reason': ' '}, status=400)
        response = self.post(
            'purchaser',
            self.url + 'cancel-remainder/',
            {'reason': '整单作废', 'lines': [{'line': line.pk}]},
            status=400,
        )
        self.assertIn('未批准采购请整单作废', str(response))
        for role in ['warehouse', 'finance', 'member']:
            self.post(role, self.url + 'cancel-remainder/', {'reason': '无权作废'}, status=403)
        approvals = self.clients['manager'].get('/api/business/workbench/', {'bucket': 'approvals'}).data
        self.assertEqual(approvals['approvals']['count'], 1)
        self.post('purchaser', self.url + 'cancel-remainder/', {'reason': '供应商选错，作废重建'})
        self.order.refresh_from_db()
        line.refresh_from_db()
        self.assertEqual(self.order.status, 'cancelled')
        self.assertEqual(line.cancelled_quantity, line.quantity)
        self.assertFalse(Entry.objects.filter(purchase=self.order).exists())
        self.assertFalse(StockMove.objects.exists())
        log = AuditLog.objects.get(operation='purchase.cancel_remainder', resource=f'purchaseorder:{self.order.pk}')
        self.assertEqual(log.detail['reason'], '供应商选错，作废重建')
        # 与草稿作废同一审计：记录作废金额；待审批单没有应付，不产生冲减。
        self.assertEqual(Decimal(log.detail['credit']), Decimal('500.00'))
        approvals = self.clients['manager'].get('/api/business/workbench/', {'bucket': 'approvals'}).data
        self.assertEqual(approvals['approvals']['count'], 0)
        for action, data in [
            ('approve/', {}),
            ('reject/', {'reason': '已作废'}),
            ('request-change/', {'reason': '已作废'}),
        ]:
            self.post('manager' if action != 'request-change/' else 'purchaser', self.url + action, data, status=409)
        self.post('purchaser', self.url + 'cancel-remainder/', {'reason': '重复作废'}, status=409)

    def test_voiding_submitted_purchase_is_idempotent_for_a_repeated_key(self):
        key = str(uuid.uuid4())
        first = self.post('purchaser', self.url + 'cancel-remainder/', {'reason': '物料选错'}, key=key)
        second = self.post('purchaser', self.url + 'cancel-remainder/', {'reason': '物料选错'}, key=key)
        self.assertEqual(first, second)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'cancelled')
        self.assertEqual(AuditLog.objects.filter(operation='purchase.cancel_remainder').count(), 1)
        self.assertEqual(ActionReceipt.objects.filter(key=key).count(), 1)
        self.post('purchaser', self.url + 'cancel-remainder/', {'reason': '另一原因'}, key=key, status=409)

    def test_submitted_cannot_edit_or_delete_even_without_a_request(self):
        self.post('purchaser', self.url + 'edit/', {}, status=409)
        draft = PurchaseOrder.objects.create(
            code='DRAFT',
            project=self.project,
            supplier=self.supplier,
            due_date=TODAY,
        )
        key = str(uuid.uuid4())
        self.post(
            'admin',
            'record-deletions/',
            {
                'resource': 'purchases',
                'ids': [draft.pk, self.order.pk],
                'reason': '批量删除也拒绝',
            },
            key=key,
            status=409,
        )
        self.assertFalse(ActionReceipt.objects.filter(key=key).exists())
        self.assertTrue(PurchaseOrder.objects.filter(pk=draft.pk).exists())
        self.assertTrue(PurchaseOrder.objects.filter(pk=self.order.pk).exists())
        self.assertFalse(AuditLog.objects.filter(operation='record.delete').exists())

    def test_roles_scope_and_separation_include_requester_and_multi_role(self):
        for role in ['warehouse', 'finance', 'member', 'production_manager']:
            self.post(role, self.url + 'request-change/', {'reason': '不应允许'}, status=403)
        buyer = self.users['purchaser']
        buyer.additional_roles = ['purchase_manager']
        buyer.save()
        # The original reject endpoint cannot bypass requester/approver separation.
        self.post('purchaser', self.url + 'reject/', {'reason': '自行退回'}, status=403)
        request_id = self.request_change('purchase_manager')  # another buyer, not the original creator
        self.review(request_id, role='purchase_manager', status=403)
        self.review(request_id, role='purchaser', status=403)
        for role in ['warehouse', 'finance', 'member', 'production_manager']:
            self.review(request_id, role=role, status=403)
        self.project.manager = self.users['admin']
        self.project.save()
        self.review(request_id, status=404)  # manager has no membership; purchasing scope must not leak in
        manager = self.users['manager']
        manager.additional_roles = ['purchaser']
        manager.save()
        self.review(request_id, status=403)
        self.assertFalse(self.detail('manager')['can_review_change'])
        self.review(request_id, role='admin')

    def test_admin_self_review_is_explicit_and_audited(self):
        request_id = self.request_change('admin')
        self.post(
            'admin',
            self.url + 'review-change/',
            {
                'request_id': request_id,
                'decision': 'approve',
                'reason': '',
            },
            status=400,
        )
        self.review(request_id, role='admin')
        self.assertTrue(AuditLog.objects.get(operation=REVIEW).detail['self_approval'])

    def test_idempotent_replay_and_role_revocation(self):
        key = str(uuid.uuid4())
        request_id = self.request_change(key=key)
        self.request_change(key=key)
        self.post('purchaser', self.url + 'request-change/', {'reason': '重复申请'}, status=409)
        self.assertEqual(AuditLog.objects.filter(operation=REQUEST).count(), 1)
        review_key = str(uuid.uuid4())
        self.review(request_id, key=review_key)
        self.review(request_id, key=review_key)
        self.assertEqual(AuditLog.objects.filter(operation=REVIEW).count(), 1)
        buyer = self.users['purchaser']
        buyer.role = 'warehouse'
        buyer.save()
        self.post('purchaser', self.url + 'request-change/', {'reason': '第1项数量应为3'}, key=key, status=403)

    def test_invalid_input_ended_project_and_approved_order_leave_no_effects(self):
        for data in [{}, {'reason': ' '}, {'reason': '修改', 'quantity': 1}]:
            key = str(uuid.uuid4())
            self.post('purchaser', self.url + 'request-change/', data, key=key, status=400)
            self.assertFalse(ActionReceipt.objects.filter(key=key).exists())
        request_id = self.request_change()
        for decision in ['bad', {}, None]:
            self.post(
                'manager',
                self.url + 'review-change/',
                {
                    'request_id': request_id,
                    'decision': decision,
                    'reason': '检查',
                },
                status=400,
            )
        self.project.status = 'closed'
        self.project.save()
        self.review(request_id, status=409)
        self.project.status = 'active'
        self.project.save()
        self.review(request_id, 'reject')
        self.post('manager', self.url + 'approve/')
        self.post('purchaser', self.url + 'request-change/', {'reason': '已批准不能申请'}, status=409)
        self.assertEqual(Entry.objects.get(purchase=self.order).amount, 500)
        self.post('purchaser', self.url + 'cancel-remainder/', {'reason': '保留原取消流程'})
        self.assertEqual(Entry.objects.get(purchase=self.order).credit_amount, 500)

    def test_workbench_and_progress_show_pending_request_and_independent_reviewers(self):
        self.request_change('purchase_manager')
        for role in ['manager', 'purchase_manager']:
            work = self.clients[role].get('/api/business/workbench/', {'bucket': 'approvals'}).data
            self.assertEqual(work['approvals']['count'], 1 if role == 'manager' else 0)
            if role == 'manager':
                self.assertTrue(work['approvals']['results'][0]['change_request'])
        progress = self.clients['member'].get(
            f'/api/business/projects/{self.project.pk}/progress/', {'category': 'purchases'}
        )
        self.assertEqual(progress.status_code, 200, progress.data)
        row = progress.data['results'][0]
        self.assertEqual(row['status_label'], '修改申请待处理')
        self.assertIn('先处理采购修改申请', row['hint'])
        self.assertNotIn(self.users['purchase_manager'].pk, [p['id'] for p in row['handlers']])

    def test_pending_request_list_queries_are_bounded(self):
        self.request_change()
        counts = []
        for size in [1, 10]:
            for index in range(PurchaseOrder.objects.count(), size):
                purchase = PurchaseOrder.objects.create(
                    code=f'BOUND{index}',
                    project=self.project,
                    supplier=self.supplier,
                    due_date=TODAY,
                    status='submitted',
                    created_by=self.users['purchaser'],
                )
                PurchaseLine.objects.create(purchase=purchase, item=self.item, quantity=1, unit_price=1)
                AuditLog.objects.create(
                    resource=f'purchaseorder:{purchase.pk}',
                    actor=self.users['purchaser'],
                    operation=REQUEST,
                    detail={'reason': '批量查询测试'},
                )
            with CaptureQueriesContext(connection) as queries:
                response = self.clients['manager'].get('/api/business/purchases/', {'page_size': size})
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(len(response.data['results']), size)
            self.assertTrue(all(row['can_review_change'] for row in response.data['results']))
            counts.append(len(queries))
        self.assertEqual(*counts)


class PurchaseChangeConcurrencyTests(ConcurrencyHelpers, PurchaseChangeFixtures, TransactionTestCase):
    def test_request_racing_approval_has_only_one_winner(self):
        results = self.together(
            [
                ('purchaser', self.url + 'request-change/', {'reason': '修正数量'}),
                ('manager', self.url + 'approve/', {}),
            ]
        )
        self.assertEqual(sorted(status for status, _ in results), [200, 409], results)
        self.order.refresh_from_db()
        approved = self.order.status == 'approved'
        self.assertEqual(Entry.objects.filter(purchase=self.order).count(), int(approved))
        self.assertEqual(bool(pending_requests([self.order])), not approved)

    def test_duplicate_requests_and_reviews_are_serialized(self):
        results = self.together([('purchaser', self.url + 'request-change/', {'reason': '修改'})] * 2)
        self.assertEqual(sorted(status for status, _ in results), [200, 409], results)
        request_id = AuditLog.objects.get(operation=REQUEST).pk
        results = self.together(
            [
                (
                    'manager',
                    self.url + 'review-change/',
                    {'request_id': request_id, 'decision': 'approve', 'reason': '同意'},
                )
            ]
            * 2
        )
        self.assertEqual(sorted(status for status, _ in results), [200, 409], results)
        self.assertEqual(AuditLog.objects.filter(operation=REVIEW).count(), 1)
        self.assertFalse(Entry.objects.filter(purchase=self.order).exists())


class PurchaseUnapproveTests(PurchaseChangeFixtures, TestCase):
    """反审：已批准、已收货的采购单退回草稿，冲回收货、作废应付；重新批准沿用原应付。"""

    def setUp(self):
        super().setUp()
        self.order = self.purchase(self.project)
        self.url = f'purchases/{self.order.pk}/'

    def receive(self, quantity, pending='0', order=None):
        order = order or self.order
        return self.post(
            'warehouse',
            f'purchases/{order.pk}/receive/',
            {'lines': [{'line': order.lines.get().pk, 'quantity': quantity, 'pending_quantity': pending}]},
        )

    def check(self, role='manager'):
        return self.get(role, self.url + 'unapprove-check/')

    def unapprove(self, role='manager', reason='第1项单价应为80', **kwargs):
        return self.post(role, self.url + 'unapprove/', {'reason': reason}, **kwargs)

    def stock(self):
        from apps.business.models import Stock

        stock = Stock.objects.get(item=self.item)
        return stock.quantity, stock.value

    def test_received_order_returns_to_draft_and_reapproval_reuses_the_payable(self):
        from apps.business.models import BOMLine

        BOMLine.objects.create(project=self.project, item=self.item, quantity=5)
        self.receive('3')
        self.receive('2')
        entry = Entry.objects.get(purchase=self.order)
        demand = self.get('purchaser', f'projects/{self.project.pk}/demand/')['lines']
        self.assertEqual(demand[0]['last_received_date'], timezone.localdate().isoformat())
        preview = self.check()
        self.assertTrue(preview['can_unapprove'], preview)
        self.assertEqual([row['quantity'] for row in preview['receipts']], ['3', '2'])
        self.assertEqual(preview['payable'], '500.00')
        for role in ('purchaser', 'warehouse', 'finance'):
            self.unapprove(role, status=403)
        self.unapprove(reason='', status=400)
        self.unapprove()
        self.order.refresh_from_db()
        entry.refresh_from_db()
        line = self.order.lines.get()
        self.assertEqual(self.order.status, 'draft')
        self.assertEqual((line.received_quantity, line.cancelled_quantity), (0, 0))
        self.assertEqual(self.stock(), (Decimal('0'), Decimal('0')))
        self.assertTrue(entry.cancelled)
        self.assertEqual(entry.credit_amount, entry.amount)
        reversals = StockMove.objects.filter(kind='receipt_reversal').order_by('pk')
        self.assertEqual(
            [(m.quantity, m.value, m.supplier_credit) for m in reversals],
            [
                (Decimal('-3'), Decimal('-300'), Decimal('300')),
                (Decimal('-2'), Decimal('-200'), Decimal('200')),
            ],
        )
        self.assertEqual({m.source.kind for m in reversals}, {'receipt'})
        detail = self.detail('manager')
        self.assertEqual(detail['lines'][0]['receipts'], [])
        # 冲回的收货不再算本项目入库日期。
        demand = self.get('purchaser', f'projects/{self.project.pk}/demand/')['lines']
        self.assertIsNone(demand[0]['last_received_date'])
        # 冲回的收货批次不能再登记质保。
        self.assertEqual(self.get('manager', self.url + 'warranty/')['receipts'], [])
        moves = self.get('warehouse', 'moves/', {'kind': 'receipt'})['results']
        self.assertTrue(all(row['reversed'] for row in moves))
        old = StockMove.objects.filter(kind='receipt').first()
        self.post('warehouse', f'moves/{old.pk}/return-purchase/', {'quantity': '1', 'reason': '退货'}, status=409)
        self.post('finance', f'entries/{entry.pk}/pay/', {'amount': '1', 'date': TODAY, 'reason': '付款'}, status=409)
        history = self.get('purchaser', self.url + 'handling-history/')['results']
        record = next(row for row in history if row['operation'] == 'purchase.unapprove')
        self.assertEqual(record['reason'], '第1项单价应为80')
        self.assertIn('重新提交审批', record['next_step'])

        self.post(
            'purchaser',
            self.url + 'edit/',
            {
                'expected_updated_at': self.order.updated_at.isoformat(),
                'reason': '供应商确认单价',
                'due_date': TODAY,
                'lines': [{'id': line.pk, 'quantity': '5', 'unit_price': '80', 'due_date': TODAY}],
            },
        )
        self.post('purchaser', self.url + 'submit/')
        self.post('manager', self.url + 'approve/')
        self.assertEqual(Entry.objects.filter(purchase=self.order).count(), 1)
        entry.refresh_from_db()
        self.assertEqual((entry.amount, entry.credit_amount, entry.cancelled), (Decimal('400'), Decimal('0'), False))
        self.receive('5')
        self.assertEqual(self.stock(), (Decimal('5'), Decimal('400')))
        detail = self.get('finance', f'entries/{entry.pk}/')
        self.assertEqual([row['amount'] for row in detail['payment_schedule']], ['400.00'])
        self.assertEqual([row['quantity'] for row in self.detail('manager')['lines'][0]['receipts']], ['5.000'])
        cost = self.get('finance', f'projects/{self.project.pk}/cost/')
        self.assertEqual(cost['purchase_return_variance'], '0.00')
        from apps.business.services.monthly import entry_totals

        month = timezone.localdate().strftime('%Y-%m')
        self.assertEqual(entry_totals(Entry.objects.get(pk=entry.pk), month)['received'], '400.00')
        # 再次反审只冲回尚未冲回的这一次收货。
        self.unapprove(reason='数量再次更正')
        self.assertEqual(StockMove.objects.filter(kind='receipt_reversal').count(), 3)
        self.assertEqual(self.stock(), (Decimal('0'), Decimal('0')))

    def test_approved_order_without_receipts_just_returns_to_draft(self):
        self.assertEqual(self.check()['receipts'], [])
        self.unapprove()
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'draft')
        self.assertFalse(StockMove.objects.exists())
        self.assertTrue(Entry.objects.get(purchase=self.order).cancelled)
        self.unapprove(status=409)
        self.post('purchaser', self.url + 'submit/')
        self.unapprove(status=409)

    def test_blockers_are_listed_and_nothing_changes(self):
        self.receive('3', pending='1')
        problems = self.check()['problems']
        self.assertTrue(any('隔离' in text for text in problems), problems)
        self.unapprove(status=409)
        self.post(
            'warehouse',
            self.url + 'quality-accept/',
            {'lines': [{'line': self.order.lines.get().pk, 'quantity': '1'}], 'reason': '复检合格'},
        )
        entry = Entry.objects.get(purchase=self.order)
        statement = self.reconciliation_data(entry, prepayment=True)
        payment = self.post(
            'finance', f'entries/{entry.pk}/pay/', {'amount': '100', 'date': TODAY, 'reason': '付款', **statement}
        )
        problems = self.check()['problems']
        self.assertTrue(any('已付款 100' in text for text in problems), problems)
        self.assertTrue(any('对账单' in text for text in problems), problems)
        self.unapprove(status=409)
        self.post('finance', f'payments/{payment["id"]}/reverse/', {'date': TODAY, 'reason': '付款录入有误'})
        self.post('finance', f'reconciliations/{statement["reconciliation"]}/void/', {'reason': '改单后重新对账'})
        receipt = StockMove.objects.filter(kind='receipt').first()
        self.post('warehouse', f'moves/{receipt.pk}/return-purchase/', {'quantity': '1', 'reason': '供应商确认退货'})
        problems = self.check()['problems']
        self.assertEqual(len(problems), 1, problems)
        self.assertIn('采购退货', problems[0])
        before = (self.stock(), Entry.objects.get(pk=entry.pk).credit_amount, StockMove.objects.count())
        self.unapprove(status=409)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'partial')
        self.assertEqual(
            before, (self.stock(), Entry.objects.get(pk=entry.pk).credit_amount, StockMove.objects.count())
        )

    def test_issued_goods_and_other_projects_arrivals_block_reversal(self):
        from apps.business.models import Stock

        projects = [self.active_project(), self.active_project()]
        for project in projects:
            self.post(
                'manager',
                f'projects/{project.pk}/revise-bom/',
                {'expected_revision': self.bom_version(project.pk), 'lines': [{'item': self.item.pk, 'quantity': '5'}]},
            )
        mine, theirs = (self.purchase(project) for project in projects)
        self.url = f'purchases/{mine.pk}/'
        self.receive('5', order=mine)
        stock = Stock.objects.get(item=self.item)
        self.post(
            'warehouse',
            'stocks/issue/',
            {'project': projects[0].pk, 'stock': stock.pk, 'quantity': '2', 'reason': '生产领料'},
        )
        problems = self.check()['problems']
        self.assertTrue(any('现有库存 3' in text and '冲回需要 5' in text for text in problems), problems)
        # 另一项目到货后库存够数，但冲回会吃掉它还没领的到货：说明被领走的是本单的货。
        self.receive('5', order=theirs)
        problems = self.check()['problems']
        self.assertEqual(len(problems), 1, problems)
        self.assertIn(f'{projects[1].code} 5', problems[0])
        self.unapprove(status=409)
        self.assertEqual(Stock.objects.get(item=self.item).quantity, Decimal('8'))

    def test_applicant_cannot_unapprove_own_order_admin_needs_reason(self):
        data = self.post(
            'manager',
            'purchases/',
            {
                'project': self.project.pk,
                'supplier': self.supplier.pk,
                'due_date': TODAY,
                'lines': [{'item': self.item.pk, 'quantity': '1', 'unit_price': '10'}],
            },
            status=201,
        )
        self.url = f'purchases/{data["id"]}/'
        self.post('manager', self.url + 'submit/')
        self.post('admin', self.url + 'approve/', {'reason': '经理本人申请，由管理员审批'})
        self.assertFalse(self.check()['can_unapprove'])
        self.unapprove(status=403)
        self.assertTrue(self.check('admin')['can_unapprove'])
        self.unapprove('admin')
        log = AuditLog.objects.get(operation='purchase.unapprove')
        self.assertEqual(log.detail['previous_status'], 'approved')
        self.assertFalse(log.detail['self_approval'])

    def test_list_shows_submitter_and_why_a_draft_came_back(self):
        def row(order):
            results = self.get('purchaser', 'purchases/', {'page_size': 50})['results']
            return next(item for item in results if item['id'] == order.pk)

        listed = row(self.order)
        self.assertEqual((listed['created_by_name'], listed['submitted_by_name']), ('purchaser', 'purchaser'))
        self.assertEqual((listed['returned_action'], listed['returned_note']), ('', ''))
        other = self.purchase(self.project, approve=False)
        self.post('manager', f'purchases/{other.pk}/reject/', {'reason': '第1项单价偏高，请重新询价'})
        listed = row(other)
        self.assertEqual(listed['returned_action'], '退回修改')
        self.assertTrue(listed['returned_note'].startswith('manager '), listed['returned_note'])
        self.assertEqual(listed['returned_reason'], '第1项单价偏高，请重新询价')
        self.assertTrue(
            listed['returned_note'].endswith('退回修改：第1项单价偏高，请重新询价'), listed['returned_note']
        )
        self.post('purchaser', f'purchases/{other.pk}/submit/')
        self.assertEqual(row(other)['returned_action'], '')
        self.unapprove()
        listed = row(self.order)
        self.assertEqual(listed['returned_action'], '反审')
        self.assertIn('反审：第1项单价应为80', listed['returned_note'])
        self.assertEqual(listed['submitted_by_name'], 'purchaser')
        drafts = self.get('purchaser', 'workbench/')['drafts']['results']
        self.assertEqual({item['returned_action'] for item in drafts}, {'反审'})


class PurchaseUnapproveConcurrencyTests(ConcurrencyHelpers, PurchaseChangeFixtures, TransactionTestCase):
    def test_unapprove_racing_purchase_return_has_one_winner(self):
        order = self.purchase(self.project)
        self.post(
            'warehouse', f'purchases/{order.pk}/receive/', {'lines': [{'line': order.lines.get().pk, 'quantity': '5'}]}
        )
        receipt = StockMove.objects.get(kind='receipt')
        results = self.together(
            [
                ('manager', f'purchases/{order.pk}/unapprove/', {'reason': '单价有误'}),
                ('warehouse', f'moves/{receipt.pk}/return-purchase/', {'quantity': '1', 'reason': '供应商确认退货'}),
            ]
        )
        self.assertEqual(sorted(status for status, _ in results), [200, 409], results)
        order.refresh_from_db()
        reversed_ = StockMove.objects.filter(kind='receipt_reversal').exists()
        returned = StockMove.objects.filter(kind='purchase_return').exists()
        self.assertNotEqual(reversed_, returned)
        self.assertEqual(order.status, 'draft' if reversed_ else 'received')
