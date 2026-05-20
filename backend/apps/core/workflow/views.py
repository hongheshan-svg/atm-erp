"""
Workflow API views.
"""

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permission_service import has_permission

from .models import WorkflowDefinition, WorkflowInstance, WorkflowStep, WorkflowTask
from .serializers import (
    WorkflowDefinitionSerializer,
    WorkflowInstanceSerializer,
    WorkflowStepSerializer,
    WorkflowTaskSerializer,
)
from .services import WorkflowService


def is_admin(user):
    """Check if user can manage workflow configuration."""
    if user.is_superuser:
        return True
    return has_permission(user, 'workflow:config')


def _get_step_approver_label(step):
    """Get a display label for who will approve this step."""
    if step.approver_type == 'USER' and step.approver_user:
        return step.approver_user.get_full_name() or step.approver_user.username
    if step.approver_type == 'ROLE' and step.approver_role:
        return f'{step.approver_role.name}(角色)'
    labels = {
        'DEPARTMENT_MANAGER': '部门经理',
        'PROJECT_MANAGER': '项目经理',
        'SUPERIOR': '上级主管',
    }
    return labels.get(step.approver_type, '待分配')


class WorkflowDefinitionViewSet(viewsets.ModelViewSet):
    """ViewSet for workflow definitions."""

    queryset = WorkflowDefinition.objects.filter(is_deleted=False)
    serializer_class = WorkflowDefinitionSerializer
    filterset_fields = ['business_type', 'is_active']
    search_fields = ['name', 'code']


class WorkflowStepViewSet(viewsets.ModelViewSet):
    """ViewSet for workflow steps."""

    queryset = WorkflowStep.objects.filter(is_deleted=False)
    serializer_class = WorkflowStepSerializer
    filterset_fields = ['workflow', 'approver_type']


class WorkflowInstanceViewSet(viewsets.ModelViewSet):
    """ViewSet for workflow instances."""

    queryset = WorkflowInstance.objects.filter(is_deleted=False)
    serializer_class = WorkflowInstanceSerializer
    filterset_fields = ['business_type', 'status', 'submitter']
    search_fields = ['business_no']

    @action(detail=False, methods=['get'])
    def my_submitted(self, request):
        """Get workflows submitted by current user."""
        workflows = WorkflowService.get_submitted_workflows(request.user)
        serializer = self.get_serializer(workflows, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def withdraw(self, request, pk=None):
        """Withdraw a workflow instance."""
        instance = self.get_object()
        success, message = WorkflowService.withdraw_workflow(instance, request.user)

        if success:
            return Response({'message': message})
        return Response({'error': message}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def history(self, request):
        """Get workflow history for a business object."""
        business_type = request.query_params.get('business_type')
        business_id = request.query_params.get('business_id')

        if not business_type or not business_id:
            return Response({'error': '请提供 business_type 和 business_id'}, status=status.HTTP_400_BAD_REQUEST)

        workflows = WorkflowService.get_workflow_history(business_type, int(business_id))
        serializer = self.get_serializer(workflows, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def progress(self, request, pk=None):
        """Get workflow progress with all definition steps and task status."""
        instance = self.get_object()
        definition = instance.workflow
        all_steps = definition.steps.filter(is_deleted=False).order_by('step_order')
        tasks = instance.tasks.filter(is_deleted=False).select_related('step', 'assignee')

        # Build a map of step_id -> task
        task_map = {t.step_id: t for t in tasks}

        nodes = []
        for step in all_steps:
            task = task_map.get(step.id)
            node = {
                'step_order': step.step_order,
                'step_name': step.name,
                'approver_type': step.approver_type,
                'approver_type_display': step.get_approver_type_display(),
            }
            if task:
                node.update(
                    {
                        'task_id': task.id,
                        'status': task.status,
                        'status_display': task.get_status_display(),
                        'assignee_name': task.assignee.get_full_name() if task.assignee else '',
                        'action_time': task.action_time,
                        'comment': task.comment,
                        'created_at': task.created_at,
                    }
                )
            else:
                # Future step - not yet reached
                node.update(
                    {
                        'task_id': None,
                        'status': 'WAITING',
                        'status_display': '等待中',
                        'assignee_name': _get_step_approver_label(step),
                        'action_time': None,
                        'comment': '',
                        'created_at': None,
                    }
                )
            nodes.append(node)

        return Response(
            {
                'id': instance.id,
                'workflow_name': definition.name,
                'business_type': instance.business_type,
                'business_type_display': definition.get_business_type_display(),
                'business_no': instance.business_no,
                'submitter_name': instance.submitter.get_full_name() if instance.submitter else '',
                'submit_time': instance.submit_time,
                'status': instance.status,
                'status_display': instance.get_status_display(),
                'current_step': instance.current_step,
                'total_steps': all_steps.count(),
                'amount': str(instance.amount) if instance.amount else None,
                'completed_at': instance.completed_at,
                'nodes': nodes,
            }
        )

    @action(detail=False, methods=['get'])
    def by_business(self, request):
        """Get latest workflow instance for a business object."""
        business_type = request.query_params.get('business_type')
        business_id = request.query_params.get('business_id')

        if not business_type or not business_id:
            return Response({'error': '请提供 business_type 和 business_id'}, status=status.HTTP_400_BAD_REQUEST)

        instance = (
            WorkflowInstance.objects.filter(business_type=business_type, business_id=int(business_id), is_deleted=False)
            .order_by('-submit_time')
            .first()
        )

        if not instance:
            return Response({'instance': None})

        serializer = self.get_serializer(instance)
        return Response({'instance': serializer.data})

    @action(detail=True, methods=['delete'])
    def admin_delete(self, request, pk=None):
        """Delete a workflow instance (admin only)."""
        if not is_admin(request.user):
            return Response({'error': '只有管理员可以删除审批记录'}, status=status.HTTP_403_FORBIDDEN)

        instance = self.get_object()
        # Soft delete associated tasks
        instance.tasks.update(is_deleted=True)
        # Soft delete instance
        instance.is_deleted = True
        instance.save()

        return Response({'message': '删除成功'})

    @action(detail=False, methods=['post'])
    def batch_delete(self, request):
        """Batch delete workflow instances (admin only)."""
        if not is_admin(request.user):
            return Response({'error': '只有管理员可以删除审批记录'}, status=status.HTTP_403_FORBIDDEN)

        ids = request.data.get('ids', [])
        if not ids:
            return Response({'error': '请提供要删除的记录ID'}, status=status.HTTP_400_BAD_REQUEST)

        instances = WorkflowInstance.objects.filter(id__in=ids, is_deleted=False)
        count = instances.count()

        # Soft delete associated tasks
        WorkflowTask.objects.filter(instance__in=instances).update(is_deleted=True)
        # Soft delete instances
        instances.update(is_deleted=True)

        return Response({'message': f'成功删除 {count} 条记录'})


class WorkflowTaskViewSet(viewsets.ModelViewSet):
    """ViewSet for workflow tasks."""

    queryset = WorkflowTask.objects.filter(is_deleted=False)
    serializer_class = WorkflowTaskSerializer
    filterset_fields = ['instance', 'assignee', 'status']

    @action(detail=False, methods=['get'])
    def my_pending(self, request):
        """Get pending tasks for current user."""
        tasks = WorkflowService.get_pending_tasks(request.user)
        serializer = self.get_serializer(tasks, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def pending_count(self, request):
        """Get count of pending tasks for current user."""
        count = WorkflowService.get_pending_tasks(request.user).count()
        return Response({'count': count})

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve a task."""
        task = self.get_object()
        comment = request.data.get('comment', '')

        success, message = WorkflowService.approve_task(task, request.user, comment)

        if success:
            return Response({'message': message})
        return Response({'error': message}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject a task."""
        task = self.get_object()
        comment = request.data.get('comment', '')

        if not comment:
            return Response({'error': '拒绝时必须填写原因'}, status=status.HTTP_400_BAD_REQUEST)

        success, message = WorkflowService.reject_task(task, request.user, comment)

        if success:
            return Response({'message': message})
        return Response({'error': message}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['delete'])
    def admin_delete(self, request, pk=None):
        """Delete a workflow task (admin only)."""
        if not is_admin(request.user):
            return Response({'error': '只有管理员可以删除审批任务'}, status=status.HTTP_403_FORBIDDEN)

        task = self.get_object()
        task.is_deleted = True
        task.save()

        return Response({'message': '删除成功'})

    @action(detail=False, methods=['post'])
    def batch_delete(self, request):
        """Batch delete workflow tasks (admin only)."""
        if not is_admin(request.user):
            return Response({'error': '只有管理员可以删除审批任务'}, status=status.HTTP_403_FORBIDDEN)

        ids = request.data.get('ids', [])
        if not ids:
            return Response({'error': '请提供要删除的任务ID'}, status=status.HTTP_400_BAD_REQUEST)

        tasks = WorkflowTask.objects.filter(id__in=ids, is_deleted=False)
        count = tasks.count()
        tasks.update(is_deleted=True)

        return Response({'message': f'成功删除 {count} 条任务'})
