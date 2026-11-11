import { expect, it } from 'vitest'
import { dateTimeText } from './datetime'

it('时间统一为 YYYY-MM-DD HH:mm，空值给占位', () => {
  expect(dateTimeText('2026-11-11T07:28:48.750224+08:00')).toBe('2026-11-11 07:28')
  expect(dateTimeText(null)).toBe('—')
})

it('UTC 时间（Z 或 +00:00）按 Asia/Shanghai 显示，跨日也正确', () => {
  expect(dateTimeText('2026-11-11T02:20:30.123456Z')).toBe('2026-11-11 10:20')
  expect(dateTimeText('2026-11-10T16:05:00+00:00')).toBe('2026-11-11 00:05')
  expect(dateTimeText('2026-11-10T23:59:59Z')).toBe('2026-11-11 07:59')
})

it('不带时区的时间和纯日期按业务本地时间原样截取', () => {
  expect(dateTimeText('2026-10-01T08:00:00')).toBe('2026-10-01 08:00')
  expect(dateTimeText('2026-10-01')).toBe('2026-10-01')
})
