from django.db import models
from apps.core.models import BaseModel


class PayableItem(BaseModel):
    """统一待付款项台账:各费用单据审批后登记的一条应付款。"""
    STATUS_PENDING = 'PENDING'
    STATUS_PARTIAL = 'PARTIAL'
    STATUS_PAID = 'PAID'
    STATUS_CANCELLED = 'CANCELLED'
    STATUS_CHOICES = [
        (STATUS_PENDING, '待付'), (STATUS_PARTIAL, '部分'),
        (STATUS_PAID, '已付'), (STATUS_CANCELLED, '已取消'),
    ]

    source_type = models.CharField(max_length=30, verbose_name='来源类型')
    source_id = models.PositiveIntegerField(verbose_name='来源单据ID')
    source_no = models.CharField(max_length=50, blank=True, default='', verbose_name='来源单号')
    category = models.CharField(max_length=30, blank=True, default='', verbose_name='费用类别')
    payee_name = models.CharField(max_length=255, blank=True, default='', verbose_name='收款方')
    supplier = models.ForeignKey('masterdata.Supplier', on_delete=models.SET_NULL,
                                 null=True, blank=True, related_name='payable_items', verbose_name='供应商')
    amount_due = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='应付金额')
    amount_paid = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='已付金额')
    currency = models.ForeignKey('finance.Currency', on_delete=models.PROTECT,
                                 null=True, blank=True, related_name='payable_items', verbose_name='币种')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, verbose_name='状态')
    due_date = models.DateField(null=True, blank=True, verbose_name='应付日期')
    project = models.ForeignKey('projects.Project', on_delete=models.SET_NULL,
                                null=True, blank=True, related_name='payable_items', verbose_name='项目')

    class Meta:
        db_table = 'payable_item'
        verbose_name = '待付款项'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['source_type', 'source_id'], name='uniq_payable_source'),
        ]
        indexes = [models.Index(fields=['status', 'supplier', 'due_date'])]

    def __str__(self):
        return f'{self.source_type}#{self.source_id} {self.payee_name} {self.amount_due}'

    @property
    def remaining(self):
        return self.amount_due - self.amount_paid

    def recalc_status(self):
        if self.status == self.STATUS_CANCELLED:
            return
        if self.amount_paid >= self.amount_due:
            self.status = self.STATUS_PAID
        elif self.amount_paid > 0:
            self.status = self.STATUS_PARTIAL
        else:
            self.status = self.STATUS_PENDING


class PayableSettlement(BaseModel):
    """核销记录:一笔银行流水核销一条台账项(部分金额)。"""
    bank_statement = models.ForeignKey('finance.BankStatement', on_delete=models.PROTECT,
                                       related_name='payable_settlements', verbose_name='银行流水')
    payable_item = models.ForeignKey(PayableItem, on_delete=models.PROTECT,
                                     related_name='settlements', verbose_name='待付款项')
    payment = models.ForeignKey('finance.Payment', on_delete=models.SET_NULL,
                                null=True, blank=True, related_name='payable_settlements', verbose_name='付款记录')
    amount = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='本次核销金额')

    class Meta:
        db_table = 'payable_settlement'
        verbose_name = '核销记录'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.bank_statement_id}→{self.payable_item_id} {self.amount}'
