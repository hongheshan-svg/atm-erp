import { beforeEach, expect, it, vi } from 'vitest'
import { all, read } from '../api'
import { defaults, fieldIssues, payload } from '../forms'
import { industryCommand } from '../industry-forms'
import { user } from '../session'
import { actionCommand as purchaseAction, actionNames as purchaseActions, createCommand as purchaseCreate, receiptLines } from './purchases'
import { actionCommand as projectAction } from './projects'
import { bomCommand } from './bom'
import { salesActions, salesColumns, salesCommand } from './sales'
import type { Row } from '../types'

vi.mock('../api', () => ({ all: vi.fn(), read: vi.fn(), write: vi.fn(), download: vi.fn() }))
beforeEach(() => {
  vi.resetAllMocks()
  user.value = { id: 1, roles: ['admin'] }
  vi.mocked(all).mockResolvedValue([])
})
const detail = { id: 9, updated_at: 't', due_date: '2026-11-01', payment_term: 'manual', payment_days: 0, lines: [
  { id: 1, item_name: '电机', quantity: '5.000', received_quantity: '1.000', cancelled_quantity: '1.000', pending_quantity: '0.000', unit_price: '10' },
  { id: 2, item_name: '气缸', quantity: '3.000', received_quantity: '0.000', cancelled_quantity: '0.000', pending_quantity: '2.000', unit_price: '20' },
  { id: 3, item_name: '导轨', quantity: '8.000', received_quantity: '0.000', cancelled_quantity: '0.000', pending_quantity: '0.000', unit_price: '30' },
] }

it('按明细取消默认全部为零，仅提交本次取消数量，隔离行不会被误选', async () => {
  vi.mocked(read).mockResolvedValue(detail)
  const command = industryCommand(await purchaseAction('purchases', { id: 9, status: 'partial' }, '取消未收余量'))
  const data = defaults(command.fields, command.initial)
  expect(data.lines.map((row: Row) => row.line)).toEqual([1, 3])
  expect(data.lines.map((row: Row) => row.quantity)).toEqual(['0', '0'])
  expect(data.lines[0].remaining).toBe('3.000')
  expect(() => command.prepare?.(payload(command.fields, data))).toThrow('请至少填写一条本次取消数量')
  data.reason = '该行缺货'; data.lines[1].quantity = '2.500'
  expect(fieldIssues(command.fields, data)).toEqual([])
  expect(command.prepare?.(payload(command.fields, data))).toEqual({ reason: '该行缺货', lines: [{ line: 3, quantity: '2.500' }] })
})

it('没有可取消明细时解释隔离处理并阻止空请求', async () => {
  vi.mocked(read).mockResolvedValue({ ...detail, lines: [detail.lines[1]] })
  const command = await purchaseAction('purchases', { id: 9, status: 'partial' }, '取消未收余量')
  expect(command.blocked).toContain('没有可取消')
})

it('采购新增、修改与BOM零数量准确指向明细，最小正数可以保存', async () => {
  vi.mocked(read).mockResolvedValue(detail)
  const commands = [await purchaseCreate('purchases'), await purchaseAction('purchases', { id: 9 }, '修改采购')]
  vi.mocked(read).mockResolvedValue({ revision: 'revision', lines: [] })
  commands.push(await bomCommand(1))
  for (const original of commands) {
    const command = industryCommand(original)
    const data = defaults(command.fields, command.initial)
    data.lines = [{ item: 1, quantity: '1', unit_price: '1', due_date: '2026-11-01' }, { item: 2, quantity: '0', unit_price: '1', due_date: '2026-11-01' }]
    const issues = fieldIssues(command.fields, data)
    expect(issues.find(issue => issue.path === 'lines.1.quantity')?.message).toContain('第 2 行')
    data.lines[1].quantity = '0.001'
    expect(fieldIssues(command.fields, data).some(issue => issue.path === 'lines.1.quantity')).toBe(false)
  }
})

it('收货未到行与盘点仍允许0，非法负数不会被prepare静默过滤', async () => {
  vi.mocked(read).mockImplementation(async path => path.includes('locations') ? ['主仓'] : detail)
  const command = industryCommand(await purchaseAction('purchases', { id: 9 }, '收货'))
  const data = defaults(command.fields, command.initial)
  data.lines.forEach((row: Row) => { row.quantity = '0'; row.pending_quantity = '0' })
  expect(fieldIssues(command.fields, data).filter(issue => issue.path.includes('quantity'))).toEqual([])
  const count = industryCommand({ title: '盘点', path: '/business/stocks/1/count/', fields: [{ key: 'quantity', label: '实盘数量' }] })
  expect(fieldIssues(count.fields, { quantity: '0' })).toEqual([])
  const lines = [{ line: 1, quantity: '-1' }, { line: 2, quantity: '2' }]
  expect(receiptLines({ lines }).lines).toEqual(lines)
})

it('收费售后独立填写客户付款期限，免费时不校验也不发送', async () => {
  vi.mocked(all).mockImplementation(async path => path.includes('deliveries') ? [{ id: 5, accepted_date: '2026-09-01' }] : [{ id: 1, roles: ['admin'] }])
  const command = industryCommand(await projectAction('projects', { id: 9, manager: 1, members: [], can_manage: true }, '登记售后'))
  expect(command.fields.find(field => field.key === 'due_date')?.label).toBe('维修截止日期')
  const data = defaults(command.fields)
  data.fee = '300'; data.due_date = '2026-10-25'
  expect(fieldIssues(command.fields, data).some(issue => issue.path === 'fee_due_date')).toBe(true)
  data.fee_due_date = '2026-11-25'
  expect(payload(command.fields, data)).toMatchObject({ due_date: '2026-10-25', fee_due_date: '2026-11-25' })
  data.fee = '0'
  expect(fieldIssues(command.fields, data).some(issue => issue.path === 'fee_due_date')).toBe(false)
  expect(payload(command.fields, data)).not.toHaveProperty('fee_due_date')
})

it('管理员、项目经理、财务与本人销售均有已签约交付回款入口', () => {
  for (const role of ['admin', 'manager', 'finance', 'sales_manager']) {
    user.value = { id: 1, roles: [role] }
    expect(salesActions({ id: 9, manager: 1, status: 'signed' })).toContain('交付与回款')
    expect(salesActions({ id: 9, manager: 1, status: 'draft' })).not.toContain('交付与回款')
  }
})

it('提前到期节点可以提交且动态提醒不进入请求，补充协议同样提醒', async () => {
  vi.mocked(read).mockResolvedValue({ id: 9, contract_date: '2026-10-20', contract_amount: '100', equipment_quantity: 1, warranty_months: 12, updated_at: 't' })
  for (const action of ['签约', '签订补充协议']) {
    const command = await salesCommand({ id: 9, project: 3, quote_amount: '100' }, action)
    const data = defaults(command.fields, command.initial)
    data.date = '2026-10-22'; data.milestones = [{ title: '预付款', amount: '100', due_date: '2026-10-19' }]
    const reminder = command.fields.find(field => field.key === 'early_due_notice')!
    expect(reminder.visibleWhen?.(data)).toBe(true)
    expect(reminder.initial).toContain('允许按合同约定保存')
    expect(payload(command.fields, data)).not.toHaveProperty('early_due_notice')
    expect(payload(command.fields, data).milestones[0].due_date).toBe('2026-10-19')
    data.milestones[0].due_date = '2026-11-01'
    expect(reminder.visibleWhen?.(data)).toBe(false)
  }
})

it('早于采购创建日显示必填补录原因，正常收货不提交隐藏原因', async () => {
  vi.mocked(read).mockImplementation(async path => path.includes('locations') ? ['主仓'] : { ...detail, created_at: '2026-10-22T04:00:00+08:00' })
  const command = industryCommand(await purchaseAction('purchases', { id: 9 }, '收货'))
  const data = defaults(command.fields, command.initial)
  data.received_date = '2026-10-20'
  expect(fieldIssues(command.fields, data).some(issue => issue.path === 'backfill_reason')).toBe(true)
  data.backfill_reason = '补录纸质送货单'
  expect(payload(command.fields, data).backfill_reason).toBe('补录纸质送货单')
  data.received_date = '2026-10-23'
  expect(fieldIssues(command.fields, data).some(issue => issue.path === 'backfill_reason')).toBe(false)
  expect(payload(command.fields, data)).not.toHaveProperty('backfill_reason')
})

it('全部隔离突出已到货待检及精确数量，复检后继续显示剩余隔离量', async () => {
  const { receiptStatus } = await import('./purchases')
  expect(receiptStatus({ status: 'partial', lines: [
    { received_quantity: '0.000', pending_quantity: '0.001' },
    { received_quantity: '0.000', pending_quantity: '0.002' },
  ] })).toBe('已到货待检 · 隔离 0.003')
  expect(receiptStatus({ status: 'partial', lines: [{ received_quantity: '1.000', pending_quantity: '2.000' }] })).toBe('部分收货 · 隔离 2.000')
  expect(receiptStatus({ status: 'received', lines: [{ received_quantity: '5', pending_quantity: '0' }] })).toBe('已收货')
})

it('整单取消只需一次原因，跨页明细全部交给后端计算，不提交前端数量', async () => {
  vi.mocked(read).mockResolvedValue({ ...detail, code: 'PO0055', status: 'partial', lines: Array.from({ length: 55 }, (_, i) => ({ ...detail.lines[0], id: i + 1 })) })
  const command = industryCommand(await purchaseAction('purchases', { id: 9 }, '整单取消未收余量'))
  expect(command.subject).toBe('PO0055')
  expect(command.notice?.text).toContain('55 条明细')
  expect(command.fields.map(field => field.key)).toEqual(['reason'])
  expect(command.blocked).toBeUndefined()
  const data = defaults(command.fields)
  expect(fieldIssues(command.fields, data).some(issue => issue.path === 'reason')).toBe(true)
  data.reason = '供应商停止供货'
  expect(command.prepare?.(payload(command.fields, data))).toEqual({ reason: '供应商停止供货' })
  expect(command.submitLabel).toBe('确认整单取消未收余量')
})

it('整单取消有待检、无余量或订单已结束时明确阻止，不静默跳过明细', async () => {
  for (const [data, expected] of [
    [{ ...detail, status: 'partial' }, '待检'],
    [{ ...detail, status: 'partial', lines: [] }, '没有可取消'],
    [{ ...detail, status: 'cancelled', lines: [] }, '状态已变化'],
  ] as const) {
    vi.mocked(read).mockResolvedValue(data)
    expect((await purchaseAction('purchases', { id: 9 }, '整单取消未收余量')).blocked).toContain(expected)
  }
})

it('整单与明细取消可以相互切换，仍保留明细默认0的保护', async () => {
  vi.mocked(read).mockResolvedValue({ ...detail, status: 'partial', lines: [detail.lines[0], detail.lines[2]] })
  const partial = await purchaseAction('purchases', { id: 9 }, '取消未收余量')
  const whole = await partial.alternatives![0]!.open()
  expect(whole.title).toBe('整单取消未收余量')
  const again = await whole.alternatives![0]!.open()
  expect(again.title).toBe('取消未收余量')
  expect(again.initial!.lines.map((line: Row) => line.quantity)).toEqual(['0', '0'])
})

it('整单取消入口只给采购权限且仅已批准或部分收货状态', () => {
  for (const roles of [['purchaser'], ['member', 'purchaser'], ['admin']]) {
    user.value = { id: 1, roles }
    for (const status of ['approved', 'partial']) expect(purchaseActions('purchases', { status })).toContain('整单取消未收余量')
    for (const status of ['draft', 'submitted', 'received', 'cancelled']) expect(purchaseActions('purchases', { status })).not.toContain('整单取消未收余量')
  }
  for (const role of ['warehouse', 'member', 'finance']) {
    user.value = { id: 1, roles: [role] }
    expect(purchaseActions('purchases', { status: 'approved' })).not.toContain('整单取消未收余量')
  }
})

it('非参与项目的已签约销售显示“无权查看”，不出现空金额或失效的协议附件下载', async () => {
  const contract = salesColumns.find(column => column.key === 'contract_amount')!
  expect(contract.format?.({ id: 9, amounts_visible: false })).toBe('无权查看')
  expect(contract.format?.({ id: 9, amounts_visible: true, contract_amount: '20000.00' })).toBe('20,000.00')
  expect(contract.format?.({ id: 9, amounts_visible: true, contract_amount: null })).toBe('—')
  user.value = { id: 1, roles: ['manager'] }
  const hidden = { id: 9, manager: 2, project: 3, status: 'signed', amounts_visible: false }
  expect(salesActions(hidden)).toEqual(expect.arrayContaining(['查看明细', '交付与回款', '补充协议记录']))
  expect(salesActions(hidden)).not.toContain('签订补充协议')
  expect(salesActions({ ...hidden, amounts_visible: true })).toContain('签订补充协议')

  const view = await salesCommand(hidden, '查看明细')
  expect([view.initial?.quote_amount, view.initial?.contract_amount, view.initial?.original_contract_amount]).toEqual(['无权查看', '无权查看', '无权查看'])

  vi.mocked(read).mockResolvedValueOnce({ project_status: 'active', progress_project: null, deliveries: [], receivables: [], amounts_visible: false })
  const progress = await salesCommand(hidden, '交付与回款')
  expect(progress.fields.map(field => field.key)).toEqual(['project_status', 'deliveries', 'receivables_hidden'])
  expect(progress.initial?.receivables_hidden).toContain('无权查看')

  vi.mocked(read).mockResolvedValueOnce({ project_status: 'active', progress_project: 3, deliveries: [], amounts_visible: true, receivables: [{ title: '合同款', amount: '100.00', credit_amount: '0.00', paid: '0.00', balance: '100.00', due_date: '2026-10-20' }] })
  const visible = await salesCommand({ ...hidden, amounts_visible: true }, '交付与回款')
  expect(visible.fields.map(field => field.key)).toContain('receivables')
  expect(visible.initial).not.toHaveProperty('receivables_hidden')

  vi.mocked(read).mockResolvedValueOnce([{ id: 1, date: '2026-10-20', reason: '增加调试', before: { equipment_quantity: 1, warranty_months: 12 }, after: { equipment_quantity: 2, warranty_months: 12 }, document: null, document__original_name: null }])
  const history = await salesCommand(hidden, '补充协议记录')
  expect(history.actions).toEqual([])
  expect(history.notice?.text).toContain('补充协议金额')
  expect(history.initial?.lines[0]).toMatchObject({ before_text: '设备数量：1；质保月数：12', after_text: '设备数量：2；质保月数：12', document__original_name: '无权查看' })
})

it('已签约销售单仅管理员与项目经理可见转交负责人，表单只含新负责人与原因', async () => {
  const row = { id: 9, manager: 3, status: 'signed' }
  for (const role of ['admin', 'manager']) {
    user.value = { id: 1, roles: [role] }
    expect(salesActions(row)).toContain('转交负责人')
  }
  for (const role of ['finance', 'sales_manager']) {
    user.value = { id: 3, roles: [role] }
    expect(salesActions(row)).not.toContain('转交负责人')
  }
  user.value = { id: 1, roles: ['manager'] }
  expect(salesActions({ id: 9, manager: 3, status: 'quoted' })).not.toContain('转交负责人')
  vi.mocked(all).mockResolvedValue([
    { id: 3, username: 'old', display_name: '原负责人', roles: ['sales_manager'] },
    { id: 4, username: 'new', display_name: '新负责人', roles: ['sales_manager'] },
    { id: 5, username: 'pm', display_name: '经理', roles: ['manager'] },
  ])
  const command = await salesCommand(row, '转交负责人')
  expect(command.path).toBe('/business/sales/9/transfer/')
  expect(command.fields.map(field => field.key)).toEqual(['manager', 'reason'])
  expect(command.fields[0].options).toEqual([{ value: 4, label: '新负责人（new）' }])
  expect(command.notice?.text).toContain('只更换销售负责人，不改变合同与回款')
})
