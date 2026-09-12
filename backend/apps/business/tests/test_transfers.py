import csv
import io
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from openpyxl import Workbook, load_workbook

from apps.business.models import BOMLine, Item, Partner, Payment, Project, PurchaseOrder, SalesOrder, Stock, Task
from apps.business.services import transfers
from apps.core.models import ActionReceipt, AuditLog, CodeRule

from .test_commercial_chain import TODAY, BusinessFixtures


class TransferTests(BusinessFixtures, TestCase):
    def setUp(self):
        self.setup_business()

    def preview(self, resource, rows, role='admin', xlsx=False):
        headers = [label for label, _ in transfers.LEGACY_SCHEMAS[resource][1]]
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

    def test_model_validation_errors_keep_file_rows_and_roll_back_preview(self):
        counter = CodeRule.objects.get(key='partner').counter
        receipts = ActionReceipt.objects.count()
        audits = AuditLog.objects.count()
        template = self.clients['admin'].get('/api/business/partners/import-template/')
        headers = next(csv.reader(io.StringIO(template.content.decode('utf-8-sig'))))
        stream = io.StringIO()
        writer = csv.DictWriter(stream, fieldnames=headers)
        writer.writeheader()
        writer.writerows(
            [
                {'往来单位': '错误类型一', '类型': 'unknown'},
                {'往来单位': '有效但只预览', '类型': '供应商'},
                {'往来单位': '错误类型二', '类型': 'client'},
            ]
        )
        preview = self.clients['admin'].post(
            '/api/business/partners/import-file/',
            {'file': SimpleUploadedFile('partners.csv', stream.getvalue().encode())},
            format='multipart',
        )
        self.assertEqual(preview.status_code, 200, preview.data)
        self.assertFalse(preview.data['can_import'])
        self.assertIsNone(preview.data['token'])
        self.assertEqual([error['row'] for error in preview.data['errors']], [2, 4])
        self.assertTrue(all('kind' in error['message'] for error in preview.data['errors']))
        self.assertFalse(Partner.objects.filter(name__in=['错误类型一', '有效但只预览', '错误类型二']).exists())
        self.assertEqual(CodeRule.objects.get(key='partner').counter, counter)
        self.assertEqual(ActionReceipt.objects.count(), receipts)
        self.assertEqual(AuditLog.objects.count(), audits)

    def downloaded_preview(self, resource, rows, fmt='csv'):
        response = self.clients['admin'].get(f'/api/business/{resource}/import-template/', {'file_format': fmt})
        self.assertEqual(response.status_code, 200)
        if fmt == 'csv':
            headers = next(csv.reader(io.StringIO(response.content.decode('utf-8-sig'))))
            stream = io.StringIO()
            writer = csv.writer(stream)
            writer.writerow(headers)
            writer.writerows([[row.get(label, '') for label in headers] for row in rows])
            content = stream.getvalue().encode()
        else:
            book = load_workbook(io.BytesIO(response.content))
            headers = [cell.value for cell in book.active[1]]
            for row in rows:
                book.active.append([row.get(label, '') for label in headers])
            stream = io.BytesIO()
            book.save(stream)
            book.close()
            content = stream.getvalue()
        response = self.clients['admin'].post(
            f'/api/business/{resource}/import-file/',
            {'file': SimpleUploadedFile('filled.' + fmt, content)},
            format='multipart',
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data['can_import'], response.data)
        self.assertEqual([column['label'] for column in response.data['columns']], headers)
        return response

    def test_downloaded_templates_match_schema_and_preview_for_every_resource(self):
        project = self.active_project(equipment=2)
        task = Task.objects.create(project=project, title='模板工时任务', kind='design', assignee=self.users['admin'])
        self.commit('entries', self.preview('entries', [[project.code, '待付费用', '100', TODAY]]))
        entry = project.entries.get(kind='expense')
        self.commit('stocks', self.preview('stocks', [['I1', '领料仓', '5', '2', '期初']]))
        stock = Stock.objects.get(location='领料仓')
        BOMLine.objects.create(project=project, item=self.item, quantity=2)
        for stage in ['design', 'assembly', 'test']:
            Task.objects.create(project=project, title=stage, kind=stage, assignee=self.users['admin'], status='done')
        task.status = 'done'
        task.save()
        self.commit('moves', self.preview('moves', [[project.code, str(stock.pk), '', '1', '发货准备']]))
        samples = {
            'items': {
                '物料编码': 'NEW-TEMPLATE',
                '物料名称': '模板物料',
                '规格': '规格A',
                '品牌': '品牌B',
                '物料类别': '标准件',
                '单位': '台',
            },
            'partners': {'往来单位': '模板供应商', '类型': '供应商', '采购账期': '月结30天', '电话': '00123'},
            'sales': {'销售名称': '模板销售', '客户编码': 'C1', '负责人账号': 'manager', '设备数量': '1'},
            'projects': {'项目名称': '模板项目', '客户编码': 'C1', '负责人账号': 'manager', '设备数量': '1'},
            'purchases': {
                '分组号': 'G1',
                '项目编号': project.code,
                '供应商编码': 'S1',
                '交期': TODAY,
                '物料编码': 'I1',
                '数量': '1',
                '含税单价': '12.34',
                '采购账期': '现付',
            },
            'tasks': {'任务名称': '新设计', '阶段': '设计', '执行人账号': 'member', '项目编号': project.code},
            'stocks': {'物料编码': 'I1', '库位': '新期初仓', '库存数量': '2', '单位成本': '3.45', '原因': '期初'},
            'entries': {'项目编号': project.code, '款项': '模板差旅', '原金额': '10.25', '最近待付期限': TODAY},
            'payments': {
                '款项ID': str(entry.pk),
                '金额': '10',
                '日期': TODAY,
                '说明': '实际支付',
                '结算方式': '银行转账',
            },
            'time': {'任务ID': str(task.pk), '人员账号': 'admin', '日期': TODAY, '工时': '1.25', '说明': '设计'},
            'deliveries': {
                '项目编号': project.code,
                '设备数量': '1',
                '发货日': TODAY,
                '安装人账号': 'member',
                '验收人账号': 'manager',
            },
            'moves': {'库存ID': str(stock.pk), '数量': '1', '说明': '生产领料', '项目编号': project.code},
        }
        self.assertEqual(set(samples), set(transfers.SCHEMAS))
        for resource, row in samples.items():
            for fmt in ['csv', 'xlsx']:
                with self.subTest(resource=resource, fmt=fmt):
                    layout = self.clients['admin'].get(f'/api/business/{resource}/import-schema/')
                    self.assertEqual(layout.status_code, 200)
                    preview = self.downloaded_preview(resource, [row], fmt)
                    self.assertEqual(preview.data['columns'], layout.data['columns'])
                    self.assertEqual(preview.data['row_count'], 1)
                    self.assertEqual(preview.data['rows'][0]['row'], 2)
        # Confirm the new order does not swap brand/category/unit, including Chinese enums.
        result = self.commit('items', self.downloaded_preview('items', [samples['items']], 'xlsx'))
        item = Item.objects.get(pk=result['results'][0]['id'])
        self.assertEqual((item.brand, item.part_type, item.unit), ('品牌B', 'standard', '台'))
        self.assertEqual(self.clients['member'].get('/api/business/items/import-schema/').status_code, 403)

    def test_purchase_preview_retains_file_rows_and_grouped_confirmation(self):
        project = self.active_project()
        row = {
            '分组号': 'GROUP',
            '项目编号': project.code,
            '供应商编码': 'S1',
            '交期': TODAY,
            '物料编码': 'I1',
            '数量': '2',
            '含税单价': '10',
        }
        other = Item.objects.create(code='SECOND', name='第二物料')
        preview = self.downloaded_preview(
            'purchases', [row, {**row, '物料编码': other.code, '数量': '3', '含税单价': '20'}]
        )
        self.assertEqual((preview.data['count'], preview.data['row_count']), (1, 2))
        self.assertEqual([r['row'] for r in preview.data['rows']], [2, 3])
        self.assertNotIn('lines', preview.data['rows'][0]['data'])
        self.assertEqual(preview.data['rows'][1]['data']['item'], 'SECOND')
        self.commit('purchases', preview)
        purchase = PurchaseOrder.objects.get()
        self.assertEqual(purchase.status, 'draft')
        self.assertEqual(list(purchase.lines.order_by('id').values_list('quantity', 'unit_price')), [(2, 10), (3, 20)])
