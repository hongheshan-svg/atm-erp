import { describe, expect, it, vi } from 'vitest'
import { divideHalfUp, fromScaled, MONEY_SCALE, QUANTITY_SCALE, toScaled } from './decimal'
import { decimalDifference, fieldIssues } from '../forms'
import { sumQuantities } from '../modules/warehouse-lines'
import { shipMaterialOptions } from '../modules/projects'
import { purchaseTotal, receiptStatus } from '../modules/purchases'
import type { Field } from '../types'

vi.mock('../api', () => ({ all: vi.fn(), read: vi.fn(), download: vi.fn() }))

describe('定点小数换算', () => {
  it('按 scale 换算成最小单位，保留符号和前导 0', () => {
    expect(toScaled('12.34', MONEY_SCALE)).toBe(1234n)
    expect(toScaled('12', MONEY_SCALE)).toBe(1200n)
    expect(toScaled('-0.5', MONEY_SCALE)).toBe(-50n)
    expect(toScaled(' 001.005 ', QUANTITY_SCALE)).toBe(1005n)
    expect(toScaled('7', 0)).toBe(7n)
    expect(toScaled(2.5, QUANTITY_SCALE)).toBe(2500n)
    expect(toScaled('-0', QUANTITY_SCALE)).toBe(0n)
    expect(toScaled('99999999999999999999.999', QUANTITY_SCALE)).toBe(99999999999999999999999n)
  })

  it.each([null, undefined, '', ' ', '-', '.5', '5.', '+1', '1e3', '1,000', '1 000', 'abc', true, {}, [], 1n, NaN, Infinity, Number.MAX_SAFE_INTEGER + 2])(
    '格式不符返回 null：%s', value => {
      expect(toScaled(value, QUANTITY_SCALE)).toBeNull()
    })

  it('默认拒绝多余小数位，可选截断（不舍入）', () => {
    expect(toScaled('1.2345', QUANTITY_SCALE)).toBeNull()
    expect(toScaled('1.2349', QUANTITY_SCALE, { excess: 'truncate' })).toBe(1234n)
    expect(toScaled('-1.2349', QUANTITY_SCALE, { excess: 'truncate' })).toBe(-1234n)
  })

  it('可限定非负和整数位数', () => {
    expect(toScaled('-1', QUANTITY_SCALE, { signed: false })).toBeNull()
    expect(toScaled('-0', QUANTITY_SCALE, { signed: false })).toBeNull()
    expect(toScaled('123', MONEY_SCALE, { integerDigits: 3 })).toBe(12300n)
    expect(toScaled('0123', MONEY_SCALE, { integerDigits: 3 })).toBeNull()
  })

  it('格式化补足小数位，负号只出现在最前面', () => {
    expect(fromScaled(0n, QUANTITY_SCALE)).toBe('0.000')
    expect(fromScaled(5n, MONEY_SCALE)).toBe('0.05')
    expect(fromScaled(-500n, QUANTITY_SCALE)).toBe('-0.500')
    expect(fromScaled(-1500n, QUANTITY_SCALE)).toBe('-1.500')
    expect(fromScaled(123456789012345678901234n, MONEY_SCALE)).toBe('1234567890123456789012.34')
    expect(fromScaled(-7n, 0)).toBe('-7')
  })

  it('除法按 ROUND_HALF_UP，恰好一半时远离零', () => {
    expect(divideHalfUp(1499n, 1000n)).toBe(1n)
    expect(divideHalfUp(1500n, 1000n)).toBe(2n)
    expect(divideHalfUp(2500n, 1000n)).toBe(3n)
    expect(divideHalfUp(-1500n, 1000n)).toBe(-2n)
    expect(divideHalfUp(-1499n, 1000n)).toBe(-1n)
    expect(divideHalfUp(1500n, -1000n)).toBe(-2n)
    expect(divideHalfUp(5n, 10n)).toBe(1n)
    expect(divideHalfUp(4n, 10n)).toBe(0n)
  })
})

// 各调用点原有的舍入、截断和容错口径：迁移到共用实现前后必须一致。
describe('调用点保持原有精度口径', () => {
  it('差额截断到三位小数，空串按 0', () => {
    expect(decimalDifference('1.2349', '0.0001')).toBe('1.234')
    expect(decimalDifference('', '1')).toBe('-1.000')
    expect(decimalDifference(' 2.5 ', '0.5')).toBe('2.000')
    expect(decimalDifference('100000000000000000000.001', '0.002')).toBe('99999999999999999999.999')
  })

  it('数量校验的上下限按 scale 精确比较', () => {
    const fields: Field[] = [{ key: 'q', label: '数量', numeric: { scale: 3, min: 0.001, max: 120 } }]
    expect(fieldIssues(fields, { q: '0.001' })).toEqual([])
    expect(fieldIssues(fields, { q: '0.000' }).map(issue => issue.message)).toEqual(['数量不能小于 0.001。'])
    expect(fieldIssues(fields, { q: '120.001' }).map(issue => issue.message)).toEqual(['数量不能大于 120。'])
    const signed: Field[] = [{ key: 'a', label: '金额', numeric: { scale: 2, signed: true, min: -5 } }]
    expect(fieldIssues(signed, { a: '-5.00' })).toEqual([])
    expect(fieldIssues(signed, { a: '-5.01' }).map(issue => issue.message)).toEqual(['金额不能小于 -5。'])
  })

  it('BOM 数量合计保留三位小数', () => {
    expect(sumQuantities([])).toBe('0.000')
    expect(sumQuantities(['1.5', '2', '0.125'])).toBe('3.625')
    expect(sumQuantities(['999999999999999.999', '0.001'])).toBe('1000000000000000.000')
  })

  it('发货配套 BOM 合计截断多余小数位，缺失数量按 0', () => {
    expect(shipMaterialOptions([
      { item: 1, item_code: 'M1', item_name: '导轨', assembly_unit: 'A', quantity: '1.2349' },
      { item: 1, item_code: 'M1', item_name: '导轨', assembly_unit: 'B', quantity: null },
      { item: 1, item_code: 'M1', item_name: '导轨', assembly_unit: 'C', quantity: '' },
      { item: 2, item_code: 'M2', item_name: '螺钉', assembly_unit: 'A', quantity: '0.001' },
    ]).map(option => option.label)).toEqual(['M1 · 导轨 · A、B、C · BOM 合计 1.234', 'M2 · 螺钉 · A · BOM 合计 0.001'])
  })

  it('隔离数量按三位小数累加，空值按 0', () => {
    expect(receiptStatus({ status: 'partial', lines: [{ received_quantity: '1', pending_quantity: '0.5' }, { pending_quantity: null }, { pending_quantity: '' }] })).toBe('部分收货 · 隔离 0.500')
    expect(receiptStatus({ status: 'partial', lines: [{ received_quantity: '1', pending_quantity: '0.000' }] })).toBe('部分收货')
  })

  it('采购含税合计逐行四舍五入到分后相加', () => {
    expect(purchaseTotal([{ quantity: '0.001', unit_price: '5' }, { quantity: '0.001', unit_price: '5' }])).toBe('0.02')
    expect(purchaseTotal([{ quantity: '0.001', unit_price: '4.99' }])).toBe('0.00')
    expect(purchaseTotal([{ quantity: '-1', unit_price: '5' }])).toBe('—')
  })
})
