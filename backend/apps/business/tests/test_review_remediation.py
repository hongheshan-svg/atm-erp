import uuid
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from apps.business.models import (
    BOMLine,
    ContractAmendment,
    Document,
    Entry,
    Item,
    Payment,
    PurchaseOrder,
    Stock,
    StockMove,
)
from apps.business.services import bom, bom_import, finance
from apps.core.models import ActionReceipt

from .test_commercial_chain import TODAY, BusinessFixtures


class ReviewRemediationTests(BusinessFixtures, TestCase):
    def setUp(self):
        self.setup_business()
        self.project = self.active_project()

    def test_multi_unit_import_selection_and_shared_stock_once(self):
        raw = f'物料编码,数量,变更说明,单元\n{self.item.code},2,初版,上料\n{self.item.code},3,初版,下料\n'.encode()
        preview = bom_import.preview(self.project, SimpleUploadedFile('bom.csv', raw))
        self.assertTrue(preview['can_import'], preview)
        self.post(
            'manager',
            f'projects/{self.project.pk}/revise-bom/',
            {
                'expected_revision': preview['expected_revision'],
                'lines': [
                    {k: row[k] for k in ('item', 'quantity', 'change_note', 'assembly_unit')}
                    for row in preview['lines']
                ],
            },
        )
        self.assertEqual(BOMLine.objects.count(), 2)
        self.post(
            'admin',
            'stocks/opening/',
            {'item': self.item.pk, 'quantity': '1', 'unit_cost': '10', 'location': '主仓', 'reason': '期初'},
        )
        demand = bom.demand(self.project)
        self.assertEqual(sum(Decimal(row['available']) for row in demand), 1)
        self.assertEqual(sum(Decimal(row['shortage']) for row in demand), 4)
        result = self.post(
            'purchaser',
            'purchases/',
            {
                'project': self.project.pk,
                'supplier': self.supplier.pk,
                'due_date': TODAY,
                'from_demand': True,
                'lines': [
                    {'item': row['item'], 'bom_line': row['bom_line'], 'quantity': row['shortage'], 'unit_price': '10'}
                    for row in demand
                ],
            },
            status=201,
        )
        self.assertEqual(PurchaseOrder.objects.get(pk=result['id']).lines.count(), 2)
        self.assertEqual(sum(Decimal(row['shortage']) for row in bom.demand(self.project)), 0)
        old = bom_import.preview(
            self.project, SimpleUploadedFile('bom.csv', f'物料编码,数量,变更说明\n{self.item.code},5,调整\n'.encode())
        )
        self.assertFalse(old['can_import'])
        stock = Stock.objects.get()
        self.post(
            'warehouse',
            'stocks/issue/',
            {'project': self.project.pk, 'stock': stock.pk, 'quantity': '1', 'reason': '领料'},
        )
        self.post(
            'manager',
            f'projects/{self.project.pk}/revise-bom/',
            {
                'expected_revision': self.bom_version(self.project.pk),
                'lines': [{'item': self.item.pk, 'quantity': '1', 'assembly_unit': '下料', 'change_note': '减少'}],
            },
            status=409,
        )

    def test_quality_quarantine_accept_return_and_no_double_receipt(self):
        purchase = self.purchase(self.project, qty='5')
        line = purchase.lines.get()
        url = f'purchases/{purchase.pk}/'
        payload = {
            'location': '主仓',
            'reason': '尺寸待复检',
            'lines': [{'line': line.pk, 'quantity': '2', 'pending_quantity': '3'}],
        }
        key = str(uuid.uuid4())
        self.post('warehouse', url + 'receive/', payload, key=key)
        self.post('warehouse', url + 'receive/', payload, key=key)
        self.assertEqual(Stock.objects.get().quantity, 2)
        line.refresh_from_db()
        self.assertEqual(line.pending_quantity, 3)
        self.post('purchaser', url + 'cancel-remainder/', {'reason': '取消'}, status=409)
        self.post('warehouse', url + 'receive/', payload, status=409)
        accept = {'location': '主仓', 'reason': '复检合格', 'lines': [{'line': line.pk, 'quantity': '1'}]}
        self.post('purchaser', url + 'quality-accept/', accept, status=403)
        self.post('warehouse', url + 'quality-accept/', accept)
        self.post(
            'warehouse',
            url + 'quality-return/',
            {'reason': '尺寸不合退回换货', 'lines': [{'line': line.pk, 'quantity': '2'}]},
        )
        self.assertEqual(Stock.objects.get().quantity, 3)
        self.assertEqual(Entry.objects.get(purchase=purchase).credit_amount, 0)
        self.post('purchaser', url + 'cancel-remainder/', {'reason': '不再补货'})
        self.assertEqual(Entry.objects.get(purchase=purchase).credit_amount, 200)

    def test_reject_edit_stale_and_line_due_date(self):
        purchase = self.purchase(self.project, approve=False)
        url = f'purchases/{purchase.pk}/'
        self.post('purchaser', url + 'reject/', {'reason': '退回'}, status=403)
        self.post('manager', url + 'reject/', {'reason': '修改交期和单价'})
        purchase.refresh_from_db()
        line = purchase.lines.get()
        payload = {
            'expected_updated_at': purchase.updated_at.isoformat(),
            'reason': '供应商确认',
            'due_date': TODAY,
            'note': '',
            'lines': [{'id': line.pk, 'quantity': '3', 'unit_price': '80', 'due_date': '2026-09-01'}],
        }
        self.post('purchaser', url + 'edit/', payload)
        self.post('purchaser', url + 'edit/', payload, status=409)
        self.post('purchaser', url + 'submit/')
        self.post('manager', url + 'approve/')
        self.assertEqual(Entry.objects.get(purchase=purchase).amount, 240)
        response = self.clients['purchaser'].get('/api/business/workbench/')
        self.assertEqual(response.data['overdue_purchases']['count'], 1)

    def document(self, category):
        return Document.objects.create(
            project=self.project,
            category=category,
            original_name='agreement.pdf',
            size=1,
            sha256='a' * 64,
            file='test-evidence',
        )

    def test_payment_source_reference_and_document_scope(self):
        entry = Entry.objects.get(project=self.project, kind='receivable')
        doc = self.document('receipt')
        data = {
            'amount': '50',
            'date': TODAY,
            'reason': '银行到账',
            'method': 'bank',
            'account': '基本户尾号1234',
            'reference': 'BANK-001',
            'document': doc.pk,
        }
        key = str(uuid.uuid4())
        result = self.post('finance', f'entries/{entry.pk}/pay/', data, key=key)
        self.post('finance', f'entries/{entry.pk}/pay/', data, key=key)
        payment = Payment.objects.get(pk=result['id'])
        self.assertEqual(payment.document_id, doc.pk)
        self.assertEqual(payment.reference, 'BANK-001')
        self.assertEqual(Payment.objects.count(), 1)
        self.post('finance', f'entries/{entry.pk}/pay/', {**data, 'document': self.document('contract').pk}, status=404)
        self.post('finance', f'entries/{entry.pk}/pay/', {**data, 'method': 'unknown'}, status=400)
        self.assertEqual(self.clients['member'].get('/api/business/payments/').status_code, 403)

    def test_contract_amendments_keep_original_and_create_refund_balance(self):
        sale = self.project.sale
        doc = self.document('contract')
        entry = Entry.objects.get(project=self.project)
        self.post('finance', f'entries/{entry.pk}/pay/', {'amount': '10000', 'date': TODAY, 'reason': '全款'})
        data = {
            'expected_updated_at': sale.updated_at.isoformat(),
            'reason': '补充协议减额',
            'date': TODAY,
            'document': doc.pk,
            'amount': '9000',
            'equipment_quantity': 1,
            'warranty_months': 6,
            'credits': [{'entry': entry.pk, 'amount': '1000'}],
            'milestones': [],
        }
        key = str(uuid.uuid4())
        self.post('finance', f'sales/{sale.pk}/amend/', data, status=403)
        self.post('manager', f'sales/{sale.pk}/amend/', data, key=key)
        self.post('manager', f'sales/{sale.pk}/amend/', data, key=key)
        self.post('manager', f'sales/{sale.pk}/amend/', data, status=409)
        sale.refresh_from_db()
        entry.refresh_from_db()
        self.assertEqual((sale.original_contract_amount, sale.contract_amount), (10000, 9000))
        self.assertEqual(finance.balance(entry), -1000)
        self.assertEqual(ContractAmendment.objects.count(), 1)
        data.update(
            expected_updated_at=sale.updated_at.isoformat(),
            amount='9500',
            credits=[],
            milestones=[{'title': '补充协议款', 'amount': '500', 'due_date': TODAY}],
        )
        self.post('manager', f'sales/{sale.pk}/amend/', data)
        self.assertEqual(ContractAmendment.objects.count(), 2)
        self.assertEqual(Entry.objects.get(title='补充协议款').amount, 500)

    def test_bad_amendment_rolls_back_entries_and_receipt(self):
        sale = self.project.sale
        doc = self.document('contract')
        entry = Entry.objects.get(project=self.project)
        key = str(uuid.uuid4())
        data = {
            'expected_updated_at': sale.updated_at.isoformat(),
            'reason': '错误差额',
            'date': TODAY,
            'document': doc.pk,
            'amount': '9000',
            'equipment_quantity': 1,
            'warranty_months': 12,
            'credits': [{'entry': entry.pk, 'amount': '999'}],
        }
        self.post('manager', f'sales/{sale.pk}/amend/', data, key=key, status=400)
        entry.refresh_from_db()
        self.assertEqual(entry.credit_amount, 0)
        self.assertFalse(ActionReceipt.objects.filter(key=key).exists())
        self.assertFalse(ContractAmendment.objects.exists())

    def test_forecast_is_versioned_and_never_posts_cost(self):
        before = finance.cost(self.project)
        data = {
            'remaining_materials': '0',
            'remaining_labor': '500',
            'remaining_expenses': '100',
            'expected_revision': 0,
            'reason': '剩余安装估算',
        }
        self.post('finance', f'projects/{self.project.pk}/forecast/', data, status=403)
        self.post('manager', f'projects/{self.project.pk}/forecast/', data)
        self.post('manager', f'projects/{self.project.pk}/forecast/', data, status=409)
        self.assertEqual(finance.cost(self.project), before)
        report = self.clients['manager'].get(f'/api/business/projects/{self.project.pk}/cost-analysis/').data
        self.assertEqual(report['forecast_total'], '600.00')
        self.assertEqual(
            self.clients['member'].get(f'/api/business/projects/{self.project.pk}/bom-impact/').status_code, 403
        )

    def test_thousand_bom_lines_have_bounded_query_count(self):
        items = Item.objects.bulk_create([Item(code=f'SCALE{i}', name=f'物料{i}') for i in range(1000)])
        BOMLine.objects.bulk_create([BOMLine(project=self.project, item=item, quantity=1) for item in items])
        with CaptureQueriesContext(connection) as queries:
            result = bom.demand(self.project)
        self.assertEqual(len(result), 1000)
        # 固定条数与 BOM 行数无关；其中两条是「其他在执行项目还需多少」的汇总。
        self.assertLessEqual(len(queries), 6)

    def test_two_thousand_settlements_export_without_per_row_queries(self):
        Entry.objects.bulk_create(
            [
                Entry(project=self.project, kind='expense', title=f'规模费用{i}', amount=1, due_date=TODAY)
                for i in range(2000)
            ]
        )
        with CaptureQueriesContext(connection) as queries:
            response = self.clients['finance'].get('/api/business/entries/export/?file_format=csv')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.content.decode('utf-8-sig').splitlines()), 2002)
        self.assertLessEqual(len(queries), 8)

    def test_returning_all_quarantined_goods_restores_status(self):
        purchase = self.purchase(self.project, qty='5')
        line = purchase.lines.get()
        url = f'purchases/{purchase.pk}/'
        quarantine = {
            'location': '主仓',
            'reason': '外观待检',
            'lines': [{'line': line.pk, 'quantity': '0', 'pending_quantity': '5'}],
        }
        self.post('warehouse', url + 'receive/', quarantine)
        purchase.refresh_from_db()
        self.assertEqual(purchase.status, 'partial')
        back = {'reason': '外观不合格退回', 'lines': [{'line': line.pk, 'quantity': '2'}]}
        self.post('warehouse', url + 'quality-return/', back)
        purchase.refresh_from_db()
        self.assertEqual(purchase.status, 'partial')
        self.post('warehouse', url + 'quality-return/', {**back, 'lines': [{'line': line.pk, 'quantity': '3'}]})
        purchase.refresh_from_db()
        line.refresh_from_db()
        self.assertEqual((purchase.status, line.received_quantity, line.pending_quantity), ('approved', 0, 0))
        self.assertFalse(StockMove.objects.filter(purchase_line=line).exists())
        # 恢复待收货后与取消余量规则一致：没有合格收货的整单取消为已取消。
        self.post('purchaser', url + 'cancel-remainder/', {'reason': '供应商无法补货'})
        purchase.refresh_from_db()
        self.assertEqual(purchase.status, 'cancelled')
        self.assertEqual(Entry.objects.get(purchase=purchase).credit_amount, 500)

    def test_quality_return_keeps_partial_when_qualified_goods_were_received(self):
        purchase = self.purchase(self.project, qty='5')
        line = purchase.lines.get()
        url = f'purchases/{purchase.pk}/'
        self.post(
            'warehouse',
            url + 'receive/',
            {
                'location': '主仓',
                'reason': '部分待检',
                'lines': [{'line': line.pk, 'quantity': '2', 'pending_quantity': '3'}],
            },
        )
        self.post(
            'warehouse', url + 'quality-return/', {'reason': '不合格', 'lines': [{'line': line.pk, 'quantity': '3'}]}
        )
        purchase.refresh_from_db()
        self.assertEqual(purchase.status, 'partial')


class PartialReceiveTests(BusinessFixtures, TestCase):
    def setUp(self):
        self.setup_business()
        self.project = self.active_project()
        self.other = Item.objects.create(code='I2', name='气缸')

    def two_line_purchase(self):
        data = self.post(
            'purchaser',
            'purchases/',
            {
                'project': self.project.pk,
                'supplier': self.supplier.pk,
                'due_date': TODAY,
                'lines': [
                    {'item': self.item.pk, 'quantity': '5', 'unit_price': '100'},
                    {'item': self.other.pk, 'quantity': '3', 'unit_price': '50'},
                ],
            },
            status=201,
        )
        purchase = PurchaseOrder.objects.get(pk=data['id'])
        self.post('purchaser', f'purchases/{purchase.pk}/submit/')
        self.post('manager', f'purchases/{purchase.pk}/approve/')
        return purchase

    def receive(self, purchase, lines, status=200):
        return self.post(
            'warehouse',
            f'purchases/{purchase.pk}/receive/',
            {'location': '主仓', 'reason': '分次到货', 'lines': lines},
            status=status,
        )

    def assert_only_first_received(self, purchase, first, second):
        purchase.refresh_from_db()
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(purchase.status, 'partial')
        self.assertEqual((first.received_quantity, first.pending_quantity), (5, 0))
        self.assertEqual((second.received_quantity, second.pending_quantity), (0, 0))
        self.assertEqual(StockMove.objects.filter(kind='receipt').count(), 1)

    def test_zero_row_for_untouched_line_is_skipped(self):
        purchase = self.two_line_purchase()
        first, second = purchase.lines.order_by('pk')
        self.receive(
            purchase,
            [
                {'line': first.pk, 'quantity': '5', 'pending_quantity': '0'},
                {'line': second.pk, 'quantity': '0', 'pending_quantity': '0'},
            ],
        )
        self.assert_only_first_received(purchase, first, second)

    def test_omitted_line_is_skipped(self):
        purchase = self.two_line_purchase()
        first, second = purchase.lines.order_by('pk')
        self.receive(purchase, [{'line': first.pk, 'quantity': '5'}])
        self.assert_only_first_received(purchase, first, second)

    def test_all_zero_rows_are_rejected_without_movements(self):
        purchase = self.two_line_purchase()
        first, second = purchase.lines.order_by('pk')
        result = self.receive(
            purchase,
            [
                {'line': first.pk, 'quantity': '0', 'pending_quantity': '0'},
                {'line': second.pk, 'quantity': '0'},
            ],
            status=400,
        )
        self.assertIn('请至少填写一条到货数量', str(result))
        self.assertFalse(StockMove.objects.exists())
        purchase.refresh_from_db()
        self.assertEqual(purchase.status, 'approved')

    def test_real_overage_keeps_remaining_quantity_message(self):
        purchase = self.two_line_purchase()
        first, second = purchase.lines.order_by('pk')
        result = self.receive(
            purchase,
            [{'line': first.pk, 'quantity': '6'}, {'line': second.pk, 'quantity': '0'}],
            status=409,
        )
        self.assertIn('超过未收余量', str(result))
        self.assertFalse(StockMove.objects.exists())
