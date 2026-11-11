from contextlib import nullcontext

from django.conf import settings
from django.core.exceptions import FieldError, ValidationError
from django.db import DatabaseError, connections, models, router, transaction
from django.db.models import BooleanField, Q, Value
from django.db.models.functions import Coalesce
from django.db.models.sql import Query
from django.db.models.sql.constants import SINGLE
from django.utils import timezone


def loaded_relation(instance, field):
    """The foreign key points at a related row already loaded on this instance.

    That row was read from the database (the actor set as created_by/updated_by, the parent passed to the
    constructor), and business rows are never physically deleted, so the existence query full_clean runs for
    every foreign key would only re-read it.
    """
    if not isinstance(field, models.ForeignKey) or field.remote_field.parent_link or field.choices:
        return False
    if field.validators or not field.is_cached(instance):
        return False
    value = getattr(instance, field.attname)
    related = field.get_cached_value(instance)
    return (
        value is not None
        and related is not None
        and not related._state.adding
        and getattr(related, field.target_field.attname) == value
    )


class ProtectedQuerySet(models.QuerySet):
    def delete(self):
        raise ValidationError('业务记录不可物理删除。')


class LiveManager(models.Manager.from_queryset(ProtectedQuerySet)):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, models.PROTECT, null=True, blank=True, related_name='+')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, models.PROTECT, null=True, blank=True, related_name='+')
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    objects = LiveManager()
    all_objects = ProtectedQuerySet.as_manager()

    class Meta:
        abstract = True
        ordering = ['-id']

    def delete(self, *args, **kwargs):
        raise ValidationError('业务记录不可物理删除。')

    def soft_delete(self, actor):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.updated_by = actor
        self.save(update_fields=['is_deleted', 'deleted_at', 'updated_by', 'updated_at'])

    # 业务写入统一经 services.common.save → full_clean。Django 对每个外键查一次存在性、对每条 CHECK 约束
    # 各开一个保存点再查一次；批量收货、建采购时这些校验占了绝大多数 SQL。下面两处只减少查询次数，
    # 校验规则、错误内容与顺序不变。

    def clean_fields(self, exclude=None):
        # 已加载在实例上的关联行（经办人、构造时传入的上级单据）无需再查存在性；其余字段照常校验。
        # 这些外键没有 choices 或自定义校验器，值非空且等于已加载行的主键，按原逻辑也必然通过。
        exclude = set(exclude or ())
        loaded = {field.name for field in self._meta.fields if loaded_relation(self, field)}
        if not self._state.adding:
            # 创建人只在新增时由 save() 写入，之后从不改写；更新时它是库里已有、受 PROTECT 保护的原值。
            loaded.add('created_by')
        return super().clean_fields(exclude=exclude | loaded)

    def validate_constraints(self, exclude=None):
        # 同一模型的多条 CHECK 约束合并成一次查询，再按 Django 原有顺序逐条给出相同的错误；
        # 唯一约束等其他约束仍走 Django 自身逻辑。任何特殊情况（字段已出错被排除、数据库报错）退回原逻辑。
        constraints = self.get_constraints()
        checks = [c for _, group in constraints for c in group if type(c) is models.CheckConstraint]
        if len(constraints) != 1 or len(checks) < 2:
            return super().validate_constraints(exclude=exclude)
        passed = self._passed_checks(checks, exclude)
        if passed is None:
            return super().validate_constraints(exclude=exclude)
        model_class, model_constraints = constraints[0]
        using = router.db_for_write(self.__class__, instance=self)
        errors = {}
        for constraint in model_constraints:
            try:
                if type(constraint) is models.CheckConstraint:
                    if not passed[id(constraint)]:
                        raise ValidationError(
                            constraint.get_violation_error_message(), code=constraint.violation_error_code
                        )
                else:
                    constraint.validate(model_class, self, exclude=exclude, using=using)
            except ValidationError as e:
                if getattr(e, 'code', None) == 'unique' and len(constraint.fields) == 1:
                    errors.setdefault(constraint.fields[0], []).append(e)
                else:
                    errors = e.update_error_dict(errors)
        if errors:
            raise ValidationError(errors)

    def _passed_checks(self, checks, exclude):
        """Evaluate CheckConstraint conditions in one SELECT, exactly as Q.check does for each of them."""
        using = router.db_for_write(self.__class__, instance=self)
        connection = connections[using]
        if not connection.features.supports_comparing_boolean_expr:
            return None
        query = Query(None)
        for name, value in self._get_field_expression_map(meta=self._meta, exclude=exclude).items():
            query.add_annotation(value if hasattr(value, 'resolve_expression') else Value(value), name, select=False)
        try:
            for index, constraint in enumerate(checks):
                condition = Coalesce(Q(constraint.condition), True, output_field=BooleanField())
                query.add_annotation(condition, f'_check_{index}')
        except FieldError:
            return None
        compiler = query.get_compiler(using=using)
        try:
            with transaction.atomic(using=using) if connection.in_atomic_block else nullcontext():
                row = compiler.execute_sql(SINGLE)
        except DatabaseError:
            return None
        if row is None or len(row) != len(checks):
            return None
        return {id(constraint): value is True for constraint, value in zip(checks, row, strict=True)}


class LedgerModel(BaseModel):
    class Meta(BaseModel.Meta):
        abstract = True

    def soft_delete(self, actor):
        raise ValidationError('账目和流水不可删除，请通过冲销或更正保留历史。')

    def save(self, *args, **kwargs):
        # soft_delete 被禁用了，但直接置位再保存同样能让这条账目从所有余额里消失。
        # 把「不可删除」从约定变成类型层面的约束，免得后续有人无意绕过。
        if self.is_deleted:
            raise ValidationError('账目和流水不可隐藏，请通过冲销或更正保留历史。')
        return super().save(*args, **kwargs)


class ImmutableQuerySet(ProtectedQuerySet):
    def update(self, **kwargs):
        raise ValidationError('历史流水不可覆盖，请登记冲销或更正记录。')

    def bulk_update(self, *args, **kwargs):
        raise ValidationError('历史流水不可覆盖，请登记冲销或更正记录。')

    def bulk_create(self, *args, **kwargs):
        if kwargs.get('update_conflicts'):
            raise ValidationError('历史流水不可覆盖。')
        return super().bulk_create(*args, **kwargs)


class ImmutableLedger(LedgerModel):
    objects = LiveManager.from_queryset(ImmutableQuerySet)()
    all_objects = ImmutableQuerySet.as_manager()

    class Meta(LedgerModel.Meta):
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding or self.is_deleted:
            raise ValidationError('历史流水不可覆盖或隐藏，请登记冲销或更正记录。')
        kwargs['force_insert'] = True
        return super().save(*args, **kwargs)


class UpgradeJob(BaseModel):
    target = models.CharField(max_length=40)
    status = models.CharField(max_length=20, default='queued')
    mode = models.CharField(max_length=10)
    platform = models.CharField(max_length=10)
    asset = models.JSONField(default=dict)
    claim = models.CharField(max_length=64, blank=True)
    detail = models.CharField(max_length=500, blank=True)
    backup = models.CharField(max_length=500, blank=True)

    class Meta(BaseModel.Meta):
        db_table = 'lean_upgrade_job'


class Company(models.Model):
    setup_required = models.BooleanField(default=False)
    setup_completed_at = models.DateTimeField(null=True, blank=True)
    name = models.CharField(max_length=150, default='我的公司')
    address = models.CharField(max_length=250, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    locked_through = models.DateField(null=True, blank=True)
    period_revision = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'lean_company'


class SchemaVersion(models.Model):
    generation = models.CharField(max_length=50)

    class Meta:
        db_table = 'lean_schema'


# 每种编号规则对应的业务模型（手填编号查重用）；安装向导可配置的规则数量也以此为准。
CODE_MODELS = {
    'project': 'Project',
    'sale': 'SalesOrder',
    'purchase': 'PurchaseOrder',
    'delivery': 'Delivery',
    'item': 'Item',
    'partner': 'Partner',
    'reconciliation': 'Reconciliation',
    'issue_slip': 'IssueSlip',
}


class CodeRule(models.Model):
    product_counters = models.JSONField(default=dict, editable=False)
    key = models.CharField(max_length=30, unique=True)
    prefix = models.CharField(max_length=10)
    counter = models.PositiveBigIntegerField(default=0)
    date_format = models.CharField(
        max_length=8,
        default='',
        blank=True,
        choices=[('', '无日期'), ('YY', '两位年'), ('YYYY', '年'), ('YYYYMM', '年月'), ('YYYYMMDD', '年月日')],
    )
    padding = models.PositiveSmallIntegerField(default=6)
    reset_cycle = models.CharField(
        max_length=5,
        default='never',
        choices=[('never', '不重置'), ('year', '每年'), ('month', '每月'), ('day', '每天')],
    )
    period = models.CharField(max_length=8, default='', blank=True)
    revision = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'lean_code_rule'

    @classmethod
    def generate_code(cls, key, *, product_category='', custom=''):
        from django.apps import apps

        with transaction.atomic():
            rule = cls.objects.select_for_update().get(key=key)
            model = apps.get_model('business', CODE_MODELS[key])
            if not isinstance(custom, str):
                raise ValidationError({'code': '编号请按文本填写，保留前导零。'})
            custom = custom.strip()
            if custom:
                if len(custom) > 30 or not custom.isprintable():
                    raise ValidationError({'code': '编号最多30个字符，不能包含换行、制表符或不可见字符。'})
                if model.all_objects.filter(code=custom).exists():
                    raise ValidationError(
                        {'code': '编号已使用，包括停用或已删除记录；请核对原记录，不会自动覆盖或另编号码。'}
                    )
                return custom
            stamp = timezone.localdate().strftime('%Y%m%d')
            if product_category:
                item_model = apps.get_model('business', 'Item')
                if key != 'item' or product_category not in item_model.ProductCategory.values:
                    raise ValidationError('无效的产品编码类别。')
                prefix = product_category + (stamp[2:4] if product_category.startswith('1') else '99')
                counter = rule.product_counters.get(prefix, 0)
                while True:
                    counter += 1
                    if counter > 999999:
                        raise ValidationError('此产品类别的六位流水号已耗尽。')
                    code = f'{prefix}{counter:06d}'
                    if not item_model.all_objects.filter(code=code).exists():
                        break
                rule.product_counters[prefix] = counter
                rule.save(update_fields=['product_counters'])
                return code
            period = stamp[: {'never': 0, 'year': 4, 'month': 6, 'day': 8}[rule.reset_cycle]]
            if rule.period != period:
                rule.counter = 0
                rule.period = period
            date = stamp[2:4] if rule.date_format == 'YY' else stamp[: len(rule.date_format)]
            while True:
                rule.counter += 1
                if (
                    key == 'project'
                    and rule.prefix == 'ATM'
                    and rule.date_format == 'YY'
                    and rule.padding == 2
                    and rule.counter > 99
                ):
                    raise ValidationError('本年度项目序列号01–99已耗尽，请调整项目编号规则。')
                if rule.counter > 9223372036854775807:
                    raise ValidationError('编号流水已耗尽，请调整规则。')
                code = f'{rule.prefix}{date}{rule.counter:0{rule.padding}d}'
                if len(code) > 30:
                    raise ValidationError('编号超过 30 字符，请调整规则。')
                if not model.all_objects.filter(code=code).exists():
                    break
            rule.save(update_fields=['counter', 'period'])
            return code


class AuditLog(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, models.PROTECT)
    operation = models.CharField(max_length=80)
    resource = models.CharField(max_length=100)
    detail = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'lean_audit'
        ordering = ['-id']
        # 采购审批要回查提交人、质保和处理记录要按单据回查；审计表增长最快，没有索引就是全表扫描。
        # 已删除记录列表和审计页按动作筛选、按编号倒序分页，没有以动作开头的索引同样是全表扫描。
        indexes = [
            models.Index(fields=['resource', 'operation'], name='lean_audit_resource'),
            models.Index(fields=['operation', 'id'], name='lean_audit_operation'),
        ]


class ActionReceipt(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, models.PROTECT)
    key = models.CharField(max_length=128)
    operation = models.CharField(max_length=80)
    fingerprint = models.CharField(max_length=64)
    result = models.JSONField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'lean_action_receipt'
        constraints = [models.UniqueConstraint(fields=['actor', 'key'], name='lean_unique_action')]
        # 表格导入的预览和确认都按动作与内容指纹判断是否已导入；回执随每次写入增长，导入还逐行各写一条。
        indexes = [models.Index(fields=['operation', 'fingerprint'], name='lean_receipt_fingerprint')]
