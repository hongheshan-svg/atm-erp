import { beforeEach, expect, it, vi } from 'vitest'
import { all, read } from '../api'
import { defaults, payload } from '../forms'
import { user } from '../session'
import { actionCommand, columns } from './finance'

vi.mock('../api', () => ({ all: vi.fn(), read: vi.fn(), download: vi.fn() }))
beforeEach(() => {
  vi.resetAllMocks()
  user.value = { id: 9, roles: ['finance'] }
  vi.mocked(all).mockResolvedValue([])
})
const entry = { id: 7, project: 3, purchase: 2, balance: '500.00' }
function statements(rows: Record<string, unknown>[]) {
  vi.mocked(all).mockImplementation(async path => path.includes('reconciliations') ? rows : [])
}
const statement = { id: 1, code: 'DZ1', kind: 'settlement', valid: true, remaining_amount: '300.00' }

it('采购对账申请默认已收货未付额，包括未来到期批次，按分相加', async () => {
  const command = await actionCommand('entries', { ...entry, payment_schedule: [
    { due_date: '2026-11-01', amount: '100.10' }, { due_date: '2026-12-01', amount: '100.20' },
  ] }, '生成对账单')
  expect(command.initial?.approved_amount).toBe('200.30')
  expect(command.initial?.counterparty_balance).toBe('500.00')
  expect(command.fields.find(field => field.key === 'approved_amount')?.hint).toContain('200.30')
  expect(read).not.toHaveBeenCalled()
})

it('缺少收货批次时读取款项详情，未收货不给出整单申请额度', async () => {
  vi.mocked(read).mockResolvedValue({ ...entry, payment_schedule: [] })
  const command = await actionCommand('entries', entry, '生成对账单')
  expect(read).toHaveBeenCalledWith('/business/entries/7/')
  expect(command.initial?.approved_amount).toBe('')
  expect(command.fields.find(field => field.key === 'approved_amount')?.hint).toContain('0.00')
  const prepayment = await actionCommand('entries', entry, '申请预付款核准')
  expect(prepayment.initial?.approved_amount).toBe('500')
})

it.each([
  ['500.00', '300.00', '300.00'],
  ['200.10', '300.00', '200.10'],
  ['90071992547409.93', '90071992547409.92', '90071992547409.92'],
])('单张有效对账默认取余额 %s 与额度 %s 的较小值', async (balance, remaining, expected) => {
  statements([{ ...statement, remaining_amount: remaining }, { ...statement, id: 2, valid: false }])
  const command = await actionCommand('entries', { ...entry, balance }, '登记收付款')
  expect(command.initial).toEqual({ amount: expected, reconciliation: 1 })
  expect(command.fields.find(field => field.key === 'amount')?.hint).toContain(remaining)
})

it('多张对账各自显示默认值，留空按所选额度提交且手填金额不被覆盖', async () => {
  statements([statement, { ...statement, id: 2, code: 'DZ2', remaining_amount: '120.25' }])
  const command = await actionCommand('entries', entry, '登记收付款')
  expect(command.initial?.amount).toBe('')
  expect(command.fields.find(field => field.key === 'reconciliation')?.options?.[1]?.label).toContain('本次默认 120.25')
  const form = defaults(command.fields, command.initial)
  const submit = (selection: number | string, value = '') => command.prepare!(payload(command.fields, { ...form, reconciliation: selection, amount: value }))
  expect(submit(1).amount).toBe('300.00')
  expect(submit('2').amount).toBe('120.25')
  expect(submit(2, '25.50').amount).toBe('25.50')
  expect(submit(2, '130').amount).toBe('130') // 服务端负责重验，不静默截断实际填写金额。
  expect(() => submit('')).toThrow('请选择有效的已确认对账单')
})

it('退款仅使用退款对账剩余额度，普通客户收款无对账时仍取待收余额', async () => {
  statements([statement, { ...statement, id: 2, kind: 'refund', remaining_amount: '80.20' }])
  const refund = await actionCommand('entries', { ...entry, balance: '-200.00' }, '退款')
  expect(refund.initial).toEqual({ reconciliation: 2, amount: '80.20' })
  statements([])
  const receipt = await actionCommand('entries', { ...entry, purchase: null }, '登记收付款')
  expect(receipt.initial?.amount).toBe('500.00')
})

it('多张客户对账可不选，留空默认整笔待收且显式金额优先', async () => {
  statements([statement, { ...statement, id: 2 }])
  const command = await actionCommand('entries', { ...entry, purchase: null }, '登记收付款')
  expect(command.prepare!({}).amount).toBe('500.00')
  expect(command.prepare!({ amount: '20' }).amount).toBe('20')
  expect(command.fields.find(field => field.key === 'amount')?.hint).toContain('不选对账时默认 500.00')
})

it('约定付款日独立显示且不把未收货约定转成可申请额度或到期批次', async () => {
  expect(columns.entries?.find(column => column.key === 'agreed_payment_date')?.label).toBe('约定付款日')
  expect(columns.entries?.find(column => column.key === 'due_date')?.label).toBe('到期日')
  const row = { ...entry, agreed_payment_date: '2026-01-01', due_date: null, payment_schedule: [] }
  const detail = await actionCommand('entries', row, '查看到期明细')
  expect(detail.initial).toEqual({ agreed_payment_date: '2026-01-01', lines: [] })
  expect(detail.notice?.text).toContain('仅有日期不产生可付款额度')
  const application = await actionCommand('entries', row, '生成对账单')
  expect(application.initial?.approved_amount).toBe('')
  expect(application.fields.find(field => field.key === 'approved_amount')?.hint).toContain('0.00')
})

it('款项状态在已付超过合格收货净额时显示预付提示，金额只作展示', () => {
  const status = columns.entries.find(col => col.key === 'status')!
  const plain = { status: 'open', balance: '300.00' }
  expect(status.format?.(plain)).toBe('未结')
  expect(status.tip?.(plain)).toBeUndefined()
  const prepaid = { ...plain, prepaid_excess: '200.00' }
  expect(status.format?.(prepaid)).toBe('未结 · 已超付 200.00（预付）')
  expect(status.tip?.(prepaid)).toBe('已付超过合格收货净额 200.00 元，视为预付；待后续到货或取消余量后再结算。')
})
