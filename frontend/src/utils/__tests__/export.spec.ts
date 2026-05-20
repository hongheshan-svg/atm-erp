import { describe, it, expect, vi, beforeEach } from 'vitest'
import { formatMoney, formatDateStr, exportToExcel, exportTableData } from '../export'

describe('formatMoney', () => {
  it('formats a normal number', () => {
    expect(formatMoney(1234.5)).toBe('1234.50')
  })

  it('formats string number', () => {
    expect(formatMoney('99.999')).toBe('100.00')
  })

  it('returns 0.00 for null', () => {
    expect(formatMoney(null)).toBe('0.00')
  })

  it('returns 0.00 for undefined', () => {
    expect(formatMoney(undefined)).toBe('0.00')
  })

  it('formats zero', () => {
    expect(formatMoney(0)).toBe('0.00')
  })

  it('formats negative value', () => {
    expect(formatMoney(-15.7)).toBe('-15.70')
  })
})

describe('formatDateStr', () => {
  it('formats a valid ISO date', () => {
    const result = formatDateStr('2024-03-15')
    expect(result).toContain('2024')
  })

  it('returns empty for null', () => {
    expect(formatDateStr(null)).toBe('')
  })

  it('returns empty for undefined', () => {
    expect(formatDateStr(undefined)).toBe('')
  })

  it('returns original string for invalid date', () => {
    expect(formatDateStr('not-a-date')).toBe('not-a-date')
  })

  it('returns empty for empty string', () => {
    expect(formatDateStr('')).toBe('')
  })
})

describe('exportToExcel', () => {
  let createObjectURL: any
  let revokeObjectURL: any

  beforeEach(() => {
    createObjectURL = vi.fn(() => 'blob:test')
    revokeObjectURL = vi.fn()
    Object.defineProperty(window, 'URL', {
      value: { createObjectURL, revokeObjectURL },
      writable: true
    })

    vi.spyOn(document, 'createElement').mockReturnValue({
      setAttribute: vi.fn(),
      click: vi.fn(),
      style: {},
    } as any)
    vi.spyOn(document.body, 'appendChild').mockImplementation(vi.fn())
    vi.spyOn(document.body, 'removeChild').mockImplementation(vi.fn())
  })

  it('creates a CSV blob and triggers download', () => {
    const data = [
      { name: 'Item A', price: 100 },
      { name: 'Item B', price: 200 },
    ]
    const columns = [
      { field: 'name', title: '名称' },
      { field: 'price', title: '价格' },
    ]

    exportToExcel(data, columns, 'test')

    expect(createObjectURL).toHaveBeenCalled()
    expect(revokeObjectURL).toHaveBeenCalled()
  })

  it('handles empty data', () => {
    exportToExcel([], [{ field: 'name', title: '名称' }], 'empty')
    expect(createObjectURL).toHaveBeenCalled()
  })

  it('handles formatter in columns', () => {
    const data = [{ status: 'ACTIVE' }]
    const columns = [
      { field: 'status', title: '状态', formatter: (v: string) => v === 'ACTIVE' ? '激活' : '停用' },
    ]

    exportToExcel(data, columns, 'formatted')
    expect(createObjectURL).toHaveBeenCalled()
  })
})

describe('exportTableData', () => {
  beforeEach(() => {
    Object.defineProperty(window, 'URL', {
      value: { createObjectURL: vi.fn(() => 'blob:test'), revokeObjectURL: vi.fn() },
      writable: true
    })
    vi.spyOn(document, 'createElement').mockReturnValue({
      setAttribute: vi.fn(),
      click: vi.fn(),
      style: {},
    } as any)
    vi.spyOn(document.body, 'appendChild').mockImplementation(vi.fn())
    vi.spyOn(document.body, 'removeChild').mockImplementation(vi.fn())
  })

  it('converts fieldMap to columns and exports', () => {
    const data = [{ name: 'Test', amount: 500 }]
    const fieldMap = { name: '名称', amount: '金额' }

    exportTableData(data, fieldMap, 'simple')
    expect(window.URL.createObjectURL).toHaveBeenCalled()
  })
})
