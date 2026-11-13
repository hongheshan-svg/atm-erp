from datetime import date

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from apps.business.models import BOMLine, Item
from apps.business.services import bom_import
from apps.core.models import ActionReceipt, AuditLog, CodeRule

from .test_commercial_chain import BusinessFixtures, freeze_today


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

    def test_bom_import_backfills_blank_brand_only_and_saves_without_bom_change(self):
        project = self.active_project()
        blank = Item.objects.create(code='BF-001', name='侧出上壳', specification='H24B-SE', unit='件')
        branded = Item.objects.create(code='BF-002', name='公插芯', specification='HE-024-M', unit='件', brand='哈丁')
        for item in (blank, branded):
            BOMLine.objects.create(project=project, item=item, quantity=2, assembly_unit='上料')

        def demand():
            response = self.clients['manager'].get(f'/api/business/projects/{project.pk}/demand/')
            self.assertEqual(response.status_code, 200, response.data)
            return response.data

        revision = demand()['revision']
        # 「可回导模板」原样导回，只在品牌列补上空缺：BOM 用量不变，也照样可以导入。
        row = ['BF-001', '上料', '2', '', '', '', '', '侧出上壳', 'H24B-SE', '', '', '', '哈丁', '', '件']
        same = ['BF-002', '上料', '2', '', '', '', '', '公插芯', 'HE-024-M', '', '', '', '哈丁', '', '件']
        preview = self.auto_preview(project, [row, same])
        self.assertTrue(preview['can_import'], preview)
        self.assertEqual(
            [line['material_action'] for line in preview['lines']], ['沿用已有物料，补填品牌', '使用已有编码']
        )
        self.assertEqual({line['bom_action'] for line in preview['lines']}, {'unchanged'})
        blank.refresh_from_db()
        self.assertEqual(blank.brand, '')
        self.post('manager', f'projects/{project.pk}/bom-import-confirm/', {'token': preview['token']})
        blank.refresh_from_db()
        self.assertEqual(blank.brand, '哈丁')
        self.assertTrue(
            AuditLog.objects.filter(
                operation='item.save', resource=f'item:{blank.pk}', detail__fields=['brand']
            ).exists()
        )
        current = demand()
        self.assertEqual(current['revision'], revision)
        self.assertEqual(
            {line['item_code']: line['brand'] for line in current['lines']}, {'BF-001': '哈丁', 'BF-002': '哈丁'}
        )
        # 规格不同多半是编码填错，仍然拒绝；已有品牌不同只提示并按系统资料为准。都不覆盖主数据。
        rejected = self.auto_preview(
            project, [['BF-001', '上料', '2', '', '', '', '', '侧出上壳', 'H24B-SE-X', '', '', '', '', '', '件']]
        )
        self.assertFalse(rejected['can_import'])
        self.assertIn('请核对编码是否填错', str(rejected['errors']))
        self.assertIn('只会补填原来为空的品牌', str(rejected['errors']))
        tolerated = self.auto_preview(
            project, [['BF-002', '上料', '3', '补料', '', '', '', '公插芯', 'HE-024-M', '', '', '', '浩亭', '', '件']]
        )
        self.assertTrue(tolerated['can_import'], tolerated)
        self.assertEqual(tolerated['lines'][0]['material_action'], '使用已有编码')
        self.assertIn('品牌「哈丁」', tolerated['lines'][0]['material_hint'])
        branded.refresh_from_db()
        self.assertEqual(branded.brand, '哈丁')
        # 补品牌与改用量同一张表：两样都保存。
        third = Item.objects.create(code='BF-003', name='航插上壳', specification='H3A-TE', unit='件')
        BOMLine.objects.create(project=project, item=third, quantity=1, assembly_unit='上料')
        mixed = self.auto_preview(
            project, [['BF-003', '上料', '3', '补料', '', '', '', '航插上壳', 'H3A-TE', '', '', '', '浩亭', '', '件']]
        )
        self.assertTrue(mixed['can_import'], mixed)
        self.post('manager', f'projects/{project.pk}/bom-import-confirm/', {'token': mixed['token']})
        third.refresh_from_db()
        self.assertEqual(third.brand, '浩亭')
        self.assertEqual(BOMLine.objects.get(project=project, item=third).quantity, 3)

    def test_bom_import_merges_repeated_rows_and_reuses_same_model(self):
        project = self.active_project()
        handle = Item.objects.create(
            code='RM-001', name='把手', specification='XAG66-L132', brand='怡和达', unit='PCS', product_category='21'
        )
        washer = Item.objects.create(
            code='RM-002', name='垫片', specification='M6', brand='淘宝', unit='PCS', product_category='21'
        )

        def row(name, specification, brand, quantity, unit='', code=''):
            return [code, unit, quantity, '', '', '', '', name, specification, '', '', '21', brand, 'standard', 'PCS']

        valve = row('调速阀', 'PTL601A', '亚德客', '10')
        preview = self.auto_preview(
            project,
            [
                valve,
                row('拉手', 'XAG66-L132', '怡和达', '4'),
                row('调速阀', 'PTL601A', '亚德客', '2.5'),
                row('调速阀', 'PTL601A', '亚德客', '3', unit='1工位'),
                row('调速阀', 'PTL601A', '亚德客', '1'),
                row('提手', 'XAG66-L132', '怡和达', '6', code='RM-001'),
            ],
        )
        self.assertTrue(preview['can_import'], preview)
        lines = {line['row']: line for line in preview['lines']}
        # 同物料同单元（空单元也算）的重复行并入首次出现的行；不同单元仍是独立行。
        self.assertEqual(lines[2]['quantity'], '13.500')
        self.assertEqual(lines[2]['merged_rows'], [4, 6])
        self.assertEqual((lines[4]['bom_action'], lines[4]['merged_into']), ('merged', 2))
        self.assertEqual((lines[5]['bom_action'], lines[5]['quantity']), ('create', '3.000'))
        # 规格、品牌、单位相同而名称不同：按型号复用并提示系统名称；填了编码而名称不同同样只提示。
        self.assertEqual(lines[3]['material_action'], '按型号复用已有物料')
        self.assertIn('物料名称「把手」', lines[3]['material_hint'])
        self.assertEqual((lines[7]['material_action'], lines[7]['merged_into']), ('使用已有编码', 3))
        self.assertIn('物料名称「把手」', lines[7]['material_hint'])
        self.assertEqual(lines[3]['quantity'], '10.000')
        self.assertEqual(
            preview['summary'],
            {'create': 3, 'update': 0, 'unchanged': 0, 'merged': 3, 'untouched': 0, 'new_materials': 1},
        )
        self.post('manager', f'projects/{project.pk}/bom-import-confirm/', {'token': preview['token']})
        created = Item.objects.get(specification='PTL601A')
        self.assertEqual(
            sorted(
                (line.item_id, line.assembly_unit, str(line.quantity))
                for line in BOMLine.objects.filter(project=project)
            ),
            sorted([(handle.pk, '', '10.000'), (created.pk, '', '13.500'), (created.pk, '1工位', '3.000')]),
        )
        self.assertEqual(Item.objects.filter(specification='XAG66-L132').count(), 1)
        handle.refresh_from_db()
        self.assertEqual(handle.name, '把手')

        # 品牌栏是购买渠道时，同规格可能是不同零件：名称不同不自动复用，告诉人两条出路。
        other = self.active_project()
        blocked = self.auto_preview(other, [row('螺母', 'M6', '淘宝', '2')])
        self.assertFalse(blocked['can_import'])
        self.assertIn('购买渠道', blocked['errors'][0]['message'])
        self.assertIn('在物料编码列填写 RM-002', blocked['errors'][0]['message'])
        same_name = self.auto_preview(other, [row('垫片', 'M6', '淘宝', '2')])
        self.assertEqual(same_name['lines'][0]['material_action'], '按型号复用已有物料')
        self.assertEqual(same_name['lines'][0]['material_hint'], '')
        # 同一文件内先后两行：预览时前一行的编号还没生成，提示指向行号。
        in_file = self.auto_preview(other, [row('开口销', 'M3*16', '淘宝', '1'), row('定位销', 'M3*16', '淘宝', '1')])
        self.assertFalse(in_file['can_import'])
        self.assertIn('把名称改成与第 2 行一致', in_file['errors'][0]['message'])
        self.assertEqual(washer.pk, Item.objects.get(specification='M6').pk)

    def test_bom_import_merged_total_decides_update_and_requires_note_once(self):
        project = self.active_project()
        item = Item.objects.create(code='MG-001', name='合并件', specification='MG-1', unit='件')
        BOMLine.objects.create(project=project, item=item, quantity=5, assembly_unit='上料')
        blank = ['MG-001', '上料', '2', '', '', '', '', '', '', '', '', '', '', '', '']
        # 两行合计仍等于现有用量：视为不变。
        unchanged = self.auto_preview(project, [blank, ['MG-001', '上料', '3', *blank[3:]]])
        self.assertEqual(unchanged['summary']['unchanged'], 1)
        self.assertTrue(any(error.get('unchanged') for error in unchanged['errors']))
        # 合计变了就是修改：任一行写了变更说明即可，都没写则报在首次出现的行。
        missing = self.auto_preview(project, [blank, ['MG-001', '上料', '4', *blank[3:]]])
        self.assertEqual([error['row'] for error in missing['errors']], [2])
        self.assertIn('变更说明', missing['errors'][0]['message'])
        noted = self.auto_preview(project, [blank, ['MG-001', '上料', '4', '增加备件', *blank[4:]]])
        self.assertTrue(noted['can_import'], noted)
        self.post('manager', f'projects/{project.pk}/bom-import-confirm/', {'token': noted['token']})
        line = BOMLine.objects.get(project=project, item=item)
        self.assertEqual((str(line.quantity), line.change_note), ('6.000', '增加备件'))

    def test_bom_import_locks_existing_items_in_key_order_before_backfilling(self):
        import re

        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        project = self.active_project()
        low = Item.objects.create(code='LK-001', name='锁序甲', specification='A-1', unit='件')
        high = Item.objects.create(code='LK-002', name='锁序乙', specification='B-1', unit='件')
        # 文件先写主键大的物料：逐行补填品牌会先锁它，与按主键顺序加锁的其他单据交错时死锁。
        rows = [
            [item.code, '上料', '1', '新增', '', '', '', item.name, item.specification, '', '', '', '哈丁', '', '件']
            for item in (high, low)
        ]
        preview = self.auto_preview(project, rows)
        self.assertTrue(preview['can_import'], preview)
        with CaptureQueriesContext(connection) as queries:
            self.post('manager', f'projects/{project.pk}/bom-import-confirm/', {'token': preview['token']})
        locks = [
            query['sql']
            for query in queries.captured_queries
            if 'FOR UPDATE' in query['sql'] and re.search(r'FROM "lean_item" WHERE', query['sql'])
        ]
        self.assertTrue(locks)
        locked = re.search(r'"lean_item"\."id" IN \(([^)]*)\)', locks[0])
        self.assertIsNotNone(locked, locks[0])
        self.assertEqual({int(value) for value in locked.group(1).split(',')}, {low.pk, high.pk})
        self.assertEqual(set(Item.objects.filter(pk__in=[low.pk, high.pk]).values_list('brand', flat=True)), {'哈丁'})

    def test_bom_import_without_code_backfills_unbranded_same_item_instead_of_duplicating(self):
        project = self.active_project()
        row = ['', '上料', '2', '新增', '', '', '', '长方形接头', 'KDM10P-08', '', '', '21', '', 'standard', '件']
        first = self.auto_preview(project, [row])
        self.post('manager', f'projects/{project.pk}/bom-import-confirm/', {'token': first['token']})
        item = Item.objects.get(name='长方形接头')
        self.assertEqual(item.brand, '')
        # 原始表补上品牌、编码仍留空再导入：补到原物料上，不新建物料、不新增 BOM 行。
        again = self.auto_preview(project, [[*row[:3], '', *row[4:12], '哈丁', *row[13:]]])
        self.assertTrue(again['can_import'], again)
        self.assertEqual(again['lines'][0]['material_action'], '沿用已有物料，补填品牌')
        self.assertEqual(again['lines'][0]['bom_action'], 'unchanged')
        self.post('manager', f'projects/{project.pk}/bom-import-confirm/', {'token': again['token']})
        self.assertEqual(Item.objects.filter(name='长方形接头').count(), 1)
        item.refresh_from_db()
        self.assertEqual(item.brand, '哈丁')
        self.assertEqual(BOMLine.objects.filter(project=project).count(), 1)
        # 两个除品牌外相同的无品牌物料：不猜，要求填编码。
        Item.objects.create(code='DUP-A', name='直通接头', specification='PC6-01', unit='件', product_category='21')
        Item.objects.create(code='DUP-B', name='直通接头', specification='PC6-01', unit='件', product_category='21')
        ambiguous = self.auto_preview(
            project, [['', '上料', '1', '新增', '', '', '', '直通接头', 'PC6-01', '', '', '21', 'SMC', '', '件']]
        )
        self.assertFalse(ambiguous['can_import'])
        self.assertIn('请填写要补品牌的物料编码', str(ambiguous['errors']))

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
        with freeze_today(date(2026, 9, 11)):
            self.assertEqual(CodeRule.generate_code('item', product_category='11'), '1126000001')
            self.assertEqual(CodeRule.generate_code('item', product_category='12'), '1226000001')
            self.assertEqual(CodeRule.generate_code('item', product_category='21'), '2199000001')
        with freeze_today(date(2027, 1, 1)):
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

    def test_deleted_unreferenced_item_releases_drawing_but_keeps_code(self):
        # 管理员删除的误建物料不可见也不能恢复，不应继续占用图号版本；物料编码仍全局唯一（含软删除）。
        data = {
            'name': '安装支架',
            'specification': 'Q235 5mm',
            'product_category': '12',
            'drawing_number': 'DN-PA-1',
            'drawing_revision': 'A',
        }
        created = self.post('purchaser', 'items/', data, status=201)
        self.post('admin', 'record-deletions/', {'resource': 'items', 'ids': [created['id']], 'reason': '误建'})
        self.assertTrue(Item.all_objects.get(pk=created['id']).is_deleted)
        recreated = self.post(
            'purchaser', 'items/', {**data, 'drawing_number': 'dn-pa-1', 'drawing_revision': 'a'}, status=201
        )
        deleted_code = Item.all_objects.get(pk=created['id']).code
        self.assertNotEqual(Item.objects.get(pk=recreated['id']).code, deleted_code)
        # 停用但未删除的物料仍占用图号，提示复用。
        Item.objects.filter(pk=recreated['id']).update(is_active=False)
        rejected = self.post('purchaser', 'items/', {**data, 'name': '另一支架'}, status=400)
        self.assertIn('drawing_number', rejected)
        rejected = self.post('purchaser', 'items/', {'name': '误建编码', 'code': deleted_code}, status=400)
        self.assertIn('code', rejected)
        # 物料导入与 BOM 物料导入沿用同一判重：再删除后可按同一图号版本重建。
        self.post('admin', 'record-deletions/', {'resource': 'items', 'ids': [recreated['id']], 'reason': '误建'})
        content = (
            '物料编码,物料名称,规格,图号,图档版本,产品编码类别,品牌,物料类别,单位,独立建码原因\n'
            ',安装支架,Q235 5mm,DN-PA-1,A,有图·钣金,,,件,\n'
        )
        response = self.clients['purchaser'].post(
            '/api/business/items/import-file/',
            {'file': SimpleUploadedFile('items.csv', content.encode())},
            format='multipart',
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data['can_import'], response.data)
        project = self.active_project()
        row = ['', '', '1', '新增', '', '', '', '安装支架', 'Q235 5mm', 'DN-PA-1', 'A', '12', '', '', '件']
        preview = self.auto_preview(project, [row])
        self.assertTrue(preview['can_import'], preview)
        self.post('manager', f'projects/{project.pk}/bom-import-confirm/', {'token': preview['token']})
        imported = Item.objects.get(drawing_number='DN-PA-1')
        self.assertEqual(BOMLine.objects.get(project=project).item, imported)
        self.assertEqual(Item.all_objects.filter(drawing_number__iexact='DN-PA-1').count(), 3)

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
