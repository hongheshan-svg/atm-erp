"""核销服务:为一条银行流水找出待付款项台账中的候选核销对象,并执行核销记账。"""

from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import DecimalField, ExpressionWrapper, F, Q, Value
from django.db.models.functions import Replace
from django.utils.dateparse import parse_datetime

from apps.finance.models import BankStatement, Payment
from apps.finance.payable_adapters import PAYABLE_SOURCES
from apps.finance.payable_models import PayableItem, PayableSettlement

# SQL 侧复刻 BankStatement._normalize_name 用的替换表。Python 侧是 strip() + 全半角括号归一 +
# 删空格;这里额外把制表符/换行也删掉,并对比较目标做同样的额外删除,于是
# SQL 归一化 == 「Python 归一化后再删这几个字符」——预筛结果恒为 Python 打分结果的超集,不会漏候选。
_SQL_NAME_REPLACEMENTS = (('（', '('), ('）', ')'), ('　', ''), (' ', ''), ('\t', ''), ('\n', ''), ('\r', ''))


def _sql_normalized_payee():
    expr = F('payee_name')
    for src, dst in _SQL_NAME_REPLACEMENTS:
        expr = Replace(expr, Value(src), Value(dst))
    return expr


def _drop_sql_only_chars(value):
    """把 SQL 侧比 Python 侧多删的字符从比较目标里也删掉,使两侧口径对齐。"""
    for char in ('\t', '\n', '\r'):
        value = value.replace(char, '')
    return value


def match_candidates(bank_statement, limit=10):
    """对未核销/部分核销的 PayableItem 打分,返回按 score 降序的候选列表。

    每项 `{'payable_item': PayableItem, 'score': int, 'reasons': list[str]}`。
    打分规则:
    - 收款方名规范化(全半角括号/空格归一)后相等 +50
    - 流水金额等于台账剩余金额 +40;金额大于 0 且不超过剩余金额 +15
    - 台账应付日期与流水交易日期相差 ≤7 天 +10
    只保留 score > 0 的候选,最多返回 limit 条。
    """
    if bank_statement.transaction_type != 'DEBIT':
        return []

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
    qs = PayableItem.objects.filter(status__in=[PayableItem.STATUS_PENDING, PayableItem.STATUS_PARTIAL]).annotate(
        _remaining=ExpressionWrapper(
            F('amount_due') - F('amount_paid'), output_field=DecimalField(max_digits=15, decimal_places=2)
        )
    )

    # 只有可能得分的行才值得拉进 Python 打分:score>0 等价于下面三项加分条件至少命中一项。
    # 未结台账项会累积到数千条,不预筛就要每次全表实例化并逐条归一化比较,
    # 核销候选接口的开销随台账规模线性增长。
    conditions = []
    if target:
        qs = qs.annotate(_normalized_payee=_sql_normalized_payee())
        conditions.append(Q(_normalized_payee=_drop_sql_only_chars(target)))
    # amount>0 时「金额等于剩余」已被「金额不超剩余」覆盖;amount<=0 时只有相等才得分。
    conditions.append(Q(_remaining__gte=amount) if amount > 0 else Q(_remaining=amount))
    if bs_date:
        conditions.append(Q(due_date__range=(bs_date - timedelta(days=7), bs_date + timedelta(days=7))))

    prefilter = conditions[0]
    for condition in conditions[1:]:
        prefilter |= condition

    for item in qs.filter(prefilter):
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
    bank_statement = BankStatement.objects.select_for_update().get(pk=bank_statement.pk)
    if bank_statement.transaction_type != 'DEBIT':
        raise ValueError('应付核销只能使用支出（借方）银行流水')
    if bank_statement.status in {'MATCHED', 'IGNORED'}:
        raise ValueError('该银行流水已完成处理，不能重复核销')

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

        source = PAYABLE_SOURCES.get(item.source_type)
        obj = _load_source_obj(item) if source else None
        if item.source_type == 'ap' and obj is not None and obj.po_id:
            from rest_framework.exceptions import ValidationError

            from apps.purchase.matching import assert_can_pay

            try:
                assert_can_pay(obj.po, (obj.amount_paid or Decimal('0')) + amount)
            except ValidationError as exc:
                detail = exc.detail[0] if isinstance(exc.detail, list) else exc.detail
                raise ValueError(str(detail)) from exc

        payment = Payment.objects.create(
            payment_type='PAYABLE',
            payable_item=item,
            payment_date=payment_date,
            payment_method='BANK_TRANSFER',
            amount=amount,
            currency_id=item.currency_id,
            notes=f'[BS#{bank_statement.id}] 银行流水核销',
            created_by=user,
            updated_by=user,
        )
        settlement = PayableSettlement.objects.create(
            bank_statement=bank_statement,
            payable_item=item,
            payment=payment,
            amount=amount,
            created_by=user,
            updated_by=user,
        )
        item.refresh_from_db()
        if source:
            if obj is not None:
                source.write_back(obj, item)
        settlements.append(settlement)

    new_total = already + total
    bank_statement.status = 'MATCHED' if new_total >= (bank_statement.amount or Decimal('0')) else 'PARTIAL'
    bank_statement.save(update_fields=['status', 'updated_at'])
    return settlements


def _load_source_obj(item):
    """按 PayableItem.source_type 映射回真实来源单据对象,供适配器 write_back 使用。"""
    from apps.finance.models import AccountPayable, Expense, PaymentRequest, SharedExpense
    from apps.finance.tax_management import TaxDeclaration
    from apps.oa.asset import AssetMaintenance
    from apps.oa.vehicle import VehicleMaintenance, VehicleRequest
    from apps.projects.field_service import ServiceExpense
    from apps.purchase.contract_execution import PaymentRecord
    from apps.purchase.outsource_models import OutsourceOrder

    model = {
        'ap': AccountPayable,
        'expense': Expense,
        'contract_payment': PaymentRecord,
        'outsource': OutsourceOrder,
        'shared_expense': SharedExpense,
        'tax': TaxDeclaration,
        'payment_request': PaymentRequest,
        'asset_maintenance': AssetMaintenance,
        'vehicle_maintenance': VehicleMaintenance,
        'service_expense': ServiceExpense,
        'vehicle_request': VehicleRequest,
    }.get(item.source_type)
    return model.objects.filter(pk=item.source_id).first() if model else None


@transaction.atomic
def unsettle(settlement, user):
    """反核销一条核销记录:回退台账已付、软删 Payment 与核销记录、经适配器回写源单据、
    重算银行流水状态。幂等(已软删的 settlement 再次调用直接返回)。"""
    if settlement.is_deleted:
        return
    # 与 settle 保持相同锁顺序(BankStatement → PayableItem)，防止死锁与状态漂移
    bs = BankStatement.objects.select_for_update().get(pk=settlement.bank_statement_id)
    item = PayableItem.objects.select_for_update().get(pk=settlement.payable_item_id)

    # 台账已付金额的回退统一由 Payment.soft_delete -> _reverse_target 单次完成,
    # 此处不再手工回退(否则与 Payment 反核销叠加,amount_paid 变负)。
    if settlement.payment_id:
        pay = Payment.all_objects.filter(pk=settlement.payment_id).first()
        if pay and not pay.is_deleted:
            pay.soft_delete()  # -> _reverse_target 回退台账已付并重算状态
        item.refresh_from_db()
    else:
        # 历史遗留:无关联 Payment 的核销记录,退化为手工回退
        item.amount_paid = item.amount_paid - settlement.amount
        if item.amount_paid < 0:
            item.amount_paid = Decimal('0')
        item.recalc_status()
        item.save(update_fields=['amount_paid', 'status', 'updated_at'])

    settlement.soft_delete()

    source = PAYABLE_SOURCES.get(item.source_type)
    if source:
        obj = _load_source_obj(item)
        if obj is not None:
            source.write_back(obj, item)

    remaining_total = sum((s.amount for s in bs.payable_settlements.all()), Decimal('0'))
    bs.status = 'PENDING' if remaining_total == 0 else 'PARTIAL'
    bs.save(update_fields=['status', 'updated_at'])
