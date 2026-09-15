import { describe, expect, it } from 'vitest'
import { flowFor } from './flows'

const labels = (resource: string, row: Record<string, unknown>) => {
  const flow = flowFor(resource, row)!
  return { at: flow.nodes[flow.current]?.label, aborted: flow.aborted?.label, steps: flow.nodes.map(n => n.label) }
}
const isoDays = (days: number) => new Date(Date.now() + days * 86400000).toISOString().slice(0, 10)

describe('业务流程节点定位', () => {
  it('销售、项目、采购、对账、任务按状态定位当前节点', () => {
    expect(labels('sales', { status: 'quoted' }).at).toBe('已报价')
    expect(labels('sales', { status: 'quoted' }).steps).toEqual(['需求中', '已报价', '已签约'])
    expect(labels('projects', { status: 'delivering' }).at).toBe('交付中')
    expect(labels('purchases', { status: 'partial' }).at).toBe('部分收货')
    expect(labels('reconciliations', { status: 'confirmed' }).at).toBe('已确认')
    expect(labels('tasks', { status: 'open' }).at).toBe('待完成')
  })

  it('终止状态离开主链并标记原因，不假装停在某个节点上', () => {
    const cancelled = flowFor('projects', { status: 'cancelled' })!
    expect(cancelled.current).toBe(-1)
    expect(cancelled.aborted?.label).toBe('已取消')
    expect(cancelled.nodes).toHaveLength(6)
    expect(labels('reconciliations', { status: 'void' }).aborted).toBe('已作废')
    expect(labels('purchases', { status: 'cancelled' }).aborted).toBe('已取消')
  })

  it('交付批次按发货、验收与质保日期推导，不依赖状态字段', () => {
    expect(labels('deliveries', { shipped_date: '2026-01-05' }).at).toBe('已发货')
    expect(labels('deliveries', { shipped_date: '2026-01-05', accepted_date: '2026-02-01' }).at).toBe('已验收')
    expect(labels('deliveries', { accepted_date: '2026-02-01', warranty_until: isoDays(30) }).at).toBe('质保中')
    expect(labels('deliveries', { accepted_date: '2026-02-01', warranty_until: isoDays(-1) }).at).toBe('质保期满')
  })

  it('收付款按余额推导，超收超付单独提示待退款', () => {
    expect(labels('entries', { amount: '100.00', credit_amount: '0.00', paid_amount: '0.00', balance: '100.00' }).at).toBe('待结算')
    expect(labels('entries', { amount: '100.00', credit_amount: '0.00', paid_amount: '40.00', balance: '60.00' }).at).toBe('部分结算')
    expect(labels('entries', { amount: '100.00', credit_amount: '30.00', paid_amount: '0.00', balance: '70.00' }).at).toBe('部分结算')
    expect(labels('entries', { amount: '100.00', credit_amount: '0.00', paid_amount: '100.00', balance: '0.00' }).at).toBe('已结清')
    expect(labels('entries', { amount: '100.00', paid_amount: '120.00', balance: '-20.00' }).aborted).toBe('待退款')
    expect(labels('entries', { cancelled: true, balance: '100.00' }).aborted).toBe('已取消')
  })

  it('银行流水按未匹配金额定位，待核实户名留在已登记', () => {
    expect(labels('bank-records', { amount: '500.00', remaining_amount: '500.00' }).at).toBe('已登记')
    expect(labels('bank-records', { amount: '500.00', remaining_amount: '200.00' }).at).toBe('部分匹配')
    expect(labels('bank-records', { amount: '500.00', remaining_amount: '0.00' }).at).toBe('已核对')
    expect(labels('bank-records', { amount: '500.00', remaining_amount: '0.00', needs_review: true }).at).toBe('已登记')
    expect(labels('bank-records', { amount: '-6000.00', remaining_amount: '6000.00' }).at).toBe('已登记')
    expect(labels('bank-records', { amount: '-6000.00', remaining_amount: '2500.00' }).at).toBe('部分匹配')
    expect(labels('bank-records', { void_reason: '登记错误' }).aborted).toBe('已作废')
  })

  it('收付流水区分银行核对与冲销', () => {
    expect(labels('payments', { bank_matched: false }).at).toBe('已登记')
    expect(labels('payments', { bank_matched: true }).at).toBe('银行已核对')
    expect(labels('payments', { reversed_by: 9 }).aborted).toBe('已冲销')
    expect(labels('payments', { reversal_of: 8 }).aborted).toBe('冲销记录')
  })

  it('采购质保按接口返回的中文状态定位，维修与换货同属处理中', () => {
    expect(labels('warranty', { status: '待响应' }).at).toBe('待响应')
    expect(labels('warranty', { status: '维修中' }).at).toBe('处理中')
    expect(labels('warranty', { status: '已更换' }).at).toBe('处理中')
    expect(labels('warranty', { status: '已关闭' }).at).toBe('已关闭')
    expect(labels('warranty', { status: '待响应' }).steps).toEqual(['待响应', '处理中', '已关闭'])
    expect(flowFor('warranty', { status: '未知' })).toBeNull()
  })

  it('没有流程的资源和未知状态不显示节点', () => {
    expect(flowFor('items', { id: 1 })).toBeNull()
    expect(flowFor('stocks', { id: 1 })).toBeNull()
    expect(flowFor('sales', null)).toBeNull()
    expect(flowFor('sales', { status: 'unknown' })).toBeNull()
  })
})
