import { expect, it } from 'vitest'
import { money } from './money'

it('金额按字符串分组，不经过 Number', () => {
  expect(money('1234567.5')).toBe('1,234,567.50')
  expect(money('0')).toBe('0.00')
  // 超过 2^53 的分位仍要逐位保留，走 Number 会被改写。
  expect(money('9007199254740993.01')).toBe('9,007,199,254,740,993.01')
})

it('空值、货币前缀和待退款各自只有一种写法', () => {
  expect(money(null)).toBe('—')
  expect(money(null, { placeholder: '未设置' })).toBe('未设置')
  expect(money('1234', { currency: true })).toBe('¥ 1,234.00')
  expect(money('-1234', { refund: true })).toBe('待退款 1,234.00')
  expect(money('-1234')).toBe('-1,234.00')
})
