"""
Finance models for expenses, receivables, and payables.

注意: 使用字符串引用替代直接导入以避免循环依赖
"""
from django.db import models, transaction
from apps.core.models import BaseModel


class Currency(BaseModel):
    """Currency master data"""
    code = models.CharField(max_length=3, unique=True, verbose_name='货币代码')  # USD, EUR, CNY
    name = models.CharField(max_length=50, verbose_name='货币名称')
    symbol = models.CharField(max_length=5, verbose_name='货币符号')  # $, €, ¥
    exchange_rate = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        default=1.0,
        verbose_name='汇率（相对于基准货币）'
    )
    is_base_currency = models.BooleanField(default=False, verbose_name='是否为基准货币')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    
    class Meta:
        db_table = 'currency'
        verbose_name = '货币'
        verbose_name_plural = verbose_name
        ordering = ['code']
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class ExchangeRateHistory(BaseModel):
    """Exchange rate history for tracking"""
    currency = models.ForeignKey(
        Currency,
        on_delete=models.CASCADE,
        related_name='rate_history',
        verbose_name='货币'
    )
    exchange_rate = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        verbose_name='汇率'
    )
    effective_date = models.DateField(verbose_name='生效日期', db_index=True)
    
    class Meta:
        db_table = 'exchange_rate_history'
        verbose_name = '汇率历史'
        verbose_name_plural = verbose_name
        ordering = ['-effective_date']
        indexes = [
            models.Index(fields=['currency', '-effective_date']),
        ]
    
    def __str__(self):
        return f"{self.currency.code} - {self.exchange_rate} ({self.effective_date})"


class Expense(BaseModel):
    """
    Expense records for project and department expenses.
    """
    CATEGORY_CHOICES = [
        ('TRAVEL', '差旅费'),
        ('MEAL', '餐饮费'),
        ('OFFICE', '办公用品'),
        ('COMMUNICATION', '通讯费'),
        ('TRAINING', '培训费'),
        ('OTHER', '其他'),
    ]
    
    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('SUBMITTED', '已提交'),
        ('APPROVED', '已批准'),
        ('REJECTED', '已拒绝'),
        ('PAID', '已支付'),
    ]
    
    expense_no = models.CharField(max_length=50, unique=True, verbose_name='费用编号')
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='expenses',
        verbose_name='项目'
    )
    department = models.ForeignKey(
        'accounts.Department',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='expenses',
        verbose_name='部门'
    )
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.PROTECT,
        related_name='expenses',
        verbose_name='申请人'
    )
    expense_date = models.DateField(verbose_name='费用日期')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, verbose_name='费用类别')
    
    # Multi-currency support
    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name='expenses',
        verbose_name='货币',
        null=True
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='金额')
    exchange_rate = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        default=1.0,
        verbose_name='汇率（记录时）'
    )
    base_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name='基准货币金额',
        null=True,
        blank=True
    )
    
    description = models.TextField(verbose_name='费用说明')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', verbose_name='状态')
    reimbursement_date = models.DateField(null=True, blank=True, verbose_name='报销日期')
    
    class Meta:
        db_table = 'expense'
        verbose_name = '费用'
        verbose_name_plural = verbose_name
        ordering = ['-expense_date']
    
    def __str__(self):
        return self.expense_no
    
    def save(self, *args, **kwargs):
        # Auto-generate expense_no
        if not self.expense_no:
            from django.utils import timezone
            date_str = timezone.now().strftime('%Y%m%d')
            last_expense = Expense.objects.filter(expense_no__startswith=f'EXP{date_str}').order_by('-expense_no').first()
            if last_expense:
                last_seq = int(last_expense.expense_no[-4:])
                new_seq = last_seq + 1
            else:
                new_seq = 1
            self.expense_no = f'EXP{date_str}{new_seq:04d}'
        
        # Calculate base_amount
        if self.currency and self.amount:
            self.base_amount = self.amount * self.exchange_rate
        
        super().save(*args, **kwargs)


class AccountReceivable(BaseModel):
    """
    Accounts receivable from sales orders.
    """
    STATUS_CHOICES = [
        ('PENDING', '待收款'),
        ('PARTIAL', '部分收款'),
        ('PAID', '已收款'),
        ('OVERDUE', '逾期'),
        ('CANCELLED', '已取消'),
    ]
    
    ar_no = models.CharField(max_length=50, unique=True, verbose_name='应收单号')
    customer = models.ForeignKey(
        'masterdata.Customer',
        on_delete=models.PROTECT,
        related_name='receivables',
        verbose_name='客户'
    )
    so = models.ForeignKey(
        'sales.SalesOrder',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='receivables',
        verbose_name='销售订单'
    )
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='receivables',
        verbose_name='项目'
    )
    invoice_no = models.CharField(max_length=50, null=True, blank=True, verbose_name='发票号')
    invoice_date = models.DateField(verbose_name='发票日期')
    
    # Multi-currency support
    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name='receivables',
        verbose_name='货币',
        null=True
    )
    amount_due = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='应收金额')
    amount_paid = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='已收金额')
    exchange_rate = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        default=1.0,
        verbose_name='汇率'
    )
    
    due_date = models.DateField(verbose_name='到期日')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', verbose_name='状态')
    
    class Meta:
        db_table = 'account_receivable'
        verbose_name = '应收账款'
        verbose_name_plural = verbose_name
        ordering = ['-invoice_date']
    
    def __str__(self):
        return self.ar_no
    
    @property
    def amount_remaining(self):
        return self.amount_due - self.amount_paid
    
    def save(self, *args, **kwargs):
        # Auto-generate ar_no
        if not self.ar_no:
            from django.utils import timezone
            date_str = timezone.now().strftime('%Y%m%d')
            last_ar = AccountReceivable.objects.filter(ar_no__startswith=f'AR{date_str}').order_by('-ar_no').first()
            if last_ar:
                last_seq = int(last_ar.ar_no[-4:])
                new_seq = last_seq + 1
            else:
                new_seq = 1
            self.ar_no = f'AR{date_str}{new_seq:04d}'
        
        # Update status based on payment
        if self.amount_paid >= self.amount_due:
            self.status = 'PAID'
        elif self.amount_paid > 0:
            self.status = 'PARTIAL'
        
        super().save(*args, **kwargs)


class AccountPayable(BaseModel):
    """
    Accounts payable from purchase orders.
    """
    STATUS_CHOICES = [
        ('PENDING', '待付款'),
        ('PARTIAL', '部分付款'),
        ('PAID', '已付款'),
        ('OVERDUE', '逾期'),
        ('CANCELLED', '已取消'),
    ]
    
    ap_no = models.CharField(max_length=50, unique=True, verbose_name='应付单号')
    supplier = models.ForeignKey(
        'masterdata.Supplier',
        on_delete=models.PROTECT,
        related_name='payables',
        verbose_name='供应商'
    )
    po = models.ForeignKey(
        'purchase.PurchaseOrder',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='payables',
        verbose_name='采购订单'
    )
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='payables',
        verbose_name='项目'
    )
    invoice_no = models.CharField(max_length=50, null=True, blank=True, verbose_name='发票号')
    invoice_date = models.DateField(verbose_name='发票日期')
    
    # Multi-currency support
    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name='payables',
        verbose_name='货币',
        null=True
    )
    amount_due = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='应付金额')
    amount_paid = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='已付金额')
    exchange_rate = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        default=1.0,
        verbose_name='汇率'
    )
    
    due_date = models.DateField(verbose_name='到期日')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', verbose_name='状态')
    
    class Meta:
        db_table = 'account_payable'
        verbose_name = '应付账款'
        verbose_name_plural = verbose_name
        ordering = ['-invoice_date']
    
    def __str__(self):
        return self.ap_no
    
    @property
    def amount_remaining(self):
        return self.amount_due - self.amount_paid
    
    def save(self, *args, **kwargs):
        # Auto-generate ap_no
        if not self.ap_no:
            from django.utils import timezone
            date_str = timezone.now().strftime('%Y%m%d')
            last_ap = AccountPayable.objects.filter(ap_no__startswith=f'AP{date_str}').order_by('-ap_no').first()
            if last_ap:
                last_seq = int(last_ap.ap_no[-4:])
                new_seq = last_seq + 1
            else:
                new_seq = 1
            self.ap_no = f'AP{date_str}{new_seq:04d}'
        
        # Update status based on payment
        if self.amount_paid >= self.amount_due:
            self.status = 'PAID'
        elif self.amount_paid > 0:
            self.status = 'PARTIAL'
        
        super().save(*args, **kwargs)


class Payment(BaseModel):
    """Payment records for AR/AP"""
    PAYMENT_TYPE_CHOICES = [
        ('AR', '应收款'),
        ('AP', '应付款'),
        ('PAYABLE', '待付款项'),
    ]
    
    PAYMENT_METHOD_CHOICES = [
        ('CASH', '现金'),
        ('BANK_TRANSFER', '银行转账'),
        ('CREDIT_CARD', '信用卡'),
        ('CHECK', '支票'),
        ('OTHER', '其他'),
    ]
    
    payment_no = models.CharField(max_length=50, unique=True, verbose_name='付款单号')
    payment_type = models.CharField(max_length=10, choices=PAYMENT_TYPE_CHOICES, verbose_name='付款类型')
    ar = models.ForeignKey(
        AccountReceivable,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='payments',
        verbose_name='应收账款'
    )
    ap = models.ForeignKey(
        AccountPayable,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='payments',
        verbose_name='应付账款'
    )
    payable_item = models.ForeignKey(
        'finance.PayableItem',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='payments',
        verbose_name='待付款项',
    )
    payment_date = models.DateField(verbose_name='付款日期')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, verbose_name='付款方式')
    
    # Multi-currency support
    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name='payments',
        verbose_name='货币',
        null=True
    )
    amount = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='付款金额')
    exchange_rate = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        default=1.0,
        verbose_name='汇率'
    )
    
    notes = models.TextField(null=True, blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'payment'
        verbose_name = '付款记录'
        verbose_name_plural = verbose_name
        ordering = ['-payment_date']
    
    def __str__(self):
        return self.payment_no
    
    def save(self, *args, **kwargs):
        is_new = self._state.adding
        # Auto-generate payment_no
        if not self.payment_no:
            from django.utils import timezone
            date_str = timezone.now().strftime('%Y%m%d')
            last_payment = Payment.objects.filter(payment_no__startswith=f'PAY{date_str}').order_by('-payment_no').first()
            if last_payment:
                last_seq = int(last_payment.payment_no[-4:])
                new_seq = last_seq + 1
            else:
                new_seq = 1
            self.payment_no = f'PAY{date_str}{new_seq:04d}'

        super().save(*args, **kwargs)

        if is_new:
            from django.db.models import F
            if self.ar_id:
                AccountReceivable.objects.filter(pk=self.ar_id).update(
                    amount_paid=F('amount_paid') + self.amount
                )
            elif self.ap_id:
                AccountPayable.objects.filter(pk=self.ap_id).update(
                    amount_paid=F('amount_paid') + self.amount
                )
            elif self.payable_item_id:
                from apps.finance.payable_models import PayableItem
                with transaction.atomic():
                    item = PayableItem.objects.select_for_update().get(pk=self.payable_item_id)
                    item.amount_paid = item.amount_paid + self.amount
                    item.recalc_status()
                    item.save(update_fields=['amount_paid', 'status', 'updated_at'])


class PaymentSchedule(BaseModel):
    """
    Payment schedule for tracking payment milestones based on contract terms.
    用于跟踪销售订单/合同的付款计划和进度。
    """
    MILESTONE_TYPE_CHOICES = [
        ('PREPAY', '预付款'),
        ('ON_DELIVERY', '发货款'),
        ('ON_ACCEPTANCE', '验收款'),
        ('WARRANTY', '质保金'),
        ('PROGRESS', '进度款'),
        ('FINAL', '尾款'),
        ('CUSTOM', '自定义'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', '待收款'),
        ('PARTIAL', '部分收款'),
        ('PAID', '已收款'),
        ('OVERDUE', '已逾期'),
        ('CANCELLED', '已取消'),
    ]
    
    REMINDER_STATUS_CHOICES = [
        ('NONE', '无需提醒'),
        ('PENDING', '待提醒'),
        ('REMINDED', '已提醒'),
        ('COLLECTED', '已收款'),
    ]
    
    schedule_no = models.CharField(max_length=50, unique=True, verbose_name='计划编号')
    
    # 关联销售订单
    sales_order = models.ForeignKey(
        'sales.SalesOrder',
        on_delete=models.CASCADE,
        related_name='payment_schedules',
        verbose_name='销售订单'
    )
    
    # 关联项目（可选，从销售订单继承）
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payment_schedules',
        verbose_name='项目'
    )
    
    # 里程碑信息
    milestone_type = models.CharField(
        max_length=20,
        choices=MILESTONE_TYPE_CHOICES,
        default='CUSTOM',
        verbose_name='付款节点类型'
    )
    milestone_name = models.CharField(max_length=100, verbose_name='付款节点名称')
    milestone_order = models.IntegerField(default=1, verbose_name='节点顺序')
    
    # 金额信息
    percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name='付款比例(%)'
    )
    amount_due = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='应收金额')
    amount_paid = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='已收金额')
    
    # 日期信息
    due_date = models.DateField(verbose_name='计划收款日期')
    actual_paid_date = models.DateField(null=True, blank=True, verbose_name='实际收款日期')
    
    # 状态
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
        verbose_name='状态'
    )
    
    # 提醒相关
    reminder_status = models.CharField(
        max_length=20,
        choices=REMINDER_STATUS_CHOICES,
        default='PENDING',
        verbose_name='提醒状态'
    )
    reminder_days_before = models.IntegerField(default=7, verbose_name='提前提醒天数')
    last_reminded_at = models.DateTimeField(null=True, blank=True, verbose_name='最后提醒时间')
    
    # 关联应收账款（匹配后设置）
    account_receivable = models.ForeignKey(
        'AccountReceivable',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payment_schedules',
        verbose_name='关联应收账款'
    )
    
    # 关联银行流水（匹配后设置）
    # Note: Use string reference with app label since BankStatement is in same app
    bank_statements = models.ManyToManyField(
        'finance.BankStatement',
        blank=True,
        related_name='payment_schedules',
        verbose_name='关联银行流水'
    )
    
    notes = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'payment_schedule'
        verbose_name = '付款计划'
        verbose_name_plural = verbose_name
        ordering = ['sales_order', 'milestone_order']
        indexes = [
            models.Index(fields=['sales_order', 'milestone_order']),
            models.Index(fields=['status', 'due_date']),
            models.Index(fields=['reminder_status', 'due_date']),
        ]
    
    def __str__(self):
        return f"{self.schedule_no} - {self.milestone_name}"
    
    @property
    def amount_remaining(self):
        """剩余应收金额"""
        return self.amount_due - self.amount_paid
    
    @property
    def payment_progress(self):
        """付款进度百分比"""
        if self.amount_due == 0:
            return 100
        return round(float(self.amount_paid) / float(self.amount_due) * 100, 2)
    
    @property
    def is_overdue(self):
        """是否逾期"""
        from django.utils import timezone
        return self.status == 'PENDING' and self.due_date < timezone.now().date()
    
    @property
    def days_until_due(self):
        """距离到期天数（负数表示已逾期）"""
        from django.utils import timezone
        return (self.due_date - timezone.now().date()).days
    
    def save(self, *args, **kwargs):
        # 自动生成编号
        if not self.schedule_no:
            from django.utils import timezone
            date_str = timezone.now().strftime('%Y%m%d')
            last = PaymentSchedule.objects.filter(schedule_no__startswith=f'PS{date_str}').order_by('-schedule_no').first()
            if last:
                last_seq = int(last.schedule_no[-4:])
                new_seq = last_seq + 1
            else:
                new_seq = 1
            self.schedule_no = f'PS{date_str}{new_seq:04d}'
        
        # 从销售订单继承项目
        if not self.project and self.sales_order and self.sales_order.project:
            self.project = self.sales_order.project
        
        # 更新状态
        if self.amount_paid >= self.amount_due:
            self.status = 'PAID'
            self.reminder_status = 'COLLECTED'
        elif self.amount_paid > 0:
            self.status = 'PARTIAL'
        elif self.is_overdue:
            self.status = 'OVERDUE'
        
        super().save(*args, **kwargs)
    
    @classmethod
    def generate_from_sales_order(cls, sales_order):
        """
        根据销售订单的付款条款自动生成付款计划。
        """
        from django.utils import timezone
        from decimal import Decimal
        from datetime import timedelta
        
        # 付款条款到付款计划的映射
        PAYMENT_TERMS_MAP = {
            'FULL_PREPAY': [
                {'type': 'PREPAY', 'name': '全款预付', 'percentage': Decimal('100'), 'days_offset': 0}
            ],
            'COD': [
                {'type': 'ON_DELIVERY', 'name': '货到付款', 'percentage': Decimal('100'), 'days_offset': 0}
            ],
            'NET30': [
                {'type': 'FINAL', 'name': '月结30天', 'percentage': Decimal('100'), 'days_offset': 30}
            ],
            'NET60': [
                {'type': 'FINAL', 'name': '月结60天', 'percentage': Decimal('100'), 'days_offset': 60}
            ],
            'NET90': [
                {'type': 'FINAL', 'name': '月结90天', 'percentage': Decimal('100'), 'days_offset': 90}
            ],
            'M_30_70': [
                {'type': 'PREPAY', 'name': '30%预付款', 'percentage': Decimal('30'), 'days_offset': 0},
                {'type': 'ON_DELIVERY', 'name': '70%发货款', 'percentage': Decimal('70'), 'days_offset': 0}
            ],
            'M_30_30_40': [
                {'type': 'PREPAY', 'name': '30%预付款', 'percentage': Decimal('30'), 'days_offset': 0},
                {'type': 'ON_DELIVERY', 'name': '30%发货款', 'percentage': Decimal('30'), 'days_offset': 0},
                {'type': 'ON_ACCEPTANCE', 'name': '40%验收款', 'percentage': Decimal('40'), 'days_offset': 30}
            ],
            'M_30_30_30_10': [
                {'type': 'PREPAY', 'name': '30%预付款', 'percentage': Decimal('30'), 'days_offset': 0},
                {'type': 'ON_DELIVERY', 'name': '30%发货款', 'percentage': Decimal('30'), 'days_offset': 0},
                {'type': 'ON_ACCEPTANCE', 'name': '30%验收款', 'percentage': Decimal('30'), 'days_offset': 30},
                {'type': 'WARRANTY', 'name': '10%质保金', 'percentage': Decimal('10'), 'days_offset': 365}
            ],
            'M_30_60_10': [
                {'type': 'PREPAY', 'name': '30%预付款', 'percentage': Decimal('30'), 'days_offset': 0},
                {'type': 'ON_ACCEPTANCE', 'name': '60%验收款', 'percentage': Decimal('60'), 'days_offset': 30},
                {'type': 'WARRANTY', 'name': '10%质保金', 'percentage': Decimal('10'), 'days_offset': 365}
            ],
            'M_50_40_10': [
                {'type': 'PREPAY', 'name': '50%预付款', 'percentage': Decimal('50'), 'days_offset': 0},
                {'type': 'ON_ACCEPTANCE', 'name': '40%验收款', 'percentage': Decimal('40'), 'days_offset': 30},
                {'type': 'WARRANTY', 'name': '10%质保金', 'percentage': Decimal('10'), 'days_offset': 365}
            ],
            'M_40_50_10': [
                {'type': 'PREPAY', 'name': '40%预付款', 'percentage': Decimal('40'), 'days_offset': 0},
                {'type': 'ON_ACCEPTANCE', 'name': '50%验收款', 'percentage': Decimal('50'), 'days_offset': 30},
                {'type': 'WARRANTY', 'name': '10%质保金', 'percentage': Decimal('10'), 'days_offset': 365}
            ],
            'M_20_70_10': [
                {'type': 'PREPAY', 'name': '20%预付款', 'percentage': Decimal('20'), 'days_offset': 0},
                {'type': 'ON_ACCEPTANCE', 'name': '70%验收款', 'percentage': Decimal('70'), 'days_offset': 30},
                {'type': 'WARRANTY', 'name': '10%质保金', 'percentage': Decimal('10'), 'days_offset': 365}
            ],
        }
        
        # 软删除旧的付款计划
        from django.utils import timezone
        cls.objects.filter(sales_order=sales_order, is_deleted=False).update(
            is_deleted=True, deleted_at=timezone.now()
        )
        
        # 获取付款条款
        payment_terms = sales_order.payment_terms
        milestones = PAYMENT_TERMS_MAP.get(payment_terms, [])
        
        # 如果是自定义或其他，不自动生成
        if not milestones:
            return []
        
        # 基准日期（订单日期或交货日期）
        base_date = sales_order.order_date or timezone.now().date()
        delivery_date = sales_order.delivery_date or base_date
        
        schedules = []
        for i, milestone in enumerate(milestones, 1):
            # 计算应收金额
            amount = sales_order.total_with_tax * milestone['percentage'] / Decimal('100')
            
            # 计算到期日期
            if milestone['type'] == 'PREPAY':
                due_date = base_date + timedelta(days=milestone['days_offset'])
            elif milestone['type'] == 'ON_DELIVERY':
                due_date = delivery_date
            elif milestone['type'] in ['ON_ACCEPTANCE', 'FINAL']:
                due_date = delivery_date + timedelta(days=milestone['days_offset'])
            elif milestone['type'] == 'WARRANTY':
                due_date = delivery_date + timedelta(days=milestone['days_offset'])
            else:
                due_date = base_date + timedelta(days=milestone['days_offset'])
            
            schedule = cls.objects.create(
                sales_order=sales_order,
                project=sales_order.project,
                milestone_type=milestone['type'],
                milestone_name=milestone['name'],
                milestone_order=i,
                percentage=milestone['percentage'],
                amount_due=amount,
                due_date=due_date,
                reminder_days_before=7 if milestone['type'] != 'WARRANTY' else 30
            )
            schedules.append(schedule)
        
        return schedules


class PurchasePaymentSchedule(BaseModel):
    """
    Payment schedule for tracking payment milestones based on purchase contract terms.
    用于跟踪采购订单/合同的付款计划和进度。
    """
    MILESTONE_TYPE_CHOICES = [
        ('PREPAY', '预付款'),
        ('ON_DELIVERY', '到货款'),
        ('ON_INSPECTION', '验收款'),
        ('FINAL', '尾款'),
        ('PROGRESS', '进度款'),
        ('CUSTOM', '自定义'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', '待付款'),
        ('PARTIAL', '部分付款'),
        ('PAID', '已付款'),
        ('OVERDUE', '已逾期'),
        ('CANCELLED', '已取消'),
    ]
    
    REMINDER_STATUS_CHOICES = [
        ('NONE', '无需提醒'),
        ('PENDING', '待提醒'),
        ('REMINDED', '已提醒'),
        ('PAID', '已付款'),
    ]
    
    schedule_no = models.CharField(max_length=50, unique=True, verbose_name='计划编号')
    
    # 关联采购订单
    purchase_order = models.ForeignKey(
        'purchase.PurchaseOrder',
        on_delete=models.CASCADE,
        related_name='payment_schedules',
        verbose_name='采购订单'
    )
    
    # 关联项目（可选，从采购订单继承）
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='purchase_payment_schedules',
        verbose_name='项目'
    )
    
    # 里程碑信息
    milestone_type = models.CharField(
        max_length=20,
        choices=MILESTONE_TYPE_CHOICES,
        default='CUSTOM',
        verbose_name='付款节点类型'
    )
    milestone_name = models.CharField(max_length=100, verbose_name='付款节点名称')
    milestone_order = models.IntegerField(default=1, verbose_name='节点顺序')
    
    # 金额信息
    percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name='付款比例(%)'
    )
    amount_due = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='应付金额')
    amount_paid = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='已付金额')
    
    # 日期信息
    due_date = models.DateField(verbose_name='计划付款日期')
    actual_paid_date = models.DateField(null=True, blank=True, verbose_name='实际付款日期')
    
    # 状态
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
        verbose_name='状态'
    )
    
    # 提醒相关
    reminder_status = models.CharField(
        max_length=20,
        choices=REMINDER_STATUS_CHOICES,
        default='PENDING',
        verbose_name='提醒状态'
    )
    reminder_days_before = models.IntegerField(default=3, verbose_name='提前提醒天数')
    last_reminded_at = models.DateTimeField(null=True, blank=True, verbose_name='最后提醒时间')
    
    # 关联应付账款（匹配后设置）
    account_payable = models.ForeignKey(
        'AccountPayable',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payment_schedules',
        verbose_name='关联应付账款'
    )
    
    # 关联银行流水（匹配后设置）
    bank_statements = models.ManyToManyField(
        'finance.BankStatement',
        blank=True,
        related_name='purchase_payment_schedules',
        verbose_name='关联银行流水'
    )
    
    notes = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'purchase_payment_schedule'
        verbose_name = '采购付款计划'
        verbose_name_plural = verbose_name
        ordering = ['purchase_order', 'milestone_order']
        indexes = [
            models.Index(fields=['purchase_order', 'milestone_order']),
            models.Index(fields=['status', 'due_date']),
            models.Index(fields=['reminder_status', 'due_date']),
        ]
    
    def __str__(self):
        return f"{self.schedule_no} - {self.milestone_name}"
    
    @property
    def amount_remaining(self):
        """剩余应付金额"""
        return self.amount_due - self.amount_paid
    
    @property
    def payment_progress(self):
        """付款进度百分比"""
        if self.amount_due == 0:
            return 100
        return round(float(self.amount_paid) / float(self.amount_due) * 100, 2)
    
    @property
    def is_overdue(self):
        """是否逾期"""
        from django.utils import timezone
        return self.status in ['PENDING', 'PARTIAL'] and self.due_date < timezone.now().date()
    
    @property
    def days_until_due(self):
        """距离到期天数（负数表示已逾期）"""
        from django.utils import timezone
        return (self.due_date - timezone.now().date()).days
    
    def save(self, *args, **kwargs):
        # 自动生成编号
        if not self.schedule_no:
            from django.utils import timezone
            date_str = timezone.now().strftime('%Y%m%d')
            last = PurchasePaymentSchedule.objects.filter(schedule_no__startswith=f'PPS{date_str}').order_by('-schedule_no').first()
            if last:
                last_seq = int(last.schedule_no[-4:])
                new_seq = last_seq + 1
            else:
                new_seq = 1
            self.schedule_no = f'PPS{date_str}{new_seq:04d}'
        
        # 从采购订单继承项目
        if not self.project and self.purchase_order and self.purchase_order.project:
            self.project = self.purchase_order.project
        
        # 更新状态
        if self.amount_paid >= self.amount_due:
            self.status = 'PAID'
            self.reminder_status = 'PAID'
        elif self.amount_paid > 0:
            self.status = 'PARTIAL'
        elif self.is_overdue:
            self.status = 'OVERDUE'
        
        super().save(*args, **kwargs)
    
    @classmethod
    def generate_from_purchase_order(cls, purchase_order):
        """
        根据采购订单的付款条款自动生成付款计划。
        """
        from django.utils import timezone
        from decimal import Decimal
        from datetime import timedelta
        
        # 付款条款到付款计划的映射
        PAYMENT_TERMS_MAP = {
            'PREPAY': [
                {'type': 'PREPAY', 'name': '全款预付', 'percentage': Decimal('100'), 'days_offset': 0}
            ],
            'COD': [
                {'type': 'ON_DELIVERY', 'name': '货到付款', 'percentage': Decimal('100'), 'days_offset': 0}
            ],
            'NET15': [
                {'type': 'FINAL', 'name': '月结15天', 'percentage': Decimal('100'), 'days_offset': 15}
            ],
            'NET30': [
                {'type': 'FINAL', 'name': '月结30天', 'percentage': Decimal('100'), 'days_offset': 30}
            ],
            'NET45': [
                {'type': 'FINAL', 'name': '月结45天', 'percentage': Decimal('100'), 'days_offset': 45}
            ],
            'NET60': [
                {'type': 'FINAL', 'name': '月结60天', 'percentage': Decimal('100'), 'days_offset': 60}
            ],
            'NET90': [
                {'type': 'FINAL', 'name': '月结90天', 'percentage': Decimal('100'), 'days_offset': 90}
            ],
            'NET120': [
                {'type': 'FINAL', 'name': '月结120天', 'percentage': Decimal('100'), 'days_offset': 120}
            ],
        }
        
        # 软删除旧的付款计划
        from django.utils import timezone
        cls.objects.filter(purchase_order=purchase_order, is_deleted=False).update(
            is_deleted=True, deleted_at=timezone.now()
        )
        
        # 获取付款条款
        payment_terms = purchase_order.payment_terms
        milestones = PAYMENT_TERMS_MAP.get(payment_terms, [])
        
        # 如果是分期或其他，不自动生成
        if not milestones:
            return []
        
        # 基准日期（订单日期或交货日期）
        base_date = purchase_order.order_date or timezone.now().date()
        delivery_date = purchase_order.delivery_date or base_date
        
        schedules = []
        for i, milestone in enumerate(milestones, 1):
            # 计算应付金额
            amount = purchase_order.total_with_tax * milestone['percentage'] / Decimal('100')
            
            # 计算到期日期
            if milestone['type'] == 'PREPAY':
                due_date = base_date + timedelta(days=milestone['days_offset'])
            elif milestone['type'] == 'ON_DELIVERY':
                due_date = delivery_date
            elif milestone['type'] in ['ON_INSPECTION', 'FINAL']:
                due_date = delivery_date + timedelta(days=milestone['days_offset'])
            else:
                due_date = base_date + timedelta(days=milestone['days_offset'])
            
            schedule = cls.objects.create(
                purchase_order=purchase_order,
                project=purchase_order.project,
                milestone_type=milestone['type'],
                milestone_name=milestone['name'],
                milestone_order=i,
                percentage=milestone['percentage'],
                amount_due=amount,
                due_date=due_date,
                reminder_days_before=3  # 采购付款提前3天提醒
            )
            schedules.append(schedule)
        
        return schedules


class Invoice(BaseModel):
    """
    Invoice records for tax management.
    """
    INVOICE_TYPE_CHOICES = [
        ('INPUT', '进项发票'),
        ('OUTPUT', '销项发票'),
    ]
    
    STATUS_CHOICES = [
        ('REGISTERED', '已登记'),
        ('CERTIFIED', '已认证'),
        ('VOID', '已作废'),
        ('NORMAL', '正常'),
        ('RED', '红冲'),
    ]
    
    REFERENCE_TYPE_CHOICES = [
        ('SALES_ORDER', '销售订单'),
        ('PURCHASE_ORDER', '采购订单'),
        ('EXPENSE', '费用报销'),
    ]
    
    INVOICE_CATEGORY_CHOICES = [
        ('SPECIAL', '数电发票（增值税专用发票）'),
        ('NORMAL', '数电发票（普通发票）'),
        ('PAPER_SPECIAL', '纸质增值税专用发票'),
        ('PAPER_NORMAL', '纸质普通发票'),
    ]
    
    invoice_type = models.CharField(max_length=10, choices=INVOICE_TYPE_CHOICES, verbose_name='发票类型')
    invoice_no = models.CharField(max_length=50, unique=True, verbose_name='发票号')
    invoice_code = models.CharField(max_length=50, blank=True, verbose_name='发票代码')
    digital_invoice_no = models.CharField(max_length=50, blank=True, verbose_name='数电发票号码')
    invoice_date = models.DateTimeField(verbose_name='开票日期')
    
    # 销方信息 (Seller info)
    seller_tax_no = models.CharField(max_length=50, blank=True, verbose_name='销方识别号')
    seller_name = models.CharField(max_length=200, blank=True, verbose_name='销方名称')
    
    # 购方信息 (Buyer info) 
    buyer_tax_no = models.CharField(max_length=50, blank=True, verbose_name='购方识别号')
    buyer_name = models.CharField(max_length=200, blank=True, verbose_name='购买方名称')
    
    # 保持兼容性的字段
    party_name = models.CharField(max_length=200, verbose_name='对方单位')
    tax_number = models.CharField(max_length=50, blank=True, verbose_name='税号')
    
    amount_before_tax = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='金额（不含税）')
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='税额')
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='价税合计')
    
    # 发票分类信息
    invoice_source = models.CharField(max_length=100, blank=True, verbose_name='发票来源')
    invoice_category = models.CharField(max_length=50, choices=INVOICE_CATEGORY_CHOICES, blank=True, verbose_name='发票票种')
    
    reference_type = models.CharField(
        max_length=20,
        choices=REFERENCE_TYPE_CHOICES,
        null=True,
        blank=True,
        verbose_name='关联单据类型'
    )
    reference_id = models.IntegerField(null=True, blank=True, verbose_name='关联单据ID')
    
    # 项目关联 - 用于成本核算
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='invoices',
        verbose_name='关联项目'
    )
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='REGISTERED', verbose_name='状态')
    notes = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'invoice'
        verbose_name = '发票'
        verbose_name_plural = verbose_name
        ordering = ['-invoice_date', '-id']
    
    def __str__(self):
        return f"{self.invoice_no}"
    
    def save(self, *args, **kwargs):
        # Calculate total_amount if not set
        if self.amount_before_tax and self.tax_amount:
            self.total_amount = self.amount_before_tax + self.tax_amount
        super().save(*args, **kwargs)


class InvoiceItem(BaseModel):
    """
    Invoice line items / details.
    发票明细行，记录每张发票的商品明细。
    """
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='发票'
    )
    line_no = models.IntegerField(default=1, verbose_name='行号')
    
    # 商品信息
    tax_category_code = models.CharField(max_length=50, blank=True, verbose_name='税收分类编码')
    business_type = models.CharField(max_length=100, blank=True, verbose_name='特定业务类型')
    item_name = models.CharField(max_length=500, verbose_name='货物或应税劳务名称')
    specification = models.CharField(max_length=200, blank=True, verbose_name='规格型号')
    unit = models.CharField(max_length=50, blank=True, verbose_name='单位')
    
    # 数量和金额
    quantity = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True, verbose_name='数量')
    unit_price = models.DecimalField(max_digits=15, decimal_places=6, null=True, blank=True, verbose_name='单价')
    amount = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='金额')
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name='税率(%)')
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name='税额')
    
    class Meta:
        db_table = 'invoice_item'
        verbose_name = '发票明细'
        verbose_name_plural = verbose_name
        ordering = ['invoice', 'line_no']
    
    def __str__(self):
        return f"{self.invoice.invoice_no} - {self.item_name}"


class SharedExpense(BaseModel):
    """
    Shared/Public expense for allocation across multiple projects.
    Examples: rent, utilities, shared equipment, admin expenses.
    """
    ALLOCATION_METHOD_CHOICES = [
        ('EQUAL', '平均分摊'),
        ('REVENUE', '按收入比例'),
        ('HEADCOUNT', '按人员数量'),
        ('LABOR_HOURS', '按工时比例'),
        ('BUDGET', '按预算比例'),
        ('CUSTOM', '自定义比例'),
    ]
    
    CATEGORY_CHOICES = [
        ('RENT', '房租'),
        ('UTILITIES', '水电费'),
        ('EQUIPMENT', '设备折旧'),
        ('IT', 'IT服务'),
        ('ADMIN', '行政费用'),
        ('INSURANCE', '保险费'),
        ('DEPRECIATION', '折旧'),
        ('OTHER', '其他'),
    ]
    
    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('PENDING', '待分摊'),
        ('ALLOCATED', '已分摊'),
        ('CANCELLED', '已取消'),
    ]
    
    expense_no = models.CharField(max_length=50, unique=True, verbose_name='费用编号')
    name = models.CharField(max_length=200, verbose_name='费用名称')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, verbose_name='费用类别')
    description = models.TextField(blank=True, verbose_name='费用说明')
    
    expense_date = models.DateField(verbose_name='费用日期')
    period_start = models.DateField(verbose_name='分摊期间开始')
    period_end = models.DateField(verbose_name='分摊期间结束')
    
    amount = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='费用金额')
    allocation_method = models.CharField(
        max_length=20,
        choices=ALLOCATION_METHOD_CHOICES,
        default='EQUAL',
        verbose_name='分摊方式'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', verbose_name='状态')
    
    allocated_at = models.DateTimeField(null=True, blank=True, verbose_name='分摊时间')
    allocated_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='allocated_shared_expenses',
        verbose_name='分摊人'
    )
    notes = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'shared_expense'
        verbose_name = '公共费用'
        verbose_name_plural = verbose_name
        ordering = ['-expense_date']
    
    def __str__(self):
        return f"{self.expense_no} - {self.name}"
    
    def save(self, *args, **kwargs):
        # Auto-generate expense_no
        if not self.expense_no:
            from django.utils import timezone
            date_str = timezone.now().strftime('%Y%m%d')
            prefix = 'SE'  # Shared Expense
            last = SharedExpense.objects.filter(expense_no__startswith=f'{prefix}{date_str}').order_by('-expense_no').first()
            if last:
                last_seq = int(last.expense_no[-4:])
                new_seq = last_seq + 1
            else:
                new_seq = 1
            self.expense_no = f'{prefix}{date_str}{new_seq:04d}'
        super().save(*args, **kwargs)


class SharedExpenseAllocation(BaseModel):
    """
    Allocation of shared expense to individual projects.
    """
    shared_expense = models.ForeignKey(
        SharedExpense,
        on_delete=models.CASCADE,
        related_name='allocations',
        verbose_name='公共费用'
    )
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.PROTECT,
        related_name='shared_expense_allocations',
        verbose_name='项目'
    )
    allocation_ratio = models.DecimalField(
        max_digits=6,
        decimal_places=4,
        verbose_name='分摊比例'
    )
    allocated_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='分摊金额'
    )
    notes = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'shared_expense_allocation'
        verbose_name = '费用分摊明细'
        verbose_name_plural = verbose_name
        unique_together = ['shared_expense', 'project']
    
    def __str__(self):
        return f"{self.shared_expense.expense_no} -> {self.project.code}"


class PaymentRequest(BaseModel):
    """
    付款申请 - 用于申请向供应商付款，需经审批流程
    """
    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('PENDING', '审批中'),
        ('APPROVED', '已批准'),
        ('REJECTED', '已拒绝'),
        ('PAID', '已付款'),
        ('CANCELLED', '已取消'),
    ]
    
    PAYMENT_TYPE_CHOICES = [
        ('PREPAY', '预付款'),
        ('PROGRESS', '进度款'),
        ('FINAL', '尾款'),
        ('URGENT', '紧急付款'),
        ('OTHER', '其他'),
    ]
    
    request_no = models.CharField(max_length=50, unique=True, verbose_name='申请单号')
    title = models.CharField(max_length=200, verbose_name='申请标题')
    payment_type = models.CharField(
        max_length=20, 
        choices=PAYMENT_TYPE_CHOICES, 
        default='OTHER',
        verbose_name='付款类型'
    )
    supplier = models.ForeignKey(
        'masterdata.Supplier',
        on_delete=models.PROTECT,
        related_name='payment_requests',
        verbose_name='供应商'
    )
    po = models.ForeignKey(
        'purchase.PurchaseOrder',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payment_requests',
        verbose_name='关联采购订单'
    )
    ap = models.ForeignKey(
        AccountPayable,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payment_requests',
        verbose_name='关联应付账款'
    )
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payment_requests',
        verbose_name='关联项目'
    )
    amount = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='申请金额')
    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name='币种'
    )
    bank_account = models.CharField(max_length=100, blank=True, verbose_name='收款账户')
    bank_name = models.CharField(max_length=100, blank=True, verbose_name='开户银行')
    expected_date = models.DateField(null=True, blank=True, verbose_name='期望付款日期')
    reason = models.TextField(verbose_name='付款原因')
    attachments = models.JSONField(default=list, blank=True, verbose_name='附件')
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='DRAFT',
        verbose_name='状态'
    )
    applicant = models.ForeignKey(
        'accounts.User',
        on_delete=models.PROTECT,
        related_name='payment_requests_applied',
        verbose_name='申请人'
    )
    approved_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payment_requests_approved',
        verbose_name='审批人'
    )
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name='审批时间')
    paid_at = models.DateTimeField(null=True, blank=True, verbose_name='付款时间')
    payment = models.ForeignKey(
        Payment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payment_requests',
        verbose_name='付款记录'
    )
    notes = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'payment_request'
        verbose_name = '付款申请'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.request_no} - {self.supplier.name if self.supplier else ''} - {self.amount}"
    
    def save(self, *args, **kwargs):
        if not self.request_no:
            from django.utils import timezone
            today = timezone.now().strftime('%Y%m%d')
            last = PaymentRequest.objects.filter(
                request_no__startswith=f'PAY{today}'
            ).order_by('-request_no').first()
            if last:
                seq = int(last.request_no[-4:]) + 1
            else:
                seq = 1
            self.request_no = f'PAY{today}{seq:04d}'
        super().save(*args, **kwargs)


# Import additional models for Django discovery
from .bank_statement_models import BankStatement, BankStatementImportLog  # noqa: E402, F401
from .reconciliation_models import (  # noqa: E402, F401
    PurchaseReconciliation, PurchaseReconciliationLine,
    SalesReconciliation, SalesReconciliationLine,
    InvoiceReconciliation, InvoiceReconciliationLine
)


# Import models from accounting
from .accounting import (
    AccountCategory, ChartOfAccount, FiscalPeriod,
    JournalVoucher, VoucherLine, AccountBalance
)

# Import models from tax_management
from .tax_management import (
    TaxType, TaxRate, TaxPeriod,
    TaxDeclaration, TaxDeclarationItem, TaxInvoice
)

# Import payable ledger models (payable_models.py) for Django discovery
from .payable_models import PayableItem, PayableSettlement  # noqa: E402,F401
