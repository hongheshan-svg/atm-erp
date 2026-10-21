import csv
import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from openpyxl import Workbook
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.models import User
from apps.business.models import Entry, Task
from apps.business.services import transfers
from apps.core.api import Conflict
from apps.core.models import ActionReceipt, AuditLog

from .test_commercial_chain import TODAY, BusinessFixtures


class ImportDedupTests(BusinessFixtures, TestCase):
    def setUp(self):
        self.setup_business()
        self.project = self.active_project()

    def preview(self, resource, rows, *, actor=None, xlsx=False, legacy=False):
        columns = transfers.LEGACY_SCHEMAS[resource][1] if legacy else transfers.SCHEMAS[resource][1]
        values = [[label for label, _ in columns], *[[row.get(key, '') for _, key in columns] for row in rows]]
        if xlsx:
            book, stream = Workbook(), io.BytesIO()
            for row in values:
                book.active.append(row)
            book.save(stream)
            book.close()
        else:
            stream = io.StringIO()
            csv.writer(stream).writerows(values)
        content = stream.getvalue()
        upload = SimpleUploadedFile(
            'renamed.xlsx' if xlsx else 'rows.csv', content if isinstance(content, bytes) else content.encode()
        )
        return transfers.preview(actor or self.users['admin'], resource, upload)

    def expense(self, **overrides):
        return {'project': self.project.code, 'title': '差旅费用', 'amount': '10', 'due_date': TODAY, **overrides}

    def confirm(self, preview, *, actor=None, resource='entries', **kwargs):
        self.assertTrue(preview['can_import'], preview)
        return transfers.confirm(actor or self.users['admin'], resource, preview['token'], **kwargs)

    def test_success_only_and_same_token_or_request_key_are_idempotent(self):
        before = ActionReceipt.objects.count()
        first = self.preview('entries', [self.expense()])
        self.assertIsNone(first['duplicate_import'])
        self.assertEqual(ActionReceipt.objects.count(), before)
        self.assertIsNone(self.preview('entries', [self.expense()])['duplicate_import'])
        result = self.confirm(first, key='request-one')
        self.assertEqual(self.confirm(first, key='request-two', allow_duplicate=True), result)
        second = self.preview('entries', [self.expense()])
        self.assertTrue(second['duplicate_import'])
        self.assertEqual(self.confirm(second, key='request-one'), result)
        with self.assertRaises(Conflict):
            self.confirm(second, key='request-three')
        self.assertEqual(Entry.objects.filter(kind='expense').count(), 1)
        repeated = self.confirm(second, key='request-three', allow_duplicate=True)
        self.assertNotEqual(repeated['results'], result['results'])
        self.assertEqual(self.confirm(second, key='another-retry'), repeated)
        self.assertEqual(Entry.objects.filter(kind='expense').count(), 2)

    def test_equivalent_formats_headers_order_blanks_whitespace_and_numbers_match(self):
        original = self.preview('entries', [self.expense(title='住宿'), self.expense(title='差旅')])
        self.confirm(original)
        equivalent = self.preview(
            'entries',
            [self.expense(title=' 差旅 ', amount=10.0), {}, self.expense(title='住宿', amount='10.00')],
            xlsx=True,
            legacy=True,
        )
        self.assertTrue(equivalent['can_import'], equivalent)
        self.assertTrue(equivalent['duplicate_import'])
        with self.assertRaises(Conflict):
            self.confirm(equivalent)
        changed = self.preview('entries', [self.expense(title='住宿', amount='11'), self.expense(title='差旅')])
        self.assertIsNone(changed['duplicate_import'])

    def test_business_ownership_and_resource_are_part_of_content(self):
        self.confirm(self.preview('entries', [self.expense()]))
        other = self.active_project()
        another_project = self.preview('entries', [self.expense(project=other.code)])
        self.assertIsNone(another_project['duplicate_import'])
        self.confirm(another_project)
        task = self.preview(
            'tasks', [{'project': self.project.code, 'kind': 'design', 'title': '差旅费用', 'assignee': 'manager'}]
        )
        self.assertIsNone(task['duplicate_import'])

    def test_purchase_group_labels_enum_aliases_and_numeric_cells_are_normalized(self):
        row = {
            'project': self.project.code,
            'supplier': self.supplier.code,
            'due_date': TODAY,
            'group': 'A',
            'item': self.item.code,
            'quantity': '2.000',
            'unit_price': '10.00',
            'payment_term': '月结30天',
        }
        self.confirm(self.preview('purchases', [row]), resource='purchases')
        second = self.preview(
            'purchases',
            [
                {
                    **row,
                    'group': 'renamed',
                    'quantity': 2,
                    'unit_price': 10,
                    'payment_term': 'month30',
                    'payment_days': '30',
                }
            ],
            xlsx=True,
            legacy=True,
        )
        self.assertTrue(second['can_import'], second)
        self.assertTrue(second['duplicate_import'])

    def test_people_aliases_and_default_time_owner_are_normalized(self):
        task = Task.objects.create(project=self.project, title='设计', kind='design', assignee=self.users['manager'])
        row = {'task': str(task.pk), 'date': TODAY, 'hours': '1', 'reason': '设计'}
        self.users['manager'].display_name = '项目经理'
        self.users['manager'].save()
        first = self.preview('time', [row], actor=self.users['manager'])
        self.confirm(first, resource='time', actor=self.users['manager'])
        equivalent = self.preview(
            'time', [{**row, 'user': '项目经理（manager）', 'hours': '1.00'}], actor=self.users['admin']
        )
        self.assertTrue(equivalent['duplicate_import'])
        different_owner = self.preview('time', [row], actor=self.users['admin'])
        self.assertIsNone(different_owner['duplicate_import'])

    def test_other_user_warning_contains_no_receipt_person_or_result_details(self):
        first = self.preview('entries', [self.expense()])
        self.confirm(first)
        other = User.objects.create_user(username='private-operator', display_name='另一财务', role='finance')
        preview = self.preview('entries', [self.expense()], actor=other)
        self.assertEqual(preview['duplicate_import'], {'message': transfers.DUPLICATE_MESSAGE})
        self.assertNotIn('results', preview)
        with self.assertRaises(ValidationError):
            self.confirm(first, actor=other)

    def test_invalid_preview_or_confirmation_records_no_success_and_rolls_back_earlier_rows(self):
        invalid = self.preview('entries', [self.expense(amount='-1')])
        self.assertFalse(invalid['can_import'])
        self.assertIsNone(invalid['duplicate_import'])
        other = self.active_project()
        rows = [self.expense(), self.expense(project=other.code)]
        good = self.preview('entries', rows)
        other.status = 'closed'
        other.save()
        receipts, audits = ActionReceipt.objects.count(), AuditLog.objects.count()
        with self.assertRaises(ValidationError) as failed:
            self.confirm(good, key='failed-confirmation')
        self.assertIn('rows', failed.exception.detail)
        self.assertIn('error_file', failed.exception.detail)
        self.assertFalse(Entry.objects.filter(kind='expense').exists())
        self.assertEqual((ActionReceipt.objects.count(), AuditLog.objects.count()), (receipts, audits))
        other.status = 'active'
        other.save()
        retry = self.preview('entries', rows)
        self.assertIsNone(retry['duplicate_import'])
        self.confirm(retry)

    def test_same_request_key_with_different_content_is_rejected(self):
        self.confirm(self.preview('entries', [self.expense()]), key='same-key')
        with self.assertRaises(Conflict):
            self.confirm(self.preview('entries', [self.expense(amount='11')]), key='same-key')
        with self.assertRaises(ValidationError):
            self.confirm(self.preview('entries', [self.expense(amount='12')]), allow_duplicate='true')
        self.assertEqual(Entry.objects.filter(kind='expense').count(), 1)

    def test_replay_reauthorizes_project_scope_and_denied_preview_discloses_no_duplicate(self):
        rows = [{'project': self.project.code, 'kind': 'design', 'title': '设计', 'assignee': 'manager'}]
        preview = self.preview('tasks', rows, actor=self.users['manager'])
        self.confirm(preview, resource='tasks', actor=self.users['manager'], key='manager-import')
        self.project.manager = self.users['admin']
        self.project.members.remove(self.users['manager'])
        self.project.save()
        with self.assertRaises(PermissionDenied):
            self.confirm(preview, resource='tasks', actor=self.users['manager'], key='manager-import')
        denied = self.preview('tasks', rows, actor=self.users['manager'])
        self.assertFalse(denied['can_import'])
        self.assertIsNone(denied['duplicate_import'])
