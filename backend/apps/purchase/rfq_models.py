"""
RFQ (Request for Quotation) models
询价单、供应商报价、比价分析模型

非标自动化行业使用说明：
- 核心功能：向供应商发送询价、收集报价、比价分析
- 询价类型：非标建议使用'常规询价'或'样件询价'
  - '批量询价'和'框架协议询价'更适合标准件重复采购
- 询价模板(RFQTemplate)：可选功能，用于快速创建相似询价
- 价格历史(ItemPriceHistory)：可选功能，对一次性定制件意义不大
- 最小订购量(min_order_qty)：可选字段，非标通常按项目需求采购
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
    
    # 询价类型（非标自动化增强）
    RFQ_TYPE_CHOICES = [
        ('NORMAL', '常规询价'),
        ('SAMPLE', '样件询价'),
        ('BATCH', '批量询价'),
        ('URGENT', '紧急询价'),
        ('FRAMEWORK', '框架协议询价'),
    ]
    
    # 优先级
    PRIORITY_CHOICES = [
        ('LOW', '低'),
        ('NORMAL', '普通'),
        ('HIGH', '高'),
        ('URGENT', '紧急'),
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
    
    # 非标自动化增强字段
    rfq_type = models.CharField(
        max_length=20, choices=RFQ_TYPE_CHOICES, default='NORMAL', verbose_name='询价类型'
    )
    priority = models.CharField(
        max_length=20, choices=PRIORITY_CHOICES, default='NORMAL', verbose_name='优先级'
    )
    
    # 模板关联
    template = models.ForeignKey(
        'RFQTemplate', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='rfqs', verbose_name='询价模板'
    )
    
    # 技术要求
    technical_requirements = models.TextField(blank=True, verbose_name='技术要求')
    quality_requirements = models.TextField(blank=True, verbose_name='质量要求')
    packaging_requirements = models.TextField(blank=True, verbose_name='包装要求')
    delivery_requirements = models.TextField(blank=True, verbose_name='交货要求')
    
    # 附件数量统计（便于前端显示）
    attachment_count = models.IntegerField(default=0, verbose_name='附件数量')
    
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
    """RFQ line items - 询价单明细"""
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
    
    # ==================== 非标自动化行业增强 ====================
    # 关联项目BOM
    bom_item = models.ForeignKey(
        'projects.ProjectBOM', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='rfq_lines', verbose_name='BOM项'
    )
    
    # 图纸关联
    drawing = models.ForeignKey(
        'projects.Drawing', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='rfq_lines', verbose_name='图纸'
    )
    drawing_no = models.CharField(max_length=100, blank=True, verbose_name='图号')
    drawing_version = models.CharField(max_length=50, blank=True, verbose_name='图纸版本')
    
    # 技术规格结构化
    technical_specs = models.JSONField(
        default=dict, blank=True, verbose_name='技术规格',
        help_text='结构化技术参数，如：{"材质": "SUS304", "精度": "IT7", "表面处理": "镀锌"}'
    )
    
    # 物料类型标记
    is_critical = models.BooleanField(default=False, verbose_name='关键件')
    is_long_lead = models.BooleanField(default=False, verbose_name='长周期件')
    is_custom = models.BooleanField(default=False, verbose_name='非标定制件')
    
    # 分阶段需求
    sample_qty = models.DecimalField(
        max_digits=12, decimal_places=3, null=True, blank=True, verbose_name='样件数量'
    )
    sample_required_date = models.DateField(null=True, blank=True, verbose_name='样件需求日期')
    
    # 目标价格（预算参考）
    target_price = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='目标单价'
    )
    
    # 上次采购信息
    last_supplier = models.ForeignKey(
        'masterdata.Supplier', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='rfq_lines_as_last_supplier', verbose_name='上次供应商'
    )
    last_price = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='上次采购单价'
    )
    
    # 附件数量
    attachment_count = models.IntegerField(default=0, verbose_name='附件数量')
    
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
    
    # ==================== 非标自动化行业增强 ====================
    # 技术规格结构化（用于对比）
    technical_specs = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='技术规格',
        help_text='结构化技术参数，如：{"材质": "SUS304", "精度": "IT7", "表面处理": "镀锌"}'
    )
    
    # 图纸版本（报价时的图纸版本）
    drawing_version = models.CharField(max_length=50, blank=True, verbose_name='图纸版本')
    drawing_no = models.CharField(max_length=100, blank=True, verbose_name='图号')
    
    # 分阶段交期（非标自动化常见）
    sample_qty = models.DecimalField(
        max_digits=12, decimal_places=3, null=True, blank=True, verbose_name='样件数量'
    )
    sample_delivery_days = models.IntegerField(null=True, blank=True, verbose_name='样件交期（天）')
    sample_delivery_date = models.DateField(null=True, blank=True, verbose_name='样件交货日期')
    sample_unit_price = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='样件单价'
    )
    batch_delivery_date = models.DateField(null=True, blank=True, verbose_name='批量交货日期')
    
    # 工艺能力说明
    process_capability = models.TextField(blank=True, verbose_name='工艺能力说明')
    
    # 质量承诺
    quality_commitment = models.TextField(blank=True, verbose_name='质量承诺')
    inspection_report = models.BooleanField(default=False, verbose_name='提供检验报告')
    first_article_inspection = models.BooleanField(default=False, verbose_name='首件检验')
    
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
    
    # 比价类型（非标自动化特殊需求）
    COMPARISON_TYPE_CHOICES = [
        ('NORMAL', '常规比价'),
        ('SAMPLE', '样件比价'),
        ('BATCH', '批量比价'),
        ('URGENT', '紧急比价'),
        ('CHANGE', '变更重新比价'),
    ]
    
    # 风险等级
    RISK_LEVEL_CHOICES = [
        ('LOW', '低风险'),
        ('MEDIUM', '中风险'),
        ('HIGH', '高风险'),
    ]
    
    comparison_no = models.CharField(max_length=50, unique=True, verbose_name='比价单号')
    rfq = models.ForeignKey(
        RFQ,
        on_delete=models.PROTECT,
        related_name='comparisons',
        verbose_name='询价单'
    )
    
    # 非标自动化增强字段
    comparison_type = models.CharField(
        max_length=20,
        choices=COMPARISON_TYPE_CHOICES,
        default='NORMAL',
        verbose_name='比价类型'
    )
    risk_level = models.CharField(
        max_length=20,
        choices=RISK_LEVEL_CHOICES,
        default='LOW',
        verbose_name='风险等级'
    )
    critical_items_count = models.IntegerField(default=0, verbose_name='关键件数量')
    long_lead_items_count = models.IntegerField(default=0, verbose_name='长周期件数量')
    
    # 权重模板
    WEIGHT_TEMPLATE_CHOICES = [
        ('STANDARD', '标准权重'),
        ('QUALITY_FIRST', '质量优先'),
        ('DELIVERY_FIRST', '交期优先'),
        ('PRICE_FIRST', '价格优先'),
        ('CUSTOM', '自定义'),
    ]
    weight_template = models.CharField(
        max_length=20,
        choices=WEIGHT_TEMPLATE_CHOICES,
        default='STANDARD',
        verbose_name='权重模板'
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
    # 新增技术能力权重
    weight_technical = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name='技术能力权重(%)'
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
    
    # 非标自动化新增评分维度
    score_technical = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name='技术能力得分',
        help_text='基于供应商技术能力评估'
    )
    score_reliability = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name='可靠性得分',
        help_text='基于历史履约数据'
    )
    
    # 综合得分
    total_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name='综合得分'
    )
    
    # 多维度推荐得分
    price_rank = models.IntegerField(default=0, verbose_name='价格排名')
    delivery_rank = models.IntegerField(default=0, verbose_name='交期排名')
    quality_rank = models.IntegerField(default=0, verbose_name='质量排名')
    
    # 排名
    ranking = models.IntegerField(default=0, verbose_name='综合排名')
    
    # 推荐类型
    RECOMMEND_TYPE_CHOICES = [
        ('', '不推荐'),
        ('OVERALL', '综合最优'),
        ('PRICE', '价格最优'),
        ('DELIVERY', '交期最优'),
        ('QUALITY', '质量最优'),
    ]
    recommend_type = models.CharField(
        max_length=20,
        choices=RECOMMEND_TYPE_CHOICES,
        blank=True,
        default='',
        verbose_name='推荐类型'
    )
    
    # 是否推荐
    is_recommended = models.BooleanField(default=False, verbose_name='是否推荐')
    
    # 风险提示
    risk_warnings = models.JSONField(default=list, blank=True, verbose_name='风险提示')
    
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
        """计算综合得分（加权计算）"""
        comparison = self.comparison
        
        # 计算加权总分（权重和应为100%）
        self.total_score = (
            float(self.score_price) * float(comparison.weight_price) / 100 +
            float(self.score_quality) * float(comparison.weight_quality) / 100 +
            float(self.score_delivery) * float(comparison.weight_delivery) / 100 +
            float(self.score_service) * float(comparison.weight_service) / 100 +
            float(self.score_technical) * float(comparison.weight_technical) / 100
        )
        
        # 可靠性得分作为调整系数（如果有历史数据）
        if self.score_reliability > 0:
            # 可靠性得分在80分以上不调整，低于80分每降低10分扣1%
            if self.score_reliability < 80:
                penalty = (80 - float(self.score_reliability)) / 10 * 0.01
                self.total_score *= (1 - penalty)
        
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


# ==================== 非标自动化询价增强模型 ====================

class RFQTemplate(BaseModel):
    """询价模板 - 用于快速创建常用询价单"""
    
    name = models.CharField(max_length=200, verbose_name='模板名称')
    description = models.TextField(blank=True, verbose_name='描述')
    
    # 默认设置
    default_rfq_type = models.CharField(
        max_length=20, choices=RFQ.RFQ_TYPE_CHOICES, default='NORMAL', verbose_name='默认询价类型'
    )
    default_priority = models.CharField(
        max_length=20, choices=RFQ.PRIORITY_CHOICES, default='NORMAL', verbose_name='默认优先级'
    )
    default_deadline_days = models.IntegerField(default=7, verbose_name='默认报价截止天数')
    
    # 默认技术要求
    default_technical_requirements = models.TextField(blank=True, verbose_name='默认技术要求')
    default_quality_requirements = models.TextField(blank=True, verbose_name='默认质量要求')
    default_packaging_requirements = models.TextField(blank=True, verbose_name='默认包装要求')
    default_delivery_requirements = models.TextField(blank=True, verbose_name='默认交货要求')
    
    # 默认供应商列表
    default_suppliers = models.ManyToManyField(
        'masterdata.Supplier', blank=True, related_name='rfq_templates', verbose_name='默认供应商'
    )
    
    # 使用统计
    use_count = models.IntegerField(default=0, verbose_name='使用次数')
    
    class Meta:
        db_table = 'rfq_template'
        verbose_name = '询价模板'
        verbose_name_plural = verbose_name
        ordering = ['-use_count', 'name']
    
    def __str__(self):
        return self.name


class RFQTemplateItem(BaseModel):
    """询价模板物料明细"""
    
    template = models.ForeignKey(
        RFQTemplate, on_delete=models.CASCADE, related_name='items', verbose_name='询价模板'
    )
    item = models.ForeignKey(
        'masterdata.Item', on_delete=models.CASCADE, related_name='rfq_template_items', verbose_name='物料'
    )
    default_qty = models.DecimalField(max_digits=12, decimal_places=3, default=1, verbose_name='默认数量')
    specifications = models.TextField(blank=True, verbose_name='规格说明')
    technical_specs = models.JSONField(default=dict, blank=True, verbose_name='技术规格')
    
    class Meta:
        db_table = 'rfq_template_item'
        verbose_name = '询价模板物料'
        verbose_name_plural = verbose_name
    
    def __str__(self):
        return f"{self.template.name} - {self.item.name}"


class RFQAttachment(BaseModel):
    """询价单附件"""
    
    CATEGORY_CHOICES = [
        ('DRAWING', '图纸'),
        ('SPECIFICATION', '技术规格书'),
        ('STANDARD', '检验标准'),
        ('SAMPLE_IMAGE', '样品图片'),
        ('3D_MODEL', '3D模型'),
        ('OTHER', '其他'),
    ]
    
    rfq = models.ForeignKey(
        RFQ, on_delete=models.CASCADE, null=True, blank=True,
        related_name='attachments', verbose_name='询价单'
    )
    rfq_line = models.ForeignKey(
        RFQLine, on_delete=models.CASCADE, null=True, blank=True,
        related_name='attachments', verbose_name='询价明细'
    )
    
    file_name = models.CharField(max_length=255, verbose_name='文件名')
    file_path = models.CharField(max_length=500, verbose_name='文件路径')
    file_size = models.IntegerField(default=0, verbose_name='文件大小(字节)')
    file_type = models.CharField(max_length=50, blank=True, verbose_name='文件类型')
    category = models.CharField(
        max_length=20, choices=CATEGORY_CHOICES, default='OTHER', verbose_name='附件类别'
    )
    description = models.TextField(blank=True, verbose_name='描述')
    
    # 版本控制
    version = models.CharField(max_length=20, blank=True, verbose_name='版本')
    
    class Meta:
        db_table = 'rfq_attachment'
        verbose_name = '询价单附件'
        verbose_name_plural = verbose_name
        ordering = ['category', '-created_at']
    
    def __str__(self):
        return f"{self.file_name}"


class SupplierCapability(BaseModel):
    """供应商能力标签"""
    
    CAPABILITY_TYPE_CHOICES = [
        ('PROCESS', '加工工艺'),
        ('MATERIAL', '材料类型'),
        ('SURFACE', '表面处理'),
        ('CERTIFICATION', '认证资质'),
        ('EQUIPMENT', '设备能力'),
    ]
    
    name = models.CharField(max_length=100, verbose_name='能力名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='能力代码')
    capability_type = models.CharField(
        max_length=20, choices=CAPABILITY_TYPE_CHOICES, default='PROCESS', verbose_name='能力类型'
    )
    description = models.TextField(blank=True, verbose_name='描述')
    
    class Meta:
        db_table = 'supplier_capability'
        verbose_name = '供应商能力标签'
        verbose_name_plural = verbose_name
        ordering = ['capability_type', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.get_capability_type_display()})"


class SupplierCapabilityMapping(BaseModel):
    """供应商能力关联"""
    
    supplier = models.ForeignKey(
        'masterdata.Supplier', on_delete=models.CASCADE,
        related_name='capability_mappings', verbose_name='供应商'
    )
    capability = models.ForeignKey(
        SupplierCapability, on_delete=models.CASCADE,
        related_name='supplier_mappings', verbose_name='能力'
    )
    
    # 能力等级 1-5
    level = models.IntegerField(default=3, verbose_name='能力等级')
    notes = models.TextField(blank=True, verbose_name='备注')
    
    # 认证信息（如果是认证类能力）
    certification_no = models.CharField(max_length=100, blank=True, verbose_name='认证编号')
    certification_valid_until = models.DateField(null=True, blank=True, verbose_name='认证有效期')
    
    class Meta:
        db_table = 'supplier_capability_mapping'
        verbose_name = '供应商能力关联'
        verbose_name_plural = verbose_name
        unique_together = ['supplier', 'capability']
    
    def __str__(self):
        return f"{self.supplier.name} - {self.capability.name}"


class ItemCapabilityRequirement(BaseModel):
    """物料能力需求（用于匹配供应商）"""
    
    item = models.ForeignKey(
        'masterdata.Item', on_delete=models.CASCADE,
        related_name='capability_requirements', verbose_name='物料'
    )
    capability = models.ForeignKey(
        SupplierCapability, on_delete=models.CASCADE,
        related_name='item_requirements', verbose_name='能力'
    )
    
    # 最低能力等级要求
    min_level = models.IntegerField(default=1, verbose_name='最低能力等级')
    is_required = models.BooleanField(default=True, verbose_name='是否必须')
    
    class Meta:
        db_table = 'item_capability_requirement'
        verbose_name = '物料能力需求'
        verbose_name_plural = verbose_name
        unique_together = ['item', 'capability']
    
    def __str__(self):
        return f"{self.item.sku} - {self.capability.name}"
