import csv
import io
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from openpyxl import Workbook, load_workbook

from apps.business.models import BOMLine, Item, Partner, Payment, Project, PurchaseOrder, SalesOrder, Stock, Task
from apps.business.services import transfers
from apps.core.models import ActionReceipt, CodeRule

from .test_commercial_chain import TODAY, BusinessFixtures


class TransferTests(BusinessFixtures, TestCase):
    def setUp(self):
        self.setup_business()

    def preview(self, resource, rows, role='admin', xlsx=False):
        headers = [label for label, _ in transfers.SCHEMAS[resource][1]]
        if xlsx:
            output = io.BytesIO()
            book = Workbook()
            book.active.append(headers)
            for row in rows:
                book.active.append(row)
            book.save(output)
            content = output.getvalue()
        else:
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(headers)
            writer.writerows(rows)
            content = output.getvalue().encode()
        return self.clients[role].post(
            f'/api/business/{resource}/import-file/',
            {'file': SimpleUploadedFile('rows.xlsx' if xlsx else 'rows.csv', content)},
            format='multipart',
        )

    def commit(self, resource, preview, role='admin', status=200):
        return self.post(role, resource + '/import-confirm/', {'token': preview.data['token']}, status=status)

    def test_preview_rollback_confirmation_idempotency_and_changed_data(self):
        counter = CodeRule.objects.get(key='item').counter
        receipts = ActionReceipt.objects.count()
        preview = self.preview('items', [['NEW', '新物料', '规格', '件'], ['', '自动编码', '', '台']], xlsx=True)
        self.assertTrue(preview.data['can_import'], preview.data)
        self.assertEqual(Item.objects.count(), 1)
        self.assertEqual(ActionReceipt.objects.count(), receipts)
        self.assertEqual(CodeRule.objects.get(key='item').counter, counter)
        result = self.commit('items', preview)
        self.assertEqual(result['count'], 2)
        self.assertEqual(self.commit('items', preview), result)
        self.assertEqual(Item.objects.count(), 3)
        later = self.preview('items', [['A', '一', '', '件'], ['B', '二', '', '件']])
        Item.objects.create(code='B', name='被其他操作占用')
        self.commit('items', later, status=400)
        self.assertFalse(Item.objects.filter(code='A').exists())

    def test_invalid_duplicate_token_permission_and_expiry(self):
        preview = self.preview('items', [['X', '一', '', '件'], ['X', '二', '', '件']])
        self.assertFalse(preview.data['can_import'])
        self.assertEqual(preview.data['errors'][0]['row'], 3)
        self.assertFalse(Item.objects.filter(code='X').exists())
        self.assertEqual(self.preview('items', [['X', '一', '', '件']], role='member').status_code, 403)
        valid = self.preview('items', [['X', '一', '', '件']])
        self.commit('items', valid, role='manager', status=400)
        self.post('admin', 'items/import-confirm/', {'token': valid.data['token'] + 'bad'}, status=400)
        with patch('django.core.signing.time.time', return_value=9999999999):
            self.commit('items', valid, status=400)
        self.users['admin'].role = 'member'
        self.users['admin'].save()
        self.commit('items', valid, status=403)

    def test_masterdata_sales_projects_and_grouped_purchase_import(self):
        partners = self.preview('partners', [['往来', 'both', '联系人', '001234', '地址']])
        self.commit('partners', partners)
        self.assertEqual(Partner.objects.get(name='往来').phone, '001234')
        detail = ['导入需求', 'C1', 'manager', '说明', TODAY, '2', '12']
        self.commit('sales', self.preview('sales', [detail]))
        self.assertEqual(SalesOrder.objects.get(name='导入需求').status, 'draft')
        self.commit('projects', self.preview('projects', [detail + ['member']]))
        project = Project.objects.get(name='导入需求')
        self.assertTrue(project.members.filter(username='member').exists())
        other = Item.objects.create(code='I2', name='第二物料')
        rows = [
            ['P1', project.code, 'S1', TODAY, '', 'I1', '2', '10'],
            ['P1', project.code, 'S1', TODAY, '', other.code, '3', '20'],
        ]
        preview = self.preview('purchases', rows, role='purchaser')
        self.assertTrue(preview.data['can_import'], preview.data)
        self.commit('purchases', preview, role='purchaser')
        purchase = PurchaseOrder.objects.get()
        self.assertEqual(purchase.status, 'draft')
        self.assertEqual(purchase.lines.count(), 2)
        self.assertFalse(project.entries.exists())
        exported = self.clients['purchaser'].get('/api/business/purchases/export/')
        exported_rows = list(csv.reader(io.StringIO(exported.content.decode('utf-8-sig'))))
        self.assertEqual(len(exported_rows), 3)
        self.assertIn('物料编码', exported_rows[0])

    def test_operational_imports_reuse_finance_inventory_and_execution(self):
        project = self.active_project()
        self.commit('tasks', self.preview('tasks', [[project.code, 'design', '设计任务', '', 'member', TODAY]]))
        task = Task.objects.get(title='设计任务')
        timed = self.preview('time', [[str(task.pk), 'member', TODAY, '2', '设计']], role='member')
        self.assertTrue(timed.data['can_import'], timed.data)
        self.commit('time', timed, role='member')
        bad = self.preview('time', [[str(task.pk), 'manager', TODAY, '2', '越权']], role='member')
        self.assertFalse(bad.data['can_import'])
        self.commit(
            'entries', self.preview('entries', [[project.code, '差旅', '100', TODAY]], role='finance'), role='finance'
        )
        entry = project.entries.get(kind='expense')
        payment = self.preview('payments', [[str(entry.pk), '30', TODAY, '支付']], role='finance')
        self.commit('payments', payment, role='finance')
        self.assertEqual(Payment.objects.get(entry=entry).amount, 30)
        excessive = self.preview('payments', [[str(entry.pk), '80', TODAY, '超付']], role='finance')
        self.assertFalse(excessive.data['can_import'])
        self.commit('stocks', self.preview('stocks', [['I1', '主仓', '2', '10', '期初']]))
        stock = Stock.objects.get(item=self.item)
        BOMLine.objects.create(project=project, item=self.item, quantity=1)
        self.commit(
            'moves',
            self.preview('moves', [[project.code, str(stock.pk), '', '1', '领料']], role='warehouse'),
            role='warehouse',
        )
        for stage in ['design', 'assembly', 'test']:
            Task.objects.update_or_create(
                project=project,
                kind=stage,
                defaults={'title': stage, 'assignee': self.users['member'], 'status': 'done'},
            )
        delivery = self.preview('deliveries', [[project.code, '1', TODAY, 'member', 'manager', '发货']])
        self.assertTrue(delivery.data['can_import'], delivery.data)
        self.commit('deliveries', delivery)
        self.assertEqual(project.deliveries.count(), 1)

    def test_exports_all_filtered_rows_sensitive_scope_and_formulas(self):
        for index in range(25):
            Item.objects.create(code=f'E{index}', name='=HYPERLINK("bad")')
        response = self.clients['member'].get('/api/business/items/export/', {'search': 'E', 'page_size': 1})
        self.assertEqual(response.status_code, 200)
        rows = list(csv.reader(io.StringIO(response.content.decode('utf-8-sig'))))
        self.assertEqual(len(rows), 26)
        self.assertTrue(rows[1][2].startswith("'="))
        xlsx = self.clients['admin'].get('/api/business/items/export/', {'file_format': 'xlsx'})
        book = load_workbook(io.BytesIO(xlsx.content))
        self.assertFalse(any(cell.data_type == 'f' for row in book.active for cell in row))
        project = self.active_project()
        project.members.clear()
        response = self.clients['member'].get('/api/business/projects/export/')
        self.assertNotIn(project.code, response.content.decode())
        project.members.add(self.users['member'])
        response = self.clients['member'].get('/api/business/projects/export/')
        self.assertIn(project.code, response.content.decode())
        self.assertNotIn('合同金额', response.content.decode())
        self.assertEqual(self.clients['member'].get('/api/business/payments/export/').status_code, 403)
        self.assertEqual(
            self.clients['manager'].get('/api/business/reports/', {'file_format': 'xlsx'}).status_code, 403
        )
        report = self.clients['admin'].get('/api/business/reports/', {'file_format': 'csv', 'search': project.code})
        self.assertIn(project.code, report.content.decode())
        self.assertIn('当前筛选全部项目', report.content.decode())
        with patch('apps.business.services.tabular.MAX_EXPORT', 1):
            self.assertEqual(self.clients['admin'].get('/api/business/items/export/').status_code, 400)

    def test_templates_and_malformed_files(self):
        for resource in transfers.SCHEMAS:
            for fmt in ['csv', 'xlsx']:
                response = self.clients['admin'].get(f'/api/business/{resource}/import-template/', {'file_format': fmt})
                self.assertEqual(response.status_code, 200, resource)
        formula = self.preview('items', [['X', '=1+1', '', '件']], xlsx=True)
        self.assertEqual(formula.status_code, 400)
        missing = self.preview('payments', [['999999', '1', TODAY, '不存在']])
        self.assertEqual(missing.status_code, 200)
        self.assertFalse(missing.data['can_import'])
