from django.db.models import Sum
from django.shortcuts import get_object_or_404

from apps.core.api import Conflict
from apps.core.permissions import FINANCE

from ..models import Document, Entry, Payment, PaymentEvidence, StockMove, TimeEntry
from .common import ZERO, audit, day, fields, lookup, number, project_action, rounded, save, state, text


def paid(entry):
    if hasattr(entry, 'net_paid'):
        return entry.net_paid
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
        fields(data, {'amount', 'date', 'reason', 'method', 'account', 'reference', 'document', 'reconciliation'})
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
        from .reconciliation import authorize_payment

        statement = authorize_payment(entry, data, amount, refund)
        method = text(data, 'method', default='', maximum=20)
        if method not in {'', 'bank', 'cash', 'other'}:
            from rest_framework.exceptions import ValidationError

            raise ValidationError({'method': '请选择银行转账、现金或其他。'})
        document = (
            lookup(Document, data['document'], 'document', project=entry.project, category='receipt')
            if data.get('document')
            else None
        )
        payment = save(
            Payment(
                entry=entry,
                reconciliation=statement,
                amount=amount,
                date=day(data, 'date'),
                reason=text(data, 'reason'),
                method=method,
                account=text(data, 'account', default='', maximum=100),
                reference=text(data, 'reference', default='', maximum=100),
                document=document,
            ),
            user,
        )
        audit(user, operation, entry, payment=payment.pk, amount=str(amount))
        return {'id': payment.pk}

    return entry_action(actor, key, operation, entry_id, data, execute)


def attach_evidence(actor, key, payment_id, data):
    original = lookup(Payment, payment_id)

    def execute(user, entry):
        fields(data, {'document', 'reason'})
        source = get_object_or_404(Payment.objects.select_for_update(), pk=original.pk, entry=entry)
        document = lookup(Document, data.get('document'), 'document', project=entry.project, category='receipt')
        if source.document_id == document.pk or source.evidence.filter(document=document).exists():
            raise Conflict('此凭证已关联到该流水，请刷新查看。')
        evidence = save(PaymentEvidence(payment=source, document=document, reason=text(data, 'reason')), user)
        audit(user, 'payment.evidence', source, document=document.pk, reason=evidence.reason)
        return {'id': evidence.pk}

    return entry_action(
        actor, key, 'payment.evidence', original.entry_id, {'payment': original.pk, 'data': data}, execute
    )


def reverse(actor, key, payment_id, data):
    original = lookup(Payment, payment_id)

    def execute(user, entry):
        fields(data, {'date', 'reason'})
        if entry.project.status == 'closed':
            raise Conflict('项目已结项，请先重新打开。')
        source = get_object_or_404(Payment.objects.select_for_update(), pk=original.pk, entry=entry)
        if source.reversal_of_id or Payment.objects.filter(reversal_of=source).exists():
            raise Conflict('此流水不能再次冲销。')
        if source.bank_matches.filter(reversal_of__isnull=True, reversal__isnull=True).exists():
            raise Conflict('该流水已与银行记录核对，请先撤销银行匹配，再冲销原流水。')
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
    return costs([project.pk])[project.pk]


def costs(project_ids):
    """Shared grouped projection for project detail, budgets and management reports."""
    from django.db.models import Q

    result = {pk: dict(materials=ZERO, purchase_return_variance=ZERO, labor=ZERO, expenses=ZERO) for pk in project_ids}
    moves = (
        StockMove.objects.filter(project_id__in=project_ids)
        .values('project_id')
        .annotate(
            materials=Sum('value', filter=Q(kind__in=['issue', 'return'])),
            returned=Sum('value', filter=Q(kind='purchase_return')),
            credit=Sum('supplier_credit', filter=Q(kind='purchase_return')),
        )
    )
    for row in moves:
        result[row['project_id']]['materials'] = -(row['materials'] or ZERO)
        result[row['project_id']]['purchase_return_variance'] = -(row['returned'] or ZERO) - (row['credit'] or ZERO)
    for row in (
        TimeEntry.objects.filter(task__project_id__in=project_ids)
        .values('task__project_id')
        .annotate(total=Sum('cost'))
    ):
        result[row['task__project_id']]['labor'] = row['total'] or ZERO
    for row in (
        Entry.objects.filter(project_id__in=project_ids, kind='expense', cancelled=False)
        .values('project_id')
        .annotate(total=Sum('amount'))
    ):
        result[row['project_id']]['expenses'] = row['total'] or ZERO
    return {
        pk: {key: str(rounded(value)) for key, value in {**values, 'total': sum(values.values(), ZERO)}.items()}
        for pk, values in result.items()
    }


def record_contract(user, project, milestones):
    """Record validated sales milestones in the caller's signing transaction."""
    for row in milestones:
        save(Entry(project=project, kind='receivable', **row), user)
