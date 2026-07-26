import { describe, expect, it } from 'vitest'
import {
  getBomEstimatedUnitCost,
  getPurchaseOrderUnitPrice,
  getTaxInclusiveTotal,
  projectFormRules
} from '../businessPricing'

describe('getBomEstimatedUnitCost', () => {
  it('returns the standard unit cost without multiplying by planned quantity', () => {
    expect(getBomEstimatedUnitCost({ standard_cost: '1300.00' })).toBe(1300)
  })
})

describe('getPurchaseOrderUnitPrice', () => {
  it('prefers the last purchase price over master and standard costs', () => {
    expect(
      getPurchaseOrderUnitPrice({
        last_purchase_price: '1200.00',
        purchase_price: '1234.56',
        standard_cost: '1300.00'
      })
    ).toBe(1200)
  })

  it('falls back through purchase price and standard cost', () => {
    expect(getPurchaseOrderUnitPrice({ purchase_price: '1234.56', standard_cost: '1300.00' })).toBe(1234.56)
    expect(getPurchaseOrderUnitPrice({ purchase_price: 0, standard_cost: '1300.00' })).toBe(1300)
  })
})

describe('getTaxInclusiveTotal', () => {
  it('uses the tax-inclusive amount and falls back for legacy zero values', () => {
    expect(getTaxInclusiveTotal({ total_amount: '10000.00', total_with_tax: '11300.00' })).toBe(11300)
    expect(getTaxInclusiveTotal({ total_amount: '10000.00', total_with_tax: 0 })).toBe(10000)
  })
})

describe('projectFormRules', () => {
  it('marks every field required by project submission as required', () => {
    expect(Object.keys(projectFormRules)).toEqual(['name', 'customer', 'manager', 'start_date', 'end_date'])
    for (const rules of Object.values(projectFormRules)) {
      expect(rules[0].required).toBe(true)
    }
  })
})
