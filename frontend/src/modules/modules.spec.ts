import { beforeEach, describe, expect, it, vi } from 'vitest'
import { all } from '../api'
import { actionCommand, actionNames, createCommand } from '../business'
import { user } from '../session'

vi.mock('../api', () => ({ all: vi.fn(), read: vi.fn(), write: vi.fn() }))

describe('模块边界', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    user.value = { role: 'manager' }
    vi.mocked(all).mockResolvedValue([])
  })

  it('冲销后保留流水，但不再提供重复冲销和工时更正', () => {
    user.value = { role: 'finance' }
    expect(actionNames('payments', { reversal_of: null, reversed_by: null })).toContain('冲销付款')
    expect(actionNames('payments', { reversal_of: null, reversed_by: 2 })).toEqual([])
    expect(actionNames('payments', { reversal_of: 1, reversed_by: null })).toEqual([])
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
    expect(sign.fields.map((f) => f.key)).toEqual(['date', 'manager', 'members', 'milestones'])
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
    expect(item.fields.map(f => f.key)).toEqual(['name', 'specification', 'unit', 'is_active'])
    const account = await actionCommand('users', { id: 2 }, '编辑')
    expect(account.fields.find(f => f.key === 'password')?.optional).toBe(true)
    expect(account.fields.filter(f => f.key === 'is_active')).toHaveLength(1)
    const company = await actionCommand('company', { id: 1 }, '编辑')
    expect(company.fields.map(f => f.key)).toEqual(['name', 'address', 'phone'])
    await expect(actionCommand('codes', { id: 1 }, '编辑')).rejects.toThrow('不支持')
  })

  it('销售编辑保留原值和版本，提示重新报价', async () => {
    const row = { id: 7, name: '原销售', updated_at: '2026-09-09T00:00:00Z' }
    const command = await actionCommand('sales', row, '编辑销售')
    expect(command.initial).toEqual(row)
    expect(command.prepare?.({ name: '更正' })).toEqual({ name: '更正', expected_updated_at: row.updated_at })
    expect(command.fields.find(f => f.key === 'reason')?.hint).toContain('重新报价')
  })

  it('财务只读销售，已签约销售不再显示写操作', () => {
    expect(actionNames('sales', { status: 'signed' })).toEqual(['查看明细'])
    user.value = { role: 'finance' }
    expect(actionNames('sales', { status: 'quoted' })).toEqual(['查看明细'])
  })
})
