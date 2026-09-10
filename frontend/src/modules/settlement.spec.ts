import { beforeEach, expect, it, vi } from 'vitest'
import { all } from '../api'
import { user } from '../session'
import { actionCommand as paymentCommand } from './finance'
import { actionNames, createLabel } from './settlement'
import { purchaseFields } from './purchases'
import { defaults, payload } from '../forms'

vi.mock('../api', () => ({ all: vi.fn(), read: vi.fn(), download: vi.fn() }))
beforeEach(() => { vi.resetAllMocks(); user.value = { id: 1, role: 'finance' }; vi.mocked(all).mockResolvedValue([]) })

it('采购默认继承供应商账期，不偷偷提交当天作为指定付款日', () => {
  const fields = purchaseFields({ projects: [], items: [], users: [], partners: [{ id: 1, kind: 'supplier', name: '供应商', code: 'S1', payment_term: 'month30' }] })
  const data = payload(fields, defaults(fields))
  expect(data).not.toHaveProperty('payment_due_date')
  expect(data).not.toHaveProperty('payment_term')
  expect(fields.find(f => f.key === 'supplier')?.options?.[0]?.label).toContain('月结30天')
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
  expect(refund.fields.find(f => f.key === 'reconciliation')?.optional).toBe(false)
  expect(refund.fields.find(f => f.key === 'reconciliation')?.options).toEqual([])
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
