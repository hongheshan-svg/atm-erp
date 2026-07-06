"""核销服务:为一条银行流水找出待付款项台账中的候选核销对象,并执行核销记账。"""

from decimal import Decimal

from django.db import transaction
from django.utils.dateparse import parse_datetime

from apps.finance.models import BankStatement, Payment
from apps.finance.payable_models import PayableItem, PayableSettlement
from apps.finance.payable_adapters import PAYABLE_SOURCES


def match_candidates(bank_statement, limit=10):
    """对未核销/部分核销的 PayableItem 打分,返回按 score 降序的候选列表。

    每项 `{'payable_item': PayableItem, 'score': int, 'reasons': list[str]}`。
    打分规则:
    - 收款方名规范化(全半角括号/空格归一)后相等 +50
    - 流水金额等于台账剩余金额 +40;金额大于 0 且不超过剩余金额 +15
    - 台账应付日期与流水交易日期相差 ≤7 天 +10
    只保留 score > 0 的候选,最多返回 limit 条。
    """
    norm = BankStatement._normalize_name
    target = norm(bank_statement.counterparty_name)
    amount = bank_statement.amount or 0

    # transaction_time 在实例未经数据库往返读取时可能仍是原始字符串(Django 仅在
    # 从数据库读回时才反序列化为 datetime,直接赋值构造的实例上 save() 不会就地转换)。
    transaction_time = bank_statement.transaction_time
    if isinstance(transaction_time, str):
        transaction_time = parse_datetime(transaction_time)
    bs_date = transaction_time.date() if transaction_time else None

    results = []
    qs = PayableItem.objects.filter(status__in=[PayableItem.STATUS_PENDING, PayableItem.STATUS_PARTIAL])
    for item in qs:
        score = 0
        reasons = []
        if target and norm(item.payee_name) == target:
            score += 50
            reasons.append('收款方一致')

        remaining = item.remaining
        if amount == remaining:
            score += 40
            reasons.append('金额等于剩余')
        elif 0 < amount <= remaining:
            score += 15
            reasons.append('金额不超剩余')

        if bs_date and item.due_date and abs((item.due_date - bs_date).days) <= 7:
            score += 10
            reasons.append('应付日期临近')

        if score > 0:
            results.append({'payable_item': item, 'score': score, 'reasons': reasons})

    results.sort(key=lambda r: r['score'], reverse=True)
    return results[:limit]


@transaction.atomic
def settle(bank_statement, allocations, user):
    """核销一条银行流水:按 allocations 生成 Payment + PayableSettlement,回写源单据,更新流水状态。

    `allocations` = `[{'payable_item_id': int, 'amount': Decimal}]`。
    每项 `select_for_update` 锁定台账项,校验 `0 < amount <= item.remaining`;
    所有项之和(含流水已核销金额)不得超过流水可核销总额,否则抛 `ValueError`。
    全部核销完成后按累计核销额是否达到流水金额将 `bank_statement.status`
    置为 `MATCHED`(全额)或 `PARTIAL`(部分)。
    """
    total = sum((a['amount'] for a in allocations), Decimal('0'))
    already = sum((s.amount for s in bank_statement.payable_settlements.all()), Decimal('0'))
    if total + already > (bank_statement.amount or Decimal('0')):
        raise ValueError('核销总额超过流水金额')

    # transaction_time 在实例未经数据库往返读取时可能仍是原始字符串,与
    # match_candidates 中同样的转换逻辑保持一致(见上方注释)。
    transaction_time = bank_statement.transaction_time
    if isinstance(transaction_time, str):
        transaction_time = parse_datetime(transaction_time)
    payment_date = transaction_time.date() if transaction_time else None

    settlements = []
    for a in allocations:
        item = PayableItem.objects.select_for_update().get(pk=a['payable_item_id'])
        amount = a['amount']
        if amount <= 0 or amount > item.remaining:
            raise ValueError(f'核销金额 {amount} 超过待付款项剩余 {item.remaining}')
        payment = Payment.objects.create(
            payment_type='PAYABLE', payable_item=item,
            payment_date=payment_date,
            payment_method='BANK_TRANSFER', amount=amount,
            currency_id=item.currency_id,
            notes=f'[BS#{bank_statement.id}] 银行流水核销',
            created_by=user, updated_by=user,
        )
        settlement = PayableSettlement.objects.create(
            bank_statement=bank_statement, payable_item=item,
            payment=payment, amount=amount, created_by=user, updated_by=user,
        )
        item.refresh_from_db()
        source = PAYABLE_SOURCES.get(item.source_type)
        if source:
            obj = _load_source_obj(item)
            if obj is not None:
                source.write_back(obj, item)
        settlements.append(settlement)

    new_total = already + total
    bank_statement.status = 'MATCHED' if new_total >= (bank_statement.amount or Decimal('0')) else 'PARTIAL'
    bank_statement.save(update_fields=['status', 'updated_at'])
    return settlements


def _load_source_obj(item):
    """按 PayableItem.source_type 映射回真实来源单据对象,供适配器 write_back 使用。"""
    from apps.finance.models import AccountPayable, Expense
    from apps.purchase.contract_execution import PaymentRecord
    model = {'ap': AccountPayable, 'expense': Expense, 'contract_payment': PaymentRecord}.get(item.source_type)
    return model.objects.filter(pk=item.source_id).first() if model else None
