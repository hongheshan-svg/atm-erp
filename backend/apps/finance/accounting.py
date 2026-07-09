"""
总账管理模块
General Ledger Management
会计科目、凭证管理基础功能
"""

from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.db import models, transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.mixins import SoftDeleteMixin, UserTrackingMixin
from apps.core.models import BaseModel
from apps.core.permission_mixin import PermissionMixin


class AccountCategory(BaseModel):
    """科目类别"""

    CATEGORY_TYPE_CHOICES = [
        ('ASSET', '资产类'),
        ('LIABILITY', '负债类'),
        ('EQUITY', '所有者权益类'),
        ('COST', '成本类'),
        ('PROFIT_LOSS', '损益类'),
    ]

    name = models.CharField(max_length=100, verbose_name='类别名称')
    code = models.CharField(max_length=10, unique=True, verbose_name='类别代码')
    category_type = models.CharField(max_length=20, choices=CATEGORY_TYPE_CHOICES, verbose_name='科目类型')
    sort_order = models.IntegerField(default=0, verbose_name='排序')

    class Meta:
        db_table = 'fin_account_category'
        verbose_name = '科目类别'
        verbose_name_plural = verbose_name
        ordering = ['sort_order', 'code']

    def __str__(self):
        return f'{self.code} - {self.name}'


class ChartOfAccount(BaseModel):
    """会计科目"""

    BALANCE_DIRECTION_CHOICES = [
        ('DEBIT', '借方'),
        ('CREDIT', '贷方'),
    ]

    code = models.CharField(max_length=20, unique=True, verbose_name='科目代码')
    name = models.CharField(max_length=100, verbose_name='科目名称')
    english_name = models.CharField(max_length=200, blank=True, verbose_name='英文名称')

    category = models.ForeignKey(
        AccountCategory, on_delete=models.PROTECT, related_name='accounts', verbose_name='科目类别'
    )

    parent = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True, related_name='children', verbose_name='上级科目'
    )

    level = models.IntegerField(default=1, verbose_name='科目级别')

    balance_direction = models.CharField(
        max_length=10, choices=BALANCE_DIRECTION_CHOICES, default='DEBIT', verbose_name='余额方向'
    )

    # 辅助核算
    has_auxiliary = models.BooleanField(default=False, verbose_name='是否有辅助核算')
    aux_customer = models.BooleanField(default=False, verbose_name='客户往来')
    aux_supplier = models.BooleanField(default=False, verbose_name='供应商往来')
    aux_project = models.BooleanField(default=False, verbose_name='项目核算')
    aux_department = models.BooleanField(default=False, verbose_name='部门核算')
    aux_employee = models.BooleanField(default=False, verbose_name='员工核算')

    # 币种
    is_foreign_currency = models.BooleanField(default=False, verbose_name='外币核算')

    # 状态
    is_detail = models.BooleanField(default=True, verbose_name='是否明细科目')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')

    description = models.TextField(blank=True, verbose_name='说明')

    class Meta:
        db_table = 'fin_chart_of_account'
        verbose_name = '会计科目'
        verbose_name_plural = verbose_name
        ordering = ['code']

    def __str__(self):
        return f'{self.code} - {self.name}'

    def save(self, *args, **kwargs):
        # 自动计算级别
        if self.parent:
            self.level = self.parent.level + 1
        else:
            self.level = 1

        # 有子科目则不是明细科目
        if self.pk:
            has_children = ChartOfAccount.objects.filter(parent=self, is_deleted=False).exists()
            if has_children:
                self.is_detail = False

        super().save(*args, **kwargs)


class FiscalPeriod(BaseModel):
    """会计期间"""

    STATUS_CHOICES = [
        ('OPEN', '开放'),
        ('CLOSED', '已关闭'),
        ('LOCKED', '已锁定'),
    ]

    year = models.IntegerField(verbose_name='年度')
    period = models.IntegerField(verbose_name='期间')  # 1-12

    start_date = models.DateField(verbose_name='开始日期')
    end_date = models.DateField(verbose_name='结束日期')

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='OPEN', verbose_name='状态')

    closed_at = models.DateTimeField(null=True, blank=True, verbose_name='关闭时间')
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='closed_periods',
        verbose_name='关闭人',
    )

    class Meta:
        db_table = 'fin_fiscal_period'
        verbose_name = '会计期间'
        verbose_name_plural = verbose_name
        ordering = ['-year', '-period']
        unique_together = ('year', 'period')

    def __str__(self):
        return f'{self.year}年第{self.period}期'


class JournalVoucher(BaseModel):
    """记账凭证"""

    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('PENDING', '待审核'),
        ('APPROVED', '已审核'),
        ('POSTED', '已过账'),
        ('CANCELLED', '已作废'),
    ]

    VOUCHER_TYPE_CHOICES = [
        ('RECEIPT', '收款凭证'),
        ('PAYMENT', '付款凭证'),
        ('TRANSFER', '转账凭证'),
        ('GENERAL', '记账凭证'),
    ]

    voucher_no = models.CharField(max_length=50, unique=True, verbose_name='凭证号')
    voucher_type = models.CharField(
        max_length=20, choices=VOUCHER_TYPE_CHOICES, default='GENERAL', verbose_name='凭证类型'
    )

    fiscal_period = models.ForeignKey(
        FiscalPeriod, on_delete=models.PROTECT, related_name='vouchers', verbose_name='会计期间'
    )

    voucher_date = models.DateField(verbose_name='凭证日期')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', verbose_name='状态')

    # 附件数
    attachment_count = models.IntegerField(default=0, verbose_name='附件数')

    # 摘要
    summary = models.CharField(max_length=500, blank=True, verbose_name='摘要')

    # 借贷合计
    debit_total = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='借方合计')
    credit_total = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='贷方合计')

    # 审核信息
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_vouchers',
        verbose_name='审核人',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name='审核时间')

    # 过账信息
    posted_at = models.DateTimeField(null=True, blank=True, verbose_name='过账时间')
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='posted_vouchers',
        verbose_name='过账人',
    )

    notes = models.TextField(blank=True, verbose_name='备注')

    # 自动过账来源追溯(业务单据 -> 凭证)。自动过账引擎(apps.finance.posting)据此保证
    # 幂等:一张业务单据(source_type + source_id)最多生成一张凭证。手工录入的凭证这两个
    # 字段留空/为 None,不参与幂等去重。
    source_type = models.CharField(max_length=30, blank=True, db_index=True, verbose_name='来源单据类型')
    source_id = models.IntegerField(null=True, blank=True, db_index=True, verbose_name='来源单据ID')

    class Meta:
        db_table = 'fin_journal_voucher'
        verbose_name = '记账凭证'
        verbose_name_plural = verbose_name
        ordering = ['-voucher_date', '-voucher_no']

    def __str__(self):
        return f'{self.voucher_no} - {self.summary}'

    def save(self, *args, **kwargs):
        if not self.voucher_no:
            from apps.core.utils import generate_code

            self.voucher_no = generate_code('JV')
        super().save(*args, **kwargs)

    def calculate_totals(self):
        """计算借贷合计"""
        totals = self.lines.filter(is_deleted=False).aggregate(debit=Sum('debit_amount'), credit=Sum('credit_amount'))
        self.debit_total = totals['debit'] or 0
        self.credit_total = totals['credit'] or 0
        self.save(update_fields=['debit_total', 'credit_total'])

    @property
    def is_balanced(self):
        """借贷是否平衡"""
        return self.debit_total == self.credit_total


class VoucherLine(BaseModel):
    """凭证分录"""

    voucher = models.ForeignKey(JournalVoucher, on_delete=models.CASCADE, related_name='lines', verbose_name='凭证')
    line_no = models.IntegerField(default=1, verbose_name='行号')

    account = models.ForeignKey(
        ChartOfAccount, on_delete=models.PROTECT, related_name='voucher_lines', verbose_name='会计科目'
    )

    summary = models.CharField(max_length=500, blank=True, verbose_name='摘要')

    debit_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='借方金额')
    credit_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='贷方金额')

    # 辅助核算
    customer = models.ForeignKey(
        'masterdata.Customer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='voucher_lines',
        verbose_name='客户',
    )
    supplier = models.ForeignKey(
        'masterdata.Supplier',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='voucher_lines',
        verbose_name='供应商',
    )
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='voucher_lines',
        verbose_name='项目',
    )
    department = models.ForeignKey(
        'accounts.Department',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='voucher_lines',
        verbose_name='部门',
    )

    class Meta:
        db_table = 'fin_voucher_line'
        verbose_name = '凭证分录'
        verbose_name_plural = verbose_name
        ordering = ['voucher', 'line_no']

    def __str__(self):
        return f'{self.voucher.voucher_no} - {self.line_no}'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # 更新凭证合计
        self.voucher.calculate_totals()


class AccountBalance(BaseModel):
    """科目余额"""

    account = models.ForeignKey(
        ChartOfAccount, on_delete=models.CASCADE, related_name='balances', verbose_name='会计科目'
    )
    fiscal_period = models.ForeignKey(
        FiscalPeriod, on_delete=models.CASCADE, related_name='balances', verbose_name='会计期间'
    )

    # 期初
    opening_debit = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='期初借方')
    opening_credit = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='期初贷方')

    # 本期发生
    period_debit = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='本期借方')
    period_credit = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='本期贷方')

    # 期末
    closing_debit = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='期末借方')
    closing_credit = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name='期末贷方')

    class Meta:
        db_table = 'fin_account_balance'
        verbose_name = '科目余额'
        verbose_name_plural = verbose_name
        unique_together = ('account', 'fiscal_period')

    def __str__(self):
        return f'{self.account.code} - {self.fiscal_period}'


# =====================
# 过账辅助 (posting-to-balance helper)
# =====================


def post_voucher_to_ledger(voucher, user=None):
    """把一张(已平衡的)凭证过账到科目余额并落 ``POSTED`` 状态。

    从 ``JournalVoucherViewSet.post_voucher`` 抽取为模块级函数,供手工过账 action 与
    自动过账引擎(``apps.finance.posting.post_document``)共同复用,避免"分录发生额累加到
    科目余额"这段逻辑在两处重复实现而走样。

    约定:调用方负责全部前置校验(凭证状态、借贷平衡、会计期间开放);本函数只做两件事——
      1. 每条分录的借/贷金额累加到 ``AccountBalance`` 的本期发生额,并按期初重算期末;
      2. 凭证置 ``POSTED`` 并记录过账人/时间。

    非幂等(余额为累加写入):同一张凭证只应过账一次,幂等性由调用方保证
    (手工路径靠状态机 APPROVED->POSTED;自动路径靠 source_type+source_id 去重)。
    """
    for line in voucher.lines.filter(is_deleted=False):
        balance, _ = AccountBalance.objects.get_or_create(
            account=line.account, fiscal_period=voucher.fiscal_period, defaults={'created_by': user}
        )
        balance.period_debit += line.debit_amount
        balance.period_credit += line.credit_amount
        balance.closing_debit = balance.opening_debit + balance.period_debit
        balance.closing_credit = balance.opening_credit + balance.period_credit
        balance.save()

    voucher.status = 'POSTED'
    voucher.posted_at = timezone.now()
    voucher.posted_by = user
    voucher.save()
    return voucher


# =====================
# Serializers
# =====================


class AccountCategorySerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_category_type_display', read_only=True)
    account_count = serializers.SerializerMethodField()

    class Meta:
        model = AccountCategory
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']

    def get_account_count(self, obj):
        return obj.accounts.filter(is_deleted=False).count()


class ChartOfAccountSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    parent_name = serializers.CharField(source='parent.name', read_only=True)
    balance_direction_display = serializers.CharField(source='get_balance_direction_display', read_only=True)
    children_count = serializers.SerializerMethodField()

    class Meta:
        model = ChartOfAccount
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'level']

    def get_children_count(self, obj):
        return obj.children.filter(is_deleted=False).count()


class FiscalPeriodSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    voucher_count = serializers.SerializerMethodField()

    class Meta:
        model = FiscalPeriod
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by', 'closed_at', 'closed_by']

    def get_voucher_count(self, obj):
        return obj.vouchers.filter(is_deleted=False).count()


class VoucherLineSerializer(serializers.ModelSerializer):
    account_code = serializers.CharField(source='account.code', read_only=True)
    account_name = serializers.CharField(source='account.name', read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)

    class Meta:
        model = VoucherLine
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']


class JournalVoucherSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    type_display = serializers.CharField(source='get_voucher_type_display', read_only=True)
    period_name = serializers.SerializerMethodField()
    lines = VoucherLineSerializer(many=True, read_only=True)
    is_balanced = serializers.BooleanField(read_only=True)
    reviewer_name = serializers.CharField(source='reviewer.get_full_name', read_only=True)

    class Meta:
        model = JournalVoucher
        fields = '__all__'
        read_only_fields = [
            'created_by',
            'updated_by',
            'voucher_no',
            'debit_total',
            'credit_total',
            'reviewer',
            'reviewed_at',
            'posted_at',
            'posted_by',
            'source_type',
            'source_id',
        ]

    def get_period_name(self, obj):
        return str(obj.fiscal_period)


class AccountBalanceSerializer(serializers.ModelSerializer):
    account_code = serializers.CharField(source='account.code', read_only=True)
    account_name = serializers.CharField(source='account.name', read_only=True)
    period_name = serializers.SerializerMethodField()

    class Meta:
        model = AccountBalance
        fields = '__all__'
        read_only_fields = ['created_by', 'updated_by']

    def get_period_name(self, obj):
        return str(obj.fiscal_period)


# =====================
# ViewSets
# =====================


class AccountCategoryViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    permission_module = 'finance'
    permission_resource = 'account_category'
    """科目类别管理"""
    queryset = AccountCategory.objects.filter(is_deleted=False)
    serializer_class = AccountCategorySerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['category_type']
    search_fields = ['name', 'code']


class ChartOfAccountViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    permission_module = 'finance'
    permission_resource = 'chart_of_account'
    """会计科目管理"""
    queryset = ChartOfAccount.objects.filter(is_deleted=False)
    serializer_class = ChartOfAccountSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['category', 'parent', 'level', 'is_detail', 'is_active']
    search_fields = ['code', 'name']
    ordering_fields = ['code', 'level']

    @action(detail=False, methods=['get'])
    def tree(self, request):
        """获取科目树"""
        accounts = self.get_queryset().filter(level=1)

        def build_tree(account):
            return {
                'id': account.id,
                'code': account.code,
                'name': account.name,
                'level': account.level,
                'is_detail': account.is_detail,
                'balance_direction': account.balance_direction,
                'children': [build_tree(c) for c in account.children.filter(is_deleted=False).order_by('code')],
            }

        return Response([build_tree(a) for a in accounts.order_by('code')])

    @action(detail=False, methods=['get'])
    def detail_accounts(self, request):
        """获取明细科目列表（用于选择）"""
        accounts = self.get_queryset().filter(is_detail=True, is_active=True).order_by('code')

        return Response(
            [{'id': a.id, 'code': a.code, 'name': a.name, 'full_name': f'{a.code} - {a.name}'} for a in accounts]
        )


class FiscalPeriodViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    permission_module = 'finance'
    permission_resource = 'fiscal_period'
    """会计期间管理"""
    queryset = FiscalPeriod.objects.filter(is_deleted=False)
    serializer_class = FiscalPeriodSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['year', 'status']
    ordering_fields = ['year', 'period']

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        """关闭期间,并把本期期末余额结转为下期期初余额。"""
        period = self.get_object()
        if period.status != 'OPEN':
            return Response({'error': '只有开放期间可以关闭'}, status=400)

        # 检查是否有未审核凭证
        pending_vouchers = period.vouchers.filter(status__in=['DRAFT', 'PENDING']).count()
        if pending_vouchers > 0:
            return Response({'error': f'有{pending_vouchers}张凭证未审核'}, status=400)

        with transaction.atomic():
            # 结转期末余额 -> 下期期初(否则下期 opening_* 恒为 0,试算平衡期初永远为 0)
            self._carry_forward_opening_balances(period, request.user)

            period.status = 'CLOSED'
            period.closed_at = timezone.now()
            period.closed_by = request.user
            period.save()

        return Response(self.get_serializer(period).data)

    @staticmethod
    def _next_period(period):
        """返回下一会计期间(1-12 循环,第 12 期跨年到次年第 1 期);不存在则返回 None。"""
        if period.period < 12:
            year, nxt = period.year, period.period + 1
        else:
            year, nxt = period.year + 1, 1
        return FiscalPeriod.objects.filter(year=year, period=nxt, is_deleted=False).first()

    @classmethod
    def _carry_forward_opening_balances(cls, period, user):
        """把本期各科目期末净额按余额方向结转为下期期初余额。

        期末净额 = 期初净额 +/- 本期发生净额,取号方向遵循科目 ``balance_direction``:
        - 借方科目:net = (期初借 - 期初贷) + (本期借 - 本期贷),net>=0 落借方,否则落贷方;
        - 贷方科目:net = (期初贷 - 期初借) + (本期贷 - 本期借),net>=0 落贷方,否则落借方。

        仅结转到已存在的下期(不凭空创建期间)。仅做科目余额结转,不做
        损益结转-留存收益的年末结账(属更大范围任务,列为遗留 residual)。
        """
        next_period = cls._next_period(period)
        if not next_period:
            return

        balances = AccountBalance.objects.filter(fiscal_period=period, is_deleted=False).select_related('account')

        for bal in balances:
            opening_dr = bal.opening_debit or Decimal('0')
            opening_cr = bal.opening_credit or Decimal('0')
            period_dr = bal.period_debit or Decimal('0')
            period_cr = bal.period_credit or Decimal('0')

            if bal.account.balance_direction == 'CREDIT':
                net = (opening_cr - opening_dr) + (period_cr - period_dr)
                next_open_dr = Decimal('0') if net >= 0 else -net
                next_open_cr = net if net >= 0 else Decimal('0')
            else:  # DEBIT(默认)
                net = (opening_dr - opening_cr) + (period_dr - period_cr)
                next_open_dr = net if net >= 0 else Decimal('0')
                next_open_cr = Decimal('0') if net >= 0 else -net

            nb, _ = AccountBalance.objects.get_or_create(
                account=bal.account,
                fiscal_period=next_period,
                defaults={'created_by': user},
            )
            nb.opening_debit = next_open_dr
            nb.opening_credit = next_open_cr
            nb.closing_debit = nb.opening_debit + (nb.period_debit or Decimal('0'))
            nb.closing_credit = nb.opening_credit + (nb.period_credit or Decimal('0'))
            nb.save()

    @action(detail=False, methods=['post'])
    def generate_year(self, request):
        """生成年度期间"""
        year = request.data.get('year', date.today().year)

        created = 0
        for month in range(1, 13):
            start = date(year, month, 1)
            if month == 12:
                end = date(year, 12, 31)
            else:
                end = date(year, month + 1, 1) - timedelta(days=1)

            _, is_created = FiscalPeriod.objects.get_or_create(
                year=year, period=month, defaults={'start_date': start, 'end_date': end, 'created_by': request.user}
            )
            if is_created:
                created += 1

        return Response({'success': True, 'year': year, 'created': created})


class JournalVoucherViewSet(PermissionMixin, SoftDeleteMixin, UserTrackingMixin, viewsets.ModelViewSet):
    permission_module = 'finance'
    permission_resource = 'journal_voucher'
    """记账凭证管理"""
    queryset = JournalVoucher.objects.filter(is_deleted=False)
    serializer_class = JournalVoucherSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['fiscal_period', 'voucher_type', 'status']
    search_fields = ['voucher_no', 'summary']
    ordering_fields = ['voucher_date', 'created_at']

    @action(detail=True, methods=['post'])
    def add_line(self, request, pk=None):
        """添加分录"""
        voucher = self.get_object()
        if voucher.status != 'DRAFT':
            return Response({'error': '只有草稿凭证可以添加分录'}, status=400)

        max_line = voucher.lines.aggregate(max_no=models.Max('line_no'))['max_no'] or 0

        line = VoucherLine.objects.create(
            voucher=voucher,
            line_no=max_line + 1,
            account_id=request.data.get('account_id'),
            summary=request.data.get('summary', ''),
            debit_amount=request.data.get('debit_amount', 0),
            credit_amount=request.data.get('credit_amount', 0),
            customer_id=request.data.get('customer_id'),
            supplier_id=request.data.get('supplier_id'),
            project_id=request.data.get('project_id'),
            department_id=request.data.get('department_id'),
            created_by=request.user,
        )

        return Response(VoucherLineSerializer(line).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """提交审核"""
        voucher = self.get_object()
        if voucher.status != 'DRAFT':
            return Response({'error': '只有草稿凭证可以提交'}, status=400)

        if not voucher.is_balanced:
            return Response({'error': '借贷不平衡，无法提交'}, status=400)

        voucher.status = 'PENDING'
        voucher.save()

        return Response(self.get_serializer(voucher).data)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """审核凭证"""
        voucher = self.get_object()
        if voucher.status != 'PENDING':
            return Response({'error': '只有待审核凭证可以审核'}, status=400)

        if not voucher.is_balanced or voucher.debit_total == 0:
            return Response({'error': '借贷不平衡或凭证金额为零，无法审核'}, status=400)

        voucher.status = 'APPROVED'
        voucher.reviewer = request.user
        voucher.reviewed_at = timezone.now()
        voucher.save()

        return Response(self.get_serializer(voucher).data)

    @action(detail=True, methods=['post'])
    def post_voucher(self, request, pk=None):
        """过账"""
        voucher = self.get_object()
        if voucher.status != 'APPROVED':
            return Response({'error': '只有已审核凭证可以过账'}, status=400)

        if not voucher.is_balanced or voucher.debit_total == 0:
            return Response({'error': '借贷不平衡或凭证金额为零，无法过账'}, status=400)

        if voucher.fiscal_period.status != 'OPEN':
            return Response({'error': '会计期间未开放，无法过账'}, status=400)

        # 余额结转 + 状态落地抽取到模块级 post_voucher_to_ledger,与自动过账引擎共用同一实现。
        with transaction.atomic():
            post_voucher_to_ledger(voucher, request.user)

        return Response(self.get_serializer(voucher).data)


class AccountBalanceViewSet(PermissionMixin, viewsets.ReadOnlyModelViewSet):
    permission_module = 'finance'
    permission_resource = 'account_balance'
    """科目余额查询"""
    queryset = AccountBalance.objects.filter(is_deleted=False)
    serializer_class = AccountBalanceSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['account', 'fiscal_period']

    @action(detail=False, methods=['get'])
    def trial_balance(self, request):
        """试算平衡表"""
        period_id = request.query_params.get('period_id')

        if not period_id:
            return Response({'error': '请指定会计期间'}, status=400)

        balances = (
            AccountBalance.objects.filter(fiscal_period_id=period_id)
            .select_related('account')
            .order_by('account__code')
        )

        data = []
        totals = {
            'opening_debit': Decimal('0'),
            'opening_credit': Decimal('0'),
            'period_debit': Decimal('0'),
            'period_credit': Decimal('0'),
            'closing_debit': Decimal('0'),
            'closing_credit': Decimal('0'),
        }

        for b in balances:
            data.append(
                {
                    'account_code': b.account.code,
                    'account_name': b.account.name,
                    'opening_debit': float(b.opening_debit),
                    'opening_credit': float(b.opening_credit),
                    'period_debit': float(b.period_debit),
                    'period_credit': float(b.period_credit),
                    'closing_debit': float(b.closing_debit),
                    'closing_credit': float(b.closing_credit),
                }
            )

            for key in totals:
                totals[key] += getattr(b, key)

        return Response(
            {
                'balances': data,
                'totals': {k: float(v) for k, v in totals.items()},
                'is_balanced': totals['period_debit'] == totals['period_credit'],
            }
        )


def _jsonify(value):
    """把报表 service 返回的嵌套 dict/list 里的 Decimal 递归转 float,便于 JSON 序列化。

    报表 service(financial_statements)按规范返回 Decimal,展示层在此统一转 float,
    与 trial_balance 现有输出口径一致。
    """
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {k: _jsonify(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonify(v) for v in value]
    return value


class FinancialStatementViewSet(PermissionMixin, viewsets.ViewSet):
    permission_module = 'finance'
    permission_resource = 'report'
    """三大财务报表 + 科目表种子。

    只读报表(GET):
      - ``balance-sheet``   资产负债表(?period_id=)
      - ``income-statement``利润表(?period_id= 或 ?start_date=&end_date=)
      - ``cash-flow``       现金流量表(?start_date=&end_date=)
    管理动作(POST,仅超管):
      - ``seed-accounts``   幂等初始化标准科目表(科目类别 + 8 个常用一级科目)。

    权限:``finance:report:*``,并受 MODULE_MENU_MAP 的 'finance' 菜单级兜底。
    试算平衡表(trial-balance)已由 AccountBalanceViewSet 提供,此处不重复。
    """
    permission_classes = [IsAuthenticated]

    def list(self, request):
        """报表清单(根路由),便于前端发现可用报表。"""
        return Response(
            {
                'reports': ['balance-sheet', 'income-statement', 'cash-flow'],
                'detail': '总账三大报表:资产负债表 / 利润表 / 现金流量表',
            }
        )

    def _get_period(self, period_id):
        return FiscalPeriod.objects.filter(pk=period_id, is_deleted=False).first()

    @action(detail=False, methods=['get'], url_path='balance-sheet')
    def balance_sheet(self, request):
        """资产负债表:资产 = 负债 + 所有者权益(未结转损益并入权益)。"""
        from apps.finance.financial_statements import balance_sheet

        period_id = request.query_params.get('period_id')
        if not period_id:
            return Response({'error': '请指定会计期间 period_id'}, status=400)
        period = self._get_period(period_id)
        if not period:
            return Response({'error': '会计期间不存在'}, status=404)
        return Response(_jsonify(balance_sheet(period)))

    @action(detail=False, methods=['get'], url_path='income-statement')
    def income_statement(self, request):
        """利润表:收入 - 费用 = 净利润。支持按会计期间或日期区间。"""
        from apps.finance.financial_statements import income_statement

        period_id = request.query_params.get('period_id')
        start = request.query_params.get('start_date')
        end = request.query_params.get('end_date')
        if period_id:
            period = self._get_period(period_id)
            if not period:
                return Response({'error': '会计期间不存在'}, status=404)
            return Response(_jsonify(income_statement(period=period)))
        if start and end:
            return Response(_jsonify(income_statement(start_date=start, end_date=end)))
        return Response({'error': '请指定 period_id 或 start_date + end_date'}, status=400)

    @action(detail=False, methods=['get'], url_path='cash-flow')
    def cash_flow(self, request):
        """现金流量表(简化):现金/银行存款科目在区间内的净变动,全部归经营活动。"""
        from apps.finance.financial_statements import cash_flow

        start = request.query_params.get('start_date')
        end = request.query_params.get('end_date')
        if not (start and end):
            return Response({'error': '请指定 start_date 和 end_date'}, status=400)
        return Response(_jsonify(cash_flow(start, end)))

    @action(detail=False, methods=['post'], url_path='seed-accounts')
    def seed_accounts(self, request):
        """初始化标准科目表(幂等)。仅超管可执行。"""
        if not (request.user and request.user.is_superuser):
            return Response({'error': '仅系统管理员可初始化科目表'}, status=403)
        from apps.finance.posting import seed_standard_accounts

        result = seed_standard_accounts(user=request.user)
        return Response({'success': True, **result})
