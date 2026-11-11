import { beforeEach, describe, expect, it, vi } from 'vitest'
import { actionNames } from '../business'
import { primaryActions } from '../row-actions'
import { salesColumns, salesCommand } from './sales'
import { user } from '../session'

vi.mock('../api', () => ({ read: vi.fn(), all: vi.fn(async () => [{ id: 1, name: '张工', roles: ['manager'] }]), download: vi.fn(), write: vi.fn() }))

describe('销售列表与签约对话框', () => {
  beforeEach(() => { user.value = { id: 1, roles: ['admin'] } })

  it('合同金额列：未签约显示报价金额并带标记，未报价显示破折号，已签约显示合同金额', () => {
    const column = salesColumns.find(item => item.key === 'contract_amount')!
    expect(column.label).toBe('报价 / 合同金额')
    expect(column.format!({ status: 'quoted', quote_amount: '500000.00', contract_amount: '0.00' })).toBe('500,000.00 报价')
    expect(column.format!({ status: 'draft', quote_amount: '0.00', contract_amount: '0.00' })).toBe('—')
    expect(column.format!({ status: 'signed', quote_amount: '500000.00', contract_amount: '480000.00' })).toBe('480,000.00')
  })

  it('各阶段的下一步动作排在行内主按钮：草稿报价、已报价签约、已签约交付与回款', () => {
    const primary = (row: Record<string, unknown>) => primaryActions.find(name => actionNames('sales', row).includes(name))
    expect(primary({ status: 'draft', manager: 1 })).toBe('报价')
    expect(primary({ status: 'quoted', manager: 1 })).toBe('签约')
    expect(primary({ status: 'signed', manager: 1 })).toBe('交付与回款')
  })

  it('签约：成员可搜索多选，收款节点按表格行排列，节点合计与报价不符时前端给出差额', async () => {
    const command = await salesCommand({ id: 3, status: 'quoted', manager: 1, name: '检测线', customer_name: '甲公司', quote_amount: '500000.00', equipment_quantity: 2 }, '签约')
    expect(command.fields.find(field => field.key === 'members')).toMatchObject({ searchableMulti: true })
    expect(command.fields.find(field => field.key === 'milestones')).toMatchObject({ dense: true })
    expect(command.notice?.text).toContain('甲公司 · 检测线 · 报价 500,000.00 元 · 设备 2 台')
    const mismatch = command.fields.find(field => field.key === 'milestone_mismatch')!
    expect(mismatch.visibleWhen!({ milestones: [{ amount: '300000' }, { amount: '100000.50' }] })).toBe(true)
    expect(mismatch.visibleWhen!({ milestones: [{ amount: '300000' }, { amount: '200000.00' }] })).toBe(false)
    expect(() => command.prepare!({ milestones: [{ amount: '300000' }, { amount: '100000.50' }] })).toThrow('差额 -99,999.50 元')
    const ok = { milestones: [{ amount: '300000' }, { amount: '200000' }] }
    expect(command.prepare!(ok)).toBe(ok)
  })

  it('报价说明选填，编辑与取消销售的原因仍必填', async () => {
    const quote = await salesCommand({ id: 3, status: 'draft', manager: 1 }, '报价')
    expect(quote.fields.find(field => field.key === 'reason')).toMatchObject({ label: '报价说明', optional: true })
    const cancel = await salesCommand({ id: 3, status: 'draft', manager: 1 }, '取消销售')
    expect(cancel.fields.find(field => field.key === 'reason')?.optional).toBeUndefined()
  })

  it('销售明细与交付回款的金额统一千分位', async () => {
    const api = await import('../api')
    vi.mocked(api.read).mockResolvedValueOnce({ deliveries: [], receivables: [{ title: '验收款', balance: '150000.00', paid: '0.00', amount: '150000.00', credit_amount: '0.00' }] })
    const progress = await salesCommand({ id: 5, status: 'signed' }, '交付与回款')
    expect(progress.initial?.receivables[0]).toMatchObject({ balance: '150,000.00', amount: '150,000.00', paid: '0.00' })
    const detail = await salesCommand({ id: 5, status: 'signed', quote_amount: '500000.00', contract_amount: '500000.00', original_contract_amount: null }, '查看明细')
    expect(detail.initial).toMatchObject({ quote_amount: '500,000.00', contract_amount: '500,000.00', original_contract_amount: null })
  })
})
