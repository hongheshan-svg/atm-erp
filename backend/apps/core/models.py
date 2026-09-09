from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone


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


class LedgerModel(BaseModel):
    class Meta(BaseModel.Meta):
        abstract = True

    def soft_delete(self, actor):
        raise ValidationError('账目和流水不可删除，请通过冲销或更正保留历史。')


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


class Company(models.Model):
    name = models.CharField(max_length=150, default='我的公司')
    address = models.CharField(max_length=250, blank=True)
    phone = models.CharField(max_length=50, blank=True)

    class Meta:
        db_table = 'lean_company'


class SchemaVersion(models.Model):
    generation = models.CharField(max_length=50)

    class Meta:
        db_table = 'lean_schema'


class CodeRule(models.Model):
    key = models.CharField(max_length=30, unique=True)
    prefix = models.CharField(max_length=10)
    counter = models.PositiveBigIntegerField(default=0)

    class Meta:
        db_table = 'lean_code_rule'

    @classmethod
    def generate_code(cls, key):
        with transaction.atomic():
            rule = cls.objects.select_for_update().get(key=key)
            rule.counter += 1
            rule.save(update_fields=['counter'])
            return f'{rule.prefix}{rule.counter:06d}'


class AuditLog(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, models.PROTECT)
    operation = models.CharField(max_length=80)
    resource = models.CharField(max_length=100)
    detail = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'lean_audit'
        ordering = ['-id']


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
