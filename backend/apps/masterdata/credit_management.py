"""
客户信用额度管理 (可选功能)
Customer Credit Management

功能：管理客户信用额度、账期、风险评级等

非标自动化行业使用建议：
- 此功能为可选，适用于需要控制应收款风险的场景
- 项目型业务通常按合同约定收款，信用管理需求较少
- 如有老客户赊销需求，可启用此功能
- 折扣率等功能更适合标准产品销售，非标可忽略

核心功能保留：
- 信用额度控制（防止超额赊销）
- 账期管理（控制回款周期）
"""

from datetime import date
from decimal import Decimal

from django.db import models
from django.db.models import Count, Q, Sum
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.models import BaseModel
from apps.core.permission_mixin import PermissionMixin


class CreditLevel(BaseModel):
    """
    信用等级
    """

    code = models.CharField(max_length=10, unique=True, verbose_name='等级编码')
    name = models.CharField(max_length=50, verbose_name='等级名称')

    # 默认额度和账期
    default_credit_limit = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='默认信用额度')
    default_payment_days = models.IntegerField(default=30, verbose_name='默认账期(天)')

    # 折扣
    discount_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='折扣率(%)')

    # 规则
    min_order_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='最低订单金额')
    prepayment_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='预付款比例(%)')

    color = models.CharField(max_length=20, default='#409EFF', verbose_name='显示颜色')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    description = models.TextField(blank=True, verbose_name='说明')

    class Meta:
        db_table = 'masterdata_credit_level'
        verbose_name = '信用等级'
        verbose_name_plural = verbose_name
        ordering = ['sort_order', 'code']

    def __str__(self):
        return f'{self.code} - {self.name}'


class CustomerCredit(BaseModel):
    """
    客户信用
    """

    STATUS_CHOICES = [
        ('NORMAL', '正常'),
        ('WARNING', '预警'),
        ('FROZEN', '冻结'),
        ('BLACKLIST', '黑名单'),
    ]

    customer = models.OneToOneField(
        'masterdata.Customer', on_delete=models.CASCADE, related_name='credit_info', verbose_name='客户'
    )
    credit_level = models.ForeignKey(
        CreditLevel, on_delete=models.SET_NULL, null=True, blank=True, related_name='customers', verbose_name='信用等级'
    )

    # 信用额度
    credit_limit = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='信用额度')
    temporary_limit = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='临时额度')
    temp_limit_expire = models.DateField(null=True, blank=True, verbose_name='临时额度到期日')

    # 已用额度（定期计算）
    used_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='已用额度')

    # 账期
    payment_days = models.IntegerField(default=30, verbose_name='账期(天)')

    # 状态
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='NORMAL', verbose_name='状态')

    # 风险评分
    risk_score = models.IntegerField(default=100, verbose_name='风险评分')

    # 逾期统计
    overdue_times = models.IntegerField(default=0, verbose_name='逾期次数')
    total_overdue_days = models.IntegerField(default=0, verbose_name='累计逾期天数')
    max_overdue_days = models.IntegerField(default=0, verbose_name='最长逾期天数')
    current_overdue_amount = models.DecimalField(
        max_digits=18, decimal_places=2, default=0, verbose_name='当前逾期金额'
    )

    # 历史统计
    total_order_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='累计订单金额')
    total_payment_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='累计回款金额')

    # 审批
    last_reviewed_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_credits',
        verbose_name='最后审核人',
    )
    last_reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name='最后审核时间')

    remarks = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'masterdata_customer_credit'
        verbose_name = '客户信用'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'{self.customer.name} - {self.credit_limit}'

    @property
    def available_credit(self):
        """可用额度"""
        total_limit = self.credit_limit

        # 检查临时额度
        if self.temporary_limit > 0 and self.temp_limit_expire:
            if self.temp_limit_expire >= date.today():
                total_limit += self.temporary_limit

        return max(total_limit - self.used_amount, Decimal('0'))

    @property
    def usage_rate(self):
        """额度使用率"""
        if self.credit_limit <= 0:
            return 0
        return round(float(self.used_amount) / float(self.credit_limit) * 100, 2)

    def check_credit(self, amount: Decimal) -> tuple:
        """检查信用额度
        Returns: (是否通过, 提示信息)
        """
        if self.status == 'FROZEN':
            return False, '客户信用已冻结'
        if self.status == 'BLACKLIST':
            return False, '客户在黑名单中'

        if amount > self.available_credit:
            return False, f'超出可用信用额度，可用额度: {self.available_credit}'

        return True, 'OK'

    def update_used_amount(self):
        """更新已用额度"""
        from apps.finance.models import AccountsReceivable

        # 计算未收款金额
        ar_amount = AccountsReceivable.objects.filter(
            customer=self.customer, status__in=['PENDING', 'PARTIAL'], is_deleted=False
        ).aggregate(total=Sum('balance_amount'))['total'] or Decimal('0')

        self.used_amount = ar_amount
        self.save()


class CreditAdjustment(BaseModel):
    """
    信用额度调整记录
    """

    ADJUSTMENT_TYPES = [
        ('INCREASE', '增加'),
        ('DECREASE', '减少'),
        ('TEMP_INCREASE', '临时增加'),
        ('RESET', '重置'),
    ]

    customer_credit = models.ForeignKey(
        CustomerCredit, on_delete=models.CASCADE, related_name='adjustments', verbose_name='客户信用'
    )

    adjustment_type = models.CharField(max_length=20, choices=ADJUSTMENT_TYPES, verbose_name='调整类型')

    # 调整金额
    before_amount = models.DecimalField(max_digits=18, decimal_places=2, verbose_name='调整前额度')
    adjustment_amount = models.DecimalField(max_digits=18, decimal_places=2, verbose_name='调整金额')
    after_amount = models.DecimalField(max_digits=18, decimal_places=2, verbose_name='调整后额度')

    # 临时额度专用
    expire_date = models.DateField(null=True, blank=True, verbose_name='临时额度到期日')

    reason = models.TextField(verbose_name='调整原因')

    # 审批
    approved_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_credit_adjustments',
        verbose_name='审批人',
    )
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name='审批时间')

    class Meta:
        db_table = 'masterdata_credit_adjustment'
        verbose_name = '信用额度调整'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.customer_credit.customer.name} - {self.get_adjustment_type_display()}'


# =====================
# Serializers
# =====================


class CreditLevelSerializer(serializers.ModelSerializer):
    customer_count = serializers.SerializerMethodField()

    class Meta:
        model = CreditLevel
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']

    def get_customer_count(self, obj):
        return obj.customers.filter(is_deleted=False).count()


class CustomerCreditSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    customer_code = serializers.CharField(source='customer.code', read_only=True)
    level_name = serializers.CharField(source='credit_level.name', read_only=True)
    level_code = serializers.CharField(source='credit_level.code', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    available_credit = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)
    usage_rate = serializers.FloatField(read_only=True)

    class Meta:
        model = CustomerCredit
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'used_amount', 'last_reviewed_by', 'last_reviewed_at']


class CustomerCreditListSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    customer_code = serializers.CharField(source='customer.code', read_only=True)
    level_name = serializers.CharField(source='credit_level.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    available_credit = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)
    usage_rate = serializers.FloatField(read_only=True)

    class Meta:
        model = CustomerCredit
        fields = [
            'id',
            'customer',
            'customer_name',
            'customer_code',
            'credit_level',
            'level_name',
            'credit_limit',
            'used_amount',
            'available_credit',
            'usage_rate',
            'payment_days',
            'status',
            'status_display',
            'risk_score',
            'overdue_times',
        ]


class CreditAdjustmentSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer_credit.customer.name', read_only=True)
    adjustment_type_display = serializers.CharField(source='get_adjustment_type_display', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True)

    class Meta:
        model = CreditAdjustment
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'approved_by', 'approved_at', 'before_amount', 'after_amount']


# =====================
# ViewSets
# =====================


class CreditLevelViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """信用等级管理"""

    queryset = CreditLevel.objects.filter(is_deleted=False)
    serializer_class = CreditLevelSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ['code', 'name']

    @action(detail=False, methods=['post'])
    def init_levels(self, request):
        """初始化默认信用等级"""
        levels = [
            ('A', 'A级-优质客户', 500000, 60, 5, '#67C23A'),
            ('B', 'B级-良好客户', 200000, 45, 3, '#409EFF'),
            ('C', 'C级-普通客户', 100000, 30, 0, '#E6A23C'),
            ('D', 'D级-风险客户', 50000, 15, 0, '#F56C6C'),
            ('N', 'N级-新客户', 0, 0, 0, '#909399'),
        ]

        created = 0
        for i, (code, name, limit, days, discount, color) in enumerate(levels):
            _, c = CreditLevel.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'default_credit_limit': limit,
                    'default_payment_days': days,
                    'discount_rate': discount,
                    'color': color,
                    'sort_order': i * 10,
                    'created_by': request.user,
                },
            )
            if c:
                created += 1

        return Response({'success': True, 'created': created})


class CustomerCreditViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    """客户信用管理"""

    queryset = CustomerCredit.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filterset_fields = ['credit_level', 'status']
    search_fields = ['customer__name', 'customer__code']
    ordering_fields = ['credit_limit', 'used_amount', 'risk_score']

    def get_serializer_class(self):
        if self.action == 'list':
            return CustomerCreditListSerializer
        return CustomerCreditSerializer

    @action(detail=True, methods=['post'])
    def adjust_credit(self, request, pk=None):
        """调整信用额度"""
        credit = self.get_object()
        adjustment_type = request.data.get('adjustment_type')
        amount = Decimal(str(request.data.get('amount', 0)))
        reason = request.data.get('reason', '')
        expire_date = request.data.get('expire_date')

        before_amount = credit.credit_limit

        if adjustment_type == 'INCREASE':
            credit.credit_limit += amount
        elif adjustment_type == 'DECREASE':
            credit.credit_limit = max(credit.credit_limit - amount, Decimal('0'))
        elif adjustment_type == 'TEMP_INCREASE':
            credit.temporary_limit = amount
            credit.temp_limit_expire = expire_date
        elif adjustment_type == 'RESET':
            credit.credit_limit = amount

        credit.last_reviewed_by = request.user
        credit.last_reviewed_at = timezone.now()
        credit.save()

        # 记录调整
        CreditAdjustment.objects.create(
            customer_credit=credit,
            adjustment_type=adjustment_type,
            before_amount=before_amount,
            adjustment_amount=amount,
            after_amount=credit.credit_limit,
            expire_date=expire_date if adjustment_type == 'TEMP_INCREASE' else None,
            reason=reason,
            approved_by=request.user,
            approved_at=timezone.now(),
            created_by=request.user,
        )

        return Response(self.get_serializer(credit).data)

    @action(detail=True, methods=['post'])
    def change_status(self, request, pk=None):
        """修改状态"""
        credit = self.get_object()
        new_status = request.data.get('status')
        reason = request.data.get('reason', '')

        if new_status not in dict(CustomerCredit.STATUS_CHOICES):
            return Response({'error': '无效的状态'}, status=400)

        credit.status = new_status
        credit.last_reviewed_by = request.user
        credit.last_reviewed_at = timezone.now()
        if reason:
            credit.remarks = f'{credit.remarks}\n[{timezone.now().strftime("%Y-%m-%d")}] 状态变更: {reason}'
        credit.save()

        return Response(self.get_serializer(credit).data)

    @action(detail=True, methods=['post'])
    def refresh_used(self, request, pk=None):
        """刷新已用额度"""
        credit = self.get_object()
        credit.update_used_amount()
        return Response(self.get_serializer(credit).data)

    @action(detail=False, methods=['post'])
    def check_order(self, request):
        """检查订单信用"""
        customer_id = request.data.get('customer_id')
        amount = Decimal(str(request.data.get('amount', 0)))

        try:
            credit = CustomerCredit.objects.get(customer_id=customer_id)
        except CustomerCredit.DoesNotExist:
            return Response({'passed': True, 'message': '客户无信用控制', 'available_credit': None})

        passed, message = credit.check_credit(amount)

        return Response(
            {
                'passed': passed,
                'message': message,
                'credit_limit': credit.credit_limit,
                'used_amount': credit.used_amount,
                'available_credit': credit.available_credit,
                'status': credit.status,
            }
        )

    @action(detail=False, methods=['get'])
    def warning_list(self, request):
        """预警客户列表"""
        threshold = float(request.query_params.get('threshold', 80))

        # 获取额度使用率超过阈值的客户
        credits = []
        for credit in self.get_queryset():
            if credit.usage_rate >= threshold or credit.status in ['WARNING', 'FROZEN']:
                credits.append(credit)

        return Response(CustomerCreditListSerializer(credits, many=True).data)

    @action(detail=False, methods=['get'])
    def overdue_list(self, request):
        """逾期客户列表"""
        credits = (
            self.get_queryset()
            .filter(Q(current_overdue_amount__gt=0) | Q(overdue_times__gt=0))
            .order_by('-current_overdue_amount')
        )

        return Response(CustomerCreditListSerializer(credits, many=True).data)

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """信用统计"""
        qs = self.get_queryset()

        total_limit = qs.aggregate(total=Sum('credit_limit'))['total'] or 0
        total_used = qs.aggregate(total=Sum('used_amount'))['total'] or 0

        by_status = qs.values('status').annotate(count=Count('id'), total_limit=Sum('credit_limit'))

        by_level = qs.values('credit_level__name').annotate(count=Count('id'), total_limit=Sum('credit_limit'))

        return Response(
            {
                'total_customers': qs.count(),
                'total_credit_limit': float(total_limit),
                'total_used_amount': float(total_used),
                'overall_usage_rate': round(float(total_used) / float(total_limit) * 100, 2) if total_limit > 0 else 0,
                'by_status': list(by_status),
                'by_level': list(by_level),
            }
        )


class CreditAdjustmentViewSet(PermissionMixin, viewsets.ReadOnlyModelViewSet):
    """信用调整记录"""

    queryset = CreditAdjustment.objects.filter(is_deleted=False)
    serializer_class = CreditAdjustmentSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['customer_credit', 'adjustment_type']
    ordering_fields = ['created_at']
