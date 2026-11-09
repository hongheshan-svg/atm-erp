import { beforeEach, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import ElementPlus from 'element-plus'
import TaskNotices from './TaskNotices.vue'
import { read, write } from '../api'
vi.mock('../api', () => ({ read: vi.fn(), write: vi.fn() }))
const notice = { id: 4, task: 9, project: 2, project_name: '装配线', task_title: '3D画图', message: '任务分配已调整', created_at: '2026-11-09T08:00:00Z', read_at: null }
async function render() {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/:pathMatch(.*)*', component: { template: '<div />' } }] })
  const wrapper = mount(TaskNotices, { global: { plugins: [ElementPlus, router] } })
  await flushPromises()
  return { wrapper, router }
}
beforeEach(() => { vi.resetAllMocks(); vi.mocked(read).mockResolvedValue({ count: 1, unread_count: 1, results: [notice] }); vi.mocked(write).mockResolvedValue({ id: 4 }) })
it('未读提醒点击后标记已读并直达对应任务，不完成任务', async () => {
  const { wrapper, router } = await render()
  expect(wrapper.text()).toContain('1 条未读')
  expect(wrapper.text()).toContain('装配线 · 3D画图')
  await wrapper.findAll('button').find(button => button.text() === '查看并处理')!.trigger('click')
  await flushPromises()
  expect(write).toHaveBeenCalledExactlyOnceWith('/business/task-notices/4/read/', {}, expect.any(String))
  expect(router.currentRoute.value.fullPath).toBe('/projects/2?tab=tasks&section=tasks&resource=tasks&focus=9')
  wrapper.unmount()
})
it('读取失败保留未读和错误，不误跳转；已读提醒不再写入', async () => {
  vi.mocked(write).mockRejectedValue(new Error('暂时无法保存'))
  const { wrapper, router } = await render()
  await wrapper.findAll('button').find(button => button.text() === '查看并处理')!.trigger('click')
  await flushPromises()
  expect(wrapper.text()).toContain('暂时无法保存')
  expect(router.currentRoute.value.path).toBe('/')
  vi.mocked(read).mockResolvedValue({ count: 1, unread_count: 0, results: [{ ...notice, read_at: notice.created_at }] })
  wrapper.findComponent({ name: 'ElCheckbox' }).vm.$emit('update:modelValue', false)
  await flushPromises()
  expect(read).toHaveBeenLastCalledWith('/business/task-notices/', { unread: false, page: 1, page_size: 5 })
  await wrapper.findAll('button').find(button => button.text() === '查看并处理')!.trigger('click')
  await flushPromises()
  expect(write).toHaveBeenCalledTimes(1)
  expect(router.currentRoute.value.path).toBe('/projects/2')
  wrapper.unmount()
})
