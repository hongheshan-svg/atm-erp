import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import ElementPlus from 'element-plus'
import FinancePage from './FinancePage.vue'
import ResourcePanel from '../components/ResourcePanel.vue'
import ActionDialog from '../components/ActionDialog.vue'
import { all, write } from '../api'
import { actionCommand } from '../modules/finance'
import { user } from '../session'

vi.mock('../api', () => ({ read: vi.fn(async () => ({ id: 7 })), all: vi.fn(async () => []), write: vi.fn(), download: vi.fn() }))
let unmount: (() => void) | undefined
beforeEach(() => { vi.clearAllMocks(); sessionStorage.clear(); user.value = { id: 9, roles: ['finance'] } })
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

it('登记收付款选择不同对账时，界面明示默认值且实际请求按当前选项额度生成', async () => {
  vi.mocked(all).mockImplementation(async path => path.includes('reconciliations') ? [
    { id: 1, code: 'DZ1', kind: 'settlement', valid: true, remaining_amount: '300.00' },
    { id: 2, code: 'DZ2', kind: 'settlement', valid: true, remaining_amount: '120.25' },
  ] : [])
  vi.mocked(write).mockResolvedValue({ id: 18 })
  const command = await actionCommand('entries', { id: 7, project: 3, purchase: 2, balance: '500.00' }, '登记收付款')
  const wrapper = mount(ActionDialog, { props: { command }, global: { plugins: [ElementPlus], stubs: {
    ElDialog: { template: '<div><slot /></div>' }, InlineDocumentField: true, RouterLink: true,
  } } })
  unmount = () => wrapper.unmount()
  expect(wrapper.text()).toContain('本次默认 120.25')
  await wrapper.get('select[aria-label="已确认对账 / 预付款核准"]').setValue('1')
  await wrapper.get('select[aria-label="已确认对账 / 预付款核准"]').setValue('2')
  await wrapper.get('textarea[aria-label="原因 / 说明"]').setValue('按核准支付')
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(write).toHaveBeenCalledWith('/business/entries/7/pay/', expect.objectContaining({ amount: '120.25', reconciliation: 2 }), expect.any(String), 'post')
})
