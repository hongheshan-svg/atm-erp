import { beforeEach, describe, it, expect, vi } from 'vitest'
import { reactive } from 'vue'
import { shallowMount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import ResourcePanel from './ResourcePanel.vue'
import { user } from '../session'
import { read } from '../api'
import { pageSize, setPageSize } from '../pagination'
import ListPagination from './ListPagination.vue'
import TransferTools from './TransferTools.vue'
const route = reactive<{ query: { search?: string } }>({ query: {} })
vi.mock('vue-router', () => ({ useRoute: () => route, useRouter: () => ({ replace: vi.fn() }) }))

vi.mock('../api', () => ({
  read: vi.fn().mockResolvedValue({ count: 0, results: [] }),
  all: vi.fn().mockResolvedValue([]),
  write: vi.fn(),
  download: vi.fn(),
}))

describe('列表创建入口', () => {
  beforeEach(() => { route.query = {}; sessionStorage.clear(); vi.clearAllMocks() })
  it('工作台销售链接优先使用单号筛选，同页切换链接重新查询，分页保留已提交搜索', async () => {
    user.value = { id: 8, role: 'sales_manager' }
    sessionStorage.setItem('resource-search-8-sales-{}', '原来搜索')
    route.query.search = 'SALE-ONE'
    const wrapper = shallowMount(ResourcePanel, { props: { resource: 'sales', title: '销售订单' }, global: { plugins: [ElementPlus], renderStubDefaultSlot: true, stubs: { RouterLink: true, ElTable: { template: '<div />' } } } })
    await flushPromises()
    expect(wrapper.get('input[type="search"]').element).toHaveProperty('value', 'SALE-ONE')
    expect(read).toHaveBeenLastCalledWith('/business/sales/', { page: 1, page_size: pageSize.value, search: 'SALE-ONE' })
    route.query.search = 'SALE-TWO'
    await flushPromises()
    expect(wrapper.get('input[type="search"]').element).toHaveProperty('value', 'SALE-TWO')
    expect(read).toHaveBeenLastCalledWith('/business/sales/', { page: 1, page_size: pageSize.value, search: 'SALE-TWO' })
    await wrapper.get('input[type="search"]').setValue('手工筛选')
    await wrapper.get('form').trigger('submit')
    setPageSize(20)
    await flushPromises()
    expect(read).toHaveBeenLastCalledWith('/business/sales/', { page: 1, page_size: 20, search: '手工筛选' })
    wrapper.unmount()
    setPageSize(10)
  })
  it('状态筛选从第一页查询，分页和导出沿用同一筛选', async () => {
    user.value = { role: 'admin' }
    const wrapper = shallowMount(ResourcePanel, { props: { resource: 'sales', title: '销售订单' }, global: { plugins: [ElementPlus], renderStubDefaultSlot: true, stubs: { RouterLink: true, ElTable: { template: '<div />' } } } })
    await flushPromises()
    wrapper.findComponent(ListPagination).vm.$emit('change', 3)
    await flushPromises()
    await wrapper.findAll('.resource-status-tabs button').find(button => button.text() === '已报价')!.trigger('click')
    await flushPromises()
    expect(read).toHaveBeenLastCalledWith('/business/sales/', { status: 'quoted', page: 1, page_size: pageSize.value, search: '' })
    expect(wrapper.findComponent(TransferTools).props('params')).toEqual({ status: 'quoted', search: '' })
    wrapper.findComponent(ListPagination).vm.$emit('change', 2)
    await flushPromises()
    expect(read).toHaveBeenLastCalledWith('/business/sales/', { status: 'quoted', page: 2, page_size: pageSize.value, search: '' })
    wrapper.unmount()
  })
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
