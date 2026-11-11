import csv
import io
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier
from unittest.mock import patch

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


class TaskCompletionDateTests(ExecutionFixtures, TestCase):
    def setUp(self):
        self.setup_execution()
        self.project = self.active_project()
        self.project.members.add(self.users['production_manager'])
        self.project.task_supervisors = {'production': self.users['production_manager'].pk}
        self.project.save(update_fields=['task_supervisors'])

    def detail(self, task):
        response = self.clients['member'].get(f'/api/business/tasks/{task.pk}/')
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def test_start_counts_inclusive_days_and_variance_without_labor_cost(self):
        task = self.task(self.project)
        Task.objects.filter(pk=task.pk).update(due_date='2026-09-08')
        key = str(uuid.uuid4())
        data = {'started_date': '2026-09-01', 'reason': '补录实际开始'}
        self.post('manager', f'tasks/{task.pk}/start/', data, key=key)
        self.post('manager', f'tasks/{task.pk}/start/', data, key=key)
        self.post('manager', f'tasks/{task.pk}/start/', data, status=409)
        current = self.detail(task)
        self.assertEqual((current['elapsed_days'], current['schedule_variance_days']), (9, 1))
        self.assertEqual(AuditLog.objects.filter(operation='task.start').count(), 1)
        self.post('manager', f'tasks/{task.pk}/complete/', {'completed_date': '2026-09-07', 'reason': '提前完成'})
        current = self.detail(task)
        self.assertEqual((current['elapsed_days'], current['schedule_variance_days']), (7, -1))
        self.assertFalse(TimeEntry.objects.exists())
        self.post('manager', f'tasks/{task.pk}/reopen/', {'reason': '返工'})
        current = self.detail(task)
        self.assertEqual(current['started_date'], '2026-09-01')
        self.assertEqual(current['elapsed_days'], 9)
        self.assertIsNone(current['completed_date'])

    def test_same_day_missing_dates_and_cancelled_tasks(self):
        task = self.task(self.project)
        self.assertIsNone(self.detail(task)['elapsed_days'])
        self.post(
            'manager',
            f'tasks/{task.pk}/complete/',
            {'started_date': '2026-09-09', 'completed_date': '2026-09-09', 'reason': '当天完成'},
        )
        self.assertEqual(self.detail(task)['elapsed_days'], 1)
        self.assertIsNone(self.detail(task)['schedule_variance_days'])
        self.post('manager', f'tasks/{task.pk}/cancel/', {'reason': '退出计划'})
        self.assertIsNone(self.detail(task)['elapsed_days'])
        self.assertIsNone(self.detail(task)['schedule_variance_days'])
        old = self.task(self.project, title='历史任务')
        self.complete(old)
        self.assertIsNone(self.detail(old)['elapsed_days'])
        self.post(
            'manager',
            f'tasks/{old.pk}/start-date/',
            {'started_date': '2026-09-02', 'expected_started_date': None, 'reason': '历史开工日期补录'},
        )
        self.assertEqual(self.detail(old)['elapsed_days'], 8)

    def test_invalid_start_and_completion_are_atomic(self):
        task = self.task(self.project)
        before = (AuditLog.objects.count(), ActionReceipt.objects.count())
        for value in ('2026-09-10', 'invalid', None):
            self.post('manager', f'tasks/{task.pk}/start/', {'started_date': value, 'reason': '无效'}, status=400)
        self.post(
            'manager',
            f'tasks/{task.pk}/complete/',
            {'started_date': '2026-09-09', 'completed_date': '2026-09-08', 'reason': '日期倒置'},
            status=400,
        )
        task.refresh_from_db()
        self.assertIsNone(task.started_date)
        self.assertIsNone(task.started_at)
        self.assertEqual(task.status, 'open')
        self.assertEqual((AuditLog.objects.count(), ActionReceipt.objects.count()), before)
        self.post('manager', f'tasks/{task.pk}/start/', {'started_date': '2026-09-08', 'reason': '开工'})
        self.post(
            'manager',
            f'tasks/{task.pk}/complete/',
            {'completed_date': '2026-09-07', 'reason': '不能早于开工'},
            status=400,
        )
        self.post(
            'manager',
            f'tasks/{task.pk}/complete/',
            {'started_date': '2026-09-01', 'reason': '不能偷偷覆盖开工'},
            status=409,
        )

    def test_start_permissions_and_manager_correction_keep_history(self):
        task = self.task(self.project)
        for role in ('production_manager', 'purchaser'):
            self.post(role, f'tasks/{task.pk}/start/', {'started_date': '2026-09-08', 'reason': '越权'}, status=403)
        self.post('manager', f'tasks/{task.pk}/start/', {'started_date': '2026-09-08', 'reason': '开工'})
        task.refresh_from_db()
        submitted_at = task.started_at
        change = {'started_date': '2026-09-07', 'expected_started_date': '2026-09-08', 'reason': '核对更正'}
        self.post('member', f'tasks/{task.pk}/start-date/', change, status=403)
        self.post('manager', f'tasks/{task.pk}/start-date/', change)
        self.post('manager', f'tasks/{task.pk}/start-date/', change, status=409)
        task.refresh_from_db()
        self.assertEqual(task.started_at, submitted_at)
        self.assertEqual(AuditLog.objects.get(operation='task.start-date').detail['before'], '2026-09-08')
        assembly = self.task(self.project, 'assembly')
        self.post(
            'production_manager',
            f'tasks/{assembly.pk}/start/',
            {'started_date': '2026-09-08', 'reason': '参与项目生产管理'},
        )
        self.project.members.remove(self.users['member'])
        self.post(
            'member', f'tasks/{assembly.pk}/start/', {'started_date': '2026-09-08', 'reason': '已退出项目'}, status=404
        )

    def test_business_nodes_cannot_be_manually_started(self):
        from apps.business.models import Delivery

        node = Task.objects.create(
            project=self.project,
            kind='shipping',
            milestone='shipping_dispatch',
            title='发货汇总',
            assignee=self.users['member'],
        )
        self.post(
            'manager', f'tasks/{node.pk}/start/', {'started_date': '2026-09-08', 'reason': '不能手动'}, status=409
        )
        delivery = Delivery.objects.create(
            code='START-DATE', project=self.project, quantity=1, shipped_date='2026-09-08'
        )
        install = Task.objects.create(
            project=self.project, delivery=delivery, kind='install', title='安装', assignee=self.users['member']
        )
        self.post(
            'manager', f'tasks/{install.pk}/start/', {'started_date': '2026-09-07', 'reason': '早于发货'}, status=400
        )
        self.post('manager', f'tasks/{install.pk}/start/', {'started_date': '2026-09-08', 'reason': '安装开工'})

    def test_started_tasks_preserve_existing_time_cost_and_cannot_be_deleted_as_unused(self):
        task = self.task(self.project)
        self.time(task, '2')
        original = list(TimeEntry.objects.values('id', 'hours', 'cost', 'hourly_cost'))
        self.post('manager', f'tasks/{task.pk}/start/', {'started_date': '2026-09-08', 'reason': '补录开工'})
        self.post(
            'admin', 'record-deletions/', {'resource': 'tasks', 'ids': [task.pk], 'reason': '未结束不可删'}, status=409
        )
        self.complete(task)
        self.assertEqual(list(TimeEntry.objects.values('id', 'hours', 'cost', 'hourly_cost')), original)
        new = self.task(self.project, title='仅开始没有工时')
        self.post('manager', f'tasks/{new.pk}/start/', {'started_date': '2026-09-09', 'reason': '开工'})
        self.post('admin', 'record-deletions/', {'resource': 'tasks', 'ids': [new.pk], 'reason': '已开工'}, status=409)
        self.post('manager', f'tasks/{new.pk}/cancel/', {'reason': '无需继续'})
        self.post('admin', 'record-deletions/', {'resource': 'tasks', 'ids': [new.pk], 'reason': '取消后归档'})
        self.assertTrue(Task.objects.filter(pk=new.pk).exists())

    def test_completion_keeps_actual_date_separate_from_submission_and_cost(self):
        task = self.task(self.project)
        key = str(uuid.uuid4())
        data = {'completed_date': '2026-09-08', 'reason': '补录昨天实际完成'}
        self.post('manager', f'tasks/{task.pk}/complete/', data, key=key)
        task.refresh_from_db()
        self.assertEqual(task.completed_date, date(2026, 9, 8))
        self.assertIsNotNone(task.completed_at)
        submitted_at = task.completed_at
        self.post('manager', f'tasks/{task.pk}/complete/', data, key=key)
        task.refresh_from_db()
        self.assertEqual(task.completed_at, submitted_at)
        self.assertEqual(AuditLog.objects.filter(operation='task.complete', resource=f'task:{task.pk}').count(), 1)
        self.assertFalse(TimeEntry.objects.exists())
        response = self.clients['member'].get(f'/api/business/tasks/{task.pk}/')
        self.assertEqual(response.data['completed_date'], '2026-09-08')
        exported = self.clients['member'].get('/api/business/tasks/export/?file_format=csv')
        self.assertEqual(exported.status_code, 200)
        csv_rows = list(csv.DictReader(io.StringIO(exported.content.decode('utf-8-sig'))))
        self.assertIn('计划完成日期', csv_rows[0])
        self.assertEqual(csv_rows[0]['实际完成日期'], '2026-09-08')
        self.post('manager', f'tasks/{task.pk}/reopen/', {'reason': '补充设计'})
        task.refresh_from_db()
        self.assertIsNone(task.completed_date)
        self.assertIsNone(task.completed_at)

    def test_invalid_date_permission_and_rollback(self):
        task = self.task(self.project)
        before = (AuditLog.objects.count(), ActionReceipt.objects.count())
        for value in ('2026-09-10', '2026/09/09', '', None):
            self.post('manager', f'tasks/{task.pk}/complete/', {'completed_date': value, 'reason': '无效'}, status=400)
        self.post('production_manager', f'tasks/{task.pk}/complete/', {'reason': '设计无权限'}, status=403)
        task.refresh_from_db()
        self.assertEqual(task.status, 'open')
        self.assertIsNone(task.completed_date)
        self.assertEqual((AuditLog.objects.count(), ActionReceipt.objects.count()), before)

    def test_manager_backfill_and_correction_preserve_submission_time_and_audit(self):
        task = self.task(self.project)
        self.complete(task)
        task.refresh_from_db()
        submitted_at = task.completed_at
        Task.objects.filter(pk=task.pk).update(completed_date=None)
        data = {'completed_date': '2026-09-08', 'expected_completed_date': None, 'reason': '核对交付图档补录'}
        for role in ('member', 'production_manager'):
            self.post(role, f'tasks/{task.pk}/completion-date/', data, status=403)
        self.post('manager', f'tasks/{task.pk}/completion-date/', data)
        self.post('manager', f'tasks/{task.pk}/completion-date/', {**data, 'completed_date': '2026-09-07'}, status=409)
        task.refresh_from_db()
        self.assertEqual(task.completed_date, date(2026, 9, 8))
        self.assertEqual(task.completed_at, submitted_at)
        log = AuditLog.objects.get(operation='task.completion-date', resource=f'task:{task.pk}')
        self.assertEqual(log.detail['after'], '2026-09-08')
        self.assertIsNone(log.detail['before'])
        self.assertFalse(TimeEntry.objects.exists())

    def test_migration_backfills_only_actual_business_dates(self):
        from importlib import import_module
        from types import SimpleNamespace

        from django.apps import apps
        from django.db import connection

        from apps.business.models import Delivery

        task = self.task(self.project)
        self.complete(task)
        Task.objects.filter(pk=task.pk).update(completed_date=None)
        delivery = Delivery.objects.create(
            code='HISTORY-DATE', project=self.project, quantity=1, shipped_date='2026-09-07', accepted_date='2026-09-08'
        )
        acceptance = Task.objects.create(
            project=self.project,
            delivery=delivery,
            kind='acceptance',
            title='历史验收',
            status='done',
            assignee=self.users['manager'],
        )
        import_module('apps.business.migrations.0024_task_completed_date').restore_business_dates(
            apps, SimpleNamespace(connection=connection)
        )
        task.refresh_from_db()
        acceptance.refresh_from_db()
        self.assertIsNone(task.completed_date)
        self.assertEqual(acceptance.completed_date, date(2026, 9, 8))

    def test_install_and_automatic_nodes_use_business_dates(self):
        from apps.business.models import Delivery

        self.project.status = 'delivering'
        self.project.save()
        delivery = Delivery.objects.create(code='DATE-DEL', project=self.project, quantity=1, shipped_date='2026-09-07')
        install = Task.objects.create(
            project=self.project, delivery=delivery, kind='install', title='安装', assignee=self.users['member']
        )
        acceptance = Task.objects.create(
            project=self.project, delivery=delivery, kind='acceptance', title='验收', assignee=self.users['manager']
        )
        for code in AUTOMATIC:
            Task.objects.create(
                project=self.project, kind='site', milestone=code, title=code, assignee=self.users['manager']
            )
        self.post(
            'manager',
            f'tasks/{install.pk}/complete/',
            {'completed_date': '2026-09-06', 'reason': '早于发货'},
            status=400,
        )
        self.post('manager', f'tasks/{install.pk}/complete/', {'completed_date': '2026-09-08', 'reason': '安装确认'})
        self.assertEqual(self.project.tasks.get(milestone='shipping_dispatch').completed_date, date(2026, 9, 7))
        self.assertEqual(self.project.tasks.get(milestone='site_install').completed_date, date(2026, 9, 8))
        self.post(
            'manager', f'deliveries/{delivery.pk}/accept/', {'date': '2026-09-07', 'reason': '早于安装'}, status=400
        )
        self.post('manager', f'deliveries/{delivery.pk}/accept/', {'date': '2026-09-09', 'reason': '客户确认'})
        acceptance.refresh_from_db()
        self.assertEqual(acceptance.completed_date, date(2026, 9, 9))
        self.assertEqual(self.project.tasks.get(milestone='site_acceptance').completed_date, date(2026, 9, 9))
        self.post(
            'manager',
            f'tasks/{acceptance.pk}/completion-date/',
            {'completed_date': '2026-09-08', 'reason': '不可改'},
            status=409,
        )


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

    def test_only_cancel_and_reopen_resync_automatic_nodes(self):
        task = self.task(self.project)
        url = f'tasks/{task.pk}/'
        with patch('apps.business.services.milestones.sync_milestones') as sync:
            # 计划日期和人员不影响按交付事实汇总的自动节点，改期、重新分配不再重算并锁定这些节点。
            self.post('manager', url + 'reschedule/', {'due_date': '2026-12-01', 'reason': '客户推迟'})
            self.post('manager', url + 'assign/', {'assignee': self.users['manager'].pk, 'reason': '换人'})
            sync.assert_not_called()
            self.post('manager', url + 'cancel/', {'reason': '退出计划'})
            self.post('manager', url + 'reopen/', {'reason': '恢复计划'})
        self.assertEqual(sync.call_count, 2)

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
        # 尚未生成的模板节点数供「补充里程碑节点（缺 N 个）」使用。
        self.assertEqual(
            report['missing'],
            20 - len(set(self.project.tasks.exclude(milestone='').values_list('milestone', flat=True))),
        )

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
        # 阶段卡与阶段筛选同一口径：客户终验收阶段计入两批的安装、验收任务（20 个节点 + 4 个批次任务）。
        self.assertEqual(sum(stage['total'] for stage in report['stages']), 24)
        self.assertEqual(sum(stage['done'] for stage in report['stages']), 24)
        stages = {stage['key']: stage for stage in report['stages']}
        self.assertEqual((stages['shipping']['shipped'], stages['shipping']['equipment']), (2, 2))
        self.assertEqual(report['missing'], 0)
        final_stage = self.get('member', f'?project={self.project.pk}&phase=site')
        self.assertEqual(final_stage['count'], 7)
        self.assertEqual(stages['site']['total'], final_stage['count'])
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

    def test_coexecutor_needs_explicit_supervisor_before_confirmation_and_hours(self):
        task = self.shared_task()
        self.post('production_manager', f'tasks/{task.pk}/complete/', {'reason': '仅执行人'}, status=403)
        self.project.task_supervisors = {'mechanical': self.users['production_manager'].pk}
        self.project.save(update_fields=['task_supervisors'])
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
                'reason': '主管按人员代记设计',
                'user': self.users['member'].pk,
            },
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
        self.assertEqual(TimeEntry.objects.filter(task=task).count(), 2)
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
        self.post('member', f'tasks/{task.pk}/complete/', {'reason': '员工只读'}, status=403)
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
        self.post('manager', f'tasks/{auto.pk}/complete/', {'reason': '不能手动完成'}, status=409)
        self.post(
            'manager',
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

    def test_supervisor_time_import_rechecks_assignment_at_confirmation(self):
        task = self.shared_task()
        self.project.task_supervisors = {'mechanical': self.users['production_manager'].pk}
        self.project.save(update_fields=['task_supervisors'])
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
        self.project.task_supervisors = {}
        self.project.save(update_fields=['task_supervisors'])
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
        self.project.task_supervisors = {'mechanical': self.users['production_manager'].pk}
        self.project.save(update_fields=['task_supervisors'])
        self.post('production_manager', 'time/import-confirm/', {'token': token})
        self.assertEqual(TimeEntry.objects.get(task=task).user_id, self.users['production_manager'].pk)


class MilestoneConcurrencyTests(ExecutionFixtures, TransactionTestCase):
    def setUp(self):
        self.setup_execution()

    def test_manager_and_supervisor_start_only_once(self):
        project = self.active_project()
        project.members.add(self.users['production_manager'])
        project.task_supervisors = {'mechanical': self.users['production_manager'].pk}
        project.save(update_fields=['task_supervisors'])
        task = self.task(project)
        task.co_assignees.add(self.users['production_manager'])
        barrier = Barrier(2)

        def start(actor_id):
            close_old_connections()
            try:
                actor = User.objects.get(pk=actor_id)
                barrier.wait(timeout=10)
                try:
                    execution.start_task(
                        actor, str(uuid.uuid4()), task.pk, {'started_date': '2026-09-08', 'reason': '共同开工'}
                    )
                    return 200
                except Conflict:
                    return 409
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(start, [self.users['manager'].pk, self.users['production_manager'].pk]))
        self.assertEqual(sorted(results), [200, 409])
        task.refresh_from_db()
        self.assertEqual(task.started_date, date(2026, 9, 8))
        self.assertEqual(AuditLog.objects.filter(operation='task.start', resource=f'task:{task.pk}').count(), 1)
        self.assertFalse(TimeEntry.objects.exists())

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

    def test_manager_and_supervisor_concurrently_complete_one_shared_task(self):
        project = self.active_project()
        project.members.add(self.users['production_manager'])
        project.task_supervisors = {'mechanical': self.users['production_manager'].pk}
        project.save(update_fields=['task_supervisors'])
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
            results = list(pool.map(complete, [self.users['manager'].pk, self.users['production_manager'].pk]))
        self.assertEqual(sorted(results), [200, 409])
        self.assertEqual(Task.objects.get(pk=task_id).status, 'done')
        self.assertEqual(AuditLog.objects.filter(operation='task.complete', resource=f'task:{task_id}').count(), 1)
