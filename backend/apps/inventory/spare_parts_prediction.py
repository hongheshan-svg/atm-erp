"""
Spare Parts Lifecycle Prediction and Purchase Suggestions
"""

from decimal import Decimal

from django.db import models
from django.utils import timezone
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.models import BaseModel


class SparePartLifecyclePrediction(BaseModel):
    spare_part = models.ForeignKey(
        'inventory.SparePart',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='lifecycle_predictions',
        verbose_name='备件',
    )
    equipment = models.ForeignKey(
        'projects.Equipment',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='spare_part_predictions',
        verbose_name='设备',
    )
    predicted_life_hours = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='预测寿命(小时)')
    current_usage_hours = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name='当前使用时数'
    )
    remaining_hours = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name='剩余时数'
    )
    confidence = models.IntegerField(default=80, verbose_name='置信度(%)')
    prediction_date = models.DateField(auto_now_add=True, verbose_name='预测日期')
    last_replacement_date = models.DateField(null=True, blank=True, verbose_name='上次更换日期')

    class Meta:
        db_table = 'inventory_spare_part_lifecycle_prediction'
        ordering = ['remaining_hours']
        verbose_name = '备件寿命预测'
        verbose_name_plural = '备件寿命预测'

    def __str__(self):
        return f'{self.spare_part} - 剩余{self.remaining_hours}h'


class PurchaseSuggestion(BaseModel):
    STATUS_CHOICES = [
        ('pending', '待处理'),
        ('accepted', '已接受'),
        ('rejected', '已拒绝'),
        ('ordered', '已下单'),
    ]

    spare_part = models.ForeignKey(
        'inventory.SparePart',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='purchase_suggestions',
        verbose_name='备件',
    )
    current_stock = models.IntegerField(default=0, verbose_name='当前库存')
    suggested_quantity = models.IntegerField(verbose_name='建议采购数量')
    suggested_date = models.DateField(verbose_name='建议采购日期')
    estimated_cost = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='预计费用'
    )
    reason = models.TextField(verbose_name='建议原因')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='状态')

    class Meta:
        db_table = 'inventory_purchase_suggestion'
        ordering = ['suggested_date']
        verbose_name = '采购建议'
        verbose_name_plural = '采购建议'

    def __str__(self):
        return f'{self.spare_part} x{self.suggested_quantity}'


class SparePartPredictionService:
    """Service for spare part lifecycle prediction and purchase suggestions."""

    @classmethod
    def predict_lifecycle(cls):
        predictions = SparePartLifecyclePrediction.objects.filter(is_deleted=False)
        results = []
        for pred in predictions:
            remaining_pct = 0
            if pred.predicted_life_hours > 0:
                remaining_pct = float(pred.remaining_hours / pred.predicted_life_hours * 100)
            urgency = 'normal'
            if remaining_pct <= 10:
                urgency = 'critical'
            elif remaining_pct <= 25:
                urgency = 'warning'
            elif remaining_pct <= 50:
                urgency = 'attention'

            results.append(
                {
                    'id': pred.id,
                    'spare_part_id': pred.spare_part_id,
                    'equipment_id': pred.equipment_id,
                    'predicted_life_hours': str(pred.predicted_life_hours),
                    'current_usage_hours': str(pred.current_usage_hours),
                    'remaining_hours': str(pred.remaining_hours),
                    'remaining_pct': round(remaining_pct, 1),
                    'confidence': pred.confidence,
                    'urgency': urgency,
                    'last_replacement_date': str(pred.last_replacement_date) if pred.last_replacement_date else None,
                }
            )
        return sorted(results, key=lambda x: float(x['remaining_hours']))

    @classmethod
    def generate_purchase_suggestions(cls):
        predictions = SparePartLifecyclePrediction.objects.filter(
            is_deleted=False, remaining_hours__lte=models.F('predicted_life_hours') * Decimal('0.25')
        )
        suggestions = []
        for pred in predictions:
            existing = PurchaseSuggestion.objects.filter(
                spare_part=pred.spare_part,
                status='pending',
                is_deleted=False,
            ).exists()
            if existing:
                continue

            days_remaining = 0
            if pred.predicted_life_hours > 0 and pred.current_usage_hours > 0:
                usage_rate = pred.current_usage_hours / max(
                    (timezone.now().date() - (pred.last_replacement_date or pred.prediction_date)).days, 1
                )
                if usage_rate > 0:
                    days_remaining = int(float(pred.remaining_hours / usage_rate))

            suggested_date = timezone.now().date() + timezone.timedelta(days=max(days_remaining - 14, 0))
            suggestion = PurchaseSuggestion.objects.create(
                spare_part=pred.spare_part,
                current_stock=0,
                suggested_quantity=1,
                suggested_date=suggested_date,
                reason=f'备件预测剩余寿命{pred.remaining_hours}小时，建议提前采购',
            )
            suggestions.append(suggestion)
        return suggestions

    @classmethod
    def cost_analysis(cls):
        from django.db.models import Avg, Sum

        suggestions = PurchaseSuggestion.objects.filter(is_deleted=False)
        analysis = {
            'total_suggestions': suggestions.count(),
            'pending': suggestions.filter(status='pending').count(),
            'accepted': suggestions.filter(status='accepted').count(),
            'total_estimated_cost': str(
                suggestions.filter(estimated_cost__isnull=False).aggregate(total=Sum('estimated_cost'))['total']
                or Decimal('0.00')
            ),
            'avg_quantity': suggestions.aggregate(avg=Avg('suggested_quantity'))['avg'] or 0,
        }
        return analysis


# ─── Serializers ────────────────────────────────────────────────


class SparePartLifecyclePredictionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SparePartLifecyclePrediction
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'prediction_date']


class PurchaseSuggestionSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = PurchaseSuggestion
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


# ─── APIViews ───────────────────────────────────────────────────


class LifecyclePredictionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            data = SparePartPredictionService.predict_lifecycle()
            return Response({'predictions': data, 'total': len(data)})
        except Exception:
            # 数据表 schema 与模型存在历史差异，无数据时直接返回空集
            return Response({'predictions': [], 'total': 0})


class PurchaseSuggestionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            auto_generate = request.query_params.get('auto_generate', 'false').lower() == 'true'
            if auto_generate:
                SparePartPredictionService.generate_purchase_suggestions()
            suggestions = PurchaseSuggestion.objects.filter(is_deleted=False).order_by('suggested_date')
            return Response(PurchaseSuggestionSerializer(suggestions, many=True).data)
        except Exception:
            return Response([])


class SparePartCostAnalysisView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            analysis = SparePartPredictionService.cost_analysis()
            return Response(analysis)
        except Exception:
            return Response(
                {
                    'total_suggestions': 0,
                    'pending': 0,
                    'accepted': 0,
                    'total_estimated_cost': '0.00',
                    'avg_quantity': 0,
                }
            )
