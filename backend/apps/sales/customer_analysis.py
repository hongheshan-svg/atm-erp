"""
客户价值分析
Customer Value Analysis
客户RFM分析、价值分层、流失预警等
"""
from datetime import date, timedelta
from decimal import Decimal
from django.db import models
from django.db.models import Sum, Count, Avg, Max, F, Q
from django.db.models.functions import TruncMonth
from django.utils import timezone
from rest_framework import viewsets, serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.core.models import BaseModel
from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin


class CustomerRFMAnalysis(BaseModel):
    """
    客户RFM分析记录
    R - Recency (最近一次购买)
    F - Frequency (购买频率)
    M - Monetary (购买金额)
    """
    customer = models.ForeignKey(
        'masterdata.Customer',
        on_delete=models.CASCADE,
        related_name='rfm_records',
        verbose_name='客户'
    )
    analysis_date = models.DateField(verbose_name='分析日期')
    
    # RFM原始值
    last_order_date = models.DateField(null=True, blank=True, verbose_name='最近订单日期')
    recency_days = models.IntegerField(default=0, verbose_name='距今天数')
    frequency = models.IntegerField(default=0, verbose_name='订单次数')
    monetary = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='累计金额')
    
    # RFM评分 (1-5分)
    r_score = models.IntegerField(default=1, verbose_name='R评分')
    f_score = models.IntegerField(default=1, verbose_name='F评分')
    m_score = models.IntegerField(default=1, verbose_name='M评分')
    
    # 综合评分
    rfm_score = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='RFM综合分')
    
    # 客户分层
    customer_segment = models.CharField(max_length=50, blank=True, verbose_name='客户分层')
    
    class Meta:
        db_table = 'sales_customer_rfm'
        verbose_name = '客户RFM分析'
        verbose_name_plural = verbose_name
        unique_together = ['customer', 'analysis_date']
        ordering = ['-analysis_date', '-rfm_score']
    
    def __str__(self):
        return f'{self.customer.name} - {self.analysis_date}'


class CustomerSegment(BaseModel):
    """
    客户分层定义
    """
    code = models.CharField(max_length=20, unique=True, verbose_name='分层编码')
    name = models.CharField(max_length=50, verbose_name='分层名称')
    
    # RFM条件
    r_min = models.IntegerField(default=1, verbose_name='R最小值')
    r_max = models.IntegerField(default=5, verbose_name='R最大值')
    f_min = models.IntegerField(default=1, verbose_name='F最小值')
    f_max = models.IntegerField(default=5, verbose_name='F最大值')
    m_min = models.IntegerField(default=1, verbose_name='M最小值')
    m_max = models.IntegerField(default=5, verbose_name='M最大值')
    
    color = models.CharField(max_length=20, default='#409EFF', verbose_name='显示颜色')
    priority = models.IntegerField(default=0, verbose_name='优先级')
    
    # 策略建议
    strategy = models.TextField(blank=True, verbose_name='营销策略')
    description = models.TextField(blank=True, verbose_name='描述')
    
    class Meta:
        db_table = 'sales_customer_segment'
        verbose_name = '客户分层'
        verbose_name_plural = verbose_name
        ordering = ['-priority']
    
    def __str__(self):
        return f'{self.code} - {self.name}'


class RFMAnalysisService:
    """RFM分析服务"""
    
    @staticmethod
    def analyze_all_customers(analysis_date=None):
        """分析所有客户"""
        from apps.masterdata.models import Customer
        from apps.sales.models import SalesOrder
        
        if not analysis_date:
            analysis_date = date.today()
        
        # 获取所有活跃客户
        customers = Customer.objects.filter(is_deleted=False)
        
        # 计算统计数据（用于分位数计算）
        all_rfm_data = []
        
        for customer in customers:
            # 获取订单统计
            order_stats = SalesOrder.objects.filter(
                customer=customer,
                status__in=['CONFIRMED', 'DELIVERED', 'COMPLETED'],
                is_deleted=False
            ).aggregate(
                last_order=Max('order_date'),
                order_count=Count('id'),
                total_amount=Sum('total_amount')
            )
            
            last_order = order_stats['last_order']
            order_count = order_stats['order_count'] or 0
            total_amount = order_stats['total_amount'] or Decimal('0')
            
            recency_days = (analysis_date - last_order).days if last_order else 365
            
            all_rfm_data.append({
                'customer': customer,
                'last_order_date': last_order,
                'recency_days': recency_days,
                'frequency': order_count,
                'monetary': float(total_amount)
            })
        
        if not all_rfm_data:
            return []
        
        # 计算分位数
        recency_values = sorted([d['recency_days'] for d in all_rfm_data])
        frequency_values = sorted([d['frequency'] for d in all_rfm_data])
        monetary_values = sorted([d['monetary'] for d in all_rfm_data])
        
        def get_quintiles(values):
            if len(values) < 5:
                return [0] * 5
            n = len(values)
            return [values[int(n * i / 5)] for i in range(1, 5)]
        
        r_quintiles = get_quintiles(recency_values)
        f_quintiles = get_quintiles(frequency_values)
        m_quintiles = get_quintiles(monetary_values)
        
        def score_value(value, quintiles, reverse=False):
            if not quintiles or all(q == 0 for q in quintiles):
                return 3
            for i, q in enumerate(quintiles):
                if value <= q:
                    return (5 - i) if reverse else (i + 1)
            return 1 if reverse else 5
        
        # 获取分层定义
        segments = CustomerSegment.objects.filter(is_deleted=False).order_by('-priority')
        
        # 创建分析记录
        results = []
        for data in all_rfm_data:
            r_score = score_value(data['recency_days'], r_quintiles, reverse=True)
            f_score = score_value(data['frequency'], f_quintiles, reverse=False)
            m_score = score_value(data['monetary'], m_quintiles, reverse=False)
            
            rfm_score = (r_score + f_score + m_score) / 3
            
            # 确定客户分层
            segment_name = '普通客户'
            for seg in segments:
                if (seg.r_min <= r_score <= seg.r_max and
                    seg.f_min <= f_score <= seg.f_max and
                    seg.m_min <= m_score <= seg.m_max):
                    segment_name = seg.name
                    break
            
            rfm, _ = CustomerRFMAnalysis.objects.update_or_create(
                customer=data['customer'],
                analysis_date=analysis_date,
                defaults={
                    'last_order_date': data['last_order_date'],
                    'recency_days': data['recency_days'],
                    'frequency': data['frequency'],
                    'monetary': Decimal(str(data['monetary'])),
                    'r_score': r_score,
                    'f_score': f_score,
                    'm_score': m_score,
                    'rfm_score': rfm_score,
                    'customer_segment': segment_name
                }
            )
            results.append(rfm)
        
        return results


# =====================
# Serializers
# =====================

class CustomerSegmentSerializer(serializers.ModelSerializer):
    customer_count = serializers.SerializerMethodField()
    
    class Meta:
        model = CustomerSegment
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']
    
    def get_customer_count(self, obj):
        today = date.today()
        return CustomerRFMAnalysis.objects.filter(
            customer_segment=obj.name,
            analysis_date=today,
            is_deleted=False
        ).count()


class CustomerRFMSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    customer_code = serializers.CharField(source='customer.code', read_only=True)
    
    class Meta:
        model = CustomerRFMAnalysis
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class CustomerRFMListSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    customer_code = serializers.CharField(source='customer.code', read_only=True)
    
    class Meta:
        model = CustomerRFMAnalysis
        fields = [
            'id', 'customer', 'customer_name', 'customer_code', 'analysis_date',
            'recency_days', 'frequency', 'monetary',
            'r_score', 'f_score', 'm_score', 'rfm_score', 'customer_segment'
        ]


# =====================
# ViewSets
# =====================

class CustomerSegmentViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """客户分层管理"""
    queryset = CustomerSegment.objects.filter(is_deleted=False)
    serializer_class = CustomerSegmentSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ['code', 'name']
    
    @action(detail=False, methods=['post'])
    def init_segments(self, request):
        """初始化默认分层"""
        segments = [
            ('VIP', '重要价值客户', 4, 5, 4, 5, 4, 5, '#67C23A', 100, 'R高F高M高，保持密切联系，提供VIP服务'),
            ('POTENTIAL', '潜力客户', 4, 5, 1, 3, 4, 5, '#409EFF', 90, 'R高M高但F低，增加接触频率'),
            ('LOYAL', '忠诚客户', 4, 5, 4, 5, 1, 3, '#E6A23C', 80, 'R高F高但M低，提升客单价'),
            ('NEW', '新客户', 4, 5, 1, 2, 1, 3, '#909399', 70, 'R高但F和M低，培养消费习惯'),
            ('DORMANT', '沉睡客户', 1, 3, 1, 3, 4, 5, '#F56C6C', 60, 'M高但R低，需要唤醒'),
            ('LOST', '流失客户', 1, 2, 1, 2, 1, 3, '#909399', 50, 'RFM都低，考虑放弃或特殊挽回'),
        ]
        
        created = 0
        for code, name, r_min, r_max, f_min, f_max, m_min, m_max, color, priority, strategy in segments:
            _, c = CustomerSegment.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'r_min': r_min, 'r_max': r_max,
                    'f_min': f_min, 'f_max': f_max,
                    'm_min': m_min, 'm_max': m_max,
                    'color': color,
                    'priority': priority,
                    'strategy': strategy,
                    'created_by': request.user
                }
            )
            if c:
                created += 1
        
        return Response({'success': True, 'created': created})


class CustomerRFMViewSet(viewsets.ReadOnlyModelViewSet):
    """客户RFM分析"""
    queryset = CustomerRFMAnalysis.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filterset_fields = ['customer', 'customer_segment', 'analysis_date']
    search_fields = ['customer__name', 'customer__code']
    ordering_fields = ['rfm_score', 'monetary', 'frequency', 'recency_days']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return CustomerRFMListSerializer
        return CustomerRFMSerializer
    
    @action(detail=False, methods=['post'])
    def analyze(self, request):
        """执行RFM分析"""
        results = RFMAnalysisService.analyze_all_customers()
        return Response({
            'success': True,
            'analyzed_count': len(results),
            'analysis_date': date.today().isoformat()
        })
    
    @action(detail=False, methods=['get'])
    def latest(self, request):
        """获取最新分析结果"""
        latest_date = self.get_queryset().order_by('-analysis_date').values_list(
            'analysis_date', flat=True
        ).first()
        
        if not latest_date:
            return Response({'error': '暂无分析数据'}, status=404)
        
        records = self.get_queryset().filter(analysis_date=latest_date)
        return Response({
            'analysis_date': latest_date,
            'total': records.count(),
            'data': CustomerRFMListSerializer(records, many=True).data
        })
    
    @action(detail=False, methods=['get'])
    def segment_summary(self, request):
        """分层汇总"""
        latest_date = self.get_queryset().order_by('-analysis_date').values_list(
            'analysis_date', flat=True
        ).first()
        
        if not latest_date:
            return Response({'segments': []})
        
        summary = self.get_queryset().filter(
            analysis_date=latest_date
        ).values('customer_segment').annotate(
            count=Count('id'),
            total_monetary=Sum('monetary'),
            avg_rfm=Avg('rfm_score')
        ).order_by('-count')
        
        return Response({
            'analysis_date': latest_date,
            'segments': list(summary)
        })
    
    @action(detail=False, methods=['get'])
    def top_customers(self, request):
        """价值TOP客户"""
        limit = int(request.query_params.get('limit', 20))
        
        latest_date = self.get_queryset().order_by('-analysis_date').values_list(
            'analysis_date', flat=True
        ).first()
        
        if not latest_date:
            return Response([])
        
        records = self.get_queryset().filter(
            analysis_date=latest_date
        ).order_by('-monetary')[:limit]
        
        return Response(CustomerRFMListSerializer(records, many=True).data)
    
    @action(detail=False, methods=['get'])
    def at_risk(self, request):
        """流失风险客户"""
        latest_date = self.get_queryset().order_by('-analysis_date').values_list(
            'analysis_date', flat=True
        ).first()
        
        if not latest_date:
            return Response([])
        
        # R评分低且M评分高的客户
        records = self.get_queryset().filter(
            analysis_date=latest_date,
            r_score__lte=2,
            m_score__gte=3
        ).order_by('-monetary')
        
        return Response({
            'count': records.count(),
            'data': CustomerRFMListSerializer(records, many=True).data
        })
