"""
Master data models for Items, Customers, Suppliers, and Warehouses.
"""
from django.db import models
from apps.core.models import BaseModel


class ItemCategory(BaseModel):
    """
    Item category for hierarchical organization.
    """
    name = models.CharField(max_length=100, verbose_name='类别名称')
    code = models.CharField(max_length=50, unique=True, verbose_name='类别编码')
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children',
        verbose_name='上级类别'
    )
    description = models.TextField(blank=True, verbose_name='描述')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    
    class Meta:
        db_table = 'item_category'
        verbose_name = '物料类别'
        verbose_name_plural = verbose_name
        ordering = ['sort_order', 'code']
    
    def __str__(self):
        return self.name


class Item(BaseModel):
    """
    Item master data (物料主数据).
    """
    ITEM_TYPE_CHOICES = [
        ('MATERIAL', '原材料'),
        ('PRODUCT', '产成品'),
        ('SEMI', '半成品'),
        ('SERVICE', '服务'),
    ]
    
    UNIT_CHOICES = [
        ('PCS', '个'),
        ('KG', '千克'),
        ('M', '米'),
        ('M2', '平方米'),
        ('M3', '立方米'),
        ('SET', '套'),
        ('BOX', '箱'),
        ('PACK', '包'),
        ('HOUR', '小时'),
    ]
    
    TAX_RATE_CHOICES = [
        (0, '0%'),
        (1, '1%'),
        (3, '3%'),
        (6, '6%'),
        (9, '9%'),
        (13, '13%'),
    ]
    
    sku = models.CharField(max_length=100, unique=True, verbose_name='SKU编码')
    name = models.CharField(max_length=200, verbose_name='物料名称')
    specification = models.CharField(max_length=200, blank=True, verbose_name='规格型号')
    
    # 品牌型号相关
    brand = models.CharField(max_length=100, blank=True, verbose_name='品牌')
    model = models.CharField(max_length=100, blank=True, verbose_name='型号')
    manufacturer = models.CharField(max_length=200, blank=True, verbose_name='生产厂家')
    origin_country = models.CharField(max_length=100, blank=True, verbose_name='产地')
    
    category = models.ForeignKey(
        ItemCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='items',
        verbose_name='物料类别'
    )
    item_type = models.CharField(
        max_length=20,
        choices=ITEM_TYPE_CHOICES,
        default='MATERIAL',
        verbose_name='物料类型'
    )
    unit = models.CharField(max_length=20, choices=UNIT_CHOICES, default='PCS', verbose_name='单位')
    
    # 价格和税率相关
    standard_cost = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name='标准成本'
    )
    purchase_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name='采购单价'
    )
    sale_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name='销售单价'
    )
    tax_rate = models.IntegerField(
        choices=TAX_RATE_CHOICES,
        default=13,
        verbose_name='税率(%)'
    )
    
    default_supplier = models.ForeignKey(
        'Supplier',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='default_items',
        verbose_name='默认供应商'
    )
    
    # 库存相关
    min_stock = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name='最小库存'
    )
    max_stock = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name='最大库存'
    )
    safety_stock = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name='安全库存'
    )
    lead_time = models.IntegerField(default=0, verbose_name='采购周期(天)')
    
    # 其他信息
    description = models.TextField(blank=True, verbose_name='描述')
    image = models.ImageField(upload_to='items/', blank=True, verbose_name='图片')
    barcode = models.CharField(max_length=100, blank=True, verbose_name='条形码')
    weight = models.DecimalField(max_digits=10, decimal_places=3, default=0, verbose_name='重量(kg)')
    volume = models.DecimalField(max_digits=10, decimal_places=3, default=0, verbose_name='体积(m³)')
    shelf_life = models.IntegerField(default=0, verbose_name='保质期(天)')
    is_active = models.BooleanField(default=True, verbose_name='激活状态')
    
    class Meta:
        db_table = 'item'
        verbose_name = '物料'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.sku} - {self.name}"


class Customer(BaseModel):
    """
    Customer master data (客户主数据).
    """
    STATUS_CHOICES = [
        ('ACTIVE', '激活'),
        ('INACTIVE', '停用'),
        ('POTENTIAL', '潜在客户'),
    ]
    
    code = models.CharField(max_length=50, unique=True, verbose_name='客户编码')
    name = models.CharField(max_length=200, verbose_name='客户名称')
    short_name = models.CharField(max_length=100, blank=True, verbose_name='简称')
    contact_person = models.CharField(max_length=100, blank=True, verbose_name='联系人')
    phone = models.CharField(max_length=50, blank=True, verbose_name='电话')
    email = models.EmailField(blank=True, verbose_name='邮箱')
    address = models.TextField(blank=True, verbose_name='地址')
    credit_limit = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name='信用额度'
    )
    payment_terms = models.CharField(max_length=100, blank=True, verbose_name='付款条款')
    tax_number = models.CharField(max_length=100, blank=True, verbose_name='税号')
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='ACTIVE',
        verbose_name='状态'
    )
    notes = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'customer'
        verbose_name = '客户'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class Supplier(BaseModel):
    """
    Supplier master data (供应商主数据).
    """
    STATUS_CHOICES = [
        ('ACTIVE', '激活'),
        ('INACTIVE', '停用'),
        ('POTENTIAL', '潜在供应商'),
    ]
    
    code = models.CharField(max_length=50, unique=True, verbose_name='供应商编码')
    name = models.CharField(max_length=200, verbose_name='供应商名称')
    short_name = models.CharField(max_length=100, blank=True, verbose_name='简称')
    contact_person = models.CharField(max_length=100, blank=True, verbose_name='联系人')
    phone = models.CharField(max_length=50, blank=True, verbose_name='电话')
    email = models.EmailField(blank=True, verbose_name='邮箱')
    address = models.TextField(blank=True, verbose_name='地址')
    payment_terms = models.CharField(max_length=100, blank=True, verbose_name='付款条款')
    tax_number = models.CharField(max_length=100, blank=True, verbose_name='税号')
    bank_name = models.CharField(max_length=200, blank=True, verbose_name='开户银行')
    bank_account = models.CharField(max_length=100, blank=True, verbose_name='银行账号')
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='ACTIVE',
        verbose_name='状态'
    )
    notes = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'supplier'
        verbose_name = '供应商'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class Warehouse(BaseModel):
    """
    Warehouse master data (仓库主数据).
    """
    TYPE_CHOICES = [
        ('MAIN', '主仓库'),
        ('BRANCH', '分仓库'),
        ('TRANSIT', '中转仓'),
        ('VIRTUAL', '虚拟仓'),
    ]
    
    code = models.CharField(max_length=50, unique=True, verbose_name='仓库编码')
    name = models.CharField(max_length=200, verbose_name='仓库名称')
    warehouse_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default='MAIN',
        verbose_name='仓库类型'
    )
    address = models.TextField(blank=True, verbose_name='地址')
    manager = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_warehouses',
        verbose_name='仓库管理员'
    )
    contact_phone = models.CharField(max_length=50, blank=True, verbose_name='联系电话')
    is_active = models.BooleanField(default=True, verbose_name='激活状态')
    notes = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'warehouse'
        verbose_name = '仓库'
        verbose_name_plural = verbose_name
        ordering = ['code']
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class WarehouseLocation(BaseModel):
    """
    Warehouse Location (库位) - for detailed storage management.
    Supports hierarchical structure: Zone -> Aisle -> Rack -> Shelf -> Bin
    """
    LOCATION_TYPE_CHOICES = [
        ('ZONE', '区域'),
        ('AISLE', '通道'),
        ('RACK', '货架'),
        ('SHELF', '层'),
        ('BIN', '库位'),
    ]
    
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.CASCADE,
        related_name='locations',
        verbose_name='仓库'
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        verbose_name='上级库位'
    )
    code = models.CharField(max_length=50, verbose_name='库位编码')
    name = models.CharField(max_length=100, verbose_name='库位名称')
    location_type = models.CharField(
        max_length=20,
        choices=LOCATION_TYPE_CHOICES,
        default='BIN',
        verbose_name='库位类型'
    )
    # Full path code like "A-01-03-02" for easier search
    full_path = models.CharField(max_length=200, blank=True, verbose_name='完整路径')
    
    # Capacity limits
    max_weight = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='最大承重(kg)'
    )
    max_volume = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='最大容积(m³)'
    )
    
    # Status
    is_active = models.BooleanField(default=True, verbose_name='启用')
    is_pickable = models.BooleanField(default=True, verbose_name='可拣货')
    is_storable = models.BooleanField(default=True, verbose_name='可存储')
    
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    notes = models.TextField(blank=True, verbose_name='备注')
    
    class Meta:
        db_table = 'warehouse_location'
        verbose_name = '库位'
        verbose_name_plural = verbose_name
        unique_together = ['warehouse', 'code']
        ordering = ['warehouse', 'sort_order', 'code']
    
    def __str__(self):
        return f"{self.warehouse.code}-{self.full_path or self.code}"
    
    def save(self, *args, **kwargs):
        # Auto-generate full path
        if self.parent:
            self.full_path = f"{self.parent.full_path}-{self.code}" if self.parent.full_path else f"{self.parent.code}-{self.code}"
        else:
            self.full_path = self.code
        super().save(*args, **kwargs)
    
    def get_descendants(self):
        """Get all descendant locations."""
        descendants = list(self.children.all())
        for child in self.children.all():
            descendants.extend(child.get_descendants())
        return descendants

