import { describe, it, expect } from 'vitest'
import { isOverdueCell } from './resource-ui'

describe('列表逾期标识', () => {
  const day = '2026-10-23'
  it('未收完的采购早于今天的最近待到货日显示逾期，已收货/取消/当日/未来/空值不显示', () => {
    expect(isOverdueCell('purchases', 'next_delivery_date', { status: 'partial', next_delivery_date: '2026-10-20' }, day)).toBe(true)
    expect(isOverdueCell('purchases', 'next_delivery_date', { status: 'approved', next_delivery_date: '2026-10-22' }, day)).toBe(true)
    for (const status of ['received', 'cancelled']) expect(isOverdueCell('purchases', 'next_delivery_date', { status, next_delivery_date: '2026-10-20' }, day)).toBe(false)
    expect(isOverdueCell('purchases', 'next_delivery_date', { status: 'approved', next_delivery_date: day }, day)).toBe(false)
    expect(isOverdueCell('purchases', 'next_delivery_date', { status: 'approved', next_delivery_date: null }, day)).toBe(false)
    expect(isOverdueCell('purchases', 'payment_due_date', { status: 'approved', payment_due_date: '2026-10-01' }, day)).toBe(false)
  })
  it('待完成任务早于今天的截止日期显示逾期，已完成或当日不显示', () => {
    expect(isOverdueCell('tasks', 'due_date', { status: 'open', due_date: '2026-10-22' }, day)).toBe(true)
    expect(isOverdueCell('tasks', 'due_date', { status: 'done', due_date: '2026-10-22' }, day)).toBe(false)
    expect(isOverdueCell('tasks', 'due_date', { status: 'open', due_date: day }, day)).toBe(false)
  })
})
