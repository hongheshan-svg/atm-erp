import { beforeEach, describe, expect, it, vi } from 'vitest'
import { all, read } from '../api'
import { actionCommand, actionNames, createCommand } from '../business'
import { user } from '../session'
import { shortageCommand } from './purchases'
import { navigation } from '../navigation'
import { userFields } from './settings'

vi.mock('../api', () => ({ all: vi.fn(), read: vi.fn(), write: vi.fn() }))

describe('模块边界', () => {
  it('兼岗菜单合并，销售写权限仍区分本人和他人', () => {
    user.value = { id: 7, role: 'sales_manager', roles: ['sales_manager', 'purchaser'] }
    expect(navigation().map(n => n.key)).toContain('purchases')
    expect(navigation().map(n => n.key)).not.toContain('finance')
    expect(actionNames('sales', { status: 'quoted', manager: 7 })).toContain('签约')
    user.value = { id: 7, roles: ['sales_manager', 'finance'] }
    expect(actionNames('sales', { status: 'quoted', manager: 8 })).not.toContain('签约')
    expect(actionNames('sales', { status: 'quoted', manager: 7 })).toContain('签约')
    expect(userFields.find(f => f.key === 'roles')?.type).toBe('checks')
  })
  it('销售经理的签约交接与菜单不继承项目管理权限', async () => {
    user.value = { id: 7, role: 'sales_manager' }
    expect(navigation().map(n => n.key)).toEqual(['workbench', 'sales', 'masterdata', 'settings'])
    expect(userFields.find(f => f.key === 'roles')?.options).toContainEqual({ value: 'sales_manager', label: '销售经理' })
    vi.mocked(all).mockResolvedValue([{ id: 7, role: 'sales_manager' }, { id: 8, role: 'manager' }, { id: 9, role: 'finance' }])
    const create = await createCommand('sales')
    expect(create.fields.find(f => f.key === 'manager')?.options?.map(o => o.value)).toEqual([7])
    const sign = await actionCommand('sales', { id: 1, manager: 7, status: 'quoted' }, '签约')
    expect(sign.fields.find(f => f.key === 'manager')?.options?.map(o => o.value)).toEqual([8])
    expect(sign.fields.find(f => f.key === 'manager')?.initial).toBeUndefined()
    expect(actionNames('sales', { status: 'signed', manager: 7 })).toEqual(['查看明细', '交付与回款', '附件'])
    expect(actionNames('purchases', { status: 'submitted' })).not.toContain('批准采购')
  })
  it('相同物料跨单元下单仍保留每个 BOM 行，不按物料覆盖关联', async () => {
    vi.mocked(read).mockResolvedValue({ lines: [{ bom_line: 11, item: 1, shortage: '2' }, { bom_line: 12, item: 1, shortage: '3' }] })
    const command = await shortageCommand(9, [11, 12])
    expect(command.prepare?.({ lines: [{ item: 1, quantity: '2', unit_price: '10' }, { item: 1, quantity: '3', unit_price: '10' }] }).lines.map((l: { bom_line: number }) => l.bom_line)).toEqual([11, 12])
  })
  it('BOM 采购只带入勾选项，缺口变化后拒绝沿用选择', async () => {
    vi.mocked(all).mockResolvedValue([])
    vi.mocked(read).mockResolvedValue({ lines: [{ bom_line: 11, item: 1, shortage: '2' }, { bom_line: 12, item: 2, shortage: '3' }] })
    const command = await shortageCommand(9, [12])
    expect(command.initial?.lines).toEqual([{ item: 2, item_label: 2, bom_line: 12, quantity: '3', unit_price: '' }])
    expect(command.prepare?.({ lines: [{ item: 2, quantity: '1', unit_price: '10' }] }).lines[0].bom_line).toBe(12)
    vi.mocked(read).mockResolvedValue({ lines: [{ bom_line: 12, item: 2, shortage: '0' }] })
    await expect(shortageCommand(9, [12])).rejects.toThrow('状态已变化')
  })
  it('编码规则带版本且无日期可提交，物料仅新建时可手工编码', async () => {
    user.value = { role: 'admin' }
    const c = await actionCommand('codes', { id: 1, revision: 2, date_format: '' }, '编辑')
    expect(c.initial?.date_format).toBe('none')
    expect(c.prepare?.({ date_format: 'none' })).toEqual({ date_format: '', expected_revision: 2 })
    expect((await createCommand('items')).fields.some(f => f.key === 'code')).toBe(true)
    expect((await actionCommand('items', { id: 1 }, '编辑')).fields.some(f => f.key === 'code')).toBe(false)
    expect((await actionCommand('sales', { id: 1, status: 'quoted' }, '签约')).fields.some(f => f.key === 'contract_number')).toBe(true)
    user.value = { role: 'manager' }
    expect(actionNames('codes', { id: 1 })).toEqual([])
  })
  beforeEach(() => {
    vi.clearAllMocks()
    user.value = { role: 'manager' }
    vi.mocked(all).mockResolvedValue([])
  })

  it('超预算审批明确确认并携带服务端快照，不提交展示金额', async () => {
    vi.mocked(read).mockResolvedValue({ over_budget: true, configured: true, warnings: ['超预算'],
      purchase_amount: '400', occupied_total: '400', purchase_net: '400', snapshot: 'latest' })
    const command = await actionCommand('purchases', { id: 8, status: 'submitted' }, '批准采购')
    expect(command.path).toBe('/business/purchases/8/approve-over-budget/')
    expect(command.fields.find(f => f.key === 'confirmed')?.initial).toBe(false)
    expect(command.prepare?.({ reason: '交期需要', confirmed: true, purchase_amount: '1' })).toEqual({
      reason: '交期需要', confirmed: true, expected_snapshot: 'latest',
    })
    vi.mocked(read).mockResolvedValue({ over_budget: false, configured: false, purchase_amount: '400' })
    const normal = await actionCommand('purchases', { id: 8 }, '批准采购')
    expect(normal.path).toBe('/business/purchases/8/approve/')
    expect(normal.notice?.text).toContain('未设置预算')
  })

  it('冲销后保留流水，但不再提供重复冲销和工时更正', () => {
    user.value = { role: 'finance' }
    expect(actionNames('payments', { reversal_of: null, reversed_by: null })).toContain('冲销付款')
    expect(actionNames('payments', { reversal_of: null, reversed_by: 2 })).not.toContain('冲销付款')
    expect(actionNames('payments', { reversal_of: 1, reversed_by: null })).not.toContain('冲销付款')
    expect(actionNames('payments', { reversal_of: null, reversed_by: 2 })).toContain('补录凭证')
    user.value = { role: 'manager' }
    expect(actionNames('time', { hours: '3', reversed_by: null })).toContain('更正工时')
    expect(actionNames('time', { hours: '3', reversed_by: 4 })).toEqual([])
  })

  it('无销售合同的已交付项目也隐藏交付约定编辑', async () => {
    const command = await actionCommand('projects', { id: 1, status: 'delivering', contract_date: null }, '编辑项目')
    expect(command.fields.map(f => f.key)).not.toContain('equipment_quantity')
    expect(command.fields.map(f => f.key)).not.toContain('warranty_months')
    expect(command.fields.map(f => f.key)).toContain('requirements')
  })

  it('已完成任务可补录工时，取消任务不提供入口', () => {
    user.value = { role: 'member', id: 7 }
    expect(actionNames('tasks', { status: 'done', assignee: 7, kind: 'test' })).toEqual(['登记工时'])
    expect(actionNames('tasks', { status: 'cancelled', assignee: 7, kind: 'test' })).toEqual([])
    expect(actionNames('tasks', { status: 'done', assignee: 8, kind: 'test' })).toEqual([])
  })

  it('销售表单不依赖项目或库存接口，签约负责交接人员', async () => {
    vi.mocked(all).mockImplementation(async (path) => {
      if (path.includes('/projects/') || path.includes('/stocks/'))
        throw new Error('无关模块不可用')
      return []
    })
    const create = await createCommand('sales')
    expect(create.path).toBe('/business/sales/')
    expect(all).toHaveBeenCalledTimes(2)
    const sign = await actionCommand('sales', { id: 7, manager: 2, quote_amount: '100' }, '签约')
    expect(sign.path).toBe('/business/sales/7/sign/')
    expect(sign.fields.map((f) => f.key)).toEqual(['date', 'contract_number', 'manager', 'members', 'milestones'])
    expect(actionNames('projects', { status: 'quoted' })).not.toContain('签约')
    expect(actionNames('sales', { status: 'quoted' })).toContain('签约')
  })

  it('基础资料和用户维护不请求业务模块目录', async () => {
    await createCommand('items')
    await createCommand('partners')
    user.value = { role: 'admin' }
    await createCommand('users')
    expect(all).not.toHaveBeenCalled()
  })

  it('设置与基础资料编辑保持各自字段，用户密码可留空', async () => {
    const item = await actionCommand('items', { id: 1 }, '编辑')
    expect(item.fields.map(f => f.key)).toEqual(['name', 'specification', 'brand', 'part_type', 'unit', 'duplicate_reason', 'is_active'])
    const account = await actionCommand('users', { id: 2 }, '编辑')
    expect(account.fields.find(f => f.key === 'password')?.optional).toBe(true)
    expect(account.fields.filter(f => f.key === 'is_active')).toHaveLength(1)
    const company = await actionCommand('company', { id: 1 }, '编辑')
    expect(company.fields.map(f => f.key)).toEqual(['name', 'address', 'phone'])
    await expect(actionCommand('audit', { id: 1 }, '编辑')).rejects.toThrow('不支持')
  })

  it('销售编辑保留原值和版本，提示重新报价', async () => {
    const row = { id: 7, name: '原销售', updated_at: '2026-09-09T00:00:00Z' }
    const command = await actionCommand('sales', row, '编辑销售')
    expect(command.initial).toEqual(row)
    expect(command.prepare?.({ name: '更正' })).toEqual({ name: '更正', expected_updated_at: row.updated_at })
    expect(command.fields.find(f => f.key === 'reason')?.hint).toContain('重新报价')
  })

  it('签约后仅经理可签补充协议，财务仍只读', () => {
    expect(actionNames('sales', { status: 'signed' })).toEqual(['查看明细', '补充协议记录', '签订补充协议', '附件'])
    user.value = { role: 'finance' }
    expect(actionNames('sales', { status: 'signed' })).toEqual(['查看明细', '补充协议记录', '附件'])
    expect(actionNames('sales', { status: 'quoted' })).toEqual(['查看明细', '附件'])
  })
})
