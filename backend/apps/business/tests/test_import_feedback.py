import base64
import csv
import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from openpyxl import Workbook, load_workbook

from apps.business.models import BOMLine, Item, Task
from apps.business.services import transfers
from apps.business.services.import_guides import BOM_COLUMNS
from apps.core.models import ActionReceipt, CodeRule

from .test_commercial_chain import BusinessFixtures


class ImportFeedbackTests(BusinessFixtures, TestCase):
    def setUp(self):
        self.setup_business()
        self.project = self.active_project()

    def upload(self, path, headers, rows, *, role='admin', xlsx=False):
        if xlsx:
            book = Workbook()
            book.active.append(headers)
            for row in rows:
                book.active.append(row)
            stream = io.BytesIO()
            book.save(stream)
            book.close()
            data = stream.getvalue()
        else:
            stream = io.StringIO()
            writer = csv.writer(stream)
            writer.writerow(headers)
            writer.writerows(rows)
            data = stream.getvalue().encode()
        return self.clients[role].post(
            '/api/business/' + path,
            {
                'file': SimpleUploadedFile('input.xlsx' if xlsx else 'input.csv', data),
            },
            format='multipart',
        )

    def workbook(self, result):
        return load_workbook(io.BytesIO(base64.b64decode(result['error_file']['content'])))

    def reupload(self, path, book):
        stream = io.BytesIO()
        book.save(stream)
        return self.clients['admin'].post(
            '/api/business/' + path,
            {
                'file': SimpleUploadedFile('corrected.xlsx', stream.getvalue()),
            },
            format='multipart',
        )

    def test_wrong_template_identifies_exact_resource_before_resolving_private_rows(self):
        headers = [label for label, _ in transfers.SCHEMAS['tasks'][1]]
        rows = [['任务', '设计', 'unknown-secret-person', '', 'private-project', '']]
        for xlsx in [False, True]:
            result = self.upload('projects/import-file/', headers, rows, xlsx=xlsx)
            self.assertEqual(result.status_code, 400)
            self.assertEqual(result.data['template_hint']['code'], 'tasks')
            self.assertIn('这是项目任务模板', result.data['file'])
            self.assertNotIn('unknown-secret-person', str(result.data))
            self.assertNotIn('private-project', str(result.data))
        self.assertFalse(Task.objects.exists())
        denied = self.upload('projects/import-file/', headers, rows, role='member')
        self.assertEqual(denied.status_code, 403)
        self.assertNotIn('template_hint', denied.data)

    def test_wider_bom_template_in_task_entry_is_recognized_for_xlsx(self):
        result = self.upload('tasks/import-file/', [label for label, _ in BOM_COLUMNS], [], xlsx=True)
        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.data['template_hint']['code'], 'bom')

    def test_opening_inventory_guidance_moves_to_settings_without_expanding_permissions(self):
        headers = [label for label, _ in transfers.SCHEMAS['stocks'][1]]
        result = self.upload('projects/import-file/', headers, [])
        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.data['template_hint']['code'], 'stocks')
        self.assertIn('设置 → 管理员初始化', result.data['template_hint']['entry'])
        allowed = self.clients['admin'].get('/api/business/stocks/import-schema/')
        self.assertEqual(allowed.status_code, 200)
        self.assertIn('设置 → 管理员初始化', allowed.data['entry'])
        denied = self.clients['manager'].get('/api/business/stocks/import-schema/')
        self.assertEqual(denied.status_code, 403)

    def test_error_workbook_preserves_legacy_headers_blanks_and_literal_values_then_revalidates(self):
        path = 'items/import-file/'
        headers = ['物料编码', '名称', '规格', '单位']
        before = ActionReceipt.objects.count()
        counter = CodeRule.objects.get(key='item').counter
        result = self.upload(path, headers, [['0007', '', '=literal text', '件'], [], ['0008', '新物料', '', '件']])
        self.assertEqual(result.status_code, 200, result.data)
        self.assertFalse(result.data['can_import'])
        self.assertIsNone(result.data['token'])
        self.assertEqual([row['row'] for row in result.data['rows']], [2, 4])
        self.assertEqual(Item.objects.count(), 1)
        self.assertEqual(ActionReceipt.objects.count(), before)
        self.assertEqual(CodeRule.objects.get(key='item').counter, counter)
        book = self.workbook(result.data)
        self.assertEqual(book.sheetnames, ['数据'])
        self.assertEqual([cell.value for cell in book.active[1]], headers)
        self.assertEqual(book.active['A2'].value, '0007')
        self.assertEqual(book.active['C2'].value, '=literal text')
        self.assertEqual(book.active['C2'].data_type, 's')
        self.assertIsNotNone(book.active['B2'].comment)
        self.assertEqual(book.active['B3'].value, None)
        book.active['B2'] = '修正物料'
        corrected = self.reupload(path, book)
        book.close()
        self.assertEqual(corrected.status_code, 200, corrected.data)
        self.assertTrue(corrected.data['can_import'], corrected.data)
        self.assertNotIn('error_file', corrected.data)
        self.assertEqual(Item.objects.count(), 1)
        self.post('admin', 'items/import-confirm/', {'token': corrected.data['token']})
        self.assertEqual(Item.objects.get(code='0007').name, '修正物料')

    def test_legacy_bom_failed_rows_remain_visible_and_file_can_be_corrected(self):
        path = f'projects/{self.project.pk}/import-preview/'
        headers = ['物料编码', '数量', '变更说明']
        result = self.upload(path, headers, [[self.item.code, '0', '首版']])
        self.assertEqual(result.status_code, 200, result.data)
        self.assertFalse(result.data['can_import'])
        self.assertEqual(result.data['lines'][0]['row'], 2)
        self.assertEqual(result.data['lines'][0]['quantity'], '0')
        book = self.workbook(result.data)
        self.assertIn('正数', book.active['B2'].comment.text)
        book.active['B2'] = 3
        corrected = self.reupload(path, book)
        book.close()
        self.assertTrue(corrected.data['can_import'], corrected.data)
        self.assertFalse(BOMLine.objects.exists())

    def test_new_bom_errors_do_not_generate_material_codes_and_keep_template_columns(self):
        path = f'projects/{self.project.pk}/import-preview/'
        rows = [['', '装配单元', '2', '首版', '', '', '', '新物料', '', '', '', '21', '', '', '件']]
        counter = CodeRule.objects.get(key='item').counter
        result = self.upload(path, [label for label, _ in BOM_COLUMNS], rows)
        self.assertFalse(result.data['can_import'], result.data)
        self.assertNotIn('token', result.data)
        self.assertEqual(Item.objects.count(), 1)
        self.assertEqual(CodeRule.objects.get(key='item').counter, counter)
        book = self.workbook(result.data)
        self.assertEqual(book.active.max_column, len(BOM_COLUMNS))
        self.assertIsNotNone(book.active['I2'].comment)
        book.active['I2'] = '规格-A'
        corrected = self.reupload(path, book)
        book.close()
        self.assertTrue(corrected.data['can_import'], corrected.data)
        self.assertTrue(corrected.data['token'])
        self.assertEqual(Item.objects.count(), 1)
        self.assertEqual(CodeRule.objects.get(key='item').counter, counter)

    def test_bom_feedback_requires_project_write_scope(self):
        self.users['mechanical_engineer'].roles = ['mechanical_engineer', 'purchaser']
        self.users['mechanical_engineer'].save()
        result = self.upload(
            f'projects/{self.project.pk}/import-preview/',
            ['物料编码', '数量', '变更说明'],
            [[self.item.code, '-1', '']],
            role='mechanical_engineer',
        )
        self.assertIn(result.status_code, [403, 404])
        self.assertNotIn('error_file', result.data)

    def test_resolved_person_is_shown_only_after_row_authorization(self):
        self.users['member'].display_name = '张工'
        self.users['member'].save()
        headers = [label for label, _ in transfers.SCHEMAS['tasks'][1]]
        result = self.upload('tasks/import-file/', headers, [['设计任务', '设计', '张工', '', self.project.code, '']])
        self.assertTrue(result.data['can_import'], result.data)
        self.assertEqual(result.data['rows'][0]['matches']['assignee'], '张工（member）')
        self.assertFalse(Task.objects.exists())

    def test_out_of_scope_row_adds_no_resolved_names_to_preview_or_error_workbook(self):
        self.project.manager = self.users['admin']
        self.project.name = '不可访问的后台项目名称'
        self.project.save()
        self.users['member'].display_name = '后台匹配人员名称'
        self.users['member'].save()
        before = ActionReceipt.objects.count()
        headers = [label for label, _ in transfers.SCHEMAS['tasks'][1]]
        rows = [['设计任务', '设计', 'member', '', self.project.code, '']]
        result = self.upload('tasks/import-file/', headers, rows, role='manager')
        self.assertEqual(result.status_code, 200, result.data)
        self.assertFalse(result.data['can_import'])
        self.assertIsNone(result.data['token'])
        self.assertNotIn('matches', result.data['rows'][0])
        self.assertIn('无权访问', result.data['errors'][0]['message'])
        for name in [self.project.name, self.users['member'].display_name]:
            self.assertNotIn(name, str(result.data))
        book = self.workbook(result.data)
        self.assertEqual(book.sheetnames, ['数据'])
        self.assertEqual([cell.value or '' for cell in book.active[2]], rows[0])
        comments = '\n'.join(cell.comment.text for row in book.active for cell in row if cell.comment)
        self.assertNotIn(self.project.name, comments)
        self.assertNotIn(self.users['member'].display_name, comments)
        book.close()
        self.assertFalse(Task.objects.exists())
        self.assertEqual(ActionReceipt.objects.count(), before)

    def test_mixed_error_workbook_uses_source_cells_not_authorized_display_matches(self):
        self.users['member'].display_name = '后台匹配名称'
        self.users['member'].save()
        headers = [label for label, _ in transfers.SCHEMAS['tasks'][1]]
        rows = [
            ['有效任务', '设计', 'member', '', self.project.code, ''],
            ['', '设计', 'member', '', self.project.code, ''],
        ]
        result = self.upload('tasks/import-file/', headers, rows)
        self.assertEqual(result.status_code, 200, result.data)
        self.assertFalse(result.data['can_import'])
        self.assertIsNone(result.data['token'])
        self.assertEqual(result.data['rows'][0]['matches']['assignee'], '后台匹配名称（member）')
        self.assertNotIn('matches', result.data['rows'][1])
        book = self.workbook(result.data)
        self.assertEqual(book.sheetnames, ['数据'])
        for index, source in enumerate(rows, 2):
            self.assertEqual([cell.value or '' for cell in book.active[index]], source)
        comments = '\n'.join(cell.comment.text for row in book.active for cell in row if cell.comment)
        self.assertNotIn('后台匹配名称', comments)
        book.close()
        self.assertFalse(Task.objects.exists())
