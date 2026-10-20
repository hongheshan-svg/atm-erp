import { beforeEach, expect, it, vi } from 'vitest'
import { all } from '../api'
import { user } from '../session'
import { actionCommand as paymentCommand } from './finance'
import { actionNames, createLabel, reconciliationCommand } from './settlement'
import { draftKey, loadDraft, saveDraft } from '../form-experience'
import { purchaseFields } from './purchases'
import { defaults, payload } from '../forms'

vi.mock('../api', () => ({ all: vi.fn(), read: vi.fn(), download: vi.fn() }))
beforeEach(() => { vi.resetAllMocks(); user.value = { id: 1, role: 'finance' }; vi.mocked(all).mockResolvedValue([]) })

it('采购默认继承供应商账期，不偷偷提交当天作为指定付款日', () => {
  const fields = purchaseFields()
  const data = payload(fields, defaults(fields))
  expect(data).not.toHaveProperty('payment_due_date')
  expect(data).not.toHaveProperty('payment_term')
  const supplier = fields.find(f => f.key === 'supplier')!
  expect(supplier.remotePath).toBe('/business/partners/')
  expect(supplier.remoteLabel?.({ id: 1, kind: 'supplier', name: '供应商', code: 'S1', payment_term: 'month30' })).toContain('月结30天')
  expect(fields.find(f => f.key === 'project')?.remotePath).toBe('/business/projects/')
})

it('预付款由经理核准，普通对账由财务确认，银行入口仅财务管理', () => {
  const row = { id: 1, status: 'draft', valid: true, kind: 'prepayment' }
  expect(actionNames('reconciliations', row)).not.toContain('确认对账')
  expect(actionNames('reconciliations', { ...row, kind: 'settlement' })).toContain('确认对账')
  user.value = { id: 2, role: 'manager' }
  expect(actionNames('reconciliations', row)).toContain('确认对账')
  expect(actionNames('reconciliations', { ...row, kind: 'settlement' })).not.toContain('确认对账')
  expect(createLabel('bank-records')).toBe('')
})

it('采购付款和退款必选有效对账，客户收款可不选', async () => {
  vi.mocked(all).mockImplementation(async path => path.includes('reconciliations') ? [
    { id: 1, code: 'DZ1', kind: 'settlement', valid: true, remaining_amount: '20' },
    { id: 2, code: 'DZ2', kind: 'settlement', valid: false, remaining_amount: '20' },
    { id: 3, code: 'DZ3', kind: 'settlement', valid: true, remaining_amount: '0' },
  ] : [])
  const purchase = await paymentCommand('entries', { id: 5, project: 1, purchase: 2, balance: '20' }, '登记收付款')
  const field = purchase.fields.find(f => f.key === 'reconciliation')!
  expect(field.optional).toBe(false)
  expect(field.options?.map(o => o.value)).toEqual([1])
  expect(purchase.initial?.reconciliation).toBe(1)
  const receipt = await paymentCommand('entries', { id: 6, project: 1, balance: '20' }, '登记收付款')
  expect(receipt.fields.find(f => f.key === 'reconciliation')?.optional).toBe(true)
  const refund = await paymentCommand('entries', { id: 6, project: 1, balance: '-20' }, '退款')
  expect(refund.fields).toEqual([])
  expect(refund.blocked).toContain('尚无可用的已确认退款对账单')
  expect(refund.alternatives?.map(a => a.label)).toEqual(['生成对账单'])
  const next = await refund.alternatives![0]!.open()
  expect(next.prepare?.({}).kind).toBe('refund')
})

it('已核对或支出银行记录不提供认领到账操作', () => {
  const row = { amount: '500', remaining_amount: '0', matches: [], returns: [] }
  expect(actionNames('bank-records', row)).not.toContain('认领到账')
  expect(actionNames('bank-records', { ...row, amount: '-500', remaining_amount: '500' })).not.toContain('认领到账')
  expect(actionNames('bank-records', { ...row, remaining_amount: '100' })).toContain('关联未认领款退回')
})

it('缺失户名必须核实后才能认领、匹配或关联退回', () => {
  const row = { amount: '500', remaining_amount: '500', needs_review: true, matches: [], returns: [] }
  const names = actionNames('bank-records', row)
  expect(names).toContain('核实对方户名')
  for (const action of ['认领到账', '匹配已有收付款', '关联未认领款退回']) expect(names).not.toContain(action)
  expect(actionNames('bank-records', { ...row, needs_review: false })).toContain('认领到账')
})

it('采购付款缺少核准时先给可执行的处理入口，客户到账保持可直接登记', async () => {
  const blocked = await paymentCommand('entries', { id: 5, project: 3, purchase: 2, balance: '80' }, '登记收付款')
  expect(blocked.blocked).toContain('未收货预付款')
  expect(blocked.fields).toEqual([])
  expect(blocked.links?.[0]?.path).toContain('/projects/3?tab=finance')
  const next = await blocked.alternatives![1]!.open()
  expect(next.prepare?.({}).entry).toBe(5)
  expect(next.prepare?.({}).kind).toBe('prepayment')
  expect(next.fields.find(f => f.key === 'document')?.upload).toEqual({ context: { project: 3 }, category: 'receipt' })
  const receipt = await paymentCommand('entries', { id: 6, project: 3, balance: '80' }, '登记收付款')
  expect(receipt.blocked).toBeUndefined()
  expect(receipt.fields.find(f => f.key === 'document')?.upload?.context).toEqual({ project: 3 })
})

it('余额和名称相同的两笔款项，对账草稿仍按款项身份隔离', async () => {
  const first = await reconciliationCommand({ id: 7, project: 3, title: '采购款', balance: '80' })
  const second = await reconciliationCommand({ id: 9, project: 3, title: '采购款', balance: '80' })
  saveDraft(draftKey(first, 1), first, { reason: '仅适用第一笔款项' })
  expect(loadDraft(draftKey(second, 1), second)).toBeNull()
  expect(loadDraft(draftKey(first, 1), first)?.reason).toBe('仅适用第一笔款项')
})
