import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import FinanceTotals from './FinanceTotals.vue'
import { read } from '../api'

vi.mock('../api', () => ({ read: vi.fn() }))

const totals = {
  receivable: '4926000.00',
  payable: '1845300.00',
  overdue_receivable: '682000.00',
  overdue_payable: '139840.00',
  refund_out: '50000.00',
  refund_in: '20000.00',
}
const render = async (props = {}) => {
  const wrapper = mount(FinanceTotals, { props, global: { plugins: [ElementPlus] } })
  await flushPromises()
  return wrapper
}

describe('收付款余额卡片', () => {
  beforeEach(() => { vi.clearAllMocks(); vi.mocked(read).mockResolvedValue({ ...totals }) })

  it('三张卡片给出待收、待付与其中逾期，逾期用风险色', async () => {
    const wrapper = await render()
    expect(read).toHaveBeenCalledWith('/business/entries/summary/', { project: undefined })
    const cards = wrapper.findAll('.finance-total')
    expect(cards.map(card => card.attributes('aria-label'))).toEqual(['待收款', '待付款', '其中已逾期'])
    expect(cards[0].get('strong').text()).toBe('¥ 4,926,000.00')
    expect(cards[1].get('strong').text()).toBe('¥ 1,845,300.00')
    // 其中已逾期 = 逾期待收 682,000 + 逾期待付 139,840
    expect(cards[2].get('strong').text()).toBe('¥ 821,840.00')
    expect(cards[2].get('strong').classes()).toContain('finance-risk')
    expect(cards[0].get('strong').classes()).not.toContain('finance-risk')
    expect(cards[2].text()).toContain('待收 682,000.00 · 待付 139,840.00')
    wrapper.unmount()
  })

  it('没有逾期时不标风险色', async () => {
    vi.mocked(read).mockResolvedValue({ ...totals, overdue_receivable: '0.00', overdue_payable: '0.00' })
    const wrapper = await render()
    const overdue = wrapper.findAll('.finance-total')[2]
    expect(overdue.get('strong').text()).toBe('¥ 0.00')
    expect(overdue.get('strong').classes()).not.toContain('finance-risk')
    wrapper.unmount()
  })

  it('跟着项目筛选和刷新重新汇总，过期响应不覆盖最新结果', async () => {
    const wrapper = await render({ projectId: 7, revision: 1 })
    expect(read).toHaveBeenCalledWith('/business/entries/summary/', { project: 7 })
    let resolve!: (value: unknown) => void
    vi.mocked(read).mockReturnValueOnce(new Promise(r => { resolve = r }))
    await wrapper.setProps({ revision: 2 })
    await flushPromises()
    vi.mocked(read).mockResolvedValueOnce({ ...totals, receivable: '1.00' })
    await wrapper.setProps({ projectId: 8 })
    await flushPromises()
    resolve({ ...totals, receivable: '999999.00' })
    await flushPromises()
    expect(wrapper.findAll('.finance-total')[0].get('strong').text()).toBe('¥ 1.00')
    wrapper.unmount()
  })

  it('接口失败时给出提示而不是空白卡片', async () => {
    vi.mocked(read).mockRejectedValue(new Error('网络异常'))
    const wrapper = await render()
    expect(wrapper.get('[role="alert"]').text()).toContain('网络异常')
    expect(wrapper.find('.finance-total').exists()).toBe(false)
    wrapper.unmount()
  })
})
