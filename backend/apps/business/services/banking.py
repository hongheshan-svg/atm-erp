"""Bank evidence and allocation reuse Payment; bank records do not post a second cash ledger."""

import hashlib

from django.db import IntegrityError
from django.db.models import DecimalField, F, OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Abs, Coalesce

from apps.core.actions import perform
from apps.core.api import Conflict
from apps.core.permissions import FINANCE, require_role

from ..models import BankMatch, BankOffset, BankRecord, Entry, Payment, Project, Reconciliation
from . import finance
from .common import ZERO, audit, day, fields, lookup, number, project_action, save, text
from .reconciliation import signed_number


def remaining(bank):
    if hasattr(bank, 'net_remaining'):
        return bank.net_remaining
    matched = bank.matches.aggregate(total=Sum('amount'))['total'] or ZERO
    returned = bank.returned_funds.aggregate(total=Sum('amount'))['total'] or ZERO
    refunds = bank.return_sources.aggregate(total=Sum('amount'))['total'] or ZERO
    return abs(bank.amount) - matched - returned - refunds


def with_remaining(queryset):
    def total(model, field):
        values = (
            model.objects.filter(**{field: OuterRef('pk')}).values(field).annotate(total=Sum('amount')).values('total')
        )
        return Coalesce(Subquery(values), Value(ZERO), output_field=DecimalField(max_digits=18, decimal_places=2))

    return queryset.annotate(
        net_remaining=Abs(F('amount'))
        - total(BankMatch, 'bank')
        - total(BankOffset, 'source')
        - total(BankOffset, 'returned')
    )


def cash_amount(payment):
    return payment.amount if payment.entry.kind == 'receivable' else -payment.amount


def check_review(bank):
    if bank.needs_review:
        raise Conflict('此银行流水缺少对方户名，请先核实户名并记录依据。')


def review(actor, key, bank_id, data):
    def execute(user):
        fields(data, {'counterparty', 'reason'})
        bank = BankRecord.objects.select_for_update().get(pk=bank_id)
        if not bank.needs_review or bank.void_reason:
            raise Conflict('仅可核实待核实且未作废的银行流水。')
        name = text(data, 'counterparty', maximum=150)
        if name == '原流水未提供户名（待核实）':
            raise Conflict('请填写核实后的实际户名。')
        reason = text(data, 'reason')
        bank.counterparty = name
        bank.needs_review = False
        save(bank, user)
        return audit(user, 'bank.review', bank, counterparty=name, reason=reason)

    return bank_action(actor, key, 'bank.review', {'id': bank_id, 'data': data}, execute)


def bank_action(actor, key, operation, payload, execute):
    return perform(
        actor=actor,
        key=key,
        operation=operation,
        payload=payload,
        authorize=lambda user: require_role(user, FINANCE),
        execute=execute,
    )


def create(actor, key, data):
    def execute(user):
        fields(data, {'project', 'amount', 'date', 'account', 'reference', 'counterparty', 'reason'})
        project = lookup(Project, data['project'], 'project') if data.get('project') else None
        # An actual bank movement must be recordable even if its project is already closed.
        if project:
            Project.objects.select_for_update().get(pk=project.pk)
        amount = signed_number(data.get('amount'), 'amount')
        if not amount:
            raise Conflict('银行金额不能为零，收入填正数，支出填负数。')
        bank = save(
            BankRecord(
                project=project,
                amount=amount,
                date=day(data, 'date'),
                account=text(data, 'account', maximum=100),
                reference=text(data, 'reference', maximum=100),
                counterparty=text(data, 'counterparty', maximum=150),
                reason=text(data, 'reason'),
            ),
            user,
        )
        return audit(user, 'bank.create', bank)

    try:
        return bank_action(actor, key, 'bank.create', data, execute)
    except IntegrityError as exc:
        raise Conflict('此账户和银行流水号已登记，请刷新查看原记录。') from exc


def closed_project(bank):
    return (bank.project_id and bank.project.status == 'closed') or bank.matches.filter(
        payment__entry__project__status='closed'
    ).exists()


def return_unclaimed(actor, key, bank_id, data, *, reverse=False):
    def execute(user):
        fields(data, {'offset', 'reason'} if reverse else {'returned', 'amount', 'reason'})
        original = lookup(BankOffset, data.get('offset'), 'offset', source_id=bank_id) if reverse else None
        returned_id = original.returned_id if original else lookup(BankRecord, data.get('returned'), 'returned').pk
        records = {
            b.pk: b for b in BankRecord.objects.select_for_update().filter(pk__in=[bank_id, returned_id]).order_by('pk')
        }
        source, returned = records[bank_id], records[returned_id]
        reason = text(data, 'reason')
        if reverse:
            if original.reversal_of_id or BankOffset.objects.filter(reversal_of=original).exists():
                raise Conflict('该退回关联已撤销。')
            if closed_project(source) or closed_project(returned):
                raise Conflict('相关项目已结项，请先重新打开。')
            amount = -original.amount
        else:
            check_review(source)
            check_review(returned)
            amount = number(data.get('amount'), 'amount', positive=True)
            if source.void_reason or returned.void_reason or source.amount <= 0 or returned.amount >= 0:
                raise Conflict('请选择原银行收入及实际退回的银行支出记录。')
            if source.account != returned.account or source.counterparty != returned.counterparty:
                raise Conflict('退回账户或对方户名不一致，请核对银行记录。')
            if source.project_id and returned.project_id and source.project_id != returned.project_id:
                raise Conflict('退回记录属于其他项目。')
            if amount > min(remaining(source), remaining(returned)):
                raise Conflict('退回金额超过原未认领款或实际支出的未匹配余额。')
        offset = save(
            BankOffset(source=source, returned=returned, amount=amount, reason=reason, reversal_of=original), user
        )
        return audit(user, 'bank.return-unclaimed.reverse' if reverse else 'bank.return-unclaimed', offset)

    return bank_action(
        actor,
        key,
        'bank.return-unclaimed.reverse' if reverse else 'bank.return-unclaimed',
        {'bank': bank_id, 'data': data},
        execute,
    )


def void(actor, key, bank_id, data):
    def execute(user):
        fields(data, {'reason'})
        bank = BankRecord.objects.select_for_update().get(pk=bank_id)
        if bank.void_reason or remaining(bank) != abs(bank.amount):
            raise Conflict('银行记录已作废或还有有效匹配，请先撤销匹配。')
        bank.void_reason = text(data, 'reason')
        save(bank, user)
        return audit(user, 'bank.void', bank, reason=bank.void_reason)

    return bank_action(actor, key, 'bank.void', {'id': bank_id, 'data': data}, execute)


def match_record(user, bank, payment, reason):
    check_review(bank)
    if bank.void_reason or payment.reversal_of_id or Payment.objects.filter(reversal_of=payment).exists():
        raise Conflict('已作废银行记录或已冲销流水不能匹配。')
    if bank.project_id and bank.project_id != payment.entry.project_id:
        raise Conflict('此银行记录已指定其他项目，不能跨项目匹配。')
    if payment.bank_matches.filter(reversal_of__isnull=True, reversal__isnull=True).exists():
        raise Conflict('该收付款流水已匹配银行记录。')
    cash = cash_amount(payment)
    if cash * bank.amount <= 0 or abs(cash) > remaining(bank):
        raise Conflict('银行方向或未匹配金额与收付款不一致。')
    if payment.method != 'bank' or payment.account != bank.account:
        raise Conflict('请核对收付款的银行结算方式和账户标识。')
    if payment.reference and payment.reference != bank.reference:
        raise Conflict('银行流水号不一致，请核对原始记录。')
    result = save(BankMatch(bank=bank, payment=payment, amount=abs(cash), reason=reason), user)
    return audit(user, 'bank.match', result)


def match(actor, key, bank_id, data, *, allocate=False):
    source = lookup(Entry if allocate else Payment, data.get('entry' if allocate else 'payment'))
    entry = source if allocate else source.entry

    def execute(user, project):
        fields(data, {'entry', 'amount', 'reason', 'reconciliation'} if allocate else {'payment', 'reason'})
        Entry.objects.select_for_update().get(pk=entry.pk)
        bank = BankRecord.objects.select_for_update().get(pk=bank_id)
        check_review(bank)
        reason = text(data, 'reason')
        if allocate:
            if bank.amount <= 0 or bank.void_reason:
                raise Conflict('只能认领有效的银行收入；支出请匹配已经核准登记的付款流水。')
            amount = number(data.get('amount'), 'amount', positive=True)
            if amount > remaining(bank):
                raise Conflict('认领金额超过银行待认领余额。')
            is_refund = entry.kind != 'receivable'
            inner_key = hashlib.sha256(f'{bank.pk}:{key}'.encode()).hexdigest()
            result = finance.pay(
                user,
                f'bank-allocation:{inner_key}',
                entry.pk,
                {
                    'amount': str(amount),
                    'date': bank.date.isoformat(),
                    'reason': reason,
                    'method': 'bank',
                    'account': bank.account,
                    'reference': bank.reference,
                    **({'reconciliation': data['reconciliation']} if data.get('reconciliation') else {}),
                },
                refund=is_refund,
            )
            payment = Payment.objects.get(pk=result['id'])
        else:
            payment = Payment.objects.select_for_update().get(pk=source.pk)
        return match_record(user, bank, payment, reason)

    return project_action(
        actor,
        key,
        'bank.allocate' if allocate else 'bank.match',
        entry.project_id,
        {'bank': bank_id, 'data': data},
        FINANCE,
        execute,
    )


def unmatch(actor, key, match_id, data):
    initial = lookup(BankMatch, match_id)

    def execute(user, project):
        fields(data, {'reason'})
        if project.status == 'closed':
            raise Conflict('项目已结项，请先重新打开后撤销银行匹配。')
        Entry.objects.select_for_update().get(pk=initial.payment.entry_id)
        bank = BankRecord.objects.select_for_update().get(pk=initial.bank_id)
        if (bank.project_id and bank.project.status == 'closed') or bank.matches.filter(
            payment__entry__project__status='closed'
        ).exists():
            raise Conflict('此银行记录涉及已结项项目，请先重新打开相关项目后撤销匹配。')
        source = BankMatch.objects.select_for_update().get(pk=initial.pk)
        if source.reversal_of_id or BankMatch.objects.filter(reversal_of=source).exists():
            raise Conflict('此匹配已撤销，不能重复撤销。')
        reverse = save(
            BankMatch(
                bank=source.bank,
                payment=source.payment,
                amount=-source.amount,
                reversal_of=source,
                reason=text(data, 'reason'),
            ),
            user,
        )
        return audit(user, 'bank.unmatch', reverse)

    return project_action(
        actor,
        key,
        'bank.unmatch',
        initial.payment.entry.project_id,
        {'match': match_id, 'data': data},
        FINANCE,
        execute,
    )


def check_close(project):
    if Reconciliation.objects.filter(entry__project=project, status='draft').exists():
        raise Conflict('项目还有待确认或存在差异的对账单，请确认或作废后结项。')
    banks = BankRecord.objects.filter(
        Q(project=project) | Q(matches__payment__entry__project=project), void_reason=''
    ).distinct()
    locked = BankRecord.objects.filter(pk__in=banks.values('pk')).select_for_update().order_by('pk')
    if any(remaining(bank) != 0 for bank in locked):
        raise Conflict('项目还有未认领或未匹配的银行款项，请处理后结项。')
