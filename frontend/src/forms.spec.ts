import { afterEach, describe, it, expect, vi } from 'vitest'
import { defaults, payload, decimalDifference, today } from './forms'
import type { Field } from './types'
describe('业务日期与服务端上海时区一致', () => {
  afterEach(() => vi.useRealTimers())

  it.each([
    ['2026-10-21T15:59:59Z', '2026-10-21'],
    ['2026-10-21T16:00:00Z', '2026-10-22'],
    ['2026-10-21T23:20:00Z', '2026-10-22'],
    ['2026-10-21T23:59:59Z', '2026-10-22'],
    ['2026-10-22T00:00:00Z', '2026-10-22'],
    ['2026-10-31T16:00:00Z', '2026-11-01'],
    ['2026-12-31T15:59:59Z', '2026-12-31'],
    ['2026-12-31T16:00:00Z', '2027-01-01'],
    ['2028-02-28T16:00:00Z', '2028-02-29'],
  ])('%s 默认业务日期为 %s，不依赖运行环境时区', (instant, expected) => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(instant))
    expect(today()).toBe(expected)
  })

  it('跨过业务午夜后重新计算，不缓存旧日期，也不改用户填写日期', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-12-31T15:59:59Z'))
    expect(today()).toBe('2026-12-31')
    vi.setSystemTime(new Date('2026-12-31T16:00:00Z'))
    expect(today()).toBe('2027-01-01')
    expect(payload([{ key: 'date', label: '实际日期', type: 'date' }], { date: '2026-12-30' })).toEqual({ date: '2026-12-30' })
  })
})

describe('安全表单载荷', () => {
  it('只提交可编辑字段，保留十进制字符串并移除选填空值', () => {
    const fields: Field[] = [
      { key: 'quantity', label: '数量' },
      { key: 'note', label: '说明', optional: true },
    ]
    expect(payload(fields, { id: 7, quantity: '123456789012345.001', note: '', unit_cost: '90' })).toEqual({
      quantity: '123456789012345.001',
    })
  })
  it('递归白名单过滤明细，不提交只读价格和审计字段', () => {
    expect(
      payload(
        [
          {
            key: 'lines',
            label: '收货',
            type: 'rows',
            fields: [
              { key: 'line', label: '明细' },
              { key: 'quantity', label: '数量' },
            ],
          },
        ],
        { lines: [{ line: 7, quantity: '0.001', unit_price: '1', created_by: 1 }] },
      ),
    ).toEqual({ lines: [{ line: 7, quantity: '0.001' }] })
  })
  it('保留零值、false 和空成员数组', () => {
    expect(
      defaults(
        [
          { key: 'quantity', label: '数量', initial: 1 },
          { key: 'is_active', label: '启用', type: 'boolean' },
          { key: 'members', label: '成员', type: 'multi' },
        ],
        { quantity: 0, is_active: false, members: [] },
      ),
    ).toEqual({ quantity: 0, is_active: false, members: [] })
  })
  it('大数量与千分位余量计算不经过浮点数', () => {
    expect(decimalDifference('99999999999999.999', '99999999999999.998', '0.000')).toBe('0.001')
    expect(decimalDifference('4.000', '3.000', '0.000')).toBe('1.000')
  })
})
