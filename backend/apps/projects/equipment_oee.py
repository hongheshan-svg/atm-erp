"""
设备OEE统计分析
Equipment OEE (Overall Equipment Effectiveness) Analysis
设备综合效率统计：可用率 × 性能率 × 良品率
"""

from datetime import date, timedelta
from decimal import Decimal

from django.db import models
from django.db.models import Avg, Count, Sum
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.models import BaseModel
from apps.core.permission_mixin import PermissionMixin


class EquipmentShift(BaseModel):
    """
    设备班次配置
    """

    name = models.CharField(max_length=50, verbose_name='班次名称')
    start_time = models.TimeField(verbose_name='开始时间')
    end_time = models.TimeField(verbose_name='结束时间')
    planned_hours = models.DecimalField(max_digits=5, decimal_places=2, default=8, verbose_name='计划工时')
    break_minutes = models.IntegerField(default=0, verbose_name='休息时间(分钟)')
    is_default = models.BooleanField(default=False, verbose_name='默认班次')
    is_active = models.BooleanField(default=True, verbose_name='启用')

    class Meta:
        db_table = 'equipment_shift'
        verbose_name = '设备班次'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.name


class EquipmentOEERecord(BaseModel):
    """
    设备OEE记录
    """

    equipment = models.ForeignKey(
        'projects.Equipment', on_delete=models.CASCADE, related_name='oee_records', verbose_name='设备'
    )
    record_date = models.DateField(verbose_name='记录日期')
    shift = models.ForeignKey(
        EquipmentShift,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='oee_records',
        verbose_name='班次',
    )

    # 时间数据 (分钟)
    planned_time = models.IntegerField(default=480, verbose_name='计划时间(分钟)')
    downtime = models.IntegerField(default=0, verbose_name='停机时间(分钟)')
    setup_time = models.IntegerField(default=0, verbose_name='换型时间(分钟)')

    # 产出数据
    theoretical_output = models.IntegerField(default=0, verbose_name='理论产量')
    actual_output = models.IntegerField(default=0, verbose_name='实际产量')
    qualified_output = models.IntegerField(default=0, verbose_name='合格产量')

    # 停机原因
    downtime_reasons = models.JSONField(
        default=list, blank=True, verbose_name='停机原因', help_text='[{"reason": "设备故障", "minutes": 30}, ...]'
    )

    # OEE指标
    availability = models.DecimalField(max_digits=6, decimal_places=2, default=0, verbose_name='可用率(%)')
    performance = models.DecimalField(max_digits=6, decimal_places=2, default=0, verbose_name='性能率(%)')
    quality = models.DecimalField(max_digits=6, decimal_places=2, default=0, verbose_name='良品率(%)')
    oee = models.DecimalField(max_digits=6, decimal_places=2, default=0, verbose_name='OEE(%)')

    # 操作员
    operator = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='oee_records',
        verbose_name='操作员',
    )

    remarks = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'equipment_oee_record'
        verbose_name = 'OEE记录'
        verbose_name_plural = verbose_name
        unique_together = ['equipment', 'record_date', 'shift']
        ordering = ['-record_date']

    def __str__(self):
        return f'{self.equipment.name} - {self.record_date}'

    def calculate_oee(self):
        """计算OEE指标"""
        # 可用率 = (计划时间 - 停机时间) / 计划时间
        operating_time = self.planned_time - self.downtime - self.setup_time
        if self.planned_time > 0:
            self.availability = Decimal(operating_time / self.planned_time * 100)

        # 性能率 = 实际产量 / 理论产量
        if self.theoretical_output > 0:
            self.performance = Decimal(self.actual_output / self.theoretical_output * 100)

        # 良品率 = 合格产量 / 实际产量
        if self.actual_output > 0:
            self.quality = Decimal(self.qualified_output / self.actual_output * 100)

        # OEE = 可用率 × 性能率 × 良品率 / 10000
        self.oee = self.availability * self.performance * self.quality / 10000

        return self.oee

    def save(self, *args, **kwargs):
        self.calculate_oee()
        super().save(*args, **kwargs)


class DowntimeReason(BaseModel):
    """
    停机原因字典
    """

    CATEGORY_CHOICES = [
        ('BREAKDOWN', '设备故障'),
        ('SETUP', '换型调整'),
        ('MATERIAL', '物料问题'),
        ('QUALITY', '质量问题'),
        ('MAINTENANCE', '计划维护'),
        ('HUMAN', '人员因素'),
        ('OTHER', '其他'),
    ]

    code = models.CharField(max_length=20, unique=True, verbose_name='原因编码')
    name = models.CharField(max_length=100, verbose_name='原因名称')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='OTHER', verbose_name='分类')
    description = models.TextField(blank=True, verbose_name='描述')
    is_planned = models.BooleanField(default=False, verbose_name='计划内停机')
    is_active = models.BooleanField(default=True, verbose_name='启用')

    class Meta:
        db_table = 'equipment_downtime_reason'
        verbose_name = '停机原因'
        verbose_name_plural = verbose_name
        ordering = ['category', 'code']

    def __str__(self):
        return f'{self.code} - {self.name}'


# =====================
# Serializers
# =====================


class EquipmentShiftSerializer(serializers.ModelSerializer):
    class Meta:
        model = EquipmentShift
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class DowntimeReasonSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source='get_category_display', read_only=True)

    class Meta:
        model = DowntimeReason
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class EquipmentOEERecordSerializer(serializers.ModelSerializer):
    equipment_name = serializers.CharField(source='equipment.name', read_only=True)
    equipment_code = serializers.CharField(source='equipment.equipment_no', read_only=True)
    shift_name = serializers.CharField(source='shift.name', read_only=True)
    operator_name = serializers.CharField(source='operator.get_full_name', read_only=True)

    class Meta:
        model = EquipmentOEERecord
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'availability', 'performance', 'quality', 'oee']


class EquipmentOEERecordListSerializer(serializers.ModelSerializer):
    equipment_name = serializers.CharField(source='equipment.name', read_only=True)
    shift_name = serializers.CharField(source='shift.name', read_only=True)

    class Meta:
        model = EquipmentOEERecord
        fields = [
            'id',
            'equipment',
            'equipment_name',
            'record_date',
            'shift',
            'shift_name',
            'planned_time',
            'downtime',
            'actual_output',
            'qualified_output',
            'availability',
            'performance',
            'quality',
            'oee',
        ]


# =====================
# ViewSets
# =====================


class EquipmentShiftViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """班次管理"""

    permission_module = 'projects'
    permission_resource = 'equipment_shift'
    queryset = EquipmentShift.objects.filter(is_deleted=False)
    serializer_class = EquipmentShiftSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['post'])
    def init_shifts(self, request):
        """初始化默认班次"""
        shifts = [
            ('早班', '08:00', '16:00', 8, 30),
            ('中班', '16:00', '00:00', 8, 30),
            ('晚班', '00:00', '08:00', 8, 30),
        ]

        created = 0
        for name, start, end, hours, break_min in shifts:
            _, c = EquipmentShift.objects.get_or_create(
                name=name,
                defaults={
                    'start_time': start,
                    'end_time': end,
                    'planned_hours': hours,
                    'break_minutes': break_min,
                    'created_by': request.user,
                },
            )
            if c:
                created += 1

        return Response({'success': True, 'created': created})


class DowntimeReasonViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """停机原因管理"""

    permission_module = 'projects'
    permission_resource = 'downtime_reason'
    queryset = DowntimeReason.objects.filter(is_deleted=False)
    serializer_class = DowntimeReasonSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['category', 'is_planned', 'is_active']
    search_fields = ['code', 'name']

    @action(detail=False, methods=['post'])
    def init_reasons(self, request):
        """初始化默认停机原因"""
        reasons = [
            ('B01', '设备故障', 'BREAKDOWN', False),
            ('B02', '模具损坏', 'BREAKDOWN', False),
            ('S01', '换型调整', 'SETUP', True),
            ('S02', '首件检验', 'SETUP', True),
            ('M01', '待料', 'MATERIAL', False),
            ('M02', '物料不良', 'MATERIAL', False),
            ('Q01', '质量异常', 'QUALITY', False),
            ('P01', '计划维护', 'MAINTENANCE', True),
            ('H01', '人员缺岗', 'HUMAN', False),
            ('O01', '其他原因', 'OTHER', False),
        ]

        created = 0
        for code, name, category, is_planned in reasons:
            _, c = DowntimeReason.objects.get_or_create(
                code=code,
                defaults={'name': name, 'category': category, 'is_planned': is_planned, 'created_by': request.user},
            )
            if c:
                created += 1

        return Response({'success': True, 'created': created})


class EquipmentOEERecordViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """OEE记录管理"""

    permission_module = 'projects'
    permission_resource = 'equipment_oee_record'
    queryset = EquipmentOEERecord.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filterset_fields = ['equipment', 'shift', 'record_date']
    ordering_fields = ['record_date', 'oee']

    def get_serializer_class(self):
        if self.action == 'list':
            return EquipmentOEERecordListSerializer
        return EquipmentOEERecordSerializer

    @action(detail=False, methods=['get'])
    def by_equipment(self, request):
        """按设备查询OEE"""
        equipment_id = request.query_params.get('equipment_id')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        queryset = self.get_queryset()

        if equipment_id:
            queryset = queryset.filter(equipment_id=equipment_id)
        if start_date:
            queryset = queryset.filter(record_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(record_date__lte=end_date)

        return Response(EquipmentOEERecordListSerializer(queryset, many=True).data)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """OEE汇总"""
        start_date = request.query_params.get('start_date', (date.today() - timedelta(days=30)).isoformat())
        end_date = request.query_params.get('end_date', date.today().isoformat())

        records = self.get_queryset().filter(record_date__gte=start_date, record_date__lte=end_date)

        # 总体平均
        overall = records.aggregate(
            avg_availability=Avg('availability'),
            avg_performance=Avg('performance'),
            avg_quality=Avg('quality'),
            avg_oee=Avg('oee'),
            total_planned=Sum('planned_time'),
            total_downtime=Sum('downtime'),
            total_output=Sum('actual_output'),
            total_qualified=Sum('qualified_output'),
        )

        # 按设备汇总
        by_equipment = (
            records.values('equipment__id', 'equipment__name', 'equipment__equipment_no')
            .annotate(
                avg_oee=Avg('oee'),
                avg_availability=Avg('availability'),
                avg_performance=Avg('performance'),
                avg_quality=Avg('quality'),
                record_count=Count('id'),
            )
            .order_by('-avg_oee')
        )

        # 按日期趋势
        trend = records.values('record_date').annotate(avg_oee=Avg('oee')).order_by('record_date')

        return Response(
            {
                'period': {'start': start_date, 'end': end_date},
                'overall': overall,
                'by_equipment': list(by_equipment),
                'trend': list(trend),
            }
        )

    @action(detail=False, methods=['get'])
    def downtime_analysis(self, request):
        """停机分析"""
        start_date = request.query_params.get('start_date', (date.today() - timedelta(days=30)).isoformat())
        end_date = request.query_params.get('end_date', date.today().isoformat())
        equipment_id = request.query_params.get('equipment_id')

        queryset = self.get_queryset().filter(record_date__gte=start_date, record_date__lte=end_date)

        if equipment_id:
            queryset = queryset.filter(equipment_id=equipment_id)

        # 汇总停机原因
        reason_summary = {}
        total_downtime = 0

        for record in queryset:
            for reason in record.downtime_reasons:
                reason_name = reason.get('reason', '其他')
                minutes = reason.get('minutes', 0)

                if reason_name not in reason_summary:
                    reason_summary[reason_name] = 0
                reason_summary[reason_name] += minutes
                total_downtime += minutes

        # 转换为列表并计算占比
        reasons_list = []
        for name, minutes in sorted(reason_summary.items(), key=lambda x: -x[1]):
            reasons_list.append(
                {
                    'reason': name,
                    'minutes': minutes,
                    'percentage': round(minutes / total_downtime * 100, 2) if total_downtime > 0 else 0,
                }
            )

        return Response({'total_downtime': total_downtime, 'reasons': reasons_list})

    @action(detail=False, methods=['get'])
    def downtime(self, request):
        """downtime_analysis 的别名（前端 api 调用 /oee-records/downtime/）"""
        return self.downtime_analysis(request)

    @action(detail=False, methods=['get'])
    def ranking(self, request):
        """设备 OEE 排行榜"""
        start_date = request.query_params.get('start_date', (date.today() - timedelta(days=30)).isoformat())
        end_date = request.query_params.get('end_date', date.today().isoformat())
        limit = int(request.query_params.get('limit', 10))

        records = self.get_queryset().filter(record_date__gte=start_date, record_date__lte=end_date)

        ranking = list(
            records.values('equipment__id', 'equipment__name', 'equipment__equipment_no')
            .annotate(
                avg_oee=Avg('oee'),
                avg_availability=Avg('availability'),
                avg_performance=Avg('performance'),
                avg_quality=Avg('quality'),
                record_count=Count('id'),
            )
            .order_by('-avg_oee')[:limit]
        )
        return Response({'ranking': ranking, 'period': {'start': start_date, 'end': end_date}})

    @action(detail=False, methods=['get'])
    def trend(self, request):
        """OEE 趋势（按日）"""
        start_date = request.query_params.get('start_date', (date.today() - timedelta(days=30)).isoformat())
        end_date = request.query_params.get('end_date', date.today().isoformat())
        equipment_id = request.query_params.get('equipment_id')

        qs = self.get_queryset().filter(record_date__gte=start_date, record_date__lte=end_date)
        if equipment_id:
            qs = qs.filter(equipment_id=equipment_id)

        trend = list(
            qs.values('record_date')
            .annotate(
                avg_oee=Avg('oee'),
                avg_availability=Avg('availability'),
                avg_performance=Avg('performance'),
                avg_quality=Avg('quality'),
            )
            .order_by('record_date')
        )
        return Response({'trend': trend, 'period': {'start': start_date, 'end': end_date}})

    @action(detail=False, methods=['get'])
    def benchmark(self, request):
        """OEE对标分析"""
        # 世界级OEE标准
        world_class = {'availability': 90, 'performance': 95, 'quality': 99, 'oee': 85}

        # 计算当前平均值
        last_30_days = date.today() - timedelta(days=30)
        current = (
            self.get_queryset()
            .filter(record_date__gte=last_30_days)
            .aggregate(
                availability=Avg('availability'), performance=Avg('performance'), quality=Avg('quality'), oee=Avg('oee')
            )
        )

        # 计算差距
        gap = {
            'availability': float(world_class['availability'] - (current['availability'] or 0)),
            'performance': float(world_class['performance'] - (current['performance'] or 0)),
            'quality': float(world_class['quality'] - (current['quality'] or 0)),
            'oee': float(world_class['oee'] - (current['oee'] or 0)),
        }

        return Response(
            {'world_class': world_class, 'current': {k: float(v) if v else 0 for k, v in current.items()}, 'gap': gap}
        )
