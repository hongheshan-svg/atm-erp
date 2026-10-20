import { afterEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import ImportFeedback from './ImportFeedback.vue'
import { pageSize } from '../pagination'

afterEach(() => { vi.restoreAllMocks(); pageSize.value = 10 })

it('汇总错误行、跨页定位具体单元格，筛选错误后仍保留原文件行号', async () => {
  const scroll = vi.fn()
  HTMLElement.prototype.scrollIntoView = scroll
  const rows = Array.from({ length: 14 }, (_, index) => ({ row: index + 2, data: { title: `任务${index + 1}`, quantity: index + 1 } }))
  const wrapper = mount(ImportFeedback, { attachTo: document.body, props: {
    rows, columns: [{ key: 'title', label: '任务名称' }, { key: 'quantity', label: '需求数量' }],
    errors: [{ row: 15, message: '需求数量过大', fields: ['quantity'] }, { row: 15, message: '请核对用量', fields: ['quantity'] }],
  }, global: { plugins: [ElementPlus] } })
  await flushPromises()
  expect(wrapper.text()).toContain('共 14 行，1 行有问题')
  expect(wrapper.find('[data-import-row="15"]').exists()).toBe(false)
  await wrapper.findAll('button').find(button => button.text() === '定位第 15 行')!.trigger('click')
  await flushPromises()
  expect(wrapper.get('[data-import-row="15"][data-import-field="quantity"]').element).toBe(document.activeElement)
  expect(scroll).toHaveBeenCalled()
  await wrapper.get('input[type=checkbox]').setValue(true)
  await flushPromises()
  const cells = wrapper.findAll('[data-import-row]')
  expect(cells).toHaveLength(2)
  expect(cells.every(cell => cell.attributes('data-import-row') === '15')).toBe(true)
  expect(wrapper.get('[data-import-field="quantity"]').classes()).toContain('error-cell')
  expect(wrapper.get('[data-import-field="title"]').classes()).not.toContain('error-cell')
  await wrapper.setProps({ rows: [rows[0]!], errors: [] })
  expect(wrapper.text()).toContain('共 1 行，0 行有问题')
  expect(wrapper.findAll('[data-import-row="2"]')).toHaveLength(2)
  wrapper.unmount()
})

it('错误文件下载使用服务端生成内容，并显示已校验的人员匹配结果', async () => {
  const create = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:errors')
  const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
  const wrapper = mount(ImportFeedback, { props: {
    rows: [{ row: 2, data: { assignee: '张工' }, matches: { assignee: '张工（zhang）' } }],
    columns: [{ key: 'assignee', label: '执行人' }], errors: [],
    errorFile: { name: '任务待修改.xlsx', content: btoa('xlsx-test') },
  }, global: { plugins: [ElementPlus] } })
  await flushPromises()
  expect(wrapper.text()).toContain('已对应：张工（zhang）')
  await wrapper.findAll('button').find(button => button.text() === '下载标注错误的 Excel')!.trigger('click')
  expect(create).toHaveBeenCalledWith(expect.any(Blob))
  expect(click).toHaveBeenCalledOnce()
  wrapper.unmount()
})

it('大批量错误紧随汇总显示，文件修改说明放在错误之后', async () => {
  const rows = Array.from({ length: 120 }, (_, index) => ({ row: index + 2, data: { name: '滑块' } }))
  const wrapper = mount(ImportFeedback, { props: {
    rows, columns: [{ key: 'name', label: '物料名称' }],
    errors: rows.map(row => ({ row: row.row, message: '产品编码类别不正确' })),
    errorFile: { name: 'BOM待修改.xlsx', content: btoa('xlsx-test') },
  }, global: { plugins: [ElementPlus], stubs: { ElTable: { template: '<div />' } } } })
  await flushPromises()
  const errors = wrapper.get('.import-errors')
  expect(errors.text()).toContain('第 121 行：产品编码类别不正确')
  expect(errors.element.previousElementSibling).toBe(wrapper.get('.feedback-toolbar').element)
  expect(errors.element.nextElementSibling?.textContent).toContain('红色单元格的批注')
  wrapper.unmount()
})
