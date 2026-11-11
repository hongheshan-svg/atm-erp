import { beforeEach, expect, it, vi } from 'vitest'
import { all, read } from '../api'
import { defaults, fieldIssues, payload } from '../forms'
import { user } from '../session'
import { actionCommand as purchaseAction, columns as purchaseColumns, purchaseFields } from './purchases'
import { bomIssueCommand, actionCommand as inventoryAction, columns as inventoryColumns, createCommand as inventoryCreate } from './inventory'
import { actionCommand as financeAction, actionNames as financeActions, columns as financeColumns } from './finance'

vi.mock('../api', () => ({ all: vi.fn(), read: vi.fn(), download: vi.fn() }))
beforeEach(() => {
  vi.resetAllMocks()
  user.value = { id: 3, roles: ['admin'] }
  vi.mocked(all).mockResolvedValue([])
})

const purchase = {
  id: 8, code: 'PO-8', status: 'submitted', can_approve: true, project: 4, project_code: 'ATM2680', project_name: '上料线',
  supplier_name: '精工机械', due_date: '2026-12-01', payment_term: 'month30',
  lines: [
    { id: 81, item_code: 'M-1', item_name: '伺服电机', specification: '400W', unit: '台', quantity: '2.000', unit_price: '1000.00', bom_line: 5 },
    { id: 82, item_code: 'M-2', item_name: '备用气缸', quantity: '1.000', unit_price: '95.50', bom_line: null },
  ],
}

it('超出 BOM 缺口的手工采购可填写原因，留空不提交', () => {
  const fields = purchaseFields()
  const field = fields.find(f => f.key === 'over_bom_reason')!
  expect(field.optional).toBe(true)
  expect(field.hint).toContain('从 BOM 多选下单')
  expect(payload(fields, defaults(fields))).not.toHaveProperty('over_bom_reason')
})

it('批准采购在对话框内列出供应商、合计和逐行明细，并标出超 BOM 行与申请原因', async () => {
  vi.mocked(read).mockResolvedValue({
    over_budget: false, configured: true, purchase_amount: '2095.50', occupied_total: '2095.50', purchase_net: '2095.50',
    bom_warnings: ['本单含 1 行超出 BOM 需求：备用气缸 +1.000'], bom_lines: { 82: '超出 BOM 缺口 1.000' }, over_bom_reason: '损耗补买',
  })
  const command = await purchaseAction('purchases', purchase, '批准采购')
  expect(read).toHaveBeenCalledExactlyOnceWith('/business/purchases/8/budget-check/')
  expect(command.notice).toMatchObject({ type: 'warning' })
  expect(command.notice?.text).toContain('本单含 1 行超出 BOM 需求')
  expect(command.initial).toMatchObject({ supplier_name: '精工机械', project_label: 'ATM2680 · 上料线', total_label: '2,095.50', over_bom_reason: '损耗补买' })
  expect(command.initial?.schedule_label).toBe('2026-12-01 · 月结30天')
  expect(command.initial?.approval_lines).toBe([
    '1. M-1 · 伺服电机 · 400W｜2.000 台 × 1,000.00 = 2,000.00｜按 BOM 下单',
    '2. M-2 · 备用气缸｜1.000 × 95.50 = 95.50｜超出 BOM 缺口 1.000',
  ].join('\n'))
  expect(command.fields.find(f => f.key === 'approval_lines')).toMatchObject({ label: '采购明细（2 行）', type: 'textarea', readonly: true, displayOnly: true })
  // 摘要只读，不进入审批请求；审批意见选填。
  const data = defaults(command.fields, command.initial)
  expect(fieldIssues(command.fields, data)).toEqual([])
  expect(command.prepare!(payload(command.fields, data))).toEqual({})
  const rejected = await purchaseAction('purchases', purchase, '退回修改')
  expect(rejected.initial?.approval_lines.split('\n')).toHaveLength(2)
  expect(payload(rejected.fields, { ...defaults(rejected.fields, rejected.initial), reason: '单价偏高' })).toEqual({ reason: '单价偏高' })
})

it('提交采购确认框显示金额、行数和审批人；采购列表显示含税合计并链接项目', async () => {
  const command = await purchaseAction('purchases', { ...purchase, status: 'draft' }, '提交采购')
  expect(command.notice?.text).toContain('2 行明细 · 含税合计 2,095.50 元')
  expect(command.notice?.text).toContain('审批')
  const total = purchaseColumns.purchases!.find(c => c.key === 'total')!
  expect(total.format!(purchase)).toBe('2,095.50')
  expect(total.format!({ lines: [{ quantity: '1' }] })).toBe('—')
  expect(purchaseColumns.purchases!.find(c => c.key === 'project_name')!.link!(purchase)).toBe('/projects/4')
})

it('收货说明选填，改名为送货单号 / 备注；纠错动作仍必填原因', async () => {
  vi.mocked(read).mockImplementation(async path => path.includes('locations') ? ['主仓'] : { ...purchase, status: 'approved', created_at: '2026-10-01T08:00:00', lines: [{ ...purchase.lines[0], received_quantity: '0', cancelled_quantity: '0', pending_quantity: '0' }] })
  const receive = await purchaseAction('purchases', { ...purchase, status: 'approved' }, '收货')
  const note = receive.fields.find(f => f.key === 'reason')!
  expect(note).toMatchObject({ label: '送货单号 / 备注', optional: true })
  const reject = await purchaseAction('purchases', { ...purchase, status: 'approved' }, '隔离品退回供应商')
  expect(reject.fields.find(f => f.key === 'reason')?.optional).toBeFalsy()
  const issueReturn = await inventoryAction('moves', { id: 2, kind: 'issue' }, '退料')
  expect(issueReturn.fields.find(f => f.key === 'reason')?.optional).toBeFalsy()
  const opening = await inventoryCreate('stocks')
  expect(opening.fields.find(f => f.key === 'reason')?.optional).toBe(true)
})

it('按 BOM 领料：未选项目先提示，选项目后按服务端候选预填，只提交本次领用的行', async () => {
  user.value = { id: 3, roles: ['warehouse'] }
  expect((await bomIssueCommand()).blocked).toContain('选择项目')
  vi.mocked(read).mockResolvedValue({
    project: 6, project_code: 'ATM2690', project_name: '下料线', pending_items: 3, missing_items: 1,
    lines: [
      { stock: 11, item: 1, item_code: 'M-1', item_name: '伺服电机', location: '主仓', unit: '台', assembly_units: '上料单元', required_quantity: '4.000', issued_quantity: '1.000', bom_remaining: '3.000', available: '2.000', quantity: '2.000' },
      { stock: 12, item: 1, item_code: 'M-1', item_name: '伺服电机', location: '二号仓', unit: '台', assembly_units: '上料单元', required_quantity: '4.000', issued_quantity: '1.000', bom_remaining: '3.000', available: '5.000', quantity: '1.000' },
    ],
  })
  const command = await bomIssueCommand(6)
  expect(read).toHaveBeenCalledWith('/business/stocks/bom-issue/', { project: 6 })
  expect(command.path).toBe('/business/stocks/bom-issue/')
  expect(command.notice?.text).toContain('1 种当前无库存')
  const data = defaults(command.fields, command.initial)
  data.lines[1].quantity = '0'
  data.lines[0].remark = '一号工位'
  expect(fieldIssues(command.fields, data)).toEqual([])
  expect(command.prepare!(payload(command.fields, data))).toEqual({ project: 6, confirm_shared: false, lines: [{ stock: 11, quantity: '2.000', remark: '一号工位' }] })
  data.lines[0].quantity = '0'
  expect(() => command.prepare!(payload(command.fields, data))).toThrow('至少填写一行')
  vi.mocked(read).mockResolvedValue({ project: 6, project_code: 'ATM2690', pending_items: 0, missing_items: 0, lines: [] })
  expect((await bomIssueCommand(6)).blocked).toContain('已全部领完')
})

it('库存流水显示项目与来源采购单并可跳转', () => {
  const move = { id: 1, project: 4, project_code: 'ATM2680', project_name: '上料线', purchase: 8, purchase_code: 'PO-8', item_code: 'M-1', item_name: '伺服电机', quantity: '-2.000', unit: '台', created_at: '2026-11-11T09:30:00+08:00' }
  const col = (key: string) => inventoryColumns.moves!.find(c => c.key === key)!
  expect(col('project_name').format!(move)).toBe('ATM2680 · 上料线')
  expect(col('project_name').link!(move)).toBe('/projects/4')
  expect(col('purchase_code').link!(move)).toEqual({ path: '/purchases', query: { resource: 'purchases', focus: '8', project: '4' } })
  expect(col('item_name').format!(move)).toBe('M-1 · 伺服电机')
  expect(col('quantity').format!(move)).toBe('-2.000 台')
  expect(col('created_at').format!(move)).toBe('2026-11-11 09:30')
  expect(col('project_name').link!({ ...move, project: null })).toBeUndefined()
})

it('收付款流水按方向显示收 / 付，对账单显示编号；登记收款对话框标题与按钮一致', async () => {
  user.value = { id: 3, roles: ['finance'] }
  const amount = financeColumns.payments!.find(c => c.key === 'amount')!
  expect(amount.format!({ amount: '100.00', cash_amount: '100.00' })).toBe('收 100.00')
  expect(amount.format!({ amount: '1200.00', cash_amount: '-1200.00' })).toBe('付 1,200.00')
  const statement = financeColumns.payments!.find(c => c.key === 'reconciliation_code')!
  expect(statement.format!({ reconciliation: 13, reconciliation_code: 'DZ000013' })).toBe('DZ000013')
  expect(statement.link!({ reconciliation: 13 })).toMatchObject({ path: '/finance', query: { focus: '13' } })
  const entry = { id: 7, project: 3, kind: 'receivable', title: '预付款', partner_name: '宁德客户', project_name: '上料线', amount: '150000.00', balance: '150000.00', due_date: '2026-11-05', status: 'overdue' }
  const pay = await financeAction('entries', entry, '登记收付款')
  expect(pay).toMatchObject({ title: '登记收款', submitLabel: '登记收款记录' })
  expect(pay.notice).toMatchObject({ type: 'warning' })
  expect(pay.notice?.text).toBe('宁德客户 · 上料线 · 原金额 150,000.00 · 待收 150,000.00 · 到期 2026-11-05（已逾期）')
  expect(pay.fields.find(f => f.key === 'reason')?.optional).toBe(true)
})

it('财务可调整未结应收的到期日，带当前到期日防并发并要求原因', async () => {
  user.value = { id: 3, roles: ['finance'] }
  const entry = { id: 7, kind: 'receivable', title: '发货款', balance: '100.00', due_date: '2027-02-28', cancelled: false }
  expect(financeActions('entries', entry)).toContain('调整到期日')
  expect(financeActions('entries', { ...entry, kind: 'payable' })).not.toContain('调整到期日')
  expect(financeActions('entries', { ...entry, balance: '0.00' })).not.toContain('调整到期日')
  user.value = { id: 4, roles: ['manager'] }
  expect(financeActions('entries', entry)).not.toContain('调整到期日')
  const command = await financeAction('entries', entry, '调整到期日')
  expect(command.path).toBe('/business/entries/7/adjust-due-date/')
  const data = defaults(command.fields, command.initial)
  expect(fieldIssues(command.fields, data).map(issue => issue.path)).toEqual(['reason'])
  expect(command.prepare!(payload(command.fields, { ...data, due_date: '2026-12-11', reason: '发货后 30 天' }))).toEqual({ due_date: '2026-12-11', reason: '发货后 30 天', expected_due_date: '2027-02-28' })
})
