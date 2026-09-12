import { afterEach, expect, it, vi } from 'vitest'
import { flushPromises, shallowMount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import BOMDemand from './BOMDemand.vue'
import { user } from '../session'
vi.mock('../api', () => ({ read: vi.fn().mockResolvedValue({ lines: [] }), all: vi.fn().mockResolvedValue([]), write: vi.fn(), download: vi.fn() }))
afterEach(() => { user.value = null })

it('工程师BOM维护和导入取当前项目权限，兼采购全局可读项目不扩写权限', async () => {
  user.value = { roles: ['mechanical_engineer', 'purchaser'] }
  const wrapper = shallowMount(BOMDemand, { props: { projectId: 1, status: 'active', canEditBom: false }, global: { plugins: [ElementPlus], renderStubDefaultSlot: true, stubs: { RouterLink: true, ElTable: { template: '<div />' } } } })
  await flushPromises()
  expect(wrapper.text()).not.toContain('维护 BOM')
  expect(wrapper.find('input[type="file"]').exists()).toBe(false)
  await wrapper.setProps({ canEditBom: true })
  expect(wrapper.text()).toContain('维护 BOM')
  expect(wrapper.find('input[type="file"]').exists()).toBe(true)
  await wrapper.setProps({ canEditBom: false })
  expect(wrapper.text()).not.toContain('维护 BOM')
  expect(wrapper.find('input[type="file"]').exists()).toBe(false)
  wrapper.unmount()
})
