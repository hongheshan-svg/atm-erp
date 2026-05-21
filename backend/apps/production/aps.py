"""
项目工序排程
Project Operation Scheduling

功能：基于项目的生产任务排程

非标自动化行业适用说明：
- 每个排程工单对应项目的一个生产任务
- 数量(quantity)字段通常为1（单件生产）
- 重点是工序时间和资源分配，而非数量完成率
- 优先级基于项目交付日期

注：此模块已简化，适合项目型单件/小批量生产排程
"""

from datetime import date, datetime, timedelta
from decimal import Decimal

from django.db import models
from django.db.models import Sum
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.models import BaseModel
from apps.core.permission_mixin import PermissionMixin

# 从scheduling导入WorkCenter，避免重复定义
from .scheduling import WorkCenter


class ScheduleOrder(BaseModel):
    """排程工单"""

    STATUS_CHOICES = [
        ('PENDING', '待排程'),
        ('SCHEDULED', '已排程'),
        ('IN_PROGRESS', '生产中'),
        ('COMPLETED', '已完成'),
        ('CANCELLED', '已取消'),
    ]

    PRIORITY_CHOICES = [
        (1, '最高'),
        (2, '高'),
        (3, '中'),
        (4, '低'),
        (5, '最低'),
    ]

    order_no = models.CharField(max_length=50, unique=True, verbose_name='工单编号')

    # 来源
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='schedule_orders',
        verbose_name='来源项目',
    )
    sales_order = models.ForeignKey(
        'sales.SalesOrder',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='schedule_orders',
        verbose_name='来源订单',
    )

    # 产品
    item = models.ForeignKey(
        'masterdata.Item',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='schedule_orders',
        verbose_name='产品',
    )
    quantity = models.DecimalField(max_digits=18, decimal_places=4, verbose_name='数量')

    # 时间要求
    required_date = models.DateField(verbose_name='需求日期')
    earliest_start = models.DateField(null=True, blank=True, verbose_name='最早开始')

    # 排程结果
    work_center = models.ForeignKey(
        WorkCenter,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='schedule_orders',
        verbose_name='工作中心',
    )
    planned_start = models.DateTimeField(null=True, blank=True, verbose_name='计划开始')
    planned_end = models.DateTimeField(null=True, blank=True, verbose_name='计划结束')
    planned_hours = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='计划工时')

    # 实际
    actual_start = models.DateTimeField(null=True, blank=True, verbose_name='实际开始')
    actual_end = models.DateTimeField(null=True, blank=True, verbose_name='实际结束')
    completed_qty = models.DecimalField(max_digits=18, decimal_places=4, default=0, verbose_name='完成数量')

    priority = models.IntegerField(choices=PRIORITY_CHOICES, default=3, verbose_name='优先级')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', verbose_name='状态')

    remarks = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'mes_schedule_order'
        verbose_name = '排程工单'
        verbose_name_plural = verbose_name
        ordering = ['priority', 'required_date']

    def __str__(self):
        return self.order_no

    def save(self, *args, **kwargs):
        if not self.order_no:
            from apps.core.utils import generate_code

            self.order_no = generate_code('SCH')
        super().save(*args, **kwargs)


class APSScheduleTask(BaseModel):
    """APS排程任务"""

    STATUS_CHOICES = [
        ('PENDING', '待开始'),
        ('IN_PROGRESS', '进行中'),
        ('PAUSED', '暂停'),
        ('COMPLETED', '已完成'),
    ]

    order = models.ForeignKey(ScheduleOrder, on_delete=models.CASCADE, related_name='tasks', verbose_name='工单')

    sequence = models.IntegerField(default=1, verbose_name='工序序号')
    process_name = models.CharField(max_length=100, verbose_name='工序名称')

    work_center = models.ForeignKey(
        WorkCenter,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='aps_schedule_tasks',
        verbose_name='工作中心',
    )

    # 时间
    planned_start = models.DateTimeField(null=True, blank=True, verbose_name='计划开始')
    planned_end = models.DateTimeField(null=True, blank=True, verbose_name='计划结束')
    planned_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='计划工时')

    actual_start = models.DateTimeField(null=True, blank=True, verbose_name='实际开始')
    actual_end = models.DateTimeField(null=True, blank=True, verbose_name='实际结束')
    actual_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='实际工时')

    # 操作人
    operator = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='aps_schedule_tasks',
        verbose_name='操作人',
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', verbose_name='状态')

    progress = models.IntegerField(default=0, verbose_name='进度(%)')

    class Meta:
        app_label = 'production'
        db_table = 'mes_aps_schedule_task'
        verbose_name = 'APS排程任务'
        verbose_name_plural = verbose_name
        ordering = ['order', 'sequence']


class APSService:
    """APS排程服务"""

    @staticmethod
    def auto_schedule(orders=None, start_date=None):
        """自动排程"""
        if start_date is None:
            start_date = date.today()

        if orders is None:
            orders = ScheduleOrder.objects.filter(status='PENDING', is_deleted=False).order_by(
                'priority', 'required_date'
            )

        # 获取所有可用工作中心
        work_centers = WorkCenter.objects.filter(is_active=True, is_deleted=False)

        # 工作中心可用时间表
        wc_availability = {}
        for wc in work_centers:
            wc_availability[wc.id] = datetime.combine(start_date, datetime.min.time())

        scheduled_count = 0

        for order in orders:
            # 估算工时
            if order.planned_hours:
                hours = float(order.planned_hours)
            else:
                # 默认每单位1小时
                hours = float(order.quantity) * 1.0

            # 选择最早可用的工作中心
            best_wc = None
            best_start = None

            for wc in work_centers:
                available = wc_availability[wc.id]

                # 考虑效率
                actual_hours = hours / (float(wc.efficiency) / 100)

                if best_start is None or available < best_start:
                    best_wc = wc
                    best_start = available

            if best_wc:
                # 计算结束时间
                actual_hours = hours / (float(best_wc.efficiency) / 100)
                end_time = best_start + timedelta(hours=actual_hours)

                # 更新工单
                order.work_center = best_wc
                order.planned_start = best_start
                order.planned_end = end_time
                order.planned_hours = Decimal(str(actual_hours))
                order.status = 'SCHEDULED'
                order.save()

                # 更新工作中心可用时间
                wc_availability[best_wc.id] = end_time + timedelta(minutes=best_wc.setup_time)

                scheduled_count += 1

        return scheduled_count

    @staticmethod
    def get_gantt_data(start_date=None, end_date=None):
        """获取甘特图数据"""
        qs = ScheduleOrder.objects.filter(status__in=['SCHEDULED', 'IN_PROGRESS'], is_deleted=False)

        if start_date:
            qs = qs.filter(planned_start__date__gte=start_date)
        if end_date:
            qs = qs.filter(planned_end__date__lte=end_date)

        gantt_data = []
        for order in qs.select_related('work_center', 'item'):
            gantt_data.append(
                {
                    'id': order.id,
                    'order_no': order.order_no,
                    'name': order.item.name if order.item else order.order_no,
                    'work_center': order.work_center.name if order.work_center else '',
                    'start': order.planned_start.isoformat() if order.planned_start else None,
                    'end': order.planned_end.isoformat() if order.planned_end else None,
                    'progress': int(order.completed_qty / order.quantity * 100) if order.quantity else 0,
                    'status': order.status,
                    'priority': order.priority,
                }
            )

        return gantt_data

    @staticmethod
    def get_capacity_view(work_center_id=None, start_date=None, days=7):
        """获取产能视图"""
        if start_date is None:
            start_date = date.today()

        work_centers = WorkCenter.objects.filter(is_active=True, is_deleted=False)
        if work_center_id:
            work_centers = work_centers.filter(id=work_center_id)

        result = []

        for wc in work_centers:
            daily_capacity = float(wc.capacity_per_day)
            wc_data = {
                'work_center_id': wc.id,
                'work_center_name': wc.name,
                'daily_capacity': daily_capacity,
                'days': [],
            }

            for i in range(days):
                check_date = start_date + timedelta(days=i)

                # 获取当天已排程工时
                scheduled_hours = ScheduleOrder.objects.filter(
                    work_center=wc,
                    planned_start__date=check_date,
                    status__in=['SCHEDULED', 'IN_PROGRESS'],
                    is_deleted=False,
                ).aggregate(total=Sum('planned_hours'))['total'] or Decimal('0')

                scheduled = float(scheduled_hours)
                available = max(0, daily_capacity - scheduled)
                utilization = min(100, scheduled / daily_capacity * 100) if daily_capacity > 0 else 0

                wc_data['days'].append(
                    {
                        'date': check_date.isoformat(),
                        'scheduled': scheduled,
                        'available': available,
                        'utilization': round(utilization, 1),
                    }
                )

            result.append(wc_data)

        return result


# =====================
# Serializers
# =====================

# 导入scheduling中的WorkCenterSerializer


class APSScheduleTaskSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    work_center_name = serializers.CharField(source='work_center.name', read_only=True)
    operator_name = serializers.CharField(source='operator.get_full_name', read_only=True)

    class Meta:
        model = APSScheduleTask
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class ScheduleOrderSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    work_center_name = serializers.CharField(source='work_center.name', read_only=True)
    item_name = serializers.CharField(source='item.name', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    tasks = APSScheduleTaskSerializer(many=True, read_only=True)

    class Meta:
        model = ScheduleOrder
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'order_no']


class ScheduleOrderListSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    work_center_name = serializers.CharField(source='work_center.name', read_only=True)
    item_name = serializers.CharField(source='item.name', read_only=True)

    class Meta:
        model = ScheduleOrder
        fields = [
            'id',
            'order_no',
            'item_name',
            'quantity',
            'required_date',
            'work_center_name',
            'planned_start',
            'planned_end',
            'priority',
            'priority_display',
            'status',
            'status_display',
            'completed_qty',
        ]


# =====================
# ViewSets
# =====================

# WorkCenterViewSet已在scheduling.py中定义


class ScheduleOrderViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """排程工单管理"""

    permission_module = 'production'
    permission_resource = 'schedule_order'
    queryset = ScheduleOrder.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filterset_fields = ['status', 'priority', 'work_center', 'project']
    search_fields = ['order_no']
    ordering_fields = ['priority', 'required_date', 'planned_start']

    def get_serializer_class(self):
        if self.action == 'list':
            return ScheduleOrderListSerializer
        return ScheduleOrderSerializer

    @action(detail=False, methods=['post'])
    def auto_schedule(self, request):
        """自动排程"""
        start_date = request.data.get('start_date')
        if start_date:
            start_date = date.fromisoformat(start_date)

        count = APSService.auto_schedule(start_date=start_date)
        return Response({'success': True, 'scheduled_count': count})

    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """开始生产"""
        order = self.get_object()
        order.status = 'IN_PROGRESS'
        order.actual_start = timezone.now()
        order.save()
        return Response(self.get_serializer(order).data)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """完成生产"""
        order = self.get_object()
        completed_qty = request.data.get('completed_qty', order.quantity)

        order.status = 'COMPLETED'
        order.actual_end = timezone.now()
        order.completed_qty = completed_qty
        order.save()
        return Response(self.get_serializer(order).data)

    @action(detail=False, methods=['get'])
    def gantt(self, request):
        """甘特图数据"""
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        if start_date:
            start_date = date.fromisoformat(start_date)
        if end_date:
            end_date = date.fromisoformat(end_date)

        data = APSService.get_gantt_data(start_date, end_date)
        return Response(data)

    @action(detail=False, methods=['get'])
    def capacity(self, request):
        """产能视图"""
        work_center_id = request.query_params.get('work_center_id')
        start_date = request.query_params.get('start_date')
        days = int(request.query_params.get('days', 7))

        if start_date:
            start_date = date.fromisoformat(start_date)

        data = APSService.get_capacity_view(work_center_id, start_date, days)
        return Response(data)


class APSScheduleTaskViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """APS排程任务管理"""

    permission_module = 'production'
    permission_resource = 'aps_schedule_task'
    queryset = APSScheduleTask.objects.filter(is_deleted=False)
    serializer_class = APSScheduleTaskSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['order', 'work_center', 'operator', 'status']

    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """开始任务"""
        task = self.get_object()
        task.status = 'IN_PROGRESS'
        task.actual_start = timezone.now()
        task.save()
        return Response(self.get_serializer(task).data)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """完成任务"""
        task = self.get_object()
        task.status = 'COMPLETED'
        task.actual_end = timezone.now()
        task.progress = 100

        # 计算实际工时
        if task.actual_start:
            delta = timezone.now() - task.actual_start
            task.actual_hours = Decimal(str(delta.total_seconds() / 3600))

        task.save()
        return Response(self.get_serializer(task).data)

    @action(detail=True, methods=['post'])
    def update_progress(self, request, pk=None):
        """更新进度"""
        task = self.get_object()
        progress = request.data.get('progress', 0)
        task.progress = min(100, max(0, int(progress)))
        task.save()
        return Response(self.get_serializer(task).data)
