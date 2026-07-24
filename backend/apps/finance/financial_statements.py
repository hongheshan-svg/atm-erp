"""三大财务报表 service:资产负债表 / 利润表 / 现金流量表。

全部返回**纯 dict(金额为 Decimal)**,由展示层(accounting.FinancialStatementViewSet)负责
转 float 供 JSON 序列化。数据来源:

- 资产负债表:某会计期间的 ``AccountBalance``**期末**余额(累计快照),按科目类别汇总,用科目
  ``balance_direction`` 把借/贷期末折算成带号净额。**未做期末损益结转**,故把本年利润
  (收入-费用)作为"本年利润(未结转)"并入所有者权益,使"资产 = 负债 + 权益"恒等。
- 利润表:区间内**已过账(POSTED)** 凭证分录中**损益类(PROFIT_LOSS)** 科目的发生额,贷方
  科目计收入、借方科目计费用,收入-费用=净利润。
- 现金流量表(**简化**):现金及银行存款科目(代码 1001/1002)已过账凭证在区间内的净变动,
  全部归入"经营活动";未拆分投资/筹资活动;期初现金按"区间开始日之前已过账凭证的累计净额"
  推算(不含手工录入的期初余额)。此为可运行的近似口径,复杂现金流分类留作后续增强。
"""

from decimal import Decimal


def _as_period(period):
    from apps.finance.accounting import FiscalPeriod

    if isinstance(period, FiscalPeriod):
        return period
    return FiscalPeriod.objects.get(pk=period)


def _signed_closing(bal):
    """按科目余额方向把期末借/贷折算成带号净额(正=方向内余额)。"""
    cd = bal.closing_debit or Decimal('0')
    cc = bal.closing_credit or Decimal('0')
    if bal.account.balance_direction == 'CREDIT':
        return cc - cd
    return cd - cc


def balance_sheet(period):
    """资产负债表。返回资产/负债/权益的分项与合计,并断言是否平衡。

    period: FiscalPeriod 实例或其主键。
    """
    from apps.finance.accounting import AccountBalance

    period = _as_period(period)

    balances = (
        AccountBalance.objects.filter(fiscal_period=period, is_deleted=False)
        .select_related('account', 'account__category')
    )

    assets, liabilities, equity = [], [], []
    assets_total = Decimal('0')
    liabilities_total = Decimal('0')
    equity_accounts_total = Decimal('0')
    revenue_total = Decimal('0')
    expense_total = Decimal('0')

    for bal in balances:
        acct = bal.account
        ctype = acct.category.category_type
        signed = _signed_closing(bal)
        item = {'account_code': acct.code, 'account_name': acct.name, 'amount': signed}

        if ctype == 'ASSET':
            assets.append(item)
            assets_total += signed
        elif ctype == 'LIABILITY':
            liabilities.append(item)
            liabilities_total += signed
        elif ctype == 'EQUITY':
            equity.append(item)
            equity_accounts_total += signed
        elif ctype in ('PROFIT_LOSS', 'COST'):
            # 损益/成本类计入"本年利润",贷方科目=收入,借方科目=费用。
            cd = bal.closing_debit or Decimal('0')
            cc = bal.closing_credit or Decimal('0')
            if acct.balance_direction == 'CREDIT':
                revenue_total += cc - cd
            else:
                expense_total += cd - cc

    net_profit = revenue_total - expense_total
    # 未结转损益并入权益 -> 保证会计恒等式成立。
    if net_profit != Decimal('0'):
        equity.append({'account_code': '', 'account_name': '本年利润(未结转)', 'amount': net_profit})
    equity_total = equity_accounts_total + net_profit

    liabilities_and_equity_total = liabilities_total + equity_total

    return {
        'period': str(period),
        'assets': assets,
        'liabilities': liabilities,
        'equity': equity,
        'assets_total': assets_total,
        'liabilities_total': liabilities_total,
        'equity_total': equity_total,
        'liabilities_and_equity_total': liabilities_and_equity_total,
        'net_profit': net_profit,
        'is_balanced': assets_total == liabilities_and_equity_total,
    }


def income_statement(period=None, start_date=None, end_date=None):
    """利润表:收入 - 费用 = 净利润。

    传 ``period``(FiscalPeriod/主键)按该期间;或传 ``start_date`` + ``end_date`` 按区间。
    仅统计**已过账**凭证中**损益类**科目的发生额。
    """
    from apps.finance.accounting import VoucherLine

    if period is not None:
        period = _as_period(period)
        start_date, end_date = period.start_date, period.end_date
        label = str(period)
    else:
        label = f'{start_date} ~ {end_date}'

    lines = (
        VoucherLine.objects.filter(
            is_deleted=False,
            voucher__is_deleted=False,
            voucher__status='POSTED',
            voucher__voucher_date__gte=start_date,
            voucher__voucher_date__lte=end_date,
            account__category__category_type='PROFIT_LOSS',
        )
        .select_related('account')
    )

    revenue_items = {}
    expense_items = {}
    revenue_total = Decimal('0')
    expense_total = Decimal('0')

    for ln in lines:
        acct = ln.account
        dr = ln.debit_amount or Decimal('0')
        cr = ln.credit_amount or Decimal('0')
        if acct.balance_direction == 'CREDIT':
            amount = cr - dr
            entry = revenue_items.setdefault(
                acct.code, {'account_code': acct.code, 'account_name': acct.name, 'amount': Decimal('0')}
            )
            entry['amount'] += amount
            revenue_total += amount
        else:
            amount = dr - cr
            entry = expense_items.setdefault(
                acct.code, {'account_code': acct.code, 'account_name': acct.name, 'amount': Decimal('0')}
            )
            entry['amount'] += amount
            expense_total += amount

    net_profit = revenue_total - expense_total

    return {
        'period': label,
        'revenue': list(revenue_items.values()),
        'expense': list(expense_items.values()),
        'revenue_total': revenue_total,
        'expense_total': expense_total,
        'net_profit': net_profit,
    }


def cash_flow(start_date, end_date):
    """现金流量表(简化):现金/银行存款科目在区间内的净变动。

    见模块 docstring 的简化说明:单一"经营活动"桶;现金 = 科目代码 1001/1002;期初现金按
    区间开始日之前已过账凭证累计推算。
    """
    from django.db.models import Q, Sum

    from apps.finance.accounting import ChartOfAccount, VoucherLine

    cash_ids = list(
        ChartOfAccount.objects.filter(is_deleted=False)
        .filter(Q(code__startswith='1001') | Q(code__startswith='1002'))
        .values_list('id', flat=True)
    )

    base = VoucherLine.objects.filter(
        is_deleted=False,
        voucher__is_deleted=False,
        voucher__status='POSTED',
        account_id__in=cash_ids,
    )

    def _net(qs):
        agg = qs.aggregate(d=Sum('debit_amount'), c=Sum('credit_amount'))
        return (agg['d'] or Decimal('0')) - (agg['c'] or Decimal('0'))

    opening_cash = _net(base.filter(voucher__voucher_date__lt=start_date))

    in_range = base.filter(voucher__voucher_date__gte=start_date, voucher__voucher_date__lte=end_date)
    inflow = in_range.aggregate(s=Sum('debit_amount'))['s'] or Decimal('0')
    outflow = in_range.aggregate(s=Sum('credit_amount'))['s'] or Decimal('0')
    net_cash_flow = inflow - outflow
    closing_cash = opening_cash + net_cash_flow

    return {
        'range': f'{start_date} ~ {end_date}',
        'opening_cash': opening_cash,
        'operating_inflow': inflow,
        'operating_outflow': outflow,
        'operating_net': net_cash_flow,
        'net_cash_flow': net_cash_flow,
        'closing_cash': closing_cash,
        'note': (
            '简化现金流量表:现金及银行存款(科目 1001/1002)已过账凭证在区间内的净变动,'
            '全部归入经营活动;未拆分投资/筹资活动;期初现金按区间开始日之前已过账凭证累计'
            '推算(不含手工录入的期初余额)。'
        ),
    }
