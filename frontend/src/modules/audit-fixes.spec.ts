import { beforeEach, expect, it, vi } from 'vitest'
import { read } from '../api'
import { actionCommand, actionNames } from '../business'
import { bomCommand } from './bom'
import { participants } from './shared'
import { actionGroup } from '../row-actions'
import { user } from '../session'

vi.mock('../api', () => ({ all: vi.fn(), read: vi.fn(), write: vi.fn(), download: vi.fn() }))
beforeEach(() => { vi.resetAllMocks(); user.value = { id: 1, roles: ['admin'] } })

it('执行人下拉只留项目成员和跨项目岗位', () => {
  const people = [
    { id: 1, roles: ['manager'] },
    { id: 2, roles: ['member'] },
    { id: 3, roles: ['mechanical_engineer'] },
    { id: 4, roles: ['warehouse'] },
    { id: 5, roles: ['sales_manager'] },
  ]
  const scope = { manager: 1, members: [2] }
  expect(participants(people, scope).map(p => p.id)).toEqual([1, 2, 4])
  // 没有项目上下文时（例如还没选项目）不做裁剪，交给服务端按字段报错。
  expect(participants(people, null).map(p => p.id)).toEqual([1, 2, 3, 4, 5])
})

it('维护 BOM 只提交本次变更，不再把整张 BOM 灌进表单', async () => {
  vi.mocked(read).mockResolvedValue({ revision: 'rev-1', lines: [{ bom_line: 1 }, { bom_line: 2 }] })
  const command = await bomCommand(7)
  expect(command.initial).toBeUndefined()
  expect(command.notice?.text).toContain('本项目现有 2 行')
  expect(command.fields[0]?.fields?.find(f => f.key === 'item')?.remotePath).toBe('/business/items/')
  expect(command.prepare?.({ lines: [{ item: 3, quantity: '2', change_note: '新增' }] })).toEqual({
    expected_revision: 'rev-1',
    lines: [{ item: 3, quantity: '2', change_note: '新增', required_date: null, application_date: null, applicant: '' }],
  })
})

it('BOM 单行修改只提交这一行并带上当前版本', async () => {
  vi.mocked(read).mockResolvedValue({ revision: 'rev-9', lines: [] })
  const row = { id: 5, project: 7, item: 3, item_code: 'M1', item_name: '导轨', quantity: '4.000', assembly_unit: '主机' }
  expect(actionNames('bom', { ...row, can_edit_bom: true })).toEqual(['修改此行', '移除'])
  const command = await actionCommand('bom', row, '修改此行')
  expect(command.path).toBe('/business/projects/7/revise-bom/')
  expect(command.initial?.quantity).toBe('4.000')
  expect(command.prepare?.({ quantity: '6', assembly_unit: '主机', change_note: 'ECN-3', applicant: '' })).toEqual({
    expected_revision: 'rev-9',
    lines: [{ id: 5, item: 3, quantity: '6', assembly_unit: '主机', change_note: 'ECN-3', required_date: null, application_date: null, applicant: '' }],
  })
})

it('附件可由上传者撤回，被引用时由服务端拦截', async () => {
  expect(actionNames('documents', { id: 1, can_remove: false })).toEqual(['下载'])
  expect(actionNames('documents', { id: 1, can_remove: true })).toEqual(['下载', '删除附件'])
  const command = await actionCommand('documents', { id: 1, can_remove: true, original_name: '图纸.pdf' }, '删除附件')
  expect(command.path).toBe('/business/documents/1/remove/')
  expect(command.fields.map(f => f.key)).toEqual(['reason'])
  expect(command.notice?.text).toContain('图纸.pdf')
})

it('取消、作废、撤销、删除归入更正组，不和推进单据混在一起', () => {
  for (const name of ['整单取消未收余量', '取消未收余量', '作废对账', '撤销银行匹配', '删除附件', '冲销付款', '退回修改'])
    expect(actionGroup(name)).toBe('correct')
  for (const name of ['提交采购', '收货', '登记收付款']) expect(actionGroup(name)).toBe('advance')
  for (const name of ['查看明细', '处理记录', '附件']) expect(actionGroup(name)).toBe('reference')
  expect(actionGroup('登记采购质保')).toBe('warranty')
})

it('维护 BOM 单元留空不发送 assembly_unit，填写时原样提交', async () => {
  vi.mocked(read).mockResolvedValue({ revision: 'rev-1', lines: [] })
  const command = await bomCommand(7)
  expect(command.notice?.text).toContain('单元留空')
  const lines = (command.prepare?.({ lines: [{ item: 3, quantity: '2' }, { item: 4, quantity: '1', assembly_unit: '上料' }] }) as { lines: Record<string, unknown>[] }).lines
  expect('assembly_unit' in lines[0]!).toBe(false)
  expect(lines[1]!.assembly_unit).toBe('上料')
})

const purchaseDetail = { id: 9, updated_at: 't', due_date: '2026-11-01', payment_term: 'month30', payment_days: 30, lines: [
  { id: 1, item_name: '电机', quantity: '5.000', received_quantity: '0.000', cancelled_quantity: '0.000', pending_quantity: '0.000' },
  { id: 2, item_name: '气缸', quantity: '3.000', received_quantity: '0.000', cancelled_quantity: '0.000', pending_quantity: '2.000' },
] }

it('收货与隔离品命令提交前过滤两项都为 0 的行，全部为 0 时阻止提交', async () => {
  user.value = { id: 1, roles: ['warehouse'] }
  vi.mocked(read).mockImplementation(async (path: string) => (path.includes('locations') ? ['主仓'] : purchaseDetail))
  const receive = await actionCommand('purchases', { id: 9, status: 'approved' }, '收货')
  const body = { reason: 'r', lines: [{ line: 1, quantity: '5', pending_quantity: '0' }, { line: 2, quantity: '0', pending_quantity: '0' }, { line: 3, quantity: '0', pending_quantity: '1' }] }
  expect((receive.prepare?.(body) as { lines: unknown[] }).lines).toEqual([body.lines[0], body.lines[2]])
  expect(() => receive.prepare?.({ ...body, lines: [{ line: 1, quantity: '0', pending_quantity: '0' }] })).toThrow('请至少填写一条到货数量')
  const accept = await actionCommand('purchases', { id: 9, status: 'partial' }, '隔离品合格入库')
  expect((accept.prepare?.({ lines: [{ line: 1, quantity: '0' }, { line: 2, quantity: '2' }] }) as { lines: unknown[] }).lines).toEqual([{ line: 2, quantity: '2' }])
  expect(() => accept.prepare?.({ lines: [{ line: 1, quantity: '0' }] })).toThrow('请至少填写一条到货数量')
})

it('未批准采购显示作废采购，已批准显示取消未收余量，走同一接口', async () => {
  user.value = { id: 1, roles: ['purchaser'] }
  expect(actionNames('purchases', { status: 'draft' })).toContain('作废采购')
  expect(actionNames('purchases', { status: 'submitted' })).not.toContain('取消未收余量')
  expect(actionNames('purchases', { status: 'approved' })).toContain('取消未收余量')
  expect(actionNames('purchases', { status: 'approved' })).not.toContain('作废采购')
  const voided = await actionCommand('purchases', { id: 9, status: 'draft' }, '作废采购')
  vi.mocked(read).mockResolvedValue(purchaseDetail)
  const cancel = await actionCommand('purchases', { id: 9, status: 'approved' }, '取消未收余量')
  expect(voided.path).toBe('/business/purchases/9/cancel-remainder/')
  expect(cancel.path).toBe(voided.path)
  expect(cancel.notice?.text).toContain('仅取消填写数量的明细')
})

it('修改采购含账期字段，选月结时不提交付款到期日', async () => {
  user.value = { id: 1, roles: ['purchaser'] }
  vi.mocked(read).mockResolvedValue({ ...purchaseDetail, payment_term: 'manual', payment_due_date: '2026-12-01' })
  const command = await actionCommand('purchases', { id: 9, status: 'draft' }, '修改采购')
  expect(command.fields.map(f => f.key)).toEqual(expect.arrayContaining(['payment_term', 'payment_days', 'payment_due_date']))
  const due = command.fields.find(f => f.key === 'payment_due_date')!
  const days = command.fields.find(f => f.key === 'payment_days')!
  expect(due.visibleWhen?.({ payment_term: 'manual' })).toBe(true)
  expect(due.visibleWhen?.({ payment_term: 'month30' })).toBe(false)
  expect(days.visibleWhen?.({ payment_term: 'custom' })).toBe(true)
  expect(days.visibleWhen?.({ payment_term: 'month30' })).toBe(false)
  const lines = [{ id: 1, quantity: '5', unit_price: '1', due_date: 'd' }]
  const month = command.prepare?.({ due_date: 'd', payment_term: 'month30', payment_due_date: '2026-12-01', reason: 'r', lines }) as Record<string, unknown>
  expect(month.payment_term).toBe('month30')
  expect('payment_due_date' in month).toBe(false)
  const custom = command.prepare?.({ due_date: 'd', payment_term: 'custom', payment_days: '45', reason: 'r', lines }) as Record<string, unknown>
  expect(custom.payment_days).toBe('45')
})
