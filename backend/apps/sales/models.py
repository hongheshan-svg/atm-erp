"""
Sales management models - Quotation, SO, Delivery Order.
"""
from django.db import models
from apps.core.models import BaseModel
from apps.core.utils import generate_code


class SalesQuotation(BaseModel):
    """
    Sales Quotation - 销售报价单
    """
    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('SENT', '已发送'),
        ('ACCEPTED', '已接受'),
        ('REJECTED', '已拒绝'),
        ('EXPIRED', '已过期'),
    ]
    
    TAX_RATE_CHOICES = [
        (0, '0% (免税)'),
        (1, '1%'),
        (3, '3%'),
        (6, '6%'),
        (9, '9%'),
        (13, '13%'),
    ]
    
    quote_no = models.CharField(max_length=50, unique=True, verbose_name='报价单号')
    customer = models.ForeignKey(
        'masterdata.Customer',
        on_delete=models.PROTECT,
        related_name='quotations',
        verbose_name='客户'
    )
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='quotations',
        verbose_name='关联项目'
    )
    quote_date = models.DateField(auto_now_add=True, verbose_name='报价日期')
    valid_until = models.DateField(verbose_name='有效期至')
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='DRAFT',
        verbose_name='状态'
    )
    version = models.IntegerField(default=1, verbose_name='版本号')
    
    # 税率相关
    tax_rate = models.IntegerField(
        choices=TAX_RATE_CHOICES,
        default=13,
        verbose_name='增值税税率(%)'
    )
    total_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name='不含税金额'
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
    notes = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'sales_quotation'
        verbose_name = '销售报价'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.quote_no}"
    
    def save(self, *args, **kwargs):
        if not self.quote_no:
            self.quote_no = generate_code('QT', rule_type='SALES_QUOTE')
        super().save(*args, **kwargs)


class SalesQuotationLine(BaseModel):
    """
    Sales Quotation Line - 销售报价明细
    NOTE: 非标定制项目支持手动填写产品信息，item 为可选
    """
    quotation = models.ForeignKey(
        SalesQuotation,
        on_delete=models.CASCADE,
        related_name='lines',
        verbose_name='销售报价'
    )
    # 物料关联（可选，非标产品可不选）
    item = models.ForeignKey(
        'masterdata.Item',
        on_delete=models.PROTECT,
        related_name='quotation_lines',
        verbose_name='物料',
        null=True,
        blank=True
    )
    # 手动填写的产品信息（非标定制用）
    custom_name = models.CharField(max_length=200, blank=True, verbose_name='产品名称')
    custom_spec = models.CharField(max_length=200, blank=True, verbose_name='规格型号')
    custom_unit = models.CharField(max_length=50, blank=True, default='件', verbose_name='单位')
    
    qty = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='数量')
    unit_price = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='单价')
    line_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name='行金额'
    )
    notes = models.TextField(blank=True, verbose_name='备注')
    
    @property
    def display_name(self):
        """返回产品显示名称"""
        if self.item:
            return self.item.name
        return self.custom_name or '未命名产品'
    
    class Meta:
        db_table = 'sales_quotation_line'
        verbose_name = '销售报价明细'
        verbose_name_plural = verbose_name
        ordering = ['id']
    
    def __str__(self):
        return f"{self.quotation.quote_no} - {self.item.sku}"
    
    def save(self, *args, **kwargs):
        self.line_amount = self.qty * self.unit_price
        super().save(*args, **kwargs)


class SalesOrder(BaseModel):
    """
    Sales Order (SO) - 销售订单
    NOTE: project is OPTIONAL - some orders are placed before project creation (e.g. custom orders)
    """
    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('PENDING', '审批中'),
        ('REJECTED', '已拒绝'),
        ('CONFIRMED', '已确认'),
        ('PARTIAL', '部分发货'),
        ('COMPLETED', '完成'),
        ('CANCELLED', '已取消'),
    ]
    
    TAX_RATE_CHOICES = [
        (0, '0% (免税)'),
        (1, '1%'),
        (3, '3%'),
        (6, '6%'),
        (9, '9%'),
        (13, '13%'),
    ]
    
    # 付款条款选项 - 账期/分期
    PAYMENT_TERMS_CHOICES = [
        ('FULL_PREPAY', '全款预付'),
        ('COD', '货到付款'),
        ('NET30', '月结30天'),
        ('NET60', '月结60天'),
        ('NET90', '月结90天'),
        ('M_30_70', '30%预付/70%发货前'),
        ('M_30_30_40', '30%预付/30%发货前/40%验收后'),
        ('M_30_30_30_10', '30%预付/30%发货前/30%验收/10%质保'),
        ('M_30_60_10', '30%预付/60%验收/10%质保'),
        ('M_50_40_10', '50%预付/40%验收/10%质保'),
        ('M_40_50_10', '40%预付/50%验收/10%质保'),
        ('M_20_70_10', '20%预付/70%验收/10%质保'),
        ('CUSTOM', '自定义分期'),
        ('OTHER', '其他'),
    ]
    
    # 付款方式选项
    PAYMENT_METHOD_CHOICES = [
        ('WIRE', '电汇'),
        ('ACCEPTANCE', '承兑汇票'),
        ('CHECK', '支票'),
        ('CASH', '现金'),
        ('LC', '信用证'),
        ('OTHER', '其他'),
    ]
    
    order_no = models.CharField(max_length=50, unique=True, verbose_name='订单号')
    customer = models.ForeignKey(
        'masterdata.Customer',
        on_delete=models.PROTECT,
        related_name='sales_orders',
        verbose_name='客户'
    )
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.PROTECT,
        related_name='sales_orders',
        verbose_name='关联项目',
        null=True,
        blank=True
    )
    order_date = models.DateField(auto_now_add=True, verbose_name='订单日期')
    delivery_date = models.DateField(verbose_name='交货日期')
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='DRAFT',
        verbose_name='状态'
    )
    
    # 税率相关
    tax_rate = models.IntegerField(
        choices=TAX_RATE_CHOICES,
        default=13,
        verbose_name='增值税税率(%)'
    )
    total_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name='不含税金额'
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
    
    # 付款条款与方式
    payment_terms = models.CharField(
        max_length=20,
        choices=PAYMENT_TERMS_CHOICES,
        default='M_30_30_30_10',
        verbose_name='付款条款'
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default='WIRE',
        verbose_name='付款方式'
    )
    payment_terms_detail = models.CharField(max_length=500, blank=True, verbose_name='付款条款说明')
    notes = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'sales_order'
        verbose_name = '销售订单'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.order_no}"
    
    def save(self, *args, **kwargs):
        if not self.order_no:
            self.order_no = generate_code('SO', rule_type='SALES_ORDER')
        super().save(*args, **kwargs)


class SalesOrderLine(BaseModel):
    """
    Sales Order Line - 销售订单明细
    NOTE: 非标定制项目支持手动填写产品信息，item 为可选
    """
    so = models.ForeignKey(
        SalesOrder,
        on_delete=models.CASCADE,
        related_name='lines',
        verbose_name='销售订单'
    )
    # 物料关联（可选，非标产品可不选）
    item = models.ForeignKey(
        'masterdata.Item',
        on_delete=models.PROTECT,
        related_name='so_lines',
        verbose_name='物料',
        null=True,
        blank=True
    )
    # 手动填写的产品信息（非标定制用）
    custom_name = models.CharField(max_length=200, blank=True, verbose_name='产品名称')
    custom_spec = models.CharField(max_length=200, blank=True, verbose_name='规格型号')
    custom_unit = models.CharField(max_length=50, blank=True, default='件', verbose_name='单位')
    
    qty = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='订购数量')
    unit_price = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='单价')
    line_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name='行金额'
    )
    delivered_qty = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name='已发货数量'
    )
    notes = models.TextField(blank=True, verbose_name='备注')
    
    @property
    def display_name(self):
        """返回产品显示名称"""
        if self.item:
            return self.item.name
        return self.custom_name or '未命名产品'
    
    @property
    def display_spec(self):
        """返回产品规格"""
        if self.item:
            return self.item.spec or ''
        return self.custom_spec or ''
    
    class Meta:
        db_table = 'sales_order_line'
        verbose_name = '销售订单明细'
        verbose_name_plural = verbose_name
        ordering = ['id']
    
    def __str__(self):
        return f"{self.so.order_no} - {self.item.sku}"
    
    def save(self, *args, **kwargs):
        self.line_amount = self.qty * self.unit_price
        super().save(*args, **kwargs)


class DeliveryOrder(BaseModel):
    """
    Delivery Order (DO) - 发货单
    
    完整发货流程:
    1. 销售发货通知 (DRAFT)
    2. 项目申请发货 (PENDING) - 进入审批流程，由流程配置决定审批步骤
    3. 审批通过后进入备货 (PREPARING)
    4. 采购预约物流 (LOGISTICS_BOOKING)
    5. 客户签署送货单 (CUSTOMER_SIGNING)
    6. 采购上传送货单 (UPLOADING_RECEIPT)
    7. 项目确认 (PROJECT_CONFIRMING)
    8. 完成 (COMPLETED)
    
    注意: 审批步骤由审批中心的流程配置决定，修改流程配置会影响审批流程
    """
    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('SUBMITTED', '已提交'),  # 兼容旧数据
        ('PENDING', '审批中'),  # 审批流程由流程配置决定
        ('APPROVED', '已审批'),  # 审批通过，准备进入操作流程
        ('PREPARING', '备货中'),
        ('LOGISTICS_BOOKING', '预约物流中'),
        ('CUSTOMER_SIGNING', '待客户签收'),
        ('UPLOADING_RECEIPT', '待上传送货单'),
        ('PROJECT_CONFIRMING', '待项目确认'),
        ('COMPLETED', '已完成'),
        ('REJECTED', '已拒绝'),
    ]
    
    PACKAGING_CHOICES = [
        ('STANDARD', '标准包装'),
        ('WOODEN_CASE', '木箱包装'),
        ('CARTON', '纸箱包装'),
        ('PALLET', '托盘包装'),
        ('CUSTOM', '特殊包装'),
    ]
    
    delivery_no = models.CharField(max_length=50, unique=True, verbose_name='发货单号')
    so = models.ForeignKey(
        SalesOrder,
        on_delete=models.PROTECT,
        related_name='deliveries',
        verbose_name='销售订单'
    )
    warehouse = models.ForeignKey(
        'masterdata.Warehouse',
        on_delete=models.PROTECT,
        related_name='deliveries',
        verbose_name='发货仓库'
    )
    delivery_date = models.DateField(verbose_name='计划发货日期')
    actual_delivery_date = models.DateField(null=True, blank=True, verbose_name='实际发货日期')
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='DRAFT',
        verbose_name='状态'
    )
    
    # 收货信息
    receiver_name = models.CharField(max_length=100, blank=True, verbose_name='收货人')
    receiver_phone = models.CharField(max_length=50, blank=True, verbose_name='收货电话')
    receiver_address = models.TextField(blank=True, verbose_name='收货地址')
    
    # 包装、保险、物流要求
    packaging_type = models.CharField(
        max_length=20,
        choices=PACKAGING_CHOICES,
        default='STANDARD',
        verbose_name='包装方式'
    )
    packaging_notes = models.TextField(blank=True, verbose_name='包装要求说明')
    needs_insurance = models.BooleanField(default=False, verbose_name='需要保险')
    insurance_amount = models.DecimalField(
        max_digits=15, decimal_places=2, 
        null=True, blank=True, 
        verbose_name='保险金额'
    )
    
    # 物流信息
    logistics_company = models.CharField(max_length=100, blank=True, verbose_name='物流公司')
    logistics_contact = models.CharField(max_length=100, blank=True, verbose_name='物流联系人')
    logistics_phone = models.CharField(max_length=50, blank=True, verbose_name='物流电话')
    tracking_number = models.CharField(max_length=100, blank=True, verbose_name='物流单号')
    logistics_notes = models.TextField(blank=True, verbose_name='物流要求')
    logistics_cost = models.DecimalField(
        max_digits=15, decimal_places=2, 
        null=True, blank=True, 
        verbose_name='物流费用'
    )
    
    # 送货单签收
    signed_receipt = models.FileField(
        upload_to='delivery_receipts/', 
        null=True, blank=True, 
        verbose_name='签收单据'
    )
    signed_date = models.DateField(null=True, blank=True, verbose_name='签收日期')
    signed_by = models.CharField(max_length=100, blank=True, verbose_name='签收人')
    
    notes = models.TextField(blank=True, verbose_name='备注')
    rejection_reason = models.TextField(blank=True, verbose_name='拒绝原因')
    
    class Meta:
        db_table = 'delivery_order'
        verbose_name = '发货单'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.delivery_no}"
    
    def save(self, *args, **kwargs):
        if not self.delivery_no:
            self.delivery_no = generate_code('DO', rule_type='DELIVERY_ORDER')
        super().save(*args, **kwargs)
    
    @property
    def total_amount(self):
        """计算发货单总金额"""
        total = 0
        for line in self.lines.filter(is_deleted=False):
            total += line.qty * line.so_line.unit_price
        return total


class DeliveryOrderLine(BaseModel):
    """
    Delivery Order Line - 发货明细
    NOTE: item 为可选，因为 SalesOrderLine 支持非标产品（item 可为空）
    """
    delivery = models.ForeignKey(
        DeliveryOrder,
        on_delete=models.CASCADE,
        related_name='lines',
        verbose_name='发货单'
    )
    so_line = models.ForeignKey(
        SalesOrderLine,
        on_delete=models.PROTECT,
        related_name='delivery_lines',
        verbose_name='销售订单明细'
    )
    item = models.ForeignKey(
        'masterdata.Item',
        on_delete=models.PROTECT,
        related_name='delivery_lines',
        verbose_name='物料',
        null=True,
        blank=True
    )
    qty = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='发货数量')
    notes = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'delivery_order_line'
        verbose_name = '发货明细'
        verbose_name_plural = verbose_name
        ordering = ['id']
    
    def __str__(self):
        item_desc = self.item.sku if self.item else self.so_line.display_name
        return f"{self.delivery.delivery_no} - {item_desc}"


class SalesContract(BaseModel):
    """
    Sales Contract - 销售合同
    """
    STATUS_CHOICES = [
        ('DRAFT', '草稿'),
        ('PENDING', '待审批'),
        ('APPROVED', '已审批'),
        ('SIGNED', '已签署'),
        ('COMPLETED', '已完成'),
        ('CANCELLED', '已取消'),
    ]
    
    contract_no = models.CharField(max_length=50, unique=True, verbose_name='合同编号')
    so = models.ForeignKey(
        SalesOrder,
        on_delete=models.CASCADE,
        related_name='contracts',
        verbose_name='销售订单'
    )
    customer = models.ForeignKey(
        'masterdata.Customer',
        on_delete=models.PROTECT,
        related_name='sales_contracts',
        verbose_name='客户'
    )
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sales_contracts',
        verbose_name='关联项目'
    )
    
    # 合同信息
    title = models.CharField(max_length=200, verbose_name='合同标题')
    contract_date = models.DateField(verbose_name='合同日期')
    effective_date = models.DateField(null=True, blank=True, verbose_name='生效日期')
    expiry_date = models.DateField(null=True, blank=True, verbose_name='到期日期')
    
    # 金额
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='合同金额')
    tax_rate = models.IntegerField(default=13, verbose_name='税率(%)')
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='税额')
    total_with_tax = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='含税总额')
    
    # 条款
    payment_terms = models.TextField(blank=True, verbose_name='付款条款')
    delivery_terms = models.TextField(blank=True, verbose_name='交货条款')
    quality_terms = models.TextField(blank=True, verbose_name='质量条款')
    warranty_terms = models.TextField(blank=True, verbose_name='质保条款')
    
    # 签署信息
    buyer_signer = models.CharField(max_length=100, blank=True, verbose_name='甲方签署人')
    seller_signer = models.CharField(max_length=100, blank=True, verbose_name='乙方签署人')
    signed_date = models.DateField(null=True, blank=True, verbose_name='签署日期')
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='DRAFT',
        verbose_name='状态'
    )
    notes = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'sales_contract'
        verbose_name = '销售合同'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.contract_no}"
    
    def save(self, *args, **kwargs):
        if not self.contract_no:
            self.contract_no = generate_code('SC', rule_type='SALES_CONTRACT')
        super().save(*args, **kwargs)


# Import models from win_loss_analysis
from .win_loss_analysis import WinLossReason, OpportunityCloseRecord



# Import models from marketing
from .marketing import MarketingEmailTemplate, MarketingCampaign, CampaignRecipient, EmailSendLog

# Import models from ai_prediction
from .ai_prediction import SalesPrediction, CustomerChurnRisk

# Import models from sms_marketing
from .sms_marketing import SMSTemplate, SMSCampaign, SMSRecipient, SMSSendLog

# Import models from wechat_marketing
from .wechat_marketing import (
    WeChatOfficialAccount, WeChatFollower, WeChatTemplate,
    WeChatCampaign, WeChatMessageLog
)
