import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import ElementPlus from 'element-plus'
import MaterialTrackingTable from './MaterialTrackingTable.vue'
import { user } from '../session'
import { download, read } from '../api'
import { needText, trackingParams, trackingSummary, unitPriceText } from '../modules/material-tracking'
vi.mock('../api', () => ({ read: vi.fn(), download: vi.fn(), all: vi.fn(async () => []) }))

const motor = {
  id: '3-5', project: 3, project_code: 'A2609', project_name: '自动装配线', item: 5, item_code: '2199000045', item_name: '气缸 SC50', specification: 'SC50x100',
  in_bom: true, quantity: '6.000', status: 'incoming', status_label: '在途', shortage: '0.000', ordered: '6.000', unapproved: '0.000', incoming: '4.000', received: '2.000', issued: '0.000',
  purchase_refs: [{ id: 31, code: 'PO000032', status_label: '部分收货' }, { id: 40, code: 'PO000040', status_label: '待收货' }], purchase_codes: 'PO000032 部分收货、PO000040 待收货',
  suppliers: '亚德客', unit_prices: '88.00、92.00', amount: '540.00', due_dates: '2026-11-25、2026-12-02', recipients: '装配班 张师傅', slip_refs: [{ id: 8, code: 'LL0008' }], issue_slips: 'LL0008',
}
const extra = { ...motor, id: '3-9', item: 9, item_code: 'Z9', item_name: '扎带', in_bom: false, quantity: null, status: 'unapproved', status_label: '待批采购', shortage: '0.000', ordered: '0.000', unapproved: '10.000', purchase_refs: [], slip_refs: [], unit_prices: '1.50' }
let cleanup: (() => void) | undefined
async function render(props: Record<string, unknown> = {}) {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/:pathMatch(.*)*', component: { template: '<div />' } }] })
  const wrapper = mount(MaterialTrackingTable, { attachTo: document.body, props, global: { plugins: [ElementPlus, router] } })
  cleanup = () => wrapper.unmount()
  await flushPromises()
  return wrapper
}
function narrow(width: number) {
  vi.stubGlobal('matchMedia', (query: string) => ({ matches: width <= Number(/max-width:\s*(\d+)px/.exec(query)?.[1] ?? Infinity), addEventListener: () => {}, removeEventListener: () => {} }))
}
beforeEach(() => {
  vi.clearAllMocks()
  narrow(1440)
  user.value = { id: 2, roles: ['purchaser'] }
  vi.mocked(read).mockResolvedValue({ count: 2, results: [motor, extra] })
})
afterEach(() => { cleanup?.(); cleanup = undefined; vi.unstubAllGlobals(); user.value = null })

describe('物料跟踪展示口径', () => {
  it('不在 BOM 的物料没有需求，多次采购单价不同写「多个」', () => {
    expect(needText(motor)).toBe('6')
    expect(needText(extra)).toBe('—')
    expect(unitPriceText(motor)).toBe('多个')
    expect(unitPriceText(extra)).toBe('1.50')
    expect(unitPriceText({})).toBe('—')
    expect(trackingSummary(motor)).toBe('需求 6 · 已采购 6 · 已收 2 · 已领 0 · 缺料 0')
    expect(trackingSummary(extra)).toBe('需求 — · 已采购 0 · 待批 10 · 已收 2 · 已领 0')
  })
  it('筛选参数只带填了的项，指定项目时不再带「包括已验收、已结项」', () => {
    expect(trackingParams({ search: '气缸', status: 'shortage', partType: 'custom', supplier: 4, outsideBom: true, allProjects: true })).toEqual({ search: '气缸', status: 'shortage', part_type: 'custom', supplier: 4, outside_bom: 'true', all_projects: 'true' })
    expect(trackingParams({ allProjects: true }, 3)).toEqual({ project: 3 })
    expect(trackingParams({ supplier: '' })).toEqual({})
  })
})

describe('物料跟踪表', () => {
  it('一行列出需求、采购、到货和领料，采购单号可跳转，按状态筛选重新查询', async () => {
    const wrapper = await render()
    expect(read).toHaveBeenCalledWith('/business/material-tracking/', { page: 1, page_size: expect.any(Number) })
    const text = wrapper.text()
    for (const value of ['A2609', '气缸 SC50', '在途', '亚德客', '多个', '装配班 张师傅', '不在 BOM', '待批 10']) expect(text).toContain(value)
    const links = wrapper.findAll('a').map(link => [link.text(), link.attributes('href')])
    expect(links).toContainEqual(['PO000040', '/purchases?resource=purchases&focus=40&project=3'])
    expect(links).toContainEqual(['A2609', '/bom?project=3'])
    expect(links).toContainEqual(['LL0008', '/inventory/issue-slips/8'])
    await wrapper.findAll('.resource-status-tabs button').find(button => button.text() === '缺料')!.trigger('click')
    await flushPromises()
    expect(read).toHaveBeenLastCalledWith('/business/material-tracking/', expect.objectContaining({ status: 'shortage', page: 1 }))
  })
  it('导出按当前筛选下载 Excel', async () => {
    const wrapper = await render({ projectId: 3 })
    expect(read).toHaveBeenCalledWith('/business/material-tracking/', expect.objectContaining({ project: 3 }))
    await wrapper.findAll('button').find(button => button.text() === '导出 Excel')!.trigger('click')
    await flushPromises()
    expect(download).toHaveBeenCalledWith('/business/material-tracking/export/', expect.stringMatching(/^物料跟踪-.*\.xlsx$/), { project: 3, file_format: 'xlsx' })
  })
  it('普通成员看不到采购单号、供应商和单价列', async () => {
    user.value = { id: 3, roles: ['member'] }
    const wrapper = await render()
    const headers = wrapper.findAll('th').map(th => th.text())
    expect(headers).toEqual(expect.arrayContaining(['需求', '已领', '领料人']))
    for (const hidden of ['采购单号', '供应商', '单价', '金额', '采购员']) expect(headers).not.toContain(hidden)
    expect(wrapper.findAll('a').map(link => link.text())).not.toContain('LL0008')
  })
  it('手机宽度改为卡片，需求、已采购、已收、已领、缺料一行看清', async () => {
    narrow(390)
    const wrapper = await render()
    const card = wrapper.get('.tracking-cards li')
    expect(card.text()).toContain('需求 6 · 已采购 6 · 已收 2 · 已领 0 · 缺料 0')
    expect(card.text()).toContain('交期 2026-11-25、2026-12-02')
    expect(wrapper.find('.tracking-table').exists()).toBe(false)
  })
})
