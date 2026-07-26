import { describe, expect, it } from 'vitest'
import { createInventoryCostConfigForm, toInventoryCostConfigPayload } from '../inventoryCostConfig'

describe('inventory cost config form', () => {
  it('uses backend field names and supported default values', () => {
    expect(createInventoryCostConfigForm()).toEqual({
      id: null,
      name: '',
      costing_method: 'WEIGHTED_AVG',
      period_type: 'MONTHLY',
      include_purchase_price: true,
      include_freight: true,
      include_tax: false,
      include_handling: false,
      is_default: false,
      is_active: true,
      description: ''
    })
  })

  it('sends the selected costing method instead of the obsolete method field', () => {
    const payload = toInventoryCostConfigPayload({
      ...createInventoryCostConfigForm(),
      name: 'FIFO配置',
      costing_method: 'FIFO',
      created_at: '2026-07-26T00:00:00Z'
    })

    expect(payload.costing_method).toBe('FIFO')
    expect(payload).not.toHaveProperty('method')
    expect(payload).not.toHaveProperty('created_at')
  })
})
