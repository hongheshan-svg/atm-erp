import { afterEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus, { ElTableColumn } from 'element-plus'
import { h, ref } from 'vue'
import BusinessTable from './BusinessTable.vue'
import TableScroll from './TableScroll.vue'

afterEach(() => vi.unstubAllGlobals())

it('显示分页连续序号，筛选和排序后按当前顺序重新计数，动作仍使用原记录', async () => {
  const clicked = vi.fn()
  const rows = [{ id: 133, name: '气缸' }, { id: 7, name: '滑块' }]
  const offset = ref(20), data = ref(rows)
  const wrapper = mount({ render: () => h(BusinessTable, { rowOffset: offset.value, data: data.value, rowKey: 'id', onRowClick: clicked }, { default: () => h(ElTableColumn, { prop: 'name', label: '名称' }) }) }, { global: { plugins: [ElementPlus] } })
  await flushPromises()
  const numbers = () => wrapper.findAll('td.business-row-number').map(cell => cell.text())
  expect(numbers()).toEqual(['21', '22'])
  await wrapper.get('.el-table__body tr').trigger('click')
  expect(clicked.mock.calls[0]![0].id).toBe(133)
  offset.value = 0; data.value = [rows[1]!, rows[0]!]
  await flushPromises()
  expect(numbers()).toEqual(['1', '2'])
  expect(wrapper.findAll('.el-table__body tr')[0]!.text()).toContain('滑块')
  offset.value = 100; data.value = [rows[0]!]
  await flushPromises()
  expect(numbers()).toEqual(['101'])
  wrapper.unmount()
})

it('导入预览保留文件行号，不添加容易混淆的另一套序号', async () => {
  const wrapper = mount(BusinessTable, {
    props: { numbered: false }, attrs: { data: [{ row: 133, name: '待修正物料' }] },
    slots: { default: () => h(ElTableColumn, { prop: 'row', label: '文件行号' }) }, global: { plugins: [ElementPlus] },
  })
  await flushPromises()
  expect(wrapper.text()).toContain('文件行号')
  expect(wrapper.text()).toContain('133')
  expect(wrapper.find('td.business-row-number').exists()).toBe(false)
  wrapper.unmount()
})

it('宽表显示左右按钮，到边界禁用；尺寸和内容变化后同步，不溢出时隐藏', async () => {
  const observers: { callback: () => void; disconnect: ReturnType<typeof vi.fn> }[] = []
  vi.stubGlobal('ResizeObserver', class {
    disconnect = vi.fn()
    observe = vi.fn()
    constructor(callback: () => void) { observers.push({ callback, disconnect: this.disconnect }) }
  })
  const wrapper = mount(TableScroll, { props: { label: '收货明细' }, slots: { default: '<div data-table-scroll><table><tbody><tr><td>物料</td></tr></tbody></table></div>' }, global: { plugins: [ElementPlus] } })
  const viewport = wrapper.get('[data-table-scroll]').element as HTMLElement
  let width = 400, total = 1000
  Object.defineProperties(viewport, { clientWidth: { get: () => width }, scrollWidth: { get: () => total } })
  observers[0]!.callback()
  await flushPromises()
  const left = () => wrapper.findAll('button').find(button => button.text().includes('向左查看'))!
  const right = () => wrapper.findAll('button').find(button => button.text().includes('向右查看'))!
  expect(left().attributes('disabled')).toBeDefined()
  expect(wrapper.get('[role="group"]').attributes('aria-label')).toBe('收货明细左右查看')
  await right().trigger('click')
  expect(viewport.scrollLeft).toBe(280)
  expect(left().attributes('disabled')).toBeUndefined()
  viewport.scrollLeft = 600
  await wrapper.get('[data-table-scroll]').trigger('scroll')
  expect(right().attributes('disabled')).toBeDefined()
  width = 1000; total = 1000; viewport.scrollLeft = 0
  observers[0]!.callback()
  await flushPromises()
  expect(wrapper.find('[role="group"]').exists()).toBe(false)
  expect(wrapper.classes()).not.toContain('table-scroll-narrow')
  wrapper.unmount()
  expect(observers[0]!.disconnect).toHaveBeenCalled()
})

it('序号列默认 70 宽，列多的明细表可用 numberWidth 收窄', async () => {
  const widthOf = async (props: Record<string, unknown>) => {
    const wrapper = mount({ render: () => h(BusinessTable, { data: [{ id: 1, name: '气缸' }], rowKey: 'id', ...props }, { default: () => h(ElTableColumn, { prop: 'name', label: '名称' }) }) }, { global: { plugins: [ElementPlus] } })
    await flushPromises()
    const width = wrapper.findAllComponents({ name: 'ElTableColumn' })[0]!.props('width')
    wrapper.unmount()
    return width
  }
  expect(await widthOf({})).toBe(70)
  expect(await widthOf({ numberWidth: 48 })).toBe(48)
})
