import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { all, read } from '../api'
import { defaults, fieldIssues, payload } from '../forms'
import { industryCommand } from '../industry-forms'
import { user } from '../session'
import type { Row } from '../types'
import { actionCommand as purchaseAction } from './purchases'
import { actionCommand as financeAction } from './finance'
import { createCommand as bankCreate } from './settlement'
import { salesCommand } from './sales'
import { date } from './shared'

vi.mock('../api', () => ({ all: vi.fn(), read: vi.fn(), download: vi.fn() }))

beforeEach(() => {
  vi.resetAllMocks()
  vi.useFakeTimers()
  vi.setSystemTime(new Date('2026-10-21T23:20:00Z'))
  user.value = { id: 1, roles: ['admin'] }
  vi.mocked(all).mockResolvedValue([])
})
afterEach(() => vi.useRealTimers())

it.each(['收货', '隔离品合格入库'])('%s默认当日业务日期，不误触发历史补录；真实历史仍必填原因', async name => {
  const detail = { id: 9, created_at: '2026-10-22T06:00:00+08:00', lines: [
    { id: 1, item_name: '电机', quantity: '5', received_quantity: '0', cancelled_quantity: '0', pending_quantity: '2' },
  ] }
  vi.mocked(read).mockImplementation(async path => path.includes('locations') ? ['主仓'] : detail)
  const command = industryCommand(await purchaseAction('purchases', { id: 9 }, name))
  const data = defaults(command.fields, command.initial)
  data.reason = '当日正常到货'
  expect(data.received_date).toBe('2026-10-22')
  expect(fieldIssues(command.fields, data)).toEqual([])
  expect(payload(command.fields, data)).not.toHaveProperty('backfill_reason')
  data.received_date = '2026-10-21'
  expect(fieldIssues(command.fields, data).map(issue => issue.path)).toEqual(['backfill_reason'])
  data.backfill_reason = '补录原送货单'
  expect(fieldIssues(command.fields, data)).toEqual([])
  expect(payload(command.fields, data)).toMatchObject({ received_date: '2026-10-21', backfill_reason: '补录原送货单' })
})

it('当天收货的采购报修默认同一业务日，不早于收货日', async () => {
  vi.mocked(read).mockResolvedValue({ receipts: [{ id: 3, item: '电机', quantity: '1', warranty_end: '2027-10-22' }] })
  const command = industryCommand(await purchaseAction('purchases', { id: 9 }, '登记采购质保'))
  const data: Row = { ...defaults(command.fields, command.initial), receipt: 3, quantity: '1', description: '到货当日报修' }
  expect(data.date).toBe('2026-10-22')
  expect(fieldIssues(command.fields, data)).toEqual([])
  expect(payload(command.fields, data).date).toBe('2026-10-22')
})

it('收付款和银行登记共享业务日期默认值，计划到期日仍留空', async () => {
  const payment = await financeAction('entries', { id: 9, project: 2, kind: 'expense', balance: '100.00' }, '登记收付款')
  const bank = await bankCreate('bank-records')
  for (const command of [payment, bank]) expect(defaults(command.fields, command.initial).date).toBe('2026-10-22')
  expect(date('due_date', '付款到期日').initial).toBe('')
})

it('签约和补充协议默认业务日期一致，不给合同约定到期日补默认值', async () => {
  vi.mocked(read).mockResolvedValue({ contract_amount: '100', equipment_quantity: 1, warranty_months: 12 })
  for (const name of ['签约', '签订补充协议']) {
    const command = await salesCommand({ id: 9, project: 3, quote_amount: '100' }, name)
    const data = defaults(command.fields, command.initial)
    expect(data.date).toBe('2026-10-22')
    const milestoneFields = command.fields.find(field => field.key === 'milestones')!.fields!
    expect(defaults(milestoneFields).due_date).toBe('')
    if (name === '签约') expect(data.milestones[0].due_date).toBe('')
  }
})
