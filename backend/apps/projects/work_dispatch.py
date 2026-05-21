"""
工单派工系统
Work Order Dispatch System
支持生产工单、维修工单、安装工单的派工和执行跟踪
"""

from decimal import Decimal

from django.db import models
from django.db.models import Count, Sum
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.models import BaseModel
from apps.core.permission_mixin import PermissionMixin


class WorkOrder(BaseModel):
    """
    工单
    """

    ORDER_TYPES = [
        ('PRODUCTION', '生产工单'),
        ('ASSEMBLY', '装配工单'),
        ('DEBUG', '调试工单'),
        ('REPAIR', '维修工单'),
        ('INSTALLATION', '安装工单'),
        ('MAINTENANCE', '保养工单'),
        ('INSPECTION', '检验工单'),
        ('OTHER', '其他'),
    ]

    PRIORITY_LEVELS = [
        ('LOW', '低'),
        ('NORMAL', '普通'),
        ('HIGH', '高'),
        ('URGENT', '紧急'),
    ]

    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('PENDING', '待派工'),
        ('ASSIGNED', '已派工'),
        ('IN_PROGRESS', '执行中'),
        ('PAUSED', '已暂停'),
        ('COMPLETED', '已完成'),
        ('CANCELLED', '已取消'),
    ]

    order_no = models.CharField(max_length=50, unique=True, verbose_name='工单编号')
    order_type = models.CharField(max_length=20, choices=ORDER_TYPES, default='PRODUCTION', verbose_name='工单类型')
    title = models.CharField(max_length=200, verbose_name='工单标题')
    description = models.TextField(blank=True, verbose_name='工单描述')

    # 关联
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='work_orders',
        verbose_name='关联项目',
    )
    equipment = models.ForeignKey(
        'projects.Equipment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='work_orders',
        verbose_name='关联设备',
    )

    # 时间
    planned_start = models.DateTimeField(verbose_name='计划开始时间')
    planned_end = models.DateTimeField(verbose_name='计划结束时间')
    actual_start = models.DateTimeField(null=True, blank=True, verbose_name='实际开始时间')
    actual_end = models.DateTimeField(null=True, blank=True, verbose_name='实际结束时间')

    # 优先级和状态
    priority = models.CharField(max_length=20, choices=PRIORITY_LEVELS, default='NORMAL', verbose_name='优先级')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', verbose_name='状态')

    # 工时估算
    estimated_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0, verbose_name='预估工时(小时)')
    actual_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0, verbose_name='实际工时(小时)')

    # 进度
    progress = models.IntegerField(default=0, verbose_name='进度%')

    # 地点
    location = models.CharField(max_length=200, blank=True, verbose_name='工作地点')

    # 备注
    requirements = models.TextField(blank=True, verbose_name='工作要求')
    notes = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'project_work_order'
        verbose_name = '工单'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.order_no} - {self.title}'

    @property
    def is_overdue(self):
        """是否逾期"""
        if self.status in ['COMPLETED', 'CANCELLED']:
            return False
        return self.planned_end < timezone.now()

    @property
    def assigned_workers(self):
        """已派工人员"""
        return self.dispatches.filter(
            is_deleted=False, status__in=['ASSIGNED', 'IN_PROGRESS', 'COMPLETED']
        ).values_list('worker__id', flat=True)


class WorkDispatch(BaseModel):
    """
    工单派工
    """

    STATUS_CHOICES = [
        ('ASSIGNED', '已派工'),
        ('ACCEPTED', '已接单'),
        ('IN_PROGRESS', '执行中'),
        ('COMPLETED', '已完成'),
        ('REJECTED', '已拒绝'),
    ]

    work_order = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name='dispatches', verbose_name='工单')
    worker = models.ForeignKey(
        'accounts.User', on_delete=models.CASCADE, related_name='dispatched_works', verbose_name='执行人'
    )

    # 派工信息
    dispatch_time = models.DateTimeField(auto_now_add=True, verbose_name='派工时间')
    dispatcher = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, related_name='dispatched_orders', verbose_name='派工人'
    )

    # 时间安排
    planned_start = models.DateTimeField(null=True, blank=True, verbose_name='计划开始')
    planned_end = models.DateTimeField(null=True, blank=True, verbose_name='计划结束')
    actual_start = models.DateTimeField(null=True, blank=True, verbose_name='实际开始')
    actual_end = models.DateTimeField(null=True, blank=True, verbose_name='实际结束')

    # 工时
    planned_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0, verbose_name='计划工时')
    actual_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0, verbose_name='实际工时')

    # 状态
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ASSIGNED', verbose_name='状态')

    # 工作内容
    work_content = models.TextField(blank=True, verbose_name='工作内容')

    # 反馈
    reject_reason = models.CharField(max_length=500, blank=True, verbose_name='拒绝原因')
    completion_notes = models.TextField(blank=True, verbose_name='完成备注')

    # 评价
    quality_score = models.IntegerField(null=True, blank=True, verbose_name='质量评分')
    efficiency_score = models.IntegerField(null=True, blank=True, verbose_name='效率评分')

    class Meta:
        db_table = 'project_work_dispatch'
        verbose_name = '工单派工'
        verbose_name_plural = verbose_name
        ordering = ['-dispatch_time']

    def __str__(self):
        return f'{self.work_order.order_no} - {self.worker.get_full_name()}'


class WorkLog(BaseModel):
    """
    工单执行日志
    """

    LOG_TYPES = [
        ('START', '开始执行'),
        ('PAUSE', '暂停'),
        ('RESUME', '恢复'),
        ('PROGRESS', '进度更新'),
        ('COMPLETE', '完成'),
        ('NOTE', '备注'),
        ('ISSUE', '问题'),
    ]

    dispatch = models.ForeignKey(WorkDispatch, on_delete=models.CASCADE, related_name='logs', verbose_name='派工记录')
    log_type = models.CharField(max_length=20, choices=LOG_TYPES, default='NOTE', verbose_name='日志类型')
    content = models.TextField(verbose_name='内容')
    progress = models.IntegerField(null=True, blank=True, verbose_name='进度%')
    hours = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, verbose_name='工时')
    attachments = models.JSONField(default=list, blank=True, verbose_name='附件')

    class Meta:
        db_table = 'project_work_log'
        verbose_name = '工单日志'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']


# =====================
# Serializers
# =====================


class WorkDispatchSerializer(serializers.ModelSerializer):
    worker_name = serializers.CharField(source='worker.get_full_name', read_only=True)
    dispatcher_name = serializers.CharField(source='dispatcher.get_full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = WorkDispatch
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'dispatch_time', 'dispatcher']


class WorkLogSerializer(serializers.ModelSerializer):
    log_type_display = serializers.CharField(source='get_log_type_display', read_only=True)
    author_name = serializers.CharField(source='created_by.get_full_name', read_only=True)

    class Meta:
        model = WorkLog
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class WorkOrderSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.name', read_only=True)
    order_type_display = serializers.CharField(source='get_order_type_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    dispatches = WorkDispatchSerializer(many=True, read_only=True)

    class Meta:
        model = WorkOrder
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'actual_start', 'actual_end', 'actual_hours']


class WorkOrderListSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.name', read_only=True)
    order_type_display = serializers.CharField(source='get_order_type_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    dispatch_count = serializers.SerializerMethodField()

    class Meta:
        model = WorkOrder
        fields = [
            'id',
            'order_no',
            'order_type',
            'order_type_display',
            'title',
            'project',
            'project_name',
            'priority',
            'priority_display',
            'planned_start',
            'planned_end',
            'status',
            'status_display',
            'progress',
            'estimated_hours',
            'actual_hours',
            'is_overdue',
            'dispatch_count',
            'created_at',
        ]

    def get_dispatch_count(self, obj):
        return obj.dispatches.filter(is_deleted=False).count()


# =====================
# ViewSets
# =====================


class WorkOrderViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """工单管理"""

    permission_module = 'projects'
    permission_resource = 'work_order'
    queryset = WorkOrder.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filterset_fields = ['order_type', 'status', 'priority', 'project']
    search_fields = ['order_no', 'title', 'project__name']
    ordering_fields = ['planned_start', 'priority', 'created_at']

    def get_serializer_class(self):
        if self.action == 'list':
            return WorkOrderListSerializer
        return WorkOrderSerializer

    @action(detail=False, methods=['get'])
    def order_types(self, request):
        """获取工单类型"""
        return Response([{'value': t[0], 'label': t[1]} for t in WorkOrder.ORDER_TYPES])

    @action(detail=True, methods=['post'])
    def assign_workers(self, request, pk=None):
        """派工"""
        work_order = self.get_object()
        worker_ids = request.data.get('worker_ids', [])

        if not worker_ids:
            return Response({'error': '请选择执行人'}, status=400)

        dispatched = []
        for worker_id in worker_ids:
            dispatch, created = WorkDispatch.objects.get_or_create(
                work_order=work_order,
                worker_id=worker_id,
                defaults={
                    'dispatcher': request.user,
                    'planned_start': work_order.planned_start,
                    'planned_end': work_order.planned_end,
                    'planned_hours': work_order.estimated_hours / len(worker_ids),
                    'created_by': request.user,
                },
            )
            if created:
                dispatched.append(WorkDispatchSerializer(dispatch).data)

        if work_order.status == 'PENDING':
            work_order.status = 'ASSIGNED'
            work_order.save()

        return Response({'success': True, 'dispatched': dispatched})

    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """开始执行"""
        work_order = self.get_object()
        work_order.status = 'IN_PROGRESS'
        work_order.actual_start = timezone.now()
        work_order.save()
        return Response(self.get_serializer(work_order).data)

    @action(detail=True, methods=['post'])
    def pause(self, request, pk=None):
        """暂停"""
        work_order = self.get_object()
        work_order.status = 'PAUSED'
        work_order.save()
        return Response(self.get_serializer(work_order).data)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """完成"""
        work_order = self.get_object()
        work_order.status = 'COMPLETED'
        work_order.progress = 100
        work_order.actual_end = timezone.now()

        # 计算实际工时
        if work_order.actual_start:
            duration = (work_order.actual_end - work_order.actual_start).total_seconds() / 3600
            work_order.actual_hours = Decimal(str(round(duration, 2)))

        work_order.save()
        return Response(self.get_serializer(work_order).data)

    @action(detail=True, methods=['post'])
    def update_progress(self, request, pk=None):
        """更新进度"""
        work_order = self.get_object()
        progress = request.data.get('progress', 0)

        work_order.progress = min(max(int(progress), 0), 100)
        if work_order.progress == 100:
            work_order.status = 'COMPLETED'
            work_order.actual_end = timezone.now()
        elif work_order.progress > 0 and work_order.status not in ['IN_PROGRESS', 'COMPLETED']:
            work_order.status = 'IN_PROGRESS'
            if not work_order.actual_start:
                work_order.actual_start = timezone.now()

        work_order.save()
        return Response(self.get_serializer(work_order).data)

    @action(detail=False, methods=['get'])
    def my_orders(self, request):
        """我的工单（我被派工的）"""
        dispatches = WorkDispatch.objects.filter(
            worker=request.user, is_deleted=False, work_order__is_deleted=False
        ).values_list('work_order_id', flat=True)

        orders = self.get_queryset().filter(id__in=dispatches)
        return Response(WorkOrderListSerializer(orders, many=True).data)

    @action(detail=False, methods=['get'])
    def pending_dispatch(self, request):
        """待派工工单"""
        orders = self.get_queryset().filter(status='PENDING')
        return Response(WorkOrderListSerializer(orders, many=True).data)

    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """逾期工单"""
        orders = self.get_queryset().filter(
            planned_end__lt=timezone.now(), status__in=['PENDING', 'ASSIGNED', 'IN_PROGRESS', 'PAUSED']
        )
        return Response(WorkOrderListSerializer(orders, many=True).data)

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """工单统计"""
        qs = self.get_queryset()

        # 按状态统计
        by_status = qs.values('status').annotate(count=Count('id'))

        # 按类型统计
        by_type = qs.values('order_type').annotate(count=Count('id'))

        # 按优先级统计
        by_priority = qs.values('priority').annotate(count=Count('id'))

        # 逾期数
        overdue_count = qs.filter(
            planned_end__lt=timezone.now(), status__in=['PENDING', 'ASSIGNED', 'IN_PROGRESS', 'PAUSED']
        ).count()

        # 今日待完成
        today_end = timezone.now().replace(hour=23, minute=59, second=59)
        today_pending = qs.filter(planned_end__lte=today_end, status__in=['ASSIGNED', 'IN_PROGRESS']).count()

        return Response(
            {
                'total': qs.count(),
                'overdue': overdue_count,
                'today_pending': today_pending,
                'by_status': list(by_status),
                'by_type': list(by_type),
                'by_priority': list(by_priority),
            }
        )


class WorkDispatchViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """派工管理"""

    permission_module = 'projects'
    permission_resource = 'work_dispatch'
    queryset = WorkDispatch.objects.filter(is_deleted=False)
    serializer_class = WorkDispatchSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['work_order', 'worker', 'status']

    def perform_create(self, serializer):
        serializer.save(dispatcher=self.request.user, created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        """接单"""
        dispatch = self.get_object()
        dispatch.status = 'ACCEPTED'
        dispatch.save()
        return Response(self.get_serializer(dispatch).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """拒绝"""
        dispatch = self.get_object()
        dispatch.status = 'REJECTED'
        dispatch.reject_reason = request.data.get('reason', '')
        dispatch.save()
        return Response(self.get_serializer(dispatch).data)

    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """开始执行"""
        dispatch = self.get_object()
        dispatch.status = 'IN_PROGRESS'
        dispatch.actual_start = timezone.now()
        dispatch.save()

        # 更新工单状态
        work_order = dispatch.work_order
        if work_order.status in ['PENDING', 'ASSIGNED']:
            work_order.status = 'IN_PROGRESS'
            if not work_order.actual_start:
                work_order.actual_start = timezone.now()
            work_order.save()

        return Response(self.get_serializer(dispatch).data)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """完成"""
        dispatch = self.get_object()
        dispatch.status = 'COMPLETED'
        dispatch.actual_end = timezone.now()
        dispatch.completion_notes = request.data.get('notes', '')

        # 计算实际工时
        if dispatch.actual_start:
            duration = (dispatch.actual_end - dispatch.actual_start).total_seconds() / 3600
            dispatch.actual_hours = Decimal(str(round(duration, 2)))

        dispatch.save()

        # 检查工单是否全部完成
        work_order = dispatch.work_order
        all_completed = not work_order.dispatches.filter(
            is_deleted=False, status__in=['ASSIGNED', 'ACCEPTED', 'IN_PROGRESS']
        ).exists()

        if all_completed:
            work_order.status = 'COMPLETED'
            work_order.progress = 100
            work_order.actual_end = timezone.now()

            # 汇总实际工时
            total_hours = (
                work_order.dispatches.filter(is_deleted=False, status='COMPLETED').aggregate(total=Sum('actual_hours'))[
                    'total'
                ]
                or 0
            )
            work_order.actual_hours = total_hours
            work_order.save()

        return Response(self.get_serializer(dispatch).data)

    @action(detail=True, methods=['post'])
    def add_log(self, request, pk=None):
        """添加日志"""
        dispatch = self.get_object()

        log = WorkLog.objects.create(
            dispatch=dispatch,
            log_type=request.data.get('log_type', 'NOTE'),
            content=request.data.get('content'),
            progress=request.data.get('progress'),
            hours=request.data.get('hours'),
            attachments=request.data.get('attachments', []),
            created_by=request.user,
        )

        # 更新进度
        if log.progress:
            dispatch.work_order.progress = log.progress
            dispatch.work_order.save()

        return Response(WorkLogSerializer(log).data)

    @action(detail=True, methods=['get'])
    def logs(self, request, pk=None):
        """获取日志"""
        dispatch = self.get_object()
        logs = dispatch.logs.all()
        return Response(WorkLogSerializer(logs, many=True).data)

    @action(detail=False, methods=['get'])
    def my_dispatches(self, request):
        """我的派工"""
        dispatches = self.get_queryset().filter(worker=request.user, status__in=['ASSIGNED', 'ACCEPTED', 'IN_PROGRESS'])
        return Response(self.get_serializer(dispatches, many=True).data)

    @action(detail=True, methods=['post'])
    def evaluate(self, request, pk=None):
        """评价"""
        dispatch = self.get_object()
        dispatch.quality_score = request.data.get('quality_score')
        dispatch.efficiency_score = request.data.get('efficiency_score')
        dispatch.save()
        return Response(self.get_serializer(dispatch).data)


class WorkLogViewSet(PermissionMixin, viewsets.ReadOnlyModelViewSet):
    """工单日志"""

    permission_module = 'projects'
    permission_resource = 'work_log'
    queryset = WorkLog.objects.filter(is_deleted=False)
    serializer_class = WorkLogSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['dispatch', 'log_type']
