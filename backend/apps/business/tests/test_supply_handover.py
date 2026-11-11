"""采购、库存、收付款与工作台之间的交接：超 BOM 采购、按 BOM 批量领料、正向动作说明选填、单据追溯与交接待办。"""

import uuid
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.business.models import (
    BankMatch,
    BankRecord,
    BOMLine,
    Document,
    Entry,
    Item,
    Payment,
    PaymentEvidence,
    PurchaseContractVersion,
    PurchaseLine,
    PurchaseOrder,
    Reconciliation,
    Stock,
    StockMove,
    Task,
)
from apps.core.models import ActionReceipt, AuditLog, Company

from .test_commercial_chain import TODAY, BusinessFixtures
from .test_permission_queries import counted_queries


class SupplyFixtures(BusinessFixtures):
    def setUp(self):
        self.setup_business()
        self.project = self.active_project()

    def get(self, role, url, params=None, status=200):
        response = self.clients[role].get('/api/business/' + url, params or {})
        self.assertEqual(response.status_code, status, getattr(response, 'data', None))
        return response.data

    def manual_purchase(self, qty, *, item=None, status=201, **extra):
        return self.post(
            'purchaser',
            'purchases/',
            {
                'project': self.project.pk,
                'supplier': self.supplier.pk,
                'due_date': TODAY,
                'lines': [{'item': (item or self.item).pk, 'quantity': qty, 'unit_price': '10'}],
                **extra,
            },
            status=status,
        )

    def approve(self, purchase_id):
        self.post('purchaser', f'purchases/{purchase_id}/submit/')
        self.post('manager', f'purchases/{purchase_id}/approve/')

    def receive_all(self, purchase_id):
        purchase = PurchaseOrder.objects.get(pk=purchase_id)
        lines = [{'line': line.pk, 'quantity': str(line.quantity)} for line in purchase.lines.all()]
        return self.post('warehouse', f'purchases/{purchase_id}/receive/', {'lines': lines})

    def opening(self, item, quantity, location='主仓'):
        self.post(
            'admin',
            'stocks/opening/',
            {'item': item.pk, 'location': location, 'quantity': quantity, 'unit_cost': '2', 'reason': '期初'},
        )
        return Stock.objects.get(item=item, location=location)


class OverBomPurchaseTests(SupplyFixtures, TestCase):
    def test_reordering_issued_material_requires_reason_and_is_flagged_for_approval(self):
        BOMLine.objects.create(project=self.project, item=self.item, quantity=6)
        first = self.manual_purchase('6')
        self.approve(first['id'])
        self.receive_all(first['id'])
        stock = Stock.objects.get(item=self.item)
        self.post('warehouse', 'stocks/issue/', {'project': self.project.pk, 'stock': stock.pk, 'quantity': '6'})
        before = PurchaseOrder.objects.count()
        key = str(uuid.uuid4())
        response = self.clients['purchaser'].post(
            '/api/business/purchases/',
            {
                'project': self.project.pk,
                'supplier': self.supplier.pk,
                'due_date': TODAY,
                'lines': [{'item': self.item.pk, 'quantity': '6', 'unit_price': '10'}],
            },
            format='json',
            HTTP_IDEMPOTENCY_KEY=key,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('BOM 需求 6.000、已领 6.000', str(response.data['over_bom_reason']))
        self.assertIn('还可采购 0', str(response.data['over_bom_reason']))
        # 拒绝时整单回滚，也不留幂等回执。
        self.assertEqual(PurchaseOrder.objects.count(), before)
        self.assertFalse(ActionReceipt.objects.filter(key=key).exists())

        created = self.manual_purchase('6', over_bom_reason='现场损耗补买')
        log = AuditLog.objects.get(operation='purchase.create', resource=f'purchaseorder:{created["id"]}')
        self.assertEqual(log.detail['over_bom_reason'], '现场损耗补买')
        self.assertEqual(log.detail['over_bom'][0]['excess'], '6.000')
        self.post('purchaser', f'purchases/{created["id"]}/submit/')
        check = self.get('manager', f'purchases/{created["id"]}/budget-check/')
        self.assertEqual(check['bom_warnings'], ['本单含 1 行超出 BOM 需求：伺服电机 +6.000'])
        self.assertEqual(check['over_bom_reason'], '现场损耗补买')
        line = PurchaseOrder.objects.get(pk=created['id']).lines.get()
        self.assertIn('超出 BOM 缺口 +6.000', check['bom_lines'][str(line.pk)])
        # 采购经理只拿到材料摘要，但同样看得到 BOM 复核。
        self.assertEqual(
            self.get('purchase_manager', f'purchases/{created["id"]}/budget-check/')['bom_warnings'],
            check['bom_warnings'],
        )
        self.post('manager', f'purchases/{created["id"]}/approve/')
        approval = AuditLog.objects.get(operation='purchase.approve', resource=f'purchaseorder:{created["id"]}')
        self.assertEqual(approval.detail['bom_check']['bom_warnings'], check['bom_warnings'])

    def test_received_but_not_issued_goods_count_as_covered(self):
        BOMLine.objects.create(project=self.project, item=self.item, quantity=6)
        first = self.manual_purchase('6')
        self.approve(first['id'])
        self.receive_all(first['id'])
        response = self.manual_purchase('1', status=400)
        self.assertIn('本项目已到货 6.000', str(response['over_bom_reason']))

    def test_within_shortage_and_shared_stock_need_no_reason(self):
        BOMLine.objects.create(project=self.project, item=self.item, quantity=6)
        # 共享库存不按项目预留，不能把别的库存当成本项目已备齐。
        self.opening(self.item, '20')
        self.manual_purchase('4')
        self.manual_purchase('2')
        self.manual_purchase('1', status=400)

    def test_items_outside_bom_are_only_flagged_to_approver(self):
        spare = Item.objects.create(code='SP-1', name='备用接头')
        created = self.manual_purchase('3', item=spare)
        self.post('purchaser', f'purchases/{created["id"]}/submit/')
        check = self.get('manager', f'purchases/{created["id"]}/budget-check/')
        self.assertEqual(check['bom_warnings'], ['本单含 1 行物料不在本项目 BOM：备用接头'])
        self.assertEqual(check['over_bom_reason'], '')

    def test_editing_draft_above_shortage_requires_reason(self):
        BOMLine.objects.create(project=self.project, item=self.item, quantity=5)
        created = self.manual_purchase('5')
        purchase = PurchaseOrder.objects.get(pk=created['id'])
        line = purchase.lines.get()

        def edit(quantity, status=200, **extra):
            purchase.refresh_from_db()
            return self.post(
                'purchaser',
                f'purchases/{purchase.pk}/edit/',
                {
                    'expected_updated_at': purchase.updated_at.isoformat(),
                    'reason': '调整数量',
                    'due_date': TODAY,
                    'lines': [{'id': line.pk, 'quantity': quantity, 'unit_price': '10', 'due_date': TODAY}],
                    **extra,
                },
                status=status,
            )

        # 本行自身的在途不重复计算：保持 5 不需要原因。
        edit('5')
        self.assertIn('over_bom_reason', edit('7', status=400))
        line.refresh_from_db()
        self.assertEqual(line.quantity, Decimal('5'))
        edit('7', over_bom_reason='多备两件易损件')
        log = AuditLog.objects.filter(operation='purchase.edit').order_by('-id').first()
        self.assertEqual(log.detail['over_bom'][0]['excess'], '2.000')


class BomIssueTests(SupplyFixtures, TestCase):
    def setUp(self):
        super().setUp()
        self.other = Item.objects.create(code='I2', name='气缸')
        self.missing = Item.objects.create(code='I3', name='导轨')
        BOMLine.objects.create(project=self.project, item=self.item, quantity=3, assembly_unit='上料')
        BOMLine.objects.create(project=self.project, item=self.item, quantity=2, assembly_unit='检测')
        BOMLine.objects.create(project=self.project, item=self.other, quantity=1)
        BOMLine.objects.create(project=self.project, item=self.missing, quantity=1)
        self.main = self.opening(self.item, '3')
        self.second = self.opening(self.item, '4', location='二号仓')
        self.cylinder = self.opening(self.other, '5')

    def test_candidates_fill_bom_remaining_across_locations(self):
        data = self.get('warehouse', 'stocks/bom-issue/', {'project': self.project.pk})
        rows = {(row['item_code'], row['location']): row for row in data['lines']}
        self.assertEqual(rows[('I1', '主仓')]['quantity'], '3.000')
        self.assertEqual(rows[('I1', '二号仓')]['quantity'], '2.000')
        self.assertEqual(rows[('I1', '主仓')]['bom_remaining'], '5.000')
        self.assertEqual(rows[('I1', '主仓')]['assembly_units'], '上料、检测')
        self.assertEqual(rows[('I2', '主仓')]['quantity'], '1.000')
        self.assertEqual((data['pending_items'], data['missing_items']), (3, 1))
        for role in ('purchaser', 'member', 'finance'):
            self.get(role, 'stocks/bom-issue/', {'project': self.project.pk}, status=403)

    def test_batch_issue_is_one_idempotent_transaction(self):
        payload = {
            'project': self.project.pk,
            'lines': [
                {'stock': self.main.pk, 'quantity': '3'},
                {'stock': self.second.pk, 'quantity': '2', 'remark': '二号仓补齐'},
                {'stock': self.cylinder.pk, 'quantity': '1'},
            ],
        }
        key = str(uuid.uuid4())
        result = self.post('warehouse', 'stocks/bom-issue/', payload, key=key)
        self.assertEqual(result['count'], 3)
        self.assertEqual(self.post('warehouse', 'stocks/bom-issue/', payload, key=key), result)
        moves = StockMove.objects.filter(kind='issue', project=self.project)
        self.assertEqual(moves.count(), 3)
        self.assertEqual(set(moves.values_list('reason', flat=True)), {'项目领料'})
        self.assertEqual(moves.get(stock=self.second).remark, '二号仓补齐')
        self.second.refresh_from_db()
        self.assertEqual(self.second.quantity, Decimal('2'))
        self.assertEqual(AuditLog.objects.filter(operation='stock.issue').count(), 3)
        # 全部领完后不再列出候选。
        self.assertEqual(self.get('warehouse', 'stocks/bom-issue/', {'project': self.project.pk})['lines'], [])

    def test_batch_issue_rejects_and_rolls_back(self):
        over = {
            'project': self.project.pk,
            'lines': [
                {'stock': self.cylinder.pk, 'quantity': '1'},
                {'stock': self.main.pk, 'quantity': '3'},
                {'stock': self.second.pk, 'quantity': '3'},
            ],
        }
        response = self.post('warehouse', 'stocks/bom-issue/', over, status=409)
        self.assertIn('伺服电机', str(response))
        duplicate = {'project': self.project.pk, 'lines': [{'stock': self.main.pk, 'quantity': '1'}] * 2}
        self.post('warehouse', 'stocks/bom-issue/', duplicate, status=400)
        self.post(
            'warehouse',
            'stocks/bom-issue/',
            {'project': self.project.pk, 'lines': [{'stock': self.main.pk, 'quantity': '0'}]},
            status=400,
        )
        self.post(
            'purchaser',
            'stocks/bom-issue/',
            {'project': self.project.pk, 'lines': [{'stock': self.main.pk, 'quantity': '1'}]},
            status=403,
        )
        self.assertFalse(StockMove.objects.filter(kind='issue').exists())
        self.main.refresh_from_db()
        self.cylinder.refresh_from_db()
        self.assertEqual((self.main.quantity, self.cylinder.quantity), (Decimal('3'), Decimal('5')))
        self.project.status = 'warranty'
        self.project.save()
        self.post(
            'warehouse',
            'stocks/bom-issue/',
            {'project': self.project.pk, 'lines': [{'stock': self.main.pk, 'quantity': '1'}]},
            status=409,
        )


class OptionalForwardReasonTests(SupplyFixtures, TestCase):
    def test_forward_actions_default_reason_and_corrections_still_require_it(self):
        BOMLine.objects.create(project=self.project, item=self.item, quantity=5)
        created = self.manual_purchase('5')
        self.approve(created['id'])
        self.receive_all(created['id'])
        receipt = StockMove.objects.get(kind='receipt')
        self.assertEqual(receipt.reason, '采购收货')
        AuditLog.objects.get(operation='purchase.receive')
        stock = Stock.objects.get(item=self.item)
        issued = self.post(
            'warehouse', 'stocks/issue/', {'project': self.project.pk, 'stock': stock.pk, 'quantity': '2'}
        )
        self.assertEqual(StockMove.objects.get(pk=issued['id']).reason, '项目领料')
        self.post('warehouse', f'moves/{issued["id"]}/return-material/', {'quantity': '1'}, status=400)
        self.post('warehouse', f'moves/{issued["id"]}/return-material/', {'quantity': '1', 'reason': ''}, status=400)
        self.post('warehouse', f'moves/{receipt.pk}/return-purchase/', {'quantity': '1'}, status=400)
        entry = Entry.objects.get(project=self.project, kind='receivable')
        paid = self.post('finance', f'entries/{entry.pk}/pay/', {'amount': '100', 'date': TODAY})
        payment = Payment.objects.get(pk=paid['id'])
        self.assertEqual(payment.reason, '登记收款')
        self.post('finance', f'payments/{payment.pk}/reverse/', {'date': TODAY}, status=400)

    def test_purchase_confirmations_default_reason(self):
        created = self.manual_purchase('5')
        self.approve(created['id'])
        self.assertEqual(AuditLog.objects.get(operation='purchase.approve').detail['reason'], '批准采购')
        purchase = PurchaseOrder.objects.get(pk=created['id'])
        self.post(
            'purchaser',
            f'purchases/{purchase.pk}/delivery-plan/',
            {
                'expected_updated_at': purchase.updated_at.isoformat(),
                'lines': [{'id': purchase.lines.get().pk, 'due_date': TODAY}],
            },
        )
        self.assertEqual(AuditLog.objects.get(operation='purchase.delivery_plan').detail['reason'], '更新到货计划')
        self.post(
            'admin',
            'stocks/opening/',
            {'item': self.item.pk, 'location': '期初仓', 'quantity': '3', 'unit_cost': '2'},
        )
        self.assertEqual(StockMove.objects.get(kind='opening').reason, '期初库存')

        Company.objects.create(pk=1, name='采购方', address='采购方地址', phone='123')
        self.supplier.address, self.supplier.phone = '供应商地址', '456'
        self.supplier.save()
        url = f'/api/business/purchases/{purchase.pk}/contract-preview/'
        snapshot = self.clients['purchaser'].get(url).data['snapshot_hash']
        signed = Document.objects.create(
            purchase=purchase, category='contract', original_name='签署合同.pdf', file='fixture', size=1
        )
        self.post(
            'purchaser',
            f'purchases/{purchase.pk}/archive-contract/',
            {
                'expected_snapshot': snapshot,
                'document': signed.pk,
                'delivery_address': '现场',
                'confirmed': True,
            },
            status=201,
        )
        self.assertEqual(PurchaseContractVersion.objects.get().reason, '归档采购合同')

    def test_finance_confirmations_default_reason_and_corrections_still_require_it(self):
        entry = Entry.objects.get(project=self.project, kind='receivable')

        def bank(**extra):
            data = {
                'amount': '500',
                'date': TODAY,
                'account': 'BANK-A',
                'reference': str(uuid.uuid4()),
                'counterparty': '客户银行户名',
            }
            return self.post('finance', 'bank-records/', {**data, **extra}, status=201)['id']

        claimed = bank()
        self.assertEqual(BankRecord.objects.get(pk=claimed).reason, '登记银行流水')
        self.post('finance', f'bank-records/{claimed}/allocate/', {'entry': entry.pk, 'amount': '200'})
        self.assertEqual(BankMatch.objects.get(bank_id=claimed).reason, '认领银行流水')
        self.assertEqual(Payment.objects.get().reason, '认领银行流水')

        matched = BankRecord.objects.get(pk=bank())
        paid = self.post(
            'finance',
            f'entries/{entry.pk}/pay/',
            {'amount': '500', 'date': TODAY, 'method': 'bank', 'account': 'BANK-A', 'reference': matched.reference},
        )['id']
        match = self.post('finance', f'bank-records/{matched.pk}/match/', {'payment': paid})['id']
        self.assertEqual(BankMatch.objects.get(pk=match).reason, '匹配银行流水')
        self.post('finance', f'bank-records/{matched.pk}/unmatch/', {'match': match}, status=400)
        self.post('finance', f'bank-records/{bank()}/void/', {}, status=400)

        pending = BankRecord.objects.create(
            amount=100,
            date=TODAY,
            account='BANK-A',
            reference='REVIEW-1',
            counterparty='原流水未提供户名（待核实）',
            needs_review=True,
            reason='导入',
        )
        self.post('finance', f'bank-records/{pending.pk}/review/', {'counterparty': '核实客户'})
        self.assertEqual(AuditLog.objects.get(operation='bank.review').detail['reason'], '核实户名')

        doc = Document.objects.create(
            project=self.project, category='receipt', original_name='回单.pdf', file='isolated/r.pdf', size=1
        )
        self.post('finance', f'payments/{paid}/attach-evidence/', {'document': doc.pk})
        self.assertEqual(PaymentEvidence.objects.get().reason, '补充收付凭证')

    def test_reconciliation_confirmations_default_reason_but_void_and_self_approval_require_it(self):
        purchase = self.purchase(self.project)
        entry = purchase.entry
        data = {
            'entry': entry.pk,
            'kind': 'prepayment',
            'counterparty_balance': '500.00',
            'approved_amount': '500.00',
            'basis': '合同约定预付',
        }
        statement = self.post('admin', 'reconciliations/', data, status=201)['id']
        self.assertEqual(Reconciliation.objects.get(pk=statement).reason, '发起对账')
        # 前端据此提前提示“本对账单由你生成”；判定仍由服务端的申请人分离完成。
        self.assertEqual(self.get('manager', f'reconciliations/{statement}/')['created_by'], self.users['admin'].pk)
        self.post('admin', f'reconciliations/{statement}/confirm/', {}, status=400)
        self.post('manager', f'reconciliations/{statement}/confirm/', {})
        self.assertEqual(AuditLog.objects.get(operation='reconciliation.confirm').detail['reason'], '确认对账')
        self.post('finance', f'reconciliations/{statement}/void/', {}, status=400)

        received = self.purchase(self.active_project())
        self.post(
            'warehouse',
            f'purchases/{received.pk}/receive/',
            {'lines': [{'line': received.lines.get().pk, 'quantity': '2'}]},
        )
        path = 'reconciliations/supplier-monthly/'
        month = str(timezone.localdate())[:7]
        report = self.get('finance', path, {'supplier': self.supplier.pk, 'month': month})
        result = self.post(
            'finance',
            path,
            {
                'supplier': self.supplier.pk,
                'month': report['month'],
                'expected_snapshot': report['snapshot_hash'],
                'counterparty_balance': report['totals']['closing'],
            },
        )
        monthly = Reconciliation.objects.filter(pk__in=result['reconciliations'])
        self.assertTrue(monthly)
        self.assertEqual({row.reason for row in monthly}, {'月结确认'})


class TraceabilityTests(SupplyFixtures, TestCase):
    def test_moves_and_payments_show_project_source_and_direction(self):
        BOMLine.objects.create(project=self.project, item=self.item, quantity=5)
        created = self.manual_purchase('5')
        self.approve(created['id'])
        self.receive_all(created['id'])
        stock = Stock.objects.get(item=self.item)
        self.post('warehouse', 'stocks/issue/', {'project': self.project.pk, 'stock': stock.pk, 'quantity': '2'})
        moves = {row['kind']: row for row in self.get('warehouse', 'moves/', {'project': self.project.pk})['results']}
        purchase = PurchaseOrder.objects.get(pk=created['id'])
        self.assertEqual(moves['receipt']['purchase_code'], purchase.code)
        self.assertEqual(moves['receipt']['purchase'], purchase.pk)
        self.assertEqual(moves['issue']['project_code'], self.project.code)
        self.assertEqual(moves['issue']['project_name'], self.project.name)
        self.assertEqual(moves['issue']['item_code'], 'I1')
        self.assertEqual(moves['issue']['created_by_name'], 'warehouse')
        self.assertIsNone(moves['issue']['purchase'])
        entry = Entry.objects.get(project=self.project, kind='receivable')
        self.post('finance', f'entries/{entry.pk}/pay/', {'amount': '100', 'date': TODAY, 'reason': '首付款'})
        payable = Entry.objects.get(purchase=purchase)
        self.post(
            'finance',
            f'entries/{payable.pk}/pay/',
            {'amount': '10', 'date': TODAY, **self.reconciliation_data(payable)},
        )
        payments = {
            row['kind']: row for row in self.get('finance', 'payments/', {'entry__project': self.project.pk})['results']
        }
        self.assertEqual(payments['receivable']['partner_name'], self.customer.name)
        self.assertEqual(payments['receivable']['project_code'], self.project.code)
        self.assertEqual(payments['payable']['partner_name'], self.supplier.name)
        self.assertEqual(payments['payable']['purchase'], purchase.pk)
        self.assertTrue(payments['payable']['reconciliation_code'])
        self.assertEqual(Decimal(payments['payable']['cash_amount']), Decimal('-10'))


class ReceivableDueDateTests(SupplyFixtures, TestCase):
    def test_finance_adjusts_receivable_due_date_with_audit(self):
        entry = Entry.objects.get(project=self.project, kind='receivable')
        url = f'entries/{entry.pk}/adjust-due-date/'
        later = (timezone.localdate() + timedelta(days=30)).isoformat()
        payload = {
            'due_date': later,
            'expected_due_date': entry.due_date.isoformat(),
            'reason': '合同约定发货后30天付款',
        }
        self.post('manager', url, payload, status=403)
        self.post('finance', url, {**payload, 'reason': ''}, status=400)
        self.post('finance', url, {**payload, 'expected_due_date': later}, status=409)
        self.assertEqual(
            self.get('finance', f'entries/{entry.pk}/')['status'],
            'open' if entry.due_date >= timezone.localdate() else 'overdue',
        )
        key = str(uuid.uuid4())
        self.post('finance', url, payload, key=key)
        self.post('finance', url, payload, key=key)
        entry.refresh_from_db()
        self.assertEqual(entry.due_date.isoformat(), later)
        self.assertEqual(entry.amount, Decimal('10000.00'))
        log = AuditLog.objects.get(operation='entry.due_date')
        self.assertEqual((log.detail['after'], log.detail['reason']), (later, '合同约定发货后30天付款'))
        self.post('finance', url, {**payload, 'expected_due_date': later}, status=400)

    def test_only_open_receivables_can_be_adjusted(self):
        purchase = self.purchase(self.project)
        payable = Entry.objects.get(purchase=purchase)
        tomorrow = (timezone.localdate() + timedelta(days=1)).isoformat()
        payload = {'due_date': tomorrow, 'expected_due_date': payable.due_date.isoformat(), 'reason': '调整'}
        self.post('finance', f'entries/{payable.pk}/adjust-due-date/', payload, status=409)
        entry = Entry.objects.get(project=self.project, kind='receivable')
        Payment.objects.create(entry=entry, amount=entry.amount, date=TODAY, reason='全部收齐')
        payload['expected_due_date'] = entry.due_date.isoformat()
        self.post('finance', f'entries/{entry.pk}/adjust-due-date/', payload, status=409)

    def test_entries_list_unsettled_first_by_due_date(self):
        base = timezone.localdate()
        late = Entry.objects.create(
            project=self.project, kind='receivable', title='验收款', amount=10, due_date=base + timedelta(days=60)
        )
        early = Entry.objects.create(
            project=self.project, kind='receivable', title='预付款', amount=10, due_date=base - timedelta(days=5)
        )
        settled = Entry.objects.create(
            project=self.project, kind='receivable', title='已收', amount=10, due_date=base - timedelta(days=90)
        )
        Payment.objects.create(entry=settled, amount=10, date=TODAY, reason='收齐')
        ids = [row['id'] for row in self.get('finance', 'entries/', {'project': self.project.pk})['results']]
        self.assertLess(ids.index(early.pk), ids.index(late.pk))
        self.assertEqual(ids[-1], settled.pk)


class HandoverWorkbenchTests(SupplyFixtures, TestCase):
    def workbench(self, role):
        return self.get(role, 'workbench/')

    def test_new_project_is_listed_for_its_manager_until_planned(self):
        rows = self.workbench('manager')['handover_projects']['results']
        self.assertEqual([row['project'] for row in rows], [self.project.pk])
        self.assertEqual(rows[0]['missing'], ['任务计划', 'BOM', '预算'])
        self.assertNotIn('handover_projects', self.workbench('purchaser'))
        BOMLine.objects.create(project=self.project, item=self.item, quantity=1)
        Task.objects.create(project=self.project, assignee=self.users['member'], kind='design', title='方案设计')
        self.assertEqual(self.workbench('manager')['handover_projects']['count'], 0)

    def test_supervised_overdue_tasks_count_once_in_overdue_total(self):
        yesterday = timezone.localdate() - timedelta(days=1)
        Task.objects.create(
            project=self.project, assignee=self.users['member'], kind='design', title='逾期', due_date=yesterday
        )
        Task.objects.create(
            project=self.project, assignee=self.users['manager'], kind='design', title='本人逾期', due_date=yesterday
        )
        result = self.workbench('manager')
        self.assertEqual(result['tasks']['overdue_count'], 1)
        self.assertEqual(result['supervised_tasks']['overdue_count'], 2)
        self.assertEqual(result['tasks']['overdue_total'], 2)

    def test_buyer_sees_approved_orders_and_projects_with_shortage(self):
        BOMLine.objects.create(project=self.project, item=self.item, quantity=5, required_date=TODAY)
        result = self.workbench('purchaser')
        self.assertEqual([row['project'] for row in result['shortage_projects']['results']], [self.project.pk])
        self.assertEqual(result['shortage_projects']['results'][0]['shortage_lines'], 1)
        self.assertEqual(result['approved_purchases']['count'], 0)
        created = self.manual_purchase('5')
        # 未关联 BOM 行的草稿采购与 BOM 选料下单同一口径计入在途，不再误报缺料。
        self.assertEqual(self.workbench('purchaser')['shortage_projects']['count'], 0)
        self.approve(created['id'])
        result = self.workbench('purchaser')
        self.assertEqual(result['shortage_projects']['count'], 0)
        self.assertEqual([row['id'] for row in result['approved_purchases']['results']], [created['id']])
        # 只列本人创建的，别人看不到。
        self.assertEqual(self.workbench('purchase_manager')['approved_purchases']['count'], 0)
        self.receive_all(created['id'])
        self.assertEqual(self.workbench('purchaser')['approved_purchases']['count'], 0)

    def test_sales_manager_sees_own_overdue_receivables_and_quotes(self):
        sale = self.project.sale
        sale.manager = self.users['sales_manager']
        sale.save()
        entry = Entry.objects.get(project=self.project, kind='receivable')
        entry.due_date = timezone.localdate() - timedelta(days=6)
        entry.save()
        quoted = self.post(
            'sales_manager',
            'sales/',
            {'name': '报价中', 'customer': self.customer.pk, 'manager': self.users['sales_manager'].pk},
            status=201,
        )
        self.post('sales_manager', f'sales/{quoted["id"]}/quote/', {'amount': '500', 'reason': '报价'})
        result = self.workbench('sales_manager')
        self.assertEqual([row['id'] for row in result['sale_receivables']['results']], [entry.pk])
        self.assertEqual(result['sale_receivables']['results'][0]['sale_code'], sale.code)
        self.assertEqual([row['id'] for row in result['quoted_sales']['results']], [quoted['id']])
        Payment.objects.create(entry=entry, amount=entry.amount, date=TODAY, reason='收齐')
        self.assertEqual(self.workbench('sales_manager')['sale_receivables']['count'], 0)
        sale.manager = self.users['manager']
        sale.save()
        self.assertNotIn(
            entry.pk, [row['id'] for row in self.workbench('sales_manager')['sale_receivables']['results']]
        )


class PurchaseLineLockTests(SupplyFixtures, TestCase):
    """到货计划与隔离品退回按主键顺序一次锁住本单明细，不再逐行查询；明细不属于本单仍返回 404。"""

    WRITES = ('apps.business.services.supply.save', 'apps.business.services.supply.audit')

    def order(self, size):
        items = Item.objects.bulk_create([Item(code=f'QL{size}-{i}', name=f'到货件{i}') for i in range(size)])
        purchase = PurchaseOrder.objects.create(
            code=f'QL{size}', project=self.project, supplier=self.supplier, due_date=TODAY, status='partial'
        )
        PurchaseLine.objects.bulk_create(
            [PurchaseLine(purchase=purchase, item=item, quantity=5, unit_price=1, pending_quantity=2) for item in items]
        )
        return purchase

    def test_delivery_plan_and_quality_return_lock_lines_once(self):
        def scenario(size):
            purchase = self.order(size)
            lines = list(purchase.lines.order_by('-pk'))
            plan = {
                'expected_updated_at': purchase.updated_at.isoformat(),
                'lines': [{'id': line.pk, 'due_date': '2026-10-01'} for line in lines],
            }
            sql = []
            planned, _ = counted_queries(
                lambda: self.post('purchaser', f'purchases/{purchase.pk}/delivery-plan/', plan), *self.WRITES, sql=sql
            )
            locks = [statement for statement in sql if 'FOR UPDATE' in statement and 'lean_purchase_line' in statement]
            self.assertEqual(len(locks), 1)
            self.assertIn('ORDER BY "lean_purchase_line"."id" ASC', locks[0])
            self.assertEqual(
                {str(day) for day in PurchaseLine.objects.filter(purchase=purchase).values_list('due_date', flat=True)},
                {'2026-10-01'},
            )
            back = {'reason': '不合格', 'lines': [{'line': line.pk, 'quantity': '1'} for line in lines]}
            returned, _ = counted_queries(
                lambda: self.post('warehouse', f'purchases/{purchase.pk}/quality-return/', back), *self.WRITES
            )
            self.assertEqual(
                set(PurchaseLine.objects.filter(purchase=purchase).values_list('pending_quantity', flat=True)),
                {Decimal('1')},
            )
            purchase.refresh_from_db()
            self.assertEqual(purchase.status, 'partial')
            return planned, returned

        small, large = scenario(3), scenario(30)
        self.assertEqual(small, large, f'3/30 行查询数: {small} / {large}')
        purchase = self.order(1)
        stranger = PurchaseLine.objects.exclude(purchase=purchase).first()
        missing = {'reason': '不合格', 'lines': [{'line': stranger.pk, 'quantity': '1'}]}
        self.post('warehouse', f'purchases/{purchase.pk}/quality-return/', missing, status=404)
        plan = {
            'expected_updated_at': purchase.updated_at.isoformat(),
            'lines': [{'id': stranger.pk, 'due_date': TODAY}],
        }
        self.post('purchaser', f'purchases/{purchase.pk}/delivery-plan/', plan, status=404)
