from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q

from apps.core.models import BaseModel, ImmutableLedger, LedgerModel


def money(**kwargs):
    return models.DecimalField(max_digits=18, decimal_places=2, default=0, **kwargs)


def quantity(**kwargs):
    return models.DecimalField(max_digits=18, decimal_places=3, default=0, **kwargs)


class Item(BaseModel):
    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=150)
    specification = models.CharField(max_length=250, blank=True)
    unit = models.CharField(max_length=20, default='件')
    is_active = models.BooleanField(default=True)

    class Meta(BaseModel.Meta):
        db_table = 'lean_item'


class Partner(BaseModel):
    class Kind(models.TextChoices):
        CUSTOMER = 'customer', '客户'
        SUPPLIER = 'supplier', '供应商'
        BOTH = 'both', '客户及供应商'

    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=150)
    kind = models.CharField(max_length=20, choices=Kind.choices)
    contact = models.CharField(max_length=80, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    address = models.CharField(max_length=250, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta(BaseModel.Meta):
        db_table = 'lean_partner'


class Project(BaseModel):
    class Status(models.TextChoices):
        DRAFT = 'draft', '需求中'
        QUOTED = 'quoted', '已报价'
        ACTIVE = 'active', '执行中'
        DELIVERING = 'delivering', '交付中'
        WARRANTY = 'warranty', '已验收'
        CLOSED = 'closed', '已结项'
        CANCELLED = 'cancelled', '已取消'

    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=150)
    customer = models.ForeignKey(Partner, models.PROTECT, related_name='projects')
    manager = models.ForeignKey(settings.AUTH_USER_MODEL, models.PROTECT, related_name='managed_projects')
    members = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='projects', db_table='lean_project_member')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    requirements = models.TextField(blank=True)
    due_date = models.DateField(null=True, blank=True)
    equipment_quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    warranty_months = models.PositiveIntegerField(default=12)
    close_reason = models.TextField(blank=True)

    class Meta(BaseModel.Meta):
        db_table = 'lean_project'
        constraints = [
            models.CheckConstraint(condition=Q(equipment_quantity__gt=0), name='lean_equipment_positive'),
        ]

    # Read-only projections: commercial facts belong to the sales order.
    @property
    def quote_amount(self):
        return self.sale.quote_amount if hasattr(self, 'sale') else Decimal('0.00')

    @property
    def contract_amount(self):
        return self.sale.contract_amount if hasattr(self, 'sale') else Decimal('0.00')

    @property
    def contract_date(self):
        return self.sale.contract_date if hasattr(self, 'sale') else None


class SalesOrder(BaseModel):
    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=150)
    customer = models.ForeignKey(Partner, models.PROTECT, related_name='sales')
    manager = models.ForeignKey(settings.AUTH_USER_MODEL, models.PROTECT, related_name='managed_sales')
    project = models.OneToOneField(Project, models.PROTECT, related_name='sale', null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[('draft', '需求中'), ('quoted', '已报价'), ('signed', '已签约'), ('cancelled', '已取消')],
        default='draft',
    )
    requirements = models.TextField(blank=True)
    due_date = models.DateField(null=True, blank=True)
    equipment_quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    warranty_months = models.PositiveIntegerField(default=12)
    quote_amount = money()
    contract_amount = money()
    contract_date = models.DateField(null=True, blank=True)

    class Meta(BaseModel.Meta):
        db_table = 'lean_sales_order'
        constraints = [
            models.CheckConstraint(condition=Q(quote_amount__gte=0, contract_amount__gte=0), name='lean_sales_amounts'),
            models.CheckConstraint(condition=Q(equipment_quantity__gt=0), name='lean_sales_equipment_positive'),
        ]


class BOMLine(BaseModel):
    project = models.ForeignKey(Project, models.PROTECT, related_name='bom_lines')
    item = models.ForeignKey(Item, models.PROTECT)
    quantity = quantity(validators=[MinValueValidator(Decimal('0.001'))])
    change_note = models.CharField(max_length=500, blank=True)

    class Meta(BaseModel.Meta):
        db_table = 'lean_bom_line'
        constraints = [
            models.UniqueConstraint(
                fields=['project', 'item'], condition=Q(is_deleted=False), name='lean_live_bom_item'
            ),
            models.CheckConstraint(condition=Q(quantity__gt=0), name='lean_bom_positive'),
        ]


class PurchaseOrder(BaseModel):
    class Status(models.TextChoices):
        DRAFT = 'draft', '草稿'
        SUBMITTED = 'submitted', '待批准'
        APPROVED = 'approved', '待收货'
        PARTIAL = 'partial', '部分收货'
        RECEIVED = 'received', '已收货'
        CANCELLED = 'cancelled', '已取消'

    code = models.CharField(max_length=30, unique=True)
    project = models.ForeignKey(Project, models.PROTECT, related_name='purchases')
    supplier = models.ForeignKey(Partner, models.PROTECT)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    due_date = models.DateField()
    note = models.CharField(max_length=500, blank=True)

    class Meta(BaseModel.Meta):
        db_table = 'lean_purchase'


class PurchaseLine(BaseModel):
    purchase = models.ForeignKey(PurchaseOrder, models.PROTECT, related_name='lines')
    item = models.ForeignKey(Item, models.PROTECT)
    bom_line = models.ForeignKey(BOMLine, models.PROTECT, null=True, blank=True)
    quantity = quantity(validators=[MinValueValidator(Decimal('0.001'))])
    unit_price = money(validators=[MinValueValidator(0)])
    received_quantity = models.DecimalField(max_digits=18, decimal_places=3, default=0)
    cancelled_quantity = models.DecimalField(max_digits=18, decimal_places=3, default=0)
    returned_quantity = models.DecimalField(max_digits=18, decimal_places=3, default=0)

    class Meta(BaseModel.Meta):
        db_table = 'lean_purchase_line'
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gt=0, unit_price__gte=0), name='lean_purchase_positive'),
            models.CheckConstraint(
                condition=Q(received_quantity__gte=0, cancelled_quantity__gte=0, returned_quantity__gte=0),
                name='lean_purchase_progress_nonnegative',
            ),
            models.CheckConstraint(
                condition=Q(quantity__gte=F('received_quantity') + F('cancelled_quantity')),
                name='lean_purchase_no_overreceive',
            ),
            models.CheckConstraint(
                condition=Q(returned_quantity__lte=F('received_quantity')), name='lean_purchase_no_overreturn'
            ),
        ]


class Stock(LedgerModel):
    item = models.ForeignKey(Item, models.PROTECT)
    location = models.CharField(max_length=80, default='主仓')
    quantity = quantity()
    value = money()

    class Meta(LedgerModel.Meta):
        db_table = 'lean_stock'
        constraints = [
            models.UniqueConstraint(fields=['item', 'location'], name='lean_stock_location'),
            models.CheckConstraint(condition=Q(quantity__gte=0, value__gte=0), name='lean_stock_nonnegative'),
            models.CheckConstraint(condition=Q(quantity__gt=0) | Q(value=0), name='lean_empty_stock_zero_value'),
        ]


class Delivery(BaseModel):
    code = models.CharField(max_length=30, unique=True)
    project = models.ForeignKey(Project, models.PROTECT, related_name='deliveries')
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    shipped_date = models.DateField()
    accepted_date = models.DateField(null=True, blank=True)
    warranty_until = models.DateField(null=True, blank=True)
    note = models.CharField(max_length=500, blank=True)

    class Meta(BaseModel.Meta):
        db_table = 'lean_delivery'
        constraints = [models.CheckConstraint(condition=Q(quantity__gt=0), name='lean_delivery_positive')]


class Task(BaseModel):
    class Kind(models.TextChoices):
        DESIGN = 'design', '设计'
        ASSEMBLY = 'assembly', '装配'
        TEST = 'test', '调试'
        INSTALL = 'install', '安装'
        ACCEPTANCE = 'acceptance', '验收'
        SERVICE = 'service', '售后'

    class Status(models.TextChoices):
        OPEN = 'open', '待完成'
        DONE = 'done', '已完成'
        CANCELLED = 'cancelled', '已取消'

    project = models.ForeignKey(Project, models.PROTECT, related_name='tasks')
    delivery = models.ForeignKey(Delivery, models.PROTECT, null=True, blank=True, related_name='tasks')
    kind = models.CharField(max_length=20, choices=Kind.choices)
    title = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, models.PROTECT)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    due_date = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    service_date = models.DateField(null=True, blank=True)

    class Meta(BaseModel.Meta):
        db_table = 'lean_task'


class StockMove(ImmutableLedger):
    class Kind(models.TextChoices):
        OPENING = 'opening', '期初'
        RECEIPT = 'receipt', '采购收货'
        ISSUE = 'issue', '项目领料'
        RETURN = 'return', '项目退料'
        PURCHASE_RETURN = 'purchase_return', '采购退货'
        COUNT = 'count', '盘点'

    stock = models.ForeignKey(Stock, models.PROTECT, related_name='moves')
    project = models.ForeignKey(Project, models.PROTECT, null=True, blank=True, related_name='stock_moves')
    task = models.ForeignKey(Task, models.PROTECT, null=True, blank=True)
    purchase_line = models.ForeignKey(PurchaseLine, models.PROTECT, null=True, blank=True)
    source = models.ForeignKey('self', models.PROTECT, null=True, blank=True, related_name='returns')
    kind = models.CharField(max_length=30, choices=Kind.choices)
    quantity = quantity()
    value = money()
    supplier_credit = money()
    reason = models.CharField(max_length=500)

    class Meta(LedgerModel.Meta):
        db_table = 'lean_stock_move'


class Entry(LedgerModel):
    class Kind(models.TextChoices):
        RECEIVABLE = 'receivable', '应收'
        PAYABLE = 'payable', '应付'
        EXPENSE = 'expense', '费用'

    project = models.ForeignKey(Project, models.PROTECT, related_name='entries')
    purchase = models.OneToOneField(PurchaseOrder, models.PROTECT, null=True, blank=True, related_name='entry')
    task = models.OneToOneField(Task, models.PROTECT, null=True, blank=True, related_name='entry')
    kind = models.CharField(max_length=20, choices=Kind.choices)
    title = models.CharField(max_length=150)
    amount = money()
    credit_amount = money()
    due_date = models.DateField()
    cancelled = models.BooleanField(default=False)

    class Meta(LedgerModel.Meta):
        db_table = 'lean_entry'
        constraints = [
            models.CheckConstraint(condition=Q(amount__gte=0, credit_amount__gte=0), name='lean_entry_nonnegative'),
            models.CheckConstraint(condition=Q(credit_amount__lte=F('amount')), name='lean_entry_credit_limit'),
        ]


class Payment(ImmutableLedger):
    entry = models.ForeignKey(Entry, models.PROTECT, related_name='payments')
    amount = money()
    date = models.DateField()
    reason = models.CharField(max_length=500)
    reversal_of = models.OneToOneField('self', models.PROTECT, null=True, blank=True, related_name='reversal')

    class Meta(LedgerModel.Meta):
        db_table = 'lean_payment'
        constraints = [models.CheckConstraint(condition=~Q(amount=0), name='lean_payment_nonzero')]


class TimeEntry(ImmutableLedger):
    task = models.ForeignKey(Task, models.PROTECT, related_name='time_entries')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, models.PROTECT)
    date = models.DateField()
    hours = models.DecimalField(max_digits=6, decimal_places=2)
    hourly_cost = money()
    cost = money()
    reason = models.CharField(max_length=500)
    reversal_of = models.OneToOneField('self', models.PROTECT, null=True, blank=True, related_name='reversal')
    correction_of = models.OneToOneField('self', models.PROTECT, null=True, blank=True, related_name='correction')

    class Meta(LedgerModel.Meta):
        db_table = 'lean_time_entry'
        constraints = [
            models.CheckConstraint(
                condition=~Q(hours=0) & Q(hours__gte=-24, hours__lte=24, hourly_cost__gte=0),
                name='lean_time_hours_range',
            )
        ]


class Document(BaseModel):
    class Category(models.TextChoices):
        DRAWING = 'drawing', '图纸'
        CONTRACT = 'contract', '合同'
        RECEIPT = 'receipt', '结算凭证'
        DELIVERY = 'delivery', '交付验收'
        OTHER = 'other', '其他'

    project = models.ForeignKey(Project, models.PROTECT, related_name='documents')
    category = models.CharField(max_length=20, choices=Category.choices)
    file = models.FileField(upload_to='protected/%Y/%m/')
    original_name = models.CharField(max_length=250)
    sha256 = models.CharField(max_length=64)
    size = models.PositiveIntegerField()

    class Meta(BaseModel.Meta):
        db_table = 'lean_document'
