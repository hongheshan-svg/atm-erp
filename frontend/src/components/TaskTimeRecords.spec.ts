import { beforeEach, describe, expect, it, vi } from 'vitest'
import { shallowMount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import TaskTimeRecords from './TaskTimeRecords.vue'
import { read } from '../api'

vi.mock('../api', () => ({ read: vi.fn() }))
function open() {
  return shallowMount(TaskTimeRecords, { props: { taskId: 7 }, global: { plugins: [ElementPlus], renderStubDefaultSlot: true, stubs: { BusinessTable: { name: 'BusinessTable', template: '<div />' } } } })
}
describe('任务工时核对', () => {
  beforeEach(() => { vi.resetAllMocks() })
  it('整项和本人合计独立于当前页，并按本人筛选重置分页', async () => {
    vi.mocked(read).mockResolvedValue({ count: 12, results: [{ id: 12, hours: '1' }], summary: { task_title: '3D画图', logged_hours: '25.50', my_hours: '9.00' } })
    const wrapper = open()
    await flushPromises()
    expect(wrapper.text()).toContain('任务累计：25.50 小时')
    expect(wrapper.text()).toContain('我的累计：9.00 小时')
    wrapper.findComponent({ name: 'ElPagination' }).vm.$emit('current-change', 2)
    await flushPromises()
    expect(read).toHaveBeenLastCalledWith('/business/tasks/7/time-records/', { page: 2, page_size: 10, mine: 'false' })
    await wrapper.get('input[type="checkbox"]').setValue(true)
    await flushPromises()
    expect(read).toHaveBeenLastCalledWith('/business/tasks/7/time-records/', { page: 1, page_size: 10, mine: 'true' })
    wrapper.unmount()
  })
  it('加载失败显示重试，不把查询失败说成未登记', async () => {
    vi.mocked(read).mockRejectedValue(new Error('网络中断'))
    const wrapper = open()
    await flushPromises()
    expect(wrapper.findComponent({ name: 'ElAlert' }).attributes('title')).toBe('网络中断')
    expect(wrapper.findComponent({ name: 'BusinessTable' }).exists()).toBe(false)
    vi.mocked(read).mockResolvedValue({ count: 0, results: [], summary: { task_title: '3D画图', logged_hours: '0', my_hours: '0' } })
    wrapper.findAllComponents({ name: 'ElButton' }).find(button => button.text() === '重试')!.vm.$emit('click')
    await flushPromises()
    expect(wrapper.findComponent({ name: 'BusinessTable' }).attributes('empty-text')).toBe('暂无已提交的工时记录')
    wrapper.unmount()
  })
})
