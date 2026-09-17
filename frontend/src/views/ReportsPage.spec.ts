import { describe, it, expect, vi } from 'vitest'
import { defineComponent, type Component } from 'vue'
import { shallowMount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import ReportsPage from './ReportsPage.vue'
import { read } from '../api'
import { user } from '../session'
import { navigation } from '../navigation'

vi.mock('../api', () => ({ read: vi.fn(), write: vi.fn() }))

const summary = {
  contract_amount: '12345678901234567.89',
  actual_cost: '4200000.00',
  committed_cost: '880000.00',
  receivable: '3100000.00',
  payable: '1500000.00',
  overdue_receivable: '682000.00',
  overdue_payable: '410000.00',
  refund_out: '50000.00',
  refund_in: '20000.00',
  projects: 2,
  active_projects: 1,
  over_budget: 1,
  overdue: 1,
  unbudgeted: 1,
}
const results = [
  {
    id: 7, code: 'P-2026-007', name: '装配线', manager: '李工', status: 'active', due_date: '2026-08-01',
    contract_amount: '900000.00', actual_cost: '100000.00', committed_cost: '20000.00', budget: '60000.00',
    occupied_cost: '120000.00', receivable: '300000.00', payable: '80000.00', warnings: ['材料预算已超支'],
    over_budget: true, overdue: false, unbudgeted: false,
  },
  {
    id: 8, code: 'P-2026-008', name: '检测台', manager: '王工', status: 'quoted', due_date: null,
    contract_amount: '400000.00', actual_cost: '30000.00', committed_cost: '5000.00', budget: null,
    occupied_cost: '35000.00', receivable: '0.00', payable: '0.00', warnings: [],
    over_budget: false, overdue: false, unbudgeted: true,
  },
]
const payload = { summary, results, count: 2, page: 1, page_size: 20, generated_at: '2026-09-09T00:00:00Z' }
// 表格桩件展开列定义与行内容，便于断言列数与合并后的成本单元格。
const tableStubs: Record<string, Component> = {
  ElTable: defineComponent({
    props: { data: { type: Array, default: () => [] } },
    provide() { return { tableRows: this.data } },
    template: '<div class="table"><slot /></div>',
  }),
  ElTableColumn: defineComponent({
    props: { label: { type: String, default: '' } },
    inject: ['tableRows'],
    template: '<div class="column" :data-label="label"><span v-for="(row, index) in tableRows" :key="index" class="cell"><slot :row="row" /></span></div>',
  }),
  ElButton: { template: '<button type="button"><slot /></button>' },
  ElAlert: { props: ['title'], template: '<p role="alert">{{ title }}</p>' },
}
const routerLink = { props: ['to'], template: '<a><slot /></a>' }

function mountPage(stubs: Record<string, Component>) {
  return shallowMount(ReportsPage, {
    global: {
      plugins: [ElementPlus],
      renderStubDefaultSlot: true,
      components: { 'router-link': routerLink },
      stubs,
    },
  })
}

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
    vi.mocked(read).mockResolvedValue(payload)
    const wrapper = mountPage({ ElTable: { template: '<div />' }, ElAlert: tableStubs.ElAlert })
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
  it('四个主指标用大卡片，降级指标与关注项保留在汇总行', async () => {
    vi.mocked(read).mockResolvedValue(payload)
    const wrapper = mountPage(tableStubs)
    await flushPromises()
    const cards = wrapper.findAll('.report-metric')
    expect(cards.map(card => card.attributes('aria-label'))).toEqual(['已签约合同额', '实际成本', '待收款', '待付款'])
    expect(cards[2].text()).toContain('¥ 3,100,000.00')
    expect(cards[3].text()).toContain('¥ 1,500,000.00')
    // 逾期降级后仍在主卡说明里保留金额，并用风险色标记。
    expect(cards[2].get('.report-risk').text()).toBe('682,000.00')
    expect(cards[3].get('.report-risk').text()).toBe('410,000.00')
    const watch = wrapper.get('[aria-label="经营关注"]')
    for (const [label, amount] of [['已承诺采购', '880,000.00'], ['待退客户款', '50,000.00'], ['待收退款', '20,000.00']]) {
      expect(watch.text()).toContain(`${label} ¥ ${amount}`)
    }
    // 逾期金额只出现在主卡说明里，汇总行不再重复
    for (const label of ['逾期待收款', '逾期待付款']) expect(watch.text()).not.toContain(label)
    expect(watch.findAll('.report-risk')).toHaveLength(0)
    expect(watch.text()).toContain('项目 2')
    expect(watch.text()).toContain('超预算 1')
    expect(watch.text()).toContain('交付逾期 1')
    expect(watch.text()).toContain('未设置预算 1')
    wrapper.unmount()
  })
  it('关注项按钮仍可筛选项目', async () => {
    vi.mocked(read).mockResolvedValue(payload)
    const wrapper = mountPage(tableStubs)
    await flushPromises()
    for (const [text, value] of [['超预算', 'over_budget'], ['交付逾期', 'overdue'], ['未设置预算', 'unbudgeted']]) {
      const button = wrapper.get('[aria-label="经营关注"]').findAll('button').find(item => item.text().startsWith(text))
      expect(button).toBeTruthy()
      await button!.trigger('click')
      await flushPromises()
      expect(read).toHaveBeenLastCalledWith('/business/reports/', { search: '', status: '', risk: value, page: 1, page_size: 10 })
    }
    wrapper.unmount()
  })
  it('明细表收敛为七列，预算与在途并入实际成本', async () => {
    vi.mocked(read).mockResolvedValue(payload)
    const wrapper = mountPage(tableStubs)
    await flushPromises()
    const columns = wrapper.findAll('.column')
    expect(columns).toHaveLength(7)
    expect(columns.map(column => column.attributes('data-label') || '展开')).toEqual(['项目', '状态', '合同额', '实际成本 / 预算', '待收 / 待付', '关注', '展开'])
    const cost = columns[3].findAll('.cell')
    expect(cost[0].text()).toContain('100,000.00')
    expect(cost[0].text()).toContain('材料预算 60,000.00 · 在途 20,000.00')
    expect(cost[1].text()).toContain('未设置预算 · 在途 5,000.00')
    wrapper.unmount()
  })
  it('口径说明只保留一处并使用人民币表述', async () => {
    vi.mocked(read).mockResolvedValue(payload)
    const wrapper = mountPage(tableStubs)
    await flushPromises()
    const basis = wrapper.findAll('.report-basis')
    expect(basis).toHaveLength(1)
    expect(basis[0].text()).toContain('人民币含税经营口径')
    expect(basis[0].text()).toContain('不是期间收入或会计利润')
    expect(wrapper.text()).not.toContain('CNY')
    wrapper.unmount()
  })
})
