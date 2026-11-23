import { beforeEach, expect, it, vi } from 'vitest'
import { read, all } from '../api'
import { user } from '../session'
import { actionNames, actionCommand, receiptStatus } from './purchases'

vi.mock('../api', () => ({ read: vi.fn(), all: vi.fn() }))
const pending = { id: 25, reason: '数量应为3', requested_by: '采购张三', requested_by_id: 2, requested_at: '2026-10-27T08:00:00Z' }
const submitted = { id: 9, code: 'PO000009', status: 'submitted', can_approve: true, lines: [] }
beforeEach(() => { vi.resetAllMocks(); user.value = { id: 2, roles: ['purchaser'] } })

it('待审批采购可申请修改或直接作废，不能直接编辑；批准后沿用原更正动作', async () => {
  const actions = actionNames('purchases', submitted)
  expect(actions).toContain('申请修改')
  expect(actions).toContain('作废采购')
  expect(actions).not.toContain('修改采购')
  // 有待处理修改申请时服务端拒绝作废，前端不提供入口。
  expect(actionNames('purchases', { ...submitted, change_request: pending })).not.toContain('作废采购')
  user.value = { id: 3, roles: ['warehouse'] }
  expect(actionNames('purchases', submitted)).not.toContain('作废采购')
  user.value = { id: 2, roles: ['purchaser'] }
  const voided = await actionCommand('purchases', submitted, '作废采购')
  expect(voided.path).toBe('/business/purchases/9/cancel-remainder/')
  expect(voided.fields.find(f => f.key === 'reason')?.optional).toBeFalsy()
  expect(voided.notice?.text).toContain('审批人无需再处理')
  expect((await actionCommand('purchases', { ...submitted, status: 'draft' }, '作废采购')).notice?.text).not.toContain('审批人')
  expect(actionNames('purchases', { ...submitted, status: 'draft' })).toContain('作废采购')
  expect(actionNames('purchases', { ...submitted, status: 'approved' })).not.toContain('申请修改')
  expect(actionNames('purchases', { ...submitted, status: 'approved' })).toContain('整单取消未收余量')
})

it('待处理申请隐藏批准和退回捷径，按服务端权限显示处理或查看入口', () => {
  const row = { ...submitted, change_request: pending }
  expect(receiptStatus(row)).toBe('修改申请待处理')
  expect(actionNames('purchases', row)).toContain('查看修改申请')
  user.value = { id: 3, roles: ['purchase_manager'] }
  for (const action of ['批准采购', '退回修改', '申请修改']) expect(actionNames('purchases', row)).not.toContain(action)
  expect(actionNames('purchases', { ...row, can_review_change: true })).toContain('处理修改申请')
})

it('申请只提交修改原因，不直接改变数量；状态改变后阻止过时申请', async () => {
  vi.mocked(read).mockResolvedValue(submitted)
  const command = await actionCommand('purchases', submitted, '申请修改')
  expect(command.path).toBe('/business/purchases/9/request-change/')
  expect(command.fields[0]?.optional).not.toBe(true)
  expect(command.prepare?.({ reason: '数量填错', quantity: 3 })).toEqual({ reason: '数量填错' })
  expect(command.notice?.text).toContain('重新提交审批')
  vi.mocked(read).mockResolvedValue({ ...submitted, status: 'approved' })
  expect((await actionCommand('purchases', submitted, '申请修改')).blocked).toContain('仅待审批')
})

it('处理申请展示原原因，提交申请编号防止旧弹窗处理新申请', async () => {
  vi.mocked(read).mockResolvedValue({ ...submitted, can_review_change: true, change_request: pending })
  const command = await actionCommand('purchases', submitted, '处理修改申请')
  expect(command.initial?.request_reason).toBe(pending.reason)
  // 申请时间是 UTC，按业务时区显示。
  expect(command.initial?.requested_at).toBe('2026-10-27 16:00')
  expect(command.fields.find(f => f.key === 'decision')?.options).toHaveLength(2)
  expect(command.prepare?.({ decision: 'reject', reason: '原数量正确', requested_by: '伪造' })).toEqual({ request_id: 25, decision: 'reject', reason: '原数量正确' })
  vi.mocked(read).mockResolvedValue({ ...submitted, change_request: null })
  expect((await actionCommand('purchases', submitted, '处理修改申请')).blocked).toContain('已处理')
})

it('查看申请只读，不提供处理结果选项', async () => {
  vi.mocked(read).mockResolvedValue({ ...submitted, change_request: pending })
  const command = await actionCommand('purchases', submitted, '查看修改申请')
  expect(command.readonly).toBe(true)
  expect(command.fields.some(f => f.key === 'decision')).toBe(false)
})

it('处理记录将申请、同意和驳回全部显示为中文', async () => {
  vi.mocked(all).mockResolvedValue([
    { operation: 'purchase.request_change', date: '2026-10-27T17:30:00Z', lines: [] },
    { operation: 'purchase.review_change', decision: 'approve', lines: [] },
    { operation: 'purchase.review_change', decision: 'reject', lines: [] },
  ])
  const command = await actionCommand('purchases', submitted, '处理记录')
  expect(command.initial?.lines.map((l: { operation: string }) => l.operation)).toEqual(['申请修改', '同意修改申请', '驳回修改申请'])
  expect(command.initial?.lines[0].date).toBe('2026-10-28 01:30')
})

it('反审：审批人对已批准、部分收货、已收货的采购可反审；先列出要冲回的收货和作废应付，拦下时逐条写明办法', async () => {
  const approved = { ...submitted, status: 'partial' }
  expect(actionNames('purchases', approved)).not.toContain('反审')
  user.value = { id: 3, roles: ['purchase_manager'] }
  for (const status of ['approved', 'partial', 'received']) expect(actionNames('purchases', { ...submitted, status })).toContain('反审')
  for (const status of ['draft', 'submitted', 'cancelled']) expect(actionNames('purchases', { ...submitted, status })).not.toContain('反审')
  expect(actionNames('purchases', { ...approved, can_approve: false })).not.toContain('反审')
  vi.mocked(read).mockResolvedValue({
    can_unapprove: true, problems: [], payable: '120.00', contract_versions: 1,
    receipts: [{ id: 7, item_code: 'M-1', item_name: '气缸', unit: '个', quantity: '4', location: '主仓', received_date: '2026-11-20' }],
  })
  const command = await actionCommand('purchases', approved, '反审')
  expect(read).toHaveBeenCalledWith('/business/purchases/9/unapprove-check/')
  expect(command.path).toBe('/business/purchases/9/unapprove/')
  expect(command.blocked).toBeUndefined()
  expect(command.notice?.text).toContain('将冲回 1 次收货：气缸 4 个（主仓，2026-11-20 收货）')
  expect(command.notice?.text).toContain('应付 120.00 元作废')
  expect(command.notice?.text).toContain('重签')
  expect(command.fields[0]?.label).toBe('反审原因')
  expect(command.prepare?.({ reason: '第 2 项单价改为 10.5', extra: 1 })).toEqual({ reason: '第 2 项单价改为 10.5' })
  vi.mocked(read).mockResolvedValue({ can_unapprove: false, problems: ['本单已付款 50.00 元，请财务先冲销', '有到货在隔离待检'], payable: '0.00', contract_versions: 0, receipts: [] })
  const blocked = await actionCommand('purchases', approved, '反审')
  expect(blocked.blocked).toBe('1. 本单已付款 50.00 元，请财务先冲销\n2. 有到货在隔离待检')
})

it('采购列表写出提交人；退回草稿的单子状态写明退回方式，悬停看谁、何时、为什么', async () => {
  const { columns, submitterText } = await import('./purchases')
  expect(submitterText({ submitted_by_name: '李采购', created_by_name: '王助理' })).toBe('提交人 李采购')
  expect(submitterText({ created_by_name: '王助理' })).toBe('创建人 王助理')
  const reasonText = '第 2 项单价应为 10.5，第 3 项数量改 4 件，供应商已确认，请同时把交期改到下月底并补充比价单附件'
  const draft = { status: 'draft', returned_action: '反审', returned_reason: reasonText, returned_note: `张经理（账号：zhang2） 11-20 09:30 反审：${reasonText}` }
  expect(receiptStatus(draft)).toBe('已反审，待修改')
  expect(receiptStatus({ ...draft, returned_action: '退回修改' })).toBe('已退回，待修改')
  expect(receiptStatus({ status: 'draft' })).not.toContain('退回')
  const status = columns.purchases!.find(column => column.key === 'status')!
  // 状态下面先写原因（同名人员带账号时也不会把原因挤掉），谁、何时悬停看。
  expect(status.flag?.(draft)).toEqual({ text: `${reasonText.slice(0, 36)}…`, risk: true, wrap: true })
  expect(status.tip?.(draft)).toBe(draft.returned_note)
  expect(status.flag?.({ ...draft, status: 'submitted' })).toBeUndefined()
})
