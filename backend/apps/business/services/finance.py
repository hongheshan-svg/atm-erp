from django.db.models import Sum
from django.shortcuts import get_object_or_404

from apps.core.api import Conflict
from apps.core.permissions import FINANCE

from ..models import Entry, Payment, StockMove, TimeEntry
from .common import ZERO, audit, day, fields, lookup, number, project_action, rounded, save, state, text


def paid(entry):
    return entry.payments.aggregate(total=Sum('amount'))['total'] or ZERO


def balance(entry):
    return entry.amount - entry.credit_amount - paid(entry)


def entry_action(actor, key, operation, entry_id, data, execute):
    entry = lookup(Entry, entry_id)

    def perform(user, project):
        current = get_object_or_404(Entry.objects.select_for_update(), pk=entry.pk, project=project)
        return execute(user, current)

    return project_action(actor, key, operation, entry.project_id, {'entry': entry.pk, 'data': data}, FINANCE, perform)


def pay(actor, key, entry_id, data, *, refund=False):
    operation = 'entry.refund' if refund else 'entry.pay'

    def execute(user, entry):
        fields(data, {'amount', 'date', 'reason'})
        # Cancelled projects must remain able to settle refunds; closed projects must reopen first.
        if entry.project.status == 'closed':
            raise Conflict('项目已结项，请先重新打开。')
        amount = number(data.get('amount'), 'amount', positive=True)
        remaining = balance(entry)
        if refund:
            if remaining >= 0 or amount > -remaining:
                raise Conflict('退款超过当前应退余额。')
            amount = -amount
        elif remaining <= 0 or amount > remaining:
            raise Conflict('付款超过当前未结余额。')
        payment = save(Payment(entry=entry, amount=amount, date=day(data, 'date'), reason=text(data, 'reason')), user)
        audit(user, operation, entry, payment=payment.pk, amount=str(amount))
        return {'id': payment.pk}

    return entry_action(actor, key, operation, entry_id, data, execute)


def reverse(actor, key, payment_id, data):
    original = lookup(Payment, payment_id)

    def execute(user, entry):
        fields(data, {'date', 'reason'})
        if entry.project.status == 'closed':
            raise Conflict('项目已结项，请先重新打开。')
        source = get_object_or_404(Payment.objects.select_for_update(), pk=original.pk, entry=entry)
        if source.reversal_of_id or Payment.objects.filter(reversal_of=source).exists():
            raise Conflict('此流水不能再次冲销。')
        if paid(entry) - source.amount < 0:
            raise Conflict('冲销会使净付款为负，请先处理关联退款。')
        payment = save(
            Payment(
                entry=entry,
                amount=-source.amount,
                date=day(data, 'date'),
                reason=text(data, 'reason'),
                reversal_of=source,
            ),
            user,
        )
        return audit(user, 'payment.reverse', payment, original=source.pk)

    return entry_action(
        actor, key, 'payment.reverse', original.entry_id, {'payment': original.pk, 'data': data}, execute
    )


def expense(actor, key, data):
    def execute(user, project):
        fields(data, {'project', 'title', 'amount', 'due_date'})
        state(project, {'active', 'delivering', 'warranty'})
        entry = save(
            Entry(
                project=project,
                kind='expense',
                title=text(data, 'title', maximum=150),
                amount=number(data.get('amount'), 'amount', positive=True),
                due_date=day(data, 'due_date'),
            ),
            user,
        )
        return audit(user, 'expense.create', entry)

    return project_action(actor, key, 'expense.create', data.get('project'), data, FINANCE, execute)


def cancel_expense(actor, key, entry_id, data):
    def execute(user, entry):
        fields(data, {'reason'})
        if entry.kind != 'expense' or entry.cancelled or entry.project.status == 'closed':
            raise Conflict('此费用当前不能取消。')
        reason = text(data, 'reason')
        entry.cancelled = True
        entry.credit_amount = entry.amount
        save(entry, user)
        return audit(user, 'expense.cancel', entry, reason=reason)

    return entry_action(actor, key, 'expense.cancel', entry_id, data, execute)


def cost(project):
    materials = -(
        StockMove.objects.filter(project=project, kind__in=['issue', 'return']).aggregate(total=Sum('value'))['total']
        or ZERO
    )
    variance = sum(
        (
            -move.value - move.supplier_credit
            for move in StockMove.objects.filter(project=project, kind='purchase_return')
        ),
        ZERO,
    )
    labor = TimeEntry.objects.filter(task__project=project).aggregate(total=Sum('cost'))['total'] or ZERO
    expenses = (
        Entry.objects.filter(project=project, kind='expense', cancelled=False).aggregate(total=Sum('amount'))['total']
        or ZERO
    )
    return {
        key: str(rounded(value))
        for key, value in {
            'materials': materials,
            'purchase_return_variance': variance,
            'labor': labor,
            'expenses': expenses,
            'total': materials + variance + labor + expenses,
        }.items()
    }


def record_contract(user, project, milestones):
    """Record validated sales milestones in the caller's signing transaction."""
    for row in milestones:
        save(Entry(project=project, kind='receivable', **row), user)
