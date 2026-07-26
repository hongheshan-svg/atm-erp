from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class WorkflowMigrationDataTest(TransactionTestCase):
    migrate_from = ('workflow', '0006_alter_workflowtask_status')
    migrate_to = ('workflow', '0009_unique_published_definition_route')

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_from])
        old_apps = executor.loader.project_state([self.migrate_from]).apps

        WorkflowDefinition = old_apps.get_model('workflow', 'WorkflowDefinition')
        WorkflowInstance = old_apps.get_model('workflow', 'WorkflowInstance')
        WorkflowStep = old_apps.get_model('workflow', 'WorkflowStep')
        WorkflowTask = old_apps.get_model('workflow', 'WorkflowTask')

        user = get_user_model().objects.create(
            username='migration_user',
            employee_id='migration_user',
            password='x',
            dingtalk_id='',
            wechat_work_id='',
        )
        first_definition = WorkflowDefinition.objects.create(
            name='重复默认流程一',
            code='migration_route_1',
            business_type='PURCHASE_REQUEST',
            is_active=True,
        )
        WorkflowDefinition.objects.create(
            name='重复默认流程二',
            code='migration_route_2',
            business_type='PURCHASE_REQUEST',
            is_active=True,
        )
        step = WorkflowStep.objects.create(
            workflow=first_definition,
            step_order=1,
            name='审批',
            approver_type='USER',
            approver_user_id=user.id,
        )
        first_instance = WorkflowInstance.objects.create(
            workflow=first_definition,
            business_type='PURCHASE_REQUEST',
            business_id=501,
            business_no='PR-MIGRATION',
            submitter_id=user.id,
            status='PENDING',
        )
        duplicate_instance = WorkflowInstance.objects.create(
            workflow=first_definition,
            business_type='PURCHASE_REQUEST',
            business_id=501,
            business_no='PR-MIGRATION',
            submitter_id=user.id,
            status='PENDING',
        )
        WorkflowTask.objects.create(
            instance=first_instance,
            step=step,
            assignee_id=user.id,
            status='PENDING',
        )
        WorkflowTask.objects.create(
            instance=duplicate_instance,
            step=step,
            assignee_id=user.id,
            status='PENDING',
        )

        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_to])
        self.apps = executor.loader.project_state([self.migrate_to]).apps

    def tearDown(self):
        MigrationExecutor(connection).migrate(MigrationExecutor(connection).loader.graph.leaf_nodes())
        super().tearDown()

    def test_duplicate_cleanup_closes_instances_tasks_and_routes(self):
        WorkflowDefinition = self.apps.get_model('workflow', 'WorkflowDefinition')
        WorkflowInstance = self.apps.get_model('workflow', 'WorkflowInstance')
        WorkflowTask = self.apps.get_model('workflow', 'WorkflowTask')

        self.assertEqual(
            WorkflowInstance.objects.filter(
                business_type='PURCHASE_REQUEST',
                business_id=501,
                status='PENDING',
            ).count(),
            1,
        )
        cancelled = WorkflowInstance.objects.get(
            business_type='PURCHASE_REQUEST',
            business_id=501,
            status='CANCELLED',
        )
        self.assertFalse(WorkflowTask.objects.filter(instance=cancelled, status='PENDING').exists())
        self.assertTrue(WorkflowTask.objects.filter(instance=cancelled, status='SKIPPED').exists())
        self.assertEqual(
            WorkflowDefinition.objects.filter(
                business_type='PURCHASE_REQUEST',
                amount_threshold__isnull=True,
                is_active=True,
            ).count(),
            1,
        )
