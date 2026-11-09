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
from apps.business.models import Task, TimeEntry
from apps.business.services import execution, milestones, transfers
from apps.business.task_milestones import AUTOMATIC, NODES
from apps.core.api import Conflict
from apps.core.models import ActionReceipt, AuditLog

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

    def shared_task(self, **extra):
        people = [self.users['member'].pk, self.users['production_manager'].pk]
        result = self.post(
            'manager',
            'tasks/',
            {
                'project': self.project.pk,
                'kind': 'design',
                'title': '多人评审',
                'assignees': people,
                **extra,
            },
            status=201,
        )
        return Task.objects.get(pk=result['id'])

    def test_all_executors_see_task_workbench_and_progress_without_duplicate_rows(self):
        task = self.shared_task()
        for role in ('member', 'production_manager'):
            person = self.users[role]
            rows = self.get(role, f'?project={self.project.pk}&assignee={person.pk}')
            self.assertEqual(rows['count'], 1)
            row = rows['results'][0]
            self.assertEqual(set(row['assignees']), {self.users['member'].pk, self.users['production_manager'].pk})
            self.assertIn('member', row['assignee_name'])
            self.assertIn('production_manager', row['assignee_name'])
            response = self.clients[role].get('/api/business/workbench/')
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(response.data['tasks']['count'], 1)
            self.assertEqual(response.data['tasks']['results'][0]['id'], task.pk)
        response = self.clients['member'].get(f'/api/business/projects/{self.project.pk}/progress/?category=tasks')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn('production_manager', str(response.data))
        self.assertIn('member', str(response.data))
        found = self.get('manager', f'?project={self.project.pk}&search=production_manager')
        self.assertEqual(found['count'], 1)

    def test_coexecutor_logs_own_time_and_completes_once_without_expanding_management(self):
        task = self.shared_task()
        self.post(
            'production_manager',
            f'tasks/{task.pk}/time/',
            {
                'date': '2026-09-09',
                'hours': '2',
                'reason': '本人设计工作',
            },
        )
        self.assertEqual(TimeEntry.objects.get(task=task).user_id, self.users['production_manager'].pk)
        self.post(
            'production_manager',
            f'tasks/{task.pk}/time/',
            {
                'date': '2026-09-09',
                'hours': '3',
                'reason': '不能代记设计',
                'user': self.users['member'].pk,
            },
            status=403,
        )
        self.post(
            'production_manager',
            f'tasks/{task.pk}/assign/',
            {
                'assignees': [self.users['production_manager'].pk],
                'reason': '无设计管理权限',
            },
            status=403,
        )
        key = str(uuid.uuid4())
        self.post('production_manager', f'tasks/{task.pk}/complete/', {'reason': '共同检查完成'}, key=key)
        self.post('production_manager', f'tasks/{task.pk}/complete/', {'reason': '共同检查完成'}, key=key)
        self.complete(task, status=409)
        task.refresh_from_db()
        self.assertEqual(task.status, 'done')
        self.assertEqual(AuditLog.objects.filter(operation='task.complete', resource=f'task:{task.pk}').count(), 1)
        self.assertEqual(TimeEntry.objects.filter(task=task).count(), 1)
        self.assertEqual(self.clients['member'].get('/api/business/workbench/').data['tasks']['count'], 0)

    def test_shared_names_remain_unambiguous_and_can_be_imported(self):
        for role in ('member', 'production_manager'):
            User.objects.filter(pk=self.users[role].pk).update(display_name='张工')
        task = self.shared_task()
        row = self.get('member', f'{task.pk}/')
        self.assertEqual(row['assignee_name'], '张工（账号：member）；张工（账号：production_manager）')
        resolved = transfers.payload({'assignee': row['assignee_name']})
        self.assertEqual(set(resolved['assignees']), set(row['assignees']))

    def test_reassignment_replaces_group_and_reopen_retains_everyone(self):
        task = self.shared_task()
        self.complete(task)
        self.post('manager', f'tasks/{task.pk}/reopen/', {'reason': '复核'})
        task.refresh_from_db()
        self.assertEqual(len(task.assigned_people()), 2)
        self.post(
            'manager',
            f'tasks/{task.pk}/assign/',
            {
                'assignees': [self.users['manager'].pk],
                'reason': '经理接手',
            },
        )
        self.assertFalse(task.co_assignees.exists())
        self.complete(task, status=403)
        self.post('production_manager', f'tasks/{task.pk}/complete/', {'reason': '已移出'}, status=403)
        self.post('manager', f'tasks/{task.pk}/complete/', {'reason': '完成'})
        self.post(
            'manager',
            f'tasks/{task.pk}/reopen/',
            {
                'assignees': [self.users['member'].pk, self.users['production_manager'].pk],
                'reason': '再次协作',
            },
        )
        task.refresh_from_db()
        self.assertEqual(
            {p.pk for p in task.assigned_people()}, {self.users['member'].pk, self.users['production_manager'].pk}
        )

    def test_multi_assignment_rejects_invalid_people_atomically(self):
        outsider = self.users['electrical_engineer']
        disabled = self.users['production_manager']
        disabled.is_active = False
        disabled.save()
        base = self.users['member'].pk
        counts = (Task.objects.count(), AuditLog.objects.count(), ActionReceipt.objects.count())
        for values in ([], [base, base], [base, outsider.pk], [base, disabled.pk], [base, 999999], 'member'):
            with self.subTest(values=values):
                self.post(
                    'manager',
                    'tasks/',
                    {
                        'project': self.project.pk,
                        'kind': 'design',
                        'title': '非法执行人',
                        'assignees': values,
                    },
                    status=400,
                )
                self.assertEqual(
                    (Task.objects.count(), AuditLog.objects.count(), ActionReceipt.objects.count()), counts
                )
        task = self.task(self.project)
        self.post(
            'manager',
            f'tasks/{task.pk}/assign/',
            {
                'assignees': [self.users['manager'].pk, outsider.pk],
                'reason': '应整体失败',
            },
            status=400,
        )
        task.refresh_from_db()
        self.assertEqual(task.assignee_id, base)
        self.assertFalse(task.co_assignees.exists())

    def test_open_coexecutor_cannot_be_removed_and_automatic_nodes_still_use_facts(self):
        task = self.shared_task(milestone='design_review')
        self.post(
            'manager',
            f'projects/{self.project.pk}/edit/',
            {
                'members': [self.users['member'].pk],
                'reason': '还有共同任务',
            },
            status=409,
        )
        self.assertTrue(self.project.members.filter(pk=self.users['production_manager'].pk).exists())
        auto = self.shared_task(kind='shipping', milestone='shipping_dispatch')
        self.post('production_manager', f'tasks/{auto.pk}/complete/', {'reason': '不能手动完成'}, status=409)
        self.post(
            'production_manager',
            f'tasks/{auto.pk}/time/',
            {
                'date': '2026-09-09',
                'hours': 1,
                'reason': '汇总不能记工时',
            },
            status=409,
        )
        self.project.members.remove(self.users['production_manager'])
        self.post('production_manager', f'tasks/{task.pk}/complete/', {'reason': '已移出项目'}, status=404)

    def test_stage_and_node_order_precedes_pagination_and_export(self):
        self.apply(list(reversed(self.rows())))
        expected = [code for code, *_ in NODES]
        first = self.get('member', f'?project={self.project.pk}&page_size=10&page=1')
        second = self.get('member', f'?project={self.project.pk}&page_size=10&page=2')
        self.assertEqual([row['milestone'] for row in first['results'] + second['results']], expected)
        response = self.clients['manager'].get(f'/api/business/tasks/export/?project={self.project.pk}&file_format=csv')
        self.assertEqual(response.status_code, 200)
        rows = list(csv.reader(io.StringIO(response.content.decode('utf-8-sig'))))
        titles = [title for _, _, title, _ in NODES]
        positions = [next(i for i, row in enumerate(rows) if title in row) for title in titles]
        self.assertEqual(positions, sorted(positions))

    def test_multi_person_import_preview_confirm_and_error_column(self):
        columns = transfers.SCHEMAS['tasks'][1]

        def preview(people):
            stream = io.StringIO()
            writer = csv.writer(stream)
            writer.writerow([label for label, _ in columns])
            writer.writerow(['多人导入', '设计阶段', people, '', self.project.code, '', '3D评审'])
            upload = SimpleUploadedFile('tasks.csv', stream.getvalue().encode('utf-8-sig'), content_type='text/csv')
            result = self.clients['manager'].post(
                '/api/business/tasks/import-file/', {'file': upload}, format='multipart'
            )
            self.assertEqual(result.status_code, 200, result.data)
            return result.data

        bad = preview('member；electrical_engineer')
        self.assertEqual(bad['errors'][0]['fields'], ['assignee'])
        self.assertFalse(self.project.tasks.exists())
        good = preview('member；production_manager')
        self.assertFalse(good.get('errors'), good)
        self.assertFalse(self.project.tasks.exists())
        self.post('manager', 'tasks/import-confirm/', {'token': good['token']})
        task = self.project.tasks.get()
        self.assertEqual(
            {p.pk for p in task.assigned_people()}, {self.users['member'].pk, self.users['production_manager'].pk}
        )

    def test_coexecutor_time_import_rechecks_assignment_at_confirmation(self):
        task = self.shared_task()
        stream = io.StringIO()
        writer = csv.writer(stream)
        writer.writerow([label for label, _ in transfers.SCHEMAS['time'][1]])
        writer.writerow([task.pk, 'production_manager', '2026-09-09', '1.5', '共同执行人工时'])
        upload = SimpleUploadedFile('time.csv', stream.getvalue().encode('utf-8-sig'), content_type='text/csv')
        result = self.clients['production_manager'].post(
            '/api/business/time/import-file/', {'file': upload}, format='multipart'
        )
        self.assertEqual(result.status_code, 200, result.data)
        self.assertFalse(result.data.get('errors'), result.data)
        token = result.data['token']
        self.assertFalse(TimeEntry.objects.filter(task=task).exists())
        self.post(
            'manager',
            f'tasks/{task.pk}/assign/',
            {
                'assignees': [self.users['member'].pk],
                'reason': '预览后交接',
            },
        )
        self.post('production_manager', 'time/import-confirm/', {'token': token}, status=403)
        self.assertFalse(TimeEntry.objects.filter(task=task).exists())
        self.post(
            'manager',
            f'tasks/{task.pk}/assign/',
            {
                'assignees': [self.users['member'].pk, self.users['production_manager'].pk],
                'reason': '恢复协作',
            },
        )
        self.post('production_manager', 'time/import-confirm/', {'token': token})
        self.assertEqual(TimeEntry.objects.get(task=task).user_id, self.users['production_manager'].pk)


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

    def test_two_executors_concurrently_complete_one_shared_task(self):
        project = self.active_project()
        project.members.add(self.users['production_manager'])
        task_id = self.post(
            'manager',
            'tasks/',
            {
                'project': project.pk,
                'kind': 'design',
                'title': '共同确认',
                'assignees': [self.users['member'].pk, self.users['production_manager'].pk],
            },
            status=201,
        )['id']
        barrier = Barrier(2)

        def complete(actor_id):
            close_old_connections()
            try:
                actor = User.objects.get(pk=actor_id)
                barrier.wait(timeout=10)
                try:
                    execution.complete_task(actor, str(uuid.uuid4()), task_id, {'reason': '协作完成'})
                    return 200
                except Conflict:
                    return 409
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(complete, [self.users['member'].pk, self.users['production_manager'].pk]))
        self.assertEqual(sorted(results), [200, 409])
        self.assertEqual(Task.objects.get(pk=task_id).status, 'done')
        self.assertEqual(AuditLog.objects.filter(operation='task.complete', resource=f'task:{task_id}').count(), 1)
