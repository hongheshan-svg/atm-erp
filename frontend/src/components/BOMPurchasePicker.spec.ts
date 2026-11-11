import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h, nextTick } from 'vue'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import ElementPlus, { ElMessage } from 'element-plus'
import BOMPurchasePicker from './BOMPurchasePicker.vue'
import { read, write } from '../api'
import { user } from '../session'
import { pageSize } from '../pagination'
import type { Row } from '../types'

vi.mock('../api', () => ({ read: vi.fn(), write: vi.fn(), all: vi.fn(), download: vi.fn() }))

// Keep the table, checkboxes, form and filters real; remote lookup is outside this flow.
const RemoteSelect = defineComponent({
  inheritAttrs: false,
  props: { modelValue: [String, Number], label: String, disabled: Boolean, required: Boolean },
  emits: ['update:modelValue'],
  setup(props, { emit }) {
    return () => h('select', {
      'aria-label': props.label, value: props.modelValue ?? '', disabled: props.disabled,
      required: props.required,
      onChange: (event: Event) => {
        const value = (event.target as HTMLSelectElement).value
        emit('update:modelValue', value ? Number(value) : '')
      },
    }, [h('option', { value: '' }, '请选择'), ...(props.label === '供应商'
      ? [h('option', { value: 42 }, '示例供应商')]
      : [h('option', { value: 10 }, 'ATM2651'), h('option', { value: 20 }, 'ATM2652')])])
  },
})

const base = { quantity: '8.000', available: '0.000', incoming: '0.000', issued: '0.000',
  shortage: '8.000', is_active: true, part_type: 'standard', product_category: '21', unit: '件' }
const fixtures = (): Row[] => [
  { ...base, bom_line: 101, item: 1, item_code: '2199000001', item_name: '伺服电机', brand: '台达', assembly_unit: '输送单元' },
  { ...base, bom_line: 102, item: 1, item_code: '2199000001', item_name: '伺服电机', brand: '台达', assembly_unit: '检测单元' },
  { ...base, bom_line: 103, item: 2, item_code: '2199000002', item_name: '直线导轨', brand: 'HIWIN', assembly_unit: '输送单元' },
  { ...base, bom_line: 104, item: 3, item_code: '2199000003', item_name: '光电传感器', brand: 'OMRON', assembly_unit: '检测单元', shortage: '0.000' },
  { ...base, bom_line: 105, item: 4, item_code: '2199000004', item_name: '停用气缸', brand: 'SMC', assembly_unit: '夹紧单元', is_active: false },
]
let demand: Row[]
const wrappers: VueWrapper[] = []
const originalScrollIntoView = Element.prototype.scrollIntoView

beforeEach(() => {
  demand = fixtures()
  user.value = { id: 7, roles: ['purchaser'] }
  pageSize.value = 10
  vi.mocked(read).mockReset().mockImplementation(async path => {
    if (path.endsWith('/demand/')) return { lines: demand.map(row => ({ ...row })) }
    if (path === '/business/partners/42/') return { id: 42, kind: 'supplier', payment_term: 'month30' }
    if (path === '/business/projects/10/') return { id: 10, code: 'ATM2651', name: '装配检测线', status: 'active' }
    if (path === '/business/projects/20/') return { id: 20, code: 'ATM2652', name: '包装线', status: 'active' }
    throw new Error(`Unexpected read: ${path}`)
  })
  vi.mocked(write).mockReset().mockResolvedValue({ id: 80, status: 'draft' })
  vi.spyOn(ElMessage, 'success').mockReturnValue({ close: vi.fn() })
  vi.stubGlobal('ResizeObserver', class { observe = vi.fn(); unobserve = vi.fn(); disconnect = vi.fn() })
  Element.prototype.scrollIntoView = vi.fn()
})

afterEach(() => {
  wrappers.splice(0).forEach(wrapper => wrapper.unmount())
  user.value = null
  Element.prototype.scrollIntoView = originalScrollIntoView
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

async function picker(props: { projectId?: number; initialSelection?: number[] } = { projectId: 10 }) {
  const wrapper = mount(BOMPurchasePicker, {
    props, global: { plugins: [ElementPlus], stubs: { RemoteSelect, RouterLink: true } },
  })
  wrappers.push(wrapper)
  await flushPromises()
  return wrapper
}
const draft = (wrapper: VueWrapper, unit = '输送单元', code = '2199000001') =>
  wrapper.get(`[aria-label="采购明细 ${code} ${unit}"]`)
const button = (wrapper: VueWrapper, label: string) => wrapper.findAll('button').find(value => value.text() === label)!
async function supplier(wrapper: VueWrapper) {
  await wrapper.get('select[aria-label="供应商"]').setValue('42')
  await wrapper.get('input[aria-label="交期"]').setValue('2026-09-18')
  await flushPromises()
}
async function selectMotor(wrapper: VueWrapper) {
  await wrapper.findAll('input[aria-label="选择 2199000001"]')[0]!.setValue(true)
  await draft(wrapper).get('input[aria-label="含税单价（元）"]').setValue('10.20')
}

describe('BOM 并排选料与采购草稿', () => {
  it('筛选外的选择和编辑保留，全选只增加有缺口的有效物料', async () => {
    const wrapper = await picker()
    await selectMotor(wrapper)
    await draft(wrapper).get('input[aria-label="采购数量"]').setValue('2.500')
    await wrapper.get('input[aria-label="搜索 BOM 物料"]').setValue('导轨')
    expect(wrapper.findAll('.el-table__body input[type="checkbox"]')).toHaveLength(1)
    await button(wrapper, '全选筛选结果').trigger('click')
    await draft(wrapper, '输送单元', '2199000002').get('input[aria-label="含税单价（元）"]').setValue('3.00')
    await wrapper.get('input[aria-label="搜索 BOM 物料"]').setValue('')
    expect(draft(wrapper).get<HTMLInputElement>('input[aria-label="采购数量"]').element.value).toBe('2.500')
    expect(draft(wrapper).get<HTMLInputElement>('input[aria-label="含税单价（元）"]').element.value).toBe('10.20')
    expect(wrapper.get('[aria-label="含税合计"]').text()).toBe('¥ 49.50')
    await button(wrapper, '全选筛选结果').trigger('click')
    expect(wrapper.findAll('.draft-item')).toHaveLength(3)
    expect(wrapper.get<HTMLInputElement>('input[aria-label="选择 2199000003"]').element.disabled).toBe(true)
    expect(wrapper.get<HTMLInputElement>('input[aria-label="选择 2199000004"]').element.disabled).toBe(true)
    expect(draft(wrapper).get<HTMLInputElement>('input[aria-label="采购数量"]').element.value).toBe('2.500')
  })

  it('同一物料分属不同 BOM 行，移除一行不会串改另一单元的采购明细', async () => {
    const wrapper = await picker()
    await selectMotor(wrapper)
    await wrapper.findAll('input[aria-label="选择 2199000001"]')[1]!.setValue(true)
    await draft(wrapper, '检测单元').get('input[aria-label="采购数量"]').setValue('2.000')
    await draft(wrapper, '检测单元').get('input[aria-label="含税单价（元）"]').setValue('20.00')
    await wrapper.get('button[aria-label="移除 2199000001 输送单元"]').trigger('click')
    const checks = wrapper.findAll<HTMLInputElement>('input[aria-label="选择 2199000001"]')
    expect(checks.map(check => check.element.checked)).toEqual([false, true])
    expect(wrapper.findAll('.draft-item')).toHaveLength(1)
    await supplier(wrapper)
    expect(wrapper.text()).toContain('合格收货当月月底 + 30天')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(write).toHaveBeenCalledWith('/business/purchases/', expect.objectContaining({
      project: 10, supplier: 42, from_demand: true,
      lines: [{ item: 1, bom_line: 102, quantity: '2.000', unit_price: '20.00' }],
    }), expect.any(String))
    expect(wrapper.emitted('saved')).toEqual([[{ id: 80, status: 'draft' }]])
  })

  it('切换项目清空采购草稿、供应商和筛选，重新读取新项目', async () => {
    const wrapper = await picker({})
    await wrapper.get('select[aria-label="采购项目"]').setValue('10')
    await flushPromises()
    await selectMotor(wrapper)
    await supplier(wrapper)
    await wrapper.get('textarea[aria-label="采购备注"]').setValue('分批交付')
    await wrapper.get('input[aria-label="搜索 BOM 物料"]').setValue('电机')
    await wrapper.get('select[aria-label="采购项目"]').setValue('20')
    await flushPromises()
    expect(wrapper.text()).toContain('ATM2652 · 包装线')
    expect(wrapper.findAll('.draft-item')).toHaveLength(0)
    expect(wrapper.get<HTMLSelectElement>('select[aria-label="供应商"]').element.value).toBe('')
    expect(wrapper.get<HTMLTextAreaElement>('textarea[aria-label="采购备注"]').element.value).toBe('')
    expect(wrapper.get<HTMLInputElement>('input[aria-label="搜索 BOM 物料"]').element.value).toBe('')
    expect(read).toHaveBeenCalledWith('/business/projects/20/demand/')
    expect(write).not.toHaveBeenCalled()
  })

  it('刷新后缺口缩小会阻止超量保存并保留已填数据，调整数量后可继续', async () => {
    const wrapper = await picker()
    await selectMotor(wrapper)
    await draft(wrapper).get('input[aria-label="采购数量"]').setValue('4.000')
    await supplier(wrapper)
    demand[0] = { ...demand[0], shortage: '2.000' }
    await button(wrapper, '刷新缺料').trigger('click')
    await flushPromises()
    expect(draft(wrapper).text()).toContain('数量超过当前缺料 2')
    expect(draft(wrapper).get<HTMLInputElement>('input[aria-label="采购数量"]').element.value).toBe('4.000')
    expect(draft(wrapper).get<HTMLInputElement>('input[aria-label="含税单价（元）"]').element.value).toBe('10.20')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(write).not.toHaveBeenCalled()
    expect(wrapper.get('[role="alert"]').text()).toContain('数量超过当前缺料 2')
    await draft(wrapper).get('input[aria-label="采购数量"]').setValue('2.000')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(write).toHaveBeenCalledTimes(1)
  })

  it('数量和单价格式无效时不提交，纠正后按原精度保存', async () => {
    const wrapper = await picker()
    await selectMotor(wrapper)
    await supplier(wrapper)
    for (const [quantity, price] of [
      ['0', '1'], ['-1', '1'], ['1.0001', '1'], ['1e0', '1'],
      ['1', '-0.01'], ['1', '1.001'], ['1', '1e2'], ['1', '含税10元'],
    ]) {
      await draft(wrapper).get('input[aria-label="采购数量"]').setValue(quantity)
      await draft(wrapper).get('input[aria-label="含税单价（元）"]').setValue(price)
      expect(wrapper.get('[aria-label="含税合计"]').text()).toBe('待填写')
      await wrapper.get('form').trigger('submit')
      await flushPromises()
      expect(write).not.toHaveBeenCalled()
      expect(wrapper.get('[role="alert"]').text()).toContain('伺服电机：')
    }
    await draft(wrapper).get('input[aria-label="采购数量"]').setValue('1.005')
    await draft(wrapper).get('input[aria-label="含税单价（元）"]').setValue('1.00')
    expect(wrapper.get('[aria-label="含税合计"]').text()).toBe('¥ 1.01')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(write).toHaveBeenCalledTimes(1)
    expect(vi.mocked(write).mock.calls[0]![1]).toEqual(expect.objectContaining({
      lines: [{ item: 1, bom_line: 101, quantity: '1.005', unit_price: '1.00' }],
    }))
  })

  it('刷新时已选 BOM 行被移除或停用会保留编辑和提示，主动移除后其余行可保存', async () => {
    const wrapper = await picker()
    await selectMotor(wrapper)
    await draft(wrapper).get('input[aria-label="采购数量"]').setValue('3.000')
    await wrapper.findAll('input[aria-label="选择 2199000001"]')[1]!.setValue(true)
    await draft(wrapper, '检测单元').get('input[aria-label="采购数量"]').setValue('2.000')
    await draft(wrapper, '检测单元').get('input[aria-label="含税单价（元）"]').setValue('20.00')
    await wrapper.get('input[aria-label="选择 2199000002"]').setValue(true)
    await draft(wrapper, '输送单元', '2199000002').get('input[aria-label="采购数量"]').setValue('1.000')
    await draft(wrapper, '输送单元', '2199000002').get('input[aria-label="含税单价（元）"]').setValue('8.00')
    await supplier(wrapper)
    demand = demand.filter(row => row.bom_line !== 101)
      .map(row => row.bom_line === 102 ? { ...row, is_active: false } : row)
    await button(wrapper, '刷新缺料').trigger('click')
    await flushPromises()
    expect(wrapper.findAll('.draft-item')).toHaveLength(3)
    for (const [unit, quantity, price] of [['输送单元', '3.000', '10.20'], ['检测单元', '2.000', '20.00']]) {
      expect(draft(wrapper, unit).text()).toContain('当前已无缺料或物料停用，请移除此项。')
      expect(draft(wrapper, unit).get<HTMLInputElement>('input[aria-label="采购数量"]').element.value).toBe(quantity)
      expect(draft(wrapper, unit).get<HTMLInputElement>('input[aria-label="含税单价（元）"]').element.value).toBe(price)
    }
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(write).not.toHaveBeenCalled()
    await wrapper.get('button[aria-label="移除 2199000001 输送单元"]').trigger('click')
    expect(draft(wrapper, '检测单元').get<HTMLInputElement>('input[aria-label="采购数量"]').element.value).toBe('2.000')
    await wrapper.get('button[aria-label="移除 2199000001 检测单元"]').trigger('click')
    expect(wrapper.findAll('.draft-item')).toHaveLength(1)
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(write).toHaveBeenCalledTimes(1)
    expect(vi.mocked(write).mock.calls[0]![1]).toEqual(expect.objectContaining({
      lines: [{ item: 2, bom_line: 103, quantity: '1.000', unit_price: '8.00' }],
    }))
  })

  it('连续提交仅发一次，网络失败后保留草稿并复用相同幂等键重试', async () => {
    let reject!: (error: Error) => void
    const pending = new Promise<Row>((_resolve, rejectPromise) => { reject = rejectPromise })
    vi.mocked(write).mockReturnValueOnce(pending)
    const wrapper = await picker()
    await selectMotor(wrapper)
    await supplier(wrapper)
    await wrapper.get('form').trigger('submit')
    await wrapper.get('form').trigger('submit')
    expect(write).toHaveBeenCalledTimes(1)
    const first = vi.mocked(write).mock.calls[0]!
    reject(new Error('网络中断，请重试'))
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('网络中断，请重试')
    expect(draft(wrapper).get<HTMLInputElement>('input[aria-label="含税单价（元）"]').element.value).toBe('10.20')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(write).toHaveBeenCalledTimes(2)
    expect(vi.mocked(write).mock.calls[1]).toEqual(first)
    expect(wrapper.emitted('saved')).toHaveLength(1)
  })

  it('点击物料行非勾选框区域可切换选中；勾选框冒泡点击和展开列点击不会重复触发切换', async () => {
    const wrapper = await picker()
    const checkbox = () => wrapper.findAll<HTMLInputElement>('input[aria-label="选择 2199000001"]')[0]!
    await wrapper.findAll('.material-name')[0]!.trigger('click')
    expect(checkbox().element.checked).toBe(true)
    expect(wrapper.findAll('.draft-item')).toHaveLength(1)
    await wrapper.findAll('.material-name')[0]!.trigger('click')
    expect(checkbox().element.checked).toBe(false)
    expect(wrapper.findAll('.draft-item')).toHaveLength(0)
    await checkbox().setValue(true)
    expect(wrapper.findAll('.draft-item')).toHaveLength(1)
    checkbox().element.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    await nextTick()
    expect(wrapper.findAll('.draft-item')).toHaveLength(1)
    const expandCell = wrapper.findAll('tbody tr')[0]!.findAll('td')[1]!  // 选择列后的展开列
    await expandCell.trigger('click')
    expect(wrapper.findAll('.draft-item')).toHaveLength(1)
  })

  it('移动端跳转按钮在选料区与采购草稿之间滚动', async () => {
    const wrapper = await picker()
    const scrollSpy = vi.spyOn(Element.prototype, 'scrollIntoView')
    await selectMotor(wrapper)
    const draftJump = wrapper.findAll('button').find(value => value.text() === '采购草稿 ↓')!
    await draftJump.trigger('click')
    expect(scrollSpy).toHaveBeenCalledTimes(1)
    const backJump = wrapper.findAll('button').find(value => value.text() === '← 返回选料')!
    await backJump.trigger('click')
    expect(scrollSpy).toHaveBeenCalledTimes(2)
  })

  it('采购权限取兼任岗位并集，失去采购岗位后已打开的表单也不能提交', async () => {
    user.value = { id: 7, roles: ['mechanical_engineer'] }
    const wrapper = await picker()
    expect(wrapper.find('section[aria-label="从 BOM 多选下单"]').exists()).toBe(false)
    user.value = { id: 7, roles: ['mechanical_engineer', 'purchaser'] }
    await flushPromises()
    await selectMotor(wrapper)
    await supplier(wrapper)
    const oldForm = wrapper.get('form')
    user.value = { id: 7, roles: ['mechanical_engineer', 'finance', 'production_manager'] }
    await oldForm.trigger('submit')
    await flushPromises()
    expect(write).not.toHaveBeenCalled()
    expect(wrapper.find('section[aria-label="从 BOM 多选下单"]').exists()).toBe(false)
  })

  it('同物料多单元：出现组标题与合计数量，组价写入各行，单独定价不被组价覆盖，提交仍逐 bom_line', async () => {
    const wrapper = await picker()
    await selectMotor(wrapper)
    expect(wrapper.find('.draft-group-head').exists()).toBe(false)
    await wrapper.findAll('input[aria-label="选择 2199000001"]')[1]!.setValue(true)
    const head = wrapper.get('[aria-label="物料组 2199000001"] .draft-group-head')
    expect(head.text()).toContain('伺服电机')
    expect(head.text()).toContain('2 个单元')
    expect(head.text()).toContain('合计 16 件')
    const rowPrice = (unit: string) => draft(wrapper, unit).get<HTMLInputElement>('input[aria-label="含税单价（元）"]')
    expect(rowPrice('检测单元').element.value).toBe('10.20')
    const group = wrapper.get<HTMLInputElement>('input[aria-label="2199000001 组含税单价（元）"]')
    await group.setValue('11.00')
    expect(rowPrice('输送单元').element.value).toBe('11.00')
    expect(rowPrice('检测单元').element.value).toBe('11.00')
    await rowPrice('检测单元').setValue('12.00')
    expect(draft(wrapper, '检测单元').text()).toContain('单独定价')
    await group.setValue('13.00')
    expect(rowPrice('输送单元').element.value).toBe('13.00')
    expect(rowPrice('检测单元').element.value).toBe('12.00')
    await draft(wrapper, '检测单元').get('input[aria-label="采购数量"]').setValue('9.000')
    expect(draft(wrapper, '检测单元').text()).toContain('超过当前缺料')
    expect(draft(wrapper).text()).not.toContain('超过当前缺料')
    await draft(wrapper, '检测单元').get('input[aria-label="采购数量"]').setValue('2.000')
    await supplier(wrapper)
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(vi.mocked(write).mock.calls[0]![1]).toEqual(expect.objectContaining({
      lines: [
        { item: 1, bom_line: 101, quantity: '8', unit_price: '13.00' },
        { item: 1, bom_line: 102, quantity: '2.000', unit_price: '12.00' },
      ],
    }))
  })

  it('移除组内最后一个单元时组标题消失，剩一个单元退回单行样式', async () => {
    const wrapper = await picker()
    await selectMotor(wrapper)
    await wrapper.findAll('input[aria-label="选择 2199000001"]')[1]!.setValue(true)
    expect(wrapper.find('.draft-group-head').exists()).toBe(true)
    await wrapper.get('button[aria-label="移除 2199000001 检测单元"]').trigger('click')
    expect(wrapper.find('.draft-group-head').exists()).toBe(false)
    await wrapper.get('button[aria-label="移除 2199000001 输送单元"]').trigger('click')
    expect(wrapper.findAll('.draft-item')).toHaveLength(0)
  })

  it('选料表默认按需求日期升序（无日期靠后），可切换为单元排序，并在物料列显示规格', async () => {
    demand = demand.map(row => ({ ...row, specification: `规格-${row.bom_line}`,
      required_date: row.bom_line === 103 ? '2020-01-02' : row.bom_line === 102 ? '2099-01-01' : '' }))
    const wrapper = await picker()
    const codes = () => wrapper.findAll('.material-name').map(value => value.text())
    expect(codes().slice(0, 3)).toEqual(['直线导轨', '伺服电机', '伺服电机'])
    expect(wrapper.findAll('.overdue-date').length).toBeGreaterThan(0)
    expect(wrapper.text()).toContain('2199000002 · 规格-103')
    await wrapper.get('select[aria-label="选料排序"]').setValue('unit')
    const rows = wrapper.findAll('tbody tr').map(value => value.text())
    expect(rows.findIndex(text => text.includes('夹紧单元'))).toBeLessThan(rows.findIndex(text => text.includes('输送单元')))
  })

  it('从 BOM 页打开时沿用该页的仅看缺料，保存后的提示写明采购单号并停留足够久', async () => {
    const withFilter = await picker({ projectId: 10, shortageOnly: true } as never)
    expect(withFilter.get<HTMLInputElement>('.inline-check input').element.checked).toBe(true)
    expect(withFilter.get('section[aria-label="从 BOM 多选下单"] h2').text()).toBe('从 BOM 多选下单')
    const plain = await picker()
    expect(plain.get<HTMLInputElement>('.inline-check input').element.checked).toBe(false)
    vi.mocked(write).mockResolvedValue({ id: 80, code: 'PO000080', status: 'draft' })
    await selectMotor(plain)
    await supplier(plain)
    await plain.get('form').trigger('submit')
    await flushPromises()
    expect(plain.emitted('saved')).toHaveLength(1)
    expect(document.body.textContent).toContain('PO000080')
  })
})
