import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { ElMessage } from 'element-plus'
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

  it('选择费用类别筛选后查询台账带上 category 参数', async () => {
    // 注:el-form/el-select/el-option 在全局测试配置里被整体 stub(true),不渲染任何插槽
    // 内容(见 src/test-setup.ts),因此无法通过真实 DOM 交互模拟下拉选择;此处直接驱动
    // rightFilters.category + handleLedgerSearch() 校验新增筛选项到查询参数的拼装逻辑,
    // 这也是本次改动唯一新增的业务逻辑(模板里的 v-model 绑定与既有 source_type/supplier/status
    // 筛选项写法一致,非本次新引入的风险点)。
    const wrapper = mount(PaymentReconciliationWorkbench)
    await flushPromises()
    const vm = wrapper.vm as any
    vm.rightFilters.category = '委外加工'
    await vm.handleLedgerSearch()
    await flushPromises()
    expect(getPayableItems).toHaveBeenCalledWith(expect.objectContaining({ category: '委外加工' }))
  })

  it('核销成功提示信息包含本次生成的付款单号', async () => {
    const wrapper = mount(PaymentReconciliationWorkbench)
    await flushPromises()
    const vm = wrapper.vm as any
    vm.selectedStatement = { id: 1, amount: 500, debit_amount: 500, counterparty_name: '测试供应商' }
    vm.selection[10] = { item: { id: 10, source_no: 'AP-0001', remaining: 500 }, amount: 500 }
    settlePayableReconcile.mockResolvedValue({
      ok: true,
      settlement_ids: [99],
      payment_nos: ['PAY202607070001'],
      bank_statement_status: 'MATCHED'
    })

    await vm.confirmSettle()
    await flushPromises()

    expect(settlePayableReconcile).toHaveBeenCalledWith({
      bank_statement_id: 1,
      allocations: [{ payable_item_id: 10, amount: 500 }]
    })
    expect(ElMessage.success).toHaveBeenCalledWith(expect.stringContaining('PAY202607070001'))
  })
})
