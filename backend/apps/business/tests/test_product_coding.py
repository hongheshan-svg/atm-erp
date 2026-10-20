from datetime import date
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from apps.business.models import BOMLine, Item
from apps.business.services import bom_import
from apps.core.models import ActionReceipt, AuditLog, CodeRule

from .test_commercial_chain import BusinessFixtures


class ProductCodingTests(BusinessFixtures, TestCase):
    def setUp(self):
        self.setup_business()

    def auto_preview(self, project, records):
        import csv
        import io

        from apps.business.services.bom_material_import import HEADERS

        stream = io.StringIO()
        writer = csv.writer(stream)
        writer.writerow(HEADERS)
        writer.writerows(records)
        response = self.clients['manager'].post(
            f'/api/business/projects/{project.pk}/import-preview/',
            {'file': SimpleUploadedFile('bom.csv', stream.getvalue().encode())},
            format='multipart',
        )
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def test_bom_auto_creation_preview_rollback_and_idempotent_confirmation(self):
        project = self.active_project()
        row = ['', '上料', '2', '新增', '', '', '', '新导入气缸', 'ABC-10', '', '', '21', 'SMC', 'standard', '件']
        preview = self.auto_preview(project, [row, [*row[:1], '下料', *row[2:]]])
        self.assertTrue(preview['can_import'], preview)
        self.assertEqual(preview['lines'][0]['item_code'], '确认时自动生成')
        self.assertFalse(Item.objects.filter(name='新导入气缸').exists())
        self.assertEqual(CodeRule.objects.get(key='item').product_counters, {})
        saved = self.post('manager', f'projects/{project.pk}/bom-import-confirm/', {'token': preview['token']})
        item = Item.objects.get(name='新导入气缸')
        self.assertEqual(item.code, '2199000001')
        self.assertEqual(BOMLine.objects.filter(project=project, item=item).count(), 2)
        self.assertEqual(
            self.post('manager', f'projects/{project.pk}/bom-import-confirm/', {'token': preview['token']}), saved
        )
        other = self.active_project()
        reuse = self.auto_preview(other, [row])
        self.assertEqual(reuse['lines'][0]['material_action'], '复用相同物料')
        self.post('manager', f'projects/{other.pk}/bom-import-confirm/', {'token': reuse['token']})
        self.assertEqual(Item.objects.filter(name='新导入气缸').count(), 1)

    def test_bom_auto_creation_validation_failure_and_stale_token_are_atomic(self):
        project = self.active_project()
        row = ['', '上料', '2', '新增', '', '', '', '失败不得落库', 'ABC', '', '', '21', '', 'standard', '件']
        bad = self.auto_preview(project, [row, ['', '下料', '-1', *row[3:]]])
        self.assertFalse(bad['can_import'])
        self.assertFalse(Item.objects.filter(name='失败不得落库').exists())
        preview = self.auto_preview(project, [row])
        BOMLine.objects.create(project=project, item=self.item, quantity=1)
        self.post('manager', f'projects/{project.pk}/bom-import-confirm/', {'token': preview['token']}, status=409)
        self.assertFalse(Item.objects.filter(name='失败不得落库').exists())
        self.assertEqual(CodeRule.objects.get(key='item').product_counters, {})
        self.post('member', f'projects/{project.pk}/bom-import-confirm/', {'token': preview['token']}, status=403)

    def test_invalid_material_preview_keeps_all_rows_and_collects_errors_without_writes(self):
        project = self.active_project()
        row = ['', '上料', '2', '', '', '', '吴兴广', '预览气缸', 'ABC', '', '', '21', '', '标准件', '件']
        bad_material = ['', '', '1', '', '', '', '', '预览机架', '', '图001', 'A', '有图钣金件', '', '钣金', 'PCS']
        counts = [model.objects.count() for model in (Item, BOMLine, ActionReceipt, AuditLog)]
        preview = self.auto_preview(
            project, [row, bad_material, [''] * 15, ['', '下料', '-1', *row[3:]], ['', '装配', '3', *row[3:]]]
        )
        self.assertFalse(preview['can_import'])
        self.assertNotIn('token', preview)
        self.assertEqual([line['row'] for line in preview['lines']], [2, 3, 5, 6])
        self.assertEqual([issue['row'] for issue in preview['errors']], [3, 5])
        problem = preview['lines'][1]
        self.assertEqual(problem['item_name'], '预览机架')
        self.assertEqual(problem['product_category'], '有图钣金件')
        for field in ('规格', '产品编码类别', '物料类别'):
            self.assertIn(field, problem['validation_error'])
        self.assertIn('数量', preview['lines'][2]['validation_error'])
        self.assertEqual(preview['lines'][0]['item_code'], '确认时自动生成')
        self.assertNotIn('item', preview['lines'][0])
        self.assertEqual(preview['lines'][3]['validation_error'], '')
        self.assertEqual([model.objects.count() for model in (Item, BOMLine, ActionReceipt, AuditLog)], counts)
        self.assertEqual(CodeRule.objects.get(key='item').product_counters, {})

    def test_xlsx_invalid_materials_are_visible_with_dates_and_empty_extra_column(self):
        import io

        from openpyxl import Workbook

        from apps.business.services.bom_material_import import HEADERS

        project = self.active_project()
        book = Workbook()
        sheet = book.active
        sheet.title = '数据'
        sheet.append([*HEADERS, None])
        sheet.append(
            [
                '',
                '机械手',
                4,
                '',
                date(2026, 9, 25),
                date(2026, 9, 10),
                '吴兴广',
                '滑块',
                'HGW20CC',
                '',
                'PCS',
                '无图标准件',
                '上银',
                '标准件',
                'PCS',
            ]
        )
        sheet.append(['', '', 1, '', '', '', '', '防锈润滑剂', '24瓶装', '', '', '', '', '无图其它', ''])
        stream = io.BytesIO()
        book.save(stream)
        response = self.clients['manager'].post(
            f'/api/business/projects/{project.pk}/import-preview/',
            {'file': SimpleUploadedFile('bom.xlsx', stream.getvalue())},
            format='multipart',
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(response.data['can_import'])
        self.assertEqual(len(response.data['lines']), 2)
        self.assertEqual(response.data['lines'][0]['required_date'], '2026-09-25')
        self.assertEqual([issue['row'] for issue in response.data['errors']], [2, 3])
        self.assertIn('单位', response.data['errors'][1]['message'])
        self.assertNotIn('token', response.data)
        self.assertFalse(Item.objects.filter(name__in=['滑块', '防锈润滑剂']).exists())
        self.assertEqual(CodeRule.objects.get(key='item').product_counters, {})

    def test_bom_confirmation_rechecks_purchase_floor_and_rolls_back_material(self):
        project = self.active_project()
        BOMLine.objects.create(project=project, item=self.item, quantity=3)
        row = ['', '上料', '2', '新增', '', '', '', '确认失败不得落库', 'ABC', '', '', '21', '', 'standard', '件']
        preview = self.auto_preview(project, [row, [self.item.code, '', '2', '减少', '', '', '', *([''] * 8)]])
        self.assertTrue(preview['can_import'], preview)
        self.purchase(project, qty='3.000')
        self.post('manager', f'projects/{project.pk}/bom-import-confirm/', {'token': preview['token']}, status=400)
        self.assertFalse(Item.objects.filter(name='确认失败不得落库').exists())
        self.assertEqual(CodeRule.objects.get(key='item').product_counters, {})
        self.assertEqual(BOMLine.objects.get(project=project).quantity, 3)

    def test_category_sequences_years_and_no_reuse(self):
        with patch('apps.core.models.timezone.localdate', return_value=date(2026, 9, 11)):
            self.assertEqual(CodeRule.generate_code('item', product_category='11'), '1126000001')
            self.assertEqual(CodeRule.generate_code('item', product_category='12'), '1226000001')
            self.assertEqual(CodeRule.generate_code('item', product_category='21'), '2199000001')
        with patch('apps.core.models.timezone.localdate', return_value=date(2027, 1, 1)):
            self.assertEqual(CodeRule.generate_code('item', product_category='11'), '1127000001')
            self.assertEqual(CodeRule.generate_code('item', product_category='21'), '2199000002')
        Item.all_objects.create(code='2299000001', name='已删编码', is_deleted=True)
        self.assertEqual(CodeRule.generate_code('item', product_category='22'), '2299000002')

    def test_api_requires_drawing_and_preserves_version_identity(self):
        data = {'name': '台板', 'specification': '6061 300×200', 'product_category': '11'}
        self.post('purchaser', 'items/', data, status=400)
        self.assertEqual(CodeRule.objects.get(key='item').product_counters, {})
        result = self.post(
            'purchaser', 'items/', {**data, 'drawing_number': 'a2605-01-0002', 'drawing_revision': 'A'}, status=201
        )
        item = Item.objects.get(pk=result['id'])
        self.assertRegex(item.code, r'^11\d{8}$')
        response = self.clients['purchaser'].patch(
            f'/api/business/items/{item.pk}/',
            {'drawing_revision': 'B'},
            format='json',
            HTTP_IDEMPOTENCY_KEY='version-change',
        )
        self.assertEqual(response.status_code, 400)
        item.refresh_from_db()
        self.assertEqual(item.drawing_revision, 'A')
        self.post(
            'purchaser',
            'items/',
            {**data, 'name': '另一台板', 'drawing_number': 'A2605-01-0002', 'drawing_revision': 'a'},
            status=400,
        )
        self.post(
            'purchaser',
            'items/',
            {**data, 'drawing_number': 'a2605-01-0002', 'drawing_revision': 'B'},
            status=201,
        )
        self.post('member', 'items/', {**data, 'drawing_number': 'new'}, status=403)
        self.post('purchaser', 'items/', {'name': '旧自定义', 'code': '000123'}, status=201)
        self.assertTrue(Item.objects.filter(code='000123').exists())

    def test_new_bom_template_dates_and_legacy_preservation(self):
        project = self.active_project()
        raw = ','.join(bom_import.HEADERS) + f'\n{self.item.code},上料,2,新增,2026-10-01,2026-09-11,设计员\n'
        preview = bom_import.preview(project, SimpleUploadedFile('bom.csv', raw.encode()))
        self.assertTrue(preview['can_import'], preview)
        line = preview['lines'][0]
        keys = ('item', 'quantity', 'change_note', 'assembly_unit', 'required_date', 'application_date', 'applicant')
        self.post(
            'manager',
            f'projects/{project.pk}/revise-bom/',
            {'expected_revision': preview['expected_revision'], 'lines': [{key: line[key] for key in keys}]},
        )
        saved = BOMLine.objects.get(project=project)
        self.assertEqual(saved.required_date, date(2026, 10, 1))
        old = bom_import.preview(
            project,
            SimpleUploadedFile('old.csv', f'物料编码,单元,需求数量,变更说明\n{self.item.code},上料,3,调整\n'.encode()),
        )
        self.assertTrue(old['can_import'])
        old_line = old['lines'][0]
        self.assertNotIn('required_date', old_line)
        self.post(
            'manager',
            f'projects/{project.pk}/revise-bom/',
            {'expected_revision': old['expected_revision'], 'lines': [{key: old_line[key] for key in keys[:4]}]},
        )
        saved.refresh_from_db()
        self.assertEqual(saved.required_date, date(2026, 10, 1))
        bad = bom_import.preview(
            project, SimpleUploadedFile('bad.csv', raw.replace('2026-10-01', '2026-02-30').encode())
        )
        self.assertFalse(bad['can_import'])

    def test_previous_item_template_and_new_category_template(self):
        for content in (
            '物料编码,物料名称,规格,品牌,物料类别,单位,独立建码原因\nOLD001,旧模板件,ABC,SMC,标准件,件,\n',
            '物料编码,物料名称,规格,图号,图档版本,产品编码类别,品牌,物料类别,单位,独立建码原因\n,新模板件,DEF,,,无图·标准件,SMC,标准件,件,\n',
        ):
            response = self.clients['purchaser'].post(
                '/api/business/items/import-file/',
                {'file': SimpleUploadedFile('items.csv', content.encode())},
                format='multipart',
            )
            self.assertEqual(response.status_code, 200, response.data)
            self.assertTrue(response.data['can_import'], response.data)
        self.assertFalse(Item.objects.filter(name='新模板件').exists())
        self.assertEqual(CodeRule.objects.get(key='item').product_counters, {})
