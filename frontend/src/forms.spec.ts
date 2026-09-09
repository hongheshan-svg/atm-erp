import { describe, it, expect } from 'vitest'
import { defaults, payload, decimalDifference } from './forms'
import type { Field } from './types'
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
