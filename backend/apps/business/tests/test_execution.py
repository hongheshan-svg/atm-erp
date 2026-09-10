import uuid
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from apps.accounts.models import User
from apps.business.models import BOMLine, Delivery, Entry, Project, Stock, StockMove, Task, TimeEntry
from apps.core.models import ActionReceipt

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
        return self.post('member', f'tasks/{task.pk}/complete/', {'reason': '检查完成'}, status=status)

    def time(self, task, hours='1', when=TODAY, status=200):
        return self.post(
            'member', f'tasks/{task.pk}/time/', {'hours': hours, 'date': when, 'reason': '实际工作'}, status=status
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
        self.post('member', f'time/{original}/amend/', {'hours': '2', 'date': TODAY, 'reason': '更正误记'})
        for kind in ('assembly', 'test'):
            self.time(project.tasks.get(kind=kind))
        purchase = self.purchase(project)
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
        self.complete(assembly, status=409)
        design = self.task(project)
        self.complete(design)
        self.complete(assembly)
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
        changed_id = self.post('member', f'time/{time_id}/amend/', {'hours': '2', 'date': TODAY, 'reason': '更正'})[
            'id'
        ]
        self.assertEqual(TimeEntry.objects.get(pk=changed_id).cost, Decimal('100'))
        self.assertEqual(sum(TimeEntry.objects.values_list('hours', flat=True)), Decimal('2'))
        self.assertEqual(sum(TimeEntry.objects.values_list('cost', flat=True)), Decimal('100'))
        self.post(
            'member', f'time/{time_id}/amend/', {'hours': '1', 'date': TODAY, 'reason': '原记录已更正'}, status=409
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
        self.post('manager', f'tasks/{task.pk}/reopen/', {'reason': '原成员已不在项目'}, status=403)
        self.post('manager', f'tasks/{task.pk}/reopen/', {'reason': '经理接手', 'assignee': self.users['manager'].pk})
        task.refresh_from_db()
        self.assertEqual((task.status, task.assignee_id), ('open', self.users['manager'].pk))
