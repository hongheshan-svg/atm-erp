import { describe, expect, it } from 'vitest'
import { formatPurchaseAmount, purchaseLineCents, quantityValue } from './bom-purchase'

describe('BOM 采购数量与金额预览', () => {
  it('数量保持千分位精度，允许零库存和前后空白', () => {
    expect(quantityValue('0')).toBe(0n)
    expect(quantityValue(' 001.005 ')).toBe(1005n)
    expect(quantityValue(2.5)).toBe(2500n)
    expect(quantityValue('999999999999999.999')).toBe(999999999999999999n)
  })

  it.each([
    null, undefined, '', ' ', true, {}, [], 1n, NaN, Infinity,
    '-1', '-0', '+1', '1e3', '1E-3', '1,000', '.5', '1.', '1.0000',
    '1000000000000000', Number.MAX_SAFE_INTEGER + 1,
  ])('拒绝无效数量 %s', (value) => {
    expect(quantityValue(value)).toBeNull()
    expect(purchaseLineCents(value, '1')).toBeNull()
  })

  it('采购数量必须大于零，零价格可以保存', () => {
    expect(purchaseLineCents('0', '1')).toBeNull()
    expect(purchaseLineCents('0.000', '1')).toBeNull()
    expect(purchaseLineCents('1', '0')).toBe(0n)
  })

  it.each([
    null, undefined, '', ' ', false, {}, [], 1n, NaN, Infinity,
    '-0.01', '-0', '+1', '1e3', '1E-2', '1,000', '.5', '1.', '1.001',
    '10000000000000000', Number.MAX_SAFE_INTEGER + 1,
  ])('拒绝无效价格 %s', (value) => {
    expect(purchaseLineCents('1', value)).toBeNull()
  })

  it.each([
    ['0.001', '5', 1n],
    ['1.005', '1', 101n],
    ['0.001', '4.99', 0n],
    ['0.001', '5.01', 1n],
    ['0.099', '0.05', 0n],
    ['0.100', '0.05', 1n],
    ['3.125', '0.08', 25n],
    ['2.555', '9.99', 2552n],
  ])('逐行四舍五入：%s × %s', (quantity, price, expected) => {
    expect(purchaseLineCents(quantity, price)).toBe(expected)
  })

  it('先将每行舍入到分再合计，保留多行半分尾差', () => {
    const lines = [purchaseLineCents('0.001', '5'), purchaseLineCents('0.001', '5')]
    const total = lines.reduce<bigint>((sum, line) => sum + line!, 0n)
    expect(total).toBe(2n)
    expect(formatPurchaseAmount(total)).toBe('0.02')
    expect(purchaseLineCents('0.002', '5')).toBe(1n)
  })

  it('示例采购单的单价、数量和含税合计一致', () => {
    const total = purchaseLineCents('4', '1500')! + purchaseLineCents('8', '260')! + purchaseLineCents('2', '180')!
    expect(total).toBe(844000n)
    expect(formatPurchaseAmount(total)).toBe('8,440.00')
  })

  it('大金额乘法及格式化不损失整数和分角', () => {
    expect(purchaseLineCents('1', '9999999999999999.99')).toBe(999999999999999999n)
    expect(purchaseLineCents('999999999999999.999', '9999999999999999.99'))
      .toBe(999999999999999998000000000000000n)
    expect(formatPurchaseAmount(999999999999999999n)).toBe('9,999,999,999,999,999.99')
  })

  it('缺失金额显示待填写，零值和负值格式清楚', () => {
    expect(formatPurchaseAmount(null)).toBe('待填写')
    expect(formatPurchaseAmount(0n)).toBe('0.00')
    expect(formatPurchaseAmount(5n)).toBe('0.05')
    expect(formatPurchaseAmount(-123456n)).toBe('-1,234.56')
  })
})
