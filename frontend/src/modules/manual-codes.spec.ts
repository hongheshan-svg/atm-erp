import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { all, read } from '../api'
import { actionCommand, createCommand } from '../business'
import { payload } from '../forms'
import { canImportResource, user } from '../session'
import { salesCommand } from './sales'
import { reconciliationCommand } from './settlement'

vi.mock('../api', () => ({ all: vi.fn(), read: vi.fn(), download: vi.fn(), write: vi.fn() }))
beforeEach(() => {
  user.value = { id: 1, roles: ['admin'] }
  vi.mocked(all).mockResolvedValue([])
  vi.mocked(read).mockResolvedValue({ lines: [] })
})
afterEach(() => { vi.resetAllMocks(); user.value = null })

it('所有新增编号入口均可留空且保留手工编号中的前导零', async () => {
  const commands = await Promise.all([
    ...['items', 'partners', 'projects', 'purchases'].map(resource => createCommand(resource)),
    salesCommand(),
    actionCommand('projects', { id: 1, status: 'active', can_manage: true }, '发货'),
    reconciliationCommand({ id: 1, project: 1, balance: '100' }),
  ])
  for (const command of commands) {
    const field = command.fields.find(f => f.key === 'code')!
    expect(field?.optional).toBe(true)
    expect(payload([field], { code: '00001-A' })).toEqual({ code: '00001-A' })
    expect(payload([field], { code: '' })).toEqual({})
  }
})

it('编号不得通过编辑物料或单位变更，销售签约另填执行项目编号', async () => {
  for (const resource of ['items', 'partners']) {
    const command = await actionCommand(resource, { id: 1 }, '编辑')
    expect(command.fields.some(f => f.key === 'code')).toBe(false)
  }
  const command = await salesCommand({ id: 2, status: 'quoted' }, '签约')
  expect(command.fields.find(f => f.key === 'project_code')?.optional).toBe(true)
})

it('对账草稿导入仅开放财务及管理员', () => {
  user.value = { roles: ['manager'] }
  expect(canImportResource('reconciliations')).toBe(false)
  user.value = { roles: ['finance'] }
  expect(canImportResource('reconciliations')).toBe(true)
})

it('销售的人员单选可搜索：负责人、签约的项目负责人、转交的新销售负责人', async () => {
  vi.mocked(all).mockResolvedValue([{ id: 2, display_name: '李经理', roles: ['admin', 'manager', 'sales_manager'] }])
  const create = await salesCommand()
  expect(create.fields.find(f => f.key === 'manager')?.searchable).toBe(true)
  const sign = await salesCommand({ id: 2, status: 'quoted' }, '签约')
  expect(sign.fields.find(f => f.key === 'manager')?.searchable).toBe(true)
  const transfer = await salesCommand({ id: 2, status: 'signed', manager: 9 }, '转交负责人')
  expect(transfer.fields.find(f => f.key === 'manager')?.searchable).toBe(true)
})
