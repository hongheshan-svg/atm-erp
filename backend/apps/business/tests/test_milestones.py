import csv
import io
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections, connections
from django.test import TestCase, TransactionTestCase

from apps.accounts.models import User
from apps.business.services import milestones, transfers
from apps.business.task_milestones import AUTOMATIC, NODES
from apps.core.models import AuditLog

from .test_execution import ExecutionFixtures


class MilestoneTests(ExecutionFixtures, TestCase):
    def setUp(self):
        self.setup_execution()
        self.project = self.active_project(equipment=2)
        self.project.members.add(self.users['production_manager'])

    def rows(self, codes=None):
        return [
            {'milestone': code, 'kind': kind, 'assignee': self.users['member'].pk, 'due_date': '2026-12-20'}
            for code, kind, *_ in NODES
            if codes is None or code in codes
        ]

    def apply(self, rows=None, **kwargs):
        return self.post(
            'manager',
            'tasks/apply-milestones/',
            {
                'project': self.project.pk,
                'lines': self.rows() if rows is None else rows,
            },
            status=201,
            **kwargs,
        )

    def get(self, role, suffix, status=200):
        result = self.clients[role].get('/api/business/tasks/' + suffix)
        self.assertEqual(result.status_code, status, result.data)
        return result.data

    def test_template_is_optional_idempotent_and_preserves_existing_tasks(self):
        old = self.task(self.project, title='已有设计')
        metadata = self.get('member', f'milestone-template/?project={self.project.pk}')
        self.assertEqual(len(metadata['nodes']), 20)
        self.assertEqual(len(metadata['stages']), 6)
        self.assertFalse(metadata['can_generate'])
        key = str(uuid.uuid4())
        first = self.apply(key=key)
        self.assertEqual(first['count'], 20)
        self.assertEqual(self.apply(key=key), first)
        self.assertEqual(self.apply()['count'], 0)
        self.assertEqual(self.project.tasks.count(), 21)
        old.refresh_from_db()
        self.assertEqual((old.title, old.milestone, old.status), ('已有设计', '', 'open'))
        self.assertEqual(self.project.tasks.get(milestone='design_review').title, '3D评审')

    def test_batch_is_atomic_and_rejects_duplicate_or_mismatched_nodes(self):
        before = AuditLog.objects.count()
        bad = self.rows(['design_3d', 'design_review'])
        bad[-1]['assignee'] = User.objects.create_user(username='outside', role='member').pk
        result = self.post('manager', 'tasks/apply-milestones/', {'project': self.project.pk, 'lines': bad}, status=400)
        self.assertIn('lines', result)
        self.assertFalse(self.project.tasks.exists())
        self.assertEqual(AuditLog.objects.count(), before)
        row = self.rows(['design_3d'])[0]
        for rows in [[row, row], [{**row, 'kind': 'purchase'}], []]:
            self.post('manager', 'tasks/apply-milestones/', {'project': self.project.pk, 'lines': rows}, status=400)
            self.assertFalse(self.project.tasks.exists())

    def test_project_scope_and_production_permissions_do_not_expand(self):
        for role in ('member', 'production_manager', 'purchaser'):
            self.post(role, 'tasks/apply-milestones/', {'project': self.project.pk, 'lines': self.rows()}, status=403)
        for kind in ('purchase', 'shipping', 'site', 'design'):
            self.post(
                'production_manager',
                'tasks/',
                {
                    'project': self.project.pk,
                    'kind': kind,
                    'title': '越权任务',
                    'assignee': self.users['member'].pk,
                },
                status=403,
            )
        for kind in ('assembly', 'test'):
            self.post(
                'production_manager',
                'tasks/',
                {
                    'project': self.project.pk,
                    'kind': kind,
                    'title': '允许的任务',
                    'assignee': self.users['member'].pk,
                },
                status=201,
            )
        self.project.members.remove(self.users['member'])
        self.get('member', f'milestone-summary/?project={self.project.pk}', status=403)
        self.get('member', f'milestone-template/?project={self.project.pk}', status=403)

    def test_parallel_completion_reopen_and_deadline_assignment(self):
        self.apply(self.rows(['design_3d', 'purchase_long_lead', 'test_auto']))
        tasks = {task.milestone: task for task in self.project.tasks.all()}
        self.complete(tasks['test_auto'])
        self.complete(tasks['design_3d'])
        self.post('manager', f'tasks/{tasks["design_3d"].pk}/reopen/', {'reason': '设计调整'})
        task = tasks['purchase_long_lead']
        self.post(
            'manager',
            f'tasks/{task.pk}/assign/',
            {
                'assignee': self.users['manager'].pk,
                'due_date': '2026-12-01',
                'reason': '调整计划',
            },
        )
        task.refresh_from_db()
        self.assertEqual((task.assignee_id, task.due_date), (self.users['manager'].pk, date(2026, 12, 1)))
        self.post(
            'manager',
            f'tasks/{task.pk}/assign/',
            {'assignee': self.users['manager'].pk, 'due_date': None, 'reason': '待定'},
        )
        task.refresh_from_db()
        self.assertIsNone(task.due_date)
        self.post('member', f'tasks/{task.pk}/complete/', {'reason': '非本人'}, status=403)
        report = self.get('member', f'milestone-summary/?project={self.project.pk}')
        self.assertEqual(sum(stage['total'] for stage in report['stages']), 3)
        self.assertEqual(sum(stage['done'] for stage in report['stages']), 1)

    def test_single_node_creation_rejects_duplicate_and_wrong_phase(self):
        row = {**self.rows(['design_3d'])[0], 'project': self.project.pk}
        created = self.post('manager', 'tasks/', row, status=201)
        self.post('manager', 'tasks/', row, status=409)
        self.post('manager', 'tasks/', {**row, 'kind': 'shipping'}, status=400)
        detail = self.get('member', str(created['id']) + '/')
        self.assertEqual((detail['stage_label'], detail['milestone_label']), ('设计阶段', '3D画图'))
        self.assertFalse(detail['system_managed'])
        self.assertEqual(self.project.tasks.count(), 1)

    def test_cancelled_node_is_not_duplicated_and_custom_tasks_are_allowed(self):
        self.apply(self.rows(['design_3d']))
        task = self.project.tasks.get()
        self.post('manager', f'tasks/{task.pk}/cancel/', {'reason': '项目不需要'})
        self.assertEqual(self.apply(self.rows(['design_3d']))['count'], 0)
        self.apply([{'kind': 'site', 'title': '客户培训', 'assignee': self.users['member'].pk}])
        self.assertEqual(self.project.tasks.get(milestone='').title, '客户培训')

    def test_actual_deliveries_drive_summary_nodes_and_shipping_gates_remain(self):
        self.apply()
        for task in self.project.tasks.exclude(milestone__in=AUTOMATIC).exclude(milestone='purchase_other'):
            self.complete(task)
        self.post('manager', f'projects/{self.project.pk}/ship/', {'quantity': 1, 'date': '2026-09-09'}, status=409)
        self.complete(self.project.tasks.get(milestone='purchase_other'))
        self.post(
            'manager',
            f'projects/{self.project.pk}/revise-bom/',
            {
                'expected_revision': self.bom_version(self.project.pk),
                'lines': [{'item': self.item.pk, 'quantity': '4'}],
            },
        )
        self.stock_and_issue(self.project)
        for task in self.project.tasks.filter(milestone__in=AUTOMATIC):
            self.complete(task, status=409)
            self.time(task, status=409)
        first = self.deliver(self.project, quantity=1)
        self.accept(first)
        self.assertEqual(self.project.tasks.filter(milestone__in=AUTOMATIC, status='done').count(), 0)
        second = self.deliver(self.project, quantity=1)
        self.assertEqual(self.project.tasks.get(milestone='shipping_dispatch').status, 'done')
        self.post('manager', f'deliveries/{second.pk}/accept/', {'date': '2026-09-09', 'reason': '未安装'}, status=409)
        install = second.tasks.get(kind='install')
        self.post(
            'manager',
            f'tasks/{install.pk}/assign/',
            {
                'assignee': self.users['member'].pk,
                'due_date': '2026-09-08',
                'reason': '不能早于实际发货',
            },
            status=400,
        )
        install.refresh_from_db()
        self.assertIsNone(install.due_date)
        self.complete(install)
        self.assertEqual(self.project.tasks.get(milestone='site_install').status, 'done')
        self.post('manager', f'tasks/{install.pk}/reopen/', {'reason': '现场接线复核'})
        self.assertEqual(self.project.tasks.get(milestone='site_install').status, 'open')
        self.accept(second)
        self.assertEqual(self.project.tasks.filter(milestone__in=AUTOMATIC, status='done').count(), 3)
        node = self.project.tasks.get(milestone='site_acceptance')
        for action in ('cancel', 'reopen'):
            self.post('manager', f'tasks/{node.pk}/{action}/', {'reason': '不能改变实际验收'}, status=409)
        report = self.get('member', f'milestone-summary/?project={self.project.pk}')
        self.assertEqual(sum(stage['total'] for stage in report['stages']), 20)
        self.assertEqual(sum(stage['done'] for stage in report['stages']), 20)
        final_stage = self.get('member', f'?project={self.project.pk}&phase=site')
        self.assertEqual(final_stage['count'], 7)
        self.assertEqual({row['kind'] for row in final_stage['results']}, {'site', 'install', 'acceptance'})
        self.get('member', f'?project={self.project.pk}&phase=unknown', status=400)

    def test_import_supports_new_nodes_and_previous_six_column_template(self):
        columns = transfers.SCHEMAS['tasks'][1]
        for headers, values in [
            (
                [label for label, _ in columns],
                ['长交期跟进', '采购阶段', 'member', '', self.project.code, '', '长交期'],
            ),
            (
                [label for label, _ in transfers.PREVIOUS_TASK_COLUMNS],
                ['旧任务', '设计', 'member', '', self.project.code, ''],
            ),
        ]:
            stream = io.StringIO()
            writer = csv.writer(stream)
            writer.writerow(headers)
            writer.writerow(values)
            upload = SimpleUploadedFile('tasks.csv', stream.getvalue().encode('utf-8-sig'), content_type='text/csv')
            result = self.clients['manager'].post(
                '/api/business/tasks/import-file/', {'file': upload}, format='multipart'
            )
            self.assertEqual(result.status_code, 200, result.data)
            self.assertFalse(result.data.get('errors'), result.data)
            self.post('manager', 'tasks/import-confirm/', {'token': result.data['token']})
        self.assertEqual(self.project.tasks.get(milestone='purchase_long_lead').title, '长交期跟进')
        self.assertEqual(self.project.tasks.get(title='旧任务').milestone, '')


class MilestoneConcurrencyTests(ExecutionFixtures, TransactionTestCase):
    def setUp(self):
        self.setup_execution()

    def test_two_template_requests_create_each_node_only_once(self):
        project = self.active_project()
        actor_id = self.users['manager'].pk
        payload = {
            'project': project.pk,
            'lines': [
                {'kind': kind, 'milestone': code, 'assignee': self.users['member'].pk} for code, kind, *_ in NODES
            ],
        }
        barrier = Barrier(2)

        def apply():
            close_old_connections()
            try:
                actor = User.objects.get(pk=actor_id)
                barrier.wait(timeout=10)
                return milestones.apply_template(actor, str(uuid.uuid4()), payload)
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: apply(), range(2)))
        self.assertEqual(sorted(row['count'] for row in results), [0, 20])
        self.assertEqual(project.tasks.count(), 20)
