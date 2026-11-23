import csv
import io

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from apps.business.models import IssueSlip, Item, Project, Stock

from .test_commercial_chain import TODAY, BusinessFixtures


class MaterialTrackingTests(BusinessFixtures, TestCase):
    """物料跟踪：跨项目「项目×物料」一行，需求、采购、到货、领料与缺料同 BOM 页口径；单号、价格按岗位可见。"""

    def setUp(self):
        self.setup_business()
        Item.objects.filter(pk=self.item.pk).update(part_type='standard', product_category='21')
        self.plate = Item.objects.create(code='P1', name='底板', specification='6061 板厚5mm', part_type='custom')
        self.project = self.active_project()
        self.post(
            'manager',
            f'projects/{self.project.pk}/revise-bom/',
            {
                'expected_revision': self.bom_version(self.project.pk),
                'lines': [
                    {'item': self.item.pk, 'quantity': '3', 'assembly_unit': '上料', 'change_note': '首版'},
                    {'item': self.item.pk, 'quantity': '2', 'assembly_unit': '下料', 'change_note': '首版'},
                    {'item': self.plate.pk, 'quantity': '2', 'assembly_unit': '上料', 'change_note': '首版'},
                ],
            },
        )
        self.order = self.purchase(self.project)
        line = self.order.lines.get()
        self.post(
            'warehouse',
            f'purchases/{self.order.pk}/receive/',
            {'lines': [{'line': line.pk, 'quantity': '4'}], 'reason': '送货单 SH-001'},
        )
        stock = Stock.objects.get(item=self.item)
        self.post(
            'warehouse',
            'stocks/issue/',
            {'project': self.project.pk, 'stock': stock.pk, 'quantity': '1', 'recipient': '装配班 张师傅'},
        )

    def rows(self, role='manager', **params):
        return self.get(role, 'material-tracking/', params)['results']

    def test_one_row_per_project_and_material_with_purchase_receipt_and_issue(self):
        rows = {row['item_code']: row for row in self.rows()}
        self.assertEqual(set(rows), {'I1', 'P1'})
        motor = rows['I1']
        self.assertEqual(
            {key: motor[key] for key in ('quantity', 'assembly_units', 'ordered', 'incoming', 'received', 'issued')},
            {
                'quantity': '5.000',
                'assembly_units': '上料、下料',
                'ordered': '5.000',
                'incoming': '1.000',
                'received': '4.000',
                'issued': '1.000',
            },
        )
        self.assertEqual((motor['status'], motor['status_label'], motor['shortage']), ('incoming', '在途', '0.000'))
        self.assertEqual(motor['purchase_codes'], f'{self.order.code} 部分收货')
        self.assertEqual(
            motor['purchase_refs'], [{'id': self.order.pk, 'code': self.order.code, 'status_label': '部分收货'}]
        )
        self.assertEqual([ref['code'] for ref in motor['slip_refs']], [motor['issue_slips']])
        self.assertEqual((motor['suppliers'], motor['unit_prices'], motor['amount']), ('供应商', '100.00', '500.00'))
        self.assertEqual(motor['delivery_notes'], '送货单 SH-001')
        self.assertEqual(motor['recipients'], '装配班 张师傅')
        self.assertTrue(motor['issue_slips'].startswith('LL'))
        self.assertIsNotNone(motor['last_received_date'])
        self.assertIsNotNone(motor['last_issued_date'])
        plate = rows['P1']
        self.assertEqual((plate['status'], plate['shortage'], plate['ordered']), ('shortage', '2.000', '0.000'))
        # 缺料与 BOM 页同一口径。
        demand = self.get('manager', f'projects/{self.project.pk}/demand/')['lines']
        self.assertEqual(
            sum(float(line['shortage']) for line in demand if line['item'] == self.plate.pk), float(plate['shortage'])
        )

    def test_materials_bought_outside_the_bom_get_their_own_rows(self):
        extra = Item.objects.create(code='Z9', name='扎带', specification='3x100', part_type='standard')
        order = self.post(
            'purchaser',
            'purchases/',
            {
                'project': self.project.pk,
                'supplier': self.supplier.pk,
                'due_date': TODAY,
                'over_bom_reason': '现场补料',
                'lines': [{'item': extra.pk, 'quantity': '10', 'unit_price': '1.50'}],
            },
            status=201,
        )
        self.post('purchaser', f'purchases/{order["id"]}/submit/')
        row = {row['item_code']: row for row in self.rows()}['Z9']
        self.assertEqual(
            {key: row[key] for key in ('in_bom', 'quantity', 'shortage', 'unapproved', 'status_label', 'amount')},
            {
                'in_bom': False,
                'quantity': None,
                'shortage': '0.000',
                'unapproved': '10.000',
                'status_label': '待批采购',
                'amount': '15.00',
            },
        )
        self.assertEqual([row['item_code'] for row in self.rows(outside_bom='true')], ['Z9'])
        self.assertEqual([row['item_code'] for row in self.rows(search='扎带')], ['Z9'])
        self.assertTrue(all(row['in_bom'] for row in self.rows() if row['item_code'] != 'Z9'))

    def test_filters_by_status_search_part_type_supplier_and_project_scope(self):
        self.assertEqual([row['item_code'] for row in self.rows(status='shortage')], ['P1'])
        self.assertEqual([row['item_code'] for row in self.rows(search='底板')], ['P1'])
        self.assertEqual([row['item_code'] for row in self.rows(part_type='standard')], ['I1'])
        self.assertEqual([row['item_code'] for row in self.rows(supplier=self.supplier.pk)], ['I1'])
        self.get('manager', 'material-tracking/', {'status': 'bogus'}, status=400)
        # 已结项项目默认不列；勾「包括已验收、已结项」或指定项目时列出。
        Project.objects.filter(pk=self.project.pk).update(status='closed')
        self.assertEqual(self.rows(), [])
        self.assertEqual(len(self.rows(all_projects='true')), 2)
        self.assertEqual(len(self.rows(project=self.project.pk)), 2)

    def test_purchase_details_and_prices_follow_roles_and_project_scope(self):
        member = {row['item_code']: row for row in self.rows('member')}['I1']
        for hidden in (
            'purchase_codes',
            'purchase_refs',
            'suppliers',
            'buyers',
            'delivery_notes',
            'unit_prices',
            'amount',
        ):
            self.assertNotIn(hidden, member)
        self.assertEqual(
            (member['received'], member['recipients'], member['due_dates']),
            ('4.000', '装配班 张师傅', member['due_dates']),
        )
        warehouse = {row['item_code']: row for row in self.rows('warehouse')}['I1']
        self.assertIn('purchase_codes', warehouse)
        self.assertNotIn('unit_prices', warehouse)
        # 不是项目成员的工程师看不到这个项目；只有销售岗位的账号没有入口。
        self.assertEqual(self.rows('mechanical_engineer'), [])
        self.get('sales_manager', 'material-tracking/', status=403)

    def test_export_matches_the_list_and_drops_columns_by_role(self):
        response = self.clients['purchaser'].get('/api/business/material-tracking/export/', {'file_format': 'csv'})
        self.assertEqual(response.status_code, 200)
        rows = list(csv.DictReader(io.StringIO(response.content.decode('utf-8-sig'))))
        self.assertEqual([row['物料编码'] for row in rows], [row['item_code'] for row in self.rows('purchaser')])
        motor = next(row for row in rows if row['物料编码'] == 'I1')
        self.assertEqual((motor['领料人'], motor['单价'], motor['状态']), ('装配班 张师傅', '100.00', '在途'))
        self.assertEqual(motor['物料类别'], '标准件')
        response = self.clients['member'].get('/api/business/material-tracking/export/', {'file_format': 'xlsx'})
        self.assertEqual(response.status_code, 200)
        from openpyxl import load_workbook

        headers = [cell.value for cell in load_workbook(io.BytesIO(response.content)).active[1]]
        self.assertIn('领料人', headers)
        for hidden in ('单价', '金额', '采购单号', '供应商'):
            self.assertNotIn(hidden, headers)

    def test_query_count_does_not_grow_with_rows(self):
        def count():
            with CaptureQueriesContext(connection) as queries:
                self.rows()
            return len(queries)

        before = count()
        extra = Item.objects.bulk_create([Item(code=f'X{i}', name=f'物料{i}') for i in range(30)])
        self.post(
            'manager',
            f'projects/{self.project.pk}/revise-bom/',
            {
                'expected_revision': self.bom_version(self.project.pk),
                'lines': [
                    {'item': self.item.pk, 'quantity': '3', 'assembly_unit': '上料', 'change_note': '补充'},
                    {'item': self.item.pk, 'quantity': '2', 'assembly_unit': '下料', 'change_note': '补充'},
                    {'item': self.plate.pk, 'quantity': '2', 'assembly_unit': '上料', 'change_note': '补充'},
                    *(
                        {'item': item.pk, 'quantity': '1', 'assembly_unit': '上料', 'change_note': '补充'}
                        for item in extra
                    ),
                ],
            },
        )
        self.assertEqual(count(), before)


class IssueRecipientTests(BusinessFixtures, TestCase):
    """领料人：实际来领料的人记在领料单上，单行领料、批量领料都可填，领料单与库存流水可查。"""

    def setUp(self):
        self.setup_business()
        self.project = self.active_project()
        self.post(
            'manager',
            f'projects/{self.project.pk}/revise-bom/',
            {
                'expected_revision': self.bom_version(self.project.pk),
                'lines': [{'item': self.item.pk, 'quantity': '5', 'assembly_unit': '上料', 'change_note': '首版'}],
            },
        )
        order = self.purchase(self.project)
        self.post(
            'warehouse', f'purchases/{order.pk}/receive/', {'lines': [{'line': order.lines.get().pk, 'quantity': '5'}]}
        )
        self.stock = Stock.objects.get(item=self.item)

    def test_single_and_batch_issue_record_recipient_on_the_slip(self):
        single = self.post(
            'warehouse',
            'stocks/issue/',
            {'project': self.project.pk, 'stock': self.stock.pk, 'quantity': '1', 'recipient': ' 李四 '},
        )
        self.assertEqual(IssueSlip.objects.get(pk=single['slip']).recipient, '李四')
        batch = self.post(
            'warehouse',
            'stocks/bom-issue/',
            {'project': self.project.pk, 'recipient': '王五', 'lines': [{'stock': self.stock.pk, 'quantity': '1'}]},
        )
        slips = self.get('warehouse', 'issue-slips/', {'search': '王五'})['results']
        self.assertEqual([(row['id'], row['recipient']) for row in slips], [(batch['slip'], '王五')])
        detail = self.get('warehouse', f'issue-slips/{batch["slip"]}/')
        self.assertEqual(detail['recipient'], '王五')
        moves = self.get('warehouse', 'moves/', {'slip': batch['slip']})['results']
        self.assertEqual([row['recipient'] for row in moves], ['王五'])
        # 不填照常领料；超长拒绝。
        plain = self.post(
            'warehouse', 'stocks/issue/', {'project': self.project.pk, 'stock': self.stock.pk, 'quantity': '1'}
        )
        self.assertEqual(IssueSlip.objects.get(pk=plain['slip']).recipient, '')
        self.post(
            'warehouse',
            'stocks/issue/',
            {'project': self.project.pk, 'stock': self.stock.pk, 'quantity': '1', 'recipient': '长' * 81},
            status=400,
        )
