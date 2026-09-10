"""Settlement evidence is a snapshot of existing facts, never a second balance ledger."""

import json
from decimal import Decimal

from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.core.api import Conflict
from apps.core.models import CodeRule
from apps.core.permissions import FINANCE, MANAGERS, require_role

from ..models import Document, Entry, Reconciliation, StockMove
from .common import ZERO, audit, fields, lookup, number, project_action, rounded, save, text


def signed_number(value, key):
    negative = isinstance(value, str) and value.startswith('-')
    return number(value[1:] if negative else value, key) * (-1 if negative else 1)


def snapshot(statement):
    entry = statement.entry
    payments = list(
        entry.payments.exclude(reconciliation_id=statement.pk)
        .order_by('pk')
        .values('id', 'amount', 'reversal_of', 'date', 'reason', 'method', 'account', 'reference')
    )
    baseline_paid = sum((p['amount'] for p in payments), ZERO)
    remaining = entry.amount - entry.credit_amount - baseline_paid
    data = {
        'entry': {
            'id': entry.pk,
            'title': entry.title,
            'kind': entry.kind,
            'amount': entry.amount,
            'credit_amount': entry.credit_amount,
            'due_date': entry.due_date,
            'cancelled': entry.cancelled,
        },
        'payments': payments,
        'paid': baseline_paid,
        'balance': remaining,
        'project': {
            'id': entry.project_id,
            'name': entry.project.name,
            'customer_id': entry.project.customer_id,
            'customer': entry.project.customer.name,
        },
    }
    eligible = abs(remaining)
    if entry.purchase_id:
        purchase = entry.purchase
        data['purchase'] = {
            'code': purchase.code,
            'supplier': purchase.supplier.name,
            'supplier_id': purchase.supplier_id,
            'status': purchase.status,
            'note': purchase.note,
            'payment_due_date': purchase.payment_due_date,
            'payment_term': purchase.payment_term,
            'payment_days': purchase.payment_days,
        }
        data['lines'] = list(
            purchase.lines.order_by('pk').values(
                'id',
                'item__code',
                'item__name',
                'quantity',
                'unit_price',
                'received_quantity',
                'returned_quantity',
                'cancelled_quantity',
                'pending_quantity',
            )
        )
        moves = list(
            StockMove.objects.filter(purchase_line__purchase=purchase)
            .order_by('pk')
            .values('id', 'kind', 'quantity', 'value', 'supplier_credit', 'received_date')
        )
        data['stock_moves'] = moves
        received_value = sum(
            (
                m['value']
                if m['kind'] == 'receipt'
                else -m['supplier_credit']
                if m['kind'] == 'purchase_return'
                else ZERO
                for m in moves
            ),
            ZERO,
        )
        data['received_net'] = received_value
        if statement.kind == 'settlement':
            eligible = max(ZERO, min(remaining, received_value - baseline_paid))
    else:
        sale = getattr(entry.project, 'sale', None)
        data['contract'] = (
            {
                'code': sale.code,
                'contract_number': sale.contract_number,
                'amount': sale.contract_amount,
                'updated_at': sale.updated_at,
            }
            if sale
            else None
        )
        data['deliveries'] = list(
            entry.project.deliveries.order_by('pk').values('code', 'quantity', 'shipped_date', 'accepted_date')
        )
    data['eligible'] = rounded(eligible)
    return json.loads(json.dumps(data, cls=DjangoJSONEncoder))


def used(statement):
    # A reversal must not resurrect an old authorization; it requires a new check.
    return sum((abs(p.amount) for p in statement.payments.filter(reversal_of__isnull=True)), ZERO)


def current(statement):
    return snapshot(statement) == statement.snapshot


def difference(statement):
    return statement.counterparty_balance - Decimal(statement.snapshot['balance'])


def create(actor, key, data):
    entry = lookup(Entry, data.get('entry'), 'entry')

    def execute(user, project):
        fields(data, {'entry', 'kind', 'counterparty_balance', 'approved_amount', 'basis', 'document', 'reason'})
        if project.status == 'closed':
            raise Conflict('项目已结项，请先重新打开。')
        source = Entry.objects.select_for_update().get(pk=entry.pk)
        kind = data.get('kind', 'settlement')
        if kind not in {'settlement', 'prepayment', 'refund'} or (kind == 'prepayment' and not source.purchase_id):
            raise ValidationError({'kind': '预付款核准仅适用于采购应付。'})
        doc = lookup(Document, data['document'], 'document') if data.get('document') else None
        if doc and doc.project_id and doc.category not in {'contract', 'receipt'}:
            raise ValidationError({'document': '项目对账附件请使用合同或结算凭证分类，避免向无金额权限人员公开。'})
        if doc and not (
            doc.project_id == project.pk
            or (doc.purchase_id and doc.purchase_id == source.purchase_id)
            or (doc.sale_id and doc.sale.project_id == project.pk)
        ):
            raise ValidationError({'document': '只能关联当前项目或原单据的附件。'})
        basis = text(data, 'basis', default='')
        if kind == 'prepayment' and not basis:
            raise ValidationError({'basis': '请填写合同编号、预付条款及比例或金额依据。'})
        CodeRule.objects.get_or_create(key='reconciliation', defaults={'prefix': 'DZ'})
        statement = Reconciliation(
            code=CodeRule.generate_code('reconciliation'),
            entry=source,
            kind=kind,
            counterparty_balance=signed_number(data.get('counterparty_balance'), 'counterparty_balance'),
            approved_amount=number(data.get('approved_amount'), 'approved_amount', positive=True),
            basis=basis,
            document=doc,
            reason=text(data, 'reason'),
        )
        save(statement, user)
        statement.snapshot = snapshot(statement)
        remaining = Decimal(statement.snapshot['balance'])
        if (kind == 'refund') != (remaining < 0) or remaining == 0:
            raise Conflict('请按当前待收付或待退款余额选择对账类型。')
        save(statement, user)
        return audit(user, 'reconciliation.create', statement)

    return project_action(actor, key, 'reconciliation.create', entry.project_id, data, FINANCE, execute)


def action(actor, key, statement_id, data, *, void=False):
    initial = lookup(Reconciliation, statement_id)

    def execute(user, project):
        fields(data, {'reason'})
        Entry.objects.select_for_update().get(pk=initial.entry_id)
        statement = (
            Reconciliation.objects.select_for_update(of=('self',))
            .select_related('entry__project', 'entry__purchase')
            .get(pk=initial.pk)
        )
        reason = text(data, 'reason')
        if statement.status == 'void' or (not void and statement.status != 'draft'):
            raise Conflict('此对账单已处理，请刷新。')
        if void:
            require_role(user, FINANCE)
            statement.status, statement.void_reason = 'void', reason
        else:
            require_role(user, MANAGERS if statement.kind == 'prepayment' else FINANCE)
            if not current(statement):
                raise Conflict('原单据、收退货或资金流水已变化，请作废后重新生成对账单。')
            if difference(statement) != 0:
                raise Conflict('对账差异未解决，请先更正原业务或对方账单后重新生成。')
            if statement.approved_amount > Decimal(statement.snapshot['eligible']):
                raise Conflict('核准金额超过可结算额度。未收货部分需按合同申请预付款核准。')
            if project.status == 'closed':
                raise Conflict('项目已结项，请先重新打开。')
            statement.status, statement.confirmed_at, statement.confirmed_by = 'confirmed', timezone.now(), user
        save(statement, user)
        return audit(user, 'reconciliation.void' if void else 'reconciliation.confirm', statement, reason=reason)

    return project_action(
        actor,
        key,
        'reconciliation.void' if void else 'reconciliation.confirm',
        initial.entry.project_id,
        {'id': initial.pk, 'data': data},
        FINANCE | MANAGERS,
        execute,
    )


def authorize_payment(entry, data, amount, refund):
    required = refund or bool(entry.purchase_id)
    if not data.get('reconciliation'):
        if required:
            raise Conflict('此付款或退款必须先完成对账；采购预付款请先按合同核准。')
        return None
    statement = lookup(Reconciliation, data['reconciliation'], 'reconciliation', entry=entry)
    if statement.status != 'confirmed' or not current(statement):
        raise Conflict('对账未确认或原业务已变化，请重新对账。')
    if (statement.kind == 'refund') != refund:
        raise Conflict('对账类型与收付款方向不一致。')
    if abs(amount) > statement.approved_amount - used(statement):
        raise Conflict('本次金额超过对账剩余核准额度。')
    return statement
