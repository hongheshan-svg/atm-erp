import { describe, it, expect } from 'vitest'
import { toFixedSafe, subtractFixedSafe } from '../number'

describe('toFixedSafe', () => {
  it('formats a normal number', () => {
    expect(toFixedSafe(123.456)).toBe('123.46')
  })

  it('formats integer values', () => {
    expect(toFixedSafe(100)).toBe('100.00')
  })

  it('handles string numbers', () => {
    expect(toFixedSafe('99.9')).toBe('99.90')
  })

  it('handles null', () => {
    expect(toFixedSafe(null)).toBe('0.00')
  })

  it('handles undefined', () => {
    expect(toFixedSafe(undefined)).toBe('0.00')
  })

  it('handles NaN string', () => {
    expect(toFixedSafe('abc')).toBe('0.00')
  })

  it('handles Infinity', () => {
    expect(toFixedSafe(Infinity)).toBe('0.00')
  })

  it('respects custom digits', () => {
    expect(toFixedSafe(3.14159, 4)).toBe('3.1416')
  })

  it('uses custom fallback', () => {
    expect(toFixedSafe('not_a_number', 2, 'N/A')).toBe('N/A')
  })

  it('handles zero', () => {
    expect(toFixedSafe(0)).toBe('0.00')
  })

  it('handles negative numbers', () => {
    expect(toFixedSafe(-42.5)).toBe('-42.50')
  })
})

describe('subtractFixedSafe', () => {
  it('subtracts two normal numbers', () => {
    expect(subtractFixedSafe(100, 30)).toBe('70.00')
  })

  it('handles string numbers', () => {
    expect(subtractFixedSafe('200.50', '100.25')).toBe('100.25')
  })

  it('handles null left', () => {
    expect(subtractFixedSafe(null, 10)).toBe('-10.00')
  })

  it('handles null right', () => {
    expect(subtractFixedSafe(50, null)).toBe('50.00')
  })

  it('handles NaN input', () => {
    expect(subtractFixedSafe('abc', 10)).toBe('0.00')
  })

  it('handles both NaN', () => {
    expect(subtractFixedSafe('x', 'y')).toBe('0.00')
  })

  it('respects custom digits', () => {
    expect(subtractFixedSafe(10.1234, 5.5678, 3)).toBe('4.556')
  })

  it('handles negative result', () => {
    expect(subtractFixedSafe(10, 25)).toBe('-15.00')
  })
})
