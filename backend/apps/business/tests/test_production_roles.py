import uuid
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.business.models import Delivery, Entry, Task, TimeEntry
from apps.core.models import ActionReceipt, AuditLog

from .test_commercial_chain import BusinessFixtures


class ProductionResponsibilityTests(BusinessFixtures, TestCase):
    def setUp(self):
        self.setup_business()
        self.project = self.active_project()
        self.other_project = self.active_project()
        self.production = self.users['production_manager']
        self.project.members.add(self.production)
        self.today = timezone.localdate()
        self.users['member'].hourly_cost = Decimal('50.00')
        self.users['member'].save()

    def get(self, path, status=200):
        response = self.clients['production_manager'].get('/api/business/' + path)
        self.assertEqual(response.status_code, status, response.data)
        return response.data

    def task(self, kind='assembly', *, project=None, status='open', delivery=None):
        return Task.objects.create(
            project=project or self.project,
            kind=kind,
            title=f'{kind}生产职责验收',
            assignee=self.users['member'],
            status=status,
            completed_at=timezone.now() if status == 'done' else None,
            delivery=delivery,
        )

    def delivery(self, *, accepted=False, expired=False):
        self.project.status = 'warranty' if accepted else 'delivering'
        self.project.save()
        return Delivery.objects.create(
            project=self.project,
            code=f'PROD-DEL-{self.project.pk}',
            quantity=1,
            shipped_date=self.today - timedelta(days=4),
            accepted_date=self.today - timedelta(days=3) if accepted else None,
            warranty_until=self.today + timedelta(days=-1 if expired else 30) if accepted else None,
        )

    def service_data(self, delivery, fee='0'):
        return {
            'delivery': delivery.pk,
            'date': str(self.today),
            'title': '生产经理售后协调',
            'assignee': self.users['member'].pk,
            'fee': fee,
        }

    def test_production_manager_creates_assembly_and_test_tasks_with_stage_prerequisites(self):
        project = self.get(f'projects/{self.project.pk}/')
        self.assertTrue(project['can_manage_production'])
        self.assertFalse(project['can_manage'])
        self.assertFalse(project['can_edit_bom'])
        self.assertNotIn('contract_amount', project)
        design = self.task('design')
        tasks = {}
        for kind in ('assembly', 'test'):
            tasks[kind] = self.post(
                'production_manager',
                'tasks/',
                {
                    'project': self.project.pk,
                    'kind': kind,
                    'title': f'生产新建{kind}',
                    'assignee': self.users['member'].pk,
                },
                status=201,
            )['id']
            detail = self.get(f'tasks/{tasks[kind]}/')
            self.assertTrue(detail['can_manage'])
            self.assertTrue(detail['can_cancel'])
            self.assertFalse(detail['can_reopen'])
        before = ActionReceipt.objects.count()
        self.post('production_manager', f'tasks/{tasks["assembly"]}/complete/', {'reason': '设计尚未完成'}, status=409)
        self.assertEqual(ActionReceipt.objects.count(), before)
        self.post('member', f'tasks/{design.pk}/complete/', {'reason': '设计确认'})
        self.post('production_manager', f'tasks/{tasks["test"]}/complete/', {'reason': '装配尚未完成'}, status=409)
        self.post('production_manager', f'tasks/{tasks["assembly"]}/complete/', {'reason': '装配完毕复核'})
        self.post('production_manager', f'tasks/{tasks["test"]}/complete/', {'reason': '调试完毕复核'})
        self.assertEqual(Task.objects.get(pk=tasks['assembly']).status, 'done')
        self.assertEqual(Task.objects.get(pk=tasks['test']).status, 'done')
        self.post(
            'production_manager', f'tasks/{tasks["assembly"]}/reopen/', {'reason': '不能越过已完成调试'}, status=409
        )

    def test_production_manager_reassigns_cancels_and_reopens_production_tasks_only(self):
        for kind in ('assembly', 'test'):
            with self.subTest(kind=kind):
                task = self.task(kind)
                self.post(
                    'production_manager',
                    f'tasks/{task.pk}/assign/',
                    {'assignee': self.production.pk, 'reason': '生产经理接手协调'},
                )
                task.refresh_from_db()
                self.assertEqual(task.assignee_id, self.production.pk)
                self.post('production_manager', f'tasks/{task.pk}/cancel/', {'reason': '生产计划调整'})
                self.assertEqual(Task.objects.get(pk=task.pk).status, 'cancelled')
                self.assertTrue(self.get(f'tasks/{task.pk}/')['can_reopen'])
                self.post(
                    'production_manager',
                    f'tasks/{task.pk}/reopen/',
                    {'assignee': self.users['member'].pk, 'reason': '恢复生产任务'},
                )
                task.refresh_from_db()
                self.assertEqual(
                    (task.status, task.assignee_id, task.completed_at), ('open', self.users['member'].pk, None)
                )
        for kind in ('design', 'acceptance'):
            with self.subTest(denied_kind=kind):
                task = self.task(kind)
                detail = self.get(f'tasks/{task.pk}/')
                self.assertFalse(detail['can_manage'])
                self.assertFalse(detail['can_cancel'])
                self.assertFalse(detail['can_reopen'])
                before = ActionReceipt.objects.count()
                self.post(
                    'production_manager',
                    f'tasks/{task.pk}/assign/',
                    {'assignee': self.production.pk, 'reason': '不能管理设计验收'},
                    status=403,
                )
                self.post(
                    'production_manager', f'tasks/{task.pk}/complete/', {'reason': '不能代办设计验收'}, status=403
                )
                self.post('production_manager', f'tasks/{task.pk}/cancel/', {'reason': '不能取消设计验收'}, status=403)
                self.assertEqual(ActionReceipt.objects.count(), before)
                self.assertEqual(Task.objects.get(pk=task.pk).status, 'open')
        self.post(
            'production_manager',
            'tasks/',
            {
                'project': self.project.pk,
                'kind': 'design',
                'title': '不能创建设计任务',
                'assignee': self.users['member'].pk,
            },
            status=403,
        )

    def test_production_install_management_cannot_cancel_delivery_or_reverse_acceptance(self):
        delivery = self.delivery()
        install = self.task('install', delivery=delivery)
        acceptance = self.task('acceptance', delivery=delivery)
        self.assertTrue(self.get(f'tasks/{install.pk}/')['can_manage'])
        self.assertFalse(self.get(f'tasks/{install.pk}/')['can_cancel'])
        self.post('production_manager', f'tasks/{install.pk}/cancel/', {'reason': '安装任务随交付保留'}, status=409)
        self.post(
            'production_manager',
            f'tasks/{install.pk}/assign/',
            {'assignee': self.production.pk, 'reason': '安排安装负责人'},
        )
        self.post('production_manager', f'tasks/{install.pk}/complete/', {'reason': '现场安装完成'})
        self.post(
            'production_manager',
            f'deliveries/{delivery.pk}/accept/',
            {'date': str(self.today), 'reason': '生产不能代表验收'},
            status=403,
        )
        self.post(
            'manager', f'deliveries/{delivery.pk}/accept/', {'date': str(self.today), 'reason': '项目经理登记客户验收'}
        )
        self.assertEqual(Task.objects.get(pk=acceptance.pk).status, 'done')
        self.assertFalse(self.get(f'tasks/{install.pk}/')['can_reopen'])
        self.post('production_manager', f'tasks/{install.pk}/reopen/', {'reason': '不能撤回已验收事实'}, status=409)
        delivery.refresh_from_db()
        self.assertEqual(delivery.accepted_date, self.today)

    def test_production_manager_team_hours_amend_preserves_cost_snapshot_and_hides_money(self):
        task = self.task()
        entry_id = self.post(
            'production_manager',
            f'tasks/{task.pk}/time/',
            {'user': self.users['member'].pk, 'date': str(self.today), 'hours': '2', 'reason': '代登记班组实际工时'},
        )['id']
        original = TimeEntry.objects.get(pk=entry_id)
        self.assertEqual(
            (original.hours, original.hourly_cost, original.cost), (Decimal('2'), Decimal('50'), Decimal('100'))
        )
        detail = self.get(f'time/{entry_id}/')
        self.assertTrue(detail['can_amend'])
        self.assertNotIn('hourly_cost', detail)
        self.assertNotIn('cost', detail)
        self.users['member'].hourly_cost = Decimal('90.00')
        self.users['member'].save()
        amended_id = self.post(
            'production_manager',
            f'time/{entry_id}/amend/',
            {'date': str(self.today), 'hours': '3', 'reason': '补齐漏记的一小时'},
        )['id']
        amended = TimeEntry.objects.get(pk=amended_id)
        original.refresh_from_db()
        reversal = TimeEntry.objects.get(reversal_of=original)
        self.assertEqual((original.hours, original.cost), (Decimal('2'), Decimal('100')))
        self.assertEqual((reversal.hours, reversal.cost), (Decimal('-2'), Decimal('-100')))
        self.assertEqual(
            (amended.hours, amended.hourly_cost, amended.cost), (Decimal('3'), Decimal('50'), Decimal('150'))
        )
        self.assertFalse(self.get(f'time/{entry_id}/')['can_amend'])
        self.assertTrue(self.get(f'time/{amended_id}/')['can_amend'])
        self.assertEqual(TimeEntry.objects.filter(task=task).count(), 3)
        design = self.task('design')
        own_design_time = self.post(
            'member', f'tasks/{design.pk}/time/', {'date': str(self.today), 'hours': '1', 'reason': '设计工时'}
        )['id']
        self.assertFalse(self.get(f'time/{own_design_time}/')['can_amend'])
        self.post(
            'production_manager',
            f'time/{own_design_time}/amend/',
            {'date': str(self.today), 'hours': '2', 'reason': '不得更正设计团队工时'},
            status=403,
        )
        self.post(
            'production_manager',
            f'tasks/{design.pk}/time/',
            {'user': self.users['member'].pk, 'date': str(self.today), 'hours': '1', 'reason': '不得代记设计工时'},
            status=403,
        )

    def test_production_manager_can_create_and_cancel_free_in_warranty_service(self):
        delivery = self.delivery(accepted=True)
        self.assertTrue(self.get(f'projects/{self.project.pk}/')['can_register_service'])
        task_id = self.post('production_manager', f'projects/{self.project.pk}/service/', self.service_data(delivery))[
            'id'
        ]
        self.assertFalse(Entry.objects.filter(task_id=task_id).exists())
        self.assertTrue(self.get(f'tasks/{task_id}/')['can_cancel'])
        self.post('production_manager', f'tasks/{task_id}/cancel/', {'reason': '客户暂缓免费维修'})
        self.post('production_manager', f'tasks/{task_id}/reopen/', {'reason': '恢复免费维修'})
        self.post(
            'production_manager',
            f'tasks/{task_id}/assign/',
            {'assignee': self.production.pk, 'reason': '协调免费维修人员'},
        )
        self.post('production_manager', f'tasks/{task_id}/complete/', {'reason': '免费维修完成'})
        self.assertEqual(Task.objects.get(pk=task_id).status, 'done')
        self.assertFalse(Entry.objects.filter(task_id=task_id).exists())
        before = Task.objects.count(), Entry.objects.count(), ActionReceipt.objects.count()
        self.post(
            'production_manager', f'projects/{self.project.pk}/service/', self.service_data(delivery, '100'), status=403
        )
        self.assertEqual((Task.objects.count(), Entry.objects.count(), ActionReceipt.objects.count()), before)

    def test_production_manager_cannot_create_out_of_warranty_service_even_with_zero_fee(self):
        delivery = self.delivery(accepted=True, expired=True)
        before = Task.objects.count(), Entry.objects.count(), ActionReceipt.objects.count()
        for fee in ('100', '0'):
            with self.subTest(fee=fee):
                self.post(
                    'production_manager',
                    f'projects/{self.project.pk}/service/',
                    self.service_data(delivery, fee),
                    status=403,
                )
        self.assertEqual((Task.objects.count(), Entry.objects.count(), ActionReceipt.objects.count()), before)

    def test_charged_service_can_be_assigned_completed_but_financial_cancel_and_reopen_are_denied(self):
        delivery = self.delivery(accepted=True, expired=True)
        task_id = self.post('manager', f'projects/{self.project.pk}/service/', self.service_data(delivery, '100'))['id']
        entry = Entry.objects.get(task_id=task_id)
        self.assertEqual(entry.amount, 100)
        detail = self.get(f'tasks/{task_id}/')
        self.assertTrue(detail['can_manage'])
        self.assertFalse(detail['can_cancel'])
        self.post(
            'production_manager',
            f'tasks/{task_id}/assign/',
            {'assignee': self.production.pk, 'reason': '协调已收费维修'},
        )
        self.post('production_manager', f'tasks/{task_id}/complete/', {'reason': '现场维修完成'})
        self.assertFalse(self.get(f'tasks/{task_id}/')['can_reopen'])
        before = ActionReceipt.objects.count(), AuditLog.objects.count()
        self.post('production_manager', f'tasks/{task_id}/cancel/', {'reason': '不得自动抵减售后款'}, status=403)
        self.post('production_manager', f'tasks/{task_id}/reopen/', {'reason': '不得重置收费事实'}, status=403)
        entry.refresh_from_db()
        self.assertEqual((entry.amount, entry.credit_amount, entry.cancelled), (Decimal('100'), Decimal('0'), False))
        self.assertEqual((ActionReceipt.objects.count(), AuditLog.objects.count()), before)
        self.post('manager', f'tasks/{task_id}/cancel/', {'reason': '项目经理确认取消并抵减收费'})
        entry.refresh_from_db()
        self.assertEqual((entry.credit_amount, entry.cancelled), (Decimal('100'), True))
        self.post('production_manager', f'tasks/{task_id}/reopen/', {'reason': '不得恢复已抵减的售后款'}, status=403)
        entry.refresh_from_db()
        self.assertEqual((entry.credit_amount, entry.cancelled), (Decimal('100'), True))

    def test_production_role_cannot_manage_project_budget_bom_purchase_approval_or_finance(self):
        purchase = self.purchase(self.project, approve=False)
        for path in (
            'sales/',
            'entries/',
            'payments/',
            'reconciliations/',
            'bank-records/',
            'reports/',
            f'projects/{self.project.pk}/cost/',
            f'projects/{self.project.pk}/cost-analysis/',
            f'projects/{self.project.pk}/cost-sources/',
        ):
            with self.subTest(path=path):
                self.get(path, status=403)
        before = ActionReceipt.objects.count()
        for path, payload in (
            (f'projects/{self.project.pk}/cancel/', {'reason': '生产不能取消项目'}),
            (
                f'projects/{self.project.pk}/budget/',
                {
                    'materials': '100',
                    'labor': '100',
                    'expenses': '100',
                    'expected_revision': 0,
                    'reason': '生产不能改预算',
                },
            ),
            (
                f'projects/{self.project.pk}/revise-bom/',
                {
                    'expected_revision': self.bom_version(self.project.pk),
                    'lines': [{'item': self.item.pk, 'quantity': '1'}],
                },
            ),
            (f'purchases/{purchase.pk}/approve/', {}),
            (
                'entries/expense/',
                {'project': self.project.pk, 'title': '生产不能入费用账', 'amount': '10', 'due_date': str(self.today)},
            ),
        ):
            with self.subTest(path=path):
                self.post('production_manager', path, payload, status=403)
        self.assertEqual(ActionReceipt.objects.count(), before)
        self.assertFalse(Entry.objects.filter(purchase=purchase).exists())
        self.assertEqual(self.get('projects/')['count'], 1)
        self.get(f'projects/{self.other_project.pk}/', status=404)

    def test_global_read_from_additional_roles_does_not_expand_production_task_or_time_write_scope(self):
        outside = self.task(project=self.other_project)
        original_time = TimeEntry.objects.create(
            task=outside,
            user=self.users['member'],
            date=self.today,
            hours=1,
            hourly_cost=50,
            cost=50,
            reason='外部项目原工时',
        )
        for additional in ('purchaser', 'purchase_manager', 'finance'):
            with self.subTest(additional=additional):
                self.production.additional_roles = [additional]
                self.production.save()
                project = self.get(f'projects/{self.other_project.pk}/')
                self.assertFalse(project['can_manage_production'])
                self.assertFalse(project['can_manage'])
                self.assertFalse(self.get(f'tasks/{outside.pk}/')['can_manage'])
                self.assertFalse(self.get(f'time/{original_time.pk}/')['can_amend'])
                before = ActionReceipt.objects.count()
                self.post(
                    'production_manager',
                    'tasks/',
                    {
                        'project': self.other_project.pk,
                        'kind': 'assembly',
                        'title': '跨项目生产新建应拒绝',
                        'assignee': self.users['member'].pk,
                    },
                    status=403,
                )
                self.post(
                    'production_manager',
                    f'tasks/{outside.pk}/assign/',
                    {'assignee': self.production.pk, 'reason': '采购全局读取不是生产授权'},
                    status=403,
                )
                self.post(
                    'production_manager',
                    f'tasks/{outside.pk}/time/',
                    {
                        'user': self.users['member'].pk,
                        'date': str(self.today),
                        'hours': '2',
                        'reason': '不可代记外部生产工时',
                    },
                    status=403,
                )
                self.post(
                    'production_manager',
                    f'time/{original_time.pk}/amend/',
                    {'date': str(self.today), 'hours': '2', 'reason': '不可更正外部工时'},
                    status=403,
                )
                self.assertEqual(ActionReceipt.objects.count(), before)
        self.assertEqual(Task.objects.get(pk=outside.pk).assignee_id, self.users['member'].pk)
        self.assertEqual(TimeEntry.objects.filter(task=outside).count(), 1)

    def test_role_revocation_and_project_removal_reject_successful_production_action_replay(self):
        task = self.task()
        payload = {'assignee': self.production.pk, 'reason': '生产经理首次派工'}
        key = str(uuid.uuid4())
        self.post('production_manager', f'tasks/{task.pk}/assign/', payload, key=key)
        self.production.role = 'member'
        self.production.save()
        before = ActionReceipt.objects.count()
        self.post('production_manager', f'tasks/{task.pk}/assign/', payload, key=key, status=403)
        self.assertEqual(ActionReceipt.objects.count(), before)
        self.production.role = 'production_manager'
        self.production.save()
        created_payload = {
            'project': self.project.pk,
            'kind': 'test',
            'title': '生产回放新任务',
            'assignee': self.users['member'].pk,
        }
        key = str(uuid.uuid4())
        self.post('production_manager', 'tasks/', created_payload, key=key, status=201)
        self.project.members.remove(self.production)
        before = ActionReceipt.objects.count(), Task.objects.count()
        self.post('production_manager', 'tasks/', created_payload, key=key, status=403)
        self.assertEqual((ActionReceipt.objects.count(), Task.objects.count()), before)

    def test_revoked_team_privilege_rechecks_cached_completion_time_and_amendment(self):
        self.task('design', status='done')
        for operation in ('complete', 'time', 'amend'):
            with self.subTest(operation=operation):
                self.production.role = 'production_manager'
                self.production.save()
                task = self.task()
                path = f'tasks/{task.pk}/{operation}/'
                payload = {'reason': '生产经理获授权时代班组操作'}
                if operation == 'time':
                    payload.update(user=self.users['member'].pk, date=str(self.today), hours='1')
                elif operation == 'amend':
                    source = TimeEntry.objects.create(
                        task=task,
                        user=self.users['member'],
                        date=self.today,
                        hours=1,
                        hourly_cost=50,
                        cost=50,
                        reason='原班组工时',
                    )
                    path = f'time/{source.pk}/amend/'
                    payload.update(date=str(self.today), hours='2')
                key = str(uuid.uuid4())
                self.post('production_manager', path, payload, key=key)
                self.production.role = 'member'
                self.production.save()
                before = ActionReceipt.objects.count(), TimeEntry.objects.count(), AuditLog.objects.count()
                # The actor still participates in the project, but has lost team authority.
                self.post('production_manager', path, payload, key=key, status=403)
                self.assertEqual(
                    (ActionReceipt.objects.count(), TimeEntry.objects.count(), AuditLog.objects.count()), before
                )
