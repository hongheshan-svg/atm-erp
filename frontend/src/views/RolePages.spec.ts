import { beforeEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import type { Component } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import ElementPlus from 'element-plus'
import InventoryPage from './InventoryPage.vue'
import ProjectPage from './ProjectPage.vue'
import BOMPage from './BOMPage.vue'
import SettingsPage from './SettingsPage.vue'
import ResourcePanel from '../components/ResourcePanel.vue'
import ActionDialog from '../components/ActionDialog.vue'
import { user } from '../session'
import { read } from '../api'
import { primaryActions } from '../row-actions'

vi.mock('../api', () => ({ read: vi.fn(), all: vi.fn(), write: vi.fn(), download: vi.fn() }))
const project = { id: 7, code: 'PRJ-7', name: '装配线', status: 'active', can_manage: true, equipment_quantity: 2, can_edit_bom: true }
async function render(component: Component, path: string) {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/projects/:id', component: { template: '<div />' } }, { path: '/:pathMatch(.*)*', component: { template: '<div />' } }] })
  await router.push(path)
  const wrapper = mount(component, { global: {
    plugins: [ElementPlus, router],
    stubs: { ResourcePanel: true, ActionDialog: true, ProjectAttention: true, ProcessSteps: true, BOMDemand: true, BudgetPanel: true, CodingRules: true, RemoteSelect: true },
  } })
  await flushPromises()
  return { wrapper, router }
}
beforeEach(() => {
  vi.clearAllMocks(); localStorage.clear(); sessionStorage.clear()
  user.value = { id: 11, roles: ['warehouse'] }
  vi.mocked(read).mockImplementation(async path => path.endsWith('/locations/') ? ['主仓'] : project)
})
it('库存从日常入口进入原采购收货，保留项目并覆盖部分收货状态', async () => {
  const { wrapper, router } = await render(InventoryPage, '/inventory?section=receipts&project=7')
  let panel = wrapper.findComponent(ResourcePanel)
  expect(panel.props()).toMatchObject({ resource: 'purchases', params: { project: 7, status: 'approved' }, allowCreate: false })
  await wrapper.get('[aria-label="收货进度"]').findAll('a')[1]!.trigger('click')
  await flushPromises()
  panel = wrapper.findComponent(ResourcePanel)
  expect(panel.props('params')).toEqual({ project: 7, status: 'partial' })
  await wrapper.get('[aria-label="日常库存操作"]').findAll('a')[2]!.trigger('click')
  await flushPromises()
  expect(router.currentRoute.value.query).toMatchObject({ project: '7', intent: 'return', section: 'moves' })
  expect(wrapper.findComponent(ResourcePanel).props()).toMatchObject({ resource: 'moves', params: { project: 7, kind: 'issue' } })
  expect(wrapper.text()).toContain('选择原领料流水')
  wrapper.unmount()
})
it('日常库存不显示新建期初，领料与退料成为行内主动作', async () => {
  user.value = { id: 1, roles: ['admin'] }
  const { wrapper } = await render(InventoryPage, '/inventory?section=stocks')
  expect(wrapper.findComponent(ResourcePanel).props('allowCreate')).toBe(false)
  expect(wrapper.findAll('a').some(link => link.attributes('href') === '/settings?section=initialization')).toBe(true)
  expect(primaryActions).toContain('领料')
  expect(primaryActions).toContain('退料')
  wrapper.unmount()
})
it('采购读者不获得仓管日常动作入口', async () => {
  user.value = { id: 2, roles: ['purchaser'] }
  const { wrapper } = await render(InventoryPage, '/inventory?section=receipts')
  expect(wrapper.find('[aria-label="日常库存操作"]').exists()).toBe(false)
  expect(wrapper.find('#tab-receipts').exists()).toBe(false)
  wrapper.unmount()
})
it('项目摘要进入任务和采购时带状态筛选，可清除恢复当前项目完整列表', async () => {
  user.value = { id: 1, roles: ['admin'] }
  const { wrapper, router } = await render(ProjectPage, '/projects/7?tab=tasks&section=tasks&attention=open-tasks')
  expect(wrapper.findComponent(ResourcePanel).props('params')).toEqual({ project: 7, status: 'open' })
  await router.push('/projects/7?tab=purchases&attention=submitted')
  await flushPromises()
  expect(wrapper.findComponent(ResourcePanel).props('params')).toEqual({ project: 7, status: 'submitted' })
  await wrapper.get('.attention-filter button').trigger('click')
  await flushPromises()
  expect(wrapper.findComponent(ResourcePanel).props('params')).toEqual({ project: 7 })
  expect(router.currentRoute.value.path).toBe('/projects/7')
  wrapper.unmount()
})
it('工程师直接访问采购摘要地址仍不会加载采购页签，也不获得验收按钮', async () => {
  user.value = { id: 2, roles: ['mechanical_engineer'] }
  const { wrapper, router } = await render(ProjectPage, '/projects/7?tab=purchases&attention=submitted')
  expect(wrapper.find('#tab-purchases').exists()).toBe(false)
  expect(wrapper.findAllComponents(ResourcePanel).some(panel => panel.props('resource') === 'purchases')).toBe(false)
  await router.push('/projects/7?tab=tasks&section=tasks&attention=acceptance')
  await flushPromises()
  expect(wrapper.findComponent(ResourcePanel).props('params')).toEqual({ project: 7, kind: 'acceptance', status: 'open' })
  expect(wrapper.text()).not.toContain('前往交付批次登记验收')
  wrapper.unmount()
})
it('BOM 的继续查看入口重新校验权限并切换项目上下文', async () => {
  user.value = { id: 2, roles: ['mechanical_engineer'] }
  sessionStorage.setItem('current-project-2', '7')
  const { wrapper, router } = await render(BOMPage, '/bom')
  expect(read).toHaveBeenCalledWith('/business/projects/7/')
  const link = wrapper.findAll('a').find(item => item.text().includes('继续查看当前项目'))!
  expect(link.text()).toContain('装配线')
  await link.trigger('click')
  await flushPromises()
  expect(router.currentRoute.value.query.project).toBe('7')
  expect(wrapper.findComponent({ name: 'BOMDemand' }).props('projectId')).toBe(7)
  wrapper.unmount()
})
it('BOM 不显示已失去权限的上次项目名称', async () => {
  sessionStorage.setItem('current-project-11', '7')
  vi.mocked(read).mockRejectedValue(new Error('无权限'))
  const { wrapper } = await render(BOMPage, '/bom')
  expect(wrapper.text()).not.toContain('装配线')
  expect(wrapper.text()).not.toContain('继续查看当前项目')
  wrapper.unmount()
})
it('管理员初始化复用原期初命令，完成后给出库存去向', async () => {
  user.value = { id: 1, roles: ['admin'] }
  const { wrapper } = await render(SettingsPage, '/settings?section=initialization')
  await wrapper.get('[aria-label="管理员初始化"]').findAll('button').find(button => button.text() === '期初入库')!.trigger('click')
  await flushPromises()
  const dialog = wrapper.findComponent(ActionDialog)
  expect(dialog.props('command')).toMatchObject({ title: '期初入库', path: '/business/stocks/opening/' })
  dialog.vm.$emit('saved')
  await flushPromises()
  expect(wrapper.text()).toContain('期初库存已登记')
  expect(user.value?.id).toBe(1)
  wrapper.unmount()
})
it('非管理员不能进入期初初始化；设置仍提供再次查看岗位指引', async () => {
  const { wrapper } = await render(SettingsPage, '/settings?section=initialization')
  expect(wrapper.find('[aria-label="管理员初始化"]').exists()).toBe(false)
  expect(wrapper.findAll('a').some(link => link.attributes('href') === '/workbench?guide=show')).toBe(true)
  wrapper.unmount()
})
