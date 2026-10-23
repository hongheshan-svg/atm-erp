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
  expect(wrapper.findAll('th').map(th => th.text()).slice(1, 10)).toEqual(['项目号', '产品编号', '零件名称', '单元', '图号 / 型号', '版本 / 品牌', '单位', '需求数量', '零件类型'])
  expect(wrapper.findAll('th').at(-1)!.text()).toBe('备注')
  expect(wrapper.text()).toContain('001226000006')
  expect(wrapper.text()).toContain('A2608-01-00017')
  expect(wrapper.text()).toContain('有图·钣金')
  await wrapper.findAll('textarea')[0]!.setValue('第一件备注')
  await wrapper.findAll('textarea')[1]!.setValue('第二件备注')
  expect(payload([field], data)).toEqual({ lines: [
    { line: 1, quantity: '1', pending_quantity: '0', remark: '第一件备注' },
    { line: 2, quantity: '1', pending_quantity: '0', remark: '第二件备注' },
  ] })
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
