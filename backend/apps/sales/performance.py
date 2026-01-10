"""
销售业绩统计
Sales Performance Analytics
跟踪销售人员业绩、目标达成率等
"""
from datetime import date, timedelta
from decimal import Decimal
from django.db import models
from django.db.models import Sum, Count, Avg, F, Q
from django.db.models.functions import TruncMonth, TruncQuarter, TruncYear
from rest_framework import viewsets, serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.core.models import BaseModel
from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin


class SalesTarget(BaseModel):
    """
    销售目标
    """
    TARGET_TYPES = [
        ('MONTHLY', '月度目标'),
        ('QUARTERLY', '季度目标'),
        ('YEARLY', '年度目标'),
    ]
    
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='sales_targets',
        verbose_name='销售人员'
    )
    
    target_type = models.CharField(
        max_length=20,
        choices=TARGET_TYPES,
        default='MONTHLY',
        verbose_name='目标类型'
    )
    
    year = models.IntegerField(verbose_name='年份')
    month = models.IntegerField(null=True, blank=True, verbose_name='月份')
    quarter = models.IntegerField(null=True, blank=True, verbose_name='季度')
    
    # 目标金额
    order_target = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0,
        verbose_name='订单目标'
    )
    collection_target = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0,
        verbose_name='回款目标'
    )
    
    # 目标数量
    customer_target = models.IntegerField(default=0, verbose_name='新客户目标')
    opportunity_target = models.IntegerField(default=0, verbose_name='商机目标')
    
    # 实际完成（定期计算）
    order_actual = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0,
        verbose_name='订单实际'
    )
    collection_actual = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0,
        verbose_name='回款实际'
    )
    customer_actual = models.IntegerField(default=0, verbose_name='新客户实际')
    opportunity_actual = models.IntegerField(default=0, verbose_name='商机实际')
    
    remarks = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'sales_target'
        verbose_name = '销售目标'
        verbose_name_plural = verbose_name
        unique_together = ['user', 'target_type', 'year', 'month', 'quarter']
        ordering = ['-year', '-month']
    
    def __str__(self):
        if self.target_type == 'MONTHLY':
            return f'{self.user.get_full_name()} - {self.year}年{self.month}月'
        elif self.target_type == 'QUARTERLY':
            return f'{self.user.get_full_name()} - {self.year}年Q{self.quarter}'
        return f'{self.user.get_full_name()} - {self.year}年'
    
    @property
    def order_rate(self):
        """订单完成率"""
        if self.order_target == 0:
            return 0
        return round(float(self.order_actual) / float(self.order_target) * 100, 2)
    
    @property
    def collection_rate(self):
        """回款完成率"""
        if self.collection_target == 0:
            return 0
        return round(float(self.collection_actual) / float(self.collection_target) * 100, 2)


class SalesCommission(BaseModel):
    """
    销售提成
    """
    COMMISSION_TYPES = [
        ('ORDER', '订单提成'),
        ('COLLECTION', '回款提成'),
        ('BONUS', '奖金'),
        ('DEDUCTION', '扣款'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', '待确认'),
        ('CONFIRMED', '已确认'),
        ('PAID', '已发放'),
        ('CANCELLED', '已取消'),
    ]
    
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='commissions',
        verbose_name='销售人员'
    )
    
    commission_type = models.CharField(
        max_length=20,
        choices=COMMISSION_TYPES,
        default='ORDER',
        verbose_name='类型'
    )
    
    # 期间
    year = models.IntegerField(verbose_name='年份')
    month = models.IntegerField(verbose_name='月份')
    
    # 金额
    base_amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        verbose_name='基数金额'
    )
    commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name='提成比例%'
    )
    commission_amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        verbose_name='提成金额'
    )
    
    # 关联
    order = models.ForeignKey(
        'sales.SalesOrder',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='commissions',
        verbose_name='关联订单'
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
        verbose_name='状态'
    )
    
    confirmed_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='confirmed_commissions',
        verbose_name='确认人'
    )
    confirmed_at = models.DateTimeField(null=True, blank=True, verbose_name='确认时间')
    
    remarks = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'sales_commission'
        verbose_name = '销售提成'
        verbose_name_plural = verbose_name
        ordering = ['-year', '-month', '-created_at']
    
    def __str__(self):
        return f'{self.user.get_full_name()} - {self.year}年{self.month}月 - {self.commission_amount}'


# =====================
# Performance Service
# =====================

class SalesPerformanceService:
    """销售业绩服务"""
    
    @staticmethod
    def calculate_user_performance(user_id, year, month=None):
        """计算用户业绩"""
        from apps.sales.models import SalesOrder, SalesQuotation
        from apps.masterdata.models import Customer
        
        filters = {'salesperson_id': user_id, 'is_deleted': False}
        date_filters = Q(order_date__year=year)
        
        if month:
            date_filters &= Q(order_date__month=month)
        
        # 订单统计
        orders = SalesOrder.objects.filter(**filters).filter(date_filters)
        order_count = orders.count()
        order_amount = orders.filter(status__in=['CONFIRMED', 'COMPLETED']).aggregate(
            total=Sum('total_amount')
        )['total'] or 0
        
        # 报价统计
        quote_filters = Q(created_at__year=year)
        if month:
            quote_filters &= Q(created_at__month=month)
        
        quotes = SalesQuotation.objects.filter(
            created_by_id=user_id,
            is_deleted=False
        ).filter(quote_filters)
        quote_count = quotes.count()
        quote_amount = quotes.aggregate(total=Sum('total_amount'))['total'] or 0
        
        # 转化率
        won_quotes = quotes.filter(status='WON').count()
        conversion_rate = round(won_quotes / quote_count * 100, 2) if quote_count > 0 else 0
        
        # 新客户
        customer_filters = Q(created_at__year=year)
        if month:
            customer_filters &= Q(created_at__month=month)
        
        new_customers = Customer.objects.filter(
            created_by_id=user_id,
            is_deleted=False
        ).filter(customer_filters).count()
        
        return {
            'user_id': user_id,
            'year': year,
            'month': month,
            'order_count': order_count,
            'order_amount': float(order_amount),
            'quote_count': quote_count,
            'quote_amount': float(quote_amount),
            'conversion_rate': conversion_rate,
            'new_customers': new_customers
        }
    
    @staticmethod
    def calculate_team_ranking(year, month=None, limit=10):
        """计算团队排名"""
        from apps.sales.models import SalesOrder
        from apps.accounts.models import User
        
        date_filters = Q(order_date__year=year)
        if month:
            date_filters &= Q(order_date__month=month)
        
        ranking = SalesOrder.objects.filter(
            is_deleted=False,
            status__in=['CONFIRMED', 'COMPLETED']
        ).filter(date_filters).values(
            'salesperson', 'salesperson__first_name', 'salesperson__last_name'
        ).annotate(
            order_count=Count('id'),
            total_amount=Sum('total_amount')
        ).order_by('-total_amount')[:limit]
        
        result = []
        for i, item in enumerate(ranking, 1):
            result.append({
                'rank': i,
                'user_id': item['salesperson'],
                'name': f"{item['salesperson__first_name'] or ''}{item['salesperson__last_name'] or ''}".strip() or '未知',
                'order_count': item['order_count'],
                'total_amount': float(item['total_amount'] or 0)
            })
        
        return result
    
    @staticmethod
    def update_target_actual(target_id):
        """更新目标实际完成情况"""
        target = SalesTarget.objects.get(id=target_id)
        performance = SalesPerformanceService.calculate_user_performance(
            target.user_id, target.year, target.month
        )
        
        target.order_actual = performance['order_amount']
        target.customer_actual = performance['new_customers']
        # 回款需要单独计算
        target.save()
        
        return target


# =====================
# Serializers
# =====================

class SalesTargetSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    target_type_display = serializers.CharField(source='get_target_type_display', read_only=True)
    order_rate = serializers.FloatField(read_only=True)
    collection_rate = serializers.FloatField(read_only=True)
    
    class Meta:
        model = SalesTarget
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'order_actual', 'collection_actual', 
                          'customer_actual', 'opportunity_actual']


class SalesCommissionSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    commission_type_display = serializers.CharField(source='get_commission_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    order_no = serializers.CharField(source='order.order_no', read_only=True)
    
    class Meta:
        model = SalesCommission
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'confirmed_by', 'confirmed_at']


# =====================
# ViewSets
# =====================

class SalesTargetViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """销售目标管理"""
    queryset = SalesTarget.objects.filter(is_deleted=False)
    serializer_class = SalesTargetSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['user', 'target_type', 'year', 'month', 'quarter']
    ordering_fields = ['year', 'month', 'order_target']
    
    @action(detail=False, methods=['get'])
    def my_targets(self, request):
        """我的目标"""
        targets = self.get_queryset().filter(user=request.user)
        return Response(self.get_serializer(targets, many=True).data)
    
    @action(detail=True, methods=['post'])
    def refresh(self, request, pk=None):
        """刷新实际完成情况"""
        target = self.get_object()
        SalesPerformanceService.update_target_actual(target.id)
        target.refresh_from_db()
        return Response(self.get_serializer(target).data)
    
    @action(detail=False, methods=['post'])
    def batch_create(self, request):
        """批量创建目标"""
        year = request.data.get('year', date.today().year)
        users = request.data.get('users', [])
        order_target = Decimal(str(request.data.get('order_target', 0)))
        
        created = 0
        for user_id in users:
            for month in range(1, 13):
                _, c = SalesTarget.objects.get_or_create(
                    user_id=user_id,
                    target_type='MONTHLY',
                    year=year,
                    month=month,
                    defaults={
                        'order_target': order_target,
                        'created_by': request.user
                    }
                )
                if c:
                    created += 1
        
        return Response({'success': True, 'created': created})
    
    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        """目标完成仪表盘"""
        year = int(request.query_params.get('year', date.today().year))
        month = request.query_params.get('month')
        
        filters = {'year': year}
        if month:
            filters['month'] = int(month)
            filters['target_type'] = 'MONTHLY'
        
        targets = self.get_queryset().filter(**filters)
        
        # 汇总
        summary = targets.aggregate(
            total_order_target=Sum('order_target'),
            total_order_actual=Sum('order_actual'),
            total_collection_target=Sum('collection_target'),
            total_collection_actual=Sum('collection_actual')
        )
        
        order_target = summary['total_order_target'] or 0
        order_actual = summary['total_order_actual'] or 0
        
        return Response({
            'year': year,
            'month': month,
            'order_target': float(order_target),
            'order_actual': float(order_actual),
            'order_rate': round(float(order_actual) / float(order_target) * 100, 2) if order_target > 0 else 0,
            'collection_target': float(summary['total_collection_target'] or 0),
            'collection_actual': float(summary['total_collection_actual'] or 0),
            'targets': self.get_serializer(targets, many=True).data
        })


class SalesCommissionViewSet(SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """销售提成管理"""
    queryset = SalesCommission.objects.filter(is_deleted=False)
    serializer_class = SalesCommissionSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['user', 'commission_type', 'status', 'year', 'month']
    ordering_fields = ['year', 'month', 'commission_amount']
    
    @action(detail=False, methods=['get'])
    def my_commissions(self, request):
        """我的提成"""
        commissions = self.get_queryset().filter(user=request.user)
        return Response(self.get_serializer(commissions, many=True).data)
    
    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """确认提成"""
        from django.utils import timezone
        
        commission = self.get_object()
        commission.status = 'CONFIRMED'
        commission.confirmed_by = request.user
        commission.confirmed_at = timezone.now()
        commission.save()
        return Response(self.get_serializer(commission).data)
    
    @action(detail=True, methods=['post'])
    def pay(self, request, pk=None):
        """发放提成"""
        commission = self.get_object()
        if commission.status != 'CONFIRMED':
            return Response({'error': '只有已确认的提成才能发放'}, status=400)
        
        commission.status = 'PAID'
        commission.save()
        return Response(self.get_serializer(commission).data)
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """提成汇总"""
        year = int(request.query_params.get('year', date.today().year))
        
        # 按用户汇总
        by_user = self.get_queryset().filter(
            year=year,
            status__in=['CONFIRMED', 'PAID']
        ).values('user', 'user__first_name', 'user__last_name').annotate(
            total_commission=Sum('commission_amount'),
            total_base=Sum('base_amount'),
            count=Count('id')
        ).order_by('-total_commission')
        
        # 按月汇总
        by_month = self.get_queryset().filter(
            year=year,
            status__in=['CONFIRMED', 'PAID']
        ).values('month').annotate(
            total=Sum('commission_amount'),
            count=Count('id')
        ).order_by('month')
        
        return Response({
            'year': year,
            'by_user': list(by_user),
            'by_month': list(by_month),
            'total': self.get_queryset().filter(
                year=year, status__in=['CONFIRMED', 'PAID']
            ).aggregate(total=Sum('commission_amount'))['total'] or 0
        })


class SalesPerformanceViewSet(viewsets.ViewSet):
    """销售业绩统计"""
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def my_performance(self, request):
        """我的业绩"""
        year = int(request.query_params.get('year', date.today().year))
        month = request.query_params.get('month')
        if month:
            month = int(month)
        
        performance = SalesPerformanceService.calculate_user_performance(
            request.user.id, year, month
        )
        return Response(performance)
    
    @action(detail=False, methods=['get'])
    def team_ranking(self, request):
        """团队排名"""
        year = int(request.query_params.get('year', date.today().year))
        month = request.query_params.get('month')
        limit = int(request.query_params.get('limit', 10))
        
        if month:
            month = int(month)
        
        ranking = SalesPerformanceService.calculate_team_ranking(year, month, limit)
        return Response(ranking)
    
    @action(detail=False, methods=['get'])
    def monthly_trend(self, request):
        """月度趋势"""
        from apps.sales.models import SalesOrder
        
        year = int(request.query_params.get('year', date.today().year))
        user_id = request.query_params.get('user_id')
        
        filters = Q(order_date__year=year, is_deleted=False, status__in=['CONFIRMED', 'COMPLETED'])
        if user_id:
            filters &= Q(salesperson_id=user_id)
        
        monthly = SalesOrder.objects.filter(filters).annotate(
            month=TruncMonth('order_date')
        ).values('month').annotate(
            order_count=Count('id'),
            total_amount=Sum('total_amount')
        ).order_by('month')
        
        return Response(list(monthly))
    
    @action(detail=False, methods=['get'])
    def customer_analysis(self, request):
        """客户分析"""
        from apps.sales.models import SalesOrder
        from apps.masterdata.models import Customer
        
        year = int(request.query_params.get('year', date.today().year))
        
        # 客户贡献排名
        top_customers = SalesOrder.objects.filter(
            order_date__year=year,
            is_deleted=False,
            status__in=['CONFIRMED', 'COMPLETED']
        ).values('customer', 'customer__name').annotate(
            order_count=Count('id'),
            total_amount=Sum('total_amount')
        ).order_by('-total_amount')[:10]
        
        # 新客户数量
        new_customers_by_month = Customer.objects.filter(
            created_at__year=year,
            is_deleted=False
        ).annotate(
            month=TruncMonth('created_at')
        ).values('month').annotate(
            count=Count('id')
        ).order_by('month')
        
        return Response({
            'top_customers': list(top_customers),
            'new_customers_trend': list(new_customers_by_month)
        })
    
    @action(detail=False, methods=['get'])
    def pipeline_analysis(self, request):
        """销售漏斗分析"""
        from apps.sales.models import SalesQuotation
        
        year = int(request.query_params.get('year', date.today().year))
        
        # 各阶段统计
        stages = SalesQuotation.objects.filter(
            created_at__year=year,
            is_deleted=False
        ).values('status').annotate(
            count=Count('id'),
            total_amount=Sum('total_amount')
        )
        
        # 转化率
        total = SalesQuotation.objects.filter(
            created_at__year=year, is_deleted=False
        ).count()
        won = SalesQuotation.objects.filter(
            created_at__year=year, is_deleted=False, status='WON'
        ).count()
        
        return Response({
            'stages': list(stages),
            'total_quotes': total,
            'won_quotes': won,
            'conversion_rate': round(won / total * 100, 2) if total > 0 else 0
        })
