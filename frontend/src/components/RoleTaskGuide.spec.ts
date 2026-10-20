import { beforeEach, expect, it } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import ElementPlus from 'element-plus'
import RoleTaskGuide from './RoleTaskGuide.vue'
import { user } from '../session'

async function render(path = '/workbench') {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/:pathMatch(.*)*', component: { template: '<div />' } }] })
  await router.push(path)
  const wrapper = mount(RoleTaskGuide, { global: { plugins: [ElementPlus, router] } })
  await flushPromises()
  return wrapper
}
beforeEach(() => { localStorage.clear(); user.value = { id: 7, roles: ['mechanical_engineer'] } })
it('工程岗位只显示本人任务与工程入口，不显示采购、财务和管理设置', async () => {
  const wrapper = await render()
  expect(wrapper.findAll('a').map(link => link.attributes('href'))).toEqual(['/projects?section=tasks', '/bom'])
  for (const text of ['采购草稿', '收付款', '管理员', '安排项目执行']) expect(wrapper.text()).not.toContain(text)
  wrapper.unmount()
})
it('多角色按并集显示且共同任务只出现一次，兼采购不增加工程或项目管理职责', async () => {
  user.value = { id: 7, role: 'mechanical_engineer', roles: ['mechanical_engineer', 'electrical_engineer', 'purchaser'] }
  const wrapper = await render()
  expect(wrapper.findAll('h3').map(item => item.text())).toEqual(['处理我的任务', '编制项目用料', '从缺料开始采购'])
  expect(wrapper.text()).toContain('选择参与的项目')
  wrapper.unmount()
})
it('跳过后按账号记忆，可通过按钮或设置链接重新打开，换账号不继承', async () => {
  const wrapper = await render()
  await wrapper.get('button').trigger('click')
  expect(wrapper.findAll('li')).toHaveLength(0)
  wrapper.unmount()
  const second = await render()
  expect(second.findAll('li')).toHaveLength(0)
  await second.get('button').trigger('click')
  expect(second.findAll('li')).toHaveLength(2)
  second.unmount()
  const reopened = await render('/workbench?guide=show')
  expect(reopened.findAll('li')).toHaveLength(2)
  reopened.unmount()
  user.value = { id: 8, roles: ['finance'] }
  const other = await render()
  expect(other.text()).toContain('核对后登记收付款')
  expect(other.text()).not.toContain('编制项目用料')
  other.unmount()
})
