from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase

from apps.accounts.models import Role
from apps.core.models import SystemNotification
from apps.core.workflow.mixins import WorkflowEnforcementMixin
from apps.core.workflow.models import WorkflowDefinition, WorkflowInstance, WorkflowStep, WorkflowTask
from apps.core.workflow.services import WorkflowService

User = get_user_model()


class WorkflowServiceIntegrityTest(TestCase):
    def setUp(self):
        self.submitter = User.objects.create_user(
            username='workflow_submitter',
            password='x',
            employee_id='workflow_submitter',
        )
        self.approver = User.objects.create_user(
            username='workflow_approver',
            password='x',
            employee_id='workflow_approver',
        )
        self.notify_patcher = patch.object(WorkflowService, '_notify_assignee', return_value=None)
        self.notify_patcher.start()
        self.addCleanup(self.notify_patcher.stop)

    def _definition(self, code='workflow_integrity', threshold=None, active=True):
        workflow = WorkflowDefinition.objects.create(
            name=code,
            code=code,
            business_type='PURCHASE_REQUEST',
            amount_threshold=threshold,
            is_active=active,
        )
        WorkflowStep.objects.create(
            workflow=workflow,
            step_order=1,
            name='审批',
            approver_type='USER',
            approver_user=self.approver,
        )
        return workflow

    def test_amount_routing_prefers_highest_matching_threshold_over_default(self):
        default = self._definition('route_default', threshold=None)
        high = self._definition('route_high', threshold=Decimal('10000'))

        selected = WorkflowService.get_workflow_for_business('PURCHASE_REQUEST', Decimal('20000'))

        self.assertEqual(selected, high)
        self.assertNotEqual(selected, default)

    def test_amount_routing_without_amount_uses_only_default_definition(self):
        default = self._definition('route_no_amount_default', threshold=None)
        self._definition('route_no_amount_threshold', threshold=Decimal('10000'))

        selected = WorkflowService.get_workflow_for_business('PURCHASE_REQUEST')

        self.assertEqual(selected, default)

    def test_zero_amount_applies_skip_threshold(self):
        workflow = WorkflowDefinition.objects.create(
            name='zero amount route',
            code='zero_amount_route',
            business_type='PURCHASE_REQUEST',
            is_active=True,
        )
        skipped = WorkflowStep.objects.create(
            workflow=workflow,
            step_order=1,
            name='零金额应跳过',
            approver_type='USER',
            approver_user=self.approver,
            skip_amount_threshold=Decimal('100'),
        )
        next_step = WorkflowStep.objects.create(
            workflow=workflow,
            step_order=2,
            name='下一步',
            approver_type='USER',
            approver_user=self.approver,
        )

        instance, error = WorkflowService.start_workflow(
            'PURCHASE_REQUEST',
            101,
            'PR-ZERO',
            self.submitter,
            Decimal('0'),
        )

        self.assertIsNone(error)
        self.assertFalse(WorkflowTask.objects.filter(instance=instance, step=skipped).exists())
        self.assertTrue(WorkflowTask.objects.filter(instance=instance, step=next_step, status='PENDING').exists())

    def test_workflow_without_steps_is_rejected_instead_of_auto_approved(self):
        WorkflowDefinition.objects.create(
            name='empty workflow',
            code='empty_workflow',
            business_type='PURCHASE_REQUEST',
            is_active=True,
        )

        instance, error = WorkflowService.start_workflow(
            'PURCHASE_REQUEST',
            102,
            'PR-EMPTY',
            self.submitter,
        )

        self.assertIsNone(instance)
        self.assertIn('没有审批步骤', error)
        self.assertFalse(WorkflowInstance.objects.filter(business_id=102).exists())

    def test_unresolvable_assignee_is_rejected_instead_of_falling_back_to_superuser(self):
        workflow = WorkflowDefinition.objects.create(
            name='missing assignee',
            code='missing_assignee',
            business_type='PURCHASE_REQUEST',
            is_active=True,
        )
        WorkflowStep.objects.create(
            workflow=workflow,
            step_order=1,
            name='缺少审批人',
            approver_type='USER',
            approver_user=None,
        )
        User.objects.create_superuser(
            username='workflow_superuser',
            password='x',
            employee_id='workflow_superuser',
        )

        instance, error = WorkflowService.start_workflow(
            'PURCHASE_REQUEST',
            103,
            'PR-NO-ASSIGNEE',
            self.submitter,
        )

        self.assertIsNone(instance)
        self.assertIn('无法确定审批人', error)
        self.assertFalse(WorkflowInstance.objects.filter(business_id=103).exists())

    def test_inactive_user_cannot_be_resolved_as_approver(self):
        inactive = User.objects.create_user(
            username='inactive_approver',
            password='x',
            employee_id='inactive_approver',
            is_active=False,
        )
        workflow = WorkflowDefinition.objects.create(
            name='inactive assignee',
            code='inactive_assignee',
            business_type='PURCHASE_REQUEST',
            is_active=True,
        )
        WorkflowStep.objects.create(
            workflow=workflow,
            step_order=1,
            name='停用审批人',
            approver_type='USER',
            approver_user=inactive,
        )

        instance, error = WorkflowService.start_workflow(
            'PURCHASE_REQUEST',
            110,
            'PR-INACTIVE',
            self.submitter,
        )

        self.assertIsNone(instance)
        self.assertIn('无法确定审批人', error)

    def test_can_reject_false_blocks_full_rejection(self):
        workflow = self._definition('reject_disabled')
        step = workflow.steps.get()
        step.can_reject = False
        step.save(update_fields=['can_reject'])
        instance, _ = WorkflowService.start_workflow(
            'PURCHASE_REQUEST',
            104,
            'PR-NO-REJECT',
            self.submitter,
        )
        task = WorkflowTask.objects.get(instance=instance)

        success, message = WorkflowService.reject_task(task, self.approver, '不应允许')

        self.assertFalse(success)
        self.assertIn('不允许拒绝', message)
        task.refresh_from_db()
        instance.refresh_from_db()
        self.assertEqual(task.status, 'PENDING')
        self.assertEqual(instance.status, 'PENDING')

    def test_skip_assignee_check_cannot_authorize_unassigned_non_superuser(self):
        outsider = User.objects.create_user(
            username='workflow_outsider',
            password='x',
            employee_id='workflow_outsider',
        )
        self._definition('assignee_boundary')
        instance, _ = WorkflowService.start_workflow(
            'PURCHASE_REQUEST',
            112,
            'PR-ASSIGNEE',
            self.submitter,
        )
        task = WorkflowTask.objects.get(instance=instance)

        success, message = WorkflowService.approve_task(
            task,
            outsider,
            skip_assignee_check=True,
        )

        self.assertFalse(success)
        self.assertIn('没有权限', message)
        task.refresh_from_db()
        self.assertEqual(task.status, 'PENDING')

    def test_reject_to_step_rechecks_assignee_after_locking_instance(self):
        replacement = User.objects.create_user(
            username='workflow_replacement',
            password='x',
            employee_id='workflow_replacement',
        )
        workflow = self._definition('return_reassignment')
        WorkflowStep.objects.create(
            workflow=workflow,
            step_order=2,
            name='二审',
            approver_type='USER',
            approver_user=self.approver,
        )
        instance, _ = WorkflowService.start_workflow(
            'PURCHASE_REQUEST',
            113,
            'PR-RETURN-REASSIGN',
            self.submitter,
        )
        first_task = WorkflowTask.objects.get(instance=instance)
        with patch.object(WorkflowService, '_on_workflow_complete', return_value=None):
            success, _ = WorkflowService.approve_task(first_task, self.approver)
        self.assertTrue(success)
        stale_task = WorkflowTask.objects.get(instance=instance, status='PENDING')
        WorkflowTask.objects.filter(pk=stale_task.pk).update(assignee=replacement)

        success, message = WorkflowService.reject_to_step(
            stale_task,
            1,
            self.approver,
            '旧审批人不应再有权限',
        )

        self.assertFalse(success)
        self.assertIn('没有权限', message)
        stale_task.refresh_from_db()
        instance.refresh_from_db()
        self.assertEqual(stale_task.status, 'PENDING')
        self.assertEqual(instance.current_step, 2)

    def test_stale_instance_cannot_withdraw_completed_workflow(self):
        self._definition('stale_withdraw')
        instance, _ = WorkflowService.start_workflow(
            'PURCHASE_REQUEST',
            105,
            'PR-STALE',
            self.submitter,
        )
        stale_instance = WorkflowInstance.objects.get(pk=instance.pk)
        task = WorkflowTask.objects.get(instance=instance)

        with patch.object(WorkflowService, '_on_workflow_complete', return_value=None):
            success, _ = WorkflowService.approve_task(task, self.approver)
            self.assertTrue(success)
            success, message = WorkflowService.withdraw_workflow(stale_instance, self.submitter)

        self.assertFalse(success)
        self.assertIn('进行中的审批', message)
        instance.refresh_from_db()
        self.assertEqual(instance.status, 'APPROVED')

    def test_business_sync_failure_rolls_back_task_and_instance(self):
        self._definition('sync_rollback')
        instance, _ = WorkflowService.start_workflow(
            'PURCHASE_REQUEST',
            106,
            'PR-ROLLBACK',
            self.submitter,
        )
        task = WorkflowTask.objects.get(instance=instance)

        with (
            patch.object(WorkflowService, '_on_workflow_complete', side_effect=RuntimeError('sync failed')),
            patch('apps.core.workflow.services.logger.exception'),
        ):
            success, message = WorkflowService.approve_task(task, self.approver)

        self.assertFalse(success)
        self.assertIn('业务状态同步失败', message)
        task.refresh_from_db()
        instance.refresh_from_db()
        self.assertEqual(task.status, 'PENDING')
        self.assertEqual(instance.status, 'PENDING')

    def test_mixin_does_not_auto_approve_a_start_failure(self):
        class DummyObject:
            id = 107
            status = 'DRAFT'
            total_amount = Decimal('1')
            request_no = 'PR-MIXIN-ERROR'

        class DummyView(WorkflowEnforcementMixin):
            workflow_business_type = 'PURCHASE_REQUEST'
            workflow_no_field = 'request_no'

        with (
            patch.object(WorkflowService, 'start_workflow', return_value=(None, '该单据已有进行中的审批流程')),
            patch('apps.core.workflow.mixins.logger.warning'),
        ):
            result = DummyView().start_workflow_or_auto_approve(DummyObject(), self.submitter)

        self.assertFalse(result['workflow_started'])
        self.assertFalse(result['auto_approved'])
        self.assertEqual(result['new_status'], 'DRAFT')
        self.assertIn('已有进行中', result['message'])

    def test_cancel_workflow_is_idempotent_and_closes_pending_tasks(self):
        self._definition('cancel_workflow')
        instance, _ = WorkflowService.start_workflow(
            'PURCHASE_REQUEST',
            108,
            'PR-CANCEL',
            self.submitter,
        )

        success, message = WorkflowService.cancel_workflow('PURCHASE_REQUEST', 108)
        second_success, second_message = WorkflowService.cancel_workflow('PURCHASE_REQUEST', 108)

        self.assertTrue(success, message)
        self.assertTrue(second_success, second_message)
        instance.refresh_from_db()
        self.assertEqual(instance.status, 'CANCELLED')
        self.assertFalse(instance.tasks.filter(status='PENDING').exists())
        self.assertIsNone(instance.events.get(event_type='CANCELLED').actor)

    def test_lifecycle_actions_create_transactional_domain_audit_events(self):
        self._definition('domain_audit')
        instance, _ = WorkflowService.start_workflow(
            'PURCHASE_REQUEST',
            109,
            'PR-AUDIT',
            self.submitter,
        )
        self.assertTrue(hasattr(instance, 'events'), '审批实例应具备不可变的域审计事件账本')
        self.assertEqual(instance.events.filter(event_type='STARTED', actor=self.submitter).count(), 1)

        task = WorkflowTask.objects.get(instance=instance)
        with patch.object(WorkflowService, '_on_workflow_complete', return_value=None):
            success, _ = WorkflowService.approve_task(task, self.approver, '同意')

        self.assertTrue(success)
        event = instance.events.get(event_type='APPROVED')
        self.assertEqual(event.actor, self.approver)
        self.assertEqual(event.task, task)
        self.assertEqual(event.comment, '同意')
        self.assertEqual(event.to_status, 'APPROVED')

    def test_completed_step_notifies_deduplicated_cc_users_after_commit(self):
        cc_role = Role.objects.create(name='抄送角色', code='workflow_cc_role')
        cc_direct = User.objects.create_user(
            username='cc_direct',
            password='x',
            employee_id='cc_direct',
        )
        cc_role_member = User.objects.create_user(
            username='cc_role_member',
            password='x',
            employee_id='cc_role_member',
        )
        cc_direct.roles.add(cc_role)
        cc_role_member.roles.add(cc_role)
        workflow = self._definition('cc_notifications')
        step = workflow.steps.get()
        step.cc_users.add(cc_direct)
        step.cc_roles.add(cc_role)
        instance, _ = WorkflowService.start_workflow(
            'PURCHASE_REQUEST',
            111,
            'PR-CC',
            self.submitter,
        )
        task = WorkflowTask.objects.get(instance=instance)

        with patch.object(WorkflowService, '_on_workflow_complete', return_value=None):
            with self.captureOnCommitCallbacks(execute=True):
                success, _ = WorkflowService.approve_task(task, self.approver)

        self.assertTrue(success)
        notifications = SystemNotification.objects.filter(
            title='审批步骤已完成',
            message__contains='PR-CC',
        )
        self.assertEqual(notifications.filter(user=cc_direct).count(), 1)
        self.assertEqual(notifications.filter(user=cc_role_member).count(), 1)


class WorkflowStartConcurrencyTest(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.submitter = User.objects.create_user(
            username='concurrent_submitter',
            password='x',
            employee_id='concurrent_submitter',
        )
        self.approver = User.objects.create_user(
            username='concurrent_approver',
            password='x',
            employee_id='concurrent_approver',
        )
        workflow = WorkflowDefinition.objects.create(
            name='concurrent workflow',
            code='concurrent_workflow',
            business_type='PURCHASE_REQUEST',
            is_active=True,
        )
        WorkflowStep.objects.create(
            workflow=workflow,
            step_order=1,
            name='审批',
            approver_type='USER',
            approver_user=self.approver,
        )

    @staticmethod
    def _start(submitter_id):
        close_old_connections()
        try:
            submitter = User.objects.get(pk=submitter_id)
            return WorkflowService.start_workflow(
                'PURCHASE_REQUEST',
                201,
                'PR-CONCURRENT',
                submitter,
            )
        finally:
            close_old_connections()

    def test_concurrent_start_creates_exactly_one_pending_instance(self):
        with patch.object(WorkflowService, '_notify_assignee', return_value=None):
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(self._start, [self.submitter.id, self.submitter.id]))

        self.assertEqual(sum(instance is not None for instance, _ in results), 1)
        self.assertEqual(
            WorkflowInstance.objects.filter(
                business_type='PURCHASE_REQUEST',
                business_id=201,
                status='PENDING',
                is_deleted=False,
            ).count(),
            1,
        )


class WorkflowActionConcurrencyTest(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.submitter = User.objects.create_user(
            username='action_submitter',
            password='x',
            employee_id='action_submitter',
        )
        role = Role.objects.create(name='并发或签组', code='concurrent_or_sign')
        self.approvers = []
        for index in range(2):
            user = User.objects.create_user(
                username=f'action_approver_{index}',
                password='x',
                employee_id=f'action_approver_{index}',
            )
            user.roles.add(role)
            self.approvers.append(user)
        workflow = WorkflowDefinition.objects.create(
            name='concurrent action workflow',
            code='concurrent_action_workflow',
            business_type='PURCHASE_REQUEST',
            is_active=True,
        )
        WorkflowStep.objects.create(
            workflow=workflow,
            step_order=1,
            name='并发或签',
            approver_type='ROLE',
            approver_role=role,
            action_type='OR_SIGN',
        )
        with patch.object(WorkflowService, '_notify_assignee', return_value=None):
            self.instance, _ = WorkflowService.start_workflow(
                'PURCHASE_REQUEST',
                202,
                'PR-CONCURRENT-ACTION',
                self.submitter,
            )

    @staticmethod
    def _approve(task_id, user_id):
        close_old_connections()
        try:
            return WorkflowService.approve_task(
                WorkflowTask.objects.get(pk=task_id),
                User.objects.get(pk=user_id),
            )
        finally:
            close_old_connections()

    def test_concurrent_or_sign_approval_advances_once(self):
        tasks = list(self.instance.tasks.order_by('id'))
        arguments = [(tasks[0].id, tasks[0].assignee_id), (tasks[1].id, tasks[1].assignee_id)]

        with patch.object(WorkflowService, '_on_workflow_complete', return_value=None):
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda values: self._approve(*values), arguments))

        self.instance.refresh_from_db()
        self.assertEqual(self.instance.status, 'APPROVED')
        self.assertEqual(sum(success for success, _ in results), 1)
        self.assertEqual(self.instance.tasks.filter(status='APPROVED').count(), 1)
        self.assertEqual(self.instance.tasks.filter(status='SKIPPED').count(), 1)
        self.assertEqual(self.instance.events.filter(event_type='APPROVED').count(), 1)
