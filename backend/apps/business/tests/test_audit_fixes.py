"""审计修复的行为回归：锁账依据、派工归属、共享库存冲突和附件删除。"""

import tempfile
import uuid
from datetime import timedelta
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.business.models import Document, Entry, Stock
from apps.core.models import Company

from .test_commercial_chain import TODAY, BusinessFixtures


class PeriodLockScopeTests(BusinessFixtures, TestCase):
    def setUp(self):
        self.setup_business()
        Company.objects.create(pk=1)

    def lock(self, through, revision=0):
        response = self.clients['admin'].post(
            '/api/core/company/1/period-lock/',
            {'locked_through': str(through), 'expected_revision': revision, 'reason': '月度核对完成'},
            format='json',
            HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
        )
        self.assertEqual(response.status_code, 200, response.data)

    def age(self, entry):
        # 把款项挪到已锁期间之前建单，模拟「上个月开的单，这个月才退货」。
        Entry.all_objects.filter(pk=entry.pk).update(created_at=timezone.now() - timedelta(days=40))

    def test_todays_credit_on_an_older_payable_is_not_blocked_by_the_cutoff(self):
        project = self.active_project()
        purchase = self.purchase(project)
        entry = Entry.objects.get(purchase=purchase)
        self.age(entry)
        self.lock(timezone.localdate() - timedelta(days=1))
        # 取消未收余量记录的是今天发生的事，锁账依据应是今天而不是原单建单日。
        self.post('purchaser', f'purchases/{purchase.pk}/cancel-remainder/', {'reason': '供应商缺货'})
        entry.refresh_from_db()
        self.assertEqual(entry.credit_amount, Decimal('500.00'))
        self.assertEqual(entry.payments.count(), 0)

    def test_expense_cancelled_today_is_not_blocked_by_the_cutoff(self):
        project = self.active_project()
        expense = self.post(
            'finance',
            'entries/expense/',
            {'project': project.pk, 'title': '外协加工', 'amount': '800', 'due_date': TODAY},
            status=201,
        )
        self.age(Entry.objects.get(pk=expense['id']))
        self.lock(timezone.localdate() - timedelta(days=1))
        self.post('finance', f'entries/{expense["id"]}/cancel-expense/', {'reason': '重复登记'})
        self.assertTrue(Entry.objects.get(pk=expense['id']).cancelled)

    def test_backdated_receipt_is_still_refused_inside_the_locked_period(self):
        # 补录到已锁期间的实际业务日期仍然要拦住，锁账不能整体失效。
        project = self.active_project()
        purchase = self.purchase(project)
        cutoff = timezone.localdate() - timedelta(days=1)
        self.lock(cutoff)
        self.post(
            'warehouse',
            f'purchases/{purchase.pk}/receive/',
            {
                'received_date': str(cutoff),
                'reason': '实际到货',
                'lines': [{'line': purchase.lines.get().pk, 'quantity': '1'}],
            },
            status=409,
        )


class AssignmentScopeTests(BusinessFixtures, TestCase):
    def setUp(self):
        self.setup_business()
        self.project = self.active_project()

    def task_payload(self, assignee):
        return {
            'project': self.project.pk,
            'kind': 'design',
            'title': '机械总装图',
            'assignee': assignee.pk,
            'due_date': TODAY,
        }

    def test_outsider_assignment_names_the_person_and_the_field(self):
        outsider = self.users['electrical_engineer']
        response = self.clients['manager'].post(
            '/api/business/tasks/',
            self.task_payload(outsider),
            format='json',
            HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
        )
        # 报错要指向 assignee 字段和被指派人，而不是让操作者以为自己没权限。
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn('assignee', response.data)
        self.assertIn('不是该项目的负责人或成员', str(response.data['assignee']))
        self.assertNotIn('无权访问此项目', str(response.data))

    def test_member_and_cross_project_roles_remain_assignable(self):
        self.post('manager', 'tasks/', self.task_payload(self.users['member']), status=201)
        self.post('manager', 'tasks/', {**self.task_payload(self.users['purchaser']), 'kind': 'assembly'}, status=201)

    def test_time_logged_for_an_outsider_reports_the_person_field(self):
        task = self.post('manager', 'tasks/', self.task_payload(self.users['member']), status=201)
        response = self.clients['manager'].post(
            f'/api/business/tasks/{task["id"]}/time/',
            {'user': self.users['electrical_engineer'].pk, 'date': TODAY, 'hours': '2', 'reason': '协助调试'},
            format='json',
            HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
        )
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn('user', response.data)


class SharedStockVisibilityTests(BusinessFixtures, TestCase):
    def setUp(self):
        self.setup_business()

    def bom(self, project, quantity):
        self.post(
            'manager',
            f'projects/{project.pk}/revise-bom/',
            {
                'expected_revision': self.bom_version(project.pk),
                'lines': [{'item': self.item.pk, 'quantity': quantity}],
            },
        )

    def first_line(self, project):
        response = self.clients['purchaser'].get(f'/api/business/projects/{project.pk}/demand/')
        self.assertEqual(response.status_code, 200, response.data)
        return response.data['lines'][0]

    def test_demand_exposes_what_other_running_projects_still_need(self):
        mine, other = self.active_project(), self.active_project()
        self.bom(mine, '4.000')
        self.bom(other, '4.000')
        line = self.first_line(mine)
        self.assertEqual(Decimal(line['other_demand']), Decimal('4'))
        self.assertEqual(line['other_projects'], 1)
        # 对方领走的部分不再算作竞争需求。
        self.post(
            'admin', 'stocks/opening/', {'item': self.item.pk, 'quantity': '10', 'unit_cost': '10', 'reason': '期初'}
        )
        stock = Stock.objects.get(item=self.item)
        self.post(
            'warehouse',
            'stocks/issue/',
            {'project': other.pk, 'stock': stock.pk, 'quantity': '3', 'reason': '装配领料'},
        )
        self.assertEqual(Decimal(self.first_line(mine)['other_demand']), Decimal('1'))

    def test_closed_and_own_project_demand_is_not_counted_as_competition(self):
        mine = self.active_project()
        self.bom(mine, '2.000')
        self.assertEqual(Decimal(self.first_line(mine)['other_demand']), Decimal('0'))
        self.assertEqual(self.first_line(mine)['other_projects'], 0)


class DocumentRemovalTests(BusinessFixtures, TestCase):
    def setUp(self):
        self.setup_business()
        self.project = self.active_project()
        self.directory = tempfile.TemporaryDirectory(prefix='lean-remove-test-')
        self.addCleanup(self.directory.cleanup)
        settings = override_settings(MEDIA_ROOT=self.directory.name)
        settings.enable()
        self.addCleanup(settings.disable)

    def upload(self, role='member', category='drawing', name='assembly.pdf'):
        response = self.clients[role].post(
            '/api/business/documents/',
            {'project': self.project.pk, 'category': category, 'file': SimpleUploadedFile(name, b'demo')},
            format='multipart',
            HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
        )
        self.assertEqual(response.status_code, 201, response.data)
        return response.data['id']

    def test_uploader_can_withdraw_a_wrong_file_and_others_cannot(self):
        document = self.upload()
        listing = self.clients['member'].get(f'/api/business/documents/?project={self.project.pk}').data['results']
        self.assertTrue(next(row for row in listing if row['id'] == document)['can_remove'])
        # 仓管能看到这个项目的附件，但不是上传者也不是项目经理。
        self.post('warehouse', f'documents/{document}/remove/', {'reason': '误传'}, status=403)
        self.post('member', f'documents/{document}/remove/', {'reason': '传错了分类'})
        self.assertTrue(Document.all_objects.get(pk=document).is_deleted)
        self.assertEqual(self.clients['member'].get(f'/api/business/documents/{document}/').status_code, 404)

    def test_project_manager_can_tidy_up_someone_elses_upload(self):
        document = self.upload()
        self.post('manager', f'documents/{document}/remove/', {'reason': '重复上传'})
        self.assertTrue(Document.all_objects.get(pk=document).is_deleted)

    def test_a_document_backing_a_payment_can_never_be_removed(self):
        receipt = self.upload(role='finance', category='receipt', name='回单.pdf')
        entry = Entry.objects.filter(project=self.project, kind='receivable').first()
        self.post(
            'finance',
            f'entries/{entry.pk}/pay/',
            {'amount': '100', 'date': TODAY, 'reason': '客户回款', 'document': receipt},
        )
        self.post('finance', f'documents/{receipt}/remove/', {'reason': '想换一张'}, status=409)
        self.assertFalse(Document.all_objects.get(pk=receipt).is_deleted)

    def test_removal_requires_a_reason(self):
        document = self.upload()
        self.post('member', f'documents/{document}/remove/', {}, status=400)
