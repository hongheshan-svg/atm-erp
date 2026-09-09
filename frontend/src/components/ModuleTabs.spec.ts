import { describe, it, expect } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import ElementPlus from 'element-plus'
import ModuleTabs from './ModuleTabs.vue'

describe('模块页签', () => {
  it('等待项目父页签导航，子页签不得把地址改回旧父页签', async () => {
    const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/project', component: { template: '<div />' } }] })
    await router.push('/project?tab=cost&section=budget')
    const wrapper = mount(ModuleTabs, {
      props: { tabs: [{ key: 'entries', label: '款项' }, { key: 'payments', label: '流水' }], storageKey: 'race-test', parentTab: 'finance' },
      global: { plugins: [router, ElementPlus] },
    })
    await flushPromises()
    expect(router.currentRoute.value.query).toEqual({ tab: 'cost', section: 'budget' })
    await router.replace('/project?tab=finance&section=budget')
    await flushPromises()
    expect(router.currentRoute.value.query).toEqual({ tab: 'finance', section: 'entries' })
    await wrapper.get('#tab-payments').trigger('keydown', { key: 'Enter' })
    await flushPromises()
    expect(router.currentRoute.value.query).toEqual({ tab: 'finance', section: 'payments' })
    await wrapper.get('#tab-entries').trigger('keydown', { key: ' ' })
    await flushPromises()
    expect(router.currentRoute.value.query.section).toBe('entries')
    wrapper.unmount()
  })
})
