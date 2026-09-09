import uuid
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.business.models import (
    BOMLine,
    Entry,
    Item,
    Partner,
    Payment,
    Project,
    PurchaseOrder,
    SalesOrder,
    Stock,
    StockMove,
)
from apps.core.models import ActionReceipt, CodeRule

TODAY = '2026-09-09'


class BusinessFixtures:
    def bom_version(self, project_id):
        response = self.clients['manager'].get(f'/api/business/projects/{project_id}/demand/')
        self.assertEqual(response.status_code, 200, response.data)
        return response.data['revision']

    def setup_business(self):
        self.users = {role: User.objects.create_user(username=role, role=role) for role in User.Role.values}
        self.clients = {}
        for role, user in self.users.items():
            client = APIClient()
            client.force_authenticate(user)
            self.clients[role] = client
        for key, prefix in [
            ('project', 'PRJ'),
            ('sale', 'SO'),
            ('purchase', 'PO'),
            ('delivery', 'DEL'),
            ('item', 'MAT'),
            ('partner', 'PTY'),
        ]:
            CodeRule.objects.create(key=key, prefix=prefix)
        self.customer = Partner.objects.create(code='C1', name='客户', kind='customer')
        self.supplier = Partner.objects.create(code='S1', name='供应商', kind='supplier')
        self.item = Item.objects.create(code='I1', name='伺服电机')

    def post(self, role, url, data=None, *, key=None, status=200):
        response = self.clients[role].post(
            '/api/business/' + url, data or {}, format='json', HTTP_IDEMPOTENCY_KEY=key or str(uuid.uuid4())
        )
        self.assertEqual(response.status_code, status, response.data)
        return response.data

    def active_project(self, amount='10000.00', equipment=1, warranty=12):
        sale = self.post(
            'manager',
            'sales/',
            {
                'name': '自动装配线',
                'customer': self.customer.pk,
                'manager': self.users['manager'].pk,
                'equipment_quantity': equipment,
                'warranty_months': warranty,
            },
            status=201,
        )
        self.post('manager', f'sales/{sale["id"]}/quote/', {'amount': amount, 'reason': '双方确认方案'})
        result = self.post(
            'manager',
            f'sales/{sale["id"]}/sign/',
            {
                'date': TODAY,
                'members': [self.users['member'].pk],
                'milestones': [{'title': '合同款', 'amount': amount, 'due_date': TODAY}],
            },
        )
        return Project.objects.get(pk=result['project'])

    def purchase(self, project, qty='5.000', price='100.00', *, approve=True):
        data = self.post(
            'purchaser',
            'purchases/',
            {
                'project': project.pk,
                'supplier': self.supplier.pk,
                'due_date': TODAY,
                'lines': [{'item': self.item.pk, 'quantity': qty, 'unit_price': price}],
            },
            status=201,
        )
        purchase = PurchaseOrder.objects.get(pk=data['id'])
        self.post('purchaser', f'purchases/{purchase.pk}/submit/')
        if approve:
            self.post('manager', f'purchases/{purchase.pk}/approve/')
        purchase.refresh_from_db()
        return purchase


class CommercialChainTests(BusinessFixtures, TestCase):
    def setUp(self):
        self.setup_business()

    def test_quote_contract_bom_purchase_receipt_and_settlement(self):
        project = self.active_project()
        self.assertEqual(project.contract_amount, Decimal('10000.00'))
        self.post(
            'manager',
            f'projects/{project.pk}/revise-bom/',
            {'expected_revision': self.bom_version(project.pk), 'lines': [{'item': self.item.pk, 'quantity': '5.000'}]},
        )
        bom = BOMLine.objects.get(project=project)
        demand = self.clients['purchaser'].get(f'/api/business/projects/{project.pk}/demand/').data
        self.assertEqual(Decimal(demand['lines'][0]['shortage']), Decimal('5'))
        result = self.post(
            'purchaser',
            'purchases/',
            {
                'project': project.pk,
                'supplier': self.supplier.pk,
                'due_date': TODAY,
                'from_demand': True,
                'lines': [{'item': self.item.pk, 'bom_line': bom.pk, 'quantity': '5', 'unit_price': '100'}],
            },
            status=201,
        )
        purchase = PurchaseOrder.objects.get(pk=result['id'])
        self.post('purchaser', f'purchases/{purchase.pk}/submit/')
        approve_key = str(uuid.uuid4())
        self.post('manager', f'purchases/{purchase.pk}/approve/', key=approve_key)
        self.post('manager', f'purchases/{purchase.pk}/approve/', key=approve_key)
        self.assertEqual(Entry.objects.filter(purchase=purchase).count(), 1)
        line = purchase.lines.get()
        receipt_key = str(uuid.uuid4())
        payload = {'lines': [{'line': line.pk, 'quantity': '2'}], 'reason': '第一批到货'}
        self.post('warehouse', f'purchases/{purchase.pk}/receive/', payload, key=receipt_key)
        self.post('warehouse', f'purchases/{purchase.pk}/receive/', payload, key=receipt_key)
        self.post(
            'warehouse',
            f'purchases/{purchase.pk}/receive/',
            {'lines': [{'line': line.pk, 'quantity': '3'}], 'reason': '第二批到货'},
        )
        stock = Stock.objects.get(item=self.item)
        self.assertEqual((stock.quantity, stock.value), (Decimal('5'), Decimal('500')))
        self.assertEqual(StockMove.objects.count(), 2)
        purchase.refresh_from_db()
        self.assertEqual(purchase.status, 'received')
        payable = Entry.objects.get(purchase=purchase)
        receivable = Entry.objects.get(project=project, kind='receivable')
        for entry in (payable, receivable):
            self.post(
                'finance',
                f'entries/{entry.pk}/pay/',
                {'amount': str(entry.amount), 'date': TODAY, 'reason': '银行已确认'},
            )
            response = self.clients['finance'].get(f'/api/business/entries/{entry.pk}/')
            self.assertEqual(Decimal(response.data['balance']), 0)
        self.assertEqual(Payment.objects.count(), 2)
        cost = self.clients['finance'].get(f'/api/business/projects/{project.pk}/cost/').data
        self.assertEqual(cost['total'], '0.00', '库存尚未领用，采购付款不能重复算为项目成本')

    def test_masterdata_creation_and_edit_generate_codes_without_privilege_fields(self):
        item_id = self.post('purchaser', 'items/', {'name': '气缸', 'unit': '件'}, status=201)['id']
        self.assertEqual(Item.objects.get(pk=item_id).code, 'MAT000001')
        response = self.clients['purchaser'].patch(
            f'/api/business/items/{item_id}/',
            {'is_active': False},
            format='json',
            HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.post('member', 'items/', {'name': '非法新建'}, status=403)
        self.post('purchaser', 'items/', {'name': '非法字段', 'created_by': 1}, status=400)

    def test_manual_item_codes_reserve_automatic_numbers_and_cannot_be_edited(self):
        manual = self.post('purchaser', 'items/', {'name': '企业物料', 'code': ' MAT000001 '}, status=201)
        self.post('purchaser', 'items/', {'name': '重复', 'code': 'MAT000001'}, status=400)
        auto = self.post('purchaser', 'items/', {'name': '自动编码'}, status=201)
        self.assertEqual(Item.objects.get(pk=auto['id']).code, 'MAT000002')
        obj = Item.objects.get(pk=manual['id'])
        obj.soft_delete(self.users['purchaser'])
        self.post('purchaser', 'items/', {'name': '已删除编码仍占用', 'code': 'MAT000001'}, status=400)
        response = self.clients['purchaser'].patch(
            f'/api/business/items/{auto["id"]}/',
            {'code': 'CHANGED'},
            format='json',
            HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Item.objects.get(pk=auto['id']).code, 'MAT000002')

    def test_contract_node_mismatch_rolls_back_and_same_key_can_retry(self):
        project = SalesOrder.objects.create(
            code='P0',
            name='测试',
            customer=self.customer,
            manager=self.users['manager'],
            status='quoted',
            quote_amount=100,
        )
        key = str(uuid.uuid4())
        self.post(
            'manager',
            f'sales/{project.pk}/sign/',
            {'date': TODAY, 'milestones': [{'title': '首款', 'amount': '99', 'due_date': TODAY}]},
            key=key,
            status=400,
        )
        self.assertFalse(Entry.objects.exists())
        self.assertFalse(ActionReceipt.objects.filter(key=key).exists())
        project.refresh_from_db()
        self.assertEqual(project.status, 'quoted')
        self.post(
            'manager',
            f'sales/{project.pk}/sign/',
            {'date': TODAY, 'milestones': [{'title': '首款', 'amount': '100', 'due_date': TODAY}]},
            key=key,
        )

    def test_numeric_inputs_reject_nan_precision_negative_and_overflow(self):
        project = self.active_project()
        for value in ['NaN', 'Infinity', '-1', '1.001', '10000000000000000', True]:
            with self.subTest(value=value):
                self.post(
                    'purchaser',
                    'purchases/',
                    {
                        'project': project.pk,
                        'supplier': self.supplier.pk,
                        'due_date': TODAY,
                        'lines': [{'item': self.item.pk, 'quantity': '1', 'unit_price': value}],
                    },
                    status=400,
                )
        self.assertFalse(PurchaseOrder.objects.exists())
        self.assertEqual(CodeRule.objects.get(key='purchase').counter, 0)

    def test_roles_scope_and_sensitive_fields(self):
        project = self.active_project()
        purchase = self.purchase(project)
        unrelated = Project.objects.create(
            code='HIDDEN', name='无关项目', customer=self.customer, manager=self.users['manager']
        )
        response = self.clients['member'].get('/api/business/projects/')
        self.assertEqual([row['id'] for row in response.data['results']], [project.pk])
        self.assertNotIn('contract_amount', response.data['results'][0])
        self.assertEqual(self.clients['member'].get(f'/api/business/projects/{unrelated.pk}/').status_code, 404)
        self.assertEqual(self.clients['member'].get(f'/api/business/projects/{unrelated.pk}/demand/').status_code, 404)
        self.assertEqual(self.clients['warehouse'].get('/api/business/entries/').status_code, 403)
        warehouse = self.clients['warehouse'].get(f'/api/business/purchases/{purchase.pk}/').data
        self.assertNotIn('unit_price', warehouse['lines'][0])
        self.post('purchaser', f'purchases/{purchase.pk}/approve/', status=403)
        self.post('manager', f'purchases/{purchase.pk}/receive/', {'reason': '越权', 'lines': []}, status=403)

    def test_partial_receipt_cancellation_and_overpaid_refund(self):
        project = self.active_project()
        purchase = self.purchase(project)
        entry = Entry.objects.get(purchase=purchase)
        self.post('finance', f'entries/{entry.pk}/pay/', {'amount': '500', 'date': TODAY, 'reason': '预付'})
        self.post(
            'warehouse',
            f'purchases/{purchase.pk}/receive/',
            {'lines': [{'line': purchase.lines.get().pk, 'quantity': '2'}], 'reason': '到货两件'},
        )
        self.post('purchaser', f'purchases/{purchase.pk}/cancel-remainder/', {'reason': '供应商无法提供剩余三件'})
        entry.refresh_from_db()
        self.assertEqual(entry.amount, Decimal('500'))
        self.assertEqual(entry.credit_amount, Decimal('300'))
        self.assertEqual(self.clients['finance'].get(f'/api/business/entries/{entry.pk}/').data['balance'], '-300.00')
        self.post(
            'finance', f'entries/{entry.pk}/refund/', {'amount': '301', 'date': TODAY, 'reason': '超额'}, status=409
        )
        self.post('finance', f'entries/{entry.pk}/refund/', {'amount': '300', 'date': TODAY, 'reason': '退款到账'})
        self.assertEqual(Decimal(self.clients['finance'].get(f'/api/business/entries/{entry.pk}/').data['balance']), 0)
        self.assertEqual(Stock.objects.get().quantity, Decimal('2'))

    def test_receipts_preserve_fractional_cent_total(self):
        project = self.active_project()
        purchase = self.purchase(project, qty='0.003', price='3.33')
        line = purchase.lines.get()
        for _ in range(3):
            self.post(
                'warehouse',
                f'purchases/{purchase.pk}/receive/',
                {'lines': [{'line': line.pk, 'quantity': '0.001'}], 'reason': '分批称量'},
            )
        self.assertEqual(Entry.objects.get(purchase=purchase).amount, Decimal('0.01'))
        self.assertEqual(Stock.objects.get().value, Decimal('0.01'))
        self.assertEqual(sum(StockMove.objects.values_list('value', flat=True)), Decimal('0.01'))

    def test_receipt_overflow_and_foreign_line_are_atomic(self):
        project = self.active_project()
        first = self.purchase(project)
        second = self.purchase(project)
        self.post(
            'warehouse',
            f'purchases/{first.pk}/receive/',
            {'reason': '错误单行', 'lines': [{'line': second.lines.get().pk, 'quantity': '1'}]},
            status=400,
        )
        self.post(
            'warehouse',
            f'purchases/{first.pk}/receive/',
            {'reason': '超收', 'lines': [{'line': first.lines.get().pk, 'quantity': '6'}]},
            status=409,
        )
        self.assertFalse(Stock.objects.exists())
        self.assertFalse(StockMove.objects.exists())

    def test_bom_revision_cannot_erase_ordered_quantity_or_use_stale_version(self):
        project = self.active_project()
        stale = self.clients['manager'].get(f'/api/business/projects/{project.pk}/demand/').data['revision']
        self.post(
            'manager',
            f'projects/{project.pk}/revise-bom/',
            {'expected_revision': self.bom_version(project.pk), 'lines': [{'item': self.item.pk, 'quantity': '5'}]},
        )
        self.post(
            'manager',
            f'projects/{project.pk}/revise-bom/',
            {'expected_revision': stale, 'lines': [{'item': self.item.pk, 'quantity': '6', 'change_note': '旧预览'}]},
            status=409,
        )
        self.purchase(project)
        self.post(
            'manager',
            f'projects/{project.pk}/revise-bom/',
            {
                'expected_revision': self.bom_version(project.pk),
                'lines': [{'item': self.item.pk, 'quantity': '4', 'change_note': '减少'}],
            },
            status=409,
        )
        self.assertEqual(BOMLine.objects.get().quantity, Decimal('5'))

    def test_bom_requires_valid_version_without_partial_writes(self):
        project = self.active_project()
        payload = {'lines': [{'item': self.item.pk, 'quantity': '5'}]}
        self.post('manager', f'projects/{project.pk}/revise-bom/', payload, status=400)
        for version in [None, '', 123, 'invalid']:
            key = str(uuid.uuid4())
            self.post(
                'manager',
                f'projects/{project.pk}/revise-bom/',
                {**payload, 'expected_revision': version},
                key=key,
                status=400,
            )
            self.assertFalse(ActionReceipt.objects.filter(key=key).exists())
        self.assertFalse(BOMLine.objects.exists())
        self.post(
            'manager',
            f'projects/{project.pk}/revise-bom/',
            {**payload, 'expected_revision': self.bom_version(project.pk)},
        )
        self.assertEqual(BOMLine.objects.get().quantity, Decimal('5'))

    def test_pay_reversal_expense_cancel_and_refund_keep_history(self):
        project = self.active_project()
        expense_id = self.post(
            'finance',
            'entries/expense/',
            {'project': project.pk, 'title': '安装交通费', 'amount': '100', 'due_date': TODAY},
            status=201,
        )['id']
        payment_id = self.post(
            'finance', f'entries/{expense_id}/pay/', {'amount': '100', 'date': TODAY, 'reason': '已付'}
        )['id']
        reverse_id = self.post('finance', f'payments/{payment_id}/reverse/', {'date': TODAY, 'reason': '付款录错'})[
            'id'
        ]
        history = self.clients['finance'].get('/api/business/payments/', {'entry': expense_id})
        self.assertEqual(history.status_code, 200)
        records = {row['id']: row for row in history.data['results']}
        self.assertEqual(records[payment_id]['reversed_by'], reverse_id)
        self.assertIsNone(records[reverse_id]['reversed_by'])
        self.assertEqual(records[reverse_id]['reversal_of'], payment_id)
        self.assertEqual(records[payment_id]['amount'], '100.00')
        self.post('finance', f'payments/{payment_id}/reverse/', {'date': TODAY, 'reason': '不能再冲'}, status=409)
        self.assertEqual(Payment.objects.count(), 2)
        self.post('finance', f'entries/{expense_id}/pay/', {'amount': '100', 'date': TODAY, 'reason': '重新登记'})
        self.post('finance', f'entries/{expense_id}/cancel-expense/', {'reason': '交通取消并退款'})
        self.post('finance', f'entries/{expense_id}/refund/', {'amount': '100', 'date': TODAY, 'reason': '退回银行'})
        self.assertEqual(
            self.clients['finance'].get(f'/api/business/projects/{project.pk}/cost/').data['expenses'], '0.00'
        )
        self.assertEqual(Payment.objects.count(), 4)

    def test_refund_must_be_reversed_before_original_payment(self):
        from apps.business.services.finance import balance, paid

        project = self.active_project()
        purchase = self.purchase(project)
        entry = Entry.objects.get(purchase=purchase)
        payment = self.post(
            'finance', f'entries/{entry.pk}/pay/', {'amount': '500', 'date': TODAY, 'reason': '预付款'}
        )['id']
        self.post('purchaser', f'purchases/{purchase.pk}/cancel-remainder/', {'reason': '订单取消'})
        refund = self.post(
            'finance', f'entries/{entry.pk}/refund/', {'amount': '500', 'date': TODAY, 'reason': '已退款'}
        )['id']
        count = ActionReceipt.objects.count()
        self.post('finance', f'payments/{payment}/reverse/', {'date': TODAY, 'reason': '顺序错误'}, status=409)
        self.assertEqual(ActionReceipt.objects.count(), count)
        self.assertEqual(Payment.objects.filter(entry=entry).count(), 2)
        entry.refresh_from_db()
        self.assertEqual((paid(entry), balance(entry)), (Decimal('0'), Decimal('0')))
        key = str(uuid.uuid4())
        for _ in range(2):
            self.post('finance', f'payments/{refund}/reverse/', {'date': TODAY, 'reason': '退款录错'}, key=key)
        self.assertEqual(Payment.objects.filter(entry=entry).count(), 3)
        self.assertEqual(balance(entry), Decimal('-500'))
        self.post('finance', f'payments/{payment}/reverse/', {'date': TODAY, 'reason': '付款录错'})
        self.assertEqual(Payment.objects.filter(entry=entry).count(), 4)
        self.assertEqual((paid(entry), balance(entry)), (Decimal('0'), Decimal('0')))
        self.assertEqual(Payment.objects.get(pk=payment).amount, Decimal('500'))
        self.assertEqual(Payment.objects.get(pk=refund).amount, Decimal('-500'))

    def test_missing_idempotency_key_rejected_before_any_write(self):
        response = self.clients['manager'].post('/api/business/projects/', {'name': '未提供标识'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Project.objects.exists())

    def test_duplicate_operation_with_changed_payload_conflicts(self):
        key = str(uuid.uuid4())
        self.post('purchaser', 'items/', {'name': '原物料'}, key=key, status=201)
        self.post('purchaser', 'items/', {'name': '不同物料'}, key=key, status=409)
        self.assertEqual(Item.objects.count(), 2)

    def test_non_object_json_returns_validation_error_without_writes(self):
        for url in ('projects/', 'purchases/', 'stocks/issue/', 'entries/expense/'):
            for body in ([], [1], 'not-an-object'):
                with self.subTest(url=url, body=body):
                    response = self.clients['admin'].post(
                        '/api/business/' + url, body, format='json', HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4())
                    )
                    self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(Project.objects.exists())
        self.assertFalse(ActionReceipt.objects.exists())

    def test_successful_action_replay_rechecks_current_role(self):
        project = self.active_project()
        purchase = self.purchase(project, approve=False)
        key = str(uuid.uuid4())
        self.post('manager', f'purchases/{purchase.pk}/approve/', key=key)
        User.objects.filter(pk=self.users['manager'].pk).update(role='member')
        self.post('manager', f'purchases/{purchase.pk}/approve/', key=key, status=403)
        self.assertEqual(Entry.objects.filter(purchase=purchase).count(), 1)
