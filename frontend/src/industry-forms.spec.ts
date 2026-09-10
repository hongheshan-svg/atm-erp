import { describe, expect, it } from 'vitest'
import { industryCommand } from './industry-forms'
import { defaults, payload, validateFields } from './forms'
import { date } from './modules/shared'
import { options } from './catalog'
import type { Command, Field } from './types'

const form = (path: string, fields: Field[]): Command => industryCommand({ title: '操作', path, fields })
describe('自动化设备表单', () => {
  it('需求指引只用于提示，不自动写入技术指标或改变原始载荷', () => {
    const fields: Field[] = [{ key: 'requirements', label: '需求说明', optional: true }, { key: 'equipment_quantity', label: '设备数量', initial: 1 }]
    const c = form('/business/sales/', fields)
    expect(c.fields[0]?.placeholder).toContain('精度')
    expect(payload(c.fields, defaults(c.fields))).toEqual({ equipment_quantity: 1 })
    expect(fields[0]?.placeholder).toBeUndefined()
    expect(() => validateFields(c.fields, { equipment_quantity: '1.5' })).toThrow('整数')
    expect(() => validateFields(c.fields, { equipment_quantity: '0' })).toThrow('不能小于 1')
  })
  it('采购材料允许小数，收货允许全隔离，发货台数单独限制整数', () => {
    const c = form('/business/purchases/1/receive/', [{ key: 'quantity', label: '数量' }, { key: 'pending_quantity', label: '隔离数量' }])
    expect(() => validateFields(c.fields, { quantity: '0', pending_quantity: '12.125' })).not.toThrow()
    expect(() => validateFields(c.fields, { quantity: '1.0001', pending_quantity: '0' })).toThrow('3 位小数')
    const ship = form('/business/projects/1/ship/', [{ key: 'quantity', label: '设备数量' }, { key: 'materials', label: '配套', type: 'rows', fields: [{ key: 'quantity', label: '数量' }] }])
    expect(ship.fields[1]?.numeric).toBeUndefined()
    expect(ship.fields[1]?.hint).toBeUndefined()
    expect(() => validateFields(ship.fields, { quantity: '1', materials: [{ quantity: '0.125' }] })).not.toThrow()
    expect(() => validateFields(ship.fields, { quantity: '1.2', materials: [] })).toThrow('整数')
  })
  it('银行支出和退款对账允许负数，付款金额仍非负，不舍入大金额', () => {
    const bank = form('/business/bank-records/', [{ key: 'amount', label: '银行金额' }])
    const pay = form('/business/entries/1/pay/', bank.fields.map(f => ({ key: f.key, label: f.label })))
    expect(() => validateFields(bank.fields, { amount: '-100.01' })).not.toThrow()
    expect(() => validateFields(pay.fields, { amount: '-100.01' })).toThrow()
    for (const amount of ['1e3', '1,000', '1.001', 'NaN']) expect(() => validateFields(pay.fields, { amount })).toThrow()
    const large = { amount: '9999999999999999.99' }
    expect(() => validateFields(pay.fields, large)).not.toThrow()
    expect(payload(pay.fields, large)).toEqual(large)
    const refund = form('/business/reconciliations/', [{ key: 'counterparty_balance', label: '对方余额' }])
    expect(() => validateFields(refund.fields, { counterparty_balance: '-1' })).not.toThrow()
  })
  it('工时更正可归零，拒绝超 24 小时，备注与只读字段按原规则保留', () => {
    const c = form('/business/time/1/amend/', [{ key: 'hours', label: '工时', hint: '0 撤销原工时' }])
    expect(c.fields[0]?.hint).toBe('0 撤销原工时')
    expect(() => validateFields(c.fields, { hours: '0' })).not.toThrow()
    expect(() => validateFields(c.fields, { hours: '24.01' })).toThrow('24')
    const readonly: Command = { title: '历史', path: '', readonly: true, fields: [{ key: 'hours', label: '工时' }] }
    expect(industryCommand(readonly)).toBe(readonly)
  })
  it('检查未显示分页的明细，锁定行结构仍检查可编辑的子字段', () => {
    const c = form('/business/purchases/', [{ key: 'lines', label: '采购明细', type: 'rows', readonly: true, fields: [{ key: 'item_label', label: '物料', displayOnly: true }, { key: 'unit_price', label: '单价' }] }])
    const lines = Array.from({ length: 21 }, () => ({ unit_price: '2.00' }))
    lines[20]!.unit_price = ''
    expect(() => validateFields(c.fields, { lines })).toThrow('第 21 行')
  })
  it('计划日期不假设今天，实际日期保留默认值，选项显示型号品牌单位', () => {
    expect(date('due_date', '计划交期', true).initial).toBe('')
    expect(date('received_date', '实际收货').initial).toMatch(/^\d{4}-\d{2}-\d{2}$/)
    expect(options([{ id: 1, code: '001', name: '电机', specification: '750W', brand: '确认品牌', unit: '台' }])[0]?.label).toBe('001 · 电机 · 750W · 确认品牌 · 台')
  })
})
