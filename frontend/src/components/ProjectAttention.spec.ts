import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import ElementPlus from 'element-plus'
import ProjectAttention from './ProjectAttention.vue'
import { user } from '../session'
import { read } from '../api'
vi.mock('../api', () => ({ read: vi.fn() }))
let cleanup: (() => void) | undefined
async function render() {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/:pathMatch(.*)*', component: { template: '<div />' } }] })
  const wrapper = mount(ProjectAttention, { attachTo: document.body, props: { project: { id: 7, can_manage: false }, revision: 1 }, global: { plugins: [ElementPlus, router] } })
  cleanup = () => wrapper.unmount()
  await flushPromises()
  return wrapper
}
beforeEach(() => {
  vi.clearAllMocks()
  vi.stubGlobal('innerWidth', 1440)
  user.value = { id: 9, roles: ['mechanical_engineer'] }
  vi.mocked(read).mockImplementation(async (path, params) => path.endsWith('/demand/')
    ? { lines: [{ bom_line: 1, item: 5, shortage: '1' }, { bom_line: 2, item: 5, shortage: '2' }, { bom_line: 3, shortage: '0' }] }
    : { count: params?.kind === 'acceptance' ? 1 : 3, results: [] })
})
afterEach(() => { cleanup?.(); cleanup = undefined; vi.unstubAllGlobals() })
it('工程师摘要仅查询当前项目技术事项，缺料按稳定明细行计数而非物料合并', async () => {
  const wrapper = await render()
  expect(read).toHaveBeenCalledWith('/business/tasks/', { project: 7, status: 'open', page_size: 1 })
  expect(read).toHaveBeenCalledWith('/business/projects/7/demand/')
  expect(vi.mocked(read).mock.calls.some(([path]) => /purchases|finance|cost|entries/.test(path))).toBe(false)
  expect(wrapper.findAll('a').map(link => link.text())).toEqual(['未完成任务3 项', '缺料明细2 行', '待验收任务1 项'])
  expect(wrapper.get('.attention-details').isVisible()).toBe(true)
  expect(wrapper.find('.attention-toggle').exists()).toBe(false)
  expect(wrapper.findAll('a')[0]!.attributes('href')).toBe('/projects/7?tab=tasks&section=tasks&attention=open-tasks')
})
it('手机默认紧凑摘要，明确展开收起入口保留六类事项和项目链接，不重复查询', async () => {
  vi.stubGlobal('innerWidth', 390)
  user.value = { roles: ['admin'] }
  const wrapper = await render()
  const button = wrapper.get('.attention-toggle')
  expect(button.text()).toBe('展开项目待办')
  expect(button.attributes('aria-expanded')).toBe('false')
  expect(button.attributes('aria-controls')).toBe(wrapper.get('.attention-details').attributes('id'))
  expect(wrapper.get('.attention-details').isVisible()).toBe(false)
  expect(wrapper.get('.compact-summary').text()).toBe('任务 3 项 · 缺料 2 行 · 验收 1 项')
  expect(wrapper.get('.compact-hint').text()).toContain('展开项目待办”查看 6 类事项及入口')
  const calls = vi.mocked(read).mock.calls.length
  await button.trigger('click')
  expect(button.text()).toBe('收起项目待办')
  expect(button.attributes('aria-expanded')).toBe('true')
  expect(wrapper.findAll('a')).toHaveLength(6)
  expect(wrapper.findAll('a').every(link => link.isVisible() && link.attributes('href')?.startsWith('/projects/7?'))).toBe(true)
  await button.trigger('click')
  expect(wrapper.get('.attention-details').isVisible()).toBe(false)
  expect(read).toHaveBeenCalledTimes(calls)
})
it('手机收起后切换桌面宽度仍完整展开', async () => {
  vi.stubGlobal('innerWidth', 390)
  const wrapper = await render()
  expect(wrapper.get('.attention-details').isVisible()).toBe(false)
  vi.stubGlobal('innerWidth', 1440)
  window.dispatchEvent(new Event('resize'))
  await flushPromises()
  expect(wrapper.get('.attention-details').isVisible()).toBe(true)
  expect(wrapper.find('.attention-toggle').exists()).toBe(false)
})
it('手机收起时也提示摘要加载失败，不把未知缺料数量显示为零', async () => {
  vi.stubGlobal('innerWidth', 390)
  vi.mocked(read).mockImplementation(async path => { if (path.endsWith('/demand/')) throw new Error('读取缺料失败'); return { count: 4 } })
  const wrapper = await render()
  expect(wrapper.get('.compact-error').isVisible()).toBe(true)
  expect(wrapper.get('.compact-summary').text()).toContain('缺料 — 行')
  await wrapper.get('.attention-toggle').trigger('click')
  expect(wrapper.get('[role="alert"]').text()).toContain('读取缺料失败')
})
it('兼采购增加收货进度；兼采购经理才增加待批准，链接继续携带项目与状态', async () => {
  user.value = { roles: ['mechanical_engineer', 'purchaser'] }
  const wrapper = await render()
  expect(wrapper.text()).toContain('待收货采购')
  expect(wrapper.text()).not.toContain('待批准采购')
  user.value = { roles: ['mechanical_engineer', 'purchase_manager'] }
  await flushPromises()
  expect(read).toHaveBeenCalledWith('/business/purchases/', { project: 7, status: 'submitted', page_size: 1 })
  expect(wrapper.findAll('a').find(link => link.text().includes('待批准采购'))!.attributes('href')).toBe('/projects/7?tab=purchases&attention=submitted')
  expect(wrapper.text()).not.toContain('金额')
})
it('失败显示未加载和错误，不把失败伪装成零，其他摘要继续显示', async () => {
  vi.mocked(read).mockImplementation(async path => { if (path.endsWith('/demand/')) throw new Error('读取缺料失败'); return { count: 4 } })
  const wrapper = await render()
  expect(wrapper.get('[role="alert"]').text()).toContain('读取缺料失败')
  expect(wrapper.findAll('a').map(link => link.text())).toEqual(['未完成任务4 项', '缺料明细— 行', '待验收任务4 项'])
})
it('项目切换期间过期请求不能覆盖新项目摘要', async () => {
  const finish: (() => void)[] = []
  vi.mocked(read).mockImplementation((path, params) => (path.includes('/7/') || params?.project === 7) ? new Promise(resolve => { finish.push(() => resolve(path.endsWith('/demand/') ? { lines: [{ shortage: 999 }] } : { count: 999 })) }) : Promise.resolve(path.endsWith('/demand/') ? { lines: [] } : { count: 8 }))
  const wrapper = await render()
  await wrapper.setProps({ project: { id: 8 }, revision: 2 })
  await flushPromises()
  finish.forEach(resolve => resolve())
  await flushPromises()
  expect(wrapper.text()).not.toContain('999')
  expect(wrapper.findAll('a')[0]!.attributes('href')).toContain('/projects/8?')
})
