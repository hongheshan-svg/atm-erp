"""Business cutoff, not a statutory accounting period or a duplicate ledger."""

from django.db import connection
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .api import Conflict
from .models import AuditLog, Company
from .permissions import ADMIN, require_role


def mutation_lock(exclusive=False):
    # Readers run concurrently. A cutoff change waits for all in-flight writes.
    function = 'pg_advisory_xact_lock' if exclusive else 'pg_advisory_xact_lock_shared'
    with connection.cursor() as cursor:
        cursor.execute(f'SELECT {function}(18360, 1)')


def check_dates(*dates):
    cutoff = Company.objects.filter(pk=1).values_list('locked_through', flat=True).first()
    if cutoff and any(date and date <= cutoff for date in dates):
        raise Conflict(
            f'业务已锁账至 {cutoff}。此日期的记录不能补录或更改，请联系管理员在公司资料中说明原因并重开期间。'
        )


def check_record(obj):
    name = obj._meta.model_name
    if name in {'payment', 'timeentry', 'bankrecord'}:
        check_dates(obj.date)
    elif name == 'stockmove':
        check_dates(obj.received_date or timezone.localdate())
    elif name == 'entry':
        check_dates(timezone.localdate(obj.created_at) if obj.created_at else timezone.localdate())


def configure(actor, key, data):
    from apps.business.services.common import day, fields, text

    from .actions import perform

    def execute(user):
        fields(data, {'locked_through', 'expected_revision', 'reason'})
        company, _ = Company.objects.get_or_create(pk=1)
        if type(data.get('expected_revision')) is not int or data['expected_revision'] != company.period_revision:
            raise Conflict('锁账状态已变化，请刷新后重试。')
        reason = text(data, 'reason')
        date = day(data, 'locked_through') if data.get('locked_through') else None
        if date and date >= timezone.localdate():
            raise ValidationError({'locked_through': '只能锁定今天之前的已结束日期。'})
        before = company.locked_through
        company.locked_through = date
        company.period_revision += 1
        company.save(update_fields=['locked_through', 'period_revision'])
        AuditLog.objects.create(
            actor=user,
            operation='period.lock',
            resource='company:1',
            detail={
                'before': str(before) if before else None,
                'after': str(date) if date else None,
                'reason': reason,
                'revision': company.period_revision,
            },
        )
        return {'id': 1, 'locked_through': str(date) if date else None, 'period_revision': company.period_revision}

    return perform(
        actor=actor,
        key=key,
        operation='period.lock',
        payload=data,
        authorize=lambda user: require_role(user, ADMIN),
        execute=execute,
    )
