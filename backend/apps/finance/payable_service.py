"""核销服务:为一条银行流水找出待付款项台账中的候选核销对象。"""

from django.utils.dateparse import parse_datetime

from apps.finance.models import BankStatement
from apps.finance.payable_models import PayableItem


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
