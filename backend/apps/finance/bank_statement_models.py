"""
Bank Statement models for importing and managing bank transactions.
"""

from django.db import models
from django.utils import timezone

from apps.core.models import BaseModel
from apps.masterdata.models import Customer, Supplier
from apps.projects.models import Project


class BankStatement(BaseModel):
    """
    Bank statement record imported from bank transaction files.
    """

    TRANSACTION_TYPE_CHOICES = [
        ('DEBIT', '借（支出）'),
        ('CREDIT', '贷（收入）'),
    ]

    STATUS_CHOICES = [
        ('PENDING', '待匹配'),
        ('MATCHED', '已匹配'),
        ('PARTIAL', '部分核销'),
        ('IGNORED', '已忽略'),
        ('ERROR', '匹配错误'),
    ]

    MATCH_TYPE_CHOICES = [
        ('AP', '应付账款'),
        ('AR', '应收账款'),
        ('EXPENSE', '费用'),
        ('OTHER', '其他'),
    ]

    # 导入批次信息
    import_batch = models.CharField(max_length=50, verbose_name='导入批次号', db_index=True)
    import_date = models.DateTimeField(default=timezone.now, verbose_name='导入时间')
    source_file = models.CharField(max_length=255, blank=True, verbose_name='源文件名')

    # 银行信息标签
    bank_name = models.CharField(max_length=100, blank=True, default='', verbose_name='银行名称', db_index=True)
    bank_account = models.CharField(max_length=50, blank=True, default='', verbose_name='银行账号')

    # 银行流水原始信息
    voucher_no = models.CharField(max_length=100, blank=True, verbose_name='凭证号')
    counterparty_account = models.CharField(max_length=100, blank=True, verbose_name='对方账号')
    transaction_time = models.DateTimeField(verbose_name='交易时间')
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPE_CHOICES, verbose_name='借贷标志')
    counterparty_name = models.CharField(max_length=255, verbose_name='对方单位')
    counterparty_bank = models.CharField(max_length=100, blank=True, verbose_name='对方行号')
    purpose = models.CharField(max_length=100, blank=True, verbose_name='用途')
    summary = models.CharField(max_length=255, blank=True, verbose_name='摘要')
    postscript = models.TextField(blank=True, verbose_name='附言')
    receipt_info = models.TextField(blank=True, verbose_name='回单个性化信息')

    # 金额
    credit_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='转入金额')
    debit_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='转出金额')
    balance = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name='余额')

    # 支付凭证
    payment_voucher_type = models.CharField(max_length=50, blank=True, verbose_name='支付凭证种类')

    # 匹配信息
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', verbose_name='状态')
    match_type = models.CharField(
        max_length=20, choices=MATCH_TYPE_CHOICES, null=True, blank=True, verbose_name='匹配类型'
    )

    # 关联供应商/客户
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bank_statements',
        verbose_name='匹配供应商',
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bank_statements',
        verbose_name='匹配客户',
    )

    # 关联到具体业务单据
    related_ap = models.ForeignKey(
        'AccountPayable',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bank_statements',
        verbose_name='关联应付账款',
    )
    related_ar = models.ForeignKey(
        'AccountReceivable',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bank_statements',
        verbose_name='关联应收账款',
    )
    related_payment = models.ForeignKey(
        'Payment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bank_statements',
        verbose_name='关联付款记录',
    )

    # 项目关联 - 用于成本核算
    project = models.ForeignKey(
        Project,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bank_statements',
        verbose_name='关联项目',
    )

    match_confidence = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='匹配置信度(%)')
    match_notes = models.TextField(blank=True, verbose_name='匹配备注')

    class Meta:
        db_table = 'bank_statement'
        verbose_name = '银行流水'
        verbose_name_plural = verbose_name
        ordering = ['-transaction_time']
        indexes = [
            models.Index(fields=['counterparty_name']),
            models.Index(fields=['transaction_time']),
            models.Index(fields=['status']),
            models.Index(fields=['import_batch']),
        ]

    def __str__(self):
        return f"{self.transaction_time.strftime('%Y-%m-%d')} - {self.counterparty_name} - {self.amount}"

    @property
    def amount(self):
        """Get the actual transaction amount."""
        if self.transaction_type == 'DEBIT':
            return self.debit_amount
        return self.credit_amount

    @staticmethod
    def _normalize_name(name):
        """匹配用名称归一化:统一全角/半角括号（）()、去除空白。

        银行导出的对方单位名与主数据常因括号全半角、空格差异无法精确匹配，
        归一化后再比较可避免「考泰斯（长春）」匹配不到「考泰斯(长春)」。
        """
        s = (name or '').strip()
        for full, half in (('（', '('), ('）', ')'), ('　', ''), (' ', '')):
            s = s.replace(full, half)
        return s

    def auto_match_supplier(self):
        """
        Automatically match supplier based on counterparty name.
        Returns: (supplier, confidence) or (None, 0)
        """
        if not self.counterparty_name:
            return None, 0

        # Exact match
        exact_supplier = Supplier.objects.filter(name=self.counterparty_name, is_deleted=False).first()

        if exact_supplier:
            return exact_supplier, 100.0

        # Normalized exact match (全角/半角括号、空格归一后精确相等)
        target = self._normalize_name(self.counterparty_name)
        for supplier in Supplier.objects.filter(is_deleted=False):
            if self._normalize_name(supplier.name) == target:
                return supplier, 100.0

        # Partial match (contains)
        partial_suppliers = Supplier.objects.filter(name__icontains=self.counterparty_name, is_deleted=False)

        if partial_suppliers.count() == 1:
            return partial_suppliers.first(), 80.0

        # Reverse partial match (supplier name contains counterparty name or vice versa)
        for supplier in Supplier.objects.filter(is_deleted=False):
            if supplier.name in self.counterparty_name or self.counterparty_name in supplier.name:
                return supplier, 70.0

        # Fuzzy match based on keywords
        counterparty_keywords = set(self.counterparty_name.replace('有限公司', '').replace('股份', '').split())

        best_match = None
        best_score = 0

        for supplier in Supplier.objects.filter(is_deleted=False):
            supplier_keywords = set(supplier.name.replace('有限公司', '').replace('股份', '').split())

            # Calculate Jaccard similarity
            intersection = len(counterparty_keywords & supplier_keywords)
            union = len(counterparty_keywords | supplier_keywords)

            if union > 0:
                score = intersection / union * 100
                if score > best_score and score >= 30:
                    best_score = score
                    best_match = supplier

        if best_match:
            return best_match, best_score

        return None, 0

    def auto_match_customer(self):
        """
        Automatically match customer based on counterparty name.
        Returns: (customer, confidence) or (None, 0)
        """
        if not self.counterparty_name:
            return None, 0

        # Exact match
        exact_customer = Customer.objects.filter(name=self.counterparty_name, is_deleted=False).first()

        if exact_customer:
            return exact_customer, 100.0

        # Normalized exact match (全角/半角括号、空格归一后精确相等)
        target = self._normalize_name(self.counterparty_name)
        for customer in Customer.objects.filter(is_deleted=False):
            if self._normalize_name(customer.name) == target:
                return customer, 100.0

        # Partial match
        partial_customers = Customer.objects.filter(name__icontains=self.counterparty_name, is_deleted=False)

        if partial_customers.count() == 1:
            return partial_customers.first(), 80.0

        # Reverse partial match
        for customer in Customer.objects.filter(is_deleted=False):
            if customer.name in self.counterparty_name or self.counterparty_name in customer.name:
                return customer, 70.0

        return None, 0

    def auto_match_project(self):
        """
        Automatically match project based on customer/supplier.
        Returns: Project or None
        """
        # If customer is matched, find projects for that customer
        if self.customer:
            # Find active projects for this customer
            project = (
                Project.objects.filter(customer=self.customer, is_deleted=False, status__in=['ACTIVE', 'PLANNING'])
                .order_by('-created_at')
                .first()
            )

            if project:
                return project

        # If supplier is matched, try to find project via purchase orders
        if self.supplier:
            from apps.purchase.models import PurchaseOrder

            # Find purchase orders for this supplier
            po = (
                PurchaseOrder.objects.filter(supplier=self.supplier, is_deleted=False)
                .select_related('project')
                .order_by('-created_at')
                .first()
            )

            if po and po.project:
                return po.project

        return None


class BankStatementImportLog(BaseModel):
    """
    Log for bank statement import batches.
    """

    batch_no = models.CharField(max_length=50, unique=True, verbose_name='批次号')
    file_name = models.CharField(max_length=255, verbose_name='文件名')
    import_time = models.DateTimeField(default=timezone.now, verbose_name='导入时间')
    bank_name = models.CharField(max_length=100, blank=True, default='', verbose_name='银行名称')
    bank_account = models.CharField(max_length=50, blank=True, default='', verbose_name='银行账号')

    total_count = models.IntegerField(default=0, verbose_name='总记录数')
    success_count = models.IntegerField(default=0, verbose_name='成功导入数')
    error_count = models.IntegerField(default=0, verbose_name='错误数')
    matched_count = models.IntegerField(default=0, verbose_name='自动匹配数')

    debit_total = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='支出总额')
    credit_total = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='收入总额')

    notes = models.TextField(blank=True, verbose_name='备注')
    error_details = models.JSONField(default=list, verbose_name='错误详情')

    class Meta:
        db_table = 'bank_statement_import_log'
        verbose_name = '银行流水导入日志'
        verbose_name_plural = verbose_name
        ordering = ['-import_time']

    def __str__(self):
        return f'{self.batch_no} - {self.file_name}'
