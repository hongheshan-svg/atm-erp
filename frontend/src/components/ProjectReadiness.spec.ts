import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import ProjectReadiness from './ProjectReadiness.vue'
import { read } from '../api'
vi.mock('../api', () => ({ read: vi.fn() }))
const RouterLink = { props: ['to'], template: '<a :href="to"><slot /></a>' }
function render(project = { id: 81, status: 'active' }) {
  return mount(ProjectReadiness, { props: { project, revision: 1 }, global: { plugins: [ElementPlus], stubs: { RouterLink } } })
}
beforeEach(() => vi.clearAllMocks())
afterEach(() => vi.unstubAllGlobals())
it('发货前一次列出全部缺项并可跳到对应阶段，应收逾期只作提示', async () => {
  vi.mocked(read).mockResolvedValue({ status: 'active', ship: [
    { key: 'stage_design', ok: true, label: '设计阶段', detail: '已完成 6 / 6', blocking: true, target: { tab: 'tasks', phase: 'design' } },
    { key: 'stage_assembly', ok: false, label: '装配阶段', detail: '已完成 0 / 2', blocking: true, target: { tab: 'tasks', phase: 'assembly' } },
    { key: 'bom', ok: false, label: '设备 BOM', detail: '尚未登记 BOM', blocking: true, target: { tab: 'bom' } },
    { key: 'receivable', ok: false, label: '应收状态', detail: '其中已逾期 1 笔', blocking: false, target: { tab: 'finance' } },
  ], accept: [], close: [] })
  const wrapper = render(); await flushPromises()
  expect(read).toHaveBeenCalledWith('/business/projects/81/readiness/')
  expect(wrapper.text()).toContain('发货前还差')
  const links = wrapper.findAll('a').map(link => [link.text(), link.attributes('href')])
  expect(links).toEqual([
    ['装配阶段 · 已完成 0 / 2', '/projects/81?tab=tasks&section=tasks&phase=assembly'],
    ['设备 BOM · 尚未登记 BOM', '/projects/81?tab=bom'],
    ['应收状态 · 其中已逾期 1 笔', '/projects/81?tab=finance'],
  ])
  expect(wrapper.findAll('button').some(button => button.text() === '登记发货')).toBe(false)
  await wrapper.get('.readiness-toggle').trigger('click')
  expect(wrapper.findAll('.readiness-list li')).toHaveLength(4)
  expect(wrapper.get('.readiness-list').text()).toContain('已满足')
})
it('条件满足时直接给出登记发货或结项主按钮', async () => {
  vi.mocked(read).mockResolvedValue({ status: 'warranty', ship: [], accept: [], close: [
    { key: 'tasks', ok: true, label: '任务全部完成或取消', detail: '全部任务已结束', blocking: true, target: { tab: 'tasks' } },
  ] })
  const wrapper = render({ id: 37, status: 'warranty' }); await flushPromises()
  expect(wrapper.text()).toContain('结项条件已满足')
  await wrapper.findAll('button').find(button => button.text() === '结项')!.trigger('click')
  expect(wrapper.emitted('act')).toEqual([['结项']])
})
it('接口异常或返回格式不符时不渲染检查，也不报脚本错误', async () => {
  vi.mocked(read).mockResolvedValue({ id: 81, name: '不是推进检查' })
  const wrapper = render(); await flushPromises()
  expect(wrapper.find('.project-readiness').exists()).toBe(false)
  vi.mocked(read).mockRejectedValue(new Error('没有权限'))
  const failed = render(); await flushPromises()
  expect(failed.get('[role="alert"]').text()).toContain('没有权限')
})
it('手机默认一行「发货前还差 N 项」，展开后才列出缺项和全部检查', async () => {
  vi.stubGlobal('innerWidth', 390)
  vi.mocked(read).mockResolvedValue({ status: 'active', ship: [
    { key: 'stage_assembly', ok: false, label: '装配阶段', detail: '已完成 0 / 2', blocking: true, target: { tab: 'tasks', phase: 'assembly' } },
    { key: 'bom', ok: false, label: '设备 BOM', detail: '尚未登记 BOM', blocking: true, target: { tab: 'bom' } },
    { key: 'receivable', ok: false, label: '应收状态', detail: '其中已逾期 1 笔', blocking: false, target: { tab: 'finance' } },
  ], accept: [], close: [] })
  const wrapper = render(); await flushPromises()
  expect(wrapper.get('.readiness-blocked').text()).toBe('发货前还差 2 项')
  expect(wrapper.get('.readiness-warning-count').text()).toBe('1 项提示')
  expect(wrapper.findAll('a')).toHaveLength(0)
  expect(wrapper.find('.readiness-toggle').exists()).toBe(false)
  const expand = wrapper.get('.readiness-expand')
  expect(expand.attributes('aria-label')).toBe('展开推进检查')
  expect(expand.attributes('aria-expanded')).toBe('false')
  await expand.trigger('click')
  expect(expand.attributes('aria-label')).toBe('收起推进检查')
  expect(wrapper.findAll('a')).toHaveLength(3)
  expect(wrapper.get('.readiness-blocked').text()).toBe('发货前还差')
  expect(wrapper.find('.readiness-toggle').exists()).toBe(true)
})
