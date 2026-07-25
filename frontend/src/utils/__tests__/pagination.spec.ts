import { describe, expect, it } from 'vitest'

import { getPaginationTotal } from '../pagination'

describe('getPaginationTotal', () => {
  it('preserves a zero count from a paginated API response', () => {
    expect(getPaginationTotal({ count: 0, results: [] })).toBe(0)
  })

  it('falls back to the array length for unpaginated responses', () => {
    expect(getPaginationTotal([{ id: 1 }, { id: 2 }])).toBe(2)
  })
})
