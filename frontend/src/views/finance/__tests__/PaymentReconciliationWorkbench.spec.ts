import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import PaymentReconciliationWorkbench from '../PaymentReconciliationWorkbench.vue'

const getBankStatements = vi.fn()
const getPayableItems = vi.fn()
const getBankStatementPayableCandidates = vi.fn()
const getBankStatementSettlements = vi.fn()
const settlePayableReconcile = vi.fn()
const unsettlePayableReconcile = vi.fn()
const getSupplierList = vi.fn()

vi.mock('@/api/finance', () => ({
  getBankStatements: (...args: any[]) => getBankStatements(...args),
  getPayableItems: (...args: any[]) => getPayableItems(...args),
  getBankStatementPayableCandidates: (...args: any[]) => getBankStatementPayableCandidates(...args),
  getBankStatementSettlements: (...args: any[]) => getBankStatementSettlements(...args),
  settlePayableReconcile: (...args: any[]) => settlePayableReconcile(...args),
  unsettlePayableReconcile: (...args: any[]) => unsettlePayableReconcile(...args)
}))

vi.mock('@/api/masterdata', () => ({
  getSupplierList: (...args: any[]) => getSupplierList(...args)
}))

describe('PaymentReconciliationWorkbench', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getBankStatements.mockResolvedValue({ results: [], count: 0 })
    getPayableItems.mockResolvedValue({ results: [], count: 0 })
    getSupplierList.mockResolvedValue({ results: [] })
  })

  it('挂载后拉取左侧未核销银行流水(固定 transaction_type=DEBIT)', async () => {
    mount(PaymentReconciliationWorkbench)
    await flushPromises()
    expect(getBankStatements).toHaveBeenCalledTimes(1)
    expect(getBankStatements).toHaveBeenCalledWith(
      expect.objectContaining({ transaction_type: 'DEBIT', page: 1, page_size: 20 })
    )
  })

  it('挂载后加载供应商下拉数据,且不预先请求台账/候选接口', async () => {
    mount(PaymentReconciliationWorkbench)
    await flushPromises()
    expect(getSupplierList).toHaveBeenCalledTimes(1)
    // 未选择银行流水前不应请求候选匹配接口
    expect(getBankStatementPayableCandidates).not.toHaveBeenCalled()
    // “台账查询”页签懒加载,未切换前不应请求
    expect(getPayableItems).not.toHaveBeenCalled()
  })

  it('未选择银行流水时右侧候选栏提示用户先选流水', async () => {
    // 注:el-card 的 #header 具名插槽内容(标题文案)依赖真实 Element Plus 组件渲染,
    // 而测试全局 setup(src/test-setup.ts)对 'element-plus' 做了整模块 mock,
    // 未解析的自定义标签不会消费具名插槽,故此处仅断言默认插槽区域会渲染的提示文案,
    // 不对 #header 标题文案做强依赖断言。
    const wrapper = mount(PaymentReconciliationWorkbench)
    await flushPromises()
    expect(wrapper.text()).toContain('请先在左侧选择一条待核销的银行流水')
  })
})
