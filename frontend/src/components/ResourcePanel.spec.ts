import { describe, it, expect, vi } from 'vitest'
import { shallowMount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import ResourcePanel from './ResourcePanel.vue'
import { user } from '../session'

vi.mock('../api', () => ({
  read: vi.fn().mockResolvedValue({ count: 0, results: [] }),
  all: vi.fn().mockResolvedValue([]),
  write: vi.fn(),
  download: vi.fn(),
}))

describe('列表创建入口', () => {
  it('有权限时默认显示新建；项目状态禁止时才隐藏；普通成员没有创建权限', async () => {
    user.value = { role: 'manager' }
    const wrapper = shallowMount(ResourcePanel, {
      props: { resource: 'projects', title: '项目' },
      global: { plugins: [ElementPlus], renderStubDefaultSlot: true, stubs: { ElTable: { template: '<div />' } } },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('新建项目')
    await wrapper.setProps({ allowCreate: false })
    expect(wrapper.text()).not.toContain('新建项目')
    await wrapper.setProps({ allowCreate: true })
    user.value = { role: 'member' }
    await flushPromises()
    expect(wrapper.text()).not.toContain('新建项目')
    wrapper.unmount()
  })
})
