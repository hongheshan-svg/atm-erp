"""
税务管理模块
Tax Management
税率设置、税务申报、发票税务处理等
"""

from datetime import date, timedelta

from django.conf import settings
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


class TaxType(BaseModel):
    """税种"""

    code = models.CharField(max_length=20, unique=True, verbose_name='税种代码')
    name = models.CharField(max_length=100, verbose_name='税种名称')

    description = models.TextField(blank=True, verbose_name='描述')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')

    class Meta:
        db_table = 'finance_tax_type'
        verbose_name = '税种'
        verbose_name_plural = verbose_name
        ordering = ['code']

    def __str__(self):
        return f'{self.code} - {self.name}'


class TaxRate(BaseModel):
    """税率"""

    tax_type = models.ForeignKey(TaxType, on_delete=models.PROTECT, related_name='rates', verbose_name='税种')

    name = models.CharField(max_length=100, verbose_name='税率名称')
    rate = models.DecimalField(max_digits=8, decimal_places=4, verbose_name='税率')

    # 适用范围
    apply_to = models.CharField(max_length=50, blank=True, verbose_name='适用对象')

    # 有效期
    effective_from = models.DateField(verbose_name='生效日期')
    effective_to = models.DateField(null=True, blank=True, verbose_name='失效日期')

    is_default = models.BooleanField(default=False, verbose_name='是否默认')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')

    description = models.TextField(blank=True, verbose_name='描述')

    class Meta:
        db_table = 'finance_tax_rate'
        verbose_name = '税率'
        verbose_name_plural = verbose_name
        ordering = ['tax_type', '-effective_from']

    def __str__(self):
        return f'{self.name} ({self.rate * 100}%)'

    @property
    def is_effective(self):
        today = date.today()
        if self.effective_from > today:
            return False
        if self.effective_to and self.effective_to < today:
            return False
        return self.is_active


class TaxPeriod(BaseModel):
    """税务申报期间"""

    PERIOD_TYPE_CHOICES = [
        ('MONTHLY', '月度'),
        ('QUARTERLY', '季度'),
        ('YEARLY', '年度'),
    ]

    STATUS_CHOICES = [
        ('OPEN', '开放'),
        ('CLOSED', '已关闭'),
        ('DECLARED', '已申报'),
    ]

    period_type = models.CharField(
        max_length=20, choices=PERIOD_TYPE_CHOICES, default='MONTHLY', verbose_name='期间类型'
    )
    year = models.IntegerField(verbose_name='年度')
    period = models.IntegerField(verbose_name='期间')  # 月份(1-12)或季度(1-4)

    start_date = models.DateField(verbose_name='开始日期')
    end_date = models.DateField(verbose_name='结束日期')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OPEN', verbose_name='状态')

    # 申报截止日期
    declare_deadline = models.DateField(null=True, blank=True, verbose_name='申报截止日')

    # 申报信息
    declared_at = models.DateTimeField(null=True, blank=True, verbose_name='申报时间')
    declared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='declared_tax_periods',
        verbose_name='申报人',
    )

    notes = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'finance_tax_period'
        verbose_name = '税务期间'
        verbose_name_plural = verbose_name
        ordering = ['-year', '-period']
        unique_together = ['period_type', 'year', 'period']

    def __str__(self):
        if self.period_type == 'MONTHLY':
            return f'{self.year}年{self.period}月'
        elif self.period_type == 'QUARTERLY':
            return f'{self.year}年第{self.period}季度'
        else:
            return f'{self.year}年度'


class TaxDeclaration(BaseModel):
    """税务申报"""

    DECLARATION_TYPE_CHOICES = [
        ('VAT', '增值税'),
        ('INCOME', '企业所得税'),
        ('STAMP', '印花税'),
        ('URBAN', '城建税'),
        ('EDUCATION', '教育费附加'),
        ('LOCAL_EDUCATION', '地方教育附加'),
        ('OTHER', '其他'),
    ]

    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('SUBMITTED', '已提交'),
        ('APPROVED', '已审核'),
        ('DECLARED', '已申报'),
        ('PAID', '已缴款'),
        ('REJECTED', '已驳回'),
    ]

    declaration_no = models.CharField(max_length=50, unique=True, verbose_name='申报编号')

    tax_period = models.ForeignKey(
        TaxPeriod, on_delete=models.PROTECT, related_name='declarations', verbose_name='税务期间'
    )

    tax_type = models.ForeignKey(TaxType, on_delete=models.PROTECT, related_name='declarations', verbose_name='税种')

    declaration_type = models.CharField(
        max_length=20, choices=DECLARATION_TYPE_CHOICES, default='VAT', verbose_name='申报类型'
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', verbose_name='状态')

    # 金额信息
    taxable_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='应税金额')
    tax_rate = models.DecimalField(max_digits=8, decimal_places=4, default=0, verbose_name='税率')
    tax_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='应纳税额')

    # 抵扣信息
    deductible_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='可抵扣税额')

    # 实际应缴
    payable_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='应缴税额')

    # 已缴税款
    paid_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='已缴税额')

    # 申报信息
    submitted_at = models.DateTimeField(null=True, blank=True, verbose_name='提交时间')
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='submitted_declarations',
        verbose_name='提交人',
    )

    # 审核信息
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name='审核时间')
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_declarations',
        verbose_name='审核人',
    )

    # 申报信息
    declared_at = models.DateTimeField(null=True, blank=True, verbose_name='申报时间')
    declaration_receipt = models.CharField(max_length=100, blank=True, verbose_name='申报回执')

    # 缴款信息
    paid_at = models.DateTimeField(null=True, blank=True, verbose_name='缴款时间')
    payment_receipt = models.CharField(max_length=100, blank=True, verbose_name='缴款凭证')

    notes = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'finance_tax_declaration'
        verbose_name = '税务申报'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.declaration_no}'

    def save(self, *args, **kwargs):
        if not self.declaration_no:
            from apps.core.utils import generate_code

            self.declaration_no = generate_code('TAX')

        # 计算应缴税额
        self.payable_amount = self.tax_amount - self.deductible_amount

        super().save(*args, **kwargs)


class TaxDeclarationItem(BaseModel):
    """税务申报明细"""

    declaration = models.ForeignKey(
        TaxDeclaration, on_delete=models.CASCADE, related_name='items', verbose_name='申报单'
    )

    item_type = models.CharField(max_length=50, verbose_name='项目类型')
    item_name = models.CharField(max_length=200, verbose_name='项目名称')

    # 金额
    amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='金额')
    tax_rate = models.DecimalField(max_digits=8, decimal_places=4, default=0, verbose_name='税率')
    tax_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='税额')

    # 来源
    source_type = models.CharField(max_length=50, blank=True, verbose_name='来源类型')
    source_id = models.IntegerField(null=True, blank=True, verbose_name='来源ID')

    notes = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'finance_tax_declaration_item'
        verbose_name = '税务申报明细'
        verbose_name_plural = verbose_name
        ordering = ['declaration', 'id']


class TaxInvoice(BaseModel):
    """税务发票（进项/销项）"""

    INVOICE_DIRECTION_CHOICES = [
        ('INPUT', '进项'),
        ('OUTPUT', '销项'),
    ]

    INVOICE_TYPE_CHOICES = [
        ('SPECIAL', '增值税专用发票'),
        ('NORMAL', '增值税普通发票'),
        ('ELECTRONIC', '电子发票'),
        ('OTHER', '其他'),
    ]

    STATUS_CHOICES = [
        ('NORMAL', '正常'),
        ('VERIFIED', '已认证'),
        ('DEDUCTED', '已抵扣'),
        ('VOID', '已作废'),
        ('RED', '红冲'),
    ]

    direction = models.CharField(max_length=10, choices=INVOICE_DIRECTION_CHOICES, verbose_name='发票方向')
    invoice_type = models.CharField(
        max_length=20, choices=INVOICE_TYPE_CHOICES, default='SPECIAL', verbose_name='发票类型'
    )

    # 发票信息
    invoice_code = models.CharField(max_length=20, verbose_name='发票代码')
    invoice_no = models.CharField(max_length=20, verbose_name='发票号码')
    invoice_date = models.DateField(verbose_name='开票日期')

    # 购销方信息
    buyer_name = models.CharField(max_length=200, verbose_name='购买方名称')
    buyer_tax_no = models.CharField(max_length=50, verbose_name='购买方税号')
    seller_name = models.CharField(max_length=200, verbose_name='销售方名称')
    seller_tax_no = models.CharField(max_length=50, verbose_name='销售方税号')

    # 金额
    amount = models.DecimalField(max_digits=18, decimal_places=2, verbose_name='金额')
    tax_rate = models.DecimalField(max_digits=8, decimal_places=4, verbose_name='税率')
    tax_amount = models.DecimalField(max_digits=18, decimal_places=2, verbose_name='税额')
    total_amount = models.DecimalField(max_digits=18, decimal_places=2, verbose_name='价税合计')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='NORMAL', verbose_name='状态')

    # 认证信息（进项）
    verified_at = models.DateField(null=True, blank=True, verbose_name='认证日期')
    verify_period = models.ForeignKey(
        TaxPeriod,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_invoices',
        verbose_name='认证期间',
    )

    # 抵扣信息
    deduct_period = models.ForeignKey(
        TaxPeriod,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='deducted_invoices',
        verbose_name='抵扣期间',
    )

    # 关联业务
    source_type = models.CharField(max_length=50, blank=True, verbose_name='来源类型')
    source_id = models.IntegerField(null=True, blank=True, verbose_name='来源ID')

    notes = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'finance_tax_invoice'
        verbose_name = '税务发票'
        verbose_name_plural = verbose_name
        ordering = ['-invoice_date']
        unique_together = ['invoice_code', 'invoice_no']

    def __str__(self):
        return f'{self.invoice_code}-{self.invoice_no}'


# =====================
# Serializers
# =====================


class TaxTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxType
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class TaxRateSerializer(serializers.ModelSerializer):
    tax_type_name = serializers.CharField(source='tax_type.name', read_only=True)
    is_effective = serializers.BooleanField(read_only=True)
    rate_percent = serializers.SerializerMethodField()

    class Meta:
        model = TaxRate
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']

    def get_rate_percent(self, obj):
        return f'{obj.rate * 100}%'


class TaxPeriodSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_period_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    period_name = serializers.SerializerMethodField()

    class Meta:
        model = TaxPeriod
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'declared_at', 'declared_by']

    def get_period_name(self, obj):
        return str(obj)


class TaxDeclarationItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxDeclarationItem
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class TaxDeclarationSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_declaration_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    tax_type_name = serializers.CharField(source='tax_type.name', read_only=True)
    period_name = serializers.SerializerMethodField()
    items = TaxDeclarationItemSerializer(many=True, read_only=True)

    class Meta:
        model = TaxDeclaration
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'declaration_no', 'payable_amount']

    def get_period_name(self, obj):
        return str(obj.tax_period)


class TaxInvoiceSerializer(serializers.ModelSerializer):
    direction_display = serializers.CharField(source='get_direction_display', read_only=True)
    type_display = serializers.CharField(source='get_invoice_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = TaxInvoice
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


# =====================
# ViewSets
# =====================


class TaxTypeViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    permission_module = 'finance'
    permission_resource = 'tax_type'
    """税种管理"""
    queryset = TaxType.objects.filter(is_deleted=False)
    serializer_class = TaxTypeSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['is_active']
    search_fields = ['code', 'name']


class TaxRateViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    permission_module = 'finance'
    permission_resource = 'tax_rate'
    """税率管理"""
    queryset = TaxRate.objects.filter(is_deleted=False)
    serializer_class = TaxRateSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['tax_type', 'is_active', 'is_default']
    search_fields = ['name']

    @action(detail=False, methods=['get'])
    def effective(self, request):
        """获取当前有效税率"""
        today = date.today()
        rates = (
            self.get_queryset()
            .filter(is_active=True, effective_from__lte=today)
            .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=today))
        )
        return Response(self.get_serializer(rates, many=True).data)


class TaxPeriodViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    permission_module = 'finance'
    permission_resource = 'tax_period'
    """税务期间管理"""
    queryset = TaxPeriod.objects.filter(is_deleted=False)
    serializer_class = TaxPeriodSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['period_type', 'year', 'status']

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        """关闭期间"""
        period = self.get_object()
        period.status = 'CLOSED'
        period.save()
        return Response(self.get_serializer(period).data)

    @action(detail=False, methods=['post'])
    def generate(self, request):
        """生成期间"""
        year = request.data.get('year', date.today().year)
        period_type = request.data.get('period_type', 'MONTHLY')

        periods = []

        if period_type == 'MONTHLY':
            for month in range(1, 13):
                start = date(year, month, 1)
                if month == 12:
                    end = date(year + 1, 1, 1) - timedelta(days=1)
                else:
                    end = date(year, month + 1, 1) - timedelta(days=1)

                period, created = TaxPeriod.objects.get_or_create(
                    period_type='MONTHLY',
                    year=year,
                    period=month,
                    defaults={'start_date': start, 'end_date': end, 'created_by': request.user},
                )
                if created:
                    periods.append(period)

        elif period_type == 'QUARTERLY':
            for q in range(1, 5):
                start_month = (q - 1) * 3 + 1
                start = date(year, start_month, 1)
                end_month = q * 3
                if end_month == 12:
                    end = date(year + 1, 1, 1) - timedelta(days=1)
                else:
                    end = date(year, end_month + 1, 1) - timedelta(days=1)

                period, created = TaxPeriod.objects.get_or_create(
                    period_type='QUARTERLY',
                    year=year,
                    period=q,
                    defaults={'start_date': start, 'end_date': end, 'created_by': request.user},
                )
                if created:
                    periods.append(period)

        return Response(
            {'message': f'生成 {len(periods)} 个期间', 'periods': self.get_serializer(periods, many=True).data}
        )


class TaxDeclarationViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    permission_module = 'finance'
    permission_resource = 'tax_declaration'
    """税务申报管理"""
    queryset = TaxDeclaration.objects.filter(is_deleted=False)
    serializer_class = TaxDeclarationSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['tax_period', 'tax_type', 'declaration_type', 'status']
    search_fields = ['declaration_no']
    ordering_fields = ['created_at', 'submitted_at']

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """提交申报"""
        declaration = self.get_object()

        if declaration.status != 'DRAFT':
            return Response({'error': '当前状态无法提交'}, status=400)

        declaration.status = 'SUBMITTED'
        declaration.submitted_at = timezone.now()
        declaration.submitted_by = request.user
        declaration.save()

        return Response(self.get_serializer(declaration).data)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """审核通过"""
        declaration = self.get_object()

        if declaration.status != 'SUBMITTED':
            return Response({'error': '当前状态无法审核'}, status=400)

        declaration.status = 'APPROVED'
        declaration.approved_at = timezone.now()
        declaration.approved_by = request.user
        declaration.save()

        return Response(self.get_serializer(declaration).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """驳回"""
        declaration = self.get_object()

        if declaration.status != 'SUBMITTED':
            return Response({'error': '当前状态无法驳回'}, status=400)

        declaration.status = 'REJECTED'
        declaration.notes = request.data.get('reason', '')
        declaration.save()

        return Response(self.get_serializer(declaration).data)

    @action(detail=True, methods=['post'])
    def declare(self, request, pk=None):
        """确认申报"""
        declaration = self.get_object()

        if declaration.status != 'APPROVED':
            return Response({'error': '请先完成审核'}, status=400)

        declaration.status = 'DECLARED'
        declaration.declared_at = timezone.now()
        declaration.declaration_receipt = request.data.get('receipt', '')
        declaration.save()

        return Response(self.get_serializer(declaration).data)

    @action(detail=True, methods=['post'])
    def pay(self, request, pk=None):
        """确认缴款"""
        declaration = self.get_object()

        if declaration.status != 'DECLARED':
            return Response({'error': '请先完成申报'}, status=400)

        declaration.status = 'PAID'
        declaration.paid_at = timezone.now()
        declaration.paid_amount = declaration.payable_amount
        declaration.payment_receipt = request.data.get('receipt', '')
        declaration.save()

        return Response(self.get_serializer(declaration).data)

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """申报统计"""
        qs = self.get_queryset()
        year = request.query_params.get('year', date.today().year)

        # 按税种统计
        by_type = (
            qs.filter(tax_period__year=year, status='PAID')
            .values('declaration_type')
            .annotate(total_amount=Sum('payable_amount'), count=Count('id'))
        )

        # 月度趋势
        monthly = (
            qs.filter(tax_period__year=year, tax_period__period_type='MONTHLY', status='PAID')
            .values('tax_period__period')
            .annotate(total_amount=Sum('payable_amount'))
            .order_by('tax_period__period')
        )

        return Response(
            {
                'by_type': list(by_type),
                'monthly': list(monthly),
                'total_paid': qs.filter(status='PAID').aggregate(total=Sum('paid_amount'))['total'] or 0,
            }
        )


class TaxInvoiceViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    permission_module = 'finance'
    permission_resource = 'tax_invoice'
    """税务发票管理"""
    queryset = TaxInvoice.objects.filter(is_deleted=False)
    serializer_class = TaxInvoiceSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['direction', 'invoice_type', 'status']
    search_fields = ['invoice_code', 'invoice_no', 'buyer_name', 'seller_name']
    ordering_fields = ['invoice_date']

    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        """认证发票"""
        invoice = self.get_object()

        if invoice.direction != 'INPUT':
            return Response({'error': '只能认证进项发票'}, status=400)

        if invoice.status != 'NORMAL':
            return Response({'error': '当前状态无法认证'}, status=400)

        invoice.status = 'VERIFIED'
        invoice.verified_at = date.today()
        invoice.verify_period_id = request.data.get('period_id')
        invoice.save()

        return Response(self.get_serializer(invoice).data)

    @action(detail=True, methods=['post'])
    def deduct(self, request, pk=None):
        """抵扣发票"""
        invoice = self.get_object()

        if invoice.direction != 'INPUT':
            return Response({'error': '只能抵扣进项发票'}, status=400)

        if invoice.status != 'VERIFIED':
            return Response({'error': '请先完成认证'}, status=400)

        invoice.status = 'DEDUCTED'
        invoice.deduct_period_id = request.data.get('period_id')
        invoice.save()

        return Response(self.get_serializer(invoice).data)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """发票汇总"""
        qs = self.get_queryset()

        # 按方向统计
        input_total = qs.filter(direction='INPUT', status__in=['NORMAL', 'VERIFIED', 'DEDUCTED']).aggregate(
            amount=Sum('amount'), tax=Sum('tax_amount'), total=Sum('total_amount')
        )

        output_total = qs.filter(direction='OUTPUT', status='NORMAL').aggregate(
            amount=Sum('amount'), tax=Sum('tax_amount'), total=Sum('total_amount')
        )

        # 待认证进项
        pending_verify = qs.filter(direction='INPUT', status='NORMAL').aggregate(
            count=Count('id'), tax=Sum('tax_amount')
        )

        # 已认证未抵扣
        pending_deduct = qs.filter(direction='INPUT', status='VERIFIED').aggregate(
            count=Count('id'), tax=Sum('tax_amount')
        )

        return Response(
            {
                'input': input_total,
                'output': output_total,
                'pending_verify': pending_verify,
                'pending_deduct': pending_deduct,
            }
        )
