import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, expect, it, vi } from 'vitest'
import { read } from '../api'
import { defaults, payload } from '../forms'
import { draftKey, loadDraft, saveDraft } from '../form-experience'
import { materialDetails, warehouseLines } from '../modules/warehouse-lines'
import FormFields from './FormFields.vue'
import WarehouseLines from './WarehouseLines.vue'
import type { Row } from '../types'
vi.mock('../api', () => ({ read: vi.fn() }))
beforeEach(() => { vi.resetAllMocks(); sessionStorage.clear() })
const material = materialDetails({ item: 1, item_code: '001226000006', item_name: '坦克链安装板', drawing_number: 'A2608-01-00017', specification: '板厚2mm', drawing_revision: 'A', brand: '指定品牌', product_category: '12', part_type: 'custom', unit: 'PCS' })

it('收货表包含截图资料，末列备注；输入按行保留且资料不进入写入请求', async () => {
  const initial = [1, 2].map(line => ({ ...material, line, project_code: 'A2608', assembly_unit: `单元${line}`, required_quantity: '3', remaining: '2', quantity: '1', pending_quantity: '0', remark: '' }))
  const field = warehouseLines('receipt', initial)
  const data = defaults([field])
  const wrapper = mount(FormFields, { props: { fields: [field], modelValue: data } })
  // 1366 宽度下不横向滚动：项目号移到表头，编号与名称、图号型号版本品牌与类型各并成一列，数量输入紧随待收。
  expect(wrapper.findAll('th').map(th => th.text()).slice(1)).toEqual(['产品编号 / 零件名称', '单元', '图号 / 型号 / 版本 / 类型', '单位', '需求数量', '待收数量', '本次合格数量', '不合格隔离数量', '备注'])
  expect(wrapper.get('legend').text()).toContain('项目 A2608')
  expect(wrapper.get('.warehouse-summary').text()).toContain('本次合格 2.000 / 待收 4.000，共 2 行')
  // 待收 2、本次只填 1：两行都高亮提醒部分到货。
  expect(wrapper.findAll('tbody tr.partial-line')).toHaveLength(2)
  expect(wrapper.text()).toContain('001226000006')
  expect(wrapper.text()).toContain('A2608-01-00017')
  expect(wrapper.text()).toContain('有图·钣金')
  await wrapper.findAll('textarea')[0]!.setValue('第一件备注')
  await wrapper.findAll('textarea')[1]!.setValue('第二件备注')
  expect(payload([field], data)).toEqual({ lines: [
    { line: 1, quantity: '1', pending_quantity: '0', remark: '第一件备注' },
    { line: 2, quantity: '1', pending_quantity: '0', remark: '第二件备注' },
  ] })
  const button = (text: string) => wrapper.findAll('button').find(b => b.text() === text)!
  await button('全部按待收填入').trigger('click')
  expect(data.lines.map((line: Row) => line.quantity)).toEqual(['2', '2'])
  expect(wrapper.get('.warehouse-summary').text()).toContain('本次合格 4.000 / 待收 4.000')
  expect(wrapper.findAll('tbody tr.partial-line')).toHaveLength(0)
  await button('全部清零').trigger('click')
  expect(data.lines.map((line: Row) => line.quantity)).toEqual(['0', '0'])
  wrapper.unmount()
})

it('按 BOM 批量领料：服务端给出需求和未领量，不逐行读取项目需求，可清零后恢复建议数量', async () => {
  const initial = [{ ...material, stock: 4, project_code: 'A2608', project_name: '上料线', location: '主仓', required_quantity: '5.000', bom_remaining: '3.000', remaining: '2.000', quantity: '2.000', remark: '' },
    { ...material, stock: 5, project_code: 'A2608', project_name: '上料线', location: '二号仓', required_quantity: '5.000', bom_remaining: '3.000', remaining: '9.000', quantity: '1.000', remark: '' }]
  const field = warehouseLines('issue', initial, { batch: true })
  const wrapper = mount(WarehouseLines, { props: { field, prefix: 'lines', modelValue: initial.map(row => ({ stock: row.stock, quantity: row.quantity, remark: '' })), context: { project: 1 } } })
  await flushPromises()
  expect(read).not.toHaveBeenCalled()
  expect(wrapper.findAll('th').map(th => th.text())).toContain('BOM 未领')
  expect(wrapper.get('legend').text()).toContain('项目 A2608 · 上料线')
  expect(wrapper.text()).toContain('5.000')
  expect(wrapper.get('.warehouse-summary').text()).toContain('本次出库 3.000')
  const button = (text: string) => wrapper.findAll('button').find(b => b.text() === text)!
  await button('全部清零').trigger('click')
  expect(wrapper.get('.warehouse-summary').text()).toContain('本次出库 0.000')
  await button('恢复建议数量').trigger('click')
  expect(wrapper.get('.warehouse-summary').text()).toContain('本次出库 3.000')
  expect(field.fields!.find(f => f.key === 'quantity')!.numeric!.min).toBe(0)
  wrapper.unmount()
})

it('分页错误定位跳到正确页；恢复草稿后仍显示原物料资料', async () => {
  const initial = Array.from({ length: 25 }, (_, i) => ({ ...material, line: i + 1, quantity: '1', pending_quantity: '0', remark: '' }))
  const field = warehouseLines('receipt', initial)
  const command = { title: '收货', path: '/business/purchases/9/receive/', fields: [field] }
  const data = defaults(command.fields)
  data.lines[24].remark = '末行已填写'
  const key = draftKey(command, 1)
  expect(saveDraft(key, command, data)).toBe(true)
  const restored = loadDraft(key, command)!
  expect(restored.lines[24]).not.toHaveProperty('item_name')
  const wrapper = mount(FormFields, { props: { fields: [field], modelValue: restored, issues: { 'lines.24.quantity': '超出数量' } } })
  await wrapper.vm.focusPath('lines.24.quantity')
  expect(wrapper.findAll('tbody tr')).toHaveLength(5)
  expect(wrapper.text()).toContain('坦克链安装板')
  expect(wrapper.text()).toContain('超出数量')
  expect((wrapper.findAll('textarea').at(-1)!.element as HTMLTextAreaElement).value).toBe('末行已填写')
  wrapper.unmount()
})

it('项目切换后清除旧需求，迟到响应不能覆盖新项目，售后不显示BOM限制', async () => {
  let resolveOld!: (value: Row) => void
  vi.mocked(read).mockImplementation(async path => {
    if (path === '/business/projects/1/') return new Promise(resolve => { resolveOld = resolve })
    if (path.endsWith('/demand/')) return { lines: [{ item: 1, quantity: '2.001' }, { item: 1, quantity: '3.002' }, { item: 2, quantity: '99' }] }
    return { code: 'NEW' }
  })
  const field = warehouseLines('issue', [{ ...material, stock: 4, remaining: '10' }])
  const wrapper = mount(WarehouseLines, { props: { field, prefix: 'lines', modelValue: [{ stock: 4, quantity: '1', remark: '' }], context: { project: 1 } } })
  await wrapper.setProps({ context: { project: 2 } })
  await flushPromises()
  expect(wrapper.text()).toContain('NEW')
  expect(wrapper.text()).toContain('5.003')
  resolveOld({ code: 'OLD' }); await flushPromises()
  expect(wrapper.text()).not.toContain('OLD')
  await wrapper.setProps({ context: { project: 2, task: 10 } }); await flushPromises()
  expect(wrapper.text()).toContain('按售后任务领用')
  await wrapper.setProps({ context: {} }); await flushPromises()
  expect(wrapper.text()).not.toContain('NEW')
  expect(wrapper.text()).toContain('请先选择项目')
  wrapper.unmount()
})

it('需求读取失败显示重试提示，不显示旧项目需求', async () => {
  vi.mocked(read).mockRejectedValue(new Error('读取失败'))
  const field = warehouseLines('issue', [{ ...material, stock: 1 }])
  const wrapper = mount(WarehouseLines, { props: { field, prefix: 'lines', modelValue: [{ stock: 1, quantity: '1' }], context: { project: 1 } } })
  await flushPromises()
  expect(wrapper.get('[role="alert"]').text()).toContain('项目需求读取失败')
  vi.mocked(read).mockImplementation(async path => path.endsWith('demand/') ? { lines: [] } : { code: 'A2608' })
  await wrapper.get('button').trigger('click'); await flushPromises()
  expect(wrapper.find('[role="alert"]').exists()).toBe(false)
  expect(wrapper.text()).toContain('A2608')
  wrapper.unmount()
})

it('库存勾选批量领料：逐行显示库位，数量默认留空，可一键按可用填入或清空，并读取所选项目需求', async () => {
  const initial = [{ ...material, stock: 1, location: '主仓', remaining: '5.000', quantity: '', remark: '' }, { ...materialDetails({ item: 2, item_code: 'M-2', item_name: '气缸', unit: '个' }), stock: 2, location: '二号仓', remaining: '1.500', quantity: '', remark: '' }]
  vi.mocked(read).mockImplementation(async path => String(path).endsWith('/demand/') ? { lines: [{ item: 1, quantity: '4.000' }] } : { id: 7, code: 'ATM01', name: '上料线' })
  const field = warehouseLines('issue', initial, { location: true })
  const wrapper = mount(WarehouseLines, { props: { field, prefix: 'lines', modelValue: initial.map(row => ({ stock: row.stock, quantity: '', remark: '' })), context: { project: 7 } } })
  await flushPromises()
  expect(wrapper.findAll('th').map(th => th.text()).slice(1)).toEqual(['产品编号 / 零件名称', '库位', '图号 / 型号 / 版本 / 类型', '单位', '需求数量', '本库位可用', '本次出库数量', '备注'])
  expect(wrapper.get('legend').text()).toContain('项目 ATM01 · 上料线')
  expect(wrapper.findAll('tbody tr')[0]!.text()).toContain('4.000')
  const button = (text: string) => wrapper.findAll('.warehouse-fill button').find(item => item.text() === text)!
  expect(wrapper.findAll('.warehouse-fill button').map(item => item.text())).toEqual(['全部按可用填入', '全部清空'])
  await button('全部按可用填入').trigger('click')
  expect(wrapper.props('modelValue').map((row: Row) => row.quantity)).toEqual(['5.000', '1.500'])
  await button('全部清空').trigger('click')
  expect(wrapper.props('modelValue').map((row: Row) => row.quantity)).toEqual(['', ''])
  wrapper.unmount()
})
