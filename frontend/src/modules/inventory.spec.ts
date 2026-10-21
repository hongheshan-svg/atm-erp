import { beforeEach, expect, it, vi } from 'vitest'
import { all, read } from '../api'
import { fieldIssues } from '../forms'
import { industryCommand } from '../industry-forms'
import { user } from '../session'
import { actionCommand, createCommand } from './inventory'

vi.mock('../api', () => ({ all: vi.fn(), read: vi.fn() }))

beforeEach(() => {
  user.value = { id: 2, roles: ['warehouse'] }
  vi.mocked(all).mockResolvedValue([])
  vi.mocked(read).mockResolvedValue(['主仓'])
})

it.each([
  ['期初入库', 'stocks', 'opening'],
  ['领料', 'stocks', 'issue'],
  ['退料', 'moves', 'return-material'],
  ['采购退货', 'moves', 'return-purchase'],
])('%s数量在提交前拒绝零值，允许最小数量0.001', async (name, resource, route) => {
  user.value = { id: 1, roles: ['admin'] }
  const command = industryCommand(name === '期初入库'
    ? await createCommand(resource)
    : await actionCommand(resource, { id: 1, quantity: '5.000' }, name))
  expect(command.path).toContain(`/${route}/`)
  const fields = command.fields.filter(field => field.key === 'quantity')
  expect(fields).toHaveLength(1)
  for (const quantity of ['0', '0.000']) {
    expect(fieldIssues(fields, { quantity })).toEqual([
      { path: 'quantity', label: '数量', message: '数量不能小于 0.001。' },
    ])
  }
  for (const quantity of ['-0.001', '0.0001']) expect(fieldIssues(fields, { quantity })).toHaveLength(1)
  for (const quantity of ['0.001', '1', '12.345']) expect(fieldIssues(fields, { quantity })).toEqual([])
})

it('盘点实盘数量允许零，仍拒绝负数', async () => {
  const command = industryCommand(await actionCommand('stocks', { id: 1, quantity: '5.000' }, '盘点'))
  const fields = command.fields.filter(field => field.key === 'quantity')
  for (const quantity of ['0', '0.000', '0.001']) expect(fieldIssues(fields, { quantity })).toEqual([])
  expect(fieldIssues(fields, { quantity: '-0.001' })).toHaveLength(1)
})

it('零库存盘盈向仓管说明管理员操作路径，仍不提供成本字段', async () => {
  const command = await actionCommand('stocks', { id: 1, quantity: '0.000', updated_at: 't1' }, '盘点')
  expect(command.fields.find(field => field.key === 'quantity')?.hint).toContain('管理员在库存页面盘点并填写单位成本')
  expect(command.fields.some(field => field.key === 'unit_cost')).toBe(false)
  expect(command.prepare?.({ quantity: '3', reason: '实盘' })).toEqual({ quantity: '3', reason: '实盘', expected_quantity: '0.000', expected_updated_at: 't1' })
})

it('管理员零库存盘盈仍填写单位成本', async () => {
  user.value = { id: 1, roles: ['admin'] }
  const command = await actionCommand('stocks', { id: 1, quantity: '0.000' }, '盘点')
  expect(command.fields.some(field => field.key === 'unit_cost')).toBe(true)
})

it('非零库存盘点不出现零库存处理提示', async () => {
  const command = await actionCommand('stocks', { id: 1, quantity: '5.000' }, '盘点')
  expect(command.fields.find(field => field.key === 'quantity')?.hint).toBeUndefined()
})
