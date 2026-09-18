import { beforeEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createRouter, createMemoryHistory } from 'vue-router'
import ProjectPage from './ProjectPage.vue'
import { read } from '../api'
import { money } from '../session'
vi.mock('../api', () => ({ read: vi.fn() }))
// Only the permission gates are faked; the rest of the session (and the whole module registry) stays real.
vi.mock('../session', async importOriginal => ({
  ...(await importOriginal<typeof import('../session')>()),
  money: vi.fn(() => true),
  purchaseReader: () => false,
  productionProject: () => false,
}))
const project = {
  id: 7, code: 'PRJ-7', name: '自动装配线', customer_name: '客户甲', manager_name: '张经理', status: 'active',
  equipment_quantity: 12, due_date: '2026-12-20', warranty_months: 12, contract_amount: '2860000.00',
  requirements: '第一行需求说明\n第二行需求说明',
}
async function render() {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/projects/:id', component: { template: '<div />' } }, { path: '/:pathMatch(.*)*', component: { template: '<div />' } }] })
  await router.push('/projects/7')
  await router.isReady()
  const wrapper = mount(ProjectPage, {
    global: {
      plugins: [ElementPlus, router],
      stubs: { ProcessSteps: true, ModuleTabs: true, ResourcePanel: true, BOMDemand: true, BudgetPanel: true, ActionDialog: true },
    },
  })
  await flushPromises()
  return wrapper
}
const button = (wrapper: Awaited<ReturnType<typeof render>>, label: string) =>
  wrapper.findAll('button').find(item => item.text().includes(label))!
beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
  vi.mocked(read).mockResolvedValue(project)
  vi.mocked(money).mockReturnValue(true)
})
it('collapses the overview by default and keeps the flow bar plus a one-line summary', async () => {
  const wrapper = await render()
  expect(wrapper.find('.project-summary').isVisible()).toBe(false)
  // The flow bar is the status backbone and never collapses with the overview.
  expect(wrapper.find('.project-flow').isVisible()).toBe(true)
  expect(wrapper.find('.project-brief').text()).toBe('12 台 · 交期 2026-12-20 · 合同 ¥ 2,860,000.00')
  wrapper.unmount()
})
it('remembers an expanded overview for the next visit', async () => {
  const first = await render()
  await button(first, '展开项目概览').trigger('click')
  expect(first.find('.project-summary').isVisible()).toBe(true)
  expect(first.find('.project-brief').exists()).toBe(false)
  expect(localStorage.getItem('project-overview')).toBe('expanded')
  first.unmount()
  const second = await render()
  expect(second.find('.project-summary').isVisible()).toBe(true)
  await button(second, '收起项目概览').trigger('click')
  expect(localStorage.getItem('project-overview')).toBe('collapsed')
  second.unmount()
})
it('keeps the contract amount out of the summary without the money permission', async () => {
  vi.mocked(money).mockReturnValue(false)
  const wrapper = await render()
  const brief = wrapper.find('.project-brief').text()
  expect(brief).toBe('12 台 · 交期 2026-12-20')
  expect(brief).not.toContain('2,860,000')
  await button(wrapper, '展开项目概览').trigger('click')
  expect(wrapper.text()).not.toContain('合同金额')
  expect(wrapper.text()).not.toContain('2,860,000')
  wrapper.unmount()
})
it('shows the requirements as one line until the reader opens them', async () => {
  const wrapper = await render()
  await button(wrapper, '展开项目概览').trigger('click')
  expect(wrapper.find('.requirement-text').classes()).toContain('requirement-clamped')
  const toggle = wrapper.find('.requirement-toggle')
  expect(toggle.text()).toBe('展开全文')
  await toggle.trigger('click')
  expect(wrapper.find('.requirement-text').classes()).not.toContain('requirement-clamped')
  expect(wrapper.find('.requirement-text').text()).toContain('第二行需求说明')
  expect(wrapper.find('.requirement-toggle').text()).toBe('收起')
  await wrapper.find('.requirement-toggle').trigger('click')
  expect(wrapper.find('.requirement-text').classes()).toContain('requirement-clamped')
  wrapper.unmount()
})
