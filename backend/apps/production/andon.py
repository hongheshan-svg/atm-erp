"""
安灯系统
Andon System
MES异常管理功能
"""
from datetime import date, timedelta

from django.db import models
from django.db.models import Avg, Count
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.models import BaseModel


class AndonType(BaseModel):
    """安灯类型"""
    CATEGORY_CHOICES = [
        ('QUALITY', '质量异常'),
        ('EQUIPMENT', '设备故障'),
        ('MATERIAL', '物料短缺'),
        ('PROCESS', '工艺问题'),
        ('SAFETY', '安全隐患'),
        ('OTHER', '其他'),
    ]

    name = models.CharField(max_length=100, verbose_name='类型名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='类型编码')
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default='OTHER',
        verbose_name='分类'
    )

    # 颜色标识
    color = models.CharField(max_length=20, default='#FF4D4F', verbose_name='颜色')
    icon = models.CharField(max_length=50, blank=True, verbose_name='图标')

    # 响应时间要求(分钟)
    response_time_limit = models.IntegerField(default=15, verbose_name='响应时限(分钟)')
    resolve_time_limit = models.IntegerField(default=60, verbose_name='解决时限(分钟)')

    # 通知配置
    notify_roles = models.JSONField(default=list, blank=True, verbose_name='通知角色')
    notify_users = models.ManyToManyField(
        'accounts.User',
        blank=True,
        related_name='andon_type_notifications',
        verbose_name='通知人员'
    )

    is_active = models.BooleanField(default=True, verbose_name='启用')
    description = models.TextField(blank=True, verbose_name='描述')

    class Meta:
        app_label = 'production'
        db_table = 'mes_andon_type'
        verbose_name = '安灯类型'
        verbose_name_plural = verbose_name
        ordering = ['code']

    def __str__(self):
        return f'{self.code} - {self.name}'


class AndonStation(BaseModel):
    """安灯工位"""
    name = models.CharField(max_length=100, verbose_name='工位名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='工位编码')

    # 关联
    work_center = models.ForeignKey(
        'production.WorkCenter',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='andon_stations',
        verbose_name='工作中心'
    )
    equipment = models.ForeignKey(
        'projects.Equipment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='andon_stations',
        verbose_name='设备'
    )

    location = models.CharField(max_length=200, blank=True, verbose_name='位置')

    # 当前状态
    current_status = models.CharField(
        max_length=20,
        choices=[
            ('GREEN', '正常'),
            ('YELLOW', '警告'),
            ('RED', '异常'),
        ],
        default='GREEN',
        verbose_name='当前状态'
    )

    is_active = models.BooleanField(default=True, verbose_name='启用')

    class Meta:
        app_label = 'production'
        db_table = 'mes_andon_station'
        verbose_name = '安灯工位'
        verbose_name_plural = verbose_name
        ordering = ['code']

    def __str__(self):
        return f'{self.code} - {self.name}'


class AndonCall(BaseModel):
    """安灯呼叫"""
    STATUS_CHOICES = [
        ('PENDING', '待响应'),
        ('RESPONDING', '响应中'),
        ('PROCESSING', '处理中'),
        ('RESOLVED', '已解决'),
        ('ESCALATED', '已升级'),
        ('CANCELLED', '已取消'),
    ]

    PRIORITY_CHOICES = [
        ('LOW', '低'),
        ('MEDIUM', '中'),
        ('HIGH', '高'),
        ('CRITICAL', '紧急'),
    ]

    call_no = models.CharField(max_length=50, unique=True, verbose_name='呼叫编号')

    # 关联
    station = models.ForeignKey(
        AndonStation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='calls',
        verbose_name='工位'
    )
    andon_type = models.ForeignKey(
        AndonType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='calls',
        verbose_name='异常类型'
    )

    # 呼叫信息
    title = models.CharField(max_length=200, verbose_name='异常标题')
    description = models.TextField(blank=True, verbose_name='异常描述')
    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default='MEDIUM',
        verbose_name='优先级'
    )

    # 呼叫人
    caller = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='andon_calls',
        verbose_name='呼叫人'
    )
    call_time = models.DateTimeField(default=timezone.now, verbose_name='呼叫时间')

    # 响应
    responder = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='responded_andon_calls',
        verbose_name='响应人'
    )
    response_time = models.DateTimeField(null=True, blank=True, verbose_name='响应时间')

    # 解决
    resolver = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_andon_calls',
        verbose_name='解决人'
    )
    resolve_time = models.DateTimeField(null=True, blank=True, verbose_name='解决时间')
    resolution = models.TextField(blank=True, verbose_name='解决方案')

    # 状态
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
        verbose_name='状态'
    )

    # 时间统计(分钟)
    response_duration = models.IntegerField(null=True, blank=True, verbose_name='响应时长(分钟)')
    resolve_duration = models.IntegerField(null=True, blank=True, verbose_name='解决时长(分钟)')
    total_duration = models.IntegerField(null=True, blank=True, verbose_name='总时长(分钟)')

    # 关联业务
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='andon_calls',
        verbose_name='项目'
    )
    batch_no = models.CharField(max_length=50, blank=True, verbose_name='批次号')

    attachments = models.JSONField(default=list, blank=True, verbose_name='附件')

    class Meta:
        app_label = 'production'
        db_table = 'mes_andon_call'
        verbose_name = '安灯呼叫'
        verbose_name_plural = verbose_name
        ordering = ['-call_time']

    def __str__(self):
        return f'{self.call_no} - {self.title}'

    def save(self, *args, **kwargs):
        if not self.call_no:
            from apps.core.utils import generate_code
            self.call_no = generate_code('ADN')

        # 计算时长
        if self.response_time and self.call_time:
            self.response_duration = int((self.response_time - self.call_time).total_seconds() / 60)

        if self.resolve_time and self.call_time:
            self.total_duration = int((self.resolve_time - self.call_time).total_seconds() / 60)

        if self.resolve_time and self.response_time:
            self.resolve_duration = int((self.resolve_time - self.response_time).total_seconds() / 60)

        super().save(*args, **kwargs)

        # 更新工位状态
        if self.station:
            if self.status in ['PENDING', 'RESPONDING', 'PROCESSING']:
                self.station.current_status = 'RED'
            else:
                # 检查是否有其他未解决的呼叫
                has_pending = AndonCall.objects.filter(
                    station=self.station,
                    status__in=['PENDING', 'RESPONDING', 'PROCESSING'],
                    is_deleted=False
                ).exclude(pk=self.pk).exists()

                self.station.current_status = 'RED' if has_pending else 'GREEN'
            self.station.save()


class AndonEscalation(BaseModel):
    """安灯升级"""
    call = models.ForeignKey(
        AndonCall,
        on_delete=models.CASCADE,
        related_name='escalations',
        verbose_name='呼叫'
    )

    level = models.IntegerField(default=1, verbose_name='升级级别')
    escalation_time = models.DateTimeField(default=timezone.now, verbose_name='升级时间')

    escalated_to = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='escalated_andon_calls',
        verbose_name='升级给'
    )
    reason = models.TextField(blank=True, verbose_name='升级原因')

    class Meta:
        app_label = 'production'
        db_table = 'mes_andon_escalation'
        verbose_name = '安灯升级'
        verbose_name_plural = verbose_name
        ordering = ['call', 'level']


class AndonAction(BaseModel):
    """安灯处理记录"""
    call = models.ForeignKey(
        AndonCall,
        on_delete=models.CASCADE,
        related_name='actions',
        verbose_name='呼叫'
    )

    action_type = models.CharField(
        max_length=20,
        choices=[
            ('RESPONSE', '响应'),
            ('UPDATE', '更新'),
            ('TRANSFER', '转交'),
            ('ESCALATE', '升级'),
            ('RESOLVE', '解决'),
            ('CLOSE', '关闭'),
        ],
        verbose_name='操作类型'
    )
    action_time = models.DateTimeField(default=timezone.now, verbose_name='操作时间')

    actor = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='andon_actions',
        verbose_name='操作人'
    )

    content = models.TextField(blank=True, verbose_name='操作内容')

    class Meta:
        app_label = 'production'
        db_table = 'mes_andon_action'
        verbose_name = '安灯操作'
        verbose_name_plural = verbose_name
        ordering = ['action_time']


# =====================
# Serializers
# =====================

class AndonTypeSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source='get_category_display', read_only=True)

    class Meta:
        model = AndonType
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class AndonStationSerializer(serializers.ModelSerializer):
    work_center_name = serializers.CharField(source='work_center.name', read_only=True)
    equipment_name = serializers.CharField(source='equipment.name', read_only=True)
    status_display = serializers.CharField(source='get_current_status_display', read_only=True)

    class Meta:
        model = AndonStation
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class AndonActionSerializer(serializers.ModelSerializer):
    action_type_display = serializers.CharField(source='get_action_type_display', read_only=True)
    actor_name = serializers.CharField(source='actor.get_full_name', read_only=True)

    class Meta:
        model = AndonAction
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class AndonEscalationSerializer(serializers.ModelSerializer):
    escalated_to_name = serializers.CharField(source='escalated_to.get_full_name', read_only=True)

    class Meta:
        model = AndonEscalation
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class AndonCallSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    station_name = serializers.CharField(source='station.name', read_only=True)
    type_name = serializers.CharField(source='andon_type.name', read_only=True)
    caller_name = serializers.CharField(source='caller.get_full_name', read_only=True)
    responder_name = serializers.CharField(source='responder.get_full_name', read_only=True)
    resolver_name = serializers.CharField(source='resolver.get_full_name', read_only=True)
    actions = AndonActionSerializer(many=True, read_only=True)
    escalations = AndonEscalationSerializer(many=True, read_only=True)

    class Meta:
        model = AndonCall
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'call_no', 'response_duration', 'resolve_duration', 'total_duration']


class AndonCallListSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    station_name = serializers.CharField(source='station.name', read_only=True)
    type_name = serializers.CharField(source='andon_type.name', read_only=True)
    caller_name = serializers.CharField(source='caller.get_full_name', read_only=True)

    class Meta:
        model = AndonCall
        fields = [
            'id', 'call_no', 'title', 'station', 'station_name',
            'andon_type', 'type_name', 'priority', 'priority_display',
            'status', 'status_display', 'caller_name', 'call_time',
            'response_duration', 'total_duration'
        ]


# =====================
# ViewSets
# =====================

class AndonTypeViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """安灯类型管理"""
    queryset = AndonType.objects.filter(is_deleted=False)
    serializer_class = AndonTypeSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['category', 'is_active']
    search_fields = ['name', 'code']


class AndonStationViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """安灯工位管理"""
    queryset = AndonStation.objects.filter(is_deleted=False)
    serializer_class = AndonStationSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['work_center', 'current_status', 'is_active']
    search_fields = ['name', 'code']

    @action(detail=False, methods=['get'])
    def status_board(self, request):
        """状态看板"""
        stations = self.get_queryset().filter(is_active=True)

        status_summary = stations.values('current_status').annotate(count=Count('id'))

        station_list = []
        for station in stations:
            # 获取当前未解决的呼叫
            active_call = AndonCall.objects.filter(
                station=station,
                status__in=['PENDING', 'RESPONDING', 'PROCESSING'],
                is_deleted=False
            ).first()

            station_list.append({
                'id': station.id,
                'code': station.code,
                'name': station.name,
                'location': station.location,
                'status': station.current_status,
                'active_call': AndonCallListSerializer(active_call).data if active_call else None
            })

        return Response({
            'summary': list(status_summary),
            'stations': station_list
        })


class AndonCallViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """安灯呼叫管理"""
    queryset = AndonCall.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filterset_fields = ['status', 'priority', 'station', 'andon_type', 'caller']
    search_fields = ['call_no', 'title', 'description']
    ordering_fields = ['call_time', 'priority']

    def get_serializer_class(self):
        if self.action == 'list':
            return AndonCallListSerializer
        return AndonCallSerializer

    def perform_create(self, serializer):
        call = serializer.save(caller=self.request.user, created_by=self.request.user)

        # 创建呼叫操作记录
        AndonAction.objects.create(
            call=call,
            action_type='UPDATE',
            actor=self.request.user,
            content='创建安灯呼叫',
            created_by=self.request.user
        )

    @action(detail=True, methods=['post'])
    def respond(self, request, pk=None):
        """响应呼叫"""
        call = self.get_object()
        if call.status != 'PENDING':
            return Response({'error': '只有待响应状态可以响应'}, status=400)

        call.status = 'RESPONDING'
        call.responder = request.user
        call.response_time = timezone.now()
        call.save()

        AndonAction.objects.create(
            call=call,
            action_type='RESPONSE',
            actor=request.user,
            content='响应呼叫',
            created_by=request.user
        )

        return Response(self.get_serializer(call).data)

    @action(detail=True, methods=['post'])
    def start_process(self, request, pk=None):
        """开始处理"""
        call = self.get_object()
        call.status = 'PROCESSING'
        call.save()

        AndonAction.objects.create(
            call=call,
            action_type='UPDATE',
            actor=request.user,
            content='开始处理',
            created_by=request.user
        )

        return Response(self.get_serializer(call).data)

    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """解决问题"""
        call = self.get_object()

        call.status = 'RESOLVED'
        call.resolver = request.user
        call.resolve_time = timezone.now()
        call.resolution = request.data.get('resolution', '')
        call.save()

        AndonAction.objects.create(
            call=call,
            action_type='RESOLVE',
            actor=request.user,
            content=f'解决问题: {call.resolution}',
            created_by=request.user
        )

        return Response(self.get_serializer(call).data)

    @action(detail=True, methods=['post'])
    def escalate(self, request, pk=None):
        """升级呼叫"""
        call = self.get_object()

        # 获取当前升级级别
        current_level = call.escalations.count()
        new_level = current_level + 1

        call.status = 'ESCALATED'
        call.save()

        escalation = AndonEscalation.objects.create(
            call=call,
            level=new_level,
            escalated_to_id=request.data.get('escalated_to'),
            reason=request.data.get('reason', ''),
            created_by=request.user
        )

        AndonAction.objects.create(
            call=call,
            action_type='ESCALATE',
            actor=request.user,
            content=f'升级到级别{new_level}',
            created_by=request.user
        )

        return Response(self.get_serializer(call).data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """取消呼叫"""
        call = self.get_object()
        call.status = 'CANCELLED'
        call.save()

        AndonAction.objects.create(
            call=call,
            action_type='CLOSE',
            actor=request.user,
            content=f'取消呼叫: {request.data.get("reason", "")}',
            created_by=request.user
        )

        return Response(self.get_serializer(call).data)

    @action(detail=False, methods=['get'])
    def pending(self, request):
        """待处理呼叫"""
        calls = self.get_queryset().filter(
            status__in=['PENDING', 'RESPONDING', 'PROCESSING']
        ).order_by('-priority', 'call_time')

        return Response(AndonCallListSerializer(calls, many=True).data)

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """统计分析"""
        days = int(request.query_params.get('days', 7))
        start_date = date.today() - timedelta(days=days)

        qs = self.get_queryset().filter(call_time__date__gte=start_date)

        by_status = qs.values('status').annotate(count=Count('id'))
        by_type = qs.values('andon_type__name').annotate(count=Count('id'))
        by_station = qs.values('station__name').annotate(count=Count('id'))

        # 平均响应和解决时间
        avg_times = qs.filter(status='RESOLVED').aggregate(
            avg_response=Avg('response_duration'),
            avg_resolve=Avg('resolve_duration'),
            avg_total=Avg('total_duration')
        )

        # 每日趋势
        daily_trend = qs.annotate(day=TruncDate('call_time')).values('day').annotate(
            count=Count('id')
        ).order_by('day')

        return Response({
            'total': qs.count(),
            'by_status': list(by_status),
            'by_type': list(by_type),
            'by_station': list(by_station),
            'avg_times': avg_times,
            'daily_trend': list(daily_trend)
        })


class AndonActionViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """安灯操作管理"""
    queryset = AndonAction.objects.filter(is_deleted=False)
    serializer_class = AndonActionSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['call', 'action_type', 'actor']
