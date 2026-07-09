"""业务单据自动过账引擎 + 标准科目表种子。

审计缺口:业务单据(应收/应付/收付款)长期只维护往来台账,却不生成会计凭证,总账与
三大报表无从谈起。本模块补齐"业务事件 -> 记账凭证 -> 科目余额"这一环:

- ``seed_standard_accounts()``  幂等地播下一套最小可用的标准科目表(科目类别 + 8 个
  常用一级科目),供过账引擎按科目代码取数。
- ``POSTING_RULES``             业务类型 -> (借方/贷方科目) 的模块级映射(文档化配置);
- ``post_document(...)``        据映射与单据金额构造一张**借贷平衡**的记账凭证,落到单据
  日期所在的**开放**会计期间并**过账**(复用 accounting.post_voucher_to_ledger 更新科目
  余额),然后返回凭证。

关键设计约束(务必保持):
1. **不打断业务操作**:自动过账挂在 post_save 信号上、运行在业务事务内。任何异常都必须被
   吞掉——``post_document`` 用 ``transaction.atomic()`` 建**保存点**包裹全部写入,失败时
   仅回滚该保存点并记日志,绝不把异常抛回调用方的事务(否则一次凭证生成失败会连带回滚整张
   应收单/付款单,得不偿失)。
2. **幂等**:一张业务单据(source_type + source_id)最多一张凭证;重复保存/信号重入直接
   返回已存在的凭证。
3. **只进开放期间**:单据日期所在期间开放才过账;期间存在但未开放时,凭证留 ``DRAFT``
   待人工过账;没有任何匹配期间(或科目表未种子化)时跳过并记日志。

科目类别取值对齐 ``AccountCategory.CATEGORY_TYPE_CHOICES``:ASSET/LIABILITY/EQUITY/
COST/PROFIT_LOSS(注意本系统**没有**独立的 REVENUE/EXPENSE 类型——收入/费用同属**损益类**
PROFIT_LOSS,靠科目的 ``balance_direction`` 区分:贷方=收入,借方=费用)。
"""

import logging
from decimal import Decimal

from django.db import transaction

logger = logging.getLogger(__name__)


# (code, name, category_type, sort_order) —— 5 个标准科目类别,与 AccountCategory 取值一一对应。
STANDARD_CATEGORIES = [
    ('1', '资产类', 'ASSET', 1),
    ('2', '负债类', 'LIABILITY', 2),
    ('3', '所有者权益类', 'EQUITY', 3),
    ('4', '成本类', 'COST', 4),
    ('5', '损益类', 'PROFIT_LOSS', 5),
]

# (code, name, category_type, balance_direction) —— 最小可用的标准一级科目表。
# 收入(6001)贷方、成本/费用(6401/6602)借方,均归损益类 PROFIT_LOSS。
STANDARD_ACCOUNTS = [
    ('1002', '银行存款', 'ASSET', 'DEBIT'),
    ('1122', '应收账款', 'ASSET', 'DEBIT'),
    ('1405', '库存商品', 'ASSET', 'DEBIT'),
    ('2202', '应付账款', 'LIABILITY', 'CREDIT'),
    ('2221', '应交税费', 'LIABILITY', 'CREDIT'),
    ('6001', '主营业务收入', 'PROFIT_LOSS', 'CREDIT'),
    ('6401', '主营业务成本', 'PROFIT_LOSS', 'DEBIT'),
    ('6602', '管理费用', 'PROFIT_LOSS', 'DEBIT'),
]

# 业务类型 -> 过账规则(文档化的模块级映射;如需运行时可配可另建 DB 模型)。
#   AR_INVOICE  销售应收开票:借 1122 应收账款(价税合计)/ 贷 6001 主营业务收入(不含税)
#                            + 贷 2221 应交税费(销项税,tax_amount 有值时)
#   AP_INVOICE  采购应付确认:借 1405 库存商品 或 6602 管理费用(不含税)/ 贷 2202 应付账款(价税合计)
#                            + 借 2221 应交税费(进项税,tax_amount 有值时)
#   AR_RECEIPT  收到货款:    借 1002 银行存款 / 贷 1122 应收账款
#   AP_PAYMENT  对外付款:    借 2202 应付账款 / 贷 1002 银行存款
POSTING_RULES = {
    'AR_INVOICE': {'voucher_type': 'TRANSFER'},
    'AP_INVOICE': {'voucher_type': 'TRANSFER'},
    'AR_RECEIPT': {'voucher_type': 'RECEIPT'},
    'AP_PAYMENT': {'voucher_type': 'PAYMENT'},
}


def seed_standard_accounts(user=None):
    """幂等地播下标准科目类别与一级科目表。

    - 科目类别:按 ``category_type`` ``get_or_create``(缺则补,已存在不动);
    - 会计科目:仅当 COA **为空**时才批量创建 8 个标准科目(符合"COA 为空才种子"的语义);
      逐条仍走 ``get_or_create(code=...)``,即使并发/重复调用也不会重复插入。

    返回 ``{'categories': n, 'accounts': m}`` 统计新建数量。
    """
    from apps.finance.accounting import AccountCategory, ChartOfAccount

    created = {'categories': 0, 'accounts': 0}

    cat_map = {}
    for code, name, ctype, order in STANDARD_CATEGORIES:
        cat, was_created = AccountCategory.objects.get_or_create(
            category_type=ctype,
            is_deleted=False,
            defaults={'code': code, 'name': name, 'sort_order': order, 'created_by': user},
        )
        cat_map[ctype] = cat
        if was_created:
            created['categories'] += 1

    # "COA 为空才种子":已经有明细科目就不再铺,避免覆盖用户自定义的科目表。
    if not ChartOfAccount.objects.filter(is_deleted=False).exists():
        for code, name, ctype, direction in STANDARD_ACCOUNTS:
            _, was_created = ChartOfAccount.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'category': cat_map[ctype],
                    'balance_direction': direction,
                    'level': 1,
                    'is_detail': True,
                    'is_active': True,
                    'created_by': user,
                },
            )
            if was_created:
                created['accounts'] += 1

    return created


def _get_account(code):
    from apps.finance.accounting import ChartOfAccount

    return ChartOfAccount.objects.filter(code=code, is_deleted=False).first()


def _to_decimal(value):
    if value is None:
        return Decimal('0')
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _source_tax(obj):
    """单据税额:仅当来源模型带 ``tax_amount`` 字段时才拆分销项/进项税。

    AR/AP 模型当前没有 tax_amount 字段 -> 返回 0 -> 全额进收入/存货,不产生 2221 分录。
    未来若在来源单据上补 tax_amount,本引擎自动开始拆税(价税分离),无需改动。
    """
    return _to_decimal(getattr(obj, 'tax_amount', None))


def _resolve_date(source_type, obj):
    if source_type in ('AR_INVOICE', 'AP_INVOICE'):
        return obj.invoice_date
    return obj.payment_date  # AR_RECEIPT / AP_PAYMENT 来自 Payment


def _build_summary(source_type, obj):
    if source_type == 'AR_INVOICE':
        return f'销售应收开票 {obj.ar_no}'
    if source_type == 'AP_INVOICE':
        return f'采购应付确认 {obj.ap_no}'
    if source_type == 'AR_RECEIPT':
        return f'收款 {obj.payment_no}'
    if source_type == 'AP_PAYMENT':
        return f'付款 {obj.payment_no}'
    return ''


def _build_lines(source_type, obj):
    """据映射与单据金额构造分录列表(dict 形式);缺标准科目则记日志并返回 [](跳过过账)。

    每个 dict:{account, debit, credit, [customer/supplier/project]}。借贷两侧金额相等,
    保证凭证平衡。返回 [] 表示"无法/无需过账",调用方据此跳过。
    """
    missing = []
    cache = {}

    def acct(code):
        if code not in cache:
            a = _get_account(code)
            cache[code] = a
            if a is None:
                missing.append(code)
        return cache[code]

    zero = Decimal('0')
    lines = []

    if source_type == 'AR_INVOICE':
        amount = _to_decimal(getattr(obj, 'amount_due', None))
        tax = _source_tax(obj)
        net = amount - tax
        customer = getattr(obj, 'customer', None)
        project = getattr(obj, 'project', None)
        lines.append({'account': acct('1122'), 'debit': amount, 'credit': zero, 'customer': customer, 'project': project})
        lines.append({'account': acct('6001'), 'debit': zero, 'credit': net, 'project': project})
        if tax > zero:
            lines.append({'account': acct('2221'), 'debit': zero, 'credit': tax})

    elif source_type == 'AP_INVOICE':
        amount = _to_decimal(getattr(obj, 'amount_due', None))
        tax = _source_tax(obj)
        net = amount - tax
        supplier = getattr(obj, 'supplier', None)
        project = getattr(obj, 'project', None)
        # 有采购订单(po)视为采购入库 -> 库存商品;否则视为费用类应付 -> 管理费用。
        debit_code = '1405' if getattr(obj, 'po_id', None) else '6602'
        lines.append({'account': acct(debit_code), 'debit': net, 'credit': zero, 'supplier': supplier, 'project': project})
        if tax > zero:
            lines.append({'account': acct('2221'), 'debit': tax, 'credit': zero})
        lines.append({'account': acct('2202'), 'debit': zero, 'credit': amount, 'supplier': supplier, 'project': project})

    elif source_type == 'AR_RECEIPT':
        amount = _to_decimal(getattr(obj, 'amount', None))
        ar = getattr(obj, 'ar', None)
        customer = getattr(ar, 'customer', None) if ar else None
        project = getattr(ar, 'project', None) if ar else None
        lines.append({'account': acct('1002'), 'debit': amount, 'credit': zero})
        lines.append({'account': acct('1122'), 'debit': zero, 'credit': amount, 'customer': customer, 'project': project})

    elif source_type == 'AP_PAYMENT':
        amount = _to_decimal(getattr(obj, 'amount', None))
        ap = getattr(obj, 'ap', None)
        supplier = getattr(ap, 'supplier', None) if ap else None
        project = getattr(ap, 'project', None) if ap else None
        lines.append({'account': acct('2202'), 'debit': amount, 'credit': zero, 'supplier': supplier, 'project': project})
        lines.append({'account': acct('1002'), 'debit': zero, 'credit': amount})

    if missing:
        logger.warning(
            '缺少标准科目 %s,跳过自动过账(请先执行 seed_standard_accounts) source=%s id=%s',
            missing, source_type, getattr(obj, 'pk', None),
        )
        return []

    return lines


def post_document(source_type, obj, user=None):
    """业务单据自动过账入口:生成并过账一张平衡凭证,返回该凭证(或 None)。

    幂等 + 保存点包裹 + 绝不冒泡异常(见模块级 docstring 的约束 1/2/3)。
    """
    try:
        with transaction.atomic():  # 保存点:失败只回滚本次凭证写入,不牵连业务事务
            return _post_document_inner(source_type, obj, user)
    except Exception:
        logger.exception(
            '自动过账失败 source_type=%s id=%s(已回滚本次凭证写入,不影响业务操作)',
            source_type, getattr(obj, 'pk', None),
        )
        return None


def _post_document_inner(source_type, obj, user):
    from apps.finance.accounting import (
        FiscalPeriod,
        JournalVoucher,
        VoucherLine,
        post_voucher_to_ledger,
    )

    rule = POSTING_RULES.get(source_type)
    if not rule:
        logger.warning('未知的自动过账来源类型: %s', source_type)
        return None

    source_id = obj.pk
    if source_id is None:
        return None

    # 幂等:一张业务单据最多一张凭证。
    existing = JournalVoucher.objects.filter(
        source_type=source_type, source_id=source_id, is_deleted=False
    ).first()
    if existing:
        return existing

    lines = _build_lines(source_type, obj)
    if not lines:
        return None  # 科目缺失/无金额 -> 跳过(已记日志)

    voucher_date = _resolve_date(source_type, obj)
    if voucher_date is None:
        logger.warning('单据无凭证日期,跳过自动过账 source=%s id=%s', source_type, source_id)
        return None

    open_period = FiscalPeriod.objects.filter(
        start_date__lte=voucher_date, end_date__gte=voucher_date, status='OPEN', is_deleted=False
    ).first()
    period = open_period or FiscalPeriod.objects.filter(
        start_date__lte=voucher_date, end_date__gte=voucher_date, is_deleted=False
    ).first()
    if period is None:
        logger.warning(
            '日期 %s 无匹配会计期间,跳过自动过账 source=%s id=%s', voucher_date, source_type, source_id
        )
        return None

    voucher = JournalVoucher.objects.create(
        voucher_type=rule['voucher_type'],
        fiscal_period=period,
        voucher_date=voucher_date,
        status='DRAFT',
        summary=_build_summary(source_type, obj),
        source_type=source_type,
        source_id=source_id,
        created_by=user,
    )
    for idx, ln in enumerate(lines, 1):
        VoucherLine.objects.create(
            voucher=voucher,
            line_no=idx,
            account=ln['account'],
            summary=voucher.summary,
            debit_amount=ln['debit'],
            credit_amount=ln['credit'],
            customer=ln.get('customer'),
            supplier=ln.get('supplier'),
            project=ln.get('project'),
            department=ln.get('department'),
            created_by=user,
        )

    # VoucherLine.save() 每次都重算凭证借贷合计,重新读取以拿到最终值。
    voucher.refresh_from_db()

    if voucher.debit_total != voucher.credit_total or voucher.debit_total == 0:
        logger.error(
            '自动生成凭证不平衡/金额为零,保留草稿不过账 source=%s id=%s dr=%s cr=%s',
            source_type, source_id, voucher.debit_total, voucher.credit_total,
        )
        return voucher

    if open_period is not None:
        post_voucher_to_ledger(voucher, user)
    else:
        logger.info(
            '会计期间 %s 未开放(status=%s),凭证 %s 留草稿待人工过账',
            period, period.status, voucher.voucher_no,
        )
    return voucher
