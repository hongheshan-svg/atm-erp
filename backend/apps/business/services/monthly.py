"""Supplier month projection from receipt, return and payment facts."""

import calendar
import uuid
from datetime import date

from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.core.actions import perform
from apps.core.api import Conflict
from apps.core.models import AuditLog
from apps.core.permissions import FINANCE, MONEY_READERS, projects_for, require_role

from ..models import Entry, Project, PurchaseOrder
from .common import ZERO, fields, identity, text
from .purchase_contract import fingerprint


def bounds(month):
    try:
        start = date.fromisoformat(f'{month}-01')
    except (TypeError, ValueError):
        raise ValidationError({'month': '月份格式为 YYYY-MM。'})
    if start > timezone.localdate():
        raise ValidationError({'month': '不能核对未来月份。'})
    return start, min(start.replace(day=calendar.monthrange(start.year, start.month)[1]), timezone.localdate())


def entry_totals(entry, month, *, excluded_statement=None):
    start, end = bounds(month)
    opening, received, returned, paid = ZERO, ZERO, ZERO, ZERO
    for move in (move for line in entry.purchase.lines.all() for move in line.stockmove_set.all()):
        day = move.received_date or timezone.localdate(move.created_at)
        amount = (
            move.value if move.kind == 'receipt' else -move.supplier_credit if move.kind == 'purchase_return' else ZERO
        )
        if day < start:
            opening += amount
        elif day <= end:
            if move.kind == 'receipt':
                received += amount
            else:
                returned -= amount
    for payment in entry.payments.all():
        if excluded_statement and payment.reconciliation_id == excluded_statement:
            continue
        if payment.date < start:
            opening -= payment.amount
        elif payment.date <= end:
            paid += payment.amount
    return {
        key: format(value, '.2f')
        for key, value in {
            'opening': opening,
            'received': received,
            'returned': returned,
            'paid': paid,
            'closing': opening + received - returned - paid,
        }.items()
    }


def summary(user, supplier, month):
    from decimal import Decimal

    require_role(user, MONEY_READERS)
    start, end = bounds(month)
    if not str(supplier).isdigit():
        raise ValidationError({'supplier': '请选择供应商。'})
    entries = (
        Entry.objects.filter(purchase__supplier_id=supplier, project__in=projects_for(user, Project.objects.all()))
        .select_related('purchase__supplier', 'project')
        .prefetch_related('payments', 'purchase__lines__stockmove_set')
        .order_by('project_id', 'id')
    )
    if entries.count() > 200:
        raise ValidationError('供应商应付超过200单，请分批在原应付页面核对。')
    rows = []
    for entry in entries:
        totals = entry_totals(entry, month)
        if all(Decimal(value) == 0 for value in totals.values()):
            continue
        rows.append(
            {
                'entry': entry.pk,
                'purchase': entry.purchase_id,
                'code': entry.purchase.code,
                'project': entry.project_id,
                'project_name': entry.project.name,
                **totals,
            }
        )
    totals = {
        key: str(sum((Decimal(row[key]) for row in rows), ZERO))
        for key in ('opening', 'received', 'returned', 'paid', 'closing')
    }
    result = {'supplier': int(supplier), 'month': month, 'through': str(end), 'rows': rows, 'totals': totals}
    return {**result, 'snapshot_hash': fingerprint(result)}


def confirm(actor, key, data):
    from decimal import Decimal

    from . import reconciliation

    def execute(user):
        fields(data, {'supplier', 'month', 'expected_snapshot', 'counterparty_balance', 'reason'})
        reason = text(data, 'reason')
        supplier = identity(data.get('supplier'), 'supplier')
        # Match the normal project-before-entry locking order across every affected order.
        project_ids = PurchaseOrder.objects.filter(supplier_id=supplier).values('project_id')
        list(Project.objects.filter(pk__in=project_ids).select_for_update().order_by('pk'))
        report = summary(user, data.get('supplier'), data.get('month'))
        if data.get('expected_snapshot') != report['snapshot_hash']:
            raise Conflict('收退货或资金事实已变化，请重新查询月度对账。')
        if reconciliation.signed_number(data.get('counterparty_balance'), 'counterparty_balance') != Decimal(
            report['totals']['closing']
        ):
            raise Conflict('月度期末余额与供应商不一致，请核对原收退货或资金记录后重试。')
        created = []
        if not report['rows']:
            raise Conflict('该供应商本月没有收退货、付款或期初余额可核对。')
        has_advances = any(Decimal(row['closing']) < 0 for row in report['rows'])
        for row in report['rows']:
            if has_advances:
                # Do not invent a cross-order allocation of a supplier advance.
                break
            entry = Entry.objects.select_for_update().get(pk=row['entry'])
            provisional = reconciliation.Reconciliation(
                entry=entry, kind='settlement', settlement_month=report['month']
            )
            snap = reconciliation.snapshot(provisional)
            eligible = Decimal(snap['eligible'])
            if eligible <= 0:
                continue
            result = reconciliation.create(
                user,
                str(uuid.uuid5(uuid.NAMESPACE_URL, f'{key}:entry:{entry.pk}')),
                {
                    'entry': entry.pk,
                    'kind': 'settlement',
                    'settlement_month': report['month'],
                    'counterparty_balance': snap['balance'],
                    'approved_amount': str(eligible),
                    'basis': f'供应商 {report["supplier"]} 月度核对 {report["month"]}',
                    'reason': reason,
                },
            )
            reconciliation.action(
                user, str(uuid.uuid5(uuid.NAMESPACE_URL, f'{key}:confirm:{entry.pk}')), result['id'], {'reason': reason}
            )
            created.append(result['id'])
        AuditLog.objects.create(
            actor=user,
            operation='supplier.monthly_confirm',
            resource=f'supplier:{report["supplier"]}',
            detail={'report': report, 'reconciliations': created, 'reason': reason},
        )
        return {'reconciliations': created, 'requires_advance_review': has_advances}

    return perform(
        actor=actor,
        key=key,
        operation='supplier.monthly_confirm',
        payload=data,
        authorize=lambda user: require_role(user, FINANCE),
        execute=execute,
    )
