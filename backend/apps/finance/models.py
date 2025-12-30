"""
Finance models for expenses, receivables, and payables.
"""
from django.db import models
from apps.core.models import BaseModel
from apps.accounts.models import User, Department
from apps.masterdata.models import Customer, Supplier
from apps.projects.models import Project
from apps.sales.models import SalesOrder
from apps.purchase.models import PurchaseOrder


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


class ExchangeRateHistory(models.Model):
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
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    
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
        Project,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='expenses',
        verbose_name='项目'
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='expenses',
        verbose_name='部门'
    )
    user = models.ForeignKey(
        User,
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
        Customer,
        on_delete=models.PROTECT,
        related_name='receivables',
        verbose_name='客户'
    )
    so = models.ForeignKey(
        SalesOrder,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='receivables',
        verbose_name='销售订单'
    )
    project = models.ForeignKey(
        Project,
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
        Supplier,
        on_delete=models.PROTECT,
        related_name='payables',
        verbose_name='供应商'
    )
    po = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='payables',
        verbose_name='采购订单'
    )
    project = models.ForeignKey(
        Project,
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
        
        # Update AR/AP amount_paid
        if self.ar:
            self.ar.amount_paid += self.amount
            self.ar.save()
        elif self.ap:
            self.ap.amount_paid += self.amount
            self.ap.save()


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
        Project,
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
        User,
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
        Project,
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


# Import additional models for Django discovery
from .bank_statement_models import BankStatement, BankStatementImportLog  # noqa: E402, F401
from .reconciliation_models import (  # noqa: E402, F401
    PurchaseReconciliation, PurchaseReconciliationLine,
    SalesReconciliation, SalesReconciliationLine,
    InvoiceReconciliation, InvoiceReconciliationLine
)
