from decimal import Decimal

from django.conf import settings
from django.contrib.postgres.indexes import HashIndex
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import CharField, F, Func, Q, Value
from django.db.models.functions import Lower

from apps.core.models import BaseModel, ImmutableLedger, LedgerModel


def comparison_expression(field):
    """物料查重用的规范化文本：全角 ASCII 转半角、去掉全部空白、转小写。

    查重查询（services.masterdata）与下方函数索引共用这一表达式，数据库才能按索引精确匹配；
    TRANSLATE、REGEXP_REPLACE 和 LOWER 都是不可变函数，可以建函数索引。最终身份核对仍使用完整字段。
    """
    translated = Func(
        field,
        Value(''.join(chr(i) for i in range(0xFF01, 0xFF5F)) + '\u3000'),
        Value(''.join(chr(i) for i in range(0x21, 0x7F)) + ' '),
        function='TRANSLATE',
        output_field=CharField(),
    )
    return Lower(
        Func(
            translated,
            Value('[[:space:]]+'),
            Value(''),
            Value('g'),
            function='REGEXP_REPLACE',
            output_field=CharField(),
        )
    )


def money(**kwargs):
    return models.DecimalField(max_digits=18, decimal_places=2, default=0, **kwargs)


def quantity(**kwargs):
    return models.DecimalField(max_digits=18, decimal_places=3, default=0, **kwargs)


class PurchaseContractVersion(ImmutableLedger):
    purchase = models.ForeignKey('PurchaseOrder', models.PROTECT, related_name='contract_versions')
    version = models.PositiveIntegerField()
    snapshot = models.JSONField()
    document = models.ForeignKey('Document', models.PROTECT, related_name='purchase_contract_versions')
    reason = models.CharField(max_length=500)

    class Meta(ImmutableLedger.Meta):
        db_table = 'lean_purchase_contract_version'
        constraints = [
            models.UniqueConstraint(fields=['purchase', 'version'], name='lean_purchase_contract_version_unique')
        ]


class PurchaseWarranty(BaseModel):
    receipt = models.ForeignKey('StockMove', models.PROTECT, related_name='warranty_cases')
    date = models.DateField()
    quantity = quantity()
    description = models.CharField(max_length=500)
    status = models.CharField(
        max_length=20,
        default='open',
        choices=[('open', '待响应'), ('repairing', '维修中'), ('replaced', '已更换'), ('closed', '已关闭')],
    )
    response = models.CharField(max_length=500, blank=True)
    replacement = models.ForeignKey('StockMove', models.PROTECT, null=True, blank=True, related_name='+')
    returned = models.ForeignKey('StockMove', models.PROTECT, null=True, blank=True, related_name='+')
    expense = models.ForeignKey('Entry', models.PROTECT, null=True, blank=True, related_name='+')

    class Meta(BaseModel.Meta):
        db_table = 'lean_purchase_warranty'


class PaymentTerm(models.TextChoices):
    MANUAL = 'manual', '指定付款日期'
    CASH = 'cash', '现付（合格收货日）'
    MONTH30 = 'month30', '月结30天'
    MONTH60 = 'month60', '月结60天'
    MONTH90 = 'month90', '月结90天'
    MONTH120 = 'month120', '月结120天'
    CUSTOM = 'custom', '月结自定义天数'


class Item(BaseModel):
    class ProductCategory(models.TextChoices):
        MACHINED = '11', '有图·机加'
        SHEET_METAL = '12', '有图·钣金'
        SPECIAL = '13', '有图·特殊工艺'
        DRAWING_OTHER = '19', '有图·其它'
        STANDARD = '21', '无图·标准件'
        CONSUMABLE = '22', '无图·耗材辅料'
        OFFICE = '23', '无图·办公用品'
        OTHER = '29', '无图·其它'

    class PartType(models.TextChoices):
        STANDARD = 'standard', '标准件'
        CUSTOM = 'custom', '非标件'

    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=150)
    specification = models.CharField(max_length=2000, blank=True)
    product_category = models.CharField(max_length=2, choices=ProductCategory.choices, blank=True, default='')
    drawing_number = models.CharField(max_length=100, blank=True, default='')
    drawing_revision = models.CharField(max_length=30, blank=True, default='')
    brand = models.CharField(max_length=80, blank=True)
    part_type = models.CharField(max_length=20, choices=PartType.choices, blank=True, default='')
    unit = models.CharField(max_length=20, default='件')
    # 网购件（淘宝、京东等）的商品页链接：采购按链接下单。不参与查重和物料身份，可随时改。
    purchase_url = models.CharField(max_length=1000, blank=True, default='')
    is_active = models.BooleanField(default=True)

    class Meta(BaseModel.Meta):
        db_table = 'lean_item'
        indexes = [
            # 建料、改料和 BOM 物料导入的每一行都要按规范化名称、规格、图号查重；
            # 没有函数索引时这三处都是整表顺序扫描，导入 1000 行就扫 1000 次。
            models.Index(comparison_expression('name'), name='lean_item_name_match'),
            # 规格最长 2000 字，中文可超过 B 树单条索引上限（约 2.7 KB），且查重只做等值比较，用哈希索引。
            HashIndex(comparison_expression('specification'), name='lean_item_spec_match'),
            models.Index(Lower('drawing_number'), Lower('drawing_revision'), name='lean_item_drawing_key'),
        ]


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
    payment_term = models.CharField(max_length=20, choices=PaymentTerm.choices, default=PaymentTerm.MANUAL)
    payment_days = models.PositiveSmallIntegerField(default=30)
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
    task_supervisors = models.JSONField(default=dict, blank=True)
    supervisor_revision = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    requirements = models.TextField(blank=True)
    due_date = models.DateField(null=True, blank=True)
    equipment_quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    warranty_months = models.PositiveIntegerField(default=12)
    close_reason = models.TextField(blank=True)
    budget_materials = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    budget_labor = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    budget_expenses = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    budget_revision = models.PositiveIntegerField(default=0)
    budget_changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, models.PROTECT, null=True, blank=True, related_name='+'
    )
    remaining_labor = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    remaining_expenses = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    forecast_revision = models.PositiveIntegerField(default=0)
    remaining_materials = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    forecast_at = models.DateTimeField(null=True, blank=True)
    forecast_by = models.ForeignKey(settings.AUTH_USER_MODEL, models.PROTECT, null=True, blank=True, related_name='+')

    class Meta(BaseModel.Meta):
        db_table = 'lean_project'
        constraints = [
            models.CheckConstraint(condition=Q(equipment_quantity__gt=0), name='lean_equipment_positive'),
            models.CheckConstraint(
                condition=Q(budget_materials__isnull=True, budget_labor__isnull=True, budget_expenses__isnull=True)
                | Q(
                    budget_materials__isnull=False,
                    budget_materials__gte=0,
                    budget_labor__isnull=False,
                    budget_labor__gte=0,
                    budget_expenses__isnull=False,
                    budget_expenses__gte=0,
                ),
                name='lean_project_budget_valid',
            ),
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
    original_contract_amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    code = models.CharField(max_length=30, unique=True)
    contract_number = models.CharField(max_length=80, unique=True, null=True, blank=True)
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
    # 报价测算：报价时预估的材料、人工、费用成本（未测算为空）；签约时带入尚未设预算项目的首版预算。
    estimate_materials = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    estimate_labor = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    estimate_expenses = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    estimated_by = models.ForeignKey(settings.AUTH_USER_MODEL, models.PROTECT, null=True, blank=True, related_name='+')

    class Meta(BaseModel.Meta):
        db_table = 'lean_sales_order'
        constraints = [
            models.CheckConstraint(condition=Q(quote_amount__gte=0, contract_amount__gte=0), name='lean_sales_amounts'),
            models.CheckConstraint(condition=Q(equipment_quantity__gt=0), name='lean_sales_equipment_positive'),
        ]


class ContractAmendment(ImmutableLedger):
    sale = models.ForeignKey(SalesOrder, models.PROTECT, related_name='amendments')
    document = models.ForeignKey('Document', models.PROTECT, related_name='+')
    reason = models.CharField(max_length=500)
    before = models.JSONField()
    after = models.JSONField()
    date = models.DateField()

    class Meta(ImmutableLedger.Meta):
        db_table = 'lean_contract_amendment'


class BOMLine(BaseModel):
    required_date = models.DateField(null=True, blank=True)
    application_date = models.DateField(null=True, blank=True)
    applicant = models.CharField(max_length=80, blank=True, default='')
    project = models.ForeignKey(Project, models.PROTECT, related_name='bom_lines')
    item = models.ForeignKey(Item, models.PROTECT)
    quantity = quantity(validators=[MinValueValidator(Decimal('0.001'))])
    change_note = models.CharField(max_length=500, blank=True)
    assembly_unit = models.CharField(max_length=100, blank=True)

    class Meta(BaseModel.Meta):
        db_table = 'lean_bom_line'
        constraints = [
            models.UniqueConstraint(
                fields=['project', 'item', 'assembly_unit'], condition=Q(is_deleted=False), name='lean_live_bom_unit'
            ),
            models.CheckConstraint(condition=Q(quantity__gt=0), name='lean_bom_positive'),
        ]


class RevisionChange(ImmutableLedger):
    """换版记录：项目 BOM 某单元把旧版（或旧型号）物料换成新物料的一次变更。

    旧版的在途采购在换版时转为新版（已批准的待采购确认），已到货和已领用的旧版留作待处理，
    由仓管报废或留作备件、采购下返修单改制成新版；待处理数量按项目实时口径计算，不另记余额。
    """

    project = models.ForeignKey(Project, models.PROTECT, related_name='revision_changes')
    old_item = models.ForeignKey(Item, models.PROTECT, related_name='+')
    new_item = models.ForeignKey(Item, models.PROTECT, related_name='+')
    old_line = models.ForeignKey(BOMLine, models.PROTECT, related_name='+')
    new_line = models.ForeignKey(BOMLine, models.PROTECT, related_name='+')
    assembly_unit = models.CharField(max_length=100, blank=True)
    old_quantity = quantity()
    new_quantity = quantity()
    # 换版时由旧版转为新版的未到货采购数量（快照，只用于展示）。
    converted_quantity = quantity()
    reason = models.CharField(max_length=500)

    class Meta(ImmutableLedger.Meta):
        db_table = 'lean_revision_change'
        indexes = [models.Index(fields=['project', 'old_item'], name='lean_revision_project_item')]


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
    payment_due_date = models.DateField(null=True, blank=True)
    payment_term = models.CharField(max_length=20, choices=PaymentTerm.choices, default=PaymentTerm.MANUAL)
    payment_days = models.PositiveSmallIntegerField(default=30)
    # 供应商质保月数，按每批合格收货日起算；默认一年，与采购合同质保条款同一来源。
    warranty_months = models.PositiveSmallIntegerField(default=12)
    note = models.CharField(max_length=500, blank=True)

    class Meta(BaseModel.Meta):
        db_table = 'lean_purchase'
        constraints = [
            models.CheckConstraint(
                condition=Q(warranty_months__gte=1, warranty_months__lte=120), name='lean_purchase_warranty_months'
            )
        ]
        indexes = [
            models.Index(
                fields=['project', 'status'], condition=Q(is_deleted=False), name='lean_purchase_project_status'
            )
        ]


class PurchaseLine(BaseModel):
    purchase = models.ForeignKey(PurchaseOrder, models.PROTECT, related_name='lines')
    item = models.ForeignKey(Item, models.PROTECT)
    bom_line = models.ForeignKey(BOMLine, models.PROTECT, null=True, blank=True)
    quantity = quantity(validators=[MinValueValidator(Decimal('0.001'))])
    unit_price = money(validators=[MinValueValidator(0)])
    received_quantity = models.DecimalField(max_digits=18, decimal_places=3, default=0)
    cancelled_quantity = models.DecimalField(max_digits=18, decimal_places=3, default=0)
    returned_quantity = models.DecimalField(max_digits=18, decimal_places=3, default=0)
    pending_quantity = models.DecimalField(max_digits=18, decimal_places=3, default=0)
    due_date = models.DateField(null=True, blank=True)

    class RevisionRole(models.TextChoices):
        NONE = '', ''
        CONVERTED = 'converted', '换版改单'
        REWORK_STOCK = 'rework_stock', '在库旧版返修'
        REWORK_ISSUED = 'rework_issued', '已领旧版返修'

    # 换版产生的明细：旧版在途转成的新版明细，或把旧版返修改制成新版的返修明细。
    revision = models.ForeignKey(RevisionChange, models.PROTECT, null=True, blank=True, related_name='purchase_lines')
    revision_role = models.CharField(max_length=20, choices=RevisionRole.choices, blank=True, default='')
    # 已批准采购的旧版在途转为新版后，须采购向供应商确认（可调价）或取消余量，确认前不能收货。
    revision_pending = models.BooleanField(default=False)

    class Meta(BaseModel.Meta):
        db_table = 'lean_purchase_line'
        constraints = [
            models.CheckConstraint(
                condition=Q(
                    pending_quantity__gte=0,
                    quantity__gte=F('received_quantity') + F('cancelled_quantity') + F('pending_quantity'),
                ),
                name='lean_purchase_pending_limit',
            ),
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
    material_requirements = models.JSONField(null=True, blank=True)
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
    class Discipline(models.TextChoices):
        MECHANICAL = 'mechanical', '机械'
        ELECTRICAL = 'electrical', '电气'
        PURCHASING = 'purchasing', '采购'
        PRODUCTION = 'production', '生产'
        DELIVERY = 'delivery', '交付与验收'

    class Kind(models.TextChoices):
        DESIGN = 'design', '设计'
        PURCHASE = 'purchase', '采购'
        SHIPPING = 'shipping', '发货'
        SITE = 'site', '客户终验收'
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
    milestone = models.CharField(max_length=40, blank=True, default='')
    discipline = models.CharField(max_length=20, choices=Discipline.choices, default='mechanical')
    title = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, models.PROTECT)
    # 旧接口的单执行人作为首个成员保留，其余成员不重复存储。
    co_assignees = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name='coassigned_tasks')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    due_date = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_date = models.DateField(null=True, blank=True)
    started_date = models.DateField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    service_date = models.DateField(null=True, blank=True)

    def assigned_people(self):
        return [self.assignee, *self.co_assignees.all()]

    def is_assigned_to(self, user):
        return self.assignee_id == user.pk or any(person.pk == user.pk for person in self.co_assignees.all())

    class Meta(BaseModel.Meta):
        db_table = 'lean_task'
        constraints = [
            models.UniqueConstraint(
                fields=['project', 'milestone'],
                condition=Q(is_deleted=False) & ~Q(milestone=''),
                name='lean_task_project_milestone',
            ),
        ]
        indexes = [
            # 工作台按「我参与的项目 + 我 + 待完成」取待办；阶段完工判定按项目 + 阶段取。
            models.Index(
                fields=['project', 'assignee', 'status'], condition=Q(is_deleted=False), name='lean_task_todo'
            ),
            models.Index(fields=['project', 'kind', 'status'], condition=Q(is_deleted=False), name='lean_task_stage'),
        ]


class TaskNotice(BaseModel):
    task = models.ForeignKey(Task, models.PROTECT, related_name='notices')
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, models.PROTECT, related_name='+')
    message = models.CharField(max_length=1000)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta(BaseModel.Meta):
        db_table = 'lean_task_notice'
        indexes = [models.Index(fields=['recipient', 'read_at'], name='lean_task_notice_unread')]


class IssueSlip(ImmutableLedger):
    """领料单：每次领料提交（单行领料、库存勾选批量领料、按 BOM 领料）生成一张，明细即挂在它下面的领料流水。

    单头记项目、任务、领料人和领料说明；经办仓管与时间取 created_by/created_at，数量、库位和成本仍以流水为准。
    """

    code = models.CharField(max_length=30, unique=True)
    project = models.ForeignKey(Project, models.PROTECT, related_name='issue_slips')
    task = models.ForeignKey(Task, models.PROTECT, null=True, blank=True, related_name='issue_slips')
    reason = models.CharField(max_length=500)
    # 实际来仓库领料的人（班组、装配人员等，不一定是系统用户）；经办仓管另记在 created_by。历史领料单为空。
    recipient = models.CharField(max_length=80, blank=True, default='')

    class Meta(ImmutableLedger.Meta):
        db_table = 'lean_issue_slip'


class StockMove(ImmutableLedger):
    class Kind(models.TextChoices):
        OPENING = 'opening', '期初'
        RECEIPT = 'receipt', '采购收货'
        ISSUE = 'issue', '项目领料'
        RETURN = 'return', '项目退料'
        PURCHASE_RETURN = 'purchase_return', '采购退货'
        COUNT = 'count', '盘点'
        SCRAP = 'scrap', '旧版报废'
        REWORK = 'rework', '送修改制'
        # 采购反审时冲回原收货（source 指向原收货）：数量、库存金额为负，supplier_credit 为原收货金额。
        RECEIPT_REVERSAL = 'receipt_reversal', '反审冲回'

    stock = models.ForeignKey(Stock, models.PROTECT, related_name='moves')
    project = models.ForeignKey(Project, models.PROTECT, null=True, blank=True, related_name='stock_moves')
    task = models.ForeignKey(Task, models.PROTECT, null=True, blank=True)
    purchase_line = models.ForeignKey(PurchaseLine, models.PROTECT, null=True, blank=True)
    source = models.ForeignKey('self', models.PROTECT, null=True, blank=True, related_name='returns')
    # 领料流水所属领料单；领料单上线前的历史领料和其他类型流水为空。
    slip = models.ForeignKey(IssueSlip, models.PROTECT, null=True, blank=True, related_name='moves')
    kind = models.CharField(max_length=30, choices=Kind.choices)
    quantity = quantity()
    value = money()
    supplier_credit = money()
    received_date = models.DateField(null=True, blank=True)
    reason = models.CharField(max_length=500)
    remark = models.CharField(max_length=500, blank=True, default='')

    class Meta(ImmutableLedger.Meta):
        db_table = 'lean_stock_move'
        indexes = [
            # 项目成本、已领量和缺料计算都按项目或库存加流水类型过滤。
            models.Index(fields=['project', 'kind'], condition=Q(is_deleted=False), name='lean_move_project_kind'),
            models.Index(fields=['stock', 'kind'], condition=Q(is_deleted=False), name='lean_move_stock_kind'),
        ]


class RevisionDisposition(ImmutableLedger):
    """旧版处理：换版后项目里多出的旧版，报废（在库的出库、已装机的只登记）或留作公用备件。

    返修改制不在这里登记，以返修采购明细为准（见 PurchaseLine.revision_role）。
    """

    class Source(models.TextChoices):
        STOCK = 'stock', '在库'
        ISSUED = 'issued', '已领用'

    class Kind(models.TextChoices):
        SCRAP = 'scrap', '报废'
        KEEP = 'keep', '留作备件'

    change = models.ForeignKey(RevisionChange, models.PROTECT, related_name='dispositions')
    source = models.CharField(max_length=10, choices=Source.choices)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    quantity = quantity(validators=[MinValueValidator(Decimal('0.001'))])
    move = models.OneToOneField(StockMove, models.PROTECT, null=True, blank=True, related_name='disposition')
    reason = models.CharField(max_length=500)

    class Meta(ImmutableLedger.Meta):
        db_table = 'lean_revision_disposition'
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gt=0), name='lean_disposition_positive'),
            models.CheckConstraint(
                condition=~Q(source='issued', kind='keep'), name='lean_disposition_issued_scrap_only'
            ),
        ]


class Entry(LedgerModel):
    class Kind(models.TextChoices):
        RECEIVABLE = 'receivable', '应收'
        PAYABLE = 'payable', '应付'
        EXPENSE = 'expense', '费用'

    class Trigger(models.TextChoices):
        # 收款节点的起算事件：事件发生后到期日 = 事件日期 + trigger_days；发生前 due_date 是签约时填的预计日期。
        SIGNED = 'signed', '签约'
        FIRST_SHIPMENT = 'first_shipment', '首批发货'
        ALL_SHIPPED = 'all_shipped', '全部发货'
        ALL_ACCEPTED = 'all_accepted', '全部终验收'
        WARRANTY_END = 'warranty_end', '质保期满'

    project = models.ForeignKey(Project, models.PROTECT, related_name='entries')
    purchase = models.OneToOneField(PurchaseOrder, models.PROTECT, null=True, blank=True, related_name='entry')
    task = models.OneToOneField(Task, models.PROTECT, null=True, blank=True, related_name='entry')
    kind = models.CharField(max_length=20, choices=Kind.choices)
    title = models.CharField(max_length=150)
    amount = money()
    credit_amount = money()
    cancellation_credit = models.DecimalField(max_digits=18, decimal_places=2, null=True, editable=False)
    due_date = models.DateField()
    cancelled = models.BooleanField(default=False)
    trigger = models.CharField(max_length=20, choices=Trigger.choices, blank=True, default='')
    trigger_days = models.PositiveSmallIntegerField(default=0)
    # 签约时填的预计收款日（起算前可由财务调整），起算后保留作预计与实际的对照。
    planned_date = models.DateField(null=True, blank=True)
    triggered_on = models.DateField(null=True, blank=True)

    @property
    def awaiting_trigger(self):
        return bool(self.trigger) and self.triggered_on is None

    class Meta(LedgerModel.Meta):
        db_table = 'lean_entry'
        indexes = [
            models.Index(
                fields=['project', 'kind', 'cancelled'], condition=Q(is_deleted=False), name='lean_entry_project_kind'
            )
        ]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gte=0, credit_amount__gte=0), name='lean_entry_nonnegative'),
            models.CheckConstraint(condition=Q(credit_amount__lte=F('amount')), name='lean_entry_credit_limit'),
            models.CheckConstraint(condition=Q(trigger_days__lte=365), name='lean_entry_trigger_days'),
        ]


class Payment(ImmutableLedger):
    entry = models.ForeignKey(Entry, models.PROTECT, related_name='payments')
    reconciliation = models.ForeignKey('Reconciliation', models.PROTECT, null=True, blank=True, related_name='payments')
    amount = money()
    date = models.DateField()
    reason = models.CharField(max_length=500)
    method = models.CharField(max_length=20, blank=True)
    account = models.CharField(max_length=100, blank=True)
    reference = models.CharField(max_length=100, blank=True)
    document = models.ForeignKey('Document', models.PROTECT, null=True, blank=True, related_name='payments')
    reversal_of = models.OneToOneField('self', models.PROTECT, null=True, blank=True, related_name='reversal')

    class Meta(ImmutableLedger.Meta):
        db_table = 'lean_payment'
        constraints = [models.CheckConstraint(condition=~Q(amount=0), name='lean_payment_nonzero')]


class PaymentEvidence(ImmutableLedger):
    payment = models.ForeignKey(Payment, models.PROTECT, related_name='evidence')
    document = models.ForeignKey('Document', models.PROTECT, related_name='+')
    reason = models.CharField(max_length=500)

    class Meta(ImmutableLedger.Meta):
        db_table = 'lean_payment_evidence'
        constraints = [models.UniqueConstraint(fields=['payment', 'document'], name='lean_payment_evidence_unique')]


class Reconciliation(LedgerModel):
    settlement_month = models.CharField(max_length=7, blank=True)
    code = models.CharField(max_length=30, unique=True)
    entry = models.ForeignKey(Entry, models.PROTECT, related_name='reconciliations')
    kind = models.CharField(
        max_length=20, choices=[('settlement', '业务对账'), ('prepayment', '预付款核准'), ('refund', '退款对账')]
    )
    status = models.CharField(
        max_length=20, default='draft', choices=[('draft', '待确认'), ('confirmed', '已确认'), ('void', '已作废')]
    )
    snapshot = models.JSONField(default=dict, blank=True)
    counterparty_balance = money()
    approved_amount = money()
    basis = models.CharField(max_length=500, blank=True)
    document = models.ForeignKey('Document', models.PROTECT, null=True, blank=True, related_name='reconciliations')
    reason = models.CharField(max_length=500)
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, models.PROTECT, null=True, blank=True, related_name='+')
    confirmed_at = models.DateTimeField(null=True, blank=True)
    void_reason = models.CharField(max_length=500, blank=True)

    class Meta(LedgerModel.Meta):
        db_table = 'lean_reconciliation'
        constraints = [models.CheckConstraint(condition=Q(approved_amount__gt=0), name='lean_reconcile_positive')]


class BankRecord(LedgerModel):
    import_fingerprint = models.CharField(max_length=64, null=True, blank=True, unique=True)
    source = models.JSONField(default=dict, blank=True)
    needs_review = models.BooleanField(default=False)
    project = models.ForeignKey(Project, models.PROTECT, null=True, blank=True, related_name='bank_records')
    amount = money()
    date = models.DateField()
    account = models.CharField(max_length=100)
    reference = models.CharField(max_length=100)
    counterparty = models.CharField(max_length=150)
    reason = models.CharField(max_length=500)
    void_reason = models.CharField(max_length=500, blank=True)

    class Meta(LedgerModel.Meta):
        db_table = 'lean_bank_record'
        constraints = [
            models.CheckConstraint(condition=~Q(amount=0), name='lean_bank_nonzero'),
            models.UniqueConstraint(
                fields=['account', 'reference'], condition=Q(void_reason=''), name='lean_bank_reference_unique'
            ),
        ]


class BankMatch(ImmutableLedger):
    bank = models.ForeignKey(BankRecord, models.PROTECT, related_name='matches')
    payment = models.ForeignKey(Payment, models.PROTECT, related_name='bank_matches')
    amount = money()
    reason = models.CharField(max_length=500)
    reversal_of = models.OneToOneField('self', models.PROTECT, null=True, blank=True, related_name='reversal')

    class Meta(ImmutableLedger.Meta):
        db_table = 'lean_bank_match'
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0, reversal_of__isnull=True) | Q(amount__lt=0, reversal_of__isnull=False),
                name='lean_bank_match_direction',
            )
        ]


class BankOffset(ImmutableLedger):
    source = models.ForeignKey(BankRecord, models.PROTECT, related_name='returned_funds')
    returned = models.ForeignKey(BankRecord, models.PROTECT, related_name='return_sources')
    amount = money()
    reason = models.CharField(max_length=500)
    reversal_of = models.OneToOneField('self', models.PROTECT, null=True, blank=True, related_name='reversal')

    class Meta(ImmutableLedger.Meta):
        db_table = 'lean_bank_offset'
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0, reversal_of__isnull=True) | Q(amount__lt=0, reversal_of__isnull=False),
                name='lean_bank_offset_direction',
            )
        ]


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

    class Meta(ImmutableLedger.Meta):
        db_table = 'lean_time_entry'
        # 每次登记或更正工时都要汇总此人当天的净工时。
        indexes = [models.Index(fields=['user', 'date'], condition=Q(is_deleted=False), name='lean_time_user_date')]
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

    project = models.ForeignKey(Project, models.PROTECT, related_name='documents', null=True, blank=True)
    sale = models.ForeignKey(SalesOrder, models.PROTECT, related_name='documents', null=True, blank=True)
    purchase = models.ForeignKey(PurchaseOrder, models.PROTECT, related_name='documents', null=True, blank=True)
    category = models.CharField(max_length=20, choices=Category.choices)
    file = models.FileField(upload_to='protected/%Y/%m/')
    original_name = models.CharField(max_length=250)
    sha256 = models.CharField(max_length=64)
    size = models.PositiveIntegerField()

    class Meta(BaseModel.Meta):
        db_table = 'lean_document'
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(project__isnull=False, sale__isnull=True, purchase__isnull=True)
                    | Q(project__isnull=True, sale__isnull=False, purchase__isnull=True)
                    | Q(project__isnull=True, sale__isnull=True, purchase__isnull=False)
                ),
                name='lean_document_one_owner',
            )
        ]
