"""
Predictive Analytics for ERP
"""
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone
from rest_framework import serializers, viewsets, status
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.core.models import BaseModel


class PredictionModel(BaseModel):
    MODEL_TYPE_CHOICES = [
        ('cost_trend', '成本趋势'),
        ('delivery_risk', '交付风险'),
        ('capacity_load', '产能负荷'),
        ('quality_prediction', '质量预测'),
        ('demand_forecast', '需求预测'),
    ]

    name = models.CharField(max_length=200, verbose_name='模型名称')
    model_type = models.CharField(
        max_length=30, choices=MODEL_TYPE_CHOICES, verbose_name='模型类型'
    )
    config = models.JSONField(default=dict, verbose_name='配置')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')

    class Meta:
        db_table = 'reports_prediction_model'
        ordering = ['model_type', 'name']
        verbose_name = '预测模型'
        verbose_name_plural = '预测模型'

    def __str__(self):
        return self.name


class PredictionResult(BaseModel):
    model = models.ForeignKey(
        PredictionModel, on_delete=models.CASCADE,
        related_name='results', verbose_name='预测模型'
    )
    result_type = models.CharField(max_length=100, verbose_name='结果类型')
    result_data = models.JSONField(default=dict, verbose_name='结果数据')
    confidence = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True, verbose_name='置信度'
    )
    valid_until = models.DateTimeField(null=True, blank=True, verbose_name='有效期至')

    class Meta:
        db_table = 'reports_prediction_result'
        ordering = ['-created_at']
        verbose_name = '预测结果'
        verbose_name_plural = '预测结果'

    def __str__(self):
        return f"{self.model.name} - {self.result_type}"


class RiskAlert(BaseModel):
    ALERT_TYPE_CHOICES = [
        ('cost_overrun', '成本超支'),
        ('schedule_delay', '进度延迟'),
        ('capacity_shortage', '产能不足'),
        ('inventory_anomaly', '库存异常'),
        ('quality_risk', '质量风险'),
        ('supply_chain_risk', '供应链风险'),
    ]
    SEVERITY_CHOICES = [
        ('low', '低'),
        ('medium', '中'),
        ('high', '高'),
        ('critical', '严重'),
    ]
    STATUS_CHOICES = [
        ('open', '待处理'),
        ('acknowledged', '已确认'),
        ('resolved', '已解决'),
        ('closed', '已关闭'),
    ]

    alert_type = models.CharField(
        max_length=30, choices=ALERT_TYPE_CHOICES, verbose_name='告警类型'
    )
    severity = models.CharField(
        max_length=10, choices=SEVERITY_CHOICES, verbose_name='严重程度'
    )
    title = models.CharField(max_length=300, verbose_name='标题')
    description = models.TextField(verbose_name='描述')
    related_object_type = models.CharField(
        max_length=100, blank=True, default='', verbose_name='关联对象类型'
    )
    related_object_id = models.IntegerField(null=True, blank=True, verbose_name='关联对象ID')
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='open', verbose_name='状态'
    )
    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='acknowledged_risk_alerts', verbose_name='确认人'
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='resolved_risk_alerts', verbose_name='解决人'
    )
    resolution = models.TextField(blank=True, default='', verbose_name='解决方案')

    class Meta:
        db_table = 'reports_risk_alert'
        ordering = ['-created_at']
        verbose_name = '风险告警'
        verbose_name_plural = '风险告警'

    def __str__(self):
        return f"[{self.get_severity_display()}] {self.title}"


class PredictionService:
    """Predictive analytics service."""

    @staticmethod
    def analyze_cost_trend():
        from django.db.models import Sum, Count
        from django.db.models.functions import TruncMonth
        try:
            from apps.projects.models import Project
            projects = Project.objects.filter(is_deleted=False).annotate(
                month=TruncMonth('created_at')
            ).values('month').annotate(
                count=Count('id'),
                total_budget=Sum('budget'),
            ).order_by('month')
            return list(projects)
        except Exception:
            return []

    @staticmethod
    def analyze_delivery_risk():
        try:
            from apps.projects.models import Project
            projects = Project.objects.filter(
                is_deleted=False, status__in=['in_progress', 'active']
            )
            risks = []
            for proj in projects:
                planned_end = getattr(proj, 'planned_end_date', None) or getattr(proj, 'end_date', None)
                if planned_end and planned_end < timezone.now().date():
                    risks.append({
                        'project_id': proj.id,
                        'project_name': str(proj),
                        'planned_end': str(planned_end),
                        'days_overdue': (timezone.now().date() - planned_end).days,
                        'risk_level': 'high',
                    })
            return risks
        except Exception:
            return []

    @staticmethod
    def analyze_capacity_load():
        try:
            from apps.production.models import ProductionOrder
            from django.db.models import Count
            load = ProductionOrder.objects.filter(
                is_deleted=False, status='in_progress'
            ).values('work_center').annotate(
                active_orders=Count('id')
            ).order_by('-active_orders')
            return list(load)
        except Exception:
            return []


# ─── Serializers ────────────────────────────────────────────────

class PredictionModelSerializer(serializers.ModelSerializer):
    model_type_display = serializers.CharField(source='get_model_type_display', read_only=True)

    class Meta:
        model = PredictionModel
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class PredictionResultSerializer(serializers.ModelSerializer):
    model_name = serializers.CharField(source='model.name', read_only=True)

    class Meta:
        model = PredictionResult
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class RiskAlertSerializer(serializers.ModelSerializer):
    alert_type_display = serializers.CharField(source='get_alert_type_display', read_only=True)
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = RiskAlert
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


# ─── ViewSets ───────────────────────────────────────────────────

class PredictionModelViewSet(viewsets.ModelViewSet):
    serializer_class = PredictionModelSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return PredictionModel.objects.filter(is_deleted=False)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class PredictionResultViewSet(viewsets.ModelViewSet):
    serializer_class = PredictionResultSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = PredictionResult.objects.filter(is_deleted=False)
        model_id = self.request.query_params.get('model_id')
        if model_id:
            qs = qs.filter(model_id=model_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class RiskAlertViewSet(viewsets.ModelViewSet):
    serializer_class = RiskAlertSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = RiskAlert.objects.filter(is_deleted=False)
        alert_status = self.request.query_params.get('status')
        severity = self.request.query_params.get('severity')
        if alert_status:
            qs = qs.filter(status=alert_status)
        if severity:
            qs = qs.filter(severity=severity)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def acknowledge(self, request, pk=None):
        alert = self.get_object()
        if alert.status != 'open':
            return Response({'error': '只有待处理的告警才能确认'}, status=status.HTTP_400_BAD_REQUEST)
        alert.status = 'acknowledged'
        alert.acknowledged_by = request.user
        alert.save(update_fields=['status', 'acknowledged_by', 'updated_at'])
        return Response(RiskAlertSerializer(alert).data)

    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        alert = self.get_object()
        if alert.status not in ('open', 'acknowledged'):
            return Response({'error': '该告警无法解决'}, status=status.HTTP_400_BAD_REQUEST)
        alert.status = 'resolved'
        alert.resolved_by = request.user
        alert.resolution = request.data.get('resolution', '')
        alert.save(update_fields=['status', 'resolved_by', 'resolution', 'updated_at'])
        return Response(RiskAlertSerializer(alert).data)


# ─── APIViews ───────────────────────────────────────────────────

class CostTrendView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = PredictionService.analyze_cost_trend()
        return Response({'trends': data})


class DeliveryRiskView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = PredictionService.analyze_delivery_risk()
        return Response({'risks': data, 'total': len(data)})


class CapacityLoadView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = PredictionService.analyze_capacity_load()
        return Response({'capacity_load': data})
