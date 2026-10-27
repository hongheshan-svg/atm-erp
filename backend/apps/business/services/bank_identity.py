"""One bank transaction identity for manual payments, imported evidence and settlement.

Account locks also cover identities not imported yet and raw/native reference aliases.
Lock order: accounting period -> all projects/entries -> sorted accounts -> bank rows.
Batch writers must acquire every account before processing their first row.
"""

import hashlib

from django.db import connection
from django.db.models import Q

from apps.core.api import Conflict

from ..models import BankMatch, BankRecord, Payment


def lock_accounts(accounts):
    keys = {
        int.from_bytes(hashlib.sha256(f'lean-bank-account:{account}'.encode()).digest()[:8], signed=True)
        for account in accounts
    }
    with connection.cursor() as cursor:
        for key in sorted(keys):
            cursor.execute('SELECT pg_advisory_xact_lock(%s)', [key])


def incoming_payments():
    return Q(entry__kind='receivable', amount__gt=0) | (~Q(entry__kind='receivable') & Q(amount__lt=0))


def live_payments(account, incoming):
    received = incoming_payments()
    return Payment.objects.filter(
        received if incoming else ~received,
        account=account,
        reversal_of__isnull=True,
        reversal__isnull=True,
    )


def native_reference(bank):
    # ICBC voucher numbers are not unique transaction numbers; never alias those.
    return bank.source.get('original_reference', '') if bank.source.get('bank') == 'HXB' else ''


def references(bank):
    original = native_reference(bank)
    return {bank.reference, original, f'{bank.date.isoformat()}:{original}'} if original else {bank.reference}


def reference_matches(bank, reference, date):
    return reference in references(bank) and (not native_reference(bank) or date == bank.date)


def payment_filter(bank):
    identity = Q(reference__in=references(bank))
    return identity & Q(date=bank.date) if native_reference(bank) else identity


def unmatched(payments):
    matched = BankMatch.objects.filter(reversal_of__isnull=True, reversal__isnull=True).values('payment')
    return payments.exclude(pk__in=matched)


def bank_payments(bank):
    return live_payments(bank.account, bank.amount > 0).filter(payment_filter(bank))


def manual_context(account, reference, date, *, incoming):
    """Return known banks and payments for one manual identity, preserving all original strings."""
    direction = Q(amount__gt=0) if incoming else Q(amount__lt=0)
    candidates = list(
        BankRecord.objects.filter(direction, account=account, void_reason='').filter(
            Q(reference=reference)
            | Q(source__bank='HXB', source__original_reference=reference)
            | Q(source__bank='HXB', date=date)
        )
    )
    native = any(native_reference(bank) and reference in references(bank) for bank in candidates)
    if any(
        native_reference(bank) and reference in references(bank) - {native_reference(bank)} and date != bank.date
        for bank in candidates
    ):
        raise Conflict('银行流水号对应的交易日期不一致，请核对实际银行日期后登记。')
    # A known Huaxia core number is scoped to its actual bank date, including a later day's reuse.
    identity = Q(reference=reference, date=date) if native else Q(reference=reference)
    banks = [bank for bank in candidates if reference_matches(bank, reference, date)]
    for bank in banks:
        identity |= payment_filter(bank)
    return banks, live_payments(account, incoming).filter(identity)
