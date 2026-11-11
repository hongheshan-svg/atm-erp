import uuid
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from apps.accounts.models import User
from apps.business.models import BOMLine, Delivery, Entry, Project, Stock, StockMove, Task, TimeEntry
from apps.core.models import ActionReceipt, AuditLog

from .test_commercial_chain import TODAY, BusinessFixtures


class ExecutionFixtures(BusinessFixtures):
    def setup_execution(self):
        self.setup_business()
        self.clock = patch(
            'apps.business.services.execution.timezone.localdate', return_value=date.fromisoformat(TODAY)
        )
        self.clock.start()
        self.addCleanup(self.clock.stop)
        User.objects.filter(pk=self.users['member'].pk).update(hourly_cost=50)

    def task(self, project, kind='design', title=None):
        task_id = self.post(
            'manager',
            'tasks/',
            {'project': project.pk, 'kind': kind, 'title': title or kind, 'assignee': self.users['member'].pk},
            status=201,
        )['id']
        return Task.objects.get(pk=task_id)

    def complete(self, task, status=200):
        return self.post('manager', f'tasks/{task.pk}/complete/', {'reason': '检查完成'}, status=status)

    def time(self, task, hours='1', when=TODAY, status=200):
        return self.post(
            'manager',
            f'tasks/{task.pk}/time/',
            {'user': self.users['member'].pk, 'hours': hours, 'date': when, 'reason': '实际工作'},
            status=status,
        )

    def ready_project(self, *, equipment=1, warranty=12):
        project = self.active_project(equipment=equipment, warranty=warranty)
        self.post(
            'manager',
            f'projects/{project.pk}/revise-bom/',
            {'expected_revision': self.bom_version(project.pk), 'lines': [{'item': self.item.pk, 'quantity': '4'}]},
        )
        for kind in ('design', 'assembly', 'test'):
            self.complete(self.task(project, kind))
        return project

    def stock_and_issue(self, project, quantity='4'):
        self.post(
            'admin', 'stocks/opening/', {'item': self.item.pk, 'quantity': '5', 'unit_cost': '100', 'reason': '期初'}
        )
        stock = Stock.objects.get()
        self.post(
            'warehouse',
            'stocks/issue/',
            {'project': project.pk, 'stock': stock.pk, 'quantity': quantity, 'reason': '领料'},
        )
        return stock

    def deliver(self, project, *, quantity=1):
        result = self.post(
            'manager',
            f'projects/{project.pk}/ship/',
            {
                'date': TODAY,
                'quantity': quantity,
                'installer': self.users['member'].pk,
                'acceptor': self.users['manager'].pk,
            },
        )
        return Delivery.objects.get(pk=result['id'])

    def accept(self, delivery):
        self.complete(delivery.tasks.get(kind='install'))
        self.post('manager', f'deliveries/{delivery.pk}/accept/', {'date': TODAY, 'reason': '客户确认验收'})
        delivery.refresh_from_db()


class ExecutionTests(ExecutionFixtures, TestCase):
    def test_task_time_receipt_and_net_history_survive_correction_and_archiving(self):
        project = self.active_project()
        task = self.task(project)
        self.complete(task)
        receipt = self.time(task, '9')
        self.assertEqual(receipt['task'], task.pk)
        self.assertEqual(Decimal(receipt['hours']), Decimal('9'))
        self.assertEqual(receipt['date'], TODAY)
        self.post('manager', f'time/{receipt["id"]}/amend/', {'hours': '2.5', 'date': TODAY, 'reason': '核对更正'})
        self.post('admin', 'record-deletions/', {'resource': 'time', 'ids': [receipt['id']], 'reason': '归档原记录'})
        self.post(
            'manager',
            f'tasks/{task.pk}/time/',
            {'user': self.users['manager'].pk, 'date': TODAY, 'hours': '1', 'reason': '经理协同'},
        )
        other = self.task(project, title='另一任务')
        self.time(other, '3')
        response = self.clients['member'].get(f'/api/business/tasks/{task.pk}/time-records/', {'page_size': 2})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['count'], 4)
        self.assertEqual(len(response.data['results']), 2)
        self.assertEqual(Decimal(response.data['summary']['logged_hours']), Decimal('3.5'))
        self.assertEqual(Decimal(response.data['summary']['my_hours']), Decimal('2.5'))
        own = self.clients['member'].get(f'/api/business/tasks/{task.pk}/time-records/', {'mine': 'true'})
        self.assertEqual(own.data['count'], 3)
        self.assertTrue(all(row['user'] == self.users['member'].pk for row in own.data['results']))
        archived = next(row for row in own.data['results'] if row['id'] == receipt['id'])
        self.assertTrue(archived['archived'])
        self.assertIsNotNone(archived['reversed_by'])
        self.assertNotIn('hourly_cost', archived)
        self.assertNotIn('cost', archived)
        detail = self.clients['member'].get(f'/api/business/tasks/{task.pk}/').data
        self.assertEqual(detail['logged_hours'], '3.50')
        self.assertEqual(detail['time_entry_count'], 4)
        listed = self.clients['member'].get('/api/business/tasks/', {'project': project.pk}).data['results']
        self.assertEqual(next(row['logged_hours'] for row in listed if row['id'] == task.pk), '3.50')
        exported = self.clients['member'].get('/api/business/tasks/export/', {'project': project.pk})
        self.assertEqual(exported.status_code, 200)
        self.assertIn('已登记净工时（小时）', exported.content.decode('utf-8-sig'))
        self.assertIn('3.50', exported.content.decode('utf-8-sig'))

    def test_task_time_history_empty_and_project_scope(self):
        task = self.task(self.active_project())
        response = self.clients['member'].get(f'/api/business/tasks/{task.pk}/time-records/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['results'], [])
        self.assertEqual(Decimal(response.data['summary']['logged_hours']), 0)
        receipt_key = str(uuid.uuid4())
        body = {'hours': '1.5', 'date': TODAY, 'reason': '回执核对'}
        receipt = self.post('manager', f'tasks/{task.pk}/time/', body, key=receipt_key)
        self.assertEqual(self.post('manager', f'tasks/{task.pk}/time/', body, key=receipt_key), receipt)
        self.assertEqual(TimeEntry.objects.filter(task=task).count(), 1)
        outside = Project.objects.create(
            code='PRIVATE', name='未参与项目', customer=self.customer, manager=self.users['admin'], status='active'
        )
        hidden = Task.objects.create(project=outside, kind='design', title='不可见任务', assignee=self.users['admin'])
        self.assertEqual(self.clients['member'].get(f'/api/business/tasks/{hidden.pk}/time-records/').status_code, 404)
        self.assertEqual(
            self.clients['member'].get(f'/api/business/tasks/{task.pk}/time-records/', {'mine': 'other'}).status_code,
            400,
        )

    def test_manager_only_change_rejects_when_old_manager_has_open_task(self):
        project = self.active_project()
        old = self.users['manager']
        new = User.objects.create_user(username='manager2', role='manager')
        task_id = self.post(
            'manager',
            'tasks/',
            {'project': project.pk, 'kind': 'design', 'title': '经理自领设计', 'assignee': old.pk},
            status=201,
        )['id']
        before_members = set(project.members.values_list('pk', flat=True))
        audits = AuditLog.objects.count()
        result = self.clients['admin'].post(
            f'/api/business/projects/{project.pk}/edit/',
            {'manager': new.pk, 'reason': '负责人交接'},
            format='json',
            HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
        )
        self.assertEqual(result.status_code, 409, result.data)
        self.assertIn('原负责人', str(result.data))
        project.refresh_from_db()
        self.assertEqual(project.manager_id, old.pk)
        self.assertEqual(set(project.members.values_list('pk', flat=True)), before_members)
        self.assertEqual(AuditLog.objects.count(), audits)
        self.assertEqual(Task.objects.get(pk=task_id).assignee_id, old.pk)

    def test_manager_only_change_allows_old_manager_kept_as_member_or_task_done(self):
        project = self.active_project()
        old = self.users['manager']
        new = User.objects.create_user(username='manager2', role='manager')
        task_id = self.post(
            'manager',
            'tasks/',
            {'project': project.pk, 'kind': 'design', 'title': '经理自领设计', 'assignee': old.pk},
            status=201,
        )['id']
        # Kept as member in the same request: allowed.
        self.post(
            'admin',
            f'projects/{project.pk}/edit/',
            {'manager': new.pk, 'members': [self.users['member'].pk, old.pk], 'reason': '保留为成员'},
        )
        self.assertTrue(project.members.filter(pk=old.pk).exists())
        # Already a member: swapping back and forth by manager only is allowed too.
        self.post('admin', f'projects/{project.pk}/edit/', {'manager': old.pk, 'reason': '换回'})
        self.post('manager', f'tasks/{task_id}/complete/', {'reason': '完成'})
        # Task done: a manager-only change without membership is allowed.
        self.post('admin', f'projects/{project.pk}/edit/', {'members': [self.users['member'].pk], 'reason': '清理成员'})
        self.post('admin', f'projects/{project.pk}/edit/', {'manager': new.pk, 'reason': '负责人交接'})
        project.refresh_from_db()
        self.assertEqual(project.manager_id, new.pk)

    def setUp(self):
        self.setup_execution()

    def test_standalone_project_cannot_change_delivery_terms_after_shipping(self):
        project = Project.objects.create(
            code='INTERNAL',
            name='内部设备',
            customer=self.customer,
            manager=self.users['manager'],
            status='delivering',
            equipment_quantity=2,
        )
        Delivery.objects.create(code='INTERNAL-D', project=project, quantity=2, shipped_date=TODAY)
        self.assertIsNone(project.contract_date)
        for field, value in [('equipment_quantity', 1), ('warranty_months', 0), ('customer', self.customer.pk)]:
            self.post(
                'manager', f'projects/{project.pk}/edit/', {field: value, 'reason': '不应覆盖交付约定'}, status=409
            )
        project.refresh_from_db()
        self.assertEqual((project.equipment_quantity, project.warranty_months), (2, 12))
        self.post('manager', f'projects/{project.pk}/edit/', {'requirements': '补充说明', 'reason': '记录执行情况'})
        project.refresh_from_db()
        self.assertEqual(project.requirements, '补充说明')

    def test_full_api_chain_from_sales_to_two_deliveries_and_after_sales(self):
        project = self.ready_project(equipment=2, warranty=0)
        design = project.tasks.get(kind='design')
        original = self.time(design, '3')['id']
        self.post('manager', f'time/{original}/amend/', {'hours': '2', 'date': TODAY, 'reason': '更正误记'})
        for kind in ('assembly', 'test'):
            self.time(project.tasks.get(kind=kind))
        purchase = self.purchase(project, over_bom_reason='备件随整线一并采购')
        self.post(
            'warehouse',
            f'purchases/{purchase.pk}/receive/',
            {'lines': [{'line': purchase.lines.get().pk, 'quantity': '5'}], 'reason': '全部收货'},
        )
        stock = Stock.objects.get()
        self.post(
            'warehouse',
            'stocks/issue/',
            {'project': project.pk, 'stock': stock.pk, 'quantity': '4', 'reason': '两台设备生产领料'},
        )
        deliveries = []
        for _ in range(2):
            delivery = self.deliver(project)
            self.time(delivery.tasks.get(kind='install'))
            self.accept(delivery)
            deliveries.append(delivery)
        project.refresh_from_db()
        self.assertEqual(project.status, 'warranty')
        self.assertTrue(all(d.warranty_until == date.fromisoformat(TODAY) for d in deliveries))
        service_payload = {
            'delivery': deliveries[0].pk,
            'date': TODAY,
            'title': '质保换件',
            'assignee': self.users['member'].pk,
        }
        free_id = self.post('manager', f'projects/{project.pk}/service/', service_payload)['id']
        free_task = Task.objects.get(pk=free_id)
        self.assertFalse(Entry.objects.filter(task=free_task).exists())
        self.post(
            'warehouse',
            'stocks/issue/',
            {'project': project.pk, 'stock': stock.pk, 'task': free_id, 'quantity': '1', 'reason': '售后换件'},
        )
        self.time(free_task)
        self.post('manager', f'projects/{project.pk}/close/', {'reason': '尚有售后任务'}, status=409)
        self.complete(free_task)
        tomorrow = date.fromisoformat(TODAY) + timedelta(days=1)
        with patch('apps.business.services.execution.timezone.localdate', return_value=tomorrow):
            paid_id = self.post(
                'manager',
                f'projects/{project.pk}/service/',
                {**service_payload, 'date': tomorrow.isoformat(), 'title': '质保外维护', 'fee': '300'},
            )['id']
            paid_task = Task.objects.get(pk=paid_id)
            self.time(paid_task, when=tomorrow.isoformat())
            self.complete(paid_task)
        self.assertEqual(Entry.objects.get(task_id=paid_id).amount, Decimal('300'))
        self.post(
            'finance',
            'entries/expense/',
            {'project': project.pk, 'title': '现场差旅', 'amount': '50', 'due_date': TODAY},
            status=201,
        )
        self.post('manager', f'projects/{project.pk}/close/', {'reason': '还未结清款项'}, status=409)
        entries = self.clients['finance'].get('/api/business/entries/', {'project': project.pk}).data['results']
        self.assertEqual(sum(Decimal(e['amount']) for e in entries if e['kind'] == 'receivable'), Decimal('10300'))
        for entry in entries:
            self.post(
                'finance',
                f'entries/{entry["id"]}/pay/',
                {
                    'amount': entry['balance'],
                    'date': TODAY,
                    'reason': '银行到账确认',
                    **(self.reconciliation_data(entry['id']) if entry['purchase'] else {}),
                },
            )
        result = self.clients['finance'].get(f'/api/business/projects/{project.pk}/cost/').data
        self.assertEqual(
            result,
            {
                'materials': '500.00',
                'purchase_return_variance': '0.00',
                'labor': '400.00',
                'expenses': '50.00',
                'total': '950.00',
            },
        )
        close_key = str(uuid.uuid4())
        self.post('manager', f'projects/{project.pk}/close/', {'reason': '全部履约并结清'}, key=close_key)
        self.post('manager', f'projects/{project.pk}/close/', {'reason': '全部履约并结清'}, key=close_key)
        project.refresh_from_db()
        self.assertEqual(project.status, 'closed')
        self.post('manager', f'projects/{project.pk}/reopen/', {'reason': '后续仍可登记售后'})
        project.refresh_from_db()
        self.assertEqual(project.status, 'warranty')
        self.assertEqual(self.clients['finance'].get(f'/api/business/projects/{project.pk}/cost/').data, result)

    def test_stage_gates_shipping_and_acceptance(self):
        project = self.active_project()
        assembly = self.task(project, 'assembly')
        self.complete(assembly)  # 阶段可交叉推进，发货仍校验所有必需阶段。
        design = self.task(project)
        self.complete(design)
        self.post('manager', f'projects/{project.pk}/ship/', {'quantity': 1, 'date': TODAY}, status=409)
        self.complete(self.task(project, 'test'))
        self.post('manager', f'projects/{project.pk}/ship/', {'quantity': 1, 'date': TODAY}, status=409)
        self.post(
            'manager',
            f'projects/{project.pk}/revise-bom/',
            {'expected_revision': self.bom_version(project.pk), 'lines': [{'item': self.item.pk, 'quantity': '4'}]},
        )
        self.stock_and_issue(project)
        delivery = self.deliver(project)
        self.post('manager', f'deliveries/{delivery.pk}/accept/', {'date': TODAY, 'reason': '尚未安装'}, status=409)
        acceptance = delivery.tasks.get(kind='acceptance')
        self.post('manager', f'tasks/{acceptance.pk}/complete/', {'reason': '不能直接验收'}, status=409)
        self.accept(delivery)
        self.post('manager', f'projects/{project.pk}/ship/', {'quantity': 1, 'date': TODAY}, status=409)

    def test_ship_writes_optional_install_and_acceptance_deadlines(self):
        project = self.ready_project(equipment=2)
        self.stock_and_issue(project)
        shipped = date.fromisoformat(TODAY)
        base = {
            'date': TODAY,
            'quantity': 1,
            'installer': self.users['member'].pk,
            'acceptor': self.users['manager'].pk,
        }
        before = Delivery.objects.count(), Task.objects.count(), ActionReceipt.objects.count()
        for key in ('install_due_date', 'acceptance_due_date'):
            with self.subTest(key=key):
                early = (shipped - timedelta(days=1)).isoformat()
                denied = self.post('manager', f'projects/{project.pk}/ship/', {**base, key: early}, status=400)
                self.assertIn('不能早于发货日期', str(denied[key]))
                self.post('manager', f'projects/{project.pk}/ship/', {**base, key: '2026/09/30'}, status=400)
        self.assertEqual((Delivery.objects.count(), Task.objects.count(), ActionReceipt.objects.count()), before)
        install_due, acceptance_due = shipped + timedelta(days=3), shipped + timedelta(days=10)
        result = self.post(
            'manager',
            f'projects/{project.pk}/ship/',
            {**base, 'install_due_date': install_due.isoformat(), 'acceptance_due_date': acceptance_due.isoformat()},
        )
        delivery = Delivery.objects.get(pk=result['id'])
        self.assertEqual(
            dict(delivery.tasks.values_list('kind', 'due_date')), {'install': install_due, 'acceptance': acceptance_due}
        )

        def progress_due():
            rows = (
                self.clients['manager']
                .get(f'/api/business/projects/{project.pk}/progress/', {'category': 'deliveries'})
                .data['results']
            )
            return next(str(row['due_date']) for row in rows if row['title'] == delivery.code)

        # 流程进度交付行按未完成的安装任务取期限，安装完成后改看验收期限。
        self.assertEqual(progress_due(), install_due.isoformat())
        self.complete(delivery.tasks.get(kind='install'))
        self.assertEqual(progress_due(), acceptance_due.isoformat())
        # 期限可与发货同日；留空保持原样（不设期限）。
        second = Delivery.objects.get(
            pk=self.post(
                'manager',
                f'projects/{project.pk}/ship/',
                {**base, 'install_due_date': TODAY, 'acceptance_due_date': ''},
            )['id']
        )
        self.assertEqual(dict(second.tasks.values_list('kind', 'due_date')), {'install': shipped, 'acceptance': None})

    def test_partial_delivery_requires_proportional_materials(self):
        project = self.ready_project(equipment=2)
        stock = self.stock_and_issue(project, quantity='2')
        self.deliver(project)
        self.post('manager', f'projects/{project.pk}/ship/', {'quantity': 1, 'date': TODAY}, status=409)
        self.post(
            'warehouse',
            'stocks/issue/',
            {'project': project.pk, 'stock': stock.pk, 'quantity': '2', 'reason': '第二台补足领料'},
        )
        self.deliver(project)
        self.assertEqual(project.deliveries.count(), 2)

    def test_time_amend_keeps_original_rate_and_rejects_repeat(self):
        project = self.active_project()
        task = self.task(project)
        time_id = self.time(task, '3')['id']
        User.objects.filter(pk=self.users['member'].pk).update(hourly_cost=100)
        changed_id = self.post('manager', f'time/{time_id}/amend/', {'hours': '2', 'date': TODAY, 'reason': '更正'})[
            'id'
        ]
        self.assertEqual(TimeEntry.objects.get(pk=changed_id).cost, Decimal('100'))
        self.assertEqual(sum(TimeEntry.objects.values_list('hours', flat=True)), Decimal('2'))
        self.assertEqual(sum(TimeEntry.objects.values_list('cost', flat=True)), Decimal('100'))
        self.post(
            'manager', f'time/{time_id}/amend/', {'hours': '1', 'date': TODAY, 'reason': '原记录已更正'}, status=409
        )
        response = self.clients['member'].get('/api/business/time/', {'task__project': project.pk})
        self.assertEqual(response.data['count'], 3)
        records = {row['id']: row for row in response.data['results']}
        reverse_id = records[time_id]['reversed_by']
        self.assertEqual(records[reverse_id]['reversal_of'], time_id)
        self.assertIsNone(records[changed_id]['reversed_by'])
        self.assertTrue(all('cost' not in row and 'hourly_cost' not in row for row in response.data['results']))

    def test_daily_time_limit_and_permission(self):
        project = self.active_project()
        task = self.task(project)
        self.time(task, '23')
        self.time(task, '2', status=409)
        self.post(
            'member',
            f'tasks/{task.pk}/time/',
            {'user': self.users['manager'].pk, 'hours': '1', 'date': TODAY, 'reason': '冒记他人工时'},
            status=403,
        )
        self.post('finance', f'tasks/{task.pk}/complete/', {'reason': '不是负责人'}, status=403)
        future = (date.fromisoformat(TODAY) + timedelta(days=1)).isoformat()
        self.time(task, '1', when=future, status=400)

    def test_project_member_change_cannot_strand_open_tasks(self):
        project = self.active_project()
        task = self.task(project)
        self.post('manager', f'projects/{project.pk}/edit/', {'members': [], 'reason': '移除人员'}, status=409)
        self.post('manager', f'tasks/{task.pk}/assign/', {'assignee': self.users['manager'].pk, 'reason': '经理接手'})
        self.post('manager', f'projects/{project.pk}/edit/', {'members': [], 'reason': '交接完成'})
        self.assertEqual(self.clients['member'].get(f'/api/business/tasks/{task.pk}/').status_code, 404)
        self.assertEqual(self.clients['member'].get(f'/api/business/projects/{project.pk}/').status_code, 404)
        self.post(
            'manager',
            f'projects/{project.pk}/edit/',
            {'equipment_quantity': 2, 'reason': '不能直接改已签约数量'},
            status=409,
        )

    def test_cancel_project_refund_and_reopen_preserve_contract_and_cost(self):
        project = self.active_project()
        task = self.task(project)
        self.time(task)
        entry = project.entries.get(kind='receivable')
        self.post('finance', f'entries/{entry.pk}/pay/', {'amount': '500', 'date': TODAY, 'reason': '预收'})
        self.post('manager', f'projects/{project.pk}/cancel/', {'reason': '客户取消'})
        task.refresh_from_db()
        self.assertEqual(task.status, 'cancelled')
        entry.refresh_from_db()
        self.assertEqual(entry.credit_amount, Decimal('10000'))
        self.post(
            'finance',
            f'entries/{entry.pk}/refund/',
            {'amount': '500', 'date': TODAY, 'reason': '预收款退还', **self.reconciliation_data(entry)},
        )
        self.post('manager', f'projects/{project.pk}/reopen/', {'reason': '客户恢复项目'})
        self.assertEqual(project.entries.count(), 1)
        entry.refresh_from_db()
        self.assertEqual((entry.amount, entry.credit_amount), (Decimal('10000'), Decimal('0')))
        self.post('manager', f'tasks/{task.pk}/reopen/', {'reason': '恢复原设计任务'})
        self.assertEqual(
            self.clients['finance'].get(f'/api/business/projects/{project.pk}/cost/').data['labor'], '50.00'
        )

    def test_remove_bom_replay_keeps_soft_deleted_history(self):
        project = self.active_project()
        self.post(
            'manager',
            f'projects/{project.pk}/revise-bom/',
            {'expected_revision': self.bom_version(project.pk), 'lines': [{'item': self.item.pk, 'quantity': '4'}]},
        )
        line = BOMLine.objects.get()
        key = str(uuid.uuid4())
        self.post('manager', f'bom/{line.pk}/remove/', {'reason': '不再使用'}, key=key)
        self.post('manager', f'bom/{line.pk}/remove/', {'reason': '不再使用'}, key=key)
        self.assertFalse(BOMLine.objects.exists())
        self.assertTrue(BOMLine.all_objects.get(pk=line.pk).is_deleted)
        self.assertEqual(ActionReceipt.objects.filter(key=key).count(), 1)

    def test_service_fee_cancellation_and_reopening_restore_same_entry(self):
        project = self.ready_project(warranty=0)
        self.stock_and_issue(project)
        delivery = self.deliver(project)
        self.accept(delivery)
        tomorrow = date.fromisoformat(TODAY) + timedelta(days=1)
        with patch('apps.business.services.execution.timezone.localdate', return_value=tomorrow):
            task_id = self.post(
                'manager',
                f'projects/{project.pk}/service/',
                {
                    'delivery': delivery.pk,
                    'date': tomorrow.isoformat(),
                    'title': '收费检修',
                    'fee': '300',
                    'assignee': self.users['member'].pk,
                },
            )['id']
        entry = Entry.objects.get(task_id=task_id)
        self.post('manager', f'tasks/{task_id}/cancel/', {'reason': '客户暂缓'})
        entry.refresh_from_db()
        self.assertEqual(entry.credit_amount, Decimal('300'))
        self.post('manager', f'tasks/{task_id}/reopen/', {'reason': '客户确认继续'})
        entry.refresh_from_db()
        self.assertEqual(entry.credit_amount, Decimal('0'))
        self.assertEqual(Entry.objects.filter(task_id=task_id).count(), 1)

    def test_service_date_and_fee_are_validated_by_server(self):
        project = self.ready_project(warranty=0)
        self.stock_and_issue(project)
        delivery = self.deliver(project)
        payload = {'delivery': delivery.pk, 'date': TODAY, 'title': '维修', 'assignee': self.users['member'].pk}
        self.post('manager', f'projects/{project.pk}/service/', payload, status=409)
        self.accept(delivery)
        self.post('manager', f'projects/{project.pk}/service/', {**payload, 'fee': '1'}, status=400)
        tomorrow = date.fromisoformat(TODAY) + timedelta(days=1)
        with patch('apps.business.services.execution.timezone.localdate', return_value=tomorrow):
            self.post(
                'manager',
                f'projects/{project.pk}/service/',
                {**payload, 'date': tomorrow.isoformat(), 'fee': '0'},
                status=400,
            )

    def test_in_warranty_chargeable_service_requires_non_warranty_reason(self):
        project = self.ready_project()
        self.stock_and_issue(project)
        delivery = self.deliver(project)
        self.accept(delivery)
        payment_due = date.fromisoformat(TODAY) + timedelta(days=30)
        payload = {
            'delivery': delivery.pk,
            'date': TODAY,
            'title': '客户误操作撞机维修',
            'assignee': self.users['member'].pk,
            'fee': '800',
            'fee_due_date': payment_due.isoformat(),
        }
        before = Task.objects.count(), Entry.objects.count(), ActionReceipt.objects.count()
        for reason in (None, '  '):
            with self.subTest(reason=reason):
                data = payload if reason is None else {**payload, 'charge_reason': reason}
                denied = self.post('manager', f'projects/{project.pk}/service/', data, status=400)
                self.assertIn('非质保责任原因', str(denied['charge_reason']))
        self.assertEqual((Task.objects.count(), Entry.objects.count(), ActionReceipt.objects.count()), before)
        task_id = self.post(
            'manager', f'projects/{project.pk}/service/', {**payload, 'charge_reason': '客户误操作撞机，非质保责任'}
        )['id']
        entry = Entry.objects.get(task_id=task_id)
        self.assertEqual((entry.kind, entry.amount, entry.due_date), ('receivable', Decimal('800'), payment_due))
        log = AuditLog.objects.get(operation='service.create', resource=f'task:{task_id}')
        self.assertEqual(log.detail['charge_reason'], '客户误操作撞机，非质保责任')
        self.assertEqual(Decimal(log.detail['fee']), Decimal('800'))
        free = {key: value for key, value in payload.items() if key not in {'fee', 'fee_due_date'}}
        free_id = self.post('manager', f'projects/{project.pk}/service/', {**free, 'title': '质保换件'})['id']
        self.assertFalse(Entry.objects.filter(task_id=free_id).exists())
        self.assertEqual(
            AuditLog.objects.get(operation='service.create', resource=f'task:{free_id}').detail['charge_reason'], ''
        )

    def test_installed_and_accepted_tasks_cannot_be_deleted_or_reopened(self):
        project = self.ready_project()
        self.stock_and_issue(project)
        delivery = self.deliver(project)
        install = delivery.tasks.get(kind='install')
        self.post('manager', f'tasks/{install.pk}/cancel/', {'reason': '不能移除必经步骤'}, status=409)
        self.accept(delivery)
        self.post('manager', f'tasks/{install.pk}/reopen/', {'reason': '不能倒退已验收事实'}, status=409)

    def test_delivered_materials_cannot_be_returned_as_unused_stock(self):
        project = self.ready_project()
        stock = self.stock_and_issue(project)
        self.deliver(project)
        original = StockMove.objects.get(kind='issue')
        self.post(
            'warehouse',
            f'moves/{original.pk}/return-material/',
            {'quantity': '1', 'reason': '不能退回设备内材料'},
            status=409,
        )
        stock.refresh_from_db()
        self.assertEqual(stock.quantity, Decimal('1'))
        self.assertEqual(
            self.clients['finance'].get(f'/api/business/projects/{project.pk}/cost/').data['materials'], '400.00'
        )

    def test_reopening_cancelled_task_requires_valid_assignee(self):
        project = self.active_project()
        task = self.task(project)
        self.post('manager', f'tasks/{task.pk}/cancel/', {'reason': '暂缓'})
        self.post('manager', f'projects/{project.pk}/edit/', {'members': [], 'reason': '人员调离'})
        # 被拒的是原执行人而不是操作者，所以报错落在 assignee 字段上，而不是一句「无权访问此项目」。
        denied = self.post('manager', f'tasks/{task.pk}/reopen/', {'reason': '原成员已不在项目'}, status=400)
        self.assertIn('assignee', denied)
        self.assertIn('不是该项目的负责人或成员', str(denied['assignee']))
        self.post('manager', f'tasks/{task.pk}/reopen/', {'reason': '经理接手', 'assignee': self.users['manager'].pk})
        task.refresh_from_db()
        self.assertEqual((task.status, task.assignee_id), ('open', self.users['manager'].pk))

    def test_unstarted_stage_task_created_after_first_shipment_can_be_cancelled_by_manager(self):
        project = self.ready_project(equipment=2)
        self.stock_and_issue(project)
        self.deliver(project)
        original = project.tasks.get(kind='test')
        mistaken = self.task(project, 'test', '二批调试返工（误建）')
        flags = {
            row['id']: row['can_cancel']
            for row in self.clients['manager'].get('/api/business/tasks/', {'project': project.pk}).data['results']
        }
        self.assertEqual((flags[original.pk], flags[mistaken.pk]), (False, True))
        self.assertTrue(self.clients['manager'].get(f'/api/business/tasks/{mistaken.pk}/').data['can_cancel'])
        # 首批发货前的阶段任务是已发货批次的依据，仍然不能取消。
        self.post('manager', f'tasks/{original.pk}/cancel/', {'reason': '不能撤销已发货依据'}, status=409)
        self.post('manager', f'projects/{project.pk}/ship/', {'quantity': 1, 'date': TODAY}, status=409)
        self.post('manager', f'tasks/{mistaken.pk}/cancel/', {}, status=400)
        self.post('manager', f'tasks/{mistaken.pk}/cancel/', {'reason': '误建的返工任务'})
        mistaken.refresh_from_db()
        self.assertEqual(mistaken.status, 'cancelled')
        self.assertFalse(mistaken.is_deleted)
        log = AuditLog.objects.get(operation='task.cancel', resource=f'task:{mistaken.pk}')
        self.assertEqual(log.detail['reason'], '误建的返工任务')
        self.assertFalse(self.clients['manager'].get(f'/api/business/tasks/{mistaken.pk}/').data['can_reopen'])
        self.post('manager', f'tasks/{mistaken.pk}/reopen/', {'reason': '已有交付不能重开'}, status=409)
        self.deliver(project)
        self.assertEqual(project.deliveries.count(), 2)

    def test_started_or_done_stage_task_after_first_shipment_stays_locked(self):
        project = self.ready_project(equipment=2)
        stock = self.stock_and_issue(project, quantity='2')
        self.deliver(project)
        timed = self.task(project, 'assembly', '二批装配')
        self.time(timed)
        reversed_time = self.task(project, 'assembly', '二批装配更正')
        entry = self.time(reversed_time)['id']
        self.post('manager', f'time/{entry}/amend/', {'hours': '0', 'date': TODAY, 'reason': '误记撤销'})
        picked = self.task(project, 'assembly', '二批领料')
        self.post(
            'warehouse',
            'stocks/issue/',
            {'project': project.pk, 'stock': stock.pk, 'task': picked.pk, 'quantity': '1', 'reason': '二批领料'},
        )
        done = self.task(project, 'design', '二批设计')
        self.complete(done)
        listed = self.clients['manager'].get('/api/business/tasks/', {'project': project.pk}).data['results']
        flags = {row['id']: row['can_cancel'] for row in listed}
        for task, status in ((timed, 'open'), (reversed_time, 'open'), (picked, 'open'), (done, 'done')):
            with self.subTest(task=task.title):
                self.assertFalse(flags[task.pk])
                denied = self.post('manager', f'tasks/{task.pk}/cancel/', {'reason': '试图取消已开工任务'}, status=409)
                self.assertIn('工时', str(denied))
                self.assertEqual(Task.objects.get(pk=task.pk).status, status)


class ProjectTaskProgressTests(ExecutionFixtures, TestCase):
    def setUp(self):
        self.setup_execution()

    def test_project_list_and_detail_report_task_progress_without_cancelled_or_deleted(self):
        project = self.active_project()
        base = Task.objects.filter(project=project).exclude(status='cancelled')
        total, done = base.count(), base.filter(status='done').count()
        finished, dropped, removed = (self.task(project, title=name) for name in ('完成项', '取消项', '删除项'))
        self.task(project, title='进行项')
        self.complete(finished)
        self.post('manager', f'tasks/{dropped.pk}/cancel/', {'reason': '不再需要'})
        Task.objects.filter(pk=removed.pk).update(is_deleted=True)

        listed = self.clients['manager'].get('/api/business/projects/').data
        rows = listed['results'] if isinstance(listed, dict) else listed
        row = next(row for row in rows if row['id'] == project.pk)
        self.assertEqual((row['task_total'], row['task_done']), (total + 2, done + 1))
        detail = self.clients['manager'].get(f'/api/business/projects/{project.pk}/').data
        self.assertEqual((detail['task_total'], detail['task_done']), (total + 2, done + 1))


class ProjectReadinessTests(ExecutionFixtures, TestCase):
    """推进检查只读复用发货、验收、结项的同一组判断；不满足的项与实际动作的拒绝一致。"""

    def setUp(self):
        self.setup_execution()

    def readiness(self, project, role='manager', status=200):
        response = self.clients[role].get(f'/api/business/projects/{project.pk}/readiness/')
        self.assertEqual(response.status_code, status, response.data)
        return response.data

    def items(self, result, group='ship'):
        return {item['key']: item for item in result[group]}

    def test_ship_checks_list_every_gap_before_submitting_and_match_ship(self):
        project = self.active_project(equipment=2)
        self.complete(self.task(project, 'design'))
        self.task(project, 'assembly')
        shipping = self.task(project, 'shipping', title='客户预验收')
        before = AuditLog.objects.count()
        items = self.items(self.readiness(project))
        self.assertEqual(AuditLog.objects.count(), before)
        self.assertTrue(items['stage_design']['ok'])
        self.assertEqual(items['stage_design']['detail'], '已完成 1 / 1')
        self.assertEqual((items['stage_assembly']['ok'], items['stage_assembly']['detail']), (False, '已完成 0 / 1'))
        self.assertEqual(items['stage_assembly']['target'], {'tab': 'tasks', 'phase': 'assembly'})
        self.assertEqual((items['stage_test']['ok'], items['stage_test']['detail']), (False, '尚未建立调试阶段任务'))
        self.assertFalse(items['follow_up']['ok'])
        self.assertIn('客户预验收', items['follow_up']['detail'])
        self.assertEqual((items['bom']['ok'], items['bom']['detail']), (False, '尚未登记 BOM'))
        self.assertTrue(items['quantity']['ok'])
        self.assertNotIn('materials', items)
        self.assertFalse(items['receivable']['blocking'])
        self.assertTrue(all(item['blocking'] for key, item in items.items() if key != 'receivable'))
        self.assertTrue(all('message' not in item for item in items.values()))
        # 发货时仍按同样顺序逐条拒绝，报错写明差几项。
        denied = self.post('manager', f'projects/{project.pk}/ship/', {'quantity': 1, 'date': TODAY}, status=409)
        self.assertIn('装配阶段', str(denied))
        self.assertIn('还有 1 项未完成', str(denied))
        self.complete(project.tasks.get(kind='assembly'))
        denied = self.post('manager', f'projects/{project.pk}/ship/', {'quantity': 1, 'date': TODAY}, status=409)
        self.assertIn('尚未建立调试阶段任务', str(denied))
        self.complete(self.task(project, 'test'))
        denied = self.post('manager', f'projects/{project.pk}/ship/', {'quantity': 1, 'date': TODAY}, status=409)
        self.assertIn('采购跟进、客户预验收和整改', str(denied))
        self.complete(shipping)
        self.post(
            'manager',
            f'projects/{project.pk}/revise-bom/',
            {'expected_revision': self.bom_version(project.pk), 'lines': [{'item': self.item.pk, 'quantity': '4'}]},
        )
        items = self.items(self.readiness(project))
        self.assertEqual(items['materials']['ok'], False)
        self.assertIn('1 种物料领料不足', items['materials']['detail'])
        self.post('manager', f'projects/{project.pk}/ship/', {'quantity': 1, 'date': TODAY}, status=409)
        stock = self.stock_and_issue(project, quantity='2')
        items = self.items(self.readiness(project))
        self.assertTrue(all(item['ok'] for item in items.values() if item['blocking']), items)
        self.deliver(project)
        # 第二台是最后一台，须覆盖剩余 BOM：领料只够一半时提示不足，与发货拒绝一致。
        project.refresh_from_db()
        result = self.readiness(project)
        items = self.items(result)
        self.assertEqual(items['quantity']['detail'], '已发货 1 / 2 台，还可发 1 台')
        self.assertFalse(items['materials']['ok'])
        self.assertIn('最后一台', items['materials']['detail'])
        self.assertEqual([item['key'] for item in result['accept']], ['install', 'acceptance'])
        self.assertFalse(self.items(result, 'accept')['install']['ok'])
        self.post('manager', f'projects/{project.pk}/ship/', {'quantity': 1, 'date': TODAY}, status=409)
        self.post(
            'warehouse',
            'stocks/issue/',
            {'project': project.pk, 'stock': stock.pk, 'quantity': '2', 'reason': '第二台领料'},
        )
        self.assertTrue(self.items(self.readiness(project))['materials']['ok'])
        self.deliver(project)
        result = self.readiness(project)
        # 全部发货后不再列发货条件，只剩验收进度。
        self.assertEqual(result['ship'], [])
        self.assertEqual(self.items(result, 'accept')['acceptance']['detail'], '已验收 0 / 2 批')

    def test_close_checks_match_close_and_scope_is_project_manager(self):
        project = self.ready_project()
        self.stock_and_issue(project)
        delivery = self.deliver(project)
        self.accept(delivery)
        project.refresh_from_db()
        self.assertEqual(project.status, 'warranty')
        result = self.readiness(project)
        self.assertEqual((result['ship'], result['accept']), ([], []))
        items = self.items(result, 'close')
        self.assertEqual(list(items), ['tasks', 'deliveries', 'purchases', 'entries', 'banking'])
        self.assertTrue(items['tasks']['ok'])
        self.assertTrue(items['deliveries']['ok'])
        self.assertFalse(items['entries']['ok'])
        self.assertEqual(items['entries']['detail'], '还有 1 笔未结清或待退款')
        self.assertTrue(items['banking']['ok'])
        denied = self.post('manager', f'projects/{project.pk}/close/', {'reason': '尝试结项'}, status=409)
        self.assertIn('未结清款项', str(denied))
        project.members.add(self.users['production_manager'])
        for role in ('member', 'production_manager', 'finance', 'purchaser'):
            with self.subTest(role=role):
                self.readiness(project, role, status=403)
        outside = Project.objects.create(
            code='OUT-1', name='未参与项目', customer=self.customer, manager=self.users['admin'], status='active'
        )
        self.readiness(outside, status=404)

    def test_receivable_status_is_a_hint_and_never_blocks_shipping(self):
        project = self.ready_project()
        self.stock_and_issue(project)
        entry = project.entries.get(kind='receivable')
        Entry.objects.filter(pk=entry.pk).update(due_date=date.fromisoformat(TODAY) - timedelta(days=5))
        items = self.items(self.readiness(project))
        receivable = items['receivable']
        self.assertEqual((receivable['ok'], receivable['blocking']), (False, False))
        self.assertIn('已逾期 1 笔 ¥10,000.00', receivable['detail'])
        self.assertTrue(all(item['ok'] for item in items.values() if item['blocking']))
        self.deliver(project)


class TaskEditAndDailyNoteTests(ExecutionFixtures, TestCase):
    """正向日常登记的说明选填并缺省为动作名；纠错与逆向动作仍须写明原因。"""

    def setUp(self):
        self.setup_execution()
        self.project = self.active_project()

    def last_audit(self, operation):
        return AuditLog.objects.filter(operation=operation).latest('pk')

    def test_edit_task_changes_only_title_and_requirements_with_audit(self):
        task = self.task(self.project)
        self.project.members.add(self.users['production_manager'])
        self.post('manager', f'tasks/{task.pk}/edit/', {'title': '3D画图', 'description': '明确图档版本'}, status=400)
        self.post('member', f'tasks/{task.pk}/edit/', {'title': '3D画图', 'reason': '越权'}, status=403)
        self.post('production_manager', f'tasks/{task.pk}/edit/', {'title': '3D画图', 'reason': '越权'}, status=403)
        self.post('manager', f'tasks/{task.pk}/edit/', {'title': task.title, 'reason': '没改'}, status=400)
        self.post('manager', f'tasks/{task.pk}/edit/', {'title': '', 'reason': '清空'}, status=400)
        self.post(
            'manager', f'tasks/{task.pk}/edit/', {'title': 'x', 'due_date': TODAY, 'reason': '多字段'}, status=400
        )
        self.post(
            'manager',
            f'tasks/{task.pk}/edit/',
            {'title': '3D画图', 'description': '完成布局并明确图档版本 V2', 'reason': '补充完成要求'},
        )
        task.refresh_from_db()
        self.assertEqual((task.title, task.description), ('3D画图', '完成布局并明确图档版本 V2'))
        record = self.last_audit('task.edit')
        self.assertEqual(record.detail['before'], {'title': 'design', 'description': ''})
        self.assertEqual(record.detail['reason'], '补充完成要求')
        detail = self.clients['member'].get(f'/api/business/tasks/{task.pk}/').data
        self.assertEqual(detail['description'], '完成布局并明确图档版本 V2')
        self.complete(task)
        self.post('manager', f'tasks/{task.pk}/edit/', {'title': '3D画图（定稿）', 'reason': '完成后更正名称'})
        self.post('manager', f'tasks/{task.pk}/cancel/', {'reason': '退出计划'})
        self.post('manager', f'tasks/{task.pk}/edit/', {'title': '已取消', 'reason': '不可改'}, status=409)
        node = Task.objects.create(
            project=self.project,
            kind='shipping',
            milestone='shipping_dispatch',
            title='发货',
            assignee=self.users['manager'],
        )
        self.post('manager', f'tasks/{node.pk}/edit/', {'title': '改名', 'reason': '汇总节点'}, status=409)

    def test_start_complete_and_time_notes_default_to_action_names(self):
        task = self.task(self.project)
        self.post('manager', f'tasks/{task.pk}/start/', {'started_date': TODAY})
        self.assertEqual(self.last_audit('task.start').detail['reason'], '开始任务')
        self.post('manager', f'tasks/{task.pk}/complete/', {'completed_date': TODAY})
        self.assertEqual(self.last_audit('task.complete').detail['reason'], '完成任务')
        other = self.task(self.project, title='另一任务')
        self.post('manager', f'tasks/{other.pk}/complete/', {'reason': '  '})
        self.assertEqual(self.last_audit('task.complete').detail['reason'], '完成任务')
        receipt = self.post(
            'manager', f'tasks/{task.pk}/time/', {'user': self.users['member'].pk, 'hours': '2', 'date': TODAY}
        )
        self.assertEqual(TimeEntry.objects.get(pk=receipt['id']).reason, '登记工时')
        self.post('manager', f'tasks/{task.pk}/time/', {'hours': '1', 'date': TODAY, 'reason': '画装配图'})
        self.assertEqual(TimeEntry.objects.latest('pk').reason, '画装配图')

    def test_corrections_and_reverse_actions_still_require_reason(self):
        task = self.task(self.project)
        self.post('manager', f'tasks/{task.pk}/start/', {'started_date': TODAY})
        self.post(
            'manager',
            f'tasks/{task.pk}/start-date/',
            {'started_date': TODAY, 'expected_started_date': TODAY},
            status=400,
        )
        self.complete(task)
        self.post(
            'manager',
            f'tasks/{task.pk}/completion-date/',
            {'completed_date': TODAY, 'expected_completed_date': TODAY},
            status=400,
        )
        receipt = self.time(task, '2')
        self.post('manager', f'time/{receipt["id"]}/amend/', {'hours': '1', 'date': TODAY}, status=400)
        self.post('manager', f'tasks/{task.pk}/reopen/', {}, status=400)
        other = self.task(self.project, title='待取消')
        self.post('manager', f'tasks/{other.pk}/cancel/', {}, status=400)
        self.post('manager', f'tasks/{other.pk}/assign/', {'assignees': [self.users['member'].pk]}, status=400)
        self.assertEqual(Task.objects.get(pk=other.pk).status, 'open')
        self.assertEqual(Task.objects.get(pk=task.pk).status, 'done')
        self.post(
            'manager',
            f'projects/{self.project.pk}/budget/',
            {'materials': '1', 'labor': '1', 'expenses': '1', 'expected_revision': 0},
            status=400,
        )

    def test_reschedule_changes_only_due_date_with_reason_and_audit(self):
        task = self.task(self.project)
        self.project.members.add(self.users['production_manager'])
        later = (date.fromisoformat(TODAY) + timedelta(days=10)).isoformat()
        path = f'tasks/{task.pk}/reschedule/'
        self.post('manager', path, {'due_date': later}, status=400)
        self.post('manager', path, {'due_date': '', 'reason': '清空'}, status=400)
        self.post('manager', path, {'due_date': later, 'reason': '多字段', 'assignees': [1]}, status=400)
        self.post('member', path, {'due_date': later, 'reason': '越权'}, status=403)
        key = str(uuid.uuid4())
        first = self.post('manager', path, {'due_date': later, 'reason': '客户推迟评审'}, key=key)
        self.assertEqual(self.post('manager', path, {'due_date': later, 'reason': '客户推迟评审'}, key=key), first)
        task.refresh_from_db()
        self.assertEqual((task.due_date.isoformat(), task.assignee), (later, self.users['member']))
        record = AuditLog.objects.filter(operation='task.reschedule').latest('pk')
        self.assertEqual(
            (record.detail['previous_due_date'], record.detail['due_date'], record.detail['reason']),
            (None, later, '客户推迟评审'),
        )
        self.assertEqual(AuditLog.objects.filter(operation='task.reschedule').count(), 1)
        self.post('manager', path, {'due_date': later, 'reason': '同一天'}, status=400)
        self.complete(task)
        self.post('manager', path, {'due_date': TODAY, 'reason': '已完成'}, status=409)

    def test_project_detail_lists_member_names_and_whether_a_sale_exists(self):
        self.project.members.add(self.users['member'], self.users['production_manager'])
        detail = self.clients['manager'].get(f'/api/business/projects/{self.project.pk}/').data
        self.assertTrue(detail['has_sale'])
        people = sorted((self.users['member'], self.users['production_manager']), key=lambda user: user.pk)
        self.assertEqual(detail['member_names'], [user.display_name or user.username for user in people])
        standalone = Project.objects.create(
            code='SOLO', name='独立项目', customer=self.customer, manager=self.users['manager'], status='active'
        )
        row = self.clients['manager'].get(f'/api/business/projects/{standalone.pk}/').data
        self.assertEqual((row['has_sale'], row['member_names'], row['contract_date']), (False, [], None))

    def test_acceptance_forecast_and_supervisors_notes_are_optional(self):
        project = self.ready_project()
        self.stock_and_issue(project)
        delivery = self.deliver(project)
        self.complete(delivery.tasks.get(kind='install'))
        self.post('manager', f'deliveries/{delivery.pk}/accept/', {'date': TODAY})
        self.assertEqual(self.last_audit('delivery.accept').detail['reason'], '交付验收')
        self.post(
            'manager',
            f'projects/{project.pk}/forecast/',
            {'remaining_labor': '0', 'remaining_expenses': '0', 'expected_revision': project.forecast_revision},
        )
        self.assertEqual(self.last_audit('project.forecast').detail['reason'], '更新完工估算')
        project.refresh_from_db()
        self.post(
            'manager',
            f'projects/{project.pk}/task-supervisors/',
            {'supervisors': {'mechanical': self.users['member'].pk}, 'expected_revision': project.supervisor_revision},
        )
        self.assertEqual(self.last_audit('project.supervisors').detail['reason'], '设置专业主管')


class ProjectRiskListTests(ExecutionFixtures, TestCase):
    """项目列表的逾期任务数、只看有逾期和排序；任务的进行中筛选与交付批次进度。"""

    def setUp(self):
        self.setup_execution()

    def rows(self, role='manager', **params):
        response = self.clients[role].get('/api/business/projects/', params)
        self.assertEqual(response.status_code, 200, response.data)
        return response.data['results']

    def test_overdue_count_filter_and_ordering(self):
        late, calm, past = (self.active_project() for _ in range(3))
        today = date.fromisoformat(TODAY)
        Project.objects.filter(pk=late.pk).update(due_date=today + timedelta(days=60))
        Project.objects.filter(pk=calm.pk).update(due_date=today + timedelta(days=30))
        Project.objects.filter(pk=past.pk).update(due_date=today - timedelta(days=3))
        overdue = [self.task(late, title=f'逾期{index}') for index in range(3)]
        Task.objects.filter(pk__in=[task.pk for task in overdue]).update(due_date=today - timedelta(days=1))
        self.complete(overdue[0])
        self.post('manager', f'tasks/{overdue[1].pk}/cancel/', {'reason': '不再需要'})
        Task.objects.filter(pk=self.task(calm, title='明天到期').pk).update(due_date=today + timedelta(days=1))
        Task.objects.filter(pk=self.task(calm, title='今天到期').pk).update(due_date=today)
        counts = {row['id']: row['task_overdue'] for row in self.rows()}
        self.assertEqual((counts[late.pk], counts[calm.pk], counts[past.pk]), (1, 0, 0))
        detail = self.clients['manager'].get(f'/api/business/projects/{late.pk}/').data
        self.assertEqual(detail['task_overdue'], 1)
        self.assertEqual({row['id'] for row in self.rows(overdue='true')}, {late.pk, past.pk})
        self.assertEqual([row['id'] for row in self.rows(ordering='due_date')], [past.pk, calm.pk, late.pk])
        self.assertEqual([row['id'] for row in self.rows(ordering='-due_date')], [late.pk, calm.pk, past.pk])
        self.assertEqual(self.rows(ordering='-task_overdue')[0]['id'], late.pk)
        self.assertEqual([row['id'] for row in self.rows()], [past.pk, calm.pk, late.pk])
        Project.objects.filter(pk=past.pk).update(status='warranty')
        self.assertEqual({row['id'] for row in self.rows(overdue='true')}, {late.pk})
        for params in ({'ordering': 'name'}, {'overdue': 'yes'}):
            with self.subTest(params=params):
                self.assertEqual(self.clients['manager'].get('/api/business/projects/', params).status_code, 400)

    def test_started_filter_and_delivery_stage(self):
        project = self.ready_project()
        started, waiting = self.task(project, title='已开工'), self.task(project, title='未开工')
        self.post('manager', f'tasks/{started.pk}/start/', {'started_date': TODAY})

        def ids(value):
            response = self.clients['manager'].get('/api/business/tasks/', {'project': project.pk, 'started': value})
            return {row['id'] for row in response.data['results']}

        self.assertEqual(ids('true'), {started.pk})
        self.assertIn(waiting.pk, ids('false'))
        self.assertNotIn(started.pk, ids('false'))
        self.assertTrue(all(Task.objects.get(pk=pk).status == 'open' for pk in ids('false')))
        self.complete(started)
        self.complete(waiting)
        self.stock_and_issue(project)
        delivery = self.deliver(project)
        row = self.clients['manager'].get('/api/business/deliveries/', {'project': project.pk}).data['results'][0]
        self.assertEqual(
            (row['stage'], row['installer_name'], row['acceptor_name']), ('installing', 'member', 'manager')
        )
        self.complete(delivery.tasks.get(kind='install'))
        row = self.clients['manager'].get(f'/api/business/deliveries/{delivery.pk}/').data
        self.assertEqual(row['stage'], 'awaiting_acceptance')
        self.post('manager', f'deliveries/{delivery.pk}/accept/', {'date': TODAY, 'reason': '客户签字'})
        self.assertEqual(
            self.clients['manager'].get(f'/api/business/deliveries/{delivery.pk}/').data['stage'], 'accepted'
        )
