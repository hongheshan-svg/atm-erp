import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.business.models import Entry, PurchaseLine, PurchaseOrder, StockMove
from apps.business.services.purchase_changes import REQUEST, REVIEW, pending_requests
from apps.core.models import ActionReceipt, AuditLog

from .test_commercial_chain import TODAY, BusinessFixtures


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

    def test_submitted_cannot_edit_cancel_or_delete_even_without_a_request(self):
        self.post('purchaser', self.url + 'edit/', {}, status=409)
        for role in ['purchaser', 'purchase_manager', 'admin']:
            self.post(role, self.url + 'cancel-remainder/', {'reason': '不能直接作废'}, status=409)
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


class PurchaseChangeConcurrencyTests(PurchaseChangeFixtures, TransactionTestCase):
    def together(self, requests):
        barrier = Barrier(len(requests))

        def perform(spec):
            role, action, data = spec
            close_old_connections()
            try:
                client = APIClient()
                client.force_authenticate(User.objects.get(pk=self.users[role].pk))
                barrier.wait(timeout=10)
                response = client.post(
                    '/api/business/' + self.url + action,
                    data,
                    format='json',
                    HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
                )
                return response.status_code, response.data
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=len(requests)) as pool:
            return list(pool.map(perform, requests))

    def test_request_racing_approval_has_only_one_winner(self):
        results = self.together(
            [
                ('purchaser', 'request-change/', {'reason': '修正数量'}),
                ('manager', 'approve/', {}),
            ]
        )
        self.assertEqual(sorted(status for status, _ in results), [200, 409], results)
        self.order.refresh_from_db()
        approved = self.order.status == 'approved'
        self.assertEqual(Entry.objects.filter(purchase=self.order).count(), int(approved))
        self.assertEqual(bool(pending_requests([self.order])), not approved)

    def test_duplicate_requests_and_reviews_are_serialized(self):
        results = self.together([('purchaser', 'request-change/', {'reason': '修改'})] * 2)
        self.assertEqual(sorted(status for status, _ in results), [200, 409], results)
        request_id = AuditLog.objects.get(operation=REQUEST).pk
        results = self.together(
            [('manager', 'review-change/', {'request_id': request_id, 'decision': 'approve', 'reason': '同意'})] * 2
        )
        self.assertEqual(sorted(status for status, _ in results), [200, 409], results)
        self.assertEqual(AuditLog.objects.filter(operation=REVIEW).count(), 1)
        self.assertFalse(Entry.objects.filter(purchase=self.order).exists())
