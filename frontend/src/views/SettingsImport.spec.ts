import { afterEach, expect, it } from 'vitest'
import { shallowMount, RouterLinkStub } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import SettingsPage from './SettingsPage.vue'
import TransferTools from '../components/TransferTools.vue'
import { user } from '../session'

afterEach(() => { user.value = null })
it('仅管理员初始化区提供期初批量导入，完成后提供原库存入口', async () => {
  user.value = { roles: ['admin'] }
  const wrapper = shallowMount(SettingsPage, { global: { plugins: [ElementPlus], stubs: {
    RouterLink: RouterLinkStub,
    ModuleTabs: { template: '<div><slot name="initialization" /></div>' },
  } } })
  expect(wrapper.getComponent(TransferTools).props()).toMatchObject({ resource: 'stocks', path: '/business/stocks/', allowImport: true })
  wrapper.getComponent(TransferTools).vm.$emit('changed')
  await wrapper.vm.$nextTick()
  expect(wrapper.text()).toContain('期初库存已登记')
  user.value = { roles: ['warehouse'] }
  await wrapper.vm.$nextTick()
  expect(wrapper.findComponent(TransferTools).exists()).toBe(false)
  wrapper.unmount()
})
