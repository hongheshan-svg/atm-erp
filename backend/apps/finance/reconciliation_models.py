"""
财务对账模型 - 采购付款对账、销售收款对账、发票对账
"""
from django.db import models

from apps.accounts.models import User
from apps.core.models import BaseModel
from apps.core.utils import generate_code
from apps.masterdata.models import Customer, Supplier
from apps.purchase.models import PurchaseOrder
from apps.sales.models import SalesOrder


class PurchaseReconciliation(BaseModel):
    """
    采购付款对账单 - 按供应商对账采购订单和付款情况
    """
    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('PENDING', '待确认'),
        ('CONFIRMED', '已确认'),
        ('DISPUTED', '有争议'),
        ('CLOSED', '已关闭'),
    ]

    reconciliation_no = models.CharField(max_length=50, unique=True, verbose_name='对账单号')
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name='purchase_reconciliations',
        verbose_name='供应商'
    )

    # 对账期间
    period_start = models.DateField(verbose_name='对账期间开始')
    period_end = models.DateField(verbose_name='对账期间结束')

    # 汇总金额
    total_order_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name='订单总金额'
    )
    total_received_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name='已收货金额'
    )
    total_invoice_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name='发票金额'
    )
    total_paid_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name='已付款金额'
    )
    balance_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name='差额/欠款'
    )

    # 期初余额
    opening_balance = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name='期初余额'
    )
    # 期末余额
    closing_balance = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name='期末余额'
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', verbose_name='状态')
    reconciled_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='purchase_reconciliations_done',
        verbose_name='对账人'
    )
    reconciled_at = models.DateTimeField(null=True, blank=True, verbose_name='对账时间')
    confirmed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='purchase_reconciliations_confirmed',
        verbose_name='确认人'
    )
    confirmed_at = models.DateTimeField(null=True, blank=True, verbose_name='确认时间')
    notes = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'purchase_reconciliation'
        verbose_name = '采购对账单'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.reconciliation_no}"

    def save(self, *args, **kwargs):
        if not self.reconciliation_no:
            self.reconciliation_no = generate_code('PR_REC')
        # 计算期末余额
        self.closing_balance = self.opening_balance + self.total_invoice_amount - self.total_paid_amount
        self.balance_amount = self.closing_balance
        super().save(*args, **kwargs)


class PurchaseReconciliationLine(BaseModel):
    """
    采购对账单明细 - 关联的采购订单/发票/付款
    """
    LINE_TYPE_CHOICES = [
        ('ORDER', '采购订单'),
        ('RECEIPT', '收货单'),
        ('INVOICE', '发票'),
        ('PAYMENT', '付款'),
        ('ADJUSTMENT', '调整'),
    ]

    # 收货状态
    RECEIPT_STATUS_CHOICES = [
        ('NOT_RECEIVED', '未收货'),
        ('PARTIAL', '部分收货'),
        ('RECEIVED', '已收货'),
        ('VERIFIED', '已验收'),
    ]

    reconciliation = models.ForeignKey(
        PurchaseReconciliation,
        on_delete=models.CASCADE,
        related_name='lines',
        verbose_name='对账单'
    )
    line_type = models.CharField(max_length=20, choices=LINE_TYPE_CHOICES, verbose_name='类型')

    # 关联单据
    po = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reconciliation_lines',
        verbose_name='采购订单'
    )
    reference_no = models.CharField(max_length=100, blank=True, verbose_name='单据号')
    reference_date = models.DateField(null=True, blank=True, verbose_name='单据日期')

    # 金额
    debit_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name='借方金额'
    )
    credit_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name='贷方金额'
    )
    balance = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name='余额'
    )

    # 收货状态相关
    order_qty = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name='订单数量'
    )
    received_qty = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name='已收货数量'
    )
    receipt_status = models.CharField(
        max_length=20,
        choices=RECEIPT_STATUS_CHOICES,
        default='NOT_RECEIVED',
        verbose_name='收货状态'
    )
    receipt_confirmed = models.BooleanField(default=False, verbose_name='收货已确认')
    receipt_confirmed_at = models.DateTimeField(null=True, blank=True, verbose_name='收货确认时间')

    # 付款进度相关
    payable_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name='应付金额'
    )
    paid_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name='已付金额'
    )
    payment_progress = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        verbose_name='付款进度(%)'
    )

    is_matched = models.BooleanField(default=False, verbose_name='已核销')
    notes = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'purchase_reconciliation_line'
        verbose_name = '采购对账单明细'
        verbose_name_plural = verbose_name
        ordering = ['reference_date', 'id']

    def __str__(self):
        return f"{self.reconciliation.reconciliation_no} - {self.reference_no}"


class SalesReconciliation(BaseModel):
    """
    销售收款对账单 - 按客户对账销售订单和收款情况
    """
    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('PENDING', '待确认'),
        ('CONFIRMED', '已确认'),
        ('DISPUTED', '有争议'),
        ('CLOSED', '已关闭'),
    ]

    reconciliation_no = models.CharField(max_length=50, unique=True, verbose_name='对账单号')
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name='sales_reconciliations',
        verbose_name='客户'
    )

    # 对账期间
    period_start = models.DateField(verbose_name='对账期间开始')
    period_end = models.DateField(verbose_name='对账期间结束')

    # 汇总金额
    total_order_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name='订单总金额'
    )
    total_delivered_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name='已发货金额'
    )
    total_invoice_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name='发票金额'
    )
    total_received_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name='已收款金额'
    )
    balance_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name='差额/应收'
    )

    # 期初余额
    opening_balance = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name='期初余额'
    )
    # 期末余额
    closing_balance = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name='期末余额'
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', verbose_name='状态')
    reconciled_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='sales_reconciliations_done',
        verbose_name='对账人'
    )
    reconciled_at = models.DateTimeField(null=True, blank=True, verbose_name='对账时间')
    confirmed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='sales_reconciliations_confirmed',
        verbose_name='确认人'
    )
    confirmed_at = models.DateTimeField(null=True, blank=True, verbose_name='确认时间')
    notes = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'sales_reconciliation'
        verbose_name = '销售对账单'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.reconciliation_no}"

    def save(self, *args, **kwargs):
        if not self.reconciliation_no:
            self.reconciliation_no = generate_code('SR_REC')
        # 计算期末余额
        self.closing_balance = self.opening_balance + self.total_invoice_amount - self.total_received_amount
        self.balance_amount = self.closing_balance
        super().save(*args, **kwargs)


class SalesReconciliationLine(BaseModel):
    """
    销售对账单明细 - 关联的销售订单/发票/收款
    """
    LINE_TYPE_CHOICES = [
        ('ORDER', '销售订单'),
        ('DELIVERY', '发货单'),
        ('INVOICE', '发票'),
        ('RECEIPT', '收款'),
        ('ADJUSTMENT', '调整'),
    ]

    # 发货状态
    DELIVERY_STATUS_CHOICES = [
        ('NOT_DELIVERED', '未发货'),
        ('PARTIAL', '部分发货'),
        ('DELIVERED', '已发货'),
        ('SIGNED', '已签收'),
    ]

    reconciliation = models.ForeignKey(
        SalesReconciliation,
        on_delete=models.CASCADE,
        related_name='lines',
        verbose_name='对账单'
    )
    line_type = models.CharField(max_length=20, choices=LINE_TYPE_CHOICES, verbose_name='类型')

    # 关联单据
    so = models.ForeignKey(
        SalesOrder,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reconciliation_lines',
        verbose_name='销售订单'
    )
    reference_no = models.CharField(max_length=100, blank=True, verbose_name='单据号')
    reference_date = models.DateField(null=True, blank=True, verbose_name='单据日期')

    # 金额
    debit_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name='借方金额'
    )
    credit_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name='贷方金额'
    )
    balance = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name='余额'
    )

    # 发货状态相关
    order_qty = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name='订单数量'
    )
    delivered_qty = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name='已发货数量'
    )
    delivery_status = models.CharField(
        max_length=20,
        choices=DELIVERY_STATUS_CHOICES,
        default='NOT_DELIVERED',
        verbose_name='发货状态'
    )
    delivery_confirmed = models.BooleanField(default=False, verbose_name='发货已确认')
    delivery_confirmed_at = models.DateTimeField(null=True, blank=True, verbose_name='发货确认时间')

    # 收款进度相关
    receivable_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name='应收金额'
    )
    received_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name='已收金额'
    )
    collection_progress = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        verbose_name='收款进度(%)'
    )

    is_matched = models.BooleanField(default=False, verbose_name='已核销')
    notes = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'sales_reconciliation_line'
        verbose_name = '销售对账单明细'
        verbose_name_plural = verbose_name
        ordering = ['reference_date', 'id']

    def __str__(self):
        return f"{self.reconciliation.reconciliation_no} - {self.reference_no}"


class InvoiceReconciliation(BaseModel):
    """
    发票对账单 - 进项发票与采购订单对账，销项发票与销售订单对账
    """
    INVOICE_TYPE_CHOICES = [
        ('INPUT', '进项发票'),
        ('OUTPUT', '销项发票'),
    ]

    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('MATCHED', '已匹配'),
        ('PARTIAL', '部分匹配'),
        ('UNMATCHED', '未匹配'),
        ('CONFIRMED', '已确认'),
    ]

    reconciliation_no = models.CharField(max_length=50, unique=True, verbose_name='对账单号')
    invoice_type = models.CharField(max_length=10, choices=INVOICE_TYPE_CHOICES, verbose_name='发票类型')

    # 对账期间
    period_start = models.DateField(verbose_name='对账期间开始')
    period_end = models.DateField(verbose_name='对账期间结束')

    # 汇总
    total_invoice_count = models.IntegerField(default=0, verbose_name='发票数量')
    total_invoice_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name='发票总金额'
    )
    total_tax_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name='税额合计'
    )
    matched_count = models.IntegerField(default=0, verbose_name='已匹配数量')
    matched_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name='已匹配金额'
    )
    unmatched_count = models.IntegerField(default=0, verbose_name='未匹配数量')
    unmatched_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name='未匹配金额'
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', verbose_name='状态')
    reconciled_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='invoice_reconciliations_done',
        verbose_name='对账人'
    )
    reconciled_at = models.DateTimeField(null=True, blank=True, verbose_name='对账时间')
    notes = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'invoice_reconciliation'
        verbose_name = '发票对账单'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.reconciliation_no}"

    def save(self, *args, **kwargs):
        if not self.reconciliation_no:
            prefix = 'INV_IN' if self.invoice_type == 'INPUT' else 'INV_OUT'
            self.reconciliation_no = generate_code(prefix)
        super().save(*args, **kwargs)


class InvoiceReconciliationLine(BaseModel):
    """
    发票对账单明细
    """
    MATCH_STATUS_CHOICES = [
        ('MATCHED', '已匹配'),
        ('PARTIAL', '部分匹配'),
        ('UNMATCHED', '未匹配'),
        ('DISPUTED', '有争议'),
    ]

    reconciliation = models.ForeignKey(
        InvoiceReconciliation,
        on_delete=models.CASCADE,
        related_name='lines',
        verbose_name='对账单'
    )

    # 发票信息
    invoice_no = models.CharField(max_length=100, verbose_name='发票号')
    invoice_date = models.DateField(verbose_name='开票日期')
    party_name = models.CharField(max_length=200, verbose_name='对方单位')
    tax_number = models.CharField(max_length=50, blank=True, verbose_name='税号')

    amount_before_tax = models.DecimalField(
        max_digits=15, decimal_places=2,
        verbose_name='不含税金额'
    )
    tax_amount = models.DecimalField(
        max_digits=15, decimal_places=2,
        verbose_name='税额'
    )
    total_amount = models.DecimalField(
        max_digits=15, decimal_places=2,
        verbose_name='价税合计'
    )

    # 匹配的订单
    matched_order_no = models.CharField(max_length=100, blank=True, verbose_name='匹配订单号')
    matched_order_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name='订单金额'
    )
    difference_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name='差异金额'
    )

    match_status = models.CharField(
        max_length=20, choices=MATCH_STATUS_CHOICES, default='UNMATCHED',
        verbose_name='匹配状态'
    )
    notes = models.TextField(blank=True, verbose_name='备注')

    class Meta:
        db_table = 'invoice_reconciliation_line'
        verbose_name = '发票对账单明细'
        verbose_name_plural = verbose_name
        ordering = ['invoice_date', 'id']

    def __str__(self):
        return f"{self.reconciliation.reconciliation_no} - {self.invoice_no}"

    def save(self, *args, **kwargs):
        # 计算差异金额
        self.difference_amount = self.total_amount - self.matched_order_amount
        super().save(*args, **kwargs)

