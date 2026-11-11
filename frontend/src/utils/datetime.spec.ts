import { expect, it } from 'vitest'
import { dateTimeText } from './datetime'

it('时间统一为 YYYY-MM-DD HH:mm，空值给占位', () => {
  expect(dateTimeText('2026-11-11T07:28:48.750224+08:00')).toBe('2026-11-11 07:28')
  expect(dateTimeText(null)).toBe('—')
})
