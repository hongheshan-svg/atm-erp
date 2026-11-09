import uuid
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from apps.business.models import Task, TaskNotice, TimeEntry
from apps.core.models import ActionReceipt

from .test_commercial_chain import TODAY, BusinessFixtures


class TaskSupervisionTests(BusinessFixtures, TestCase):
    def setUp(self):
        self.setup_business()
        self.project = self.active_project()
        self.project.members.add(self.users['mechanical_engineer'], self.users['electrical_engineer'])
        self.task = Task.objects.create(
            project=self.project,
            title='3D画图',
            kind='design',
            discipline='mechanical',
            assignee=self.users['member'],
            due_date=TODAY,
        )

    def configure(self, values, *, role='manager', revision=None, status=200):
        self.project.refresh_from_db()
        return self.post(
            role,
            f'projects/{self.project.pk}/task-supervisors/',
            {
                'supervisors': values,
                'expected_revision': self.project.supervisor_revision if revision is None else revision,
                'reason': '专业分工',
            },
            status=status,
        )

    def test_configuration_validates_members_revision_and_permissions(self):
        values = {'mechanical': self.users['mechanical_engineer'].pk}
        self.configure(values, role='member', status=403)
        self.configure({'mechanical': self.users['purchaser'].pk}, status=400)
        self.configure({'unknown': self.users['member'].pk}, status=400)
        self.configure(values)
        self.configure({}, revision=0, status=409)
        self.project.refresh_from_db()
        self.assertEqual(self.project.task_supervisors, values)
        self.assertEqual(self.project.supervisor_revision, 1)
        notice = TaskNotice.objects.get()
        self.assertEqual(notice.recipient_id, self.users['mechanical_engineer'].pk)
        self.post(
            'manager',
            f'projects/{self.project.pk}/edit/',
            {
                'members': [self.users['member'].pk],
                'reason': '不能移除主管',
            },
            status=409,
        )
        self.configure({})
        self.assertEqual(TaskNotice.objects.order_by('pk').last().recipient_id, self.users['manager'].pk)

    def test_only_current_supervisor_can_confirm_and_record_cost_for_actual_worker(self):
        self.configure({'mechanical': self.users['mechanical_engineer'].pk})
        self.users['member'].hourly_cost = 50
        self.users['member'].save()
        for role in ('member', 'electrical_engineer', 'purchaser'):
            self.post(role, f'tasks/{self.task.pk}/complete/', {'reason': '完成'}, status=403)
            self.post(role, f'tasks/{self.task.pk}/time/', {'date': TODAY, 'hours': 3, 'reason': '工作'}, status=403)
        self.post('mechanical_engineer', f'tasks/{self.task.pk}/start/', {'started_date': TODAY, 'reason': '开工'})
        self.post(
            'mechanical_engineer', f'tasks/{self.task.pk}/complete/', {'completed_date': TODAY, 'reason': '核对完成'}
        )
        self.assertFalse(TimeEntry.objects.exists())
        data = {'user': self.users['member'].pk, 'date': TODAY, 'hours': '3', 'reason': '按日核对'}
        key = str(uuid.uuid4())
        receipt = self.post('mechanical_engineer', f'tasks/{self.task.pk}/time/', data, key=key)
        self.assertEqual(self.post('mechanical_engineer', f'tasks/{self.task.pk}/time/', data, key=key), receipt)
        entry = TimeEntry.objects.get()
        self.assertEqual(entry.user_id, self.users['member'].pk)
        self.assertEqual(entry.created_by_id, self.users['mechanical_engineer'].pk)
        self.assertEqual(entry.cost, Decimal('150'))
        self.post('mechanical_engineer', f'tasks/{self.task.pk}/time/', {**data, 'hours': 22}, status=409)
        self.post('member', f'time/{entry.pk}/amend/', {'hours': 2, 'date': TODAY, 'reason': '修改'}, status=403)
        self.post('mechanical_engineer', f'time/{entry.pk}/amend/', {'hours': 2, 'date': TODAY, 'reason': '更正核对'})
        self.assertEqual(list(TimeEntry.objects.order_by('pk').values_list('hours', flat=True)), [3, -3, 2])
        self.configure({'mechanical': self.users['electrical_engineer'].pk})
        self.post('mechanical_engineer', f'tasks/{self.task.pk}/time/', data, key=key, status=403)
        detail = self.clients['member'].get(f'/api/business/tasks/{self.task.pk}/').data
        self.assertFalse(detail['can_confirm'])
        self.assertFalse(detail['can_record_time'])
        self.assertEqual(detail['logged_hours'], '2.00')
        self.assertEqual(detail['supervisor'], self.users['electrical_engineer'].pk)
        self.assertNotIn('cost', self.clients['electrical_engineer'].get('/api/business/time/').data['results'][0])

    def test_designated_member_does_not_get_dispatch_bom_or_delivery_permissions(self):
        self.configure({'mechanical': self.users['member'].pk})
        self.post('member', f'tasks/{self.task.pk}/complete/', {'reason': '主管核对'})
        self.post('member', f'tasks/{self.task.pk}/reopen/', {'reason': '重开'}, status=403)
        self.post('member', 'tasks/', {'project': self.project.pk}, status=403)
        self.post('member', f'projects/{self.project.pk}/revise-bom/', {}, status=403)
        self.post('member', f'projects/{self.project.pk}/ship/', {}, status=403)
        self.assertFalse(self.clients['member'].get(f'/api/business/tasks/{self.task.pk}/').data['can_manage'])

    def test_manager_fallback_and_automatic_nodes_stay_linked_to_business(self):
        self.post('manager', f'tasks/{self.task.pk}/complete/', {'reason': '经理代管'})
        node = Task.objects.create(
            project=self.project,
            title='发货节点',
            kind='shipping',
            milestone='shipping_dispatch',
            discipline='delivery',
            assignee=self.users['member'],
        )
        self.configure({'delivery': self.users['member'].pk})
        self.post('member', f'tasks/{node.pk}/complete/', {'reason': '不能直接完成'}, status=409)
        self.post('member', f'tasks/{node.pk}/time/', {'date': TODAY, 'hours': 1, 'reason': '不能重复计费'}, status=409)
        self.assertFalse(TimeEntry.objects.exists())

    def test_notices_are_scoped_read_idempotently_and_workbench_targets_supervisor(self):
        self.configure({'mechanical': self.users['mechanical_engineer'].pk})
        notice = TaskNotice.objects.get()
        url = '/api/business/task-notices/'
        head = self.clients['mechanical_engineer'].get(url).data
        self.assertEqual(head['unread_count'], 1)
        self.assertEqual(head['results'][0]['task'], self.task.pk)
        self.assertEqual(self.clients['member'].get(url).data['count'], 0)
        self.post('member', f'task-notices/{notice.pk}/read/', status=404)
        key = str(uuid.uuid4())
        result = self.post('mechanical_engineer', f'task-notices/{notice.pk}/read/', key=key)
        self.assertEqual(self.post('mechanical_engineer', f'task-notices/{notice.pk}/read/', key=key), result)
        self.assertEqual(self.clients['mechanical_engineer'].get(url).data['unread_count'], 0)
        self.assertEqual(self.clients['mechanical_engineer'].get(url, {'unread': 'false'}).data['count'], 1)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, 'open')
        work = self.clients['mechanical_engineer'].get('/api/business/workbench/').data
        self.assertEqual(work['supervised_tasks']['count'], 1)
        tasks = (
            self.clients['mechanical_engineer']
            .get('/api/business/tasks/', {'supervisor': self.users['mechanical_engineer'].pk})
            .data
        )
        self.assertEqual([row['id'] for row in tasks['results']], [self.task.pk])
        self.project.status = 'closed'
        self.project.save(update_fields=['status'])
        self.assertEqual(
            self.clients['mechanical_engineer']
            .get('/api/business/tasks/', {'supervisor': self.users['mechanical_engineer'].pk})
            .data['count'],
            0,
        )
        # 已结项任务仍可从普通列表核对历史，但不占用主管待办/代录入口。
        self.assertEqual(self.clients['mechanical_engineer'].get('/api/business/tasks/').data['count'], 1)
        self.project.members.remove(self.users['mechanical_engineer'])
        self.assertEqual(self.clients['mechanical_engineer'].get(url).data['count'], 0)

    def test_notifications_follow_assignment_and_failed_creation_rolls_back(self):
        self.configure(
            {'mechanical': self.users['mechanical_engineer'].pk, 'electrical': self.users['electrical_engineer'].pk}
        )
        data = {'project': self.project.pk, 'kind': 'design', 'title': '新设计', 'assignee': self.users['member'].pk}
        key = str(uuid.uuid4())
        created = self.post('manager', 'tasks/', data, key=key, status=201)
        self.post('manager', 'tasks/', data, key=key, status=201)
        self.assertEqual(TaskNotice.objects.filter(task_id=created['id']).count(), 1)
        self.post(
            'manager',
            f'tasks/{created["id"]}/assign/',
            {'assignee': self.users['member'].pk, 'discipline': 'electrical', 'reason': '电气接手'},
        )
        notice = TaskNotice.objects.filter(task_id=created['id']).order_by('pk').last()
        self.assertEqual(notice.recipient_id, self.users['electrical_engineer'].pk)
        before = (Task.objects.count(), TaskNotice.objects.count(), ActionReceipt.objects.count())
        with patch(
            'apps.business.services.execution.notify_task', side_effect=RuntimeError('notice storage unavailable')
        ):
            with self.assertRaises(RuntimeError):
                self.post('manager', 'tasks/', {**data, 'title': '事务回滚'}, status=201)
        self.assertEqual(before, (Task.objects.count(), TaskNotice.objects.count(), ActionReceipt.objects.count()))

    def test_notification_does_not_block_deleting_unused_task(self):
        self.configure({'mechanical': self.users['mechanical_engineer'].pk})
        self.post('admin', 'record-deletions/', {'resource': 'tasks', 'ids': [self.task.pk], 'reason': '误建清理'})
        self.assertFalse(Task.objects.filter(pk=self.task.pk).exists())
        self.assertEqual(self.clients['mechanical_engineer'].get('/api/business/task-notices/').data['count'], 0)
