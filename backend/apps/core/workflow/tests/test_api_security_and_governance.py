from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.accounts.models import Role
from apps.core.workflow.flow_visualization import WorkflowDetailView
from apps.core.workflow.models import WorkflowDefinition, WorkflowStep, WorkflowTask
from apps.core.workflow.serializers import WorkflowDefinitionSerializer, WorkflowStepSerializer
from apps.core.workflow.services import WorkflowService
from apps.core.workflow.views import WorkflowInstanceViewSet, WorkflowTaskViewSet

User = get_user_model()


class WorkflowApiSecurityTest(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.submitter = User.objects.create_user(
            username='api_submitter',
            password='x',
            employee_id='api_submitter',
        )
        self.approver = User.objects.create_user(
            username='api_approver',
            password='x',
            employee_id='api_approver',
        )
        self.outsider = User.objects.create_user(
            username='api_outsider',
            password='x',
            employee_id='api_outsider',
        )
        workflow = WorkflowDefinition.objects.create(
            name='api workflow',
            code='api_workflow',
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
        with patch.object(WorkflowService, '_notify_assignee', return_value=None):
            self.instance, _ = WorkflowService.start_workflow(
                'PURCHASE_REQUEST',
                301,
                'PR-API',
                self.submitter,
            )
        self.task = WorkflowTask.objects.get(instance=self.instance)

    def _request(self, method, path, user, data=None):
        request = getattr(self.factory, method)(path, data or {}, format='json')
        force_authenticate(request, user=user)
        return request

    def test_assignee_without_system_permission_can_approve_own_task(self):
        request = self._request('post', f'/tasks/{self.task.pk}/approve/', self.approver)
        view = WorkflowTaskViewSet.as_view({'post': 'approve'})

        with patch.object(WorkflowService, '_on_workflow_complete', return_value=None):
            response = view(request, pk=self.task.pk)

        self.assertEqual(response.status_code, 200)

    def test_outsider_cannot_retrieve_another_users_task(self):
        request = self._request('get', f'/tasks/{self.task.pk}/', self.outsider)
        view = WorkflowTaskViewSet.as_view({'get': 'retrieve'})

        response = view(request, pk=self.task.pk)

        self.assertEqual(response.status_code, 404)

    def test_submitter_without_system_permission_can_withdraw_own_instance(self):
        request = self._request('post', f'/instances/{self.instance.pk}/withdraw/', self.submitter)
        view = WorkflowInstanceViewSet.as_view({'post': 'withdraw'})

        with patch.object(WorkflowService, '_on_workflow_complete', return_value=None):
            response = view(request, pk=self.instance.pk)

        self.assertEqual(response.status_code, 200)

    def test_outsider_cannot_view_workflow_visualization_detail(self):
        request = self._request('get', f'/visualization/{self.instance.pk}/', self.outsider)

        response = WorkflowDetailView.as_view()(request, workflow_id=self.instance.pk)

        self.assertEqual(response.status_code, 404)

    def test_workflow_instance_cannot_be_deleted_even_by_superuser(self):
        admin = User.objects.create_superuser(
            username='workflow_delete_admin',
            password='x',
            employee_id='workflow_delete_admin',
        )
        request = self._request('delete', f'/instances/{self.instance.pk}/', admin)
        view = WorkflowInstanceViewSet.as_view({'delete': 'destroy'})

        response = view(request, pk=self.instance.pk)

        self.assertEqual(response.status_code, 405)
        self.assertTrue(type(self.instance).objects.filter(pk=self.instance.pk).exists())

    def test_workflow_task_admin_delete_is_disabled(self):
        admin = User.objects.create_superuser(
            username='workflow_task_delete_admin',
            password='x',
            employee_id='workflow_task_delete_admin',
        )
        request = self._request('delete', f'/tasks/{self.task.pk}/admin_delete/', admin)
        view = WorkflowTaskViewSet.as_view({'delete': 'admin_delete'})

        response = view(request, pk=self.task.pk)

        self.assertEqual(response.status_code, 405)
        self.assertTrue(WorkflowTask.objects.filter(pk=self.task.pk).exists())

    def test_workflow_instance_status_cannot_be_patched(self):
        admin = User.objects.create_superuser(
            username='workflow_instance_patch_admin',
            password='x',
            employee_id='workflow_instance_patch_admin',
        )
        request = self._request(
            'patch',
            f'/instances/{self.instance.pk}/',
            admin,
            {'status': 'APPROVED'},
        )
        view = WorkflowInstanceViewSet.as_view({'patch': 'partial_update'})

        response = view(request, pk=self.instance.pk)

        self.assertEqual(response.status_code, 405)
        self.instance.refresh_from_db()
        self.assertEqual(self.instance.status, 'PENDING')

    def test_workflow_task_status_cannot_be_patched(self):
        admin = User.objects.create_superuser(
            username='workflow_task_patch_admin',
            password='x',
            employee_id='workflow_task_patch_admin',
        )
        request = self._request(
            'patch',
            f'/tasks/{self.task.pk}/',
            admin,
            {'status': 'APPROVED'},
        )
        view = WorkflowTaskViewSet.as_view({'patch': 'partial_update'})

        response = view(request, pk=self.task.pk)

        self.assertEqual(response.status_code, 405)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, 'PENDING')


class WorkflowDefinitionGovernanceTest(TestCase):
    def setUp(self):
        self.approver = User.objects.create_user(
            username='governance_approver',
            password='x',
            employee_id='governance_approver',
        )

    def test_definition_cannot_be_published_without_steps(self):
        workflow = WorkflowDefinition.objects.create(
            name='draft workflow',
            code='draft_workflow',
            business_type='PURCHASE_REQUEST',
            is_active=False,
        )
        serializer = WorkflowDefinitionSerializer(
            workflow,
            data={
                'name': workflow.name,
                'code': workflow.code,
                'business_type': workflow.business_type,
                'amount_threshold': None,
                'description': '',
                'is_active': True,
            },
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn('is_active', serializer.errors)

    def test_create_requesting_active_definition_is_saved_as_draft(self):
        serializer = WorkflowDefinitionSerializer(
            data={
                'name': 'new draft',
                'code': 'new_draft',
                'business_type': 'PURCHASE_REQUEST',
                'amount_threshold': None,
                'description': '',
                'is_active': True,
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        workflow = serializer.save()
        self.assertFalse(workflow.is_active)

    def test_duplicate_threshold_cannot_be_published(self):
        active = WorkflowDefinition.objects.create(
            name='active default',
            code='active_default',
            business_type='PURCHASE_REQUEST',
            amount_threshold=None,
            is_active=True,
        )
        WorkflowStep.objects.create(
            workflow=active,
            step_order=1,
            name='审批',
            approver_type='USER',
            approver_user=self.approver,
        )
        draft = WorkflowDefinition.objects.create(
            name='duplicate default',
            code='duplicate_default',
            business_type='PURCHASE_REQUEST',
            amount_threshold=None,
            is_active=False,
        )
        WorkflowStep.objects.create(
            workflow=draft,
            step_order=1,
            name='审批',
            approver_type='USER',
            approver_user=self.approver,
        )
        serializer = WorkflowDefinitionSerializer(draft, data={'is_active': True}, partial=True)

        self.assertFalse(serializer.is_valid())
        self.assertIn('is_active', serializer.errors)

    def test_active_definition_steps_are_immutable(self):
        workflow = WorkflowDefinition.objects.create(
            name='published workflow',
            code='published_workflow',
            business_type='PURCHASE_REQUEST',
            is_active=True,
        )
        step = WorkflowStep.objects.create(
            workflow=workflow,
            step_order=1,
            name='原审批步骤',
            approver_type='USER',
            approver_user=self.approver,
        )
        serializer = WorkflowStepSerializer(
            step,
            data={
                'workflow': workflow.id,
                'step_order': 1,
                'name': '被篡改的步骤',
                'approver_type': 'USER',
                'approver_user': self.approver.id,
                'action_type': 'APPROVE',
                'timeout_hours': 24,
                'can_reject': True,
            },
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn('workflow', serializer.errors)

    def test_published_definition_route_cannot_change_until_unpublished(self):
        workflow = WorkflowDefinition.objects.create(
            name='published route',
            code='published_route',
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
        serializer = WorkflowDefinitionSerializer(
            workflow,
            data={'amount_threshold': 1000},
            partial=True,
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn('amount_threshold', serializer.errors)

    def test_definition_metadata_is_frozen_after_instance_started(self):
        submitter = User.objects.create_user(
            username='governance_submitter',
            password='x',
            employee_id='governance_submitter',
        )
        workflow = WorkflowDefinition.objects.create(
            name='historical name',
            code='historical_definition',
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
        with patch.object(WorkflowService, '_notify_assignee', return_value=None):
            WorkflowService.start_workflow(
                'PURCHASE_REQUEST',
                302,
                'PR-HISTORY',
                submitter,
            )
        serializer = WorkflowDefinitionSerializer(
            workflow,
            data={'name': 'rewritten history'},
            partial=True,
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn('name', serializer.errors)

    def test_step_requires_configured_user_approver(self):
        workflow = WorkflowDefinition.objects.create(
            name='editable workflow',
            code='editable_workflow',
            business_type='PURCHASE_REQUEST',
            is_active=False,
        )
        serializer = WorkflowStepSerializer(
            data={
                'workflow': workflow.id,
                'step_order': 1,
                'name': '缺少用户',
                'approver_type': 'USER',
                'approver_user': None,
                'action_type': 'APPROVE',
                'timeout_hours': 24,
                'can_reject': True,
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn('approver_user', serializer.errors)

    def test_step_rejects_non_positive_timeout_and_order(self):
        workflow = WorkflowDefinition.objects.create(
            name='invalid step workflow',
            code='invalid_step_workflow',
            business_type='PURCHASE_REQUEST',
            is_active=False,
        )
        serializer = WorkflowStepSerializer(
            data={
                'workflow': workflow.id,
                'step_order': 0,
                'name': '非法步骤',
                'approver_type': 'USER',
                'approver_user': self.approver.id,
                'action_type': 'APPROVE',
                'timeout_hours': 0,
                'can_reject': True,
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn('step_order', serializer.errors)
        self.assertIn('timeout_hours', serializer.errors)


class WorkflowParallelProgressTest(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.submitter = User.objects.create_user(
            username='parallel_submitter',
            password='x',
            employee_id='parallel_submitter',
        )
        role = Role.objects.create(name='并行会签组', code='parallel_progress')
        for index in range(2):
            user = User.objects.create_user(
                username=f'parallel_approver_{index}',
                password='x',
                employee_id=f'parallel_approver_{index}',
            )
            user.roles.add(role)
        workflow = WorkflowDefinition.objects.create(
            name='parallel workflow',
            code='parallel_workflow',
            business_type='PURCHASE_REQUEST',
            is_active=True,
        )
        WorkflowStep.objects.create(
            workflow=workflow,
            step_order=1,
            name='并行会签',
            approver_type='ROLE',
            approver_role=role,
            action_type='COUNTERSIGN',
        )
        with patch.object(WorkflowService, '_notify_assignee', return_value=None):
            self.instance, _ = WorkflowService.start_workflow(
                'PURCHASE_REQUEST',
                401,
                'PR-PARALLEL',
                self.submitter,
            )

    def _get(self, path):
        request = self.factory.get(path)
        force_authenticate(request, user=self.submitter)
        return request

    def test_progress_returns_every_parallel_task(self):
        view = WorkflowInstanceViewSet.as_view({'get': 'progress'})

        response = view(self._get(f'/instances/{self.instance.pk}/progress/'), pk=self.instance.pk)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['nodes'][0]['tasks']), 2)

    def test_visualization_draws_same_step_tasks_in_parallel(self):
        response = WorkflowDetailView.as_view()(
            self._get(f'/visualization/{self.instance.pk}/'),
            workflow_id=self.instance.pk,
        )

        self.assertEqual(response.status_code, 200)
        task_ids = list(self.instance.tasks.order_by('id').values_list('id', flat=True))
        edges = {(edge['source'], edge['target']) for edge in response.data['graph']['edges']}
        self.assertIn(('start', f'step_{task_ids[0]}'), edges)
        self.assertIn(('start', f'step_{task_ids[1]}'), edges)
        self.assertNotIn((f'step_{task_ids[0]}', f'step_{task_ids[1]}'), edges)
