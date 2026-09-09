import { describe, it, expect, vi } from 'vitest'
import { shallowMount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import ResourcePanel from './ResourcePanel.vue'
import { user } from '../session'
import { read } from '../api'
import { pageSize, setPageSize } from '../pagination'
import ListPagination from './ListPagination.vue'
vi.mock('vue-router', () => ({ useRoute: () => ({ query: {} }), useRouter: () => ({ replace: vi.fn() }) }))

vi.mock('../api', () => ({
  read: vi.fn().mockResolvedValue({ count: 0, results: [] }),
  all: vi.fn().mockResolvedValue([]),
  write: vi.fn(),
  download: vi.fn(),
}))

describe('列表创建入口', () => {
  it('改变统一每页数量回到第一页并持久化，翻页请求保留数量', async () => {
    const values = new Map<string, string>()
    vi.stubGlobal('localStorage', { getItem: (key: string) => values.get(key) ?? null, setItem: (key: string, value: string) => values.set(key, value) })
    user.value = { role: 'admin' }
    setPageSize(10)
    const wrapper = shallowMount(ResourcePanel, { props: { resource: 'projects', title: '项目' }, global: { plugins: [ElementPlus], stubs: { RouterLink: true, ElTable: { template: '<div />' } } } })
    await flushPromises()
    wrapper.findComponent(ListPagination).vm.$emit('change', 3)
    await flushPromises()
    expect(read).toHaveBeenLastCalledWith('/business/projects/', { page: 3, page_size: 10, search: '' })
    await wrapper.setProps({ revision: 1 })
    await flushPromises()
    expect(read).toHaveBeenLastCalledWith('/business/projects/', { page: 3, page_size: 10, search: '' })
    setPageSize(20)
    await flushPromises()
    expect(read).toHaveBeenLastCalledWith('/business/projects/', { page: 1, page_size: 20, search: '' })
    expect(window.localStorage.getItem('erp.page-size')).toBe('20')
    setPageSize(999)
    expect(pageSize.value).toBe(20)
    wrapper.unmount()
    setPageSize(10)
  })
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
