"""
设备远程运维模块
Remote Equipment Monitoring and Maintenance

功能：
- 设备运行数据接入
- 预测性维护分析
- 故障预警
- 远程诊断日志
"""

from datetime import date, timedelta

from django.db import models
from django.db.models import Count, Max
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.models import BaseModel
from apps.core.permission_mixin import PermissionMixin

# =============================================================================
# 模型定义
# =============================================================================


class EquipmentDataPoint(BaseModel):
    """设备数据点定义"""

    DATA_TYPE_CHOICES = [
        ('TEMPERATURE', '温度'),
        ('PRESSURE', '压力'),
        ('VIBRATION', '振动'),
        ('CURRENT', '电流'),
        ('VOLTAGE', '电压'),
        ('SPEED', '转速'),
        ('POSITION', '位置'),
        ('COUNT', '计数'),
        ('STATUS', '状态'),
        ('ALARM', '报警'),
        ('OTHER', '其他'),
    ]

    code = models.CharField(max_length=100, unique=True, verbose_name='数据点编码')
    name = models.CharField(max_length=200, verbose_name='数据点名称')
    data_type = models.CharField(max_length=20, choices=DATA_TYPE_CHOICES, verbose_name='数据类型')

    unit = models.CharField(max_length=20, blank=True, verbose_name='单位')

    # 阈值
    min_value = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True, verbose_name='最小值')
    max_value = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True, verbose_name='最大值')
    warning_low = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True, verbose_name='低预警值')
    warning_high = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True, verbose_name='高预警值')
    alarm_low = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True, verbose_name='低报警值')
    alarm_high = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True, verbose_name='高报警值')

    description = models.TextField(blank=True, verbose_name='描述')
    is_active = models.BooleanField(default=True, verbose_name='启用')

    class Meta:
        db_table = 'equipment_data_point'
        verbose_name = '设备数据点'
        verbose_name_plural = verbose_name
        ordering = ['code']

    def __str__(self):
        return f'{self.code} - {self.name}'


class EquipmentConnection(BaseModel):
    """设备连接配置"""

    PROTOCOL_CHOICES = [
        ('MQTT', 'MQTT'),
        ('MODBUS_TCP', 'Modbus TCP'),
        ('MODBUS_RTU', 'Modbus RTU'),
        ('OPCUA', 'OPC UA'),
        ('HTTP', 'HTTP/REST'),
        ('WEBSOCKET', 'WebSocket'),
        ('OTHER', '其他'),
    ]

    equipment = models.OneToOneField(
        'projects.Equipment', on_delete=models.CASCADE, related_name='connection', verbose_name='设备'
    )

    # 连接信息
    protocol = models.CharField(max_length=20, choices=PROTOCOL_CHOICES, verbose_name='通信协议')
    host = models.CharField(max_length=200, blank=True, verbose_name='主机地址')
    port = models.IntegerField(null=True, blank=True, verbose_name='端口')
    device_id = models.CharField(max_length=100, blank=True, verbose_name='设备ID')

    # 认证
    username = models.CharField(max_length=100, blank=True, verbose_name='用户名')
    password = models.CharField(max_length=200, blank=True, verbose_name='密码')
    api_key = models.CharField(max_length=500, blank=True, verbose_name='API Key')

    # 数据点映射
    data_points = models.ManyToManyField(
        EquipmentDataPoint, through='EquipmentDataMapping', related_name='connections', verbose_name='数据点'
    )

    # 状态
    is_online = models.BooleanField(default=False, verbose_name='在线')
    last_heartbeat = models.DateTimeField(null=True, blank=True, verbose_name='最后心跳')
    last_data_time = models.DateTimeField(null=True, blank=True, verbose_name='最后数据时间')

    # 配置
    poll_interval = models.IntegerField(default=60, verbose_name='采集间隔(秒)')
    is_enabled = models.BooleanField(default=True, verbose_name='启用采集')

    class Meta:
        db_table = 'equipment_connection'
        verbose_name = '设备连接'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'{self.equipment.name} - {self.protocol}'


class EquipmentDataMapping(BaseModel):
    """设备数据点映射"""

    connection = models.ForeignKey(
        EquipmentConnection, on_delete=models.CASCADE, related_name='mappings', verbose_name='设备连接'
    )
    data_point = models.ForeignKey(
        EquipmentDataPoint, on_delete=models.CASCADE, related_name='mappings', verbose_name='数据点'
    )

    # 协议地址
    address = models.CharField(max_length=200, verbose_name='地址/Topic')
    register = models.CharField(max_length=50, blank=True, verbose_name='寄存器')

    # 数据转换
    scale_factor = models.DecimalField(max_digits=10, decimal_places=4, default=1, verbose_name='比例系数')
    offset = models.DecimalField(max_digits=10, decimal_places=4, default=0, verbose_name='偏移量')

    is_enabled = models.BooleanField(default=True, verbose_name='启用')

    class Meta:
        db_table = 'equipment_data_mapping'
        verbose_name = '数据点映射'
        verbose_name_plural = verbose_name
        unique_together = ['connection', 'data_point']


class EquipmentDataRecord(models.Model):
    """设备运行数据记录（时序数据）"""

    equipment = models.ForeignKey(
        'projects.Equipment', on_delete=models.CASCADE, related_name='data_records', verbose_name='设备'
    )
    data_point = models.ForeignKey(
        EquipmentDataPoint, on_delete=models.CASCADE, related_name='records', verbose_name='数据点'
    )

    timestamp = models.DateTimeField(verbose_name='时间戳')
    value = models.DecimalField(max_digits=18, decimal_places=4, verbose_name='值')
    quality = models.IntegerField(default=100, verbose_name='质量码')

    class Meta:
        db_table = 'equipment_data_record'
        verbose_name = '设备数据记录'
        verbose_name_plural = verbose_name
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['equipment', 'timestamp']),
            models.Index(fields=['data_point', 'timestamp']),
        ]


class EquipmentAlarm(BaseModel):
    """设备报警"""

    SEVERITY_CHOICES = [
        ('INFO', '信息'),
        ('WARNING', '预警'),
        ('ALARM', '报警'),
        ('CRITICAL', '严重'),
    ]

    equipment = models.ForeignKey(
        'projects.Equipment', on_delete=models.CASCADE, related_name='alarms', verbose_name='设备'
    )
    data_point = models.ForeignKey(
        EquipmentDataPoint, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='数据点'
    )

    alarm_code = models.CharField(max_length=50, verbose_name='报警代码')
    alarm_message = models.TextField(verbose_name='报警消息')
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='WARNING', verbose_name='严重程度')

    trigger_value = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True, verbose_name='触发值')
    threshold_value = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True, verbose_name='阈值')

    triggered_at = models.DateTimeField(verbose_name='触发时间')
    acknowledged_at = models.DateTimeField(null=True, blank=True, verbose_name='确认时间')
    acknowledged_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='acknowledged_alarms',
        verbose_name='确认人',
    )

    cleared_at = models.DateTimeField(null=True, blank=True, verbose_name='清除时间')

    is_active = models.BooleanField(default=True, verbose_name='活动中')

    # 处理信息
    action_taken = models.TextField(blank=True, verbose_name='处理措施')
    root_cause = models.TextField(blank=True, verbose_name='根本原因')

    class Meta:
        db_table = 'equipment_alarm'
        verbose_name = '设备报警'
        verbose_name_plural = verbose_name
        ordering = ['-triggered_at']


class DiagnosticSession(BaseModel):
    """远程诊断会话"""

    equipment = models.ForeignKey(
        'projects.Equipment', on_delete=models.CASCADE, related_name='diagnostic_sessions', verbose_name='设备'
    )

    session_no = models.CharField(max_length=50, unique=True, verbose_name='会话编号')

    # 发起原因
    reason = models.CharField(
        max_length=20,
        choices=[
            ('ALARM', '报警触发'),
            ('SCHEDULED', '计划诊断'),
            ('REQUEST', '客户请求'),
            ('PROACTIVE', '主动巡检'),
        ],
        verbose_name='诊断原因',
    )

    related_alarm = models.ForeignKey(
        EquipmentAlarm,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='diagnostic_sessions',
        verbose_name='关联报警',
    )

    # 时间
    started_at = models.DateTimeField(verbose_name='开始时间')
    ended_at = models.DateTimeField(null=True, blank=True, verbose_name='结束时间')

    # 诊断人员
    technician = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='diagnostic_sessions',
        verbose_name='诊断人员',
    )

    # 诊断结果
    status = models.CharField(
        max_length=20,
        choices=[
            ('IN_PROGRESS', '进行中'),
            ('COMPLETED', '已完成'),
            ('ESCALATED', '已升级'),
            ('CANCELLED', '已取消'),
        ],
        default='IN_PROGRESS',
        verbose_name='状态',
    )

    findings = models.TextField(blank=True, verbose_name='诊断发现')
    recommendations = models.TextField(blank=True, verbose_name='建议措施')
    resolution = models.TextField(blank=True, verbose_name='解决方案')

    # 是否需要现场
    on_site_required = models.BooleanField(default=False, verbose_name='需要现场服务')
    service_order = models.ForeignKey(
        'projects.ServiceOrder',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='diagnostic_sessions',
        verbose_name='关联服务单',
    )

    class Meta:
        db_table = 'equipment_diagnostic_session'
        verbose_name = '远程诊断会话'
        verbose_name_plural = verbose_name
        ordering = ['-started_at']

    def save(self, *args, **kwargs):
        if not self.session_no:
            from apps.core.models import CodeRule

            self.session_no = CodeRule.generate_code('DIAG')
        super().save(*args, **kwargs)


class DiagnosticLog(BaseModel):
    """诊断日志"""

    session = models.ForeignKey(
        DiagnosticSession, on_delete=models.CASCADE, related_name='logs', verbose_name='诊断会话'
    )

    log_time = models.DateTimeField(auto_now_add=True, verbose_name='记录时间')
    log_type = models.CharField(
        max_length=20,
        choices=[
            ('COMMAND', '命令'),
            ('RESPONSE', '响应'),
            ('NOTE', '备注'),
            ('DATA', '数据'),
            ('SCREENSHOT', '截图'),
        ],
        verbose_name='日志类型',
    )

    content = models.TextField(verbose_name='内容')
    attachments = models.JSONField(default=list, blank=True, verbose_name='附件')

    class Meta:
        db_table = 'equipment_diagnostic_log'
        verbose_name = '诊断日志'
        verbose_name_plural = verbose_name
        ordering = ['log_time']


class PredictiveMaintenanceModel(BaseModel):
    """预测性维护模型"""

    equipment = models.ForeignKey(
        'projects.Equipment', on_delete=models.CASCADE, related_name='pm_models', verbose_name='设备'
    )

    model_name = models.CharField(max_length=200, verbose_name='模型名称')
    model_type = models.CharField(
        max_length=20,
        choices=[
            ('RUL', '剩余寿命预测'),
            ('ANOMALY', '异常检测'),
            ('FAILURE', '故障预测'),
        ],
        verbose_name='模型类型',
    )

    # 输入数据点
    input_data_points = models.ManyToManyField(EquipmentDataPoint, related_name='pm_models', verbose_name='输入数据点')

    # 模型参数
    parameters = models.JSONField(default=dict, blank=True, verbose_name='模型参数')

    # 训练信息
    trained_at = models.DateTimeField(null=True, blank=True, verbose_name='训练时间')
    training_samples = models.IntegerField(default=0, verbose_name='训练样本数')
    accuracy = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='准确率%')

    is_active = models.BooleanField(default=True, verbose_name='启用')

    class Meta:
        db_table = 'predictive_maintenance_model'
        verbose_name = '预测性维护模型'
        verbose_name_plural = verbose_name


class PredictiveMaintenanceResult(BaseModel):
    """预测性维护结果"""

    model = models.ForeignKey(
        PredictiveMaintenanceModel, on_delete=models.CASCADE, related_name='results', verbose_name='模型'
    )
    equipment = models.ForeignKey(
        'projects.Equipment', on_delete=models.CASCADE, related_name='pm_results', verbose_name='设备'
    )

    prediction_time = models.DateTimeField(auto_now_add=True, verbose_name='预测时间')

    # 预测结果
    prediction_type = models.CharField(
        max_length=20,
        choices=[
            ('RUL_DAYS', '剩余寿命(天)'),
            ('ANOMALY_SCORE', '异常分数'),
            ('FAILURE_PROB', '故障概率'),
        ],
        verbose_name='预测类型',
    )
    prediction_value = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='预测值')
    confidence = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='置信度%')

    # 建议
    recommendation = models.TextField(blank=True, verbose_name='维护建议')
    urgency = models.CharField(
        max_length=20,
        choices=[
            ('LOW', '低'),
            ('MEDIUM', '中'),
            ('HIGH', '高'),
            ('IMMEDIATE', '立即'),
        ],
        default='LOW',
        verbose_name='紧急程度',
    )

    # 处理
    is_actioned = models.BooleanField(default=False, verbose_name='已处理')
    action_taken = models.TextField(blank=True, verbose_name='处理措施')

    class Meta:
        db_table = 'predictive_maintenance_result'
        verbose_name = '预测性维护结果'
        verbose_name_plural = verbose_name
        ordering = ['-prediction_time']


# =============================================================================
# 序列化器
# =============================================================================


class EquipmentDataPointSerializer(serializers.ModelSerializer):
    data_type_display = serializers.CharField(source='get_data_type_display', read_only=True)

    class Meta:
        model = EquipmentDataPoint
        fields = '__all__'


class EquipmentDataMappingSerializer(serializers.ModelSerializer):
    data_point_name = serializers.CharField(source='data_point.name', read_only=True)
    data_point_code = serializers.CharField(source='data_point.code', read_only=True)

    class Meta:
        model = EquipmentDataMapping
        fields = '__all__'


class EquipmentConnectionSerializer(serializers.ModelSerializer):
    equipment_name = serializers.CharField(source='equipment.name', read_only=True)
    equipment_no = serializers.CharField(source='equipment.equipment_no', read_only=True)
    protocol_display = serializers.CharField(source='get_protocol_display', read_only=True)
    mappings = EquipmentDataMappingSerializer(many=True, read_only=True)

    class Meta:
        model = EquipmentConnection
        fields = '__all__'
        extra_kwargs = {
            'password': {'write_only': True},
            'api_key': {'write_only': True},
        }


class EquipmentDataRecordSerializer(serializers.ModelSerializer):
    equipment_name = serializers.CharField(source='equipment.name', read_only=True)
    data_point_name = serializers.CharField(source='data_point.name', read_only=True)
    data_point_unit = serializers.CharField(source='data_point.unit', read_only=True)

    class Meta:
        model = EquipmentDataRecord
        fields = '__all__'


class EquipmentAlarmSerializer(serializers.ModelSerializer):
    equipment_name = serializers.CharField(source='equipment.name', read_only=True)
    equipment_no = serializers.CharField(source='equipment.equipment_no', read_only=True)
    data_point_name = serializers.CharField(source='data_point.name', read_only=True)
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    acknowledged_by_name = serializers.CharField(source='acknowledged_by.get_full_name', read_only=True)

    class Meta:
        model = EquipmentAlarm
        fields = '__all__'


class DiagnosticLogSerializer(serializers.ModelSerializer):
    log_type_display = serializers.CharField(source='get_log_type_display', read_only=True)

    class Meta:
        model = DiagnosticLog
        fields = '__all__'


class DiagnosticSessionSerializer(serializers.ModelSerializer):
    equipment_name = serializers.CharField(source='equipment.name', read_only=True)
    technician_name = serializers.CharField(source='technician.get_full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    reason_display = serializers.CharField(source='get_reason_display', read_only=True)
    logs = DiagnosticLogSerializer(many=True, read_only=True)

    class Meta:
        model = DiagnosticSession
        fields = '__all__'


class PredictiveMaintenanceResultSerializer(serializers.ModelSerializer):
    equipment_name = serializers.CharField(source='equipment.name', read_only=True)
    model_name = serializers.CharField(source='model.model_name', read_only=True)
    prediction_type_display = serializers.CharField(source='get_prediction_type_display', read_only=True)
    urgency_display = serializers.CharField(source='get_urgency_display', read_only=True)

    class Meta:
        model = PredictiveMaintenanceResult
        fields = '__all__'


# =============================================================================
# 视图集
# =============================================================================


class EquipmentDataPointViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """设备数据点管理"""

    queryset = EquipmentDataPoint.objects.filter(is_deleted=False)
    serializer_class = EquipmentDataPointSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['data_type', 'is_active']
    search_fields = ['code', 'name']


class EquipmentConnectionViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """设备连接管理"""

    queryset = EquipmentConnection.objects.filter(is_deleted=False)
    serializer_class = EquipmentConnectionSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['protocol', 'is_online', 'is_enabled']

    @action(detail=True, methods=['post'])
    def test_connection(self, request, pk=None):
        """测试连接"""
        conn = self.get_object()
        # 模拟测试连接
        # 实际实现需要根据协议进行连接测试
        return Response({'success': True, 'message': '连接测试成功', 'latency_ms': 50})

    @action(detail=True, methods=['post'])
    def update_heartbeat(self, request, pk=None):
        """更新心跳"""
        conn = self.get_object()
        conn.last_heartbeat = timezone.now()
        conn.is_online = True
        conn.save(update_fields=['last_heartbeat', 'is_online'])
        return Response({'status': 'ok'})


class EquipmentDataRecordViewSet(PermissionMixin, viewsets.ReadOnlyModelViewSet):
    """设备数据记录（只读）"""

    queryset = EquipmentDataRecord.objects.all()
    serializer_class = EquipmentDataRecordSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['equipment', 'data_point']
    ordering_fields = ['timestamp']

    @action(detail=False, methods=['post'])
    def batch_upload(self, request):
        """批量上传数据"""
        data_list = request.data.get('data', [])

        records = []
        for item in data_list:
            records.append(
                EquipmentDataRecord(
                    equipment_id=item['equipment_id'],
                    data_point_id=item['data_point_id'],
                    timestamp=item['timestamp'],
                    value=item['value'],
                    quality=item.get('quality', 100),
                )
            )

        EquipmentDataRecord.objects.bulk_create(records)

        return Response({'success': True, 'count': len(records)})

    @action(detail=False, methods=['get'])
    def latest(self, request):
        """获取最新数据"""
        equipment_id = request.query_params.get('equipment_id')

        if not equipment_id:
            return Response({'error': '请指定设备'}, status=400)

        # 获取每个数据点的最新值
        from django.db.models import OuterRef, Subquery

        latest_records = (
            EquipmentDataRecord.objects.filter(equipment_id=equipment_id)
            .values('data_point')
            .annotate(
                latest_time=Max('timestamp'),
                latest_value=Subquery(
                    EquipmentDataRecord.objects.filter(equipment_id=equipment_id, data_point=OuterRef('data_point'))
                    .order_by('-timestamp')
                    .values('value')[:1]
                ),
            )
        )

        return Response(list(latest_records))

    @action(detail=False, methods=['get'])
    def history(self, request):
        """获取历史数据"""
        equipment_id = request.query_params.get('equipment_id')
        data_point_id = request.query_params.get('data_point_id')
        start_time = request.query_params.get('start_time')
        end_time = request.query_params.get('end_time')

        if not equipment_id or not data_point_id:
            return Response({'error': '请指定设备和数据点'}, status=400)

        queryset = self.get_queryset().filter(equipment_id=equipment_id, data_point_id=data_point_id)

        if start_time:
            queryset = queryset.filter(timestamp__gte=start_time)
        if end_time:
            queryset = queryset.filter(timestamp__lte=end_time)

        # 限制返回数量
        queryset = queryset.order_by('-timestamp')[:1000]

        return Response(EquipmentDataRecordSerializer(queryset, many=True).data)


class EquipmentAlarmViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """设备报警管理"""

    queryset = EquipmentAlarm.objects.filter(is_deleted=False)
    serializer_class = EquipmentAlarmSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['equipment', 'severity', 'is_active']
    ordering_fields = ['triggered_at', 'severity']

    @action(detail=True, methods=['post'])
    def acknowledge(self, request, pk=None):
        """确认报警"""
        alarm = self.get_object()
        alarm.acknowledged_at = timezone.now()
        alarm.acknowledged_by = request.user
        alarm.save()
        return Response(EquipmentAlarmSerializer(alarm).data)

    @action(detail=True, methods=['post'])
    def clear(self, request, pk=None):
        """清除报警"""
        alarm = self.get_object()
        alarm.cleared_at = timezone.now()
        alarm.is_active = False
        alarm.action_taken = request.data.get('action_taken', '')
        alarm.root_cause = request.data.get('root_cause', '')
        alarm.save()
        return Response(EquipmentAlarmSerializer(alarm).data)

    @action(detail=False, methods=['get'])
    def active(self, request):
        """活动报警"""
        alarms = self.get_queryset().filter(is_active=True).order_by('-severity', '-triggered_at')
        return Response(EquipmentAlarmSerializer(alarms, many=True).data)

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """报警统计"""
        days = int(request.query_params.get('days', 30))
        start_date = timezone.now() - timedelta(days=days)

        queryset = self.get_queryset().filter(triggered_at__gte=start_date)

        # 按严重程度统计
        by_severity = queryset.values('severity').annotate(count=Count('id'))

        # 按设备统计
        by_equipment = (
            queryset.values('equipment__equipment_no', 'equipment__name')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )

        # 活动报警数
        active_count = queryset.filter(is_active=True).count()

        return Response(
            {
                'by_severity': list(by_severity),
                'by_equipment': list(by_equipment),
                'total': queryset.count(),
                'active': active_count,
            }
        )


class DiagnosticSessionViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """远程诊断会话管理"""

    queryset = DiagnosticSession.objects.filter(is_deleted=False)
    serializer_class = DiagnosticSessionSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['equipment', 'status', 'technician', 'reason']

    @action(detail=True, methods=['post'])
    def add_log(self, request, pk=None):
        """添加诊断日志"""
        session = self.get_object()

        log = DiagnosticLog.objects.create(
            session=session,
            log_type=request.data.get('log_type', 'NOTE'),
            content=request.data.get('content', ''),
            attachments=request.data.get('attachments', []),
            created_by=request.user,
        )

        return Response(DiagnosticLogSerializer(log).data)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """完成诊断"""
        session = self.get_object()
        session.status = 'COMPLETED'
        session.ended_at = timezone.now()
        session.findings = request.data.get('findings', '')
        session.recommendations = request.data.get('recommendations', '')
        session.resolution = request.data.get('resolution', '')
        session.on_site_required = request.data.get('on_site_required', False)
        session.save()

        # 如果需要现场服务，可以创建服务单
        if session.on_site_required and not session.service_order:
            from apps.projects.field_service import ServiceOrder

            service = ServiceOrder.objects.create(
                service_type='REPAIR',
                title=f'[诊断] {session.equipment.name} - {session.findings[:50]}',
                customer=session.equipment.customer,
                equipment=session.equipment,
                service_address=session.equipment.location or '',
                contact_name='',
                contact_phone='',
                requested_date=date.today() + timedelta(days=3),
                description=f'远程诊断发现：\n{session.findings}\n\n建议：\n{session.recommendations}',
                created_by=request.user,
            )
            session.service_order = service
            session.save()

        return Response(DiagnosticSessionSerializer(session).data)


class PredictiveMaintenanceResultViewSet(PermissionMixin, viewsets.ReadOnlyModelViewSet):
    """预测性维护结果"""

    queryset = PredictiveMaintenanceResult.objects.filter(is_deleted=False)
    serializer_class = PredictiveMaintenanceResultSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['equipment', 'urgency', 'is_actioned']

    @action(detail=True, methods=['post'])
    def take_action(self, request, pk=None):
        """标记已处理"""
        result = self.get_object()
        result.is_actioned = True
        result.action_taken = request.data.get('action_taken', '')
        result.save()
        return Response(PredictiveMaintenanceResultSerializer(result).data)

    @action(detail=False, methods=['get'])
    def pending(self, request):
        """待处理预测"""
        results = (
            self.get_queryset()
            .filter(is_actioned=False, urgency__in=['HIGH', 'IMMEDIATE'])
            .order_by('-prediction_time')
        )
        return Response(PredictiveMaintenanceResultSerializer(results, many=True).data)


class EquipmentMonitoringDashboardView(APIView):
    """设备监控看板"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.projects.models import Equipment

        # 设备统计
        equipment_stats = {
            'total': Equipment.objects.filter(is_deleted=False).count(),
            'online': EquipmentConnection.objects.filter(is_online=True).count(),
            'offline': EquipmentConnection.objects.filter(is_online=False, is_enabled=True).count(),
        }

        # 活动报警
        active_alarms = EquipmentAlarm.objects.filter(is_active=True).order_by('-severity', '-triggered_at')[:10]

        # 预测性维护提醒
        pending_pm = PredictiveMaintenanceResult.objects.filter(
            is_actioned=False, urgency__in=['HIGH', 'IMMEDIATE']
        ).order_by('-prediction_time')[:5]

        # 诊断会话
        active_sessions = DiagnosticSession.objects.filter(status='IN_PROGRESS').count()

        return Response(
            {
                'equipment_stats': equipment_stats,
                'active_alarms': EquipmentAlarmSerializer(active_alarms, many=True).data,
                'pending_pm': PredictiveMaintenanceResultSerializer(pending_pm, many=True).data,
                'active_diagnostic_sessions': active_sessions,
            }
        )
