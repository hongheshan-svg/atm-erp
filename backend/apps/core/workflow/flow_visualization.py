"""
审批流程可视化API
Workflow Visualization API
"""

from django.db.models import Avg, Count, F
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


class WorkflowVisualizationView(APIView):
    """
    审批流程可视化数据API
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, workflow_id=None):
        if workflow_id:
            return self.get_workflow_detail(workflow_id)

        return self.get_workflow_overview()

    def get_workflow_detail(self, workflow_id):
        """获取单个工作流详情"""
        from apps.core.workflow.models import WorkflowInstance, WorkflowStep

        try:
            instance = WorkflowInstance.objects.get(id=workflow_id)
        except WorkflowInstance.DoesNotExist:
            return Response({'error': '工作流不存在'}, status=404)

        # 获取所有步骤
        steps = list(instance.tasks.select_related('step', 'assignee').order_by('step__step_order'))

        # 构建流程图数据
        nodes = []
        edges = []

        # 添加开始节点
        nodes.append({'id': 'start', 'type': 'start', 'label': '开始', 'status': 'completed'})

        prev_node_id = 'start'

        for i, step in enumerate(steps):
            node_id = f'step_{step.id}'

            # 确定节点状态
            if step.status == 'APPROVED':
                status = 'completed'
            elif step.status == 'REJECTED':
                status = 'rejected'
            elif step.status == 'PENDING':
                status = 'current' if i == 0 or steps[i - 1].status in ['APPROVED'] else 'pending'
            else:
                status = 'pending'

            nodes.append(
                {
                    'id': node_id,
                    'type': 'approval',
                    'label': step.step.name or f'审批步骤 {step.step.step_order}',
                    'status': status,
                    'approver': step.assignee.username if step.assignee else None,
                    'approved_at': step.action_time.isoformat() if step.action_time else None,
                    'comments': step.comment,
                }
            )

            # 添加边
            edges.append({'source': prev_node_id, 'target': node_id})

            prev_node_id = node_id

        # 添加结束节点
        end_status = (
            'completed'
            if instance.status == 'APPROVED'
            else ('rejected' if instance.status == 'REJECTED' else 'pending')
        )
        nodes.append({'id': 'end', 'type': 'end', 'label': '结束', 'status': end_status})

        edges.append({'source': prev_node_id, 'target': 'end'})

        return Response(
            {
                'workflow': {
                    'id': instance.id,
                    'workflow_type': instance.business_type,
                    'status': instance.status,
                    'created_at': instance.created_at.isoformat(),
                    'completed_at': instance.completed_at.isoformat() if instance.completed_at else None,
                    'initiator': instance.submitter.username if instance.submitter else None,
                },
                'graph': {'nodes': nodes, 'edges': edges},
            }
        )

    def get_workflow_overview(self):
        """获取工作流概览统计"""
        from apps.core.workflow.models import WorkflowInstance

        today = timezone.now().date()
        this_month_start = today.replace(day=1)

        # 状态统计
        status_stats = WorkflowInstance.objects.values('status').annotate(count=Count('id'))

        # 类型统计
        type_stats = WorkflowInstance.objects.values(workflow_type=F('business_type')).annotate(count=Count('id'))

        # 本月趋势
        from django.db.models.functions import TruncDate

        monthly_trend = (
            WorkflowInstance.objects.filter(created_at__gte=this_month_start)
            .annotate(date=TruncDate('created_at'))
            .values('date')
            .annotate(count=Count('id'))
            .order_by('date')
        )

        # 平均处理时间
        completed_instances = WorkflowInstance.objects.filter(
            status__in=['APPROVED', 'REJECTED'], completed_at__isnull=False
        )

        avg_processing_time = None
        if completed_instances.exists():
            from django.db.models import DurationField, ExpressionWrapper

            avg_time = completed_instances.annotate(
                processing_time=ExpressionWrapper(F('completed_at') - F('created_at'), output_field=DurationField())
            ).aggregate(avg=Avg('processing_time'))

            if avg_time['avg']:
                avg_processing_time = avg_time['avg'].total_seconds() / 3600  # 转换为小时

        return Response(
            {
                'status_stats': list(status_stats),
                'type_stats': list(type_stats),
                'monthly_trend': list(monthly_trend),
                'avg_processing_hours': round(avg_processing_time, 1) if avg_processing_time else None,
                'pending_count': WorkflowInstance.objects.filter(status='PENDING').count(),
                'today_count': WorkflowInstance.objects.filter(created_at__date=today).count(),
            }
        )


class WorkflowStepStatisticsView(APIView):
    """
    审批步骤统计API
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.core.workflow.models import WorkflowTask

        user = request.user

        # 我的待审批（运行时审批任务以 assignee 为处理人）
        my_pending = WorkflowTask.objects.filter(assignee=user, status='PENDING').count()

        # 我已审批
        my_approved = WorkflowTask.objects.filter(assignee=user, status__in=['APPROVED', 'REJECTED']).count()

        # 本月审批量
        today = timezone.now().date()
        this_month_start = today.replace(day=1)

        monthly_approved = WorkflowTask.objects.filter(
            assignee=user, status__in=['APPROVED', 'REJECTED'], action_time__gte=this_month_start
        ).count()

        # 审批效率（平均处理时间）
        from django.db.models import DurationField, ExpressionWrapper

        my_steps = WorkflowTask.objects.filter(assignee=user, action_time__isnull=False).annotate(
            processing_time=ExpressionWrapper(F('action_time') - F('created_at'), output_field=DurationField())
        )

        avg_time = my_steps.aggregate(avg=Avg('processing_time'))
        avg_hours = None
        if avg_time['avg']:
            avg_hours = round(avg_time['avg'].total_seconds() / 3600, 1)

        return Response(
            {
                'pending_count': my_pending,
                'approved_count': my_approved,
                'monthly_approved': monthly_approved,
                'avg_processing_hours': avg_hours,
            }
        )


class WorkflowTimelineView(APIView):
    """
    审批流程时间线API
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, workflow_id):
        from apps.core.workflow.models import WorkflowInstance, WorkflowStep

        try:
            instance = WorkflowInstance.objects.get(id=workflow_id)
        except WorkflowInstance.DoesNotExist:
            return Response({'error': '工作流不存在'}, status=404)

        timeline = []

        # 创建事件
        timeline.append(
            {
                'time': instance.created_at.isoformat(),
                'type': 'create',
                'title': '提交申请',
                'description': f'{instance.submitter.username if instance.submitter else "系统"} 发起了审批申请',
                'status': 'completed',
            }
        )

        # 审批步骤事件
        steps = list(instance.tasks.select_related('step', 'assignee').order_by('step__step_order'))

        for step in steps:
            if step.status == 'APPROVED':
                timeline.append(
                    {
                        'time': step.action_time.isoformat() if step.action_time else None,
                        'type': 'approve',
                        'title': f'{step.step.name or "审批"} - 通过',
                        'description': f'{step.assignee.username if step.assignee else "系统"} 审批通过',
                        'comments': step.comment,
                        'status': 'completed',
                    }
                )
            elif step.status == 'REJECTED':
                timeline.append(
                    {
                        'time': step.action_time.isoformat() if step.action_time else None,
                        'type': 'reject',
                        'title': f'{step.step.name or "审批"} - 驳回',
                        'description': f'{step.assignee.username if step.assignee else "系统"} 驳回了申请',
                        'comments': step.comment,
                        'status': 'rejected',
                    }
                )
            elif step.status == 'PENDING':
                timeline.append(
                    {
                        'time': step.created_at.isoformat() if hasattr(step, 'created_at') else None,
                        'type': 'pending',
                        'title': f'{step.step.name or "审批"} - 待处理',
                        'description': f'等待 {step.assignee.username if step.assignee else "审批人"} 审批',
                        'status': 'pending',
                    }
                )

        # 完成事件
        if instance.status in ['APPROVED', 'REJECTED']:
            timeline.append(
                {
                    'time': instance.completed_at.isoformat() if instance.completed_at else None,
                    'type': 'complete',
                    'title': '审批完成' if instance.status == 'APPROVED' else '审批驳回',
                    'description': '审批流程已结束',
                    'status': 'completed' if instance.status == 'APPROVED' else 'rejected',
                }
            )

        return Response({'workflow_id': workflow_id, 'timeline': timeline})
