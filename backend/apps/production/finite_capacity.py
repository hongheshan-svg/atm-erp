"""
APS Finite Capacity Scheduling
"""

from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.db import models
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.models import BaseModel
from apps.core.permission_mixin import PermissionMixin


class FiniteCapacityPlan(BaseModel):
    STATUS_CHOICES = [
        ('draft', '草稿'),
        ('running', '运行中'),
        ('completed', '已完成'),
        ('published', '已发布'),
        ('failed', '失败'),
    ]
    STRATEGY_CHOICES = [
        ('earliest_start', '最早开始'),
        ('latest_start', '最迟开始'),
        ('bottleneck_first', '瓶颈优先'),
        ('priority_based', '优先级排序'),
    ]

    name = models.CharField(max_length=200, verbose_name='计划名称')
    plan_start = models.DateField(verbose_name='计划开始日期')
    plan_end = models.DateField(verbose_name='计划结束日期')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name='状态')
    scheduling_strategy = models.CharField(
        max_length=30, choices=STRATEGY_CHOICES, default='earliest_start', verbose_name='排程策略'
    )
    consider_setup_time = models.BooleanField(default=True, verbose_name='考虑换型时间')
    total_tasks = models.IntegerField(default=0, verbose_name='任务总数')
    avg_utilization = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00'), verbose_name='平均利用率'
    )

    class Meta:
        db_table = 'production_finite_capacity_plan'
        ordering = ['-created_at']
        verbose_name = '有限产能计划'
        verbose_name_plural = '有限产能计划'

    def __str__(self):
        return self.name


class ScheduledTask(BaseModel):
    STATUS_CHOICES = [
        ('pending', '待排'),
        ('scheduled', '已排'),
        ('in_progress', '进行中'),
        ('completed', '已完成'),
    ]

    plan = models.ForeignKey(
        FiniteCapacityPlan, on_delete=models.CASCADE, related_name='tasks', verbose_name='排程计划'
    )
    work_order = models.CharField(max_length=100, verbose_name='工单号')
    resource = models.CharField(max_length=200, verbose_name='资源')
    start_time = models.DateTimeField(verbose_name='开始时间')
    end_time = models.DateTimeField(verbose_name='结束时间')
    setup_time_minutes = models.IntegerField(default=0, verbose_name='换型时间(分钟)')
    processing_time_minutes = models.IntegerField(verbose_name='加工时间(分钟)')
    sequence = models.IntegerField(default=0, verbose_name='排序')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='状态')

    class Meta:
        db_table = 'production_scheduled_task'
        ordering = ['plan', 'resource', 'sequence']
        verbose_name = '排程任务'
        verbose_name_plural = '排程任务'

    def __str__(self):
        return f'{self.work_order} @ {self.resource}'


class FiniteCapacityScheduler:
    """有限产能排程引擎（启发式，无外部求解器依赖）。

    与旧版相比：
    - scheduling_strategy 真正生效，决定任务的排入顺序：
        earliest_start  最早开始：按请求开始时间升序（早者先占用产能）。
        latest_start    最迟开始：按请求开始时间降序（晚者先占用产能）。
        bottleneck_first瓶颈优先：先排负载最重(加工分钟合计最大)的资源上的任务。
        priority_based  优先级：按 sequence 升序（序号小=优先）。
    - 每个资源上前向排程，禁止重叠；consider_setup_time 时在相邻任务间计入换型时间。
    - avg_utilization 用真实数据计算：各资源(加工分钟 / 活动跨度) 的均值，夹在 [0,100]。
    """

    @staticmethod
    def _order_tasks(tasks, strategy):
        """按排程策略返回任务的排入顺序（不改变数据库，仅决定处理次序）。"""
        tasks = list(tasks)
        if strategy == 'latest_start':
            return sorted(tasks, key=lambda t: (t.start_time, t.sequence), reverse=True)
        if strategy == 'priority_based':
            return sorted(tasks, key=lambda t: (t.sequence, t.start_time))
        if strategy == 'bottleneck_first':
            load = defaultdict(float)
            for t in tasks:
                load[t.resource] += float(t.processing_time_minutes or 0)
            return sorted(tasks, key=lambda t: (-load[t.resource], t.resource, t.sequence, t.start_time))
        # earliest_start（默认）
        return sorted(tasks, key=lambda t: (t.start_time, t.sequence))

    @staticmethod
    def run_schedule(plan_id):
        plan = FiniteCapacityPlan.objects.get(id=plan_id, is_deleted=False)
        plan.status = 'running'
        plan.save(update_fields=['status'])

        try:
            tasks = ScheduledTask.objects.filter(plan=plan, is_deleted=False)
            ordered = FiniteCapacityScheduler._order_tasks(tasks, plan.scheduling_strategy)

            resource_end = {}
            busy_minutes = defaultdict(float)
            res_min_start = {}
            res_max_end = {}

            for seq, task in enumerate(ordered, start=1):
                resource_key = task.resource
                proc = task.processing_time_minutes or 0
                setup = task.setup_time_minutes or 0

                start = task.start_time
                prev_end = resource_end.get(resource_key)
                if prev_end is not None and prev_end > start:
                    start = prev_end
                # 换型时间仅在与前一任务衔接时计入（首个任务不计）
                if plan.consider_setup_time and prev_end is not None and setup:
                    start = start + timedelta(minutes=setup)
                end = start + timedelta(minutes=proc)

                task.start_time = start
                task.end_time = end
                # 记录策略决定的排入次序，便于甘特图/前端稳定排序
                task.sequence = seq
                task.status = 'scheduled'
                task.save()

                resource_end[resource_key] = end
                busy_minutes[resource_key] += float(proc)
                if resource_key not in res_min_start or start < res_min_start[resource_key]:
                    res_min_start[resource_key] = start
                if resource_key not in res_max_end or end > res_max_end[resource_key]:
                    res_max_end[resource_key] = end

            # 真实平均利用率：各资源 busy / span 的均值（span 含换型与空闲）
            utils = []
            for resource_key, busy in busy_minutes.items():
                span = (res_max_end[resource_key] - res_min_start[resource_key]).total_seconds() / 60.0
                pct = (busy / span * 100.0) if span > 0 else 0.0
                utils.append(max(0.0, min(100.0, pct)))
            avg_util = sum(utils) / len(utils) if utils else 0.0

            plan.total_tasks = len(ordered)
            plan.avg_utilization = Decimal(str(round(avg_util, 2)))
            plan.status = 'completed'
            plan.save(update_fields=['total_tasks', 'avg_utilization', 'status'])
        except Exception as e:
            plan.status = 'failed'
            plan.save(update_fields=['status'])
            raise e
        return plan


# ─── Serializers ────────────────────────────────────────────────


class ScheduledTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScheduledTask
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class FiniteCapacityPlanSerializer(serializers.ModelSerializer):
    tasks = ScheduledTaskSerializer(many=True, read_only=True)

    class Meta:
        model = FiniteCapacityPlan
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'total_tasks', 'avg_utilization']


# ─── ViewSets ───────────────────────────────────────────────────


class FiniteCapacityPlanViewSet(
    PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet
):
    permission_module = 'production'
    permission_resource = 'finite_capacity_plan'
    serializer_class = FiniteCapacityPlanSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return FiniteCapacityPlan.objects.filter(is_deleted=False)

    @action(detail=True, methods=['post'])
    def run_schedule(self, request, pk=None):
        try:
            plan = FiniteCapacityScheduler.run_schedule(pk)
            return Response(FiniteCapacityPlanSerializer(plan).data)
        except FiniteCapacityPlan.DoesNotExist:
            return Response({'error': '计划不存在'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        plan = self.get_object()
        if plan.status != 'completed':
            return Response({'error': '只有已完成的计划才能发布'}, status=status.HTTP_400_BAD_REQUEST)
        plan.status = 'published'
        plan.save(update_fields=['status'])
        return Response(FiniteCapacityPlanSerializer(plan).data)

    @action(detail=True, methods=['get'])
    def gantt_data(self, request, pk=None):
        """获取排程甘特图数据"""
        plan = self.get_object()
        tasks = plan.tasks.filter(is_deleted=False).order_by('start_time')
        gantt_items = []
        for task in tasks:
            gantt_items.append({
                'id': task.id,
                'name': task.work_order,
                'start': task.start_time.isoformat() if task.start_time else None,
                'end': task.end_time.isoformat() if task.end_time else None,
                'resource': task.resource,
                'status': task.status,
                'sequence': task.sequence,
            })
        return Response({
            'plan': FiniteCapacityPlanSerializer(plan).data,
            'gantt_items': gantt_items,
        })


class ScheduledTaskViewSet(
    PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet
):
    permission_module = 'production'
    permission_resource = 'scheduled_task'
    serializer_class = ScheduledTaskSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = ScheduledTask.objects.filter(is_deleted=False)
        plan_id = self.request.query_params.get('plan_id')
        if plan_id:
            qs = qs.filter(plan_id=plan_id)
        return qs
