"""
导入价格解析公共实现。

三个导入入口（采购申请 / BOM 询价 / 物料主数据）统一使用此模块，
消除各自独立解析逻辑导致的口径漂移。

解析规则（按优先级）：
  1. 有明确「未税单价」列 → 按未税读（用户显式声明口径，尊重它）
  2. 有「含税单价」列     → 按含税读，反算未税
  3. 只有裸「单价」列     → 按含税读（调用方在列检测阶段已将裸列折叠进 raw_inclusive）
  4. 两列都给             → 各按各的，不猜

税率来源由调用方决定：行内税率列 > 单据表头税率 > 物料 tax_rate > 默认 13
"""

from decimal import ROUND_HALF_UP, Decimal
from typing import Optional, Tuple

# 与 apps.purchase.models.PRICE_QUANT 保持一致：入账价保留 2 位
_QUANT = Decimal('0.01')


def resolve_import_prices(
    raw_exclusive: Optional[float],
    raw_inclusive: Optional[float],
    tax_rate,
) -> Tuple[float, float]:
    """统一导入价格解析，返回 (未税单价, 含税单价)。

    Args:
        raw_exclusive: 从「未税单价」列或其别名读到的原始值，None 表示该列缺失/空。
        raw_inclusive: 从「含税单价」列、其别名、**或裸「单价」列**读到的原始值。
                       调用方负责将裸「单价」列的值传入此参数（在列检测阶段折叠）。
        tax_rate:      百分数形式（13 表示 13%）。None 等同于 0%（免税）。

    Returns:
        Tuple[float, float]: (未税单价, 含税单价)，均为 float，2 位小数（ROUND_HALF_UP）。
        两侧均为 None 时返回 (0.0, 0.0)，不抛异常。
    """
    rate = Decimal(str(tax_rate or 0))
    multiplier = Decimal('1') + rate / Decimal('100')

    if raw_exclusive is not None:
        excl = Decimal(str(raw_exclusive)).quantize(_QUANT, rounding=ROUND_HALF_UP)
        if raw_inclusive is not None:
            incl = Decimal(str(raw_inclusive)).quantize(_QUANT, rounding=ROUND_HALF_UP)
        else:
            incl = (excl * multiplier).quantize(_QUANT, rounding=ROUND_HALF_UP)
        return float(excl), float(incl)

    if raw_inclusive is not None:
        incl = Decimal(str(raw_inclusive)).quantize(_QUANT, rounding=ROUND_HALF_UP)
        if multiplier == 0:
            excl = incl
        else:
            excl = (incl / multiplier).quantize(_QUANT, rounding=ROUND_HALF_UP)
        return float(excl), float(incl)

    return 0.0, 0.0
