"""
SPC统计过程控制
Statistical Process Control
MES质量管理功能
"""
from datetime import date, datetime, timedelta
from decimal import Decimal
import math
from django.db import models
from django.db.models import Sum, Count, Avg, StdDev, Min, Max, F, Q
from django.utils import timezone
from rest_framework import viewsets, serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.core.models import BaseModel
from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin


class ControlChart(BaseModel):
    """控制图配置"""
    CHART_TYPES = [
        ('XBAR_R', 'X̄-R控制图'),
        ('XBAR_S', 'X̄-S控制图'),
        ('P', 'P控制图'),
        ('NP', 'NP控制图'),
        ('C', 'C控制图'),
        ('U', 'U控制图'),
    ]
    
    name = models.CharField(max_length=200, verbose_name='控制图名称')
    chart_type = models.CharField(
        max_length=20,
        choices=CHART_TYPES,
        default='XBAR_R',
        verbose_name='控制图类型'
    )
    
    # 关联
    process = models.ForeignKey(
        'production.ProductionProcess',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='control_charts',
        verbose_name='工序'
    )
    item = models.ForeignKey(
        'masterdata.Item',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='control_charts',
        verbose_name='产品'
    )
    
    # 测量项目
    measurement_name = models.CharField(max_length=100, verbose_name='测量项目')
    unit = models.CharField(max_length=20, blank=True, verbose_name='单位')
    
    # 规格限
    usl = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True, verbose_name='规格上限(USL)')
    lsl = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True, verbose_name='规格下限(LSL)')
    target = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True, verbose_name='目标值')
    
    # 控制限(可选,不设置则自动计算)
    ucl = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True, verbose_name='控制上限(UCL)')
    cl = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True, verbose_name='中心线(CL)')
    lcl = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True, verbose_name='控制下限(LCL)')
    
    # 子组大小
    subgroup_size = models.IntegerField(default=5, verbose_name='子组大小')
    
    is_active = models.BooleanField(default=True, verbose_name='启用')
    
    class Meta:
        app_label = 'production'
        db_table = 'mes_control_chart'
        verbose_name = '控制图'
        verbose_name_plural = verbose_name
    
    def __str__(self):
        return f'{self.name} ({self.get_chart_type_display()})'


class SPCDataPoint(BaseModel):
    """SPC数据点"""
    control_chart = models.ForeignKey(
        ControlChart,
        on_delete=models.CASCADE,
        related_name='data_points',
        verbose_name='控制图'
    )
    
    # 时间
    sample_time = models.DateTimeField(default=timezone.now, verbose_name='采样时间')
    subgroup_no = models.IntegerField(verbose_name='子组编号')
    
    # 测量值
    value = models.DecimalField(max_digits=18, decimal_places=6, verbose_name='测量值')
    sample_no = models.IntegerField(default=1, verbose_name='样本序号')
    
    # 操作员
    operator = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='spc_data_points',
        verbose_name='操作员'
    )
    
    # 设备/批次
    equipment = models.ForeignKey(
        'projects.Equipment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='spc_data_points',
        verbose_name='设备'
    )
    batch_no = models.CharField(max_length=50, blank=True, verbose_name='批次号')
    
    remarks = models.CharField(max_length=500, blank=True, verbose_name='备注')
    
    class Meta:
        app_label = 'production'
        db_table = 'mes_spc_data_point'
        verbose_name = 'SPC数据点'
        verbose_name_plural = verbose_name
        ordering = ['sample_time']


class SubgroupStatistics(BaseModel):
    """子组统计"""
    control_chart = models.ForeignKey(
        ControlChart,
        on_delete=models.CASCADE,
        related_name='subgroup_stats',
        verbose_name='控制图'
    )
    
    subgroup_no = models.IntegerField(verbose_name='子组编号')
    sample_time = models.DateTimeField(verbose_name='采样时间')
    
    # 统计量
    x_bar = models.DecimalField(max_digits=18, decimal_places=6, verbose_name='均值(X̄)')
    r_value = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True, verbose_name='极差(R)')
    s_value = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True, verbose_name='标准差(S)')
    sample_size = models.IntegerField(verbose_name='样本量')
    
    # 判异
    is_out_of_control = models.BooleanField(default=False, verbose_name='失控')
    violation_rules = models.JSONField(default=list, blank=True, verbose_name='违反规则')
    
    class Meta:
        app_label = 'production'
        db_table = 'mes_subgroup_statistics'
        verbose_name = '子组统计'
        verbose_name_plural = verbose_name
        unique_together = ['control_chart', 'subgroup_no']
        ordering = ['subgroup_no']


class ProcessCapability(BaseModel):
    """过程能力分析"""
    control_chart = models.ForeignKey(
        ControlChart,
        on_delete=models.CASCADE,
        related_name='capability_analyses',
        verbose_name='控制图'
    )
    
    # 分析期间
    start_date = models.DateField(verbose_name='开始日期')
    end_date = models.DateField(verbose_name='结束日期')
    
    # 统计参数
    sample_count = models.IntegerField(default=0, verbose_name='样本数')
    mean = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True, verbose_name='均值')
    std_dev = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True, verbose_name='标准差')
    
    # 过程能力指数
    cp = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True, verbose_name='Cp')
    cpk = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True, verbose_name='Cpk')
    pp = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True, verbose_name='Pp')
    ppk = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True, verbose_name='Ppk')
    
    # 不合格率
    ppm_total = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='PPM总计')
    ppm_upper = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='PPM上限')
    ppm_lower = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='PPM下限')
    
    remarks = models.TextField(blank=True, verbose_name='分析说明')
    
    class Meta:
        app_label = 'production'
        db_table = 'mes_process_capability'
        verbose_name = '过程能力'
        verbose_name_plural = verbose_name
        ordering = ['-end_date']


class SPCAlarm(BaseModel):
    """SPC报警"""
    ALARM_TYPES = [
        ('OUT_UCL', '超出UCL'),
        ('OUT_LCL', '超出LCL'),
        ('TREND', '趋势'),
        ('RUN', '连串'),
        ('ZONE_A', 'A区异常'),
        ('ZONE_B', 'B区异常'),
        ('SHIFT', '偏移'),
    ]
    
    control_chart = models.ForeignKey(
        ControlChart,
        on_delete=models.CASCADE,
        related_name='alarms',
        verbose_name='控制图'
    )
    
    alarm_type = models.CharField(
        max_length=20,
        choices=ALARM_TYPES,
        verbose_name='报警类型'
    )
    alarm_time = models.DateTimeField(default=timezone.now, verbose_name='报警时间')
    
    subgroup_no = models.IntegerField(verbose_name='子组编号')
    value = models.DecimalField(max_digits=18, decimal_places=6, verbose_name='异常值')
    
    description = models.TextField(blank=True, verbose_name='描述')
    
    # 处理
    is_handled = models.BooleanField(default=False, verbose_name='已处理')
    handled_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='handled_spc_alarms',
        verbose_name='处理人'
    )
    handled_at = models.DateTimeField(null=True, blank=True, verbose_name='处理时间')
    action_taken = models.TextField(blank=True, verbose_name='处理措施')
    
    class Meta:
        app_label = 'production'
        db_table = 'mes_spc_alarm'
        verbose_name = 'SPC报警'
        verbose_name_plural = verbose_name
        ordering = ['-alarm_time']


# =====================
# Serializers
# =====================

class ControlChartSerializer(serializers.ModelSerializer):
    chart_type_display = serializers.CharField(source='get_chart_type_display', read_only=True)
    process_name = serializers.CharField(source='process.name', read_only=True)
    item_name = serializers.CharField(source='item.name', read_only=True)
    
    class Meta:
        model = ControlChart
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class SPCDataPointSerializer(serializers.ModelSerializer):
    operator_name = serializers.CharField(source='operator.get_full_name', read_only=True)
    
    class Meta:
        model = SPCDataPoint
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class SubgroupStatisticsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubgroupStatistics
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class ProcessCapabilitySerializer(serializers.ModelSerializer):
    chart_name = serializers.CharField(source='control_chart.name', read_only=True)
    
    class Meta:
        model = ProcessCapability
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class SPCAlarmSerializer(serializers.ModelSerializer):
    alarm_type_display = serializers.CharField(source='get_alarm_type_display', read_only=True)
    chart_name = serializers.CharField(source='control_chart.name', read_only=True)
    handled_by_name = serializers.CharField(source='handled_by.get_full_name', read_only=True)
    
    class Meta:
        model = SPCAlarm
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


# =====================
# ViewSets
# =====================

class ControlChartViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """控制图管理"""
    queryset = ControlChart.objects.filter(is_deleted=False)
    serializer_class = ControlChartSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['chart_type', 'process', 'item', 'is_active']
    search_fields = ['name', 'measurement_name']
    
    @action(detail=True, methods=['get'])
    def chart_data(self, request, pk=None):
        """获取控制图数据"""
        chart = self.get_object()
        
        # 获取最近100个子组
        subgroups = chart.subgroup_stats.order_by('-subgroup_no')[:100][::-1]
        
        # 计算控制限
        if subgroups:
            x_bars = [float(s.x_bar) for s in subgroups]
            r_values = [float(s.r_value) for s in subgroups if s.r_value]
            
            x_bar_bar = sum(x_bars) / len(x_bars)
            r_bar = sum(r_values) / len(r_values) if r_values else 0
            
            # A2, D3, D4系数 (n=5)
            A2 = 0.577
            D3 = 0
            D4 = 2.114
            
            ucl_xbar = x_bar_bar + A2 * r_bar
            lcl_xbar = x_bar_bar - A2 * r_bar
            
            ucl_r = D4 * r_bar
            lcl_r = D3 * r_bar
        else:
            ucl_xbar = lcl_xbar = x_bar_bar = 0
            ucl_r = lcl_r = r_bar = 0
        
        return Response({
            'chart': ControlChartSerializer(chart).data,
            'subgroups': SubgroupStatisticsSerializer(subgroups, many=True).data,
            'control_limits': {
                'xbar': {
                    'ucl': ucl_xbar,
                    'cl': x_bar_bar,
                    'lcl': lcl_xbar
                },
                'r': {
                    'ucl': ucl_r,
                    'cl': r_bar,
                    'lcl': lcl_r
                }
            }
        })
    
    @action(detail=True, methods=['post'])
    def calculate_capability(self, request, pk=None):
        """计算过程能力"""
        chart = self.get_object()
        
        # 获取数据
        days = int(request.data.get('days', 30))
        start_date = date.today() - timedelta(days=days)
        
        data_points = chart.data_points.filter(
            sample_time__date__gte=start_date
        ).values_list('value', flat=True)
        
        if len(data_points) < 30:
            return Response({'error': '数据点不足30个,无法进行分析'}, status=400)
        
        values = [float(v) for v in data_points]
        n = len(values)
        mean = sum(values) / n
        variance = sum((x - mean) ** 2 for x in values) / (n - 1)
        std_dev = math.sqrt(variance)
        
        usl = float(chart.usl) if chart.usl else None
        lsl = float(chart.lsl) if chart.lsl else None
        
        # 计算Cp, Cpk
        cp = cpk = pp = ppk = None
        
        if usl and lsl and std_dev > 0:
            cp = (usl - lsl) / (6 * std_dev)
            cpu = (usl - mean) / (3 * std_dev)
            cpl = (mean - lsl) / (3 * std_dev)
            cpk = min(cpu, cpl)
            
            # Pp, Ppk (使用总体标准差)
            pp = cp
            ppk = cpk
        
        # 保存分析结果
        capability = ProcessCapability.objects.create(
            control_chart=chart,
            start_date=start_date,
            end_date=date.today(),
            sample_count=n,
            mean=Decimal(str(mean)),
            std_dev=Decimal(str(std_dev)),
            cp=Decimal(str(cp)) if cp else None,
            cpk=Decimal(str(cpk)) if cpk else None,
            pp=Decimal(str(pp)) if pp else None,
            ppk=Decimal(str(ppk)) if ppk else None,
            created_by=request.user
        )
        
        return Response(ProcessCapabilitySerializer(capability).data)


class SPCDataPointViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """SPC数据点管理"""
    queryset = SPCDataPoint.objects.filter(is_deleted=False)
    serializer_class = SPCDataPointSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['control_chart', 'subgroup_no', 'operator']
    
    def perform_create(self, serializer):
        data_point = serializer.save(created_by=self.request.user)
        
        # 更新子组统计
        self.update_subgroup_stats(data_point)
    
    def update_subgroup_stats(self, data_point):
        """更新子组统计量"""
        chart = data_point.control_chart
        subgroup_no = data_point.subgroup_no
        
        points = SPCDataPoint.objects.filter(
            control_chart=chart,
            subgroup_no=subgroup_no,
            is_deleted=False
        ).values_list('value', flat=True)
        
        if not points:
            return
        
        values = [float(v) for v in points]
        n = len(values)
        x_bar = sum(values) / n
        r_value = max(values) - min(values)
        
        # 标准差
        if n > 1:
            variance = sum((x - x_bar) ** 2 for x in values) / (n - 1)
            s_value = math.sqrt(variance)
        else:
            s_value = 0
        
        stats, created = SubgroupStatistics.objects.update_or_create(
            control_chart=chart,
            subgroup_no=subgroup_no,
            defaults={
                'sample_time': data_point.sample_time,
                'x_bar': Decimal(str(x_bar)),
                'r_value': Decimal(str(r_value)),
                's_value': Decimal(str(s_value)),
                'sample_size': n,
                'created_by': self.request.user if created else None
            }
        )
        
        # 检查是否失控
        self.check_out_of_control(chart, stats)
    
    def check_out_of_control(self, chart, stats):
        """检查失控情况"""
        # 简单判断: 超出控制限
        if chart.ucl and stats.x_bar > chart.ucl:
            self.create_alarm(chart, stats, 'OUT_UCL', stats.x_bar)
            stats.is_out_of_control = True
            stats.violation_rules = ['超出UCL']
            stats.save()
        elif chart.lcl and stats.x_bar < chart.lcl:
            self.create_alarm(chart, stats, 'OUT_LCL', stats.x_bar)
            stats.is_out_of_control = True
            stats.violation_rules = ['超出LCL']
            stats.save()
    
    def create_alarm(self, chart, stats, alarm_type, value):
        """创建报警"""
        SPCAlarm.objects.create(
            control_chart=chart,
            alarm_type=alarm_type,
            subgroup_no=stats.subgroup_no,
            value=value,
            description=f'{chart.name} 子组{stats.subgroup_no} {alarm_type}',
            created_by=self.request.user
        )


class SubgroupStatisticsViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """子组统计管理"""
    queryset = SubgroupStatistics.objects.filter(is_deleted=False)
    serializer_class = SubgroupStatisticsSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['control_chart', 'is_out_of_control']


class ProcessCapabilityViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """过程能力管理"""
    queryset = ProcessCapability.objects.filter(is_deleted=False)
    serializer_class = ProcessCapabilitySerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['control_chart']


class SPCAlarmViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """SPC报警管理"""
    queryset = SPCAlarm.objects.filter(is_deleted=False)
    serializer_class = SPCAlarmSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['control_chart', 'alarm_type', 'is_handled']
    
    @action(detail=True, methods=['post'])
    def handle(self, request, pk=None):
        """处理报警"""
        alarm = self.get_object()
        alarm.is_handled = True
        alarm.handled_by = request.user
        alarm.handled_at = timezone.now()
        alarm.action_taken = request.data.get('action_taken', '')
        alarm.save()
        return Response(self.get_serializer(alarm).data)
    
    @action(detail=False, methods=['get'])
    def unhandled(self, request):
        """未处理报警"""
        alarms = self.get_queryset().filter(is_handled=False).order_by('-alarm_time')
        return Response(self.get_serializer(alarms, many=True).data)
