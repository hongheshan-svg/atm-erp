import { describe, expect, it } from 'vitest'
import { quantityText } from './quantity'

describe('quantityText', () => {
  it('去尾零，最多三位小数', () => {
    expect(quantityText('2.000')).toBe('2')
    expect(quantityText('1.500')).toBe('1.5')
    expect(quantityText('0.000')).toBe('0')
    expect(quantityText('140.000')).toBe('140')
    expect(quantityText('0.125')).toBe('0.125')
    expect(quantityText('10')).toBe('10')
    expect(quantityText(3)).toBe('3')
    expect(quantityText('-0.000')).toBe('0')
    expect(quantityText('-1.250')).toBe('-1.25')
  })
  it('空值给占位，非数字原样返回', () => {
    expect(quantityText(null)).toBe('—')
    expect(quantityText('')).toBe('—')
    expect(quantityText('', '')).toBe('')
    expect(quantityText('abc')).toBe('abc')
  })
})
