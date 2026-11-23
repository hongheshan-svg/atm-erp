"""采购反审：待收货、部分收货、已收货的采购单退回草稿，改完重新提交审批、重新收货。

批准生成的应付和收货生成的库存流水都不能删改，反审在同一事务里登记冲回：
- 每次未冲回的收货登记一条「反审冲回」（source 指向原收货）：库存按当前平均成本出库，supplier_credit 记原收货金额，
  两者差额与采购退货一样计入本项目「采购退货价差」；
- 应付全额冲减并标记作废，重新批准时沿用这条应付、按新金额重新起算（见 supply.approve）；
- 明细的已收、已取消数量清零，单据回到草稿，由采购按现有「修改采购」改数量、单价、交期和账期。

不能一键冲回的情况先拦下并逐条说明办法：已付款或已对账、有隔离待检、有采购退货或质保记录、含换版明细、
到货已被领用（库存不够冲回，或冲回会占用其他项目的到货）。
"""

from collections import defaultdict
from decimal import Decimal

from django.utils import timezone

from apps.core.api import Conflict
from apps.core.permissions import ADMIN, PURCHASE_APPROVERS, has_role, require_project

from ..models import Entry, Project, PurchaseWarranty, Stock, StockMove
from .approval import independent_approval
from .bom import claimed_by_others
from .common import RECEIPT_REVERSAL, ZERO, audit, fields, live_receipts, lock_items, save, state, text
from .finance import paid
from .inventory import take_value
from .supply import locked_lines, purchase_action, purchase_applicants

STATUSES = {'approved', 'partial', 'received'}
PROJECT_STATES = {'active', 'delivering', 'warranty'}


def plain(value):
    """数量去掉末尾的零：12.000 → 12，10.500 → 10.5。"""
    text_value = format(Decimal(value).quantize(Decimal('0.001')), 'f')
    return text_value.rstrip('0').rstrip('.') if '.' in text_value else text_value


def receipts(purchase):
    """本单尚未冲回的收货，按物料、库存行、主键排序（与加锁顺序一致）。"""
    return list(
        live_receipts(StockMove.objects.filter(purchase_line__purchase=purchase))
        .select_related('stock__item')
        .order_by('stock__item_id', 'stock_id', 'pk')
    )


def problems(purchase, lines, moves, stocks, entry):
    """反审前要先处理的事项，每条写清原因和办法；空列表表示可以反审。"""
    result = []
    if entry is not None:
        net = paid(entry)
        if net > ZERO:
            result.append(f'本单已付款 {net} 元，请财务先在「收付款」冲销这些付款，再反审。')
        elif net < ZERO:
            result.append(f'本单有供应商退款 {-net} 元，请财务先冲销退款记录，再反审。')
        statements = list(entry.reconciliations.exclude(status='void').order_by('pk').values_list('code', flat=True))
        if statements:
            result.append(f'本单已有对账单 {"、".join(statements)}，请财务先作废对账单，再反审。')
    if any(line.pending_quantity > ZERO for line in lines):
        result.append('有到货在隔离待检，请仓管先办理「隔离品合格入库」或「隔离品退回供应商」，再反审。')
    if any(line.revision_id or line.revision_role or line.revision_pending for line in lines):
        result.append(
            '本单含换版改单或返修明细，旧版处理挂在这些明细上，不能反审；请用「确认换版改单」或「取消未收余量」处理。'
        )
    ids = [move.pk for move in moves]
    returned = defaultdict(lambda: ZERO)
    for source, qty in StockMove.objects.filter(kind='purchase_return', source_id__in=ids).values_list(
        'source_id', 'quantity'
    ):
        returned[source] -= qty
    if returned:
        result.append('本单已有采购退货（已冲减应付），不能反审；单价或数量有误请与供应商按退货、补单处理。')
    if PurchaseWarranty.objects.filter(receipt_id__in=ids).exists():
        result.append('本单已登记采购质保，不能反审。')
    # 已退回供应商的数量不在库里，按退货后的净到货核对库存够不够冲回。
    needed = defaultdict(lambda: ZERO)
    for move in moves:
        needed[move.stock_id] += move.quantity - returned[move.pk]
    by_item, items, short = defaultdict(lambda: ZERO), {}, set()
    for stock_id, qty in needed.items():
        stock = stocks[stock_id]
        by_item[stock.item_id] += qty
        items[stock.item_id] = stock.item
        if stock.quantity < qty:
            short.add(stock.item_id)
            result.append(
                f'{stock.item.code} {stock.item.name}（{stock.location}）现有库存 {plain(stock.quantity)}，'
                f'冲回需要 {plain(qty)}：本单到货已被领用或盘点调整，请先办理退料，再反审。'
            )
    # 库存不按项目预留：数量够冲回，但冲回后不够其他项目已到货未领的量，说明被领走的其实是本单的货。
    for item_id, qty in by_item.items():
        claims = {} if item_id in short else claimed_by_others(purchase.project, item_id)
        if not claims:
            continue
        on_hand = sum((stock.quantity for stock in Stock.objects.filter(item_id=item_id)), ZERO)
        if on_hand - qty < sum(claims.values(), ZERO):
            item = items[item_id]
            others = '、'.join(
                f'{code} {plain(claims[pk])}'
                for pk, code in Project.objects.filter(pk__in=claims).order_by('code').values_list('pk', 'code')
            )
            result.append(
                f'{item.code} {item.name} 冲回后会占用其他项目已到货的物料（{others}），说明本单到货已被领用；'
                '请先办理退料，再反审。'
            )
    return result


def summary(purchase, moves, entry):
    """反审会冲回的收货和作废的应付，供确认前查看。"""
    return {
        'receipts': [
            {
                'id': move.pk,
                'item_code': move.stock.item.code,
                'item_name': move.stock.item.name,
                'unit': move.stock.item.unit,
                'quantity': plain(move.quantity),
                'location': move.stock.location,
                'received_date': (move.received_date or timezone.localdate(move.created_at)).isoformat(),
            }
            for move in moves
        ],
        'payable': str(entry.amount - entry.credit_amount) if entry is not None else '0.00',
        'contract_versions': purchase.contract_versions.count(),
    }


def check(user, purchase):
    """反审前预览：能否反审、要先处理什么、会冲回哪些收货。只读，提交时在锁内重新校验。"""
    require_project(user, purchase.project, PURCHASE_APPROVERS)
    lines = list(purchase.lines.all())
    moves = receipts(purchase)
    stocks = {
        stock.pk: stock for stock in Stock.objects.filter(pk__in={m.stock_id for m in moves}).select_related('item')
    }
    entry = Entry.objects.filter(purchase=purchase).first()
    blocked = []
    if purchase.project.status not in PROJECT_STATES:
        blocked.append('项目不在执行中，不能反审采购。')
    if purchase.status not in STATUSES:
        blocked.append('只有待收货、部分收货、已收货的采购单可以反审；请刷新采购单。')
    else:
        blocked += problems(purchase, lines, moves, stocks, entry)
    if user.pk in purchase_applicants(purchase) and not has_role(user, ADMIN):
        blocked.append('你是本单申请人，不能反审自己的采购单（与批准同一规则）；请交由其他审批人处理。')
    return {'can_unapprove': not blocked, 'problems': blocked, **summary(purchase, moves, entry)}


def unapprove(actor, key, purchase_id, data):
    def execute(user, purchase):
        fields(data, {'reason'})
        state(purchase.project, PROJECT_STATES)
        state(purchase, STATUSES)
        reason = text(data, 'reason')
        self_approval = independent_approval(user, purchase_applicants(purchase), reason)
        lines = locked_lines(purchase)
        moves = receipts(purchase)
        # 与收货同一加锁顺序：物料按主键，再按主键锁库存行；应付放在最后。
        lock_items({move.stock.item_id for move in moves})
        stocks = {
            stock.pk: stock
            for stock in Stock.objects.select_for_update()
            .filter(pk__in={move.stock_id for move in moves})
            .select_related('item')
            .order_by('pk')
        }
        entry = Entry.objects.select_for_update().filter(purchase=purchase).first()
        blocked = problems(purchase, list(lines.values()), moves, stocks, entry)
        if blocked:
            raise Conflict('不能反审：' + '；'.join(blocked))
        before = purchase.status
        reversed_rows = []
        for move in moves:
            stock = stocks[move.stock_id]
            value = take_value(stock, move.quantity)
            stock.quantity -= move.quantity
            stock.value -= value
            save(stock, user)
            reversal = save(
                StockMove(
                    stock=stock,
                    project=purchase.project,
                    purchase_line_id=move.purchase_line_id,
                    source=move,
                    kind=RECEIPT_REVERSAL,
                    quantity=-move.quantity,
                    value=-value,
                    supplier_credit=move.value,
                    reason=reason,
                ),
                user,
            )
            reversed_rows.append(
                {
                    'receipt': move.pk,
                    'reversal': reversal.pk,
                    'line': move.purchase_line_id,
                    'quantity': str(move.quantity),
                    'value': str(value),
                    'receipt_value': str(move.value),
                }
            )
        for line in lines.values():
            line.received_quantity = ZERO
            line.cancelled_quantity = ZERO
            save(line, user)
        voided = ZERO
        if entry is not None:
            voided = entry.amount - entry.credit_amount
            entry.credit_amount, entry.cancelled = entry.amount, True
            save(entry, user)
        purchase.status = 'draft'
        save(purchase, user)
        return audit(
            user,
            'purchase.unapprove',
            purchase,
            reason=reason,
            self_approval=self_approval,
            previous_status=before,
            receipts=reversed_rows,
            payable=str(voided),
        )

    return purchase_action(actor, key, 'purchase.unapprove', purchase_id, data, PURCHASE_APPROVERS, execute)
