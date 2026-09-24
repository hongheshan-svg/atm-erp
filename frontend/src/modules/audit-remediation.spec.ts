import { beforeEach, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { all, read } from '../api'
import { actionCommand, columns } from '../business'
import { user } from '../session'
import { defaults, payload } from '../forms'
import FormFields from '../components/FormFields.vue'
import { display } from './shared'
import { salesColumns } from './sales'
import { fileSize } from './documents'
import { shipMaterialOptions } from './projects'
import { purchaseFields } from './purchases'

vi.mock('../api', () => ({ all: vi.fn(), read: vi.fn(), write: vi.fn(), download: vi.fn() }))
beforeEach(() => { vi.resetAllMocks(); user.value = { id: 1, roles: ['admin'] } })

it('取消项目的已签约销售单在列表中标注项目已取消', () => {
  const status = salesColumns.find(c => c.key === 'status')!
  expect(status.format!({ status: 'signed', project_status: 'cancelled' })).toBe('已签约 · 项目已取消')
  expect(status.format!({ status: 'signed', project_status: 'active' })).toBe('已签约')
  expect(status.format!({ status: 'draft', project_status: null })).toBe('草稿')
})

it('只翻译枚举列，用户名和自由文本原样显示', () => {
  expect(display('admin', 'username')).toBe('admin')
  expect(display('finance', 'display_name')).toBe('finance')
  expect(display('test', 'title')).toBe('test')
  expect(display('admin', 'role')).toBe('管理员')
  expect(display('test', 'kind')).toBe('调试')
  // 附件分类与库存流水同用 receipt，按列区分。
  expect(display('receipt', 'category')).toBe('结算凭证')
  expect(display('receipt', 'kind')).toBe('采购收货')
  expect(display(true, 'is_active')).toBe('启用')
  expect(display(true, 'cancelled')).toBe('是')
  expect(display(false, 'bank_matched')).toBe('否')
  // 未指定列时保持原有枚举翻译（状态徽标等显式枚举场景）。
  expect(display('active')).toBe('执行中')
})

it('操作审计显示操作人姓名', () => {
  const actor = columns.audit!.find(c => c.key === 'actor')!
  expect(actor.format!({ actor: 3, actor_name: '张工' })).toBe('张工')
  expect(actor.format!({ actor: 3 })).toBe('用户 #3')
})

it('领料的售后任务只列所选项目，换项目后清空原选择', async () => {
  vi.mocked(all).mockResolvedValue([
    { id: 11, project: 1, title: '一号项目售后' },
    { id: 22, project: 2, title: '二号项目售后' },
  ])
  const command = await actionCommand('stocks', { id: 5, quantity: '3' }, '领料')
  const task = command.fields.find(f => f.key === 'task')!
  expect(task.optionsFor!({ project: 1 })).toEqual([{ value: 11, label: '一号项目售后' }])
  expect(task.optionsFor!({ project: '' })).toEqual([])
  const shared = command.fields.find(f => f.key === 'confirm_shared')!
  expect(shared.type).toBe('boolean')
  expect(defaults(command.fields).confirm_shared).toBe(false)

  const model = { ...defaults(command.fields.filter(f => !f.remotePath)), project: 1, task: 11 }
  const wrapper = mount(FormFields, { props: { fields: command.fields.filter(f => !f.remotePath), modelValue: model } })
  expect(wrapper.findAll('select[aria-label="售后任务（生产领料留空）"] option').map(o => o.text())).toEqual(['请选择', '一号项目售后'])
  model.project = 2
  await wrapper.setProps({ modelValue: { ...model } })
  await nextTick()
  expect(wrapper.props('modelValue').task).toBe('')
  wrapper.unmount()
})

it('收货提供已用库位候选并默认不新建库位', async () => {
  vi.mocked(read).mockImplementation(async (path: string) => (path === '/business/stocks/locations/' ? ['主仓', 'A区'] : { lines: [{ id: 1, item_name: '电机', quantity: '2', received_quantity: '0', cancelled_quantity: '0', pending_quantity: '0' }] }))
  const command = await actionCommand('purchases', { id: 9, status: 'approved' }, '收货')
  expect(command.fields.find(f => f.key === 'location')?.suggestions).toEqual(['主仓', 'A区'])
  const body = payload(command.fields, { ...defaults(command.fields, command.initial), reason: '到货' })
  expect(body.new_location).toBe(false)
  expect(body.location).toBe('主仓')
})

it('采购单默认一年质保并可修改', () => {
  const field = purchaseFields().find(f => f.key === 'warranty_months')!
  expect(field.initial).toBe('12')
  expect(field.numeric).toEqual({ scale: 0, min: 1, max: 120 })
})

it('项目经理登记售后可填写过保免费原因', async () => {
  vi.mocked(all).mockImplementation(async (path: string) => (path === '/business/deliveries/' ? [{ id: 4, code: 'DEL1', accepted_date: '2026-01-01' }] : []))
  const command = await actionCommand('projects', { id: 7, status: 'warranty', can_manage: true, can_register_service: true, manager: 1, members: [] }, '登记售后')
  expect(command.fields.map(f => f.key)).toEqual(expect.arrayContaining(['fee', 'free_reason']))
  expect(command.fields.find(f => f.key === 'free_reason')?.optional).toBe(true)
})

it('附件大小按 B/KB/MB 显示', () => {
  expect(fileSize(512)).toBe('512 B')
  expect(fileSize(2048)).toBe('2.0 KB')
  expect(fileSize(5 * 1024 * 1024)).toBe('5.0 MB')
  expect(fileSize(null)).toBe('—')
  expect(columns.documents!.find(c => c.key === 'size')!.format!({ size: 1536 })).toBe('1.5 KB')
})

it('发货配套物料按物料合并并列出全部单元', () => {
  const options = shipMaterialOptions([
    { item: 3, item_code: 'M1', item_name: '导轨', assembly_unit: 'A单元', quantity: '2.000' },
    { item: 3, item_code: 'M1', item_name: '导轨', assembly_unit: 'B单元', quantity: '1.500' },
    { item: 4, item_code: 'M2', item_name: '螺钉', assembly_unit: '', quantity: '10' },
  ])
  expect(options).toEqual([
    { value: 3, label: 'M1 · 导轨 · A单元、B单元 · BOM 合计 3.500' },
    { value: 4, label: 'M2 · 螺钉 · 未分单元 · BOM 合计 10.000' },
  ])
})
