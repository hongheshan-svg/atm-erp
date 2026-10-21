"""Permission flags and sensitive projections stay scoped without per-row membership queries."""

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.business.models import BOMLine, Document, Project, PurchaseLine, PurchaseOrder, Task

from .test_commercial_chain import BusinessFixtures


class PermissionQueryTests(BusinessFixtures, TestCase):
    def setUp(self):
        self.setup_business()
        self.projects = Project.objects.bulk_create(
            [
                Project(
                    code=f'QUERY{i}',
                    name=f'查询测试{i}',
                    customer=self.customer,
                    manager=self.users['admin'],
                    status='active',
                )
                for i in range(200)
            ]
        )
        Project.members.through.objects.bulk_create(
            [
                Project.members.through(project_id=project.pk, user_id=self.users[role].pk)
                for project in self.projects
                for role in ('manager', 'mechanical_engineer', 'production_manager')
            ]
        )
        self.outside = Project.objects.create(
            code='OUTSIDE', name='未参与项目', customer=self.customer, manager=self.users['admin'], status='active'
        )

    def assert_bounded(self, resource, role='manager', flag=None):
        counts = []
        for size in (20, 200):
            with CaptureQueriesContext(connection) as queries:
                response = self.clients[role].get(f'/api/business/{resource}/', {'page_size': size})
            self.assertEqual(response.status_code, 200, response.data)
            rows = response.data['results']
            self.assertEqual(len(rows), size)
            self.assertEqual(response.data['count'], 200)
            if flag:
                self.assertTrue(all(row[flag] for row in rows))
            counts.append(len(queries))
        self.assertEqual(counts[0], counts[1], f'{resource} 20/200行查询数: {counts}')

    def test_project_membership_and_money_are_bounded(self):
        self.assert_bounded('projects', flag='can_manage')
        self.assert_bounded('projects', 'production_manager', 'can_manage_production')

    def test_bom_membership_is_bounded(self):
        BOMLine.objects.bulk_create(
            [BOMLine(project=p, item=self.item, quantity=1) for p in [*self.projects, self.outside]]
        )
        self.assert_bounded('bom', 'mechanical_engineer', 'can_edit_bom')

    def test_document_membership_is_bounded(self):
        Document.objects.bulk_create(
            [
                Document(
                    project=p,
                    category='other',
                    file='protected/query.txt',
                    original_name='query.txt',
                    size=1,
                    sha256='0' * 64,
                    created_by=self.users['admin'],
                )
                for p in [*self.projects, self.outside]
            ]
        )
        self.assert_bounded('documents', flag='can_remove')

    def test_purchase_membership_and_prices_are_bounded(self):
        purchases = PurchaseOrder.objects.bulk_create(
            [
                PurchaseOrder(code=f'PQ{i}', project=p, supplier=self.supplier, due_date=timezone.localdate())
                for i, p in enumerate([*self.projects, self.outside])
            ]
        )
        PurchaseLine.objects.bulk_create(
            [PurchaseLine(purchase=p, item=self.item, quantity=1, unit_price=1) for p in purchases]
        )
        self.assert_bounded('purchases', flag='can_manage')

    def test_task_membership_is_bounded(self):
        Task.objects.bulk_create(
            [
                Task(project=p, kind='assembly', title='装配任务', assignee=self.users['member'])
                for p in [*self.projects, self.outside]
            ]
        )
        self.assert_bounded('tasks', 'production_manager', 'can_manage')
