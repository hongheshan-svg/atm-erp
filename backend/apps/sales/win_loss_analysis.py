"""
赢单/丢单分析模块
Win/Loss Analysis for Opportunities
详细分析商机赢单和丢单的原因、趋势等
"""
from datetime import date, timedelta
from decimal import Decimal
from django.db import models
from django.db.models import Sum, Count, Avg, F, Q
from django.db.models.functions import TruncMonth
from django.utils import timezone
from rest_framework import viewsets, serializers, status
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.core.models import BaseModel
from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin


class WinLossReason(BaseModel):
    """赢单/丢单原因"""
    REASON_TYPE_CHOICES = [
        ('WIN', '赢单'),
        ('LOSS', '丢单'),
    ]
    
    name = models.CharField(max_length=100, verbose_name='原因名称')
    reason_type = models.CharField(max_length=10, choices=REASON_TYPE_CHOICES, verbose_name='原因类型')
    description = models.TextField(blank=True, verbose_name='描述')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    
    class Meta:
        db_table = 'crm_win_loss_reason'
        verbose_name = '赢单/丢单原因'
        verbose_name_plural = verbose_name
        ordering = ['reason_type', 'sort_order']
    
    def __str__(self):
        return f"[{self.get_reason_type_display()}] {self.name}"


class OpportunityCloseRecord(BaseModel):
    """商机关闭记录"""
    opportunity = models.ForeignKey(
        'sales.Opportunity',
        on_delete=models.CASCADE,
        related_name='close_records',
        verbose_name='商机'
    )
    close_type = models.CharField(
        max_length=10,
        choices=[('WIN', '赢单'), ('LOSS', '丢单')],
        verbose_name='关闭类型'
    )
    primary_reason = models.ForeignKey(
        WinLossReason,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='close_records',
        verbose_name='主要原因'
    )
    secondary_reasons = models.ManyToManyField(
        WinLossReason,
        blank=True,
        related_name='secondary_close_records',
        verbose_name='次要原因'
    )
    
    # 竞争信息
    competitor = models.ForeignKey(
        'masterdata.Supplier',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='won_opportunities',
        verbose_name='赢得的竞争对手'
    )
    competitor_name = models.CharField(max_length=200, blank=True, verbose_name='竞争对手名称')
    competitor_amount = models.DecimalField(
        max_digits=18, decimal_places=2, 
        null=True, blank=True,
        verbose_name='竞争对手报价'
    )
    
    # 详细分析
    our_amount = models.DecimalField(
        max_digits=18, decimal_places=2, 
        null=True, blank=True,
        verbose_name='我方报价'
    )
    price_difference = models.DecimalField(
        max_digits=18, decimal_places=2, 
        null=True, blank=True,
        verbose_name='价格差异'
    )
    
    # 销售周期
    sales_cycle_days = models.IntegerField(null=True, blank=True, verbose_name='销售周期(天)')
    
    # 分析笔记
    analysis_notes = models.TextField(blank=True, verbose_name='分析备注')
    lessons_learned = models.TextField(blank=True, verbose_name='经验教训')
    
    # 客户反馈
    customer_feedback = models.TextField(blank=True, verbose_name='客户反馈')
    
    close_date = models.DateField(default=date.today, verbose_name='关闭日期')
    
    class Meta:
        db_table = 'crm_opportunity_close_record'
        verbose_name = '商机关闭记录'
        verbose_name_plural = verbose_name
        ordering = ['-close_date']
    
    def __str__(self):
        return f"{self.opportunity} - {self.get_close_type_display()}"
    
    def save(self, *args, **kwargs):
        # 计算价格差异
        if self.our_amount and self.competitor_amount:
            self.price_difference = self.our_amount - self.competitor_amount
        
        # 计算销售周期
        if self.opportunity and self.opportunity.created_at:
            delta = self.close_date - self.opportunity.created_at.date()
            self.sales_cycle_days = delta.days
        
        super().save(*args, **kwargs)


# =====================
# Serializers
# =====================

class WinLossReasonSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_reason_type_display', read_only=True)
    usage_count = serializers.SerializerMethodField()
    
    class Meta:
        model = WinLossReason
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']
    
    def get_usage_count(self, obj):
        return obj.close_records.count()


class OpportunityCloseRecordSerializer(serializers.ModelSerializer):
    close_type_display = serializers.CharField(source='get_close_type_display', read_only=True)
    opportunity_name = serializers.CharField(source='opportunity.name', read_only=True)
    primary_reason_name = serializers.CharField(source='primary_reason.name', read_only=True)
    secondary_reason_names = serializers.SerializerMethodField()
    customer_name = serializers.CharField(source='opportunity.customer.name', read_only=True)
    
    class Meta:
        model = OpportunityCloseRecord
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'price_difference', 'sales_cycle_days']
    
    def get_secondary_reason_names(self, obj):
        return [r.name for r in obj.secondary_reasons.all()]


class OpportunityCloseRecordCreateSerializer(serializers.ModelSerializer):
    secondary_reason_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        default=list
    )
    
    class Meta:
        model = OpportunityCloseRecord
        fields = [
            'opportunity', 'close_type', 'primary_reason', 'secondary_reason_ids',
            'competitor', 'competitor_name', 'competitor_amount', 'our_amount',
            'analysis_notes', 'lessons_learned', 'customer_feedback', 'close_date'
        ]
    
    def create(self, validated_data):
        secondary_ids = validated_data.pop('secondary_reason_ids', [])
        record = OpportunityCloseRecord.objects.create(**validated_data)
        
        if secondary_ids:
            reasons = WinLossReason.objects.filter(id__in=secondary_ids)
            record.secondary_reasons.set(reasons)
        
        return record


# =====================
# ViewSets
# =====================

class WinLossReasonViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """赢单/丢单原因管理"""
    queryset = WinLossReason.objects.filter(is_deleted=False)
    serializer_class = WinLossReasonSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['reason_type', 'is_active']
    search_fields = ['name', 'description']


class OpportunityCloseRecordViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """商机关闭记录管理"""
    queryset = OpportunityCloseRecord.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filterset_fields = ['opportunity', 'close_type', 'primary_reason']
    search_fields = ['opportunity__name', 'competitor_name']
    
    def get_serializer_class(self):
        if self.action == 'create':
            return OpportunityCloseRecordCreateSerializer
        return OpportunityCloseRecordSerializer


# =====================
# Analysis Views
# =====================

class WinLossAnalysisView(APIView):
    """赢单/丢单分析API"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """获取赢单/丢单分析数据"""
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        if not end_date:
            end_date = date.today()
        else:
            end_date = date.fromisoformat(end_date)
        
        if not start_date:
            start_date = end_date - timedelta(days=365)
        else:
            start_date = date.fromisoformat(start_date)
        
        records = OpportunityCloseRecord.objects.filter(
            close_date__gte=start_date,
            close_date__lte=end_date,
            is_deleted=False
        )
        
        # 赢单/丢单统计
        win_records = records.filter(close_type='WIN')
        loss_records = records.filter(close_type='LOSS')
        
        win_count = win_records.count()
        loss_count = loss_records.count()
        total_count = win_count + loss_count
        win_rate = round(win_count / total_count * 100, 1) if total_count > 0 else 0
        
        win_amount = win_records.aggregate(total=Sum('our_amount'))['total'] or 0
        loss_amount = loss_records.aggregate(total=Sum('our_amount'))['total'] or 0
        
        # 按原因统计
        win_by_reason = win_records.filter(
            primary_reason__isnull=False
        ).values(
            'primary_reason__id', 'primary_reason__name'
        ).annotate(
            count=Count('id'),
            amount=Sum('our_amount')
        ).order_by('-count')
        
        loss_by_reason = loss_records.filter(
            primary_reason__isnull=False
        ).values(
            'primary_reason__id', 'primary_reason__name'
        ).annotate(
            count=Count('id'),
            amount=Sum('our_amount')
        ).order_by('-count')
        
        # 按月趋势
        monthly_trend = records.annotate(
            month=TruncMonth('close_date')
        ).values('month', 'close_type').annotate(
            count=Count('id'),
            amount=Sum('our_amount')
        ).order_by('month')
        
        # 格式化趋势数据
        trend_data = {}
        for item in monthly_trend:
            month_str = item['month'].strftime('%Y-%m') if item['month'] else 'Unknown'
            if month_str not in trend_data:
                trend_data[month_str] = {'win': 0, 'loss': 0, 'win_amount': 0, 'loss_amount': 0}
            
            if item['close_type'] == 'WIN':
                trend_data[month_str]['win'] = item['count']
                trend_data[month_str]['win_amount'] = float(item['amount'] or 0)
            else:
                trend_data[month_str]['loss'] = item['count']
                trend_data[month_str]['loss_amount'] = float(item['amount'] or 0)
        
        trend_list = [
            {
                'month': month,
                'win': data['win'],
                'loss': data['loss'],
                'win_amount': data['win_amount'],
                'loss_amount': data['loss_amount'],
                'win_rate': round(data['win'] / (data['win'] + data['loss']) * 100, 1) 
                           if (data['win'] + data['loss']) > 0 else 0
            }
            for month, data in sorted(trend_data.items())
        ]
        
        # 销售周期分析
        avg_win_cycle = win_records.aggregate(avg=Avg('sales_cycle_days'))['avg'] or 0
        avg_loss_cycle = loss_records.aggregate(avg=Avg('sales_cycle_days'))['avg'] or 0
        
        # 竞争对手分析
        competitor_stats = loss_records.exclude(
            competitor_name=''
        ).values('competitor_name').annotate(
            count=Count('id'),
            total_amount=Sum('our_amount')
        ).order_by('-count')[:10]
        
        return Response({
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'summary': {
                'total': total_count,
                'win_count': win_count,
                'loss_count': loss_count,
                'win_rate': win_rate,
                'win_amount': float(win_amount),
                'loss_amount': float(loss_amount)
            },
            'win_by_reason': [
                {
                    'reason_id': item['primary_reason__id'],
                    'reason_name': item['primary_reason__name'],
                    'count': item['count'],
                    'amount': float(item['amount'] or 0)
                }
                for item in win_by_reason
            ],
            'loss_by_reason': [
                {
                    'reason_id': item['primary_reason__id'],
                    'reason_name': item['primary_reason__name'],
                    'count': item['count'],
                    'amount': float(item['amount'] or 0)
                }
                for item in loss_by_reason
            ],
            'monthly_trend': trend_list,
            'sales_cycle': {
                'avg_win_days': round(float(avg_win_cycle), 1),
                'avg_loss_days': round(float(avg_loss_cycle), 1)
            },
            'competitor_analysis': list(competitor_stats)
        })


class WinLossComparisonView(APIView):
    """赢单/丢单对比分析"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """对比分析赢单和丢单的特征"""
        from apps.sales.crm_models import Opportunity
        
        # 获取时间范围
        months = int(request.query_params.get('months', 12))
        end_date = date.today()
        start_date = end_date - timedelta(days=months * 30)
        
        # 获取关闭的商机
        closed_opps = Opportunity.objects.filter(
            stage__in=['CLOSED_WON', 'CLOSED_LOST'],
            updated_at__date__gte=start_date,
            is_deleted=False
        )
        
        won = closed_opps.filter(stage='CLOSED_WON')
        lost = closed_opps.filter(stage='CLOSED_LOST')
        
        # 平均金额对比
        avg_won_amount = won.aggregate(avg=Avg('amount'))['avg'] or 0
        avg_lost_amount = lost.aggregate(avg=Avg('amount'))['avg'] or 0
        
        # 按客户规模分析
        def analyze_by_customer_type(queryset):
            return queryset.values(
                'customer__customer_type'
            ).annotate(count=Count('id')).order_by('-count')
        
        won_by_type = list(analyze_by_customer_type(won))
        lost_by_type = list(analyze_by_customer_type(lost))
        
        # 按产品类型分析 (如果有)
        # 按销售人员分析
        won_by_sales = won.values(
            'salesperson__username'
        ).annotate(
            count=Count('id'),
            amount=Sum('amount')
        ).order_by('-count')[:10]
        
        lost_by_sales = lost.values(
            'salesperson__username'
        ).annotate(
            count=Count('id'),
            amount=Sum('amount')
        ).order_by('-count')[:10]
        
        return Response({
            'period': {
                'months': months,
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'amount_comparison': {
                'avg_won': float(avg_won_amount),
                'avg_lost': float(avg_lost_amount),
                'difference': float(avg_won_amount - avg_lost_amount)
            },
            'by_customer_type': {
                'won': won_by_type,
                'lost': lost_by_type
            },
            'by_salesperson': {
                'won': list(won_by_sales),
                'lost': list(lost_by_sales)
            }
        })
