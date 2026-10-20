import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import ElementPlus from 'element-plus'
import FinancePage from './FinancePage.vue'
import ResourcePanel from '../components/ResourcePanel.vue'
import { user } from '../session'

vi.mock('../api', () => ({ read: vi.fn(async () => ({ id: 7 })), all: vi.fn(async () => []) }))
let unmount: (() => void) | undefined
beforeEach(() => { sessionStorage.clear(); user.value = { id: 9, roles: ['finance'] } })
afterEach(() => { unmount?.() })
it('收付款流水与对账同时传递实际查询范围和详情项目范围，同页链接切换同步更新', async () => {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/finance', component: FinancePage }] })
  await router.push('/finance?section=payments&project=7')
  const wrapper = mount({ template: '<router-view />' }, { global: { plugins: [ElementPlus, router], stubs: {
    RemoteSelect: true, ResourcePanel: true, FinanceTotals: true, SupplierMonthly: true,
    ModuleTabs: { template: '<slot name="payments" /><slot name="reconciliations" />' },
  } } })
  unmount = () => wrapper.unmount()
  await flushPromises()
  const panels = () => wrapper.findAllComponents(ResourcePanel)
  expect(panels().map(panel => panel.props('resource'))).toEqual(['payments', 'reconciliations'])
  for (const panel of panels()) {
    expect(panel.props('params')).toEqual({ entry__project: 7 })
    expect(panel.props('projectId')).toBe(7)
  }
  await router.push('/finance?section=reconciliations&resource=reconciliations&focus=25&project=8')
  await flushPromises()
  for (const panel of panels()) {
    expect(panel.props('params')).toEqual({ entry__project: 8 })
    expect(panel.props('projectId')).toBe(8)
  }
})
