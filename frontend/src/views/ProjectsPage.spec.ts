import { afterEach, expect, it } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import ProjectsPage from './ProjectsPage.vue'
import { user } from '../session'

const ResourcePanel = { name: 'ResourcePanel', props: ['resource', 'params'], template: '<div />' }
async function render(path: string) {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/:pathMatch(.*)*', component: { template: '<div />' } }] })
  await router.push(path)
  const wrapper = mount(ProjectsPage, { global: { plugins: [router], stubs: {
    ModulePage: { template: '<div><slot :revision="0" :refresh="() => {}" /></div>' },
    ModuleTabs: { template: '<div><slot name="tasks" /></div>' },
    ResourcePanel,
  } } })
  await flushPromises()
  return { wrapper, router }
}
const taskParams = (wrapper: Awaited<ReturnType<typeof render>>['wrapper']) => wrapper.findAllComponents(ResourcePanel).find(panel => panel.props('resource') === 'tasks')!.props('params')
afterEach(() => { user.value = null })

it('默认只看分配给本人的任务', async () => {
  user.value = { id: 7, roles: ['member'] }
  const { wrapper } = await render('/projects?section=tasks')
  expect(taskParams(wrapper)).toEqual({ assignee: 7 })
  expect((wrapper.get('input[type="checkbox"]').element as HTMLInputElement).checked).toBe(true)
  expect(wrapper.text()).not.toContain('只显示')
  wrapper.unmount()
})

it('工作台生产与售后派工带 mine=0 与 kinds：列出参与项目的这几类任务，可回到全部类型', async () => {
  user.value = { id: 7, roles: ['production_manager'] }
  const { wrapper, router } = await render('/projects?section=tasks&mine=0&kinds=assembly,test,install,service')
  expect(taskParams(wrapper)).toEqual({ kind__in: 'assembly,test,install,service' })
  expect((wrapper.get('input[type="checkbox"]').element as HTMLInputElement).checked).toBe(false)
  expect(wrapper.text()).toContain('只显示装配、调试、安装、售后任务')
  // 仍可再勾回「只看我的」，两种筛选叠加。
  await wrapper.get('input[type="checkbox"]').setValue(true)
  expect(taskParams(wrapper)).toEqual({ assignee: 7, kind__in: 'assembly,test,install,service' })
  await wrapper.get('input[type="checkbox"]').setValue(false)
  await router.push('/projects?section=tasks&mine=0')
  await flushPromises()
  expect(taskParams(wrapper)).toEqual({})
  expect(wrapper.text()).not.toContain('只显示')
  wrapper.unmount()
})

it('不接受格式异常的 kinds 参数', async () => {
  user.value = { id: 7, roles: ['production_manager'] }
  const { wrapper } = await render('/projects?section=tasks&mine=0&kinds=assembly;drop')
  expect(taskParams(wrapper)).toEqual({})
  wrapper.unmount()
})
