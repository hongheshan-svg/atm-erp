import { beforeEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createRouter, createMemoryHistory } from 'vue-router'
import ProjectPage from './ProjectPage.vue'
import { read } from '../api'
import { money, user } from '../session'
import { confirmFormNavigation } from '../form-experience'
vi.mock('../api', () => ({ read: vi.fn() }))
vi.mock('../form-experience', async importOriginal => ({
  ...(await importOriginal<typeof import('../form-experience')>()),
  confirmFormNavigation: vi.fn(async () => true),
}))
// Only the permission gates are faked; the rest of the session (and the whole module registry) stays real.
vi.mock('../session', async importOriginal => ({
  ...(await importOriginal<typeof import('../session')>()),
  money: vi.fn(() => true),
  purchaseReader: () => false,
  productionProject: () => false,
}))
const project = {
  id: 7, code: 'PRJ-7', name: '自动装配线', customer_name: '客户甲', manager_name: '张经理', status: 'active',
  equipment_quantity: 12, due_date: '2099-12-20', warranty_months: 12, contract_amount: '2860000.00',
  requirements: '第一行需求说明\n第二行需求说明',
}
// 子页签桩把每个具名插槽都渲染出来，便于检查页签内的入口。
const ModuleTabsSlots = { props: ['tabs'], template: '<div><template v-for="item in tabs" :key="item.key"><slot :name="item.key" /></template></div>' }
async function render(path = '/projects/7', slots = false) {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/projects/:id', component: { template: '<div />' } }, { path: '/:pathMatch(.*)*', component: { template: '<div />' } }] })
  await router.push(path)
  await router.isReady()
  const wrapper = mount(ProjectPage, {
    global: {
      plugins: [ElementPlus, router],
      stubs: { ProcessSteps: true, ProjectAttention: true, ProjectReadiness: true, FinanceTotals: true, ModuleTabs: slots ? ModuleTabsSlots : true, ResourcePanel: true, BOMDemand: true, BudgetPanel: true, ActionDialog: true, ProjectMilestones: true, ProjectTaskSupervisors: true },
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
  sessionStorage.clear()
  user.value = null
  vi.mocked(read).mockResolvedValue(project)
  vi.mocked(money).mockReturnValue(true)
})
it('collapses the overview by default and keeps the flow bar plus a one-line summary', async () => {
  const wrapper = await render()
  expect(wrapper.find('.project-summary').isVisible()).toBe(false)
  // The flow bar is the status backbone and never collapses with the overview.
  expect(wrapper.find('.project-flow').isVisible()).toBe(true)
  expect(wrapper.find('.project-brief').text()).toBe('12 台 · 交期 2099-12-20 · 合同 ¥ 2,860,000.00')
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
  expect(brief).toBe('12 台 · 交期 2099-12-20')
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
it('主项目页签经过统一未保存表单守卫，拒绝离开时保留当前页签', async () => {
  const wrapper = await render()
  vi.mocked(confirmFormNavigation).mockResolvedValueOnce(false)
  await wrapper.get('#tab-bom').trigger('click')
  await flushPromises()
  expect(confirmFormNavigation).toHaveBeenCalled()
  expect(wrapper.get('#tab-tasks').attributes('aria-selected')).toBe('true')
  vi.mocked(confirmFormNavigation).mockResolvedValueOnce(true)
  await wrapper.get('#tab-bom').trigger('click')
  await flushPromises()
  expect(wrapper.get('#tab-bom').attributes('aria-selected')).toBe('true')
  wrapper.unmount()
})
it('项目经理在页头一行看到流程步骤和推进检查，其他角色不请求推进检查', async () => {
  user.value = { id: 1, roles: ['manager'] }
  const wrapper = await render()
  expect(wrapper.findComponent({ name: 'ProcessSteps' }).props('inline')).toBe(true)
  expect(wrapper.findComponent({ name: 'ProjectReadiness' }).exists()).toBe(true)
  wrapper.unmount()
  user.value = { id: 2, roles: ['mechanical_engineer'] }
  const engineer = await render()
  expect(engineer.findComponent({ name: 'ProjectReadiness' }).exists()).toBe(false)
  engineer.unmount()
})
it('成本页不再拆子页签，预算面板带合同金额以显示毛利指标带', async () => {
  const wrapper = await render('/projects/7?tab=cost')
  const panel = wrapper.findComponent({ name: 'BudgetPanel' })
  expect(panel.props('contract')).toBe('2860000.00')
  expect(wrapper.text()).not.toContain('实际成本')
  expect(wrapper.findAllComponents({ name: 'ModuleTabs' })).toHaveLength(0)
  wrapper.unmount()
})
it('交付页签内可直接登记发货，空状态说明发货后的安排而不是让经理找同事', async () => {
  user.value = { id: 1, roles: ['manager'] }
  const wrapper = await render('/projects/7?tab=deliveries', true)
  expect(wrapper.find('.tab-actions').text()).toContain('登记发货')
  const panel = wrapper.findAllComponents({ name: 'ResourcePanel' }).find(item => item.attributes('resource') === 'deliveries' || item.props?.('resource') === 'deliveries')!
  expect(String(panel.attributes('empty-hint') ?? panel.props?.('emptyHint'))).toContain('每批发货会自动生成安装和验收任务')
  wrapper.unmount()
  user.value = { id: 3, roles: ['finance'] }
  const reader = await render('/projects/7?tab=deliveries', true)
  expect(reader.find('.tab-actions').exists()).toBe(false)
  reader.unmount()
})
it('收付款页签顶部显示项目款项汇总', async () => {
  const wrapper = await render('/projects/7?tab=finance')
  const totals = wrapper.findComponent({ name: 'FinanceTotals' })
  expect(totals.exists()).toBe(true)
  expect(totals.attributes('project')).toBeDefined()
  wrapper.unmount()
})
it('交期已过在页头和概览标红，无销售合同、未签约不再显示 ¥ 0.00', async () => {
  vi.mocked(read).mockResolvedValue({ ...project, due_date: '2020-01-01', contract_amount: '0.00', has_sale: false })
  const wrapper = await render()
  const brief = wrapper.get('.project-brief')
  expect(brief.text()).toMatch(/^12 台 · 交期 2020-01-01 已逾期 \d+ 天 · 无销售合同$/)
  expect(brief.get('.project-late').text()).toContain('已逾期')
  await button(wrapper, '展开项目概览').trigger('click')
  expect(wrapper.get('.project-summary').text()).toContain('无销售合同')
  expect(wrapper.get('.project-summary span.project-late').text()).toMatch(/已逾期 \d+ 天/)
  wrapper.unmount()
  localStorage.clear()
  vi.mocked(read).mockResolvedValue({ ...project, status: 'warranty', due_date: '2020-01-01', contract_amount: '0.00', has_sale: true })
  const unsigned = await render()
  expect(unsigned.get('.project-brief').text()).toBe('12 台 · 交期 2020-01-01 · 合同 未签约')
  expect(unsigned.find('.project-brief .project-late').exists()).toBe(false)
  unsigned.unmount()
})
it('概览列出项目成员，能编辑项目的人可直接管理成员', async () => {
  user.value = { id: 1, roles: ['manager'] }
  vi.mocked(read).mockResolvedValue({ ...project, can_manage: true, member_names: ['李工', '王工'] })
  const wrapper = await render()
  await button(wrapper, '展开项目概览').trigger('click')
  const members = wrapper.get('.project-members')
  expect(members.text()).toContain('项目成员（2）')
  expect(members.text()).toContain('李工 · 王工')
  expect(members.findAll('button').map(item => item.text())).toEqual(['管理成员'])
  wrapper.unmount()
  user.value = { id: 2, roles: ['mechanical_engineer'] }
  vi.mocked(read).mockResolvedValue({ ...project, member_names: [] })
  const engineer = await render()
  expect(engineer.get('.project-members').text()).toContain('尚未添加成员')
  expect(engineer.get('.project-members').findAll('button')).toHaveLength(0)
  engineer.unmount()
})
it('需求说明只有一行时不显示「展开全文」', async () => {
  vi.mocked(read).mockResolvedValue({ ...project, requirements: '节拍 ≤ 45s/模组' })
  const wrapper = await render()
  await button(wrapper, '展开项目概览').trigger('click')
  await flushPromises()
  expect(wrapper.find('.requirement-text').text()).toBe('节拍 ≤ 45s/模组')
  expect(wrapper.find('.requirement-toggle').exists()).toBe(false)
  wrapper.unmount()
})
it('已结项、已取消的项目不再显示待办条，改为一行结项说明', async () => {
  vi.mocked(read).mockResolvedValue({ ...project, status: 'closed', close_reason: '全部履约并结清' })
  const wrapper = await render()
  expect(wrapper.findComponent({ name: 'ProjectAttention' }).exists()).toBe(false)
  expect(wrapper.get('.project-finished').text()).toBe('已结项：全部履约并结清')
  wrapper.unmount()
})
