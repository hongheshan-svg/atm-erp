"""
库存预警管理
Stock Alert Management

功能：库存预警规则、预警记录管理

非标自动化行业建议配置：
- 低库存预警：仅对常用标准件设置
- 效期预警：针对有保质期的物料（如润滑油、密封件等）
- 项目缺料预警：通过MRP计划自动生成

注：呆滞预警、补货预警、积压预警等对非标定制件意义不大，
可根据实际需要选择性启用。
"""

from datetime import date, timedelta
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


class StockAlertRule(BaseModel):
    """
    库存预警规则
    """

    ALERT_TYPES = [
        ('LOW_STOCK', '低库存预警'),
        ('OVERSTOCK', '积压预警'),
        ('EXPIRY', '效期预警'),
        ('SLOW_MOVING', '呆滞预警'),
        ('REORDER', '补货预警'),
    ]

    SCOPE_CHOICES = [
        ('ALL', '所有物料'),
        ('CATEGORY', '按分类'),
        ('ITEM', '指定物料'),
    ]

    name = models.CharField(max_length=100, verbose_name='规则名称')
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES, verbose_name='预警类型')

    # 适用范围
    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES, default='ALL', verbose_name='适用范围')
    category = models.ForeignKey(
        'masterdata.ItemCategory',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='alert_rules',
        verbose_name='物料分类',
    )
    items = models.ManyToManyField('masterdata.Item', blank=True, related_name='alert_rules', verbose_name='指定物料')

    # 阈值配置
    threshold_qty = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True, verbose_name='数量阈值')
    threshold_days = models.IntegerField(null=True, blank=True, verbose_name='天数阈值')
    threshold_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True, verbose_name='百分比阈值'
    )

    # 通知设置
    notify_roles = models.JSONField(default=list, blank=True, verbose_name='通知角色')
    notify_users = models.JSONField(default=list, blank=True, verbose_name='通知用户')

    is_active = models.BooleanField(default=True, verbose_name='启用')
    description = models.TextField(blank=True, verbose_name='描述')

    class Meta:
        db_table = 'inventory_stock_alert_rule'
        verbose_name = '库存预警规则'
        verbose_name_plural = verbose_name
        ordering = ['alert_type', 'name']

    def __str__(self):
        return f'{self.name} ({self.get_alert_type_display()})'


class StockAlert(BaseModel):
    """
    库存预警记录
    """

    STATUS_CHOICES = [
        ('ACTIVE', '活跃'),
        ('ACKNOWLEDGED', '已确认'),
        ('RESOLVED', '已解决'),
        ('IGNORED', '已忽略'),
    ]

    SEVERITY_LEVELS = [
        ('INFO', '提示'),
        ('WARNING', '警告'),
        ('CRITICAL', '严重'),
    ]

    rule = models.ForeignKey(
        StockAlertRule, on_delete=models.SET_NULL, null=True, blank=True, related_name='alerts', verbose_name='预警规则'
    )
    item = models.ForeignKey(
        'masterdata.Item', on_delete=models.CASCADE, related_name='stock_alerts', verbose_name='物料'
    )
    warehouse = models.ForeignKey(
        'masterdata.Warehouse',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stock_alerts',
        verbose_name='仓库',
    )

    alert_type = models.CharField(max_length=20, verbose_name='预警类型')
    severity = models.CharField(max_length=20, choices=SEVERITY_LEVELS, default='WARNING', verbose_name='严重程度')
    title = models.CharField(max_length=200, verbose_name='预警标题')
    description = models.TextField(verbose_name='预警描述')

    # 预警数据
    current_qty = models.DecimalField(max_digits=18, decimal_places=4, default=0, verbose_name='当前库存')
    threshold_value = models.DecimalField(max_digits=18, decimal_places=4, default=0, verbose_name='阈值')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE', verbose_name='状态')

    # 处理
    handler = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='handled_stock_alerts',
        verbose_name='处理人',
    )
    handled_at = models.DateTimeField(null=True, blank=True, verbose_name='处理时间')
    resolution = models.TextField(blank=True, verbose_name='解决方案')

    class Meta:
        db_table = 'inventory_stock_alert'
        verbose_name = '库存预警'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.item.name} - {self.title}'


class StockAlertService:
    """库存预警服务"""

    @staticmethod
    def check_all_alerts():
        """检查所有预警"""

        alerts_created = []

        # 获取所有活跃的预警规则
        rules = StockAlertRule.objects.filter(is_active=True, is_deleted=False)

        for rule in rules:
            if rule.alert_type == 'LOW_STOCK':
                alerts = StockAlertService._check_low_stock(rule)
            elif rule.alert_type == 'OVERSTOCK':
                alerts = StockAlertService._check_overstock(rule)
            elif rule.alert_type == 'REORDER':
                alerts = StockAlertService._check_reorder(rule)
            elif rule.alert_type == 'SLOW_MOVING':
                alerts = StockAlertService._check_slow_moving(rule)
            else:
                continue

            alerts_created.extend(alerts)

        return alerts_created

    @staticmethod
    def _get_items_for_rule(rule):
        """获取规则适用的物料"""
        from apps.masterdata.models import Item

        if rule.scope == 'ALL':
            return Item.objects.filter(is_deleted=False)
        elif rule.scope == 'CATEGORY' and rule.category:
            return Item.objects.filter(category=rule.category, is_deleted=False)
        elif rule.scope == 'ITEM':
            return rule.items.filter(is_deleted=False)
        return Item.objects.none()

    @staticmethod
    def _check_low_stock(rule):
        """检查低库存"""
        from apps.inventory.models import Stock

        alerts = []
        items = StockAlertService._get_items_for_rule(rule)

        for item in items:
            # 获取安全库存阈值
            threshold = rule.threshold_qty or item.safety_stock or Decimal('0')

            if threshold <= 0:
                continue

            # 获取当前库存
            current_qty = Stock.objects.filter(item=item, is_deleted=False).aggregate(total=Sum('quantity'))[
                'total'
            ] or Decimal('0')

            if current_qty < threshold:
                # 创建预警
                alert = StockAlertService._create_alert(
                    rule=rule,
                    item=item,
                    alert_type='LOW_STOCK',
                    severity='CRITICAL' if current_qty <= 0 else 'WARNING',
                    title=f'{item.name} 库存不足',
                    description=f'物料 {item.code} {item.name} 当前库存 {current_qty}，低于安全库存 {threshold}',
                    current_qty=current_qty,
                    threshold_value=threshold,
                )
                if alert:
                    alerts.append(alert)

        return alerts

    @staticmethod
    def _check_overstock(rule):
        """检查库存积压"""
        from apps.inventory.models import Stock

        alerts = []
        items = StockAlertService._get_items_for_rule(rule)
        threshold_factor = rule.threshold_percentage or Decimal('200')  # 默认超过安全库存200%

        for item in items:
            if not item.safety_stock or item.safety_stock <= 0:
                continue

            max_stock = item.safety_stock * threshold_factor / 100

            current_qty = Stock.objects.filter(item=item, is_deleted=False).aggregate(total=Sum('quantity'))[
                'total'
            ] or Decimal('0')

            if current_qty > max_stock:
                alert = StockAlertService._create_alert(
                    rule=rule,
                    item=item,
                    alert_type='OVERSTOCK',
                    severity='WARNING',
                    title=f'{item.name} 库存积压',
                    description=f'物料 {item.code} {item.name} 当前库存 {current_qty}，超过建议库存 {max_stock}',
                    current_qty=current_qty,
                    threshold_value=max_stock,
                )
                if alert:
                    alerts.append(alert)

        return alerts

    @staticmethod
    def _check_reorder(rule):
        """检查补货点"""
        from apps.inventory.models import Stock

        alerts = []
        items = StockAlertService._get_items_for_rule(rule)

        for item in items:
            # 补货点 = 安全库存 + 日均消耗 * 提前期
            reorder_point = item.reorder_point if hasattr(item, 'reorder_point') else item.safety_stock

            if not reorder_point or reorder_point <= 0:
                continue

            current_qty = Stock.objects.filter(item=item, is_deleted=False).aggregate(total=Sum('quantity'))[
                'total'
            ] or Decimal('0')

            if current_qty <= reorder_point:
                alert = StockAlertService._create_alert(
                    rule=rule,
                    item=item,
                    alert_type='REORDER',
                    severity='INFO',
                    title=f'{item.name} 达到补货点',
                    description=f'物料 {item.code} {item.name} 当前库存 {current_qty}，已达补货点 {reorder_point}，建议补货',
                    current_qty=current_qty,
                    threshold_value=reorder_point,
                )
                if alert:
                    alerts.append(alert)

        return alerts

    @staticmethod
    def _check_slow_moving(rule):
        """检查呆滞物料"""
        from apps.inventory.models import Stock, StockMove

        alerts = []
        items = StockAlertService._get_items_for_rule(rule)
        days = rule.threshold_days or 90  # 默认90天无出库

        cutoff_date = date.today() - timedelta(days=days)

        for item in items:
            current_qty = Stock.objects.filter(item=item, is_deleted=False).aggregate(total=Sum('quantity'))[
                'total'
            ] or Decimal('0')

            if current_qty <= 0:
                continue

            # 检查最近出库记录
            last_out = StockMove.objects.filter(
                item=item, move_type='OUT', created_at__gte=cutoff_date, is_deleted=False
            ).exists()

            if not last_out:
                alert = StockAlertService._create_alert(
                    rule=rule,
                    item=item,
                    alert_type='SLOW_MOVING',
                    severity='INFO',
                    title=f'{item.name} 呆滞物料',
                    description=f'物料 {item.code} {item.name} 库存 {current_qty}，超过 {days} 天无出库记录',
                    current_qty=current_qty,
                    threshold_value=Decimal(days),
                )
                if alert:
                    alerts.append(alert)

        return alerts

    @staticmethod
    def _create_alert(
        rule, item, alert_type, severity, title, description, current_qty, threshold_value, warehouse=None
    ):
        """创建预警记录"""
        # 检查是否已存在相同的活跃预警
        existing = StockAlert.objects.filter(
            item=item, alert_type=alert_type, status='ACTIVE', is_deleted=False
        ).exists()

        if existing:
            return None

        return StockAlert.objects.create(
            rule=rule,
            item=item,
            warehouse=warehouse,
            alert_type=alert_type,
            severity=severity,
            title=title,
            description=description,
            current_qty=current_qty,
            threshold_value=threshold_value,
        )


# =====================
# Serializers
# =====================


class StockAlertRuleSerializer(serializers.ModelSerializer):
    alert_type_display = serializers.CharField(source='get_alert_type_display', read_only=True)
    scope_display = serializers.CharField(source='get_scope_display', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = StockAlertRule
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class StockAlertSerializer(serializers.ModelSerializer):
    item_code = serializers.CharField(source='item.code', read_only=True)
    item_name = serializers.CharField(source='item.name', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    rule_name = serializers.CharField(source='rule.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    handler_name = serializers.CharField(source='handler.get_full_name', read_only=True)

    class Meta:
        model = StockAlert
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'handler', 'handled_at']


class StockAlertListSerializer(serializers.ModelSerializer):
    item_code = serializers.CharField(source='item.code', read_only=True)
    item_name = serializers.CharField(source='item.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)

    class Meta:
        model = StockAlert
        fields = [
            'id',
            'item',
            'item_code',
            'item_name',
            'alert_type',
            'severity',
            'severity_display',
            'title',
            'current_qty',
            'threshold_value',
            'status',
            'status_display',
            'created_at',
        ]


# =====================
# ViewSets
# =====================


class StockAlertRuleViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """库存预警规则管理"""

    queryset = StockAlertRule.objects.filter(is_deleted=False)
    serializer_class = StockAlertRuleSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['alert_type', 'scope', 'is_active']
    search_fields = ['name', 'description']

    @action(detail=False, methods=['post'])
    def init_rules(self, request):
        """初始化默认规则"""
        rules = [
            ('低库存预警', 'LOW_STOCK', 'ALL', None, None, None),
            ('库存积压预警', 'OVERSTOCK', 'ALL', None, None, Decimal('200')),
            ('补货提醒', 'REORDER', 'ALL', None, None, None),
            ('呆滞物料预警', 'SLOW_MOVING', 'ALL', None, 90, None),
        ]

        created = 0
        for name, alert_type, scope, qty, days, pct in rules:
            _, c = StockAlertRule.objects.get_or_create(
                name=name,
                defaults={
                    'alert_type': alert_type,
                    'scope': scope,
                    'threshold_qty': qty,
                    'threshold_days': days,
                    'threshold_percentage': pct,
                    'created_by': request.user,
                },
            )
            if c:
                created += 1

        return Response({'success': True, 'created': created})


class StockAlertViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """库存预警管理"""

    queryset = StockAlert.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filterset_fields = ['alert_type', 'severity', 'status', 'item']
    search_fields = ['title', 'item__code', 'item__name']
    ordering_fields = ['created_at', 'severity']

    def get_serializer_class(self):
        if self.action == 'list':
            return StockAlertListSerializer
        return StockAlertSerializer

    @action(detail=False, methods=['post'])
    def check_all(self, request):
        """检查所有预警"""
        alerts = StockAlertService.check_all_alerts()
        return Response(
            {'success': True, 'alerts_created': len(alerts), 'alerts': StockAlertListSerializer(alerts, many=True).data}
        )

    @action(detail=True, methods=['post'])
    def acknowledge(self, request, pk=None):
        """确认预警"""
        alert = self.get_object()
        alert.status = 'ACKNOWLEDGED'
        alert.handler = request.user
        alert.handled_at = timezone.now()
        alert.save()
        return Response(self.get_serializer(alert).data)

    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """解决预警"""
        alert = self.get_object()
        alert.status = 'RESOLVED'
        alert.resolution = request.data.get('resolution', '')
        alert.handler = request.user
        alert.handled_at = timezone.now()
        alert.save()
        return Response(self.get_serializer(alert).data)

    @action(detail=True, methods=['post'])
    def ignore(self, request, pk=None):
        """忽略预警"""
        alert = self.get_object()
        alert.status = 'IGNORED'
        alert.resolution = request.data.get('reason', '已忽略')
        alert.handler = request.user
        alert.handled_at = timezone.now()
        alert.save()
        return Response(self.get_serializer(alert).data)

    @action(detail=False, methods=['get'])
    def active(self, request):
        """获取活跃预警"""
        alerts = self.get_queryset().filter(status='ACTIVE')
        return Response(StockAlertListSerializer(alerts, many=True).data)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """预警汇总"""
        qs = self.get_queryset().filter(status='ACTIVE')

        by_type = qs.values('alert_type').annotate(count=Count('id'))
        by_severity = qs.values('severity').annotate(count=Count('id'))

        return Response({'total_active': qs.count(), 'by_type': list(by_type), 'by_severity': list(by_severity)})
