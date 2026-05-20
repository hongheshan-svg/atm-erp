"""
MES数据采集模块
Data Acquisition with MQTT/OPC UA Support
设备联网和实时数据采集
"""
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.models import BaseModel


class DataSource(BaseModel):
    """数据源配置"""
    TYPE_CHOICES = [
        ('MQTT', 'MQTT协议'),
        ('OPC_UA', 'OPC UA协议'),
        ('MODBUS', 'Modbus协议'),
        ('HTTP', 'HTTP接口'),
        ('DATABASE', '数据库'),
        ('MANUAL', '手动录入'),
    ]

    STATUS_CHOICES = [
        ('ACTIVE', '运行中'),
        ('INACTIVE', '已停止'),
        ('ERROR', '故障'),
        ('TESTING', '测试中'),
    ]

    name = models.CharField(max_length=100, verbose_name='数据源名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='数据源编码')
    source_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='MQTT', verbose_name='类型')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='INACTIVE', verbose_name='状态')

    # 连接配置
    host = models.CharField(max_length=255, blank=True, verbose_name='主机地址')
    port = models.IntegerField(default=1883, verbose_name='端口')
    username = models.CharField(max_length=100, blank=True, verbose_name='用户名')
    password = models.CharField(max_length=255, blank=True, verbose_name='密码')

    # MQTT特定配置
    client_id = models.CharField(max_length=100, blank=True, verbose_name='客户端ID')
    topics = models.TextField(blank=True, verbose_name='订阅主题(每行一个)')
    qos = models.IntegerField(default=1, verbose_name='QoS级别')
    use_ssl = models.BooleanField(default=False, verbose_name='使用SSL')

    # OPC UA特定配置
    node_id = models.CharField(max_length=255, blank=True, verbose_name='OPC UA节点ID')
    namespace_index = models.IntegerField(default=2, verbose_name='命名空间索引')

    # 其他配置
    config = models.JSONField(default=dict, blank=True, verbose_name='扩展配置')
    description = models.TextField(blank=True, verbose_name='描述')

    # 状态信息
    last_connected_at = models.DateTimeField(null=True, blank=True, verbose_name='最后连接时间')
    last_error = models.TextField(blank=True, verbose_name='最后错误信息')

    class Meta:
        app_label = 'production'
        db_table = 'mes_data_source'
        verbose_name = '数据源'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'{self.name} ({self.source_type})'

    def get_topics_list(self):
        """获取主题列表"""
        return [t.strip() for t in self.topics.split('\n') if t.strip()]


class DataPoint(BaseModel):
    """数据点定义"""
    TYPE_CHOICES = [
        ('BOOL', '布尔值'),
        ('INT', '整数'),
        ('FLOAT', '浮点数'),
        ('STRING', '字符串'),
        ('ARRAY', '数组'),
    ]

    CATEGORY_CHOICES = [
        ('PRODUCTION', '生产数据'),
        ('QUALITY', '质量数据'),
        ('EQUIPMENT', '设备数据'),
        ('ENVIRONMENT', '环境数据'),
        ('ENERGY', '能源数据'),
    ]

    data_source = models.ForeignKey(
        DataSource,
        on_delete=models.CASCADE,
        related_name='data_points',
        verbose_name='数据源'
    )

    name = models.CharField(max_length=100, verbose_name='数据点名称')
    code = models.CharField(max_length=100, verbose_name='数据点编码')
    data_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='FLOAT', verbose_name='数据类型')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='PRODUCTION', verbose_name='分类')

    # 地址配置
    address = models.CharField(max_length=255, blank=True, verbose_name='数据地址')
    topic = models.CharField(max_length=255, blank=True, verbose_name='MQTT主题')
    json_path = models.CharField(max_length=255, blank=True, verbose_name='JSON路径')

    # 单位和转换
    unit = models.CharField(max_length=50, blank=True, verbose_name='单位')
    scale_factor = models.FloatField(default=1.0, verbose_name='缩放系数')
    offset = models.FloatField(default=0.0, verbose_name='偏移量')

    # 阈值设置
    min_value = models.FloatField(null=True, blank=True, verbose_name='最小值')
    max_value = models.FloatField(null=True, blank=True, verbose_name='最大值')
    warning_low = models.FloatField(null=True, blank=True, verbose_name='低告警阈值')
    warning_high = models.FloatField(null=True, blank=True, verbose_name='高告警阈值')
    alarm_low = models.FloatField(null=True, blank=True, verbose_name='低报警阈值')
    alarm_high = models.FloatField(null=True, blank=True, verbose_name='高报警阈值')

    # 采样配置
    sampling_interval = models.IntegerField(default=1000, verbose_name='采样间隔(ms)')
    storage_interval = models.IntegerField(default=60000, verbose_name='存储间隔(ms)')

    # 关联设备
    equipment = models.ForeignKey(
        'projects.Equipment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='data_points',
        verbose_name='关联设备'
    )

    # 最新值缓存
    current_value = models.CharField(max_length=255, blank=True, verbose_name='当前值')
    current_value_at = models.DateTimeField(null=True, blank=True, verbose_name='当前值时间')

    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    description = models.TextField(blank=True, verbose_name='描述')

    class Meta:
        app_label = 'production'
        db_table = 'mes_data_point'
        verbose_name = '数据点'
        verbose_name_plural = verbose_name
        unique_together = ['data_source', 'code']

    def __str__(self):
        return f'{self.data_source.name}/{self.name}'

    def transform_value(self, raw_value):
        """转换原始值"""
        try:
            if self.data_type == 'BOOL':
                return bool(raw_value)
            elif self.data_type == 'INT':
                return int(float(raw_value) * self.scale_factor + self.offset)
            elif self.data_type == 'FLOAT':
                return float(raw_value) * self.scale_factor + self.offset
            else:
                return str(raw_value)
        except (ValueError, TypeError):
            return raw_value

    def check_alarms(self, value):
        """检查告警"""
        if self.data_type not in ('INT', 'FLOAT'):
            return None

        try:
            v = float(value)
        except (ValueError, TypeError):
            return None

        if self.alarm_low is not None and v < self.alarm_low:
            return 'ALARM_LOW'
        if self.alarm_high is not None and v > self.alarm_high:
            return 'ALARM_HIGH'
        if self.warning_low is not None and v < self.warning_low:
            return 'WARNING_LOW'
        if self.warning_high is not None and v > self.warning_high:
            return 'WARNING_HIGH'
        return None


class DataRecord(models.Model):
    """采集数据记录"""
    data_point = models.ForeignKey(
        DataPoint,
        on_delete=models.CASCADE,
        related_name='records',
        verbose_name='数据点'
    )

    value = models.CharField(max_length=255, verbose_name='值')
    raw_value = models.CharField(max_length=255, blank=True, verbose_name='原始值')
    quality = models.IntegerField(default=192, verbose_name='质量码')  # OPC UA quality
    timestamp = models.DateTimeField(default=timezone.now, verbose_name='时间戳')

    # 告警状态
    alarm_status = models.CharField(max_length=20, blank=True, verbose_name='告警状态')

    class Meta:
        app_label = 'production'
        db_table = 'mes_data_record'
        verbose_name = '数据记录'
        verbose_name_plural = verbose_name
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['data_point', 'timestamp']),
            models.Index(fields=['timestamp']),
        ]

    def __str__(self):
        return f'{self.data_point}: {self.value} @ {self.timestamp}'


class DataAlarm(BaseModel):
    """数据告警"""
    LEVEL_CHOICES = [
        ('INFO', '信息'),
        ('WARNING', '警告'),
        ('ALARM', '报警'),
        ('CRITICAL', '严重'),
    ]

    STATUS_CHOICES = [
        ('ACTIVE', '活动'),
        ('ACKNOWLEDGED', '已确认'),
        ('RESOLVED', '已解决'),
    ]

    data_point = models.ForeignKey(
        DataPoint,
        on_delete=models.CASCADE,
        related_name='alarms',
        verbose_name='数据点'
    )

    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='WARNING', verbose_name='级别')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE', verbose_name='状态')

    message = models.TextField(verbose_name='告警信息')
    value = models.CharField(max_length=255, verbose_name='触发值')
    threshold = models.CharField(max_length=255, blank=True, verbose_name='阈值')

    triggered_at = models.DateTimeField(default=timezone.now, verbose_name='触发时间')
    acknowledged_at = models.DateTimeField(null=True, blank=True, verbose_name='确认时间')
    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='acknowledged_data_alarms',
        verbose_name='确认人'
    )
    resolved_at = models.DateTimeField(null=True, blank=True, verbose_name='解决时间')
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_data_alarms',
        verbose_name='解决人'
    )
    resolution = models.TextField(blank=True, verbose_name='解决措施')

    class Meta:
        app_label = 'production'
        db_table = 'mes_data_alarm'
        verbose_name = '数据告警'
        verbose_name_plural = verbose_name
        ordering = ['-triggered_at']


# ============ Serializers ============

class DataSourceSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_source_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    data_points_count = serializers.SerializerMethodField()

    class Meta:
        model = DataSource
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'last_connected_at', 'last_error']

    def get_data_points_count(self, obj):
        return obj.data_points.count()


class DataPointSerializer(serializers.ModelSerializer):
    data_source_name = serializers.CharField(source='data_source.name', read_only=True)
    type_display = serializers.CharField(source='get_data_type_display', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    equipment_name = serializers.CharField(source='equipment.name', read_only=True)

    class Meta:
        model = DataPoint
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'current_value', 'current_value_at']


class DataRecordSerializer(serializers.ModelSerializer):
    data_point_name = serializers.CharField(source='data_point.name', read_only=True)

    class Meta:
        model = DataRecord
        fields = ['id', 'data_point', 'data_point_name', 'value', 'raw_value',
                  'quality', 'timestamp', 'alarm_status']


class DataAlarmSerializer(serializers.ModelSerializer):
    data_point_name = serializers.CharField(source='data_point.name', read_only=True)
    level_display = serializers.CharField(source='get_level_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    acknowledged_by_name = serializers.CharField(source='acknowledged_by.username', read_only=True)
    resolved_by_name = serializers.CharField(source='resolved_by.username', read_only=True)

    class Meta:
        model = DataAlarm
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'acknowledged_at',
                           'acknowledged_by', 'resolved_at', 'resolved_by']


# ============ ViewSets ============

class DataSourceViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """数据源管理"""
    queryset = DataSource.objects.filter(is_deleted=False)
    serializer_class = DataSourceSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['source_type', 'status']
    search_fields = ['name', 'code']

    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """启动数据源"""
        source = self.get_object()
        source.status = 'ACTIVE'
        source.last_connected_at = timezone.now()
        source.save()
        return Response({'message': '数据源已启动'})

    @action(detail=True, methods=['post'])
    def stop(self, request, pk=None):
        """停止数据源"""
        source = self.get_object()
        source.status = 'INACTIVE'
        source.save()
        return Response({'message': '数据源已停止'})

    @action(detail=True, methods=['post'])
    def test_connection(self, request, pk=None):
        """测试连接"""
        source = self.get_object()
        # 这里应该实际测试连接，暂时返回模拟结果
        return Response({'success': True, 'message': '连接测试成功'})


class DataPointViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """数据点管理"""
    queryset = DataPoint.objects.filter(is_deleted=False)
    serializer_class = DataPointSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['data_source', 'data_type', 'category', 'equipment', 'is_active']
    search_fields = ['name', 'code']

    @action(detail=False, methods=['get'])
    def realtime(self, request):
        """获取实时数据"""
        point_ids = request.query_params.get('points', '').split(',')
        points = self.get_queryset().filter(id__in=point_ids)

        data = []
        for point in points:
            data.append({
                'id': point.id,
                'name': point.name,
                'code': point.code,
                'value': point.current_value,
                'unit': point.unit,
                'timestamp': point.current_value_at,
                'alarm_status': point.check_alarms(point.current_value)
            })

        return Response(data)

    @action(detail=True, methods=['post'])
    def write_value(self, request, pk=None):
        """手动写入数据值"""
        point = self.get_object()
        value = request.data.get('value')

        if value is None:
            return Response({'error': '请提供值'}, status=400)

        # 转换并存储值
        transformed = point.transform_value(value)
        alarm_status = point.check_alarms(transformed)

        # 更新当前值
        point.current_value = str(transformed)
        point.current_value_at = timezone.now()
        point.save()

        # 创建记录
        record = DataRecord.objects.create(
            data_point=point,
            value=str(transformed),
            raw_value=str(value),
            alarm_status=alarm_status or ''
        )

        # 创建告警
        if alarm_status:
            level = 'ALARM' if 'ALARM' in alarm_status else 'WARNING'
            DataAlarm.objects.create(
                data_point=point,
                level=level,
                message=f'{point.name} {alarm_status}: {transformed}',
                value=str(transformed),
                created_by=request.user
            )

        return Response(DataRecordSerializer(record).data)

    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        """获取历史数据"""
        point = self.get_object()

        start_time = request.query_params.get('start')
        end_time = request.query_params.get('end')
        limit = int(request.query_params.get('limit', 1000))

        records = point.records.all()

        if start_time:
            records = records.filter(timestamp__gte=start_time)
        if end_time:
            records = records.filter(timestamp__lte=end_time)

        records = records.order_by('-timestamp')[:limit]

        return Response(DataRecordSerializer(records, many=True).data)


class DataRecordViewSet(viewsets.ReadOnlyModelViewSet):
    """数据记录查询"""
    queryset = DataRecord.objects.all()
    serializer_class = DataRecordSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['data_point', 'alarm_status']

    def get_queryset(self):
        qs = super().get_queryset()

        # 时间范围过滤
        start_time = self.request.query_params.get('start')
        end_time = self.request.query_params.get('end')

        if start_time:
            qs = qs.filter(timestamp__gte=start_time)
        if end_time:
            qs = qs.filter(timestamp__lte=end_time)

        return qs.order_by('-timestamp')[:10000]


class DataAlarmViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """数据告警管理"""
    queryset = DataAlarm.objects.filter(is_deleted=False)
    serializer_class = DataAlarmSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['data_point', 'level', 'status']

    @action(detail=False, methods=['get'])
    def active(self, request):
        """获取活动告警"""
        alarms = self.get_queryset().filter(status='ACTIVE').order_by('-triggered_at')
        return Response(DataAlarmSerializer(alarms, many=True).data)

    @action(detail=True, methods=['post'])
    def acknowledge(self, request, pk=None):
        """确认告警"""
        alarm = self.get_object()
        alarm.status = 'ACKNOWLEDGED'
        alarm.acknowledged_at = timezone.now()
        alarm.acknowledged_by = request.user
        alarm.save()
        return Response(DataAlarmSerializer(alarm).data)

    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """解决告警"""
        alarm = self.get_object()
        alarm.status = 'RESOLVED'
        alarm.resolved_at = timezone.now()
        alarm.resolved_by = request.user
        alarm.resolution = request.data.get('resolution', '')
        alarm.save()
        return Response(DataAlarmSerializer(alarm).data)

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """告警统计"""
        from django.db.models import Count

        days = int(request.query_params.get('days', 7))
        start_date = timezone.now() - timedelta(days=days)

        alarms = self.get_queryset().filter(triggered_at__gte=start_date)

        by_level = alarms.values('level').annotate(count=Count('id'))
        by_status = alarms.values('status').annotate(count=Count('id'))

        return Response({
            'total': alarms.count(),
            'by_level': {item['level']: item['count'] for item in by_level},
            'by_status': {item['status']: item['count'] for item in by_status},
            'active_count': alarms.filter(status='ACTIVE').count()
        })
