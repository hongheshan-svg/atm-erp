import { describe, expect, it } from 'vitest'

import { getGoodsReceiptStatusLabel, getGoodsReceiptStatusType } from '@/utils/purchaseStatus'

describe('goods receipt status presentation', () => {
  it('shows confirmed receipts as confirmed instead of in progress', () => {
    expect(getGoodsReceiptStatusLabel('CONFIRMED')).toBe('已确认')
    expect(getGoodsReceiptStatusType('CONFIRMED')).toBe('warning')
  })

  it('keeps completed receipts distinct from confirmed receipts', () => {
    expect(getGoodsReceiptStatusLabel('COMPLETED')).toBe('已完成')
    expect(getGoodsReceiptStatusType('COMPLETED')).toBe('success')
  })
})
