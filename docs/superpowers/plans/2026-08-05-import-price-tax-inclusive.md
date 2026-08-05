# 实施计划：导入价格统一按含税口径解读

- 规格：`docs/superpowers/specs/2026-08-05-import-price-tax-inclusive-design.md`
- 日期：2026-08-05
- 分支：`fix/purchase-price-tax-mode-and-trace-columns`（当前分支，继续在此分支实施）

## 范围确认

三个导入入口 + 前端新建默认值：

| # | 文件 | 改动摘要 |
|---|---|---|
| T1 | `apps/core/price_parsing.py`（新建） | 公共解析器 `resolve_import_prices` |
| T2 | `apps/purchase/views.py:478` | PR 导入：裸「单价」→ 含税 |
| T3 | `apps/projects/views.py:1790` | BOM 导入：裸「单价」→ 含税 + 补全双向 |
| T4 | `apps/masterdata/views.py:447` | 物料导入：三价列含税反算未税 |
| T5 | `frontend/src/views/purchase/RequestList.vue:759,1061,1402` | 新建默认口径 EXCLUSIVE → INCLUSIVE |
| T6 | 测试（先写） | `test_price_parsing.py` + 三个入口测试 |

## 不做什么

- 不改 `PurchaseRequest.price_input_mode` 的模型字段 `default`
- 不迁移存量 231 条 PR 明细 / 127 条 PO 明细
- 不改 `unit_price`/`estimated_price` 的入账语义
- 不改库存成本、进项税额、预算校验逻辑

---

## T0 — 先跑测试确认基线（无新代码）

```bash
cd /home/administrator/erp
bash scripts/precheck-tests.sh --plan-only   # 确认命中哪些分组
```

---

## T1 — 新建 `apps/core/price_parsing.py`

**文件**：`backend/apps/core/price_parsing.py`（新建）

```python
"""
导入价格解析公共实现。

三个导入入口（采购申请 / BOM 询价 / 物料主数据）统一使用此模块，
消除各自用各自的临时逻辑导致的口径漂移。

解析规则（按优先级）：
  1. 有明确「未税单价」列 → 按未税读（用户显式声明口径，尊重它）
  2. 有「含税单价」列     → 按含税读，反算未税
  3. 只有裸「单价」列     → 按含税读（本次核心改动，从按未税翻转）
  4. 两列都给             → 各按各的，不猜
税率来源由调用方传入，优先级：行内税率列 > 单据表头税率 > 物料税率 > 默认 13
"""

from decimal import ROUND_HALF_UP, Decimal
from typing import Optional, Tuple

# 与 apps.purchase.models.PRICE_QUANT 保持一致：入账价保留 2 位
_QUANT = Decimal('0.01')


def resolve_import_prices(
    raw_exclusive: Optional[float],
    raw_inclusive: Optional[float],
    tax_rate: float,
) -> Tuple[float, float]:
    """返回 (未税单价, 含税单价)，均为 float，2 位小数（ROUND_HALF_UP）。

    Args:
        raw_exclusive: 从「未税单价」列或其别名读到的原始值，None 表示该列缺失/空。
        raw_inclusive: 从「含税单价」列、其别名、**或裸「单价」列**读到的原始值。
                       调用方负责将裸「单价」列的值传入此参数（已在列检测阶段折叠）。
        tax_rate:      百分数形式（13 表示 13%）。
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
```

**验证用例（手算）**：

| raw_exclusive | raw_inclusive | tax_rate | 期望 excl | 期望 incl |
|---|---|---|---|---|
| None | 319.20 | 13 | 282.48 | 319.20 |
| 282.48 | None | 13 | 282.48 | 319.20 |
| 282.48 | 319.20 | 13 | 282.48 | 319.20 |
| None | 319.20 | 0  | 319.20 | 319.20 |
| None | 0 | 13 | 0.00 | 0.00 |
| None | None | 13 | 0.00 | 0.00 |

---

## T2 — 采购申请导入：裸「单价」→ 含税

**文件**：`backend/apps/purchase/views.py`

### 2a. 列检测（约 476 行）—— 翻转裸列归属

**当前**（裸「单价」归 `price_without_tax_column`）：
```python
        if not price_without_tax_column:
            legacy_price_column = find_column(df, ['单价'])
            # 旧模板只有一个「单价」列；若它就是含税列则不要重复当未税用
            if legacy_price_column and legacy_price_column != price_with_tax_column:
                price_without_tax_column = legacy_price_column
```

**改为**（裸「单价」归 `price_with_tax_column`，按含税解读）：
```python
        if not price_with_tax_column:
            legacy_price_column = find_column(df, ['单价'])
            # 裸「单价」列按含税解读（供应商报价均含税）；
            # 若它已被「未税单价」认领则跳过，避免同列当两种口径用
            if legacy_price_column and legacy_price_column != price_without_tax_column:
                price_with_tax_column = legacy_price_column
```

### 2b. 价格解析（约 572 行）—— 引入公共解析器

**导入语句**（在函数头部 import 区已有 `from apps.purchase.models import ...`，在同一块追加）：
```python
        from apps.core.price_parsing import resolve_import_prices
```

**当前**（约 572–580 行）：
```python
            row_tax_rate = _cell_float(row, tax_rate_column, default=default_tax_rate)
            price = _cell_float(row, price_without_tax_column, default=None)
            price_with_tax = _cell_float(row, price_with_tax_column, default=None)
            if price is None and price_with_tax is not None:
                price = float(price_exclusive_from_inclusive(price_with_tax, row_tax_rate))
            elif price is not None and price_with_tax is None:
                price_with_tax = float(price_inclusive_from_exclusive(price, row_tax_rate))
            if price is None:
                price = 0
            if price_with_tax is None:
                price_with_tax = 0
```

**改为**：
```python
            row_tax_rate = _cell_float(row, tax_rate_column, default=default_tax_rate)
            price, price_with_tax = resolve_import_prices(
                raw_exclusive=_cell_float(row, price_without_tax_column),
                raw_inclusive=_cell_float(row, price_with_tax_column),
                tax_rate=row_tax_rate,
            )
```

> `price_with_tax_column` 已在列检测阶段折叠了裸「单价」列，无需再传 `raw_bare` 参数。

---

## T3 — BOM 询价导入：裸「单价」+ 补全双向

**文件**：`backend/apps/projects/views.py`

### 3a. 列检测（约 1790 行，`sku_column` 之后）

在现有两个列检测语句之后追加：
```python
        price_with_tax_column = find_column(df, ['含税单价', '含税价'])
        price_without_tax_column = find_column(df, ['未税单价', '未税价', '不含税单价'])
        # 裸「单价」列：当两个明确列都缺失时，折叠进含税侧（按含税解读）
        if not price_with_tax_column and not price_without_tax_column:
            bare_price_column = find_column(df, ['单价'])
            if bare_price_column:
                price_with_tax_column = bare_price_column
```

### 3b. 导入 price_parsing（在函数内 import 块）

```python
        from apps.core.price_parsing import resolve_import_prices
```

### 3c. 行内价格读取（约 1840 行）

**当前**（各读各的，无补全）：
```python
            price_with_tax = None
            price_without_tax = None
            tax_rate = None
            ...
            if price_with_tax_column and pd.notna(row.get(price_with_tax_column)):
                try:
                    price_with_tax = float(row[price_with_tax_column])
                except (ValueError, TypeError):
                    pass

            if price_without_tax_column and pd.notna(row.get(price_without_tax_column)):
                try:
                    price_without_tax = float(row[price_without_tax_column])
                except (ValueError, TypeError):
                    pass
```

**改为**：
```python
            raw_incl = None
            raw_excl = None
            tax_rate = None
            ...
            if price_with_tax_column and pd.notna(row.get(price_with_tax_column)):
                try:
                    raw_incl = float(row[price_with_tax_column])
                except (ValueError, TypeError):
                    pass

            if price_without_tax_column and pd.notna(row.get(price_without_tax_column)):
                try:
                    raw_excl = float(row[price_without_tax_column])
                except (ValueError, TypeError):
                    pass

            # 统一解析：裸「单价」已折叠进 price_with_tax_column，此处只需传两侧
            row_tax_rate = tax_rate if tax_rate is not None else 13
            price_without_tax, price_with_tax = resolve_import_prices(
                raw_exclusive=raw_excl,
                raw_inclusive=raw_incl,
                tax_rate=row_tax_rate,
            )
            # 若未读到任何价格，退回 None 语义（保持下游「至少一项」校验有效）
            if raw_excl is None and raw_incl is None:
                price_without_tax = None
                price_with_tax = None
```

### 3d. 校验「至少一项」（约 1863 行）—— 保持不变

```python
            if price_with_tax is None and price_without_tax is None:
                error_rows.append(...)
                continue
```

> 此处保持原逻辑，确保用户确实填了价格才能通过。

---

## T4 — 物料主数据导入：三价列含税反算未税

**文件**：`backend/apps/masterdata/views.py`

### 4a. 增加导入

在函数内 import 块（或文件顶部）：
```python
from apps.core.price_parsing import resolve_import_prices
```

### 4b. 在列检测区已有 `tax_col` 之后，无需新增列检测

`tax_col = find_column(df, ['税率', 'tax'])` 已存在（约 170 行）。

### 4c. 替换 `get_num()` 直接写入的三行（约 447–449 行）

在行循环内，`get_num` 定义之后，`item = Item(...)` 或 `item.update(...)` 之前，增加价格解析：

```python
                    # 三个价格列均按含税口径解读；税率取行内列 > 物料自身 tax_rate > 默认13
                    item_tax_rate = get_num(tax_col, default=None)
                    if item_tax_rate is None:
                        # 尝试从已存在物料取税率（更新场景）
                        existing_tax = getattr(item, 'tax_rate', None) if item else None
                        item_tax_rate = existing_tax if existing_tax is not None else 13

                    raw_purchase = get_num(purchase_col, default=None)
                    raw_sale = get_num(sale_col, default=None)
                    raw_cost = get_num(cost_col, default=None)

                    # 列名无"未税"/"含税"前缀 → 归为含税（rule 3）
                    purchase_price_excl, _ = resolve_import_prices(None, raw_purchase, item_tax_rate)
                    sale_price_excl, _ = resolve_import_prices(None, raw_sale, item_tax_rate)
                    standard_cost_excl, _ = resolve_import_prices(None, raw_cost, item_tax_rate)
```

**当前**（约 447–449 行）：
```python
                        purchase_price=get_num(purchase_col),
                        sale_price=get_num(sale_col),
                        standard_cost=get_num(cost_col),
```

**改为**：
```python
                        purchase_price=purchase_price_excl,
                        sale_price=sale_price_excl,
                        standard_cost=standard_cost_excl,
```

> **注意**：`item` 变量在行循环内分"匹配已有物料"和"新建"两条路径，需在两条路径
> 的 field assignment 都应用替换。查找 `purchase_price=get_num(purchase_col)` 全局替换。

### 4d. 更新模板导出表头注释（`export_template` 方法，约 620 行附近）

在「采购单价」「销售单价」「标准成本」的列说明旁追加"(含税，自动反算未税)"备注，
或在 worksheet 注释行添加说明，使用户知道应填含税价。

---

## T5 — 前端新建默认口径

**文件**：`frontend/src/views/purchase/RequestList.vue`

三处需要改，全部从 `'EXCLUSIVE'` → `'INCLUSIVE'`：

| 行号 | 上下文 | 改动 |
|---|---|---|
| 759 | `form` reactive 初值 | `price_input_mode: 'INCLUSIVE'` |
| 1061 | `resetForm()` 内 | `price_input_mode: 'INCLUSIVE'` |
| 1402 | 另一处 reset/初始化 | `price_input_mode: 'INCLUSIVE'` |

**不改**：
- 模型字段 `PurchaseRequest.price_input_mode` 的 `default='EXCLUSIVE'`（ORM 直接创建的历史路径不受影响）
- `data.price_input_mode || 'EXCLUSIVE'`（第 1086 行，这是编辑已有单据时的兜底，保持旧单语义）

---

## T6 — 测试（TDD：先写，T1–T5 实施时运行）

### 6a. 核心公共解析器

**文件**：`backend/apps/core/tests/test_price_parsing.py`（新建）

```python
from decimal import Decimal
from django.test import SimpleTestCase
from apps.core.price_parsing import resolve_import_prices


class ResolvePricesTest(SimpleTestCase):
    """resolve_import_prices 单元测试。锚点：319.20 含税 ↔ 282.48 未税 @13%"""

    def test_inclusive_only_reverse_calculates(self):
        excl, incl = resolve_import_prices(None, 319.20, 13)
        self.assertEqual(excl, 282.48)
        self.assertEqual(incl, 319.20)

    def test_exclusive_only_forward_calculates(self):
        excl, incl = resolve_import_prices(282.48, None, 13)
        self.assertEqual(excl, 282.48)
        self.assertEqual(incl, 319.20)

    def test_both_given_uses_each_as_is(self):
        excl, incl = resolve_import_prices(282.48, 319.20, 13)
        self.assertEqual(excl, 282.48)
        self.assertEqual(incl, 319.20)

    def test_zero_tax_rate(self):
        excl, incl = resolve_import_prices(None, 319.20, 0)
        self.assertEqual(excl, 319.20)
        self.assertEqual(incl, 319.20)

    def test_zero_price(self):
        excl, incl = resolve_import_prices(None, 0, 13)
        self.assertEqual(excl, 0.0)
        self.assertEqual(incl, 0.0)

    def test_none_both_returns_zeros(self):
        excl, incl = resolve_import_prices(None, None, 13)
        self.assertEqual(excl, 0.0)
        self.assertEqual(incl, 0.0)

    def test_rounding_half_up(self):
        # 100 / 1.13 = 88.4956... → 应入账 88.50（ROUND_HALF_UP）
        excl, incl = resolve_import_prices(None, 100.0, 13)
        self.assertEqual(excl, 88.50)

    def test_6pct_tax_rate(self):
        excl, incl = resolve_import_prices(None, 106.0, 6)
        self.assertEqual(excl, 100.0)
        self.assertEqual(incl, 106.0)
```

### 6b. 采购申请导入

**文件**：`backend/apps/purchase/tests/test_pr_import.py`（新建或追加）

核心用例（使用 `APITestCase` + 内存 Excel via `BytesIO` + `openpyxl`）：

```python
# 用例概要（具体 fixture 在实施时补全）

# 1. 只有裸「单价」列 100.00 @13% → estimated_price=88.50, price_with_tax=100.00
# 2. 只有「未税单价」列 282.48 @13% → estimated_price=282.48, price_with_tax=319.20
# 3. 只有「含税单价」列 319.20 @13% → estimated_price=282.48, price_with_tax=319.20
# 4. 「含税单价」列 319.20 + 「未税单价」列 282.48 → 各按各的
# 5. 「含税单价」列不被子串匹配误认为裸「单价」（列名含"含税单价"时，不触发 legacy fallback）
# 6. 行内税率 6% 覆盖表头默认 13%
# 7. 空单价行 → 入账 0（不报错）
```

### 6c. BOM 询价导入

**文件**：`backend/apps/projects/tests/test_bom_import.py`（新建或追加）

```python
# 核心用例：
# 1. 裸「单价」列 → price_with_tax=填入值，price_without_tax 反算
# 2. 只有「含税单价」列 → price_without_tax 反算
# 3. 空价格行 → 报「缺少价格信息」错误（保持原行为）
```

### 6d. 物料主数据导入

```python
# 核心用例：
# 1. 「采购单价」列 319.20 @13% → purchase_price=282.48
# 2. 行内税率 6% → purchase_price = 319.20/1.06 = 301.13
# 3. 无税率列 → 用物料自身 tax_rate（默认 13）
```

### 6e. 前端口径默认值回归

```python
# 确认模型字段 default 未被改动：
# PurchaseRequest._meta.get_field('price_input_mode').default == 'EXCLUSIVE'
#
# 直接 ORM 创建不传 price_input_mode → 入库值为 'EXCLUSIVE'（保留存量语义）
class PRDefaultModeTest(TestCase):
    def test_orm_create_defaults_to_exclusive(self):
        pr = PurchaseRequest(...)
        self.assertEqual(pr.price_input_mode, 'EXCLUSIVE')
```

---

## 实施顺序

```
T6（写测试骨架）
  → T1（写 price_parsing.py，跑 T6a，应全绿）
  → T2（改 PR 导入，跑 T6b）
  → T3（改 BOM 导入，跑 T6c）
  → T4（改物料导入，跑 T6d）
  → T5（改前端默认值）
  → bash scripts/precheck.sh
  → bash scripts/precheck-tests.sh
```

---

## 提交建议

```
feat(import): 导入价格统一按含税口径解读

- 新增 apps/core/price_parsing.resolve_import_prices 公共解析器
- 采购申请导入：裸「单价」列从按未税翻转为按含税，反算 estimated_price
- BOM 询价导入：支持裸「单价」列（含税），补全双向价格
- 物料主数据导入：采购单价/销售单价/标准成本列按含税反算未税后入库
- 前端采购申请新建默认口径改为含税（不改模型字段 default）
- 不迁移存量数据，不改入账字段语义
```
