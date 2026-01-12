"""
AI销售预测模块
AI Sales Prediction
智能销售预测、客户流失预警
"""
from datetime import date, timedelta
from decimal import Decimal
from django.db import models
from django.db.models import Count, Sum, Avg, F, Q
from django.db.models.functions import TruncMonth, TruncWeek
from django.conf import settings
from django.utils import timezone
from rest_framework import viewsets, serializers, status
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.core.models import BaseModel
from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin


class SalesPrediction(BaseModel):
    """销售预测结果"""
    PREDICTION_TYPE_CHOICES = [
        ('MONTHLY', '月度预测'),
        ('QUARTERLY', '季度预测'),
        ('YEARLY', '年度预测'),
    ]
    
    prediction_type = models.CharField(
        max_length=20,
        choices=PREDICTION_TYPE_CHOICES,
        default='MONTHLY',
        verbose_name='预测类型'
    )
    
    # 预测期间
    period_start = models.DateField(verbose_name='期间开始')
    period_end = models.DateField(verbose_name='期间结束')
    
    # 预测值
    predicted_amount = models.DecimalField(
        max_digits=18, decimal_places=2,
        verbose_name='预测金额'
    )
    predicted_count = models.IntegerField(default=0, verbose_name='预测订单数')
    
    # 实际值（后续更新）
    actual_amount = models.DecimalField(
        max_digits=18, decimal_places=2,
        null=True, blank=True,
        verbose_name='实际金额'
    )
    actual_count = models.IntegerField(null=True, blank=True, verbose_name='实际订单数')
    
    # 置信度
    confidence = models.FloatField(default=0.8, verbose_name='置信度')
    
    # 预测区间
    lower_bound = models.DecimalField(
        max_digits=18, decimal_places=2,
        null=True, blank=True,
        verbose_name='下限'
    )
    upper_bound = models.DecimalField(
        max_digits=18, decimal_places=2,
        null=True, blank=True,
        verbose_name='上限'
    )
    
    # 影响因素
    factors = models.JSONField(default=dict, blank=True, verbose_name='影响因素')
    
    # 模型信息
    model_version = models.CharField(max_length=50, default='v1.0', verbose_name='模型版本')
    algorithm = models.CharField(max_length=50, default='linear_regression', verbose_name='算法')
    
    notes = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'crm_sales_prediction'
        verbose_name = '销售预测'
        verbose_name_plural = verbose_name
        ordering = ['-period_start']
    
    def __str__(self):
        return f"{self.get_prediction_type_display()} - {self.period_start}"
    
    @property
    def accuracy(self):
        """预测准确率"""
        if self.actual_amount and self.predicted_amount:
            error = abs(float(self.actual_amount - self.predicted_amount))
            return round((1 - error / float(self.predicted_amount)) * 100, 2)
        return None


class CustomerChurnRisk(BaseModel):
    """客户流失风险"""
    RISK_LEVEL_CHOICES = [
        ('LOW', '低风险'),
        ('MEDIUM', '中风险'),
        ('HIGH', '高风险'),
        ('CRITICAL', '极高风险'),
    ]
    
    customer = models.ForeignKey(
        'masterdata.Customer',
        on_delete=models.CASCADE,
        related_name='churn_risks',
        verbose_name='客户'
    )
    
    risk_level = models.CharField(
        max_length=20,
        choices=RISK_LEVEL_CHOICES,
        default='LOW',
        verbose_name='风险等级'
    )
    risk_score = models.FloatField(default=0, verbose_name='风险分数')
    
    # 风险指标
    days_since_last_order = models.IntegerField(default=0, verbose_name='距上次订单天数')
    order_frequency_trend = models.FloatField(default=0, verbose_name='订单频率趋势')
    amount_trend = models.FloatField(default=0, verbose_name='金额趋势')
    interaction_score = models.FloatField(default=0, verbose_name='互动评分')
    
    # 风险因素
    risk_factors = models.JSONField(default=list, blank=True, verbose_name='风险因素')
    
    # 建议措施
    recommendations = models.JSONField(default=list, blank=True, verbose_name='建议措施')
    
    # 计算时间
    calculated_at = models.DateTimeField(auto_now=True, verbose_name='计算时间')
    
    # 处理状态
    is_handled = models.BooleanField(default=False, verbose_name='是否已处理')
    handled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='handled_churn_risks',
        verbose_name='处理人'
    )
    handled_at = models.DateTimeField(null=True, blank=True, verbose_name='处理时间')
    handling_notes = models.TextField(blank=True, verbose_name='处理备注')
    
    class Meta:
        db_table = 'crm_customer_churn_risk'
        verbose_name = '客户流失风险'
        verbose_name_plural = verbose_name
        ordering = ['-risk_score', '-calculated_at']
    
    def __str__(self):
        return f"{self.customer.name} - {self.get_risk_level_display()}"


# =====================
# Serializers
# =====================

class SalesPredictionSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_prediction_type_display', read_only=True)
    accuracy = serializers.FloatField(read_only=True)
    
    class Meta:
        model = SalesPrediction
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class CustomerChurnRiskSerializer(serializers.ModelSerializer):
    risk_level_display = serializers.CharField(source='get_risk_level_display', read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    customer_type = serializers.CharField(source='customer.customer_type', read_only=True)
    handled_by_name = serializers.CharField(source='handled_by.get_full_name', read_only=True)
    
    class Meta:
        model = CustomerChurnRisk
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'calculated_at']


# =====================
# ViewSets
# =====================

class SalesPredictionViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """销售预测管理"""
    queryset = SalesPrediction.objects.filter(is_deleted=False)
    serializer_class = SalesPredictionSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['prediction_type']
    ordering_fields = ['period_start', 'created_at']


class CustomerChurnRiskViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """客户流失风险管理"""
    queryset = CustomerChurnRisk.objects.filter(is_deleted=False)
    serializer_class = CustomerChurnRiskSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['customer', 'risk_level', 'is_handled']
    ordering_fields = ['risk_score', 'calculated_at']
    
    @action(detail=True, methods=['post'])
    def handle(self, request, pk=None):
        """处理风险"""
        risk = self.get_object()
        
        risk.is_handled = True
        risk.handled_by = request.user
        risk.handled_at = timezone.now()
        risk.handling_notes = request.data.get('notes', '')
        risk.save()
        
        return Response(self.get_serializer(risk).data)
    
    @action(detail=False, methods=['get'])
    def high_risk(self, request):
        """获取高风险客户"""
        risks = self.get_queryset().filter(
            risk_level__in=['HIGH', 'CRITICAL'],
            is_handled=False
        ).select_related('customer')
        
        return Response(self.get_serializer(risks, many=True).data)


# =====================
# Analysis Views
# =====================

class SalesPredictionView(APIView):
    """销售预测API"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """获取销售预测"""
        from apps.sales.models import SalesOrder
        
        months = int(request.query_params.get('months', 3))
        
        # 获取历史数据（过去12个月）
        end_date = date.today()
        start_date = end_date - timedelta(days=365)
        
        historical = SalesOrder.objects.filter(
            order_date__gte=start_date,
            order_date__lte=end_date,
            status__in=['CONFIRMED', 'COMPLETED'],
            is_deleted=False
        ).annotate(
            month=TruncMonth('order_date')
        ).values('month').annotate(
            amount=Sum('total_amount'),
            count=Count('id')
        ).order_by('month')
        
        historical_data = list(historical)
        
        if len(historical_data) < 3:
            return Response({
                'error': '历史数据不足，无法进行预测',
                'min_required': 3,
                'current': len(historical_data)
            }, status=400)
        
        # 简单移动平均预测
        amounts = [float(h['amount'] or 0) for h in historical_data]
        counts = [h['count'] for h in historical_data]
        
        # 计算趋势（简单线性回归）
        n = len(amounts)
        x_mean = (n - 1) / 2
        y_mean = sum(amounts) / n
        
        numerator = sum((i - x_mean) * (amounts[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        
        slope = numerator / denominator if denominator != 0 else 0
        intercept = y_mean - slope * x_mean
        
        # 生成预测
        predictions = []
        current_month = date.today().replace(day=1)
        
        for i in range(months):
            month = current_month + timedelta(days=32 * i)
            month = month.replace(day=1)
            
            # 预测值
            predicted_amount = intercept + slope * (n + i)
            predicted_amount = max(0, predicted_amount)  # 不能为负
            
            # 置信区间（简化：±20%）
            lower = predicted_amount * 0.8
            upper = predicted_amount * 1.2
            
            # 预测订单数（使用平均值）
            avg_count = sum(counts) / len(counts)
            
            predictions.append({
                'period': month.strftime('%Y-%m'),
                'predicted_amount': round(predicted_amount, 2),
                'predicted_count': round(avg_count),
                'lower_bound': round(lower, 2),
                'upper_bound': round(upper, 2),
                'confidence': 0.8
            })
            
            # 保存预测结果
            SalesPrediction.objects.update_or_create(
                period_start=month,
                period_end=month.replace(day=28),
                prediction_type='MONTHLY',
                defaults={
                    'predicted_amount': Decimal(str(predicted_amount)),
                    'predicted_count': round(avg_count),
                    'lower_bound': Decimal(str(lower)),
                    'upper_bound': Decimal(str(upper)),
                    'confidence': 0.8,
                    'algorithm': 'linear_regression',
                    'created_by': request.user
                }
            )
        
        return Response({
            'historical': [
                {
                    'period': h['month'].strftime('%Y-%m'),
                    'amount': float(h['amount'] or 0),
                    'count': h['count']
                }
                for h in historical_data
            ],
            'predictions': predictions,
            'model': {
                'algorithm': 'linear_regression',
                'version': 'v1.0',
                'trend': 'up' if slope > 0 else 'down',
                'monthly_change': round(slope, 2)
            }
        })


class ChurnPredictionView(APIView):
    """客户流失预测API"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """计算客户流失风险"""
        from apps.masterdata.models import Customer
        from apps.sales.models import SalesOrder
        
        # 风险阈值配置
        INACTIVE_DAYS_THRESHOLD = 90  # 超过90天未下单视为不活跃
        FREQUENCY_DECLINE_THRESHOLD = -0.3  # 频率下降超过30%
        AMOUNT_DECLINE_THRESHOLD = -0.3  # 金额下降超过30%
        
        today = date.today()
        
        # 获取所有活跃客户
        customers = Customer.objects.filter(
            is_deleted=False,
            status='ACTIVE'  # 使用status字段而非is_active
        )
        
        risks = []
        
        for customer in customers:
            # 获取订单历史
            orders = SalesOrder.objects.filter(
                customer=customer,
                status__in=['CONFIRMED', 'COMPLETED'],
                is_deleted=False
            ).order_by('-order_date')
            
            if not orders.exists():
                continue
            
            last_order = orders.first()
            days_since_last = (today - last_order.order_date).days
            
            # 计算订单频率趋势
            recent_orders = orders.filter(order_date__gte=today - timedelta(days=180))
            old_orders = orders.filter(
                order_date__lt=today - timedelta(days=180),
                order_date__gte=today - timedelta(days=365)
            )
            
            recent_count = recent_orders.count()
            old_count = old_orders.count()
            
            frequency_trend = 0
            if old_count > 0:
                frequency_trend = (recent_count - old_count) / old_count
            
            # 计算金额趋势
            recent_amount = recent_orders.aggregate(total=Sum('total_amount'))['total'] or 0
            old_amount = old_orders.aggregate(total=Sum('total_amount'))['total'] or 0
            
            amount_trend = 0
            if old_amount > 0:
                amount_trend = float(recent_amount - old_amount) / float(old_amount)
            
            # 计算风险分数
            risk_score = 0
            risk_factors = []
            recommendations = []
            
            # 不活跃天数评分
            if days_since_last > INACTIVE_DAYS_THRESHOLD:
                inactive_score = min((days_since_last - INACTIVE_DAYS_THRESHOLD) / 90, 1) * 40
                risk_score += inactive_score
                risk_factors.append(f"超过{days_since_last}天未下单")
                recommendations.append("安排销售拜访，了解客户近况")
            
            # 频率下降评分
            if frequency_trend < FREQUENCY_DECLINE_THRESHOLD:
                freq_score = min(abs(frequency_trend) / 0.5, 1) * 30
                risk_score += freq_score
                risk_factors.append(f"订单频率下降{abs(frequency_trend)*100:.0f}%")
                recommendations.append("分析订单下降原因，提供促销活动")
            
            # 金额下降评分
            if amount_trend < AMOUNT_DECLINE_THRESHOLD:
                amount_score = min(abs(amount_trend) / 0.5, 1) * 30
                risk_score += amount_score
                risk_factors.append(f"订单金额下降{abs(amount_trend)*100:.0f}%")
                recommendations.append("了解客户预算变化，调整报价策略")
            
            # 确定风险等级
            if risk_score >= 70:
                risk_level = 'CRITICAL'
            elif risk_score >= 50:
                risk_level = 'HIGH'
            elif risk_score >= 30:
                risk_level = 'MEDIUM'
            else:
                risk_level = 'LOW'
            
            # 只记录中高风险
            if risk_score >= 30:
                risk_obj, _ = CustomerChurnRisk.objects.update_or_create(
                    customer=customer,
                    defaults={
                        'risk_level': risk_level,
                        'risk_score': risk_score,
                        'days_since_last_order': days_since_last,
                        'order_frequency_trend': frequency_trend,
                        'amount_trend': amount_trend,
                        'risk_factors': risk_factors,
                        'recommendations': recommendations,
                        'created_by': request.user
                    }
                )
                
                risks.append({
                    'customer_id': customer.id,
                    'customer_name': customer.name,
                    'risk_level': risk_level,
                    'risk_score': round(risk_score, 1),
                    'days_since_last_order': days_since_last,
                    'risk_factors': risk_factors,
                    'recommendations': recommendations
                })
        
        # 按风险分数排序
        risks.sort(key=lambda x: x['risk_score'], reverse=True)
        
        # 统计
        level_counts = {
            'CRITICAL': len([r for r in risks if r['risk_level'] == 'CRITICAL']),
            'HIGH': len([r for r in risks if r['risk_level'] == 'HIGH']),
            'MEDIUM': len([r for r in risks if r['risk_level'] == 'MEDIUM']),
        }
        
        return Response({
            'total_analyzed': customers.count(),
            'at_risk': len(risks),
            'level_counts': level_counts,
            'risks': risks[:50]  # 返回前50个
        })


class AIInsightsView(APIView):
    """AI洞察API"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """获取AI洞察"""
        from apps.sales.models import SalesOrder
        from apps.masterdata.models import Customer
        
        today = date.today()
        
        # 销售趋势洞察
        current_month = SalesOrder.objects.filter(
            order_date__year=today.year,
            order_date__month=today.month,
            status__in=['CONFIRMED', 'COMPLETED'],
            is_deleted=False
        ).aggregate(
            amount=Sum('total_amount'),
            count=Count('id')
        )
        
        last_month = SalesOrder.objects.filter(
            order_date__year=today.year if today.month > 1 else today.year - 1,
            order_date__month=today.month - 1 if today.month > 1 else 12,
            status__in=['CONFIRMED', 'COMPLETED'],
            is_deleted=False
        ).aggregate(
            amount=Sum('total_amount'),
            count=Count('id')
        )
        
        # 计算变化
        current_amount = float(current_month['amount'] or 0)
        last_amount = float(last_month['amount'] or 0)
        
        amount_change = 0
        if last_amount > 0:
            amount_change = (current_amount - last_amount) / last_amount * 100
        
        insights = []
        
        # 销售趋势洞察
        if amount_change > 10:
            insights.append({
                'type': 'positive',
                'title': '销售增长',
                'message': f'本月销售额较上月增长{amount_change:.1f}%，继续保持！'
            })
        elif amount_change < -10:
            insights.append({
                'type': 'warning',
                'title': '销售下滑',
                'message': f'本月销售额较上月下降{abs(amount_change):.1f}%，需要关注。'
            })
        
        # 流失风险洞察
        high_risk_count = CustomerChurnRisk.objects.filter(
            risk_level__in=['HIGH', 'CRITICAL'],
            is_handled=False
        ).count()
        
        if high_risk_count > 0:
            insights.append({
                'type': 'warning',
                'title': '客户流失预警',
                'message': f'发现{high_risk_count}个高风险客户，建议尽快跟进。',
                'action': '/crm/churn-risks'
            })
        
        # 预测准确度洞察
        recent_predictions = SalesPrediction.objects.filter(
            actual_amount__isnull=False,
            period_end__lt=today
        ).order_by('-period_start')[:3]
        
        if recent_predictions:
            accuracies = [p.accuracy for p in recent_predictions if p.accuracy]
            if accuracies:
                avg_accuracy = sum(accuracies) / len(accuracies)
                insights.append({
                    'type': 'info',
                    'title': '预测准确度',
                    'message': f'近期预测平均准确率为{avg_accuracy:.1f}%'
                })
        
        return Response({
            'insights': insights,
            'summary': {
                'current_month_amount': current_amount,
                'amount_change': round(amount_change, 1),
                'high_risk_customers': high_risk_count
            }
        })
