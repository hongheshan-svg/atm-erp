"""Read-only checklist of historical records that today's rules would reject.

The rules added in this release only guard new operations; records written before them may still hold
those patterns. This module only lists them so finance can correct each record with the existing reversal,
void and cancel actions on the original form. It never writes, merges or repairs anything.

Every category is one grouped/windowed query plus a fixed number of preload queries, so the number of
queries does not grow with the number of problem records.
"""

from django.db.models import (
    BooleanField,
    Case,
    Count,
    DecimalField,
    Exists,
    F,
    IntegerField,
    OuterRef,
    Q,
    Subquery,
    Sum,
    Value,
    When,
    Window,
)
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.http import content_disposition_header
from rest_framework.exceptions import ValidationError

from apps.core.api import Conflict

from ..models import BankMatch, BankRecord, Delivery, Entry, Payment, PurchaseWarranty, Reconciliation
from . import deletions, finance, tabular
from .banking import with_remaining
from .common import ZERO

CATEGORIES = {
    'duplicate-payments': '同一款项重复登记的银行收付款',
    'claim-manual': '认领与手工登记重复',
    'duplicate-banks': '疑似重复的银行记录',
    'warranty-links': '采购质保关联异常',
    'deleted-open': '已删除但仍在办的记录',
}
NOTICE = '只读核查，不会修改任何数据；请用原单上的冲销、作废、取消等动作处理。'
HEADERS = ['类别', '记录类型', '记录ID', '编号/标题', '项目编号', '金额', '问题说明', '原单路径']
FIELDS = ['category_label', 'record_type_label', 'record_id', 'title', 'project_code', 'amount', 'problem', 'path']
MONEY = DecimalField(max_digits=18, decimal_places=2)
# Same cash direction rule as finance.bank_identity_payments: money in = receipt or refund received.
INCOMING = Q(entry__kind='receivable', amount__gt=0) | (~Q(entry__kind='receivable') & Q(amount__lt=0))
# Same "no import evidence" rule as bank_import.manual_suspect.
MANUAL_BANK = Q(import_fingerprint__isnull=True) & ~Q(source__has_key='bank') & ~Q(reference__startswith='IMPORT-')
LABELS = {resource: label for resource, (_, label) in deletions.RESOURCES.items()} | {'warranties': '采购质保'}


def finance_path(resource, pk):
    section = 'bank' if resource == 'bank-records' else resource
    return f'/finance?section={section}&resource={resource}&focus={pk}&project=all'


def row(category, resource, pk, title, project, amount, problem, path):
    return {
        'category': category,
        'category_label': CATEGORIES[category],
        'record_type': resource,
        'record_type_label': LABELS[resource],
        'record_id': pk,
        'title': title,
        'project_code': project.code if project else '',
        'amount': None if amount is None else f'{amount:.2f}',
        'problem': problem,
        'path': path,
    }


def direction(incoming):
    return '收入' if incoming else '支出'


def bank_payments():
    """Unreversed payments carrying a bank reference, with their cash direction and live bank match."""
    live = BankMatch.objects.filter(payment=OuterRef('pk'), reversal_of__isnull=True, reversal__isnull=True)
    return (
        Payment.objects.filter(reversal_of__isnull=True, reversal__isnull=True)
        .exclude(reference='')
        .annotate(
            incoming=Case(When(INCOMING, then=Value(True)), default=Value(False), output_field=BooleanField()),
            matched=Exists(live),
        )
        .select_related('entry__project')
    )


def payment_title(payment):
    return f'{payment.entry.title} · 流水号 {payment.reference}'


def duplicate_payments():
    identity = [F('entry_id'), F('account'), F('reference'), F('incoming')]
    records = (
        bank_payments()
        .filter(matched=False)
        .annotate(copies=Window(Count('pk'), partition_by=identity))
        .filter(copies__gte=2)
        .order_by('entry_id', 'account', 'reference', 'pk')
    )
    return [
        row(
            'duplicate-payments',
            'payments',
            payment.pk,
            payment_title(payment),
            payment.entry.project,
            payment.amount,
            f'款项「{payment.entry.title}」下有 {payment.copies} 条同账户「{payment.account or "未填写"}」、'
            f'同流水号「{payment.reference}」的{direction(payment.incoming)}收付款，均未冲销且未匹配银行，'
            '可能重复登记；请核对银行流水后对重复的一笔使用“冲销”。',
            finance_path('payments', payment.pk),
        )
        for payment in records
    ]


def claim_manual():
    identity = [F('account'), F('reference'), F('incoming')]

    def count(matched):
        return Window(
            Sum(Case(When(matched=matched, then=Value(1)), default=Value(0), output_field=IntegerField())),
            partition_by=identity,
        )

    records = (
        bank_payments()
        .annotate(group_matched=count(True), group_open=count(False))
        .filter(group_matched__gte=1, group_open__gte=1)
        .order_by('account', 'reference', 'pk')
    )
    return [
        row(
            'claim-manual',
            'payments',
            payment.pk,
            payment_title(payment),
            payment.entry.project,
            payment.amount,
            f'同账户「{payment.account or "未填写"}」、同流水号「{payment.reference}」的{direction(payment.incoming)}'
            f'已有 {payment.group_matched} 条收付款匹配了银行流水，本条手工登记未匹配银行，'
            f'可能重复计{"收" if payment.incoming else "付"}；属于同一笔到账的请在银行流水中“匹配已有收付款”，'
            '重复登记的请冲销本条，确为另一笔交易请核对流水号。',
            finance_path('payments', payment.pk),
        )
        for payment in records
        if not payment.matched
    ]


def duplicate_banks():
    identity = [F('account'), F('date'), F('amount')]
    records = (
        BankRecord.objects.filter(void_reason='')
        .annotate(manual=Case(When(MANUAL_BANK, then=Value(1)), default=Value(0), output_field=IntegerField()))
        .annotate(
            copies=Window(Count('pk'), partition_by=identity),
            manual_copies=Window(Sum('manual'), partition_by=identity),
        )
        .filter(copies__gte=2, manual_copies__gte=1)
        .select_related('project')
        .order_by('account', 'date', 'amount', 'pk')
    )
    return [
        row(
            'duplicate-banks',
            'bank-records',
            bank.pk,
            f'{bank.account} · 流水号 {bank.reference}',
            bank.project,
            bank.amount,
            f'与另外 {bank.copies - 1} 条未作废银行记录同账户、同日期（{bank.date}）、同金额'
            f'（{direction(bank.amount > 0)} {abs(bank.amount):.2f}），其中 {bank.manual_copies} 条为手工录入、'
            f'无导入证据，本条为{"手工录入" if bank.manual else "导入记录"}，疑似同一笔交易重复登记；'
            '请核对银行原始流水，误录的记录先撤销匹配再作废。',
            finance_path('bank-records', bank.pk),
        )
        for bank in records
    ]


def warranty_links():
    records = (
        PurchaseWarranty.objects.filter(Q(returned__isnull=False) | Q(expense__isnull=False))
        .annotate(
            return_cases=Window(Count('pk'), partition_by=[F('returned_id')]),
            expense_cases=Window(Count('pk'), partition_by=[F('expense_id')]),
        )
        .select_related('receipt__purchase_line__purchase__project', 'receipt__stock__item', 'returned', 'expense')
        .order_by('pk')
    )
    rows = []
    for case in records:
        problems, amount = [], None
        if case.returned_id and case.return_cases > 1:
            problems.append(
                f'退货流水 ID {case.returned_id} 同时关联了 {case.return_cases} 张质保单，退货可能被重复计算'
            )
            amount = abs(case.returned.value)
        if case.returned_id and -case.returned.quantity > case.quantity:
            problems.append(f'关联退货数量 {-case.returned.quantity} 超过本质保单报修数量 {case.quantity}')
            amount = abs(case.returned.value)
        if case.expense_id and case.expense_cases > 1:
            problems.append(f'费用「{case.expense.title}」同时关联了 {case.expense_cases} 张质保单，费用可能被重复计算')
            amount = case.expense.amount
        if not problems:
            continue
        purchase = case.receipt.purchase_line.purchase
        rows.append(
            row(
                'warranty-links',
                'warranties',
                case.pk,
                f'{purchase.code} · {case.receipt.stock.item.name} · 报修 {case.date}',
                purchase.project,
                amount,
                '；'.join(problems)
                + '。请核对原始退货与费用单据，由采购在质保处理中改选对应本单的记录；系统不会自动解除关联。',
                f'/purchases?resource=purchases&focus={purchase.pk}',
            )
        )
    return rows


def explain(obj):
    try:
        deletions.check_open(obj)
    except Conflict as exc:
        return f'已移入“已删除记录”，但按现行在办规则仍在办：{exc.detail}'
    return ''


def deleted_open():
    """Records moved to "已删除记录" that the current in-progress rule (deletions.check_open) would keep."""

    def hidden(model):
        # Same rule as the list filter: a record.delete with no later record.restore (restored rows are live).
        return model.objects.alias(_removed=deletions.removed(model)).filter(_removed=True)

    def annotated_entries(ids):
        paid = (
            Payment.objects.filter(entry=OuterRef('pk')).values('entry').annotate(total=Sum('amount')).values('total')
        )
        return {
            entry.pk: entry
            for entry in Entry.objects.filter(pk__in=ids)
            .annotate(
                net_paid=Coalesce(Subquery(paid), Value(ZERO), output_field=MONEY),
                has_draft=Exists(Reconciliation.objects.filter(entry=OuterRef('pk'), status='draft')),
            )
            .select_related('project')
        }

    rows = []
    entries = annotated_entries(hidden(Entry).values('pk'))
    draft_problem = None
    for entry in sorted(entries.values(), key=lambda value: value.pk):
        if finance.balance(entry):
            # check_open stops at the balance check, before its per-entry reconciliation lookup.
            problem = explain(entry)
        elif entry.has_draft:
            # With a zero balance check_open looks up draft reconciliations once per entry; that explanation
            # does not depend on the entry, so one call keeps the query count bounded.
            if draft_problem is None:
                draft_problem = explain(entry)
            problem = draft_problem
        else:
            continue
        if problem:
            rows.append(
                row(
                    'deleted-open',
                    'entries',
                    entry.pk,
                    entry.title,
                    entry.project,
                    entry.amount,
                    problem,
                    finance_path('entries', entry.pk),
                )
            )

    payments = list(hidden(Payment).order_by('pk'))
    owners = annotated_entries({payment.entry_id for payment in payments})
    for payment in payments:
        payment.entry = owners[payment.entry_id]
        problem = explain(payment)
        if problem:
            rows.append(
                row(
                    'deleted-open',
                    'payments',
                    payment.pk,
                    payment_title(payment) if payment.reference else payment.entry.title,
                    payment.entry.project,
                    payment.amount,
                    problem,
                    finance_path('payments', payment.pk),
                )
            )

    statements = hidden(Reconciliation).select_related('entry__project').prefetch_related('payments')
    for statement in statements.order_by('pk'):
        problem = explain(statement)
        if problem:
            rows.append(
                row(
                    'deleted-open',
                    'reconciliations',
                    statement.pk,
                    f'{statement.code} · {statement.entry.title}',
                    statement.entry.project,
                    statement.approved_amount,
                    problem,
                    finance_path('reconciliations', statement.pk),
                )
            )

    matches = list(hidden(BankMatch).select_related('payment__entry').order_by('pk'))
    # Removed bank records and the banks of removed matches, in one query with the remaining amount.
    banks = (
        with_remaining(BankRecord.objects.annotate(removed=deletions.removed(BankRecord)))
        .filter(Q(removed=True) | Q(pk__in={match.bank_id for match in matches}))
        .select_related('project')
        .order_by('pk')
        .in_bulk()
    )
    for bank in (bank for bank in banks.values() if bank.removed):
        problem = explain(bank)
        if problem:
            rows.append(
                row(
                    'deleted-open',
                    'bank-records',
                    bank.pk,
                    f'{bank.account} · 流水号 {bank.reference}',
                    bank.project,
                    bank.amount,
                    problem,
                    finance_path('bank-records', bank.pk),
                )
            )
    for match in matches:
        match.bank = banks[match.bank_id]
        problem = explain(match)
        if problem:
            rows.append(
                row(
                    'deleted-open',
                    'bank-matches',
                    match.pk,
                    f'{match.bank.account} · 流水号 {match.bank.reference} → {match.payment.entry.title}',
                    match.bank.project,
                    match.amount,
                    problem,
                    finance_path('bank-records', match.bank_id),
                )
            )

    for delivery in hidden(Delivery).select_related('project').order_by('pk'):
        problem = explain(delivery)
        if problem:
            rows.append(
                row(
                    'deleted-open',
                    'deliveries',
                    delivery.pk,
                    delivery.code,
                    delivery.project,
                    None,
                    problem,
                    f'/projects/{delivery.project_id}?tab=deliveries&section=deliveries&resource=deliveries'
                    f'&focus={delivery.pk}',
                )
            )
    return rows


CHECKS = {
    'duplicate-payments': duplicate_payments,
    'claim-manual': claim_manual,
    'duplicate-banks': duplicate_banks,
    'warranty-links': warranty_links,
    'deleted-open': deleted_open,
}


def category(value):
    if value in (None, ''):
        return next(iter(CATEGORIES))
    if value not in CATEGORIES:
        raise ValidationError({'category': '请选择有效的核查类别。'})
    return value


def report(selected):
    """Counts of every category and the rows of the selected one. Reads only."""
    selected = category(selected)
    results = {key: check() for key, check in CHECKS.items()}
    return {
        'category': selected,
        'notice': NOTICE,
        'categories': [{'key': key, 'label': label, 'count': len(results[key])} for key, label in CATEGORIES.items()],
        'rows': results[selected],
    }


def export(selected, file_format):
    selected = category(selected)
    rows = CHECKS[selected]()
    response = tabular.document(
        'data-checks',
        HEADERS,
        [[record[field] for field in FIELDS] for record in rows],
        file_format,
        numeric={FIELDS.index('amount'), FIELDS.index('record_id')},
    )
    name = f'历史数据核查_{CATEGORIES[selected]}_{timezone.localdate():%Y-%m-%d}.{file_format}'
    response['Content-Disposition'] = content_disposition_header(True, name)
    return response
