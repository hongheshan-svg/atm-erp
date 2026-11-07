"""Manual and automatic numbering share business validation and atomic imports."""

import csv
import io
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase
from openpyxl import Workbook

from apps.business.models import (
    BOMLine,
    Delivery,
    Item,
    Partner,
    Project,
    PurchaseOrder,
    Reconciliation,
    SalesOrder,
    Task,
)
from apps.business.services import bom_material_import, masterdata, transfers
from apps.core.models import ActionReceipt, AuditLog, CodeRule

from .test_commercial_chain import TODAY, BusinessFixtures


class ManualCodeTests(BusinessFixtures, TestCase):
    def setUp(self):
        self.setup_business()
        self.project = self.active_project(equipment=3)
        for stage in ('design', 'assembly', 'test'):
            Task.objects.create(
                project=self.project, title=stage, kind=stage, status='done', assignee=self.users['manager']
            )
        BOMLine.objects.create(project=self.project, item=self.item, quantity=3)
        self.post(
            'admin',
            'stocks/opening/',
            {'item': self.item.pk, 'location': '编号测试', 'quantity': '3', 'unit_cost': '1', 'reason': '期初'},
        )
        from apps.business.models import Stock

        self.post(
            'warehouse',
            'stocks/issue/',
            {
                'stock': Stock.objects.get(location='编号测试').pk,
                'project': self.project.pk,
                'quantity': '3',
                'reason': '发货准备',
            },
        )
        self.post(
            'finance',
            'entries/expense/',
            {'project': self.project.pk, 'title': '测试费用', 'amount': '100', 'due_date': TODAY},
            status=201,
        )
        self.entry = self.project.entries.get(kind='expense')
        CodeRule.objects.get_or_create(key='reconciliation', defaults={'prefix': 'DZ'})

    def upload(self, resource, rows, *, previous=False, xlsx=False, role='admin'):
        columns = transfers.PREVIOUS_CODE_COLUMNS[resource] if previous else transfers.SCHEMAS[resource][1]
        if xlsx:
            book, stream = Workbook(), io.BytesIO()
            book.active.append([label for label, _ in columns])
            for row in rows:
                book.active.append([row.get(key, '') for _, key in columns])
            book.save(stream)
            content = stream.getvalue()
        else:
            stream = io.StringIO()
            writer = csv.writer(stream)
            writer.writerow([label for label, _ in columns])
            writer.writerows([[row.get(key, '') for _, key in columns] for row in rows])
            content = stream.getvalue().encode()
        return self.clients[role].post(
            '/api/business/' + resource + '/import-file/',
            {
                'file': SimpleUploadedFile('test.xlsx' if xlsx else 'test.csv', content),
            },
            format='multipart',
        )

    def samples(self):
        return {
            'items': (Item, 'item', {'name': '完整型号气缸', 'specification': 'ＭX-20  /  A(10)', 'unit': 'PCS'}),
            'partners': (Partner, 'partner', {'name': '自编供应商', 'kind': '供应商'}),
            'sales': (SalesOrder, 'sale', {'name': '手工销售', 'customer': 'C1', 'manager': 'manager'}),
            'projects': (Project, 'project', {'name': '手工项目', 'customer': 'C1', 'manager': 'manager'}),
            'purchases': (
                PurchaseOrder,
                'purchase',
                {
                    'group': 'G1',
                    'project': self.project.code,
                    'supplier': 'S1',
                    'due_date': TODAY,
                    'item': 'I1',
                    'quantity': '1',
                    'unit_price': '2',
                },
            ),
            'deliveries': (
                Delivery,
                'delivery',
                {
                    'project': self.project.code,
                    'quantity': '1',
                    'date': TODAY,
                    'installer': 'member',
                    'acceptor': 'manager',
                },
            ),
            'reconciliations': (
                Reconciliation,
                'reconciliation',
                {
                    'entry': str(self.entry.pk),
                    'kind': '普通结算',
                    'counterparty_balance': '100',
                    'approved_amount': '100',
                    'reason': '核对费用',
                },
            ),
        }

    def test_all_seven_resources_preserve_custom_codes_and_preview_has_no_side_effects(self):
        for resource, (model, key, row) in self.samples().items():
            with self.subTest(resource=resource):
                code = '0000-' + resource
                before = (
                    model.objects.count(),
                    AuditLog.objects.count(),
                    ActionReceipt.objects.count(),
                    CodeRule.objects.get(key=key).counter,
                )
                preview = self.upload(resource, [{**row, 'code': code}], xlsx=True)
                self.assertEqual(preview.status_code, 200, preview.data)
                self.assertTrue(preview.data['can_import'], preview.data)
                self.assertEqual(
                    before,
                    (
                        model.objects.count(),
                        AuditLog.objects.count(),
                        ActionReceipt.objects.count(),
                        CodeRule.objects.get(key=key).counter,
                    ),
                )
                result = self.post('admin', resource + '/import-confirm/', {'token': preview.data['token']})
                obj = model.objects.get(pk=result['results'][0]['id'])
                self.assertEqual(obj.code, code)
                self.assertEqual(CodeRule.objects.get(key=key).counter, before[-1])
                self.assertEqual(
                    self.post('admin', resource + '/import-confirm/', {'token': preview.data['token']}), result
                )
                if resource == 'items':
                    self.assertEqual(obj.specification, row['specification'])
                if resource == 'reconciliations':
                    self.assertEqual(obj.status, 'draft')
                    self.assertIsNone(obj.confirmed_at)
                    self.assertEqual(self.entry.payments.count(), 0)
                duplicate = self.upload(resource, [{**row, 'code': code}])
                self.assertFalse(duplicate.data['can_import'], duplicate.data)

    def test_optional_codes_keep_previous_templates_compatible(self):
        for resource in transfers.MANUAL_CODE_LABELS:
            with self.subTest(resource=resource):
                preview = self.upload(resource, [self.samples()[resource][2]], previous=True)
                self.assertTrue(preview.data['can_import'], preview.data)

    def test_automatic_number_skips_manual_and_deleted_codes(self):
        self.post('purchaser', 'partners/', {'name': '先行手编', 'kind': 'supplier', 'code': 'PTY000001'}, status=201)
        auto = self.post('purchaser', 'partners/', {'name': '自动编号', 'kind': 'supplier'}, status=201)
        self.assertEqual(Partner.objects.get(pk=auto['id']).code, 'PTY000002')
        Partner.objects.get(pk=auto['id']).soft_delete(self.users['admin'])
        self.post('purchaser', 'partners/', {'name': '禁止占用', 'kind': 'supplier', 'code': 'PTY000002'}, status=400)
        self.assertEqual(CodeRule.objects.get(key='partner').counter, 2)

    def test_import_duplicate_code_rolls_back_whole_batch_and_confirms_against_latest_state(self):
        rows = [
            {'code': '000123', 'name': '甲', 'kind': 'supplier'},
            {'code': '000123', 'name': '乙', 'kind': 'supplier'},
        ]
        bad = self.upload('partners', rows)
        self.assertFalse(bad.data['can_import'])
        self.assertFalse(Partner.objects.filter(code='000123').exists())
        preview = self.upload('partners', [rows[0]])
        self.post('admin', 'partners/', rows[1], status=201)
        self.post('admin', 'partners/import-confirm/', {'token': preview.data['token']}, status=400)
        self.assertEqual(Partner.objects.get(code='000123').name, '乙')

    def test_custom_codes_cannot_bypass_roles_or_mutate_existing_identity(self):
        for code in ('X' * 31, 'X\t1', 123):
            self.post('admin', 'items/', {'code': code, 'name': '非法编号'}, status=400)
        self.post('member', 'items/', {'code': '000-member', 'name': '无权限'}, status=403)
        response = self.clients['admin'].patch(
            '/api/business/items/' + str(self.item.pk) + '/',
            {'code': 'NEW'},
            format='json',
            HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
        )
        self.assertEqual(response.status_code, 400)
        self.item.refresh_from_db()
        self.assertEqual(self.item.code, 'I1')
        self.assertEqual(
            self.upload('reconciliations', [self.samples()['reconciliations'][2]], role='manager').status_code, 403
        )

    def test_similar_spacing_requires_review_without_merging_or_rewriting(self):
        first = self.post(
            'admin',
            'items/',
            {'name': '滑块', 'code': '001-A', 'specification': 'ＨＧＷ20  CC', 'unit': 'PCS', 'brand': '上银'},
            status=201,
        )
        data = {'name': '导轨滑块', 'code': '001-B', 'specification': 'HGW20CC', 'unit': 'PCS', 'brand': '上银'}
        self.post('admin', 'items/', data, status=400)
        self.assertFalse(Item.objects.filter(code='001-B').exists())
        second = self.post(
            'admin', 'items/', {**data, 'duplicate_reason': '厂家确认不同后缀，保留专用编号'}, status=201
        )
        self.assertNotEqual(first['id'], second['id'])
        self.assertEqual(Item.objects.get(pk=first['id']).specification, 'ＨＧＷ20  CC')

    def test_signing_accepts_project_code_without_consuming_auto_counter(self):
        sale = self.post(
            'manager',
            'sales/',
            {'code': '000-SALE', 'name': '自编合同', 'customer': self.customer.pk, 'manager': self.users['manager'].pk},
            status=201,
        )
        self.post('manager', 'sales/' + str(sale['id']) + '/quote/', {'amount': '50', 'reason': '报价'})
        before = CodeRule.objects.get(key='project').counter
        signed = self.post(
            'manager',
            'sales/' + str(sale['id']) + '/sign/',
            {
                'project_code': '000-PRJ',
                'date': TODAY,
                'milestones': [{'title': '合同款', 'amount': '50', 'due_date': TODAY}],
            },
        )
        self.assertEqual(Project.objects.get(pk=signed['project']).code, '000-PRJ')
        self.assertEqual(CodeRule.objects.get(key='project').counter, before)

    def test_bom_manual_creation_preview_exact_reuse_and_mismatch(self):
        row = [
            '0000123',
            '上料',
            '1',
            '',
            '',
            '',
            '',
            '厂家  气缸',
            'ＭX-20  /  A(10)',
            '',
            '',
            '',
            'SMC',
            '标准件',
            'PCS',
        ]

        def preview(rows):
            stream = io.StringIO()
            writer = csv.writer(stream)
            writer.writerow(bom_material_import.HEADERS)
            writer.writerows(rows)
            return bom_material_import.preview(
                self.users['manager'], self.project, SimpleUploadedFile('bom.csv', stream.getvalue().encode())
            )

        result = preview([row])
        self.assertTrue(result['can_import'], result)
        self.assertEqual(result['lines'][0]['item_code'], '0000123')
        self.assertFalse(Item.objects.filter(code='0000123').exists())
        self.post('manager', 'projects/' + str(self.project.pk) + '/bom-import-confirm/', {'token': result['token']})
        item = Item.objects.get(code='0000123')
        self.assertEqual(item.name, row[7])
        self.assertEqual(item.specification, row[8])
        reused = preview([[row[0], '其他单元', '1', '', '', '', '', *([''] * 8)]])
        self.assertTrue(reused['can_import'], reused)
        self.assertEqual(reused['lines'][0]['material_action'], '使用已有编码')
        mismatch = row[:]
        mismatch[8] = '缺少后缀'
        self.assertFalse(preview([mismatch])['can_import'])
        item.refresh_from_db()
        self.assertEqual(item.specification, row[8])
        po = self.post(
            'purchaser',
            'purchases/',
            {
                'code': '000-PO-RAW',
                'project': self.project.pk,
                'supplier': self.supplier.pk,
                'due_date': TODAY,
                'lines': [{'item': item.pk, 'quantity': '1', 'unit_price': '10'}],
            },
            status=201,
        )
        contract = self.clients['purchaser'].get('/api/business/purchases/' + str(po['id']) + '/contract-preview/')
        self.assertEqual(contract.status_code, 200, contract.data)
        self.assertIn(row[8], str(contract.data))
        self.assertIn('0000123', str(contract.data))
        response = self.clients['purchaser'].get(
            '/api/business/items/similar/', {'name': '不同名称', 'specification': 'MX-20/A(10)'}
        )
        self.assertIn(item.pk, [obj['id'] for obj in response.data])


class ManualCodeConcurrencyTests(BusinessFixtures, TransactionTestCase):
    def setUp(self):
        self.setup_business()

    def test_same_custom_number_is_created_once_under_concurrent_requests(self):
        barrier = Barrier(2)

        def create(index):
            close_old_connections()
            try:
                from django.core.exceptions import ValidationError

                from apps.core.error_messages import validation_detail

                barrier.wait(timeout=10)
                try:
                    return masterdata.masterdata(
                        self.users['admin'],
                        str(uuid.uuid4()),
                        Partner,
                        {'code': '000-same', 'name': str(index), 'kind': 'supplier'},
                    )
                except ValidationError as exc:
                    return {'rejected': str(validation_detail(exc))}
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(create, range(2)))
        self.assertEqual(sum('id' in row for row in results), 1, results)
        self.assertEqual(Partner.objects.filter(code='000-same').count(), 1)
        self.assertEqual(CodeRule.objects.get(key='partner').counter, 0)
