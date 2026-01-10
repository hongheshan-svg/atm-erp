"""
RFQ (Request for Quotation) models
询价单、供应商报价、比价分析模型
"""
from django.db import models
from django.conf import settings
from apps.core.models import BaseModel


class RFQ(BaseModel):
    """Request for Quotation - 询价单"""
    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('SENT', '已发送'),
        ('QUOTED', '已报价'),
        ('ACCEPTED', '已接受'),
        ('REJECTED', '已拒绝'),
        ('CANCELLED', '已取消'),
    ]
    
    rfq_no = models.CharField(max_length=50, unique=True, verbose_name='询价单号')
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='rfqs',
        verbose_name='项目'
    )
    request_date = models.DateField(auto_now_add=True, verbose_name='询价日期')
    response_deadline = models.DateField(verbose_name='报价截止日期')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', verbose_name='状态')
    notes = models.TextField(null=True, blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'rfq'
        verbose_name = '询价单'
        verbose_name_plural = verbose_name
        ordering = ['-request_date']
    
    def __str__(self):
        return self.rfq_no
    
    def save(self, *args, **kwargs):
        if not self.rfq_no:
            from django.utils import timezone
            date_str = timezone.now().strftime('%Y%m%d')
            last_rfq = RFQ.objects.filter(rfq_no__startswith=f'RFQ{date_str}').order_by('-rfq_no').first()
            if last_rfq:
                last_seq = int(last_rfq.rfq_no[-4:])
                new_seq = last_seq + 1
            else:
                new_seq = 1
            self.rfq_no = f'RFQ{date_str}{new_seq:04d}'
        super().save(*args, **kwargs)


class RFQLine(BaseModel):
    """RFQ line items"""
    rfq = models.ForeignKey(
        RFQ,
        on_delete=models.CASCADE,
        related_name='lines',
        verbose_name='询价单'
    )
    item = models.ForeignKey(
        'masterdata.Item',
        on_delete=models.PROTECT,
        related_name='rfq_lines',
        verbose_name='物料'
    )
    qty = models.DecimalField(max_digits=12, decimal_places=3, verbose_name='数量')
    required_date = models.DateField(verbose_name='需求日期')
    specifications = models.TextField(null=True, blank=True, verbose_name='规格说明')
    
    class Meta:
        db_table = 'rfq_line'
        verbose_name = '询价单明细'
        verbose_name_plural = verbose_name
    
    def __str__(self):
        return f"{self.rfq.rfq_no} - {self.item.name}"


class RFQSupplier(BaseModel):
    """RFQ sent to suppliers"""
    rfq = models.ForeignKey(
        RFQ,
        on_delete=models.CASCADE,
        related_name='supplier_rfqs',
        verbose_name='询价单'
    )
    supplier = models.ForeignKey(
        'masterdata.Supplier',
        on_delete=models.PROTECT,
        related_name='rfqs',
        verbose_name='供应商'
    )
    sent_date = models.DateTimeField(null=True, blank=True, verbose_name='发送日期')
    is_responded = models.BooleanField(default=False, verbose_name='是否已响应')
    
    class Meta:
        db_table = 'rfq_supplier'
        verbose_name = 'RFQ供应商'
        verbose_name_plural = verbose_name
        unique_together = ['rfq', 'supplier']
    
    def __str__(self):
        return f"{self.rfq.rfq_no} - {self.supplier.name}"


class SupplierQuotation(BaseModel):
    """Supplier quotation response to RFQ - 供应商报价"""
    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('SUBMITTED', '已提交'),
        ('ACCEPTED', '已接受'),
        ('REJECTED', '已拒绝'),
    ]
    
    TAX_RATE_CHOICES = [
        (0, '0% (免税)'),
        (1, '1%'),
        (3, '3%'),
        (6, '6%'),
        (9, '9%'),
        (13, '13%'),
    ]
    
    quotation_no = models.CharField(max_length=50, unique=True, verbose_name='报价单号')
    rfq_supplier = models.ForeignKey(
        RFQSupplier,
        on_delete=models.CASCADE,
        related_name='quotations',
        verbose_name='RFQ供应商'
    )
    quotation_date = models.DateField(auto_now_add=True, verbose_name='报价日期')
    valid_until = models.DateField(verbose_name='有效期至')
    payment_terms = models.CharField(max_length=200, verbose_name='付款条款')
    delivery_terms = models.CharField(max_length=200, verbose_name='交货条款')
    
    # 金额相关
    total_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name='不含税金额'
    )
    tax_rate = models.IntegerField(
        choices=TAX_RATE_CHOICES,
        default=13,
        verbose_name='税率(%)'
    )
    tax_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name='税额'
    )
    total_with_tax = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name='含税总额'
    )
    
    # 供应商承诺
    warranty_period = models.IntegerField(default=12, verbose_name='质保期(月)')
    min_order_qty = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='最小起订量'
    )
    
    # 历史价格参考
    last_purchase_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='上次采购总价'
    )
    price_change_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='价格变动率(%)'
    )
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', verbose_name='状态')
    notes = models.TextField(null=True, blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'supplier_quotation'
        verbose_name = '供应商报价'
        verbose_name_plural = verbose_name
        ordering = ['-quotation_date']
    
    def __str__(self):
        return self.quotation_no
    
    def save(self, *args, **kwargs):
        from decimal import Decimal
        
        if not self.quotation_no:
            from django.utils import timezone
            date_str = timezone.now().strftime('%Y%m%d')
            last_quot = SupplierQuotation.objects.filter(
                quotation_no__startswith=f'QUOT{date_str}'
            ).order_by('-quotation_no').first()
            if last_quot:
                last_seq = int(last_quot.quotation_no[-4:])
                new_seq = last_seq + 1
            else:
                new_seq = 1
            self.quotation_no = f'QUOT{date_str}{new_seq:04d}'
        
        # 计算税额和含税总额
        tax_rate = Decimal(str(self.tax_rate))
        self.tax_amount = self.total_amount * tax_rate / Decimal('100')
        self.total_with_tax = self.total_amount + self.tax_amount
        
        super().save(*args, **kwargs)
    
    def calculate_price_change(self):
        """计算与上次采购价格的变动率"""
        from decimal import Decimal
        if self.last_purchase_price and self.last_purchase_price > 0:
            self.price_change_rate = (
                (self.total_amount - self.last_purchase_price) / self.last_purchase_price * Decimal('100')
            )
        else:
            self.price_change_rate = None


class SupplierQuotationLine(BaseModel):
    """Supplier quotation line items - 供应商报价明细"""
    quotation = models.ForeignKey(
        SupplierQuotation,
        on_delete=models.CASCADE,
        related_name='lines',
        verbose_name='供应商报价'
    )
    rfq_line = models.ForeignKey(
        RFQLine,
        on_delete=models.PROTECT,
        related_name='quotation_lines',
        verbose_name='RFQ明细'
    )
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='不含税单价')
    unit_price_with_tax = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name='含税单价'
    )
    qty = models.DecimalField(max_digits=12, decimal_places=3, verbose_name='数量')
    lead_time_days = models.IntegerField(verbose_name='交货周期（天）')
    earliest_delivery_date = models.DateField(null=True, blank=True, verbose_name='最早交货日期')
    line_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='不含税金额'
    )
    line_amount_with_tax = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name='含税金额'
    )
    
    # 替代品信息
    is_alternative = models.BooleanField(default=False, verbose_name='是否替代品')
    alternative_brand = models.CharField(max_length=100, blank=True, verbose_name='替代品牌')
    alternative_model = models.CharField(max_length=100, blank=True, verbose_name='替代型号')
    
    # 历史价格参考
    last_unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='上次采购单价'
    )
    price_change_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='价格变动率(%)'
    )
    
    notes = models.TextField(null=True, blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'supplier_quotation_line'
        verbose_name = '供应商报价明细'
        verbose_name_plural = verbose_name
    
    def __str__(self):
        return f"{self.quotation.quotation_no} - {self.rfq_line.item.name}"
    
    def save(self, *args, **kwargs):
        from decimal import Decimal
        
        # 计算行金额
        self.line_amount = self.unit_price * self.qty
        
        # 计算含税价格
        tax_rate = Decimal(str(self.quotation.tax_rate)) if self.quotation else Decimal('0')
        self.unit_price_with_tax = self.unit_price * (1 + tax_rate / Decimal('100'))
        self.line_amount_with_tax = self.line_amount * (1 + tax_rate / Decimal('100'))
        
        # 计算价格变动率
        if self.last_unit_price and self.last_unit_price > 0:
            self.price_change_rate = (
                (self.unit_price - self.last_unit_price) / self.last_unit_price * Decimal('100')
            )
        
        super().save(*args, **kwargs)
        
        # 更新报价单总额
        self._update_quotation_totals()
    
    def _update_quotation_totals(self):
        """更新所属报价单的总额"""
        if self.quotation:
            total = sum(
                line.line_amount for line in self.quotation.lines.filter(is_deleted=False)
            )
            # 避免递归调用，直接使用update
            SupplierQuotation.objects.filter(pk=self.quotation.pk).update(
                total_amount=total
            )
            # 重新获取并计算税额
            self.quotation.refresh_from_db()
            self.quotation.save()  # 这会触发税额计算


class QuotationComparison(BaseModel):
    """报价比价分析"""
    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('IN_PROGRESS', '比价中'),
        ('COMPLETED', '已完成'),
        ('APPROVED', '已审批'),
    ]
    
    comparison_no = models.CharField(max_length=50, unique=True, verbose_name='比价单号')
    rfq = models.ForeignKey(
        RFQ,
        on_delete=models.PROTECT,
        related_name='comparisons',
        verbose_name='询价单'
    )
    
    # 比价维度权重配置 (总和应为100)
    weight_price = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=40,
        verbose_name='价格权重(%)'
    )
    weight_quality = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=25,
        verbose_name='质量权重(%)'
    )
    weight_delivery = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=20,
        verbose_name='交期权重(%)'
    )
    weight_service = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=15,
        verbose_name='服务权重(%)'
    )
    
    # 推荐供应商
    recommended_quotation = models.ForeignKey(
        SupplierQuotation,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='recommended_in',
        verbose_name='推荐报价'
    )
    recommendation_reason = models.TextField(blank=True, verbose_name='推荐理由')
    
    # 价格统计
    min_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='最低报价'
    )
    max_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='最高报价'
    )
    avg_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='平均报价'
    )
    
    # 审批相关
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT', verbose_name='状态')
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='approved_comparisons',
        verbose_name='审批人'
    )
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name='审批时间')
    
    notes = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'quotation_comparison'
        verbose_name = '报价比价'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.comparison_no} - {self.rfq.rfq_no}"
    
    def save(self, *args, **kwargs):
        if not self.comparison_no:
            from django.utils import timezone
            date_str = timezone.now().strftime('%Y%m%d')
            last = QuotationComparison.objects.filter(
                comparison_no__startswith=f'CMP{date_str}'
            ).order_by('-comparison_no').first()
            if last:
                last_seq = int(last.comparison_no[-4:])
                new_seq = last_seq + 1
            else:
                new_seq = 1
            self.comparison_no = f'CMP{date_str}{new_seq:04d}'
        super().save(*args, **kwargs)


class QuotationScore(BaseModel):
    """供应商报价评分明细"""
    comparison = models.ForeignKey(
        QuotationComparison,
        on_delete=models.CASCADE,
        related_name='scores',
        verbose_name='比价分析'
    )
    quotation = models.ForeignKey(
        SupplierQuotation,
        on_delete=models.CASCADE,
        related_name='comparison_scores',
        verbose_name='供应商报价'
    )
    
    # 各维度评分 (0-100)
    score_price = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name='价格得分'
    )
    score_quality = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name='质量得分'
    )
    score_delivery = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name='交期得分'
    )
    score_service = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name='服务得分'
    )
    
    # 综合得分
    total_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name='综合得分'
    )
    
    # 排名
    ranking = models.IntegerField(default=0, verbose_name='排名')
    
    # 是否推荐
    is_recommended = models.BooleanField(default=False, verbose_name='是否推荐')
    
    notes = models.TextField(blank=True, verbose_name='评价说明')
    
    class Meta:
        db_table = 'quotation_score'
        verbose_name = '报价评分'
        verbose_name_plural = verbose_name
        unique_together = ['comparison', 'quotation']
        ordering = ['ranking']
    
    def __str__(self):
        return f"{self.comparison.comparison_no} - {self.quotation.quotation_no} (Rank: {self.ranking})"
    
    def calculate_total_score(self):
        """计算综合得分"""
        comparison = self.comparison
        self.total_score = (
            float(self.score_price) * float(comparison.weight_price) / 100 +
            float(self.score_quality) * float(comparison.weight_quality) / 100 +
            float(self.score_delivery) * float(comparison.weight_delivery) / 100 +
            float(self.score_service) * float(comparison.weight_service) / 100
        )
        return self.total_score


class ItemPriceHistory(BaseModel):
    """物料采购价格历史"""
    item = models.ForeignKey(
        'masterdata.Item',
        on_delete=models.PROTECT,
        related_name='price_history',
        verbose_name='物料'
    )
    supplier = models.ForeignKey(
        'masterdata.Supplier',
        on_delete=models.PROTECT,
        related_name='price_history',
        verbose_name='供应商'
    )
    
    # 价格信息
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='单价')
    qty = models.DecimalField(max_digits=12, decimal_places=3, verbose_name='采购数量')
    tax_rate = models.IntegerField(default=13, verbose_name='税率(%)')
    
    # 来源信息
    source_type = models.CharField(
        max_length=20,
        choices=[
            ('QUOTATION', '报价'),
            ('PO', '采购订单'),
            ('RECEIPT', '收货'),
        ],
        verbose_name='来源类型'
    )
    source_id = models.IntegerField(verbose_name='来源ID')
    source_no = models.CharField(max_length=50, verbose_name='来源单号')
    
    # 时间
    price_date = models.DateField(verbose_name='价格日期')
    
    class Meta:
        db_table = 'item_price_history'
        verbose_name = '物料价格历史'
        verbose_name_plural = verbose_name
        ordering = ['-price_date']
        indexes = [
            models.Index(fields=['item', 'supplier', '-price_date']),
        ]
    
    def __str__(self):
        return f"{self.item.sku} - {self.supplier.name} - ¥{self.unit_price}"

