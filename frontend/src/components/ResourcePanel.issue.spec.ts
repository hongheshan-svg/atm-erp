import { beforeEach, describe, expect, it, vi } from 'vitest'
import { reactive } from 'vue'
import { flushPromises, shallowMount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import ResourcePanel from './ResourcePanel.vue'
import ActionDialog from './ActionDialog.vue'
import TransferTools from './TransferTools.vue'
import { user } from '../session'
import { all, read } from '../api'
import { batchMode } from '../batch-mode'
import type { Row } from '../types'

const route = reactive<{ query: Record<string, string> }>({ query: {} })
const push = vi.fn()
vi.mock('vue-router', () => ({ useRoute: () => route, useRouter: () => ({ replace: vi.fn(), push }) }))
vi.mock('../api', () => ({
  read: vi.fn(),
  all: vi.fn().mockResolvedValue([]),
  write: vi.fn(),
  download: vi.fn(),
}))

const stock = (id: number, quantity: string) => ({ id, item: id, item_code: `M-${id}`, item_name: `物料${id}`, location: '主仓', unit: '个', quantity })
let page: Row[] = []
function mountStocks() {
  return shallowMount(ResourcePanel, {
    props: { resource: 'stocks', title: '现有库存', allowCreate: false },
    global: { plugins: [ElementPlus], renderStubDefaultSlot: true, stubs: { BusinessTable: { template: '<div />' }, TransferTools: true } },
  })
}

describe('现有库存勾选批量领料', () => {
  beforeEach(() => {
    route.query = {}
    sessionStorage.clear()
    vi.clearAllMocks()
    batchMode.value = false
    user.value = { id: 5, roles: ['warehouse'] }
    page = [stock(1, '5.000'), stock(2, '0.000'), stock(3, '2.000')]
    vi.mocked(read).mockImplementation(async (path: string, params?: Row) => {
      if (path === '/business/stocks/' && params?.id__in) {
        const ids = String(params.id__in).split(',').map(Number)
        return { count: ids.length, results: ids.map(id => stock(id, '4.000')) }
      }
      return { count: page.length, results: page }
    })
  })

  it('只勾选有库存的行，翻页和刷新保留勾选，被领完的行自动移出', async () => {
    const wrapper = mountStocks()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.issuePicking).toBe(true)
    expect(vm.issuePage.map((row: Row) => row.id)).toEqual([1, 3])
    vm.issueBatch.togglePage(vm.issuePage)
    await flushPromises()
    expect(vm.issueSelection.map((row: Row) => row.id)).toEqual([1, 3])
    expect(wrapper.text()).toContain('已选 2 项物料')
    expect(wrapper.text()).toContain('批量领料（2）')
    // 第二页
    page = [stock(4, '1.000')]
    await vm.load(true)
    vm.issueBatch.toggle(page[0])
    expect(vm.issueSelection.map((row: Row) => row.id)).toEqual([1, 3, 4])
    // 回到第一页时，3 号已被领完：移出勾选；1 号按新数量更新。
    page = [stock(1, '2.000'), stock(3, '0.000')]
    await vm.load()
    expect(vm.issueSelection.map((row: Row) => [row.id, row.quantity])).toEqual([[1, '2.000'], [4, '1.000']])
    const clear = wrapper.findAllComponents({ name: 'ElButton' }).find(button => button.text() === '清空选择')!
    clear.vm.$emit('click')
    await flushPromises()
    expect(vm.issueSelection).toEqual([])
    expect(wrapper.text()).not.toContain('批量领料（')
    wrapper.unmount()
  })

  it('点「批量领料」打开一次提交的领料表单；成功后提示领料单号并清空勾选', async () => {
    const wrapper = mountStocks()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.issueBatch.toggle(page[0])
    vm.issueBatch.toggle(page[2])
    await flushPromises()
    wrapper.findAllComponents({ name: 'ElButton' }).find(button => button.text() === '批量领料（2）')!.vm.$emit('click')
    await flushPromises()
    expect(read).toHaveBeenCalledWith('/business/stocks/', { id__in: '1,3', page_size: 2 })
    expect(all).toHaveBeenCalledWith('/business/tasks/', { kind: 'service', status: 'open' })
    expect(vm.command.title).toBe('批量领料')
    expect(vm.command.initial.lines.map((row: Row) => row.stock)).toEqual([1, 3])
    wrapper.findComponent(ActionDialog).vm.$emit('saved', { slip: 5, slip_code: 'LL000005', moves: [8, 9], count: 2 })
    await flushPromises()
    expect(wrapper.text()).toContain('批量领料成功 · 领料单 LL000005')
    expect(vm.issueSelection).toEqual([])
    wrapper.findAllComponents({ name: 'ElButton' }).find(button => button.text() === '查看 / 打印领料单')!.vm.$emit('click')
    await flushPromises()
    expect(push).toHaveBeenCalledWith({ path: '/inventory/issue-slips/5' })
    wrapper.unmount()
  })

  it('单行领料成功也给出领料单号，不清空已勾选的批量领料', async () => {
    const wrapper = mountStocks()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.issueBatch.toggle(page[2])
    vm.command = { title: '领料', path: '/business/stocks/issue/', fields: [] }
    await flushPromises()
    wrapper.findComponent(ActionDialog).vm.$emit('saved', { id: 31, slip: 6, slip_code: 'LL000006', moves: [31], count: 1 })
    await flushPromises()
    expect(wrapper.text()).toContain('领料成功 · 领料单 LL000006')
    expect(vm.issueSelection.map((row: Row) => row.id)).toEqual([3])
    wrapper.unmount()
  })

  it('与管理员批量管理互斥；没有仓库岗位不显示勾选', async () => {
    user.value = { id: 1, roles: ['admin'] }
    batchMode.value = true
    const admin = mountStocks()
    await flushPromises()
    const vm = admin.vm as any
    expect(vm.batchVisible).toBe(true)
    expect(vm.issuePicking).toBe(false)
    batchMode.value = false
    await flushPromises()
    expect(vm.issuePicking).toBe(true)
    admin.unmount()
    user.value = { id: 2, roles: ['purchaser'] }
    const purchaser = mountStocks()
    await flushPromises()
    expect((purchaser.vm as any).issuePicking).toBe(false)
    purchaser.unmount()
  })
})

describe('领料单列表', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    user.value = { id: 5, roles: ['finance'] }
    vi.mocked(read).mockResolvedValue({ count: 0, results: [] })
  })

  it('按日期筛选，行操作直达打印页，不提供导入', async () => {
    const wrapper = shallowMount(ResourcePanel, {
      props: { resource: 'issue-slips', title: '领料单', allowCreate: false, params: { project: 7 }, projectId: 7 },
      global: { plugins: [ElementPlus], renderStubDefaultSlot: true, stubs: { RouterLink: true, BusinessTable: { template: '<div />' } } },
    })
    await flushPromises()
    const vm = wrapper.vm as any
    expect(wrapper.find('input[aria-label="开始日期"]').exists()).toBe(true)
    expect(wrapper.findComponent(TransferTools).props('allowImport')).toBe(false)
    vm.dateFrom = '2026-11-01'
    vm.search = 'LL0001'
    vm.searchRecords()
    await flushPromises()
    expect(read).toHaveBeenLastCalledWith('/business/issue-slips/', expect.objectContaining({ project: 7, date_from: '2026-11-01', search: 'LL0001' }))
    await vm.action({ id: 12 }, '查看 / 打印')
    expect(push).toHaveBeenCalledWith({ path: '/inventory/issue-slips/12' })
    wrapper.unmount()
  })

  it('手机宽度：只留单号与操作，项目、时间、物料摘要并入单号下方', async () => {
    const original = window.matchMedia
    window.matchMedia = ((query: string) => ({ matches: true, media: query, addEventListener: vi.fn(), removeEventListener: vi.fn() })) as unknown as typeof window.matchMedia
    try {
      const wrapper = shallowMount(ResourcePanel, { props: { resource: 'issue-slips', title: '领料单' }, global: { plugins: [ElementPlus], stubs: { BusinessTable: true } } })
      await flushPromises()
      const vm = wrapper.vm as any
      expect(vm.shownColumns.map((column: { key: string }) => column.key)).toEqual(['code'])
      const lines = vm.mobileSummary({ project_code: 'ATM01', created_at: '2026-11-11T02:00:00Z', items_summary: '气缸', line_count: 2, task_title: '换件', created_by_name: '王仓管' })
      expect(lines[0]).toMatch(/^ATM01 · 2026-11-11/)
      expect(lines[1]).toBe('气缸（2 行） · 换件 · 王仓管')
      wrapper.unmount()
    } finally { window.matchMedia = original }
  })
})
