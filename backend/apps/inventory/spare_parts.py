"""
备件管理增强模块
Spare Parts Management Enhancement

功能：
- 设备-备件关联（可用备件清单）
- 备件消耗预测
- 易损件更换周期
- 备件库存预警（按设备关联）

非标自动化行业使用说明：
- 核心功能：记录设备所需备件、易损件更换周期
- 可选功能（建议按需启用）：
  - min_stock/max_stock: 对标准易损件设置，定制备件可不设
  - reorder_point: 标准件可启用自动预警，定制件建议关闭
  - 消耗预测: 基于历史消耗，新设备/新备件数据不足时不准确

建议使用方式：
- 常用易损件（如轴承、密封件）：设置库存阈值
- 定制备件：仅记录关联关系，不设自动预警
"""
from datetime import date, timedelta
from decimal import Decimal

from celery import shared_task
from django.db import models
from django.db.models import Count, F, Sum
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.models import BaseModel

# =============================================================================
# 模型定义
# =============================================================================

class SparePartCategory(BaseModel):
    """备件类别"""
    code = models.CharField(max_length=50, unique=True, verbose_name='类别编码')
    name = models.CharField(max_length=100, verbose_name='类别名称')
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        verbose_name='上级类别'
    )
    description = models.TextField(blank=True, verbose_name='描述')
    sort_order = models.IntegerField(default=0, verbose_name='排序')

    class Meta:
        db_table = 'spare_part_category'
        verbose_name = '备件类别'
        verbose_name_plural = verbose_name
        ordering = ['sort_order', 'code']

    def __str__(self):
        return f'{self.code} - {self.name}'


class SparePart(BaseModel):
    """备件定义"""
    PART_TYPE_CHOICES = [
        ('CONSUMABLE', '耗材'),
        ('WEAR', '易损件'),
        ('STANDARD', '标准件'),
        ('CUSTOM', '定制件'),
        ('ELECTRICAL', '电气件'),
        ('MECHANICAL', '机械件'),
        ('PNEUMATIC', '气动件'),
        ('HYDRAULIC', '液压件'),
        ('OTHER', '其他'),
    ]

    CRITICALITY_CHOICES = [
        ('LOW', '低'),
        ('MEDIUM', '中'),
        ('HIGH', '高'),
        ('CRITICAL', '关键'),
    ]

    # 基本信息
    part_no = models.CharField(max_length=50, unique=True, verbose_name='备件编号')
    name = models.CharField(max_length=200, verbose_name='备件名称')
    specification = models.CharField(max_length=200, blank=True, verbose_name='规格型号')

    # 关联物料
    item = models.ForeignKey(
        'masterdata.Item',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='spare_parts',
        verbose_name='关联物料'
    )

    # 分类
    category = models.ForeignKey(
        SparePartCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='parts',
        verbose_name='备件类别'
    )
    part_type = models.CharField(max_length=20, choices=PART_TYPE_CHOICES, default='STANDARD', verbose_name='备件类型')
    criticality = models.CharField(max_length=20, choices=CRITICALITY_CHOICES, default='MEDIUM', verbose_name='关键程度')

    # 供应信息
    manufacturer = models.CharField(max_length=200, blank=True, verbose_name='制造商')
    manufacturer_part_no = models.CharField(max_length=100, blank=True, verbose_name='原厂料号')
    preferred_supplier = models.ForeignKey(
        'masterdata.Supplier',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='spare_parts',
        verbose_name='首选供应商'
    )

    # 价格
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='单价')
    currency = models.CharField(max_length=10, default='CNY', verbose_name='币种')

    # 库存参数
    unit = models.CharField(max_length=20, default='件', verbose_name='单位')
    min_stock = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='最低库存')
    max_stock = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='最高库存')
    reorder_point = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='补货点')
    reorder_qty = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='补货量')
    lead_time_days = models.IntegerField(default=7, verbose_name='采购周期(天)')

    # 易损件参数
    is_wear_part = models.BooleanField(default=False, verbose_name='是否易损件')
    expected_life_hours = models.IntegerField(default=0, verbose_name='预期寿命(小时)')
    expected_life_cycles = models.IntegerField(default=0, verbose_name='预期寿命(次)')
    replacement_interval_days = models.IntegerField(default=0, verbose_name='更换周期(天)')

    # 技术参数
    technical_specs = models.JSONField(default=dict, blank=True, verbose_name='技术参数')

    # 图片和文档
    image = models.ImageField(upload_to='spare_parts/images/', blank=True, verbose_name='图片')
    datasheet = models.FileField(upload_to='spare_parts/docs/', blank=True, verbose_name='规格书')

    is_active = models.BooleanField(default=True, verbose_name='启用')
    notes = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'spare_part'
        verbose_name = '备件'
        verbose_name_plural = verbose_name
        ordering = ['part_no']

    def __str__(self):
        return f'{self.part_no} - {self.name}'

    def get_current_stock(self):
        """获取当前库存"""
        if self.item:
            from apps.inventory.models import Stock
            stock = Stock.objects.filter(
                item=self.item, is_deleted=False
            ).aggregate(total=Sum('quantity'))
            return stock['total'] or 0
        return 0


class SparePartEquipmentRelation(BaseModel):
    """设备-备件关联（库存模块）"""
    equipment = models.ForeignKey(
        'projects.Equipment',
        on_delete=models.CASCADE,
        related_name='inventory_spare_parts',
        verbose_name='设备'
    )
    spare_part = models.ForeignKey(
        SparePart,
        on_delete=models.CASCADE,
        related_name='equipment_relations',
        verbose_name='备件'
    )

    # 用量
    quantity_per_unit = models.DecimalField(max_digits=10, decimal_places=2, default=1, verbose_name='单机用量')

    # 位置
    position = models.CharField(max_length=200, blank=True, verbose_name='安装位置')

    # 更换周期
    replacement_interval_hours = models.IntegerField(default=0, verbose_name='更换周期(小时)')
    replacement_interval_days = models.IntegerField(default=0, verbose_name='更换周期(天)')
    last_replacement_date = models.DateField(null=True, blank=True, verbose_name='上次更换日期')
    next_replacement_date = models.DateField(null=True, blank=True, verbose_name='下次更换日期')

    # 运行参数
    current_run_hours = models.IntegerField(default=0, verbose_name='当前运行小时')
    total_replacements = models.IntegerField(default=0, verbose_name='累计更换次数')

    is_critical = models.BooleanField(default=False, verbose_name='关键备件')
    notes = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'spare_part_equipment_relation'
        verbose_name = '设备备件关联'
        verbose_name_plural = verbose_name
        unique_together = ['equipment', 'spare_part', 'position']
        ordering = ['equipment', 'spare_part']

    def __str__(self):
        return f'{self.equipment.name} - {self.spare_part.name}'

    def calculate_next_replacement(self):
        """计算下次更换日期"""
        if self.replacement_interval_days > 0 and self.last_replacement_date:
            self.next_replacement_date = self.last_replacement_date + timedelta(days=self.replacement_interval_days)
            self.save(update_fields=['next_replacement_date'])


class SparePartConsumption(BaseModel):
    """备件消耗记录"""
    CONSUMPTION_TYPE_CHOICES = [
        ('REPLACEMENT', '更换'),
        ('REPAIR', '维修'),
        ('PREVENTIVE', '预防性维护'),
        ('EMERGENCY', '紧急更换'),
        ('OTHER', '其他'),
    ]

    spare_part = models.ForeignKey(
        SparePart,
        on_delete=models.PROTECT,
        related_name='consumptions',
        verbose_name='备件'
    )
    equipment = models.ForeignKey(
        'projects.Equipment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='spare_part_consumptions',
        verbose_name='设备'
    )
    equipment_spare = models.ForeignKey(
        SparePartEquipmentRelation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='consumptions',
        verbose_name='设备备件关联'
    )

    consumption_type = models.CharField(max_length=20, choices=CONSUMPTION_TYPE_CHOICES, default='REPLACEMENT', verbose_name='消耗类型')
    consumption_date = models.DateField(verbose_name='消耗日期')
    quantity = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='数量')

    # 关联单据
    service_order = models.ForeignKey(
        'projects.ServiceOrder',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='spare_part_consumptions',
        verbose_name='服务单'
    )
    maintenance_record = models.ForeignKey(
        'projects.MaintenanceSchedule',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='spare_part_consumptions',
        verbose_name='维护记录'
    )

    # 成本
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='单价')
    total_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='总成本')

    # 更换信息
    old_part_condition = models.CharField(max_length=200, blank=True, verbose_name='旧件状态')
    failure_reason = models.TextField(blank=True, verbose_name='故障原因')
    run_hours_at_replacement = models.IntegerField(default=0, verbose_name='更换时运行小时')

    technician = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='操作人员'
    )

    notes = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'spare_part_consumption'
        verbose_name = '备件消耗'
        verbose_name_plural = verbose_name
        ordering = ['-consumption_date']

    def __str__(self):
        return f'{self.spare_part.name} - {self.consumption_date}'

    def save(self, *args, **kwargs):
        # 计算总成本
        self.total_cost = self.quantity * self.unit_cost
        super().save(*args, **kwargs)

        # 更新设备备件关联
        if self.equipment_spare:
            esp = self.equipment_spare
            esp.last_replacement_date = self.consumption_date
            esp.total_replacements = F('total_replacements') + 1
            esp.current_run_hours = 0  # 重置运行小时
            esp.save()
            esp.calculate_next_replacement()


class SparePartForecast(BaseModel):
    """备件需求预测"""
    spare_part = models.ForeignKey(
        SparePart,
        on_delete=models.CASCADE,
        related_name='forecasts',
        verbose_name='备件'
    )

    forecast_date = models.DateField(verbose_name='预测日期')
    forecast_period = models.CharField(
        max_length=20,
        choices=[
            ('MONTHLY', '月度'),
            ('QUARTERLY', '季度'),
            ('YEARLY', '年度'),
        ],
        default='MONTHLY',
        verbose_name='预测周期'
    )

    # 预测数量
    predicted_quantity = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='预测需求量')
    confidence_level = models.DecimalField(max_digits=5, decimal_places=2, default=0.8, verbose_name='置信度')

    # 历史数据
    historical_avg = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='历史平均消耗')
    historical_std = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='历史标准差')

    # 预测方法
    method = models.CharField(max_length=50, default='MOVING_AVG', verbose_name='预测方法')

    class Meta:
        db_table = 'spare_part_forecast'
        verbose_name = '备件需求预测'
        verbose_name_plural = verbose_name
        ordering = ['-forecast_date']


class SparePartAlert(BaseModel):
    """备件预警"""
    ALERT_TYPE_CHOICES = [
        ('LOW_STOCK', '库存不足'),
        ('REPLACEMENT_DUE', '即将更换'),
        ('EXPIRED', '已过期'),
        ('NO_STOCK', '缺货'),
    ]

    spare_part = models.ForeignKey(
        SparePart,
        on_delete=models.CASCADE,
        related_name='alerts',
        verbose_name='备件'
    )
    equipment = models.ForeignKey(
        'projects.Equipment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='spare_part_alerts',
        verbose_name='设备'
    )

    alert_type = models.CharField(max_length=20, choices=ALERT_TYPE_CHOICES, verbose_name='预警类型')
    alert_date = models.DateTimeField(auto_now_add=True, verbose_name='预警时间')

    current_stock = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='当前库存')
    required_stock = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='需求库存')

    message = models.TextField(verbose_name='预警消息')

    is_resolved = models.BooleanField(default=False, verbose_name='已处理')
    resolved_at = models.DateTimeField(null=True, blank=True, verbose_name='处理时间')
    resolved_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='处理人'
    )
    resolution_notes = models.TextField(blank=True, verbose_name='处理说明')

    class Meta:
        db_table = 'spare_part_alert'
        verbose_name = '备件预警'
        verbose_name_plural = verbose_name
        ordering = ['-alert_date']


# =============================================================================
# 序列化器
# =============================================================================

class SparePartCategorySerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()

    class Meta:
        model = SparePartCategory
        fields = '__all__'

    def get_children(self, obj):
        children = obj.children.filter(is_deleted=False)
        return SparePartCategorySerializer(children, many=True).data


class SparePartSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    part_type_display = serializers.CharField(source='get_part_type_display', read_only=True)
    criticality_display = serializers.CharField(source='get_criticality_display', read_only=True)
    item_name = serializers.CharField(source='item.name', read_only=True)
    supplier_name = serializers.CharField(source='preferred_supplier.name', read_only=True)
    current_stock = serializers.SerializerMethodField()

    class Meta:
        model = SparePart
        fields = '__all__'

    def get_current_stock(self, obj):
        return obj.get_current_stock()


class SparePartListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    part_type_display = serializers.CharField(source='get_part_type_display', read_only=True)
    criticality_display = serializers.CharField(source='get_criticality_display', read_only=True)
    current_stock = serializers.SerializerMethodField()

    class Meta:
        model = SparePart
        fields = [
            'id', 'part_no', 'name', 'specification', 'category', 'category_name',
            'part_type', 'part_type_display', 'criticality', 'criticality_display',
            'unit_price', 'min_stock', 'reorder_point', 'current_stock',
            'is_wear_part', 'is_active'
        ]

    def get_current_stock(self, obj):
        return obj.get_current_stock()


class SparePartEquipmentRelationSerializer(serializers.ModelSerializer):
    equipment_name = serializers.CharField(source='equipment.name', read_only=True)
    equipment_no = serializers.CharField(source='equipment.equipment_no', read_only=True)
    spare_part_no = serializers.CharField(source='spare_part.part_no', read_only=True)
    spare_part_name = serializers.CharField(source='spare_part.name', read_only=True)
    current_stock = serializers.SerializerMethodField()

    class Meta:
        model = SparePartEquipmentRelation
        fields = '__all__'

    def get_current_stock(self, obj):
        return obj.spare_part.get_current_stock()


class SparePartConsumptionSerializer(serializers.ModelSerializer):
    spare_part_no = serializers.CharField(source='spare_part.part_no', read_only=True)
    spare_part_name = serializers.CharField(source='spare_part.name', read_only=True)
    equipment_name = serializers.CharField(source='equipment.name', read_only=True)
    consumption_type_display = serializers.CharField(source='get_consumption_type_display', read_only=True)
    technician_name = serializers.CharField(source='technician.get_full_name', read_only=True)

    class Meta:
        model = SparePartConsumption
        fields = '__all__'
        read_only_fields = ['total_cost']


class SparePartForecastSerializer(serializers.ModelSerializer):
    spare_part_no = serializers.CharField(source='spare_part.part_no', read_only=True)
    spare_part_name = serializers.CharField(source='spare_part.name', read_only=True)

    class Meta:
        model = SparePartForecast
        fields = '__all__'


class SparePartAlertSerializer(serializers.ModelSerializer):
    spare_part_no = serializers.CharField(source='spare_part.part_no', read_only=True)
    spare_part_name = serializers.CharField(source='spare_part.name', read_only=True)
    equipment_name = serializers.CharField(source='equipment.name', read_only=True)
    alert_type_display = serializers.CharField(source='get_alert_type_display', read_only=True)

    class Meta:
        model = SparePartAlert
        fields = '__all__'


# =============================================================================
# 视图集
# =============================================================================

class SparePartCategoryViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """备件类别管理"""
    queryset = SparePartCategory.objects.filter(is_deleted=False)

    def get_queryset(self):
        return SparePartCategory.objects.filter(is_deleted=False, parent__isnull=True)
    serializer_class = SparePartCategorySerializer
    permission_classes = [IsAuthenticated]
    search_fields = ['code', 'name']


class SparePartViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """备件管理"""
    queryset = SparePart.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filterset_fields = ['category', 'part_type', 'criticality', 'is_wear_part', 'is_active']
    search_fields = ['part_no', 'name', 'specification', 'manufacturer_part_no']
    ordering_fields = ['part_no', 'name', 'unit_price']

    def get_serializer_class(self):
        if self.action == 'list':
            return SparePartListSerializer
        return SparePartSerializer

    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        """低库存备件"""
        parts = []
        for part in self.get_queryset().filter(is_active=True):
            current = part.get_current_stock()
            if current <= part.reorder_point:
                parts.append({
                    'id': part.id,
                    'part_no': part.part_no,
                    'name': part.name,
                    'current_stock': current,
                    'min_stock': float(part.min_stock),
                    'reorder_point': float(part.reorder_point),
                    'reorder_qty': float(part.reorder_qty),
                    'criticality': part.criticality,
                })

        return Response(sorted(parts, key=lambda x: x['criticality'], reverse=True))

    @action(detail=True, methods=['get'])
    def consumption_history(self, request, pk=None):
        """消耗历史"""
        part = self.get_object()
        months = int(request.query_params.get('months', 12))

        start_date = date.today() - timedelta(days=months * 30)
        consumptions = SparePartConsumption.objects.filter(
            spare_part=part,
            consumption_date__gte=start_date,
            is_deleted=False
        ).values('consumption_date__year', 'consumption_date__month').annotate(
            total_qty=Sum('quantity'),
            total_cost=Sum('total_cost'),
            count=Count('id')
        ).order_by('consumption_date__year', 'consumption_date__month')

        return Response(list(consumptions))

    @action(detail=True, methods=['get'])
    def equipment_usage(self, request, pk=None):
        """设备使用情况"""
        part = self.get_object()
        usages = SparePartEquipmentRelation.objects.filter(
            spare_part=part, is_deleted=False
        ).select_related('equipment')

        return Response(SparePartEquipmentRelationSerializer(usages, many=True).data)

    @action(detail=False, methods=['get'])
    def forecast_summary(self, request):
        """需求预测汇总"""
        period = request.query_params.get('period', 'MONTHLY')

        forecasts = SparePartForecast.objects.filter(
            forecast_period=period,
            forecast_date__gte=date.today()
        ).select_related('spare_part').order_by('forecast_date')[:50]

        return Response(SparePartForecastSerializer(forecasts, many=True).data)


class SparePartEquipmentRelationViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """设备备件关联管理"""
    queryset = SparePartEquipmentRelation.objects.filter(is_deleted=False)
    serializer_class = SparePartEquipmentRelationSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['equipment', 'spare_part', 'is_critical']

    @action(detail=False, methods=['get'])
    def replacement_due(self, request):
        """即将更换的备件"""
        days = int(request.query_params.get('days', 30))
        due_date = date.today() + timedelta(days=days)

        items = self.get_queryset().filter(
            next_replacement_date__lte=due_date,
            next_replacement_date__gte=date.today()
        ).order_by('next_replacement_date')

        return Response(SparePartEquipmentRelationSerializer(items, many=True).data)

    @action(detail=True, methods=['post'])
    def record_replacement(self, request, pk=None):
        """记录更换"""
        esp = self.get_object()

        consumption = SparePartConsumption.objects.create(
            spare_part=esp.spare_part,
            equipment=esp.equipment,
            equipment_spare=esp,
            consumption_type=request.data.get('consumption_type', 'REPLACEMENT'),
            consumption_date=request.data.get('date', date.today()),
            quantity=request.data.get('quantity', esp.quantity_per_unit),
            unit_cost=esp.spare_part.unit_price,
            run_hours_at_replacement=request.data.get('run_hours', esp.current_run_hours),
            failure_reason=request.data.get('failure_reason', ''),
            technician=request.user,
            created_by=request.user
        )

        return Response({
            'message': '更换记录已创建',
            'consumption_id': consumption.id
        })


class SparePartConsumptionViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """备件消耗记录"""
    queryset = SparePartConsumption.objects.filter(is_deleted=False)
    serializer_class = SparePartConsumptionSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['spare_part', 'equipment', 'consumption_type', 'technician']
    ordering_fields = ['consumption_date', 'total_cost']

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """消耗统计"""
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        queryset = self.get_queryset()
        if start_date:
            queryset = queryset.filter(consumption_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(consumption_date__lte=end_date)

        # 按备件统计
        by_part = queryset.values(
            'spare_part__part_no', 'spare_part__name'
        ).annotate(
            total_qty=Sum('quantity'),
            total_cost=Sum('total_cost'),
            count=Count('id')
        ).order_by('-total_cost')[:20]

        # 按设备统计
        by_equipment = queryset.exclude(equipment__isnull=True).values(
            'equipment__equipment_no', 'equipment__name'
        ).annotate(
            total_qty=Sum('quantity'),
            total_cost=Sum('total_cost'),
            count=Count('id')
        ).order_by('-total_cost')[:20]

        # 按类型统计
        by_type = queryset.values('consumption_type').annotate(
            total_qty=Sum('quantity'),
            total_cost=Sum('total_cost'),
            count=Count('id')
        )

        return Response({
            'by_part': list(by_part),
            'by_equipment': list(by_equipment),
            'by_type': list(by_type),
            'total_cost': queryset.aggregate(total=Sum('total_cost'))['total'] or 0
        })


class SparePartAlertViewSet(SoftDeleteMixin, viewsets.ModelViewSet):
    """备件预警管理"""
    queryset = SparePartAlert.objects.filter(is_deleted=False)
    serializer_class = SparePartAlertSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['alert_type', 'is_resolved', 'spare_part', 'equipment']
    ordering_fields = ['alert_date']

    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """处理预警"""
        alert = self.get_object()
        alert.is_resolved = True
        alert.resolved_at = timezone.now()
        alert.resolved_by = request.user
        alert.resolution_notes = request.data.get('notes', '')
        alert.save()
        return Response(SparePartAlertSerializer(alert).data)

    @action(detail=False, methods=['get'])
    def pending(self, request):
        """待处理预警"""
        alerts = self.get_queryset().filter(is_resolved=False).order_by('-alert_date')
        return Response(SparePartAlertSerializer(alerts, many=True).data)


# =============================================================================
# 定时任务
# =============================================================================

@shared_task
def check_spare_part_stock():
    """检查备件库存并生成预警"""

    alerts_created = 0

    for part in SparePart.objects.filter(is_active=True, is_deleted=False):
        current_stock = part.get_current_stock()

        # 检查库存不足
        if current_stock <= part.reorder_point and current_stock > 0:
            alert, created = SparePartAlert.objects.get_or_create(
                spare_part=part,
                alert_type='LOW_STOCK',
                is_resolved=False,
                defaults={
                    'current_stock': current_stock,
                    'required_stock': part.min_stock,
                    'message': f'备件 [{part.part_no}] {part.name} 库存不足，当前库存 {current_stock}，最低库存 {part.min_stock}'
                }
            )
            if created:
                alerts_created += 1

        # 检查缺货
        elif current_stock <= 0:
            alert, created = SparePartAlert.objects.get_or_create(
                spare_part=part,
                alert_type='NO_STOCK',
                is_resolved=False,
                defaults={
                    'current_stock': 0,
                    'required_stock': part.min_stock,
                    'message': f'备件 [{part.part_no}] {part.name} 已缺货!'
                }
            )
            if created:
                alerts_created += 1

    return f'Created {alerts_created} stock alerts'


@shared_task
def check_replacement_due():
    """检查即将更换的备件"""
    today = date.today()
    warning_days = [30, 14, 7, 3, 1]

    alerts_created = 0

    for days in warning_days:
        due_date = today + timedelta(days=days)

        for esp in SparePartEquipmentRelation.objects.filter(
            next_replacement_date=due_date,
            is_deleted=False
        ):
            alert, created = SparePartAlert.objects.get_or_create(
                spare_part=esp.spare_part,
                equipment=esp.equipment,
                alert_type='REPLACEMENT_DUE',
                is_resolved=False,
                defaults={
                    'message': f'设备 [{esp.equipment.equipment_no}] 的备件 [{esp.spare_part.part_no}] {esp.spare_part.name} 将于 {days} 天后需要更换'
                }
            )
            if created:
                alerts_created += 1

    return f'Created {alerts_created} replacement alerts'


@shared_task
def generate_consumption_forecast():
    """生成备件消耗预测"""
    from django.db.models.functions import TruncMonth

    today = date.today()

    for part in SparePart.objects.filter(is_active=True, is_deleted=False):
        # 获取过去12个月的消耗数据
        history = SparePartConsumption.objects.filter(
            spare_part=part,
            consumption_date__gte=today - timedelta(days=365),
            is_deleted=False
        ).annotate(
            month=TruncMonth('consumption_date')
        ).values('month').annotate(
            qty=Sum('quantity')
        ).order_by('month')

        if history.count() < 3:
            continue

        # 简单移动平均预测
        quantities = [h['qty'] for h in history]
        avg_qty = sum(quantities) / len(quantities)

        # 计算标准差
        variance = sum((q - avg_qty) ** 2 for q in quantities) / len(quantities)
        std_qty = variance ** 0.5

        # 创建下月预测
        next_month = (today.replace(day=1) + timedelta(days=32)).replace(day=1)

        SparePartForecast.objects.update_or_create(
            spare_part=part,
            forecast_date=next_month,
            forecast_period='MONTHLY',
            defaults={
                'predicted_quantity': Decimal(str(avg_qty * 1.1)),  # 增加10%安全系数
                'historical_avg': Decimal(str(avg_qty)),
                'historical_std': Decimal(str(std_qty)),
                'method': 'MOVING_AVG'
            }
        )

    return 'Forecast generated'
