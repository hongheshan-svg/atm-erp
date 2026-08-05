"""
Unit tests for apps.core.price_parsing.resolve_import_prices.

Anchor value: 319.20 (含税) ↔ 282.48 (未税) @13%
  282.48 × 1.13 = 319.2024 → round HALF_UP to 2 dp = 319.20
  319.20 / 1.13 = 282.4778... → round HALF_UP to 2 dp = 282.48
"""

from django.test import SimpleTestCase

from apps.core.price_parsing import resolve_import_prices


class ResolvePricesTest(SimpleTestCase):
    # ------------------------------------------------------------------
    # 基础锚点
    # ------------------------------------------------------------------

    def test_inclusive_only_reverse_calculates(self):
        """只填含税单价 → 反算未税，含税原样保留。"""
        excl, incl = resolve_import_prices(None, 319.20, 13)
        self.assertEqual(excl, 282.48)
        self.assertEqual(incl, 319.20)

    def test_exclusive_only_forward_calculates(self):
        """只填未税单价 → 正算含税，未税原样保留。"""
        excl, incl = resolve_import_prices(282.48, None, 13)
        self.assertEqual(excl, 282.48)
        self.assertEqual(incl, 319.20)

    def test_both_given_uses_each_as_is(self):
        """两列都给 → 各按各的，不做重算。"""
        excl, incl = resolve_import_prices(282.48, 319.20, 13)
        self.assertEqual(excl, 282.48)
        self.assertEqual(incl, 319.20)

    # ------------------------------------------------------------------
    # 税率边界
    # ------------------------------------------------------------------

    def test_zero_tax_rate(self):
        """免税 → 含税=未税。"""
        excl, incl = resolve_import_prices(None, 319.20, 0)
        self.assertEqual(excl, 319.20)
        self.assertEqual(incl, 319.20)

    def test_6pct_tax_rate(self):
        """6% 税率。"""
        excl, incl = resolve_import_prices(None, 106.0, 6)
        self.assertEqual(excl, 100.0)
        self.assertEqual(incl, 106.0)

    def test_9pct_tax_rate(self):
        """9% 税率：109.0 含税 → 100.00 未税。"""
        excl, incl = resolve_import_prices(None, 109.0, 9)
        self.assertEqual(excl, 100.0)
        self.assertEqual(incl, 109.0)

    # ------------------------------------------------------------------
    # 零值与 None
    # ------------------------------------------------------------------

    def test_zero_price_inclusive(self):
        excl, incl = resolve_import_prices(None, 0.0, 13)
        self.assertEqual(excl, 0.0)
        self.assertEqual(incl, 0.0)

    def test_zero_price_exclusive(self):
        excl, incl = resolve_import_prices(0.0, None, 13)
        self.assertEqual(excl, 0.0)
        self.assertEqual(incl, 0.0)

    def test_none_both_returns_zeros(self):
        """两侧都是 None → 返回 (0.0, 0.0)，不抛异常。"""
        excl, incl = resolve_import_prices(None, None, 13)
        self.assertEqual(excl, 0.0)
        self.assertEqual(incl, 0.0)

    def test_none_tax_rate_treated_as_zero(self):
        """tax_rate=None → 与 0% 等效。"""
        excl, incl = resolve_import_prices(None, 100.0, None)
        self.assertEqual(excl, 100.0)
        self.assertEqual(incl, 100.0)

    # ------------------------------------------------------------------
    # 舍入
    # ------------------------------------------------------------------

    def test_rounding_half_up(self):
        """100.0 / 1.13 = 88.4956… → ROUND_HALF_UP → 88.50。"""
        excl, _ = resolve_import_prices(None, 100.0, 13)
        self.assertEqual(excl, 88.50)

    def test_return_type_is_float(self):
        excl, incl = resolve_import_prices(None, 319.20, 13)
        self.assertIsInstance(excl, float)
        self.assertIsInstance(incl, float)
