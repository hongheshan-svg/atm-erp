import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { defineComponent, ref } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import ElementPlus, { ElMessageBox } from 'element-plus'
import ModulePage from './ModulePage.vue'
import ActionDialog from './ActionDialog.vue'
import RemoteSelect from './RemoteSelect.vue'
import { read } from '../api'
import { user } from '../session'
import { draftKey, loadDraft } from '../form-experience'
import type { Command } from '../types'

vi.mock('../api', () => ({ read: vi.fn(), write: vi.fn(), all: vi.fn(), download: vi.fn(), readBlob: vi.fn() }))
const command: Command = { title: '登记费用', path: '/business/entries/expense/', initial: { project: 7 }, fields: [{ key: 'note', label: '说明', type: 'textarea' }] }
let unmount: (() => void) | undefined
async function render(path: string, editing = false) {
  const screen = defineComponent({
    components: { ModulePage, ActionDialog },
    setup: () => ({ command: ref(editing ? command : null) }),
    template: '<ModulePage title="收付款" project-filter v-slot="{ projectId }"><output>{{ projectId || "all" }}</output><ActionDialog inline :command="command" /></ModulePage>',
  })
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/finance', component: screen }] })
  await router.push(path)
  const wrapper = mount({ template: '<router-view />' }, { global: { plugins: [ElementPlus, router], stubs: { RemoteSelect: true } } })
  unmount = () => wrapper.unmount()
  await flushPromises()
  return { wrapper, router }
}
beforeEach(() => {
  vi.clearAllMocks()
  sessionStorage.clear()
  user.value = { id: 9, roles: ['finance'] }
  vi.mocked(read).mockImplementation(async path => ({ id: Number(path.split('/').at(-2)), name: '测试项目' }))
})
afterEach(() => { unmount?.(); unmount = undefined; vi.restoreAllMocks() })

it('同页结果链接同步项目筛选，all 清除范围，浏览器返回恢复上一项目', async () => {
  sessionStorage.setItem('module-project-9-收付款', '3')
  const confirm = vi.spyOn(ElMessageBox, 'confirm')
  const { wrapper, router } = await render('/finance?section=entries&project=all')
  expect(wrapper.findComponent(RemoteSelect).props('commitOnSelect')).toBe(true)
  expect(wrapper.get('output').text()).toBe('all')
  await router.push('/finance?section=payments&resource=payments&focus=25&project=7')
  await flushPromises()
  expect(wrapper.get('output').text()).toBe('7')
  expect(wrapper.findComponent(RemoteSelect).props('modelValue')).toBe(7)
  expect(read).toHaveBeenCalledWith('/business/projects/7/')
  expect(router.currentRoute.value.query.focus).toBe('25')
  await router.push('/finance?section=payments&project=all')
  await flushPromises()
  expect(wrapper.get('output').text()).toBe('all')
  expect(sessionStorage.getItem('module-project-9-收付款')).toBeNull()
  router.back()
  await flushPromises()
  expect(wrapper.get('output').text()).toBe('7')
  expect(confirm).not.toHaveBeenCalled()
})

it('切项目由路由守卫确认一次：拒绝保持原状态，接受暂存后清掉旧 focus 与 resource', async () => {
  const confirm = vi.spyOn(ElMessageBox, 'confirm').mockRejectedValueOnce('cancel').mockResolvedValue('confirm' as Awaited<ReturnType<typeof ElMessageBox.confirm>>)
  const { wrapper, router } = await render('/finance?section=entries&project=7&resource=entries&focus=11', true)
  await wrapper.get('textarea[aria-label="说明"]').setValue('甲项目待提交内容')
  wrapper.findComponent(RemoteSelect).vm.$emit('update:modelValue', 8)
  await flushPromises()
  expect(confirm).toHaveBeenCalledTimes(1)
  expect(wrapper.get('output').text()).toBe('7')
  expect(router.currentRoute.value.query).toEqual({ section: 'entries', project: '7', resource: 'entries', focus: '11' })
  expect((wrapper.get('textarea[aria-label="说明"]').element as HTMLTextAreaElement).value).toBe('甲项目待提交内容')
  wrapper.findComponent(RemoteSelect).vm.$emit('update:modelValue', 8)
  await flushPromises()
  expect(confirm).toHaveBeenCalledTimes(2)
  expect(wrapper.get('output').text()).toBe('8')
  expect(router.currentRoute.value.query).toEqual({ section: 'entries', project: '8' })
  expect(loadDraft(draftKey(command, 9), command)?.note).toBe('甲项目待提交内容')
})

it('清除项目筛选写入 all，并清除旧详情定位', async () => {
  const { wrapper, router } = await render('/finance?section=payments&project=7&resource=payments&focus=25')
  wrapper.findComponent(RemoteSelect).vm.$emit('update:modelValue', '')
  await flushPromises()
  expect(router.currentRoute.value.query).toEqual({ section: 'payments', project: 'all' })
  expect(wrapper.get('output').text()).toBe('all')
})
