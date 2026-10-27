import { beforeEach, expect, it, vi } from 'vitest'
import { read, all } from '../api'
import { user } from '../session'
import { actionNames, actionCommand, receiptStatus } from './purchases'

vi.mock('../api', () => ({ read: vi.fn(), all: vi.fn() }))
const pending = { id: 25, reason: '数量应为3', requested_by: '采购张三', requested_by_id: 2, requested_at: '2026-10-27T08:00:00Z' }
const submitted = { id: 9, code: 'PO000009', status: 'submitted', can_approve: true, lines: [] }
beforeEach(() => { vi.resetAllMocks(); user.value = { id: 2, roles: ['purchaser'] } })

it('待审批采购可申请修改，不能直接作废或编辑；批准后沿用原更正动作', () => {
  const actions = actionNames('purchases', submitted)
  expect(actions).toContain('申请修改')
  expect(actions).not.toContain('作废采购')
  expect(actions).not.toContain('修改采购')
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
    { operation: 'purchase.request_change', lines: [] },
    { operation: 'purchase.review_change', decision: 'approve', lines: [] },
    { operation: 'purchase.review_change', decision: 'reject', lines: [] },
  ])
  const command = await actionCommand('purchases', submitted, '处理记录')
  expect(command.initial?.lines.map((l: { operation: string }) => l.operation)).toEqual(['申请修改', '同意修改申请', '驳回修改申请'])
})
