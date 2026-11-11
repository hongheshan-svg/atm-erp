import { beforeEach, describe, expect, it, vi } from 'vitest'
import { all, read } from '../api'
import { defaults, fieldIssues, payload } from '../forms'
import { industryCommand } from '../industry-forms'
import { user } from '../session'
import { actionCommand, actionNames, columns, createCommand, issueSelectable, stockIssueCommand } from './inventory'

vi.mock('../api', () => ({ all: vi.fn(), read: vi.fn() }))

beforeEach(() => {
  user.value = { id: 2, roles: ['warehouse'] }
  vi.mocked(all).mockResolvedValue([])
  vi.mocked(read).mockImplementation(async path => path.includes('locations') ? ['主仓'] : { id: 1, item: 1, quantity: '5.000' })
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
  const fields = (name === '领料' ? command.fields.find(field => field.key === 'lines')!.fields! : command.fields).filter(field => field.key === 'quantity')
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

describe('库存勾选批量领料', () => {
  const stock = (id: number, quantity: string, extra = {}) => ({ id, item: id, item_code: `M-${id}`, item_name: `物料${id}`, location: id === 2 ? '二号仓' : '主仓', unit: '个', quantity, ...extra })
  function mockStocks(rows: object[], tasks: object[] = []) {
    vi.mocked(read).mockResolvedValue({ count: rows.length, results: rows })
    vi.mocked(all).mockResolvedValue(tasks)
  }

  it('只能勾选有库存的行', () => {
    expect(issueSelectable(stock(1, '2.000'))).toBe(true)
    expect(issueSelectable(stock(1, '0.000'))).toBe(false)
    expect(issueSelectable(stock(1, '0.001'))).toBe(true)
  })

  it('打开时按勾选重读当前库存，去掉已领完的行，数量默认留空且必须大于 0', async () => {
    mockStocks([stock(1, '5.000'), stock(2, '0.000'), stock(3, '1.500')])
    const command = await stockIssueCommand([stock(1, '5.000'), stock(2, '3.000'), stock(3, '1.500'), stock(1, '5.000')])
    expect(read).toHaveBeenCalledWith('/business/stocks/', { id__in: '1,2,3', page_size: 3 })
    expect(all).toHaveBeenCalledWith('/business/tasks/', { kind: 'service', status: 'open' })
    expect(command.path).toBe('/business/stocks/bom-issue/')
    expect(command.submitLabel).toBe('确认领料出库（2 行）')
    expect(command.notice).toMatchObject({ type: 'warning' })
    expect(command.notice?.text).toContain('另有 1 行已无可用库存')
    expect(command.fields.map(field => field.key)).toEqual(['project', 'task', 'lines', 'reason', 'confirm_shared'])
    const lines = command.fields.find(field => field.key === 'lines')!
    expect(lines.fields!.find(field => field.key === 'location')?.label).toBe('库位')
    expect(lines.fields!.find(field => field.key === 'remaining')?.label).toBe('本库位可用')
    expect(lines.fields!.some(field => field.key === 'bom_remaining')).toBe(false)
    const data = defaults(command.fields, command.initial)
    expect(data.lines.map((row: { stock: number; quantity: string }) => [row.stock, row.quantity])).toEqual([[1, ''], [3, '']])
    data.project = 7
    expect(fieldIssues(command.fields, data).map(issue => issue.path)).toEqual(['lines.0.quantity', 'lines.1.quantity'])
    data.lines[0].quantity = '0'
    data.lines[1].quantity = '1.5'
    expect(fieldIssues(command.fields, data).map(issue => issue.message)).toEqual(['本次出库第 1 行 · 数量不能小于 0.001。'])
  })

  it('一次提交为同一接口的一批明细：带项目、售后任务、说明与共享确认，备注只在填写时提交', async () => {
    mockStocks([stock(1, '5.000'), stock(2, '4.000')], [{ id: 41, project: 7, title: '现场换件' }, { id: 42, project: 8, title: '别的项目' }])
    const command = await stockIssueCommand([stock(1, '5.000'), stock(2, '4.000')])
    const task = command.fields.find(field => field.key === 'task')!
    expect(task.optional).toBe(true)
    expect(task.optionsFor!({ project: 7 })).toEqual([{ value: 41, label: '现场换件' }])
    const data = defaults(command.fields, command.initial)
    Object.assign(data, { project: 7, task: 41, reason: '售后换件', confirm_shared: true })
    data.lines[0].quantity = '2'
    data.lines[1].quantity = '4'
    data.lines[1].remark = '夹爪'
    expect(fieldIssues(command.fields, data)).toEqual([])
    expect(command.prepare!(payload(command.fields, data))).toEqual({
      project: 7, task: 41, reason: '售后换件', confirm_shared: true,
      lines: [{ stock: 1, quantity: '2' }, { stock: 2, quantity: '4', remark: '夹爪' }],
    })
    data.task = ''
    data.reason = ''
    expect(command.prepare!(payload(command.fields, data))).not.toHaveProperty('task')
    data.lines[1].quantity = '4.001'
    expect(() => command.prepare!(payload(command.fields, data))).toThrow('第 2 行 物料2（二号仓）：本次领料 4.001 超过本库位可用 4.000。')
  })

  it('没有勾选或勾选的行都已无库存时不允许提交', async () => {
    expect((await stockIssueCommand([])).blocked).toContain('勾选')
    mockStocks([stock(1, '0.000')])
    const command = await stockIssueCommand([stock(1, '2.000')])
    expect(command.blocked).toContain('都没有可用库存')
    expect(command.fields).toEqual([])
  })
})

it('领料单列表链到打印页；库存流水的关联单据按类型链到采购单或领料单', () => {
  const code = columns['issue-slips']!.find(column => column.key === 'code')!
  expect(code.link!({ id: 9 })).toEqual({ path: '/inventory/issue-slips/9' })
  expect(actionNames('issue-slips', { id: 9 })).toEqual(['查看 / 打印'])
  const related = columns.moves!.find(column => column.key === 'purchase_code')!
  expect(related.label).toBe('关联单据')
  user.value = { id: 2, roles: ['purchaser'] }
  expect(related.format!({ purchase_code: 'PO1', purchase: 3, project: 4 })).toBe('PO1')
  expect(related.link!({ purchase_code: 'PO1', purchase: 3, project: 4 })).toMatchObject({ path: '/purchases' })
  expect(related.format!({ slip_code: 'LL000003', slip: 3 })).toBe('LL000003')
  expect(related.link!({ slip_code: 'LL000003', slip: 3 })).toEqual({ path: '/inventory/issue-slips/3' })
  expect(related.format!({ kind: 'count' })).toBe('—')
})
