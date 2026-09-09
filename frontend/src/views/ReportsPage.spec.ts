import { describe, it, expect, vi } from 'vitest'
import { shallowMount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import ReportsPage from './ReportsPage.vue'
import { read } from '../api'
import { user } from '../session'
import { navigation } from '../navigation'

vi.mock('../api', () => ({ read: vi.fn(), write: vi.fn() }))

describe('经营报表', () => {
  it('仅管理员与显式授权经理拥有入口', () => {
    for (const profile of [{ role: 'manager' }, { role: 'finance' }, { role: 'member', management_reports: true }]) {
      user.value = profile
      expect(navigation().some(n => n.key === 'reports')).toBe(false)
    }
    for (const profile of [{ role: 'admin' }, { role: 'manager', management_reports: true }]) {
      user.value = profile
      expect(navigation().some(n => n.key === 'reports')).toBe(true)
    }
  })
  it('筛选提交到接口，失败清除旧经营金额', async () => {
    vi.mocked(read).mockResolvedValue({ summary: { contract_amount: '12345678901234567.89' }, results: [], count: 0, page: 1, page_size: 20, generated_at: '2026-09-09T00:00:00Z' })
    const wrapper = shallowMount(ReportsPage, {
      global: { plugins: [ElementPlus], renderStubDefaultSlot: true, stubs: { ElTable: { template: '<div />' }, ElAlert: { props: ['title'], template: '<p role="alert">{{ title }}</p>' } } },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('12,345,678,901,234,567.89')
    await wrapper.get('[aria-label="搜索项目"]').setValue('装配线')
    await wrapper.get('[aria-label="关注事项"]').setValue('over_budget')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(read).toHaveBeenLastCalledWith('/business/reports/', { search: '装配线', status: '', risk: 'over_budget', page: 1, page_size: 10 })
    vi.mocked(read).mockRejectedValue(new Error('报表权限已撤销'))
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.text()).not.toContain('12,345,678,901,234,567.89')
    expect(wrapper.find('[role="alert"]').exists()).toBe(true)
    wrapper.unmount()
  })
})
