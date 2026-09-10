import { beforeEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createRouter, createMemoryHistory } from 'vue-router'
import WorkbenchPage from './WorkbenchPage.vue'
import { read } from '../api'
vi.mock('../api', () => ({ read: vi.fn() }))
vi.mock('../session', () => ({ user: { display_name: '测试用户' } }))
const bucket = (results: any[], count = results.length) => ({ count, page: 1, results })
const data = () => ({
  tasks: { ...bucket([], 12), overdue_count: 7, today_count: 5 },
  drafts: bucket([]),
  bank_records: bucket([{ id: 1, counterparty: '测试客户', reference: 'BANK-1', amount: '200', remaining_amount: '100', date: '2026-09-10' }], 389),
  prepayments: bucket([{ id: 2, code: 'REC-2' }]),
})
async function render() {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/:pathMatch(.*)*', component: { template: '<div />' } }] })
  const wrapper = mount(WorkbenchPage, { global: { plugins: [ElementPlus, router] } })
  await flushPromises()
  expect(wrapper.findAll('.work-card')).toHaveLength(1)
  await wrapper.find('.work-filters button').trigger('click')
  return wrapper
}
beforeEach(() => { vi.clearAllMocks(); vi.mocked(read).mockResolvedValue(data()) })
it('shows complete counts, bank details, collapsed empty categories and correct finance links', async () => {
  const wrapper = await render()
  expect(read).toHaveBeenCalledWith('/business/workbench/', { page_size: 5 })
  expect(wrapper.find('.work-metric').text()).toContain('7')
  expect(wrapper.text()).toContain('389')
  expect(wrapper.text()).toContain('测试客户')
  expect(wrapper.text()).toContain('待指定项目')
  expect(wrapper.find('.work-card-drafts').exists()).toBe(false)
  expect(wrapper.find('[aria-label="查看全部银行待认领 / 匹配"]').attributes('href')).toBe('/finance?section=bank&project=all')
  expect(wrapper.find('[aria-label="查看全部待核准预付款"]').attributes('href')).toBe('/finance?section=reconciliations&project=all')
  wrapper.unmount()
})
it('updates only the paged category and retains other data on failure', async () => {
  const wrapper = await render()
  vi.mocked(read).mockResolvedValueOnce({ bank_records: { ...bucket([{ id: 9, counterparty: '第二页', amount: 1, remaining_amount: 1 }], 389), page: 2 } })
  const pagination = wrapper.find('.work-card-bank_records').findComponent({ name: 'ElPagination' })
  pagination.vm.$emit('current-change', 2)
  await flushPromises()
  expect(read).toHaveBeenLastCalledWith('/business/workbench/', { bucket: 'bank_records', page_size: 5, bank_records_page: 2 })
  expect(wrapper.find('.work-card-prepayments').text()).toContain('REC-2')
  expect(wrapper.find('.work-card-bank_records').text()).toContain('第二页')
  vi.mocked(read).mockRejectedValueOnce(new Error('网络异常'))
  pagination.vm.$emit('current-change', 3)
  await flushPromises()
  expect(wrapper.find('.work-card-bank_records').text()).toContain('第二页')
  expect(wrapper.find('.work-card-bank_records [role="alert"]').exists()).toBe(true)
  wrapper.unmount()
})
it('ignores an old category response after a full refresh', async () => {
  const wrapper = await render()
  let resolve!: (data: any) => void
  vi.mocked(read).mockReturnValueOnce(new Promise(r => { resolve = r }))
  wrapper.find('.work-card-bank_records').findComponent({ name: 'ElPagination' }).vm.$emit('current-change', 2)
  await flushPromises()
  vi.mocked(read).mockResolvedValueOnce({ ...data(), bank_records: bucket([{ id: 3, counterparty: '最新结果', amount: 1, remaining_amount: 1 }]) })
  await wrapper.find('.work-refresh button').trigger('click')
  await flushPromises()
  resolve({ bank_records: bucket([{ id: 4, counterparty: '过期结果' }]) })
  await flushPromises()
  expect(wrapper.text()).toContain('最新结果')
  expect(wrapper.text()).not.toContain('过期结果')
  wrapper.unmount()
})
