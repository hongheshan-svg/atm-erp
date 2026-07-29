"""
Workflow API views.
"""

from django.db import transaction
from django.db.models import Prefetch
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.permission_mixin import PermissionMixin

from .access import can_manage_workflows, visible_workflow_instances
from .models import WorkflowDefinition, WorkflowInstance, WorkflowStep, WorkflowTask
from .serializers import (
    WorkflowDefinitionSerializer,
    WorkflowInstanceSerializer,
    WorkflowStepSerializer,
    WorkflowTaskSerializer,
)
from .services import WorkflowService


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


class ImmutableRuntimeRecordMixin:
    """Runtime workflow records may only change through explicit state-machine actions."""

    def _immutable_response(self):
        return Response({'error': '审批运行记录不可直接修改或删除'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def create(self, request, *args, **kwargs):
        return self._immutable_response()

    def update(self, request, *args, **kwargs):
        return self._immutable_response()

    def partial_update(self, request, *args, **kwargs):
        return self._immutable_response()

    def destroy(self, request, *args, **kwargs):
        return self._immutable_response()


class WorkflowDefinitionViewSet(PermissionMixin, viewsets.ModelViewSet):
    """ViewSet for workflow definitions."""

    permission_module = 'system'
    permission_resource = 'workflow_definition'
    permission_menu_codes = ('workflow:config',)
    queryset = WorkflowDefinition.objects.filter(is_deleted=False)
    serializer_class = WorkflowDefinitionSerializer
    filterset_fields = ['business_type', 'is_active']
    search_fields = ['name', 'code']

    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        definition = self.get_object()
        serializer = self.get_serializer(definition, data={'is_active': True}, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def unpublish(self, request, pk=None):
        definition = self.get_object()
        definition.is_active = False
        definition.updated_by = request.user
        definition.save(update_fields=['is_active', 'updated_by', 'updated_at'])
        return Response(self.get_serializer(definition).data)

    def perform_destroy(self, instance):
        if instance.instances.filter(is_deleted=False).exists():
            raise ValidationError('已有审批实例的流程定义不可删除，请停用后保留审计记录')
        super().perform_destroy(instance)


class WorkflowStepViewSet(PermissionMixin, viewsets.ModelViewSet):
    """ViewSet for workflow steps."""

    permission_module = 'system'
    permission_resource = 'workflow_step'
    permission_menu_codes = ('workflow:config',)
    queryset = WorkflowStep.objects.filter(is_deleted=False)
    serializer_class = WorkflowStepSerializer
    filterset_fields = ['workflow', 'approver_type']

    def perform_destroy(self, instance):
        if instance.workflow.is_active:
            raise ValidationError('已发布的审批流程不可修改，请先停用流程')
        if instance.workflow.instances.filter(is_deleted=False).exists():
            raise ValidationError('已有审批实例的流程步骤不可删除，请创建新流程版本')
        super().perform_destroy(instance)

    @action(detail=False, methods=['post'])
    def reorder(self, request):
        """交换两个审批步骤的顺序。

        前端上移/下移若并发提交两条互换 step_order 的 PUT，会撞
        unique_together(workflow, step_order) 唯一约束导致 IntegrityError。
        这里在单事务内用一个临时序号完成交换，规避唯一键冲突。
        """
        step_id = request.data.get('step_id')
        target_id = request.data.get('target_id')
        if not step_id or not target_id:
            return Response({'error': '请提供 step_id 和 target_id'}, status=status.HTTP_400_BAD_REQUEST)

        queryset = self.filter_queryset(self.get_queryset())
        try:
            step = queryset.get(pk=step_id)
            target = queryset.get(pk=target_id)
        except WorkflowStep.DoesNotExist:
            return Response({'error': '步骤不存在'}, status=status.HTTP_404_NOT_FOUND)

        if step.workflow_id != target.workflow_id:
            return Response({'error': '只能在同一工作流内调整顺序'}, status=status.HTTP_400_BAD_REQUEST)
        if step.workflow.is_active:
            return Response({'error': '已发布的审批流程不可修改，请先停用流程'}, status=status.HTTP_400_BAD_REQUEST)
        if step.workflow.instances.filter(is_deleted=False).exists():
            return Response({'error': '已有审批实例的流程步骤不可调整'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            # 临时序号取该工作流现有最大序号 +1，确保不与任何现存（含软删除）记录冲突
            max_order = (
                WorkflowStep.all_objects.filter(workflow_id=step.workflow_id)
                .order_by('-step_order')
                .values_list('step_order', flat=True)
                .first()
                or 0
            )
            temp_order = max_order + 1
            step_order, target_order = step.step_order, target.step_order

            step.step_order = temp_order
            step.save(update_fields=['step_order', 'updated_at'])
            target.step_order = step_order
            target.save(update_fields=['step_order', 'updated_at'])
            step.step_order = target_order
            step.save(update_fields=['step_order', 'updated_at'])

        return Response({'message': '顺序已更新'})


class WorkflowInstanceViewSet(ImmutableRuntimeRecordMixin, PermissionMixin, viewsets.ModelViewSet):
    """ViewSet for workflow instances."""

    permission_module = 'system'
    permission_resource = 'workflow_instance'
    allow_authenticated_read = True
    skip_data_scope = True
    permission_classes = [IsAuthenticated]
    queryset = WorkflowInstance.objects.filter(is_deleted=False)
    serializer_class = WorkflowInstanceSerializer
    filterset_fields = ['business_type', 'status', 'submitter']
    search_fields = ['business_no']

    def check_permissions(self, request):
        if getattr(self, 'action', None) in {'my_submitted', 'history', 'progress', 'by_business', 'withdraw'}:
            return viewsets.ModelViewSet.check_permissions(self, request)
        return super().check_permissions(request)

    def check_object_permissions(self, request, obj):
        if request.method in ('GET', 'HEAD', 'OPTIONS') or getattr(self, 'action', None) == 'withdraw':
            return viewsets.ModelViewSet.check_object_permissions(self, request, obj)
        return super().check_object_permissions(request, obj)

    def get_queryset(self):
        # 序列化器内联了 tasks/events 且 total_steps 会按对象数步骤，只 select_related
        # 会让列表页每条实例再发若干查询（任务、事件、步骤计数），条数一多就超时。
        queryset = self.queryset.select_related('workflow', 'submitter').prefetch_related(
            'tasks__step',
            'tasks__assignee',
            'tasks__instance__workflow',
            'tasks__instance__submitter',
            'events__actor',
            Prefetch(
                'workflow__steps',
                queryset=WorkflowStep.objects.filter(is_deleted=False),
                to_attr='active_steps',
            ),
        )
        return visible_workflow_instances(queryset, self.request.user)

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

        workflows = visible_workflow_instances(
            WorkflowService.get_workflow_history(business_type, int(business_id)),
            request.user,
        )
        serializer = self.get_serializer(workflows, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def progress(self, request, pk=None):
        """Get workflow progress with all definition steps and task status."""
        instance = self.get_object()
        definition = instance.workflow
        all_steps = definition.steps.filter(is_deleted=False).order_by('step_order')
        tasks = instance.tasks.filter(is_deleted=False).select_related('step', 'assignee')

        task_map = {}
        for task in tasks:
            task_map.setdefault(task.step_id, []).append(task)

        nodes = []
        for step in all_steps:
            step_tasks = task_map.get(step.id, [])
            node = {
                'step_order': step.step_order,
                'step_name': step.name,
                'approver_type': step.approver_type,
                'approver_type_display': step.get_approver_type_display(),
            }
            if step_tasks:
                pending = [task for task in step_tasks if task.status == 'PENDING']
                approved = [task for task in step_tasks if task.status == 'APPROVED']
                rejected = [task for task in step_tasks if task.status == 'REJECTED']
                returned = [task for task in step_tasks if task.status == 'RETURNED']
                if pending:
                    aggregate_status = 'PENDING'
                elif approved:
                    aggregate_status = 'APPROVED'
                elif returned:
                    aggregate_status = 'RETURNED'
                elif rejected:
                    aggregate_status = 'REJECTED'
                else:
                    aggregate_status = 'SKIPPED'
                representative = (pending or approved or returned or rejected or step_tasks)[0]
                node.update(
                    {
                        'task_id': representative.id,
                        'status': aggregate_status,
                        'status_display': dict(WorkflowTask.STATUS_CHOICES).get(aggregate_status, aggregate_status),
                        'assignee_name': '、'.join(
                            task.assignee.get_full_name() or task.assignee.username for task in step_tasks
                        ),
                        'action_time': representative.action_time,
                        'comment': representative.comment,
                        'created_at': representative.created_at,
                        'tasks': [
                            {
                                'task_id': task.id,
                                'status': task.status,
                                'status_display': task.get_status_display(),
                                'assignee_id': task.assignee_id,
                                'assignee_name': task.assignee.get_full_name() or task.assignee.username,
                                'action_time': task.action_time,
                                'comment': task.comment,
                                'created_at': task.created_at,
                            }
                            for task in step_tasks
                        ],
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
                        'tasks': [],
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
            visible_workflow_instances(
                WorkflowInstance.objects.filter(
                    business_type=business_type,
                    business_id=int(business_id),
                    is_deleted=False,
                ),
                request.user,
            )
            .order_by('-submit_time')
            .first()
        )

        if not instance:
            return Response({'instance': None})

        serializer = self.get_serializer(instance)
        return Response({'instance': serializer.data})

    @action(detail=True, methods=['delete'])
    def admin_delete(self, request, pk=None):
        """Workflow runtime audit records are immutable."""
        return self._immutable_response()

    @action(detail=False, methods=['post'])
    def batch_delete(self, request):
        """Workflow runtime audit records are immutable."""
        return self._immutable_response()


class WorkflowTaskViewSet(ImmutableRuntimeRecordMixin, PermissionMixin, viewsets.ModelViewSet):
    """ViewSet for workflow tasks."""

    permission_module = 'system'
    permission_resource = 'workflow_task'
    allow_authenticated_read = True
    skip_data_scope = True
    permission_classes = [IsAuthenticated]
    queryset = WorkflowTask.objects.filter(is_deleted=False)
    serializer_class = WorkflowTaskSerializer
    filterset_fields = ['instance', 'assignee', 'status']

    def check_permissions(self, request):
        if getattr(self, 'action', None) in {
            'my_pending',
            'pending_count',
            'approve',
            'reject',
            'reject_to_step',
        }:
            return viewsets.ModelViewSet.check_permissions(self, request)
        return super().check_permissions(request)

    def check_object_permissions(self, request, obj):
        if getattr(self, 'action', None) in {'approve', 'reject', 'reject_to_step'}:
            return viewsets.ModelViewSet.check_object_permissions(self, request, obj)
        return super().check_object_permissions(request, obj)

    def get_queryset(self):
        # 序列化器读 instance.submitter.get_full_name，缺它会让待办列表逐条多查一次用户
        queryset = self.queryset.select_related(
            'instance', 'instance__workflow', 'instance__submitter', 'step', 'assignee'
        )
        if can_manage_workflows(self.request.user):
            return queryset
        return queryset.filter(assignee=self.request.user)

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

    @action(detail=True, methods=['post'])
    def reject_to_step(self, request, pk=None):
        """退回到指定的更早步骤（而非整单拒绝），实例保持 IN_PROGRESS 重新审批。"""
        task = self.get_object()
        target = request.data.get('target_step_order')
        comment = request.data.get('comment', '')
        if not comment:
            return Response({'error': '退回时必须填写原因'}, status=status.HTTP_400_BAD_REQUEST)
        success, message = WorkflowService.reject_to_step(task, target, request.user, comment)
        if success:
            return Response({'message': message})
        return Response({'error': message}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['delete'])
    def admin_delete(self, request, pk=None):
        """Workflow runtime audit records are immutable."""
        return self._immutable_response()

    @action(detail=False, methods=['post'])
    def batch_delete(self, request):
        """Workflow runtime audit records are immutable."""
        return self._immutable_response()
