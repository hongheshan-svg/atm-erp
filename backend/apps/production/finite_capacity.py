"""
APS Finite Capacity Scheduling
"""
from decimal import Decimal

from django.db import models
from django.utils import timezone
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.models import BaseModel


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
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name='状态'
    )
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
        FiniteCapacityPlan, on_delete=models.CASCADE,
        related_name='tasks', verbose_name='排程计划'
    )
    work_order = models.CharField(max_length=100, verbose_name='工单号')
    resource = models.CharField(max_length=200, verbose_name='资源')
    start_time = models.DateTimeField(verbose_name='开始时间')
    end_time = models.DateTimeField(verbose_name='结束时间')
    setup_time_minutes = models.IntegerField(default=0, verbose_name='换型时间(分钟)')
    processing_time_minutes = models.IntegerField(verbose_name='加工时间(分钟)')
    sequence = models.IntegerField(default=0, verbose_name='排序')
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='状态'
    )

    class Meta:
        db_table = 'production_scheduled_task'
        ordering = ['plan', 'resource', 'sequence']
        verbose_name = '排程任务'
        verbose_name_plural = '排程任务'

    def __str__(self):
        return f"{self.work_order} @ {self.resource}"


class FiniteCapacityScheduler:
    """Basic finite capacity scheduling engine."""

    @staticmethod
    def run_schedule(plan_id):
        plan = FiniteCapacityPlan.objects.get(id=plan_id, is_deleted=False)
        plan.status = 'running'
        plan.save(update_fields=['status'])

        try:
            tasks = ScheduledTask.objects.filter(
                plan=plan, is_deleted=False
            ).order_by('sequence')

            resource_end_times = {}
            for task in tasks:
                resource_key = task.resource
                current_end = resource_end_times.get(resource_key)

                if current_end and current_end > task.start_time:
                    offset = current_end - task.start_time
                    task.start_time = current_end
                    if plan.consider_setup_time:
                        task.start_time += timezone.timedelta(minutes=task.setup_time_minutes)
                    task.end_time = task.start_time + timezone.timedelta(minutes=task.processing_time_minutes)

                task.status = 'scheduled'
                task.save()
                resource_end_times[resource_key] = task.end_time

            plan.total_tasks = tasks.count()
            plan.status = 'completed'
            plan.save(update_fields=['total_tasks', 'status'])
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

class FiniteCapacityPlanViewSet(viewsets.ModelViewSet):
    serializer_class = FiniteCapacityPlanSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return FiniteCapacityPlan.objects.filter(is_deleted=False)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

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


class ScheduledTaskViewSet(viewsets.ModelViewSet):
    serializer_class = ScheduledTaskSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = ScheduledTask.objects.filter(is_deleted=False)
        plan_id = self.request.query_params.get('plan_id')
        if plan_id:
            qs = qs.filter(plan_id=plan_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
