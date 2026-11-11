import { beforeEach, expect, it, vi } from 'vitest'
import { read } from '../api'
import { defaults, fieldIssues, payload } from '../forms'
import { industryCommand } from '../industry-forms'
import { user } from '../session'
import type { Field, Row } from '../types'
import { all } from '../api'
import { actionCommand, purchaseDetailLine, purchaseTotal, receiptLines } from './purchases'

vi.mock('../api', () => ({ all: vi.fn(), read: vi.fn() }))

const detail = {
  id: 9, code: 'PO-9', status: 'partial', project: 4, project_code: 'ATM2690', project_name: '下料线', supplier_name: '精工机械',
  due_date: '2026-12-01', payment_term: 'cash', created_at: '2026-11-01T09:00:00+08:00',
  lines: [
    { id: 1, item_code: 'M-1', item_name: '伺服电机', specification: '400W', brand: '安川', drawing_number: '', unit: '台', assembly_unit: '上料单元', quantity: '5.000', unit_price: '100.00', received_quantity: '3.000', cancelled_quantity: '0.000', returned_quantity: '0.000', pending_quantity: '0.000',
      receipts: [{ id: 11, received_date: '2026-11-03', quantity: '1.000', location: '主仓' }, { id: 12, received_date: '2026-11-08', quantity: '2.000', location: 'A区' }], last_received_date: '2026-11-08' },
    { id: 2, item_code: 'M-2', item_name: '气缸', specification: 'SC32x50', brand: '', drawing_number: 'A-01', drawing_revision: 'B', unit: '件', assembly_unit: '', quantity: '4.000', unit_price: '20.00', received_quantity: '1.000', cancelled_quantity: '1.000', returned_quantity: '0.000', pending_quantity: '1.000',
      receipts: [{ id: 13, received_date: '2026-11-05', quantity: '1.000', location: '主仓' }], last_received_date: '2026-11-05' },
    { id: 3, item_code: 'M-3', item_name: '导轨', specification: '', unit: '根', quantity: '2.000', unit_price: '50.00', received_quantity: '0.000', cancelled_quantity: '0.000', returned_quantity: '0.000', pending_quantity: '0.000', receipts: [], last_received_date: null },
  ],
}

beforeEach(() => {
  vi.resetAllMocks()
  vi.mocked(read).mockImplementation(async (path: string) => (path.includes('locations') ? ['主仓', 'A区'] : detail))
})

it('收货对话框入库日期排第一并写明用途；仓管兼采购可勾选余量不再到货，原因随勾选出现', async () => {
  user.value = { id: 1, roles: ['warehouse', 'purchaser'] }
  const command = industryCommand(await actionCommand('purchases', { id: 9, status: 'partial' }, '收货'))
  expect(command.fields[0]).toMatchObject({ key: 'received_date', label: '入库日期（实际到货 / 合格收货日）' })
  expect(command.fields[0]!.hint).toContain('库存流水')
  expect(command.fields.map(f => f.key)).toEqual(['received_date', 'location', 'new_location', 'backfill_reason', 'reason', 'lines', 'cancel_reason'])
  const data = defaults(command.fields, command.initial)
  expect(data.lines.map((line: Row) => [line.line, line.selected, line.quantity, line.quarantined])).toEqual([[1, true, '2.000', '0.000'], [2, true, '1.000', '1.000'], [3, true, '2.000', '0.000']])
  const reasonField = command.fields.find(f => f.key === 'cancel_reason')!
  expect(reasonField.visibleWhen!(data)).toBe(false)
  data.lines[0].quantity = '1'
  data.lines[0].cancel_remainder = true
  data.lines[2].selected = false
  data.lines[2].quantity = '0'
  expect(reasonField.visibleWhen!(data)).toBe(true)
  expect(fieldIssues(command.fields, data).map(issue => issue.path)).toEqual(['cancel_reason'])
  data.cancel_reason = '供应商停产'
  const body = command.prepare!(payload(command.fields, data))
  expect(body).toMatchObject({ cancel_reason: '供应商停产', lines: [{ line: 1, quantity: '1', cancel_remainder: true }, { line: 2, quantity: '1.000' }] })
  expect(body.lines[1]).not.toHaveProperty('cancel_remainder')
  expect(body.lines.every((line: Row) => !('selected' in line))).toBe(true)
  expect(command.successNote!({ id: 9, cancelled: [{ line: 1, quantity: '4.000' }] })).toContain('已同时取消 1 行未收余量')
  expect(command.successNote!({ id: 9 })).toBe('')
})

it('纯仓管收货不出现余量不再到货；多送在提交前按行拦下', async () => {
  user.value = { id: 2, roles: ['warehouse'] }
  const command = await actionCommand('purchases', { id: 9, status: 'partial' }, '收货')
  expect(command.fields.some(f => f.key === 'cancel_reason')).toBe(false)
  const lines = command.fields.find(f => f.key === 'lines')!
  expect(lines.fields!.some(f => f.key === 'cancel_remainder')).toBe(false)
  const data = defaults(command.fields, command.initial)
  data.lines[1].quantity = '3'
  expect(() => command.prepare!(payload(command.fields, data))).toThrow('第 2 行超过待收 1')
  const accept = await actionCommand('purchases', { id: 9, status: 'partial' }, '隔离品合格入库')
  expect(accept.fields[0]).toMatchObject({ key: 'received_date', label: '入库日期（检验合格日）' })
})

it('查看明细：首列合并名称、编码、规格，项目号与单元同列，入库日期逐批列出', async () => {
  user.value = { id: 2, roles: ['warehouse'] }
  const command = await actionCommand('purchases', { id: 9, status: 'partial' }, '查看明细')
  expect(command.readonly).toBe(true)
  const lines = command.fields.find(f => f.key === 'lines')!
  const columns = lines.fields!.map((f: Field) => f.label)
  expect(columns).toEqual(['物料 / 编码 / 规格', '项目号 / 单元', '明细交期', '采购数量', '已收', '待收', '已取消', '隔离待处理', '入库日期'])
  expect(lines.fields!.filter((f: Field) => f.multiline).map(f => f.key)).toEqual(['material_text', 'project_unit', 'received_label'])
  expect(command.initial!.last_received_label).toBe('2026-11-08')
  const [first, second, third] = command.initial!.lines as Row[]
  expect(first!.material_text).toBe('伺服电机\n编码 M-1 · 规格 400W\n品牌 安川')
  expect(first!.project_unit).toBe('ATM2690\n上料单元')
  expect(first!.received_label).toBe('2026-11-08\n共 2 批\n2026-11-03 入库 1\n2026-11-08 入库 2')
  expect([first!.quantity, first!.received_quantity, first!.remaining]).toEqual(['5', '3', '2'])
  expect(second!.material_text).toBe('气缸\n编码 M-2 · 规格 SC32x50\n图号 A-01（B）')
  expect([second!.project_unit, second!.received_label, second!.remaining]).toEqual(['ATM2690\n未分单元', '2026-11-05', '1'])
  expect(third!.received_label).toBe('—')
  // 有单价权限的采购才看到单价列。
  user.value = { id: 3, roles: ['purchaser'] }
  const buyerView = await actionCommand('purchases', { id: 9, status: 'partial' }, '查看明细')
  expect(buyerView.fields.find(f => f.key === 'lines')!.fields!.map(f => f.key)).toContain('unit_price')
})

it('含税合计与服务端同口径：逐行四舍五入到分后再相加', () => {
  expect(purchaseTotal([{ quantity: '1.500', unit_price: '0.33' }, { quantity: '1.500', unit_price: '0.33' }])).toBe('1.00')
  expect(purchaseTotal([{ quantity: '1000.000', unit_price: '2095.50' }])).toBe('2,095,500.00')
  expect(purchaseTotal([{ quantity: '1', unit_price: null }])).toBe('—')
  expect(purchaseTotal([])).toBe('—')
})

it('收货多送不足 1 个单位也在前端拦下', () => {
  const data = { lines: [{ line: 1, quantity: '2.5', pending_quantity: '0' }] }
  expect(() => receiptLines(data, { '1': '2.000' })).toThrow('第 1 行超过待收 2')
  expect(receiptLines({ lines: [{ line: 1, quantity: '1.5', pending_quantity: '0.5' }] }, { '1': '2.000' }).lines).toHaveLength(1)
  expect(purchaseDetailLine({ quantity: '2.000', received_quantity: '2.500' }, {}).remaining).toBe('0')
})

it('处理采购质保只按类型读取收货和采购退货流水', async () => {
  user.value = { id: 1, roles: ['warehouse'] }
  vi.mocked(read).mockResolvedValue({ cases: [], receipts: [], warranty_months: 12 })
  vi.mocked(all).mockImplementation(async (_path: string, params?: Row) => params?.kind === 'receipt'
    ? [{ id: 31, kind: 'receipt', item_name: '电机', quantity: '1.000' }]
    : [{ id: 32, kind: 'purchase_return', item_name: '电机', quantity: '1.000' }])
  const command = await actionCommand('purchases', { id: 9, project: 4, status: 'approved' }, '处理采购质保')
  expect(all).toHaveBeenCalledWith('/business/moves/', { project: 4, kind: 'receipt' })
  expect(all).toHaveBeenCalledWith('/business/moves/', { project: 4, kind: 'purchase_return' })
  expect(all).not.toHaveBeenCalledWith('/business/moves/', { project: 4 })
  expect(command.fields.find(f => f.key === 'replacement')?.options?.map(o => o.value)).toEqual([31])
  expect(command.fields.find(f => f.key === 'returned')?.options?.map(o => o.value)).toEqual([32])
})

it('明细待收不出现负数；批次多时入库日期只列最近 3 批', () => {
  expect(purchaseDetailLine({ quantity: '1.000', received_quantity: '1.000', cancelled_quantity: '1.000', pending_quantity: '0' }, {}).remaining).toBe('0')
  const receipts = ['01', '02', '03', '04'].map((day, index) => ({ id: index, received_date: `2026-11-${day}`, quantity: '1.000' }))
  expect(purchaseDetailLine({ quantity: '9.000', received_quantity: '4.000', receipts, last_received_date: '2026-11-04' }, {}).received_label)
    .toBe('2026-11-04\n共 4 批，列出最近 3 批\n2026-11-02 入库 1\n2026-11-03 入库 1\n2026-11-04 入库 1')
})
