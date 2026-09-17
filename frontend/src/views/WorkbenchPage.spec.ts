import { beforeEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createRouter, createMemoryHistory } from 'vue-router'
import WorkbenchPage from './WorkbenchPage.vue'
import { read } from '../api'
import { today } from '../forms'
vi.mock('../api', () => ({ read: vi.fn() }))
vi.mock('../session', () => ({ user: { display_name: '测试用户' } }))
const bucket = (results: any[], count = results.length) => ({ count, page: 1, results })
const day = today()
const data = () => ({
  tasks: { ...bucket([], 12), overdue_count: 7, today_count: 5 },
  production_tasks: { ...bucket([]), overdue_count: 2 },
  overdue_purchases: bucket([{ id: 8, code: 'PO-8', project: 4, next_delivery_date: '2020-01-01' }], 3),
  drafts: bucket([]),
  bank_records: bucket([{ id: 1, counterparty: '测试客户', reference: 'BANK-1', amount: '200', remaining_amount: '100', date: '2026-09-10', needs_review: true }], 389),
  prepayments: bucket([{ id: 2, code: 'REC-2' }]),
})
async function render() {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/:pathMatch(.*)*', component: { template: '<div />' } }] })
  const wrapper = mount(WorkbenchPage, { global: { plugins: [ElementPlus, router] } })
  await flushPromises()
  return wrapper
}
const rows = (wrapper: any) => wrapper.get('.priority-table').findAll('.el-table__body-wrapper tbody tr')
beforeEach(() => { vi.clearAllMocks(); vi.mocked(read).mockResolvedValue(data()) })

it('三个指标合并全部风险提示，分类入口直达完整列表', async () => {
  const wrapper = await render()
  expect(read).toHaveBeenCalledWith('/business/workbench/', { page_size: 5 })
  const metrics = wrapper.findAll('.work-metric')
  expect(metrics).toHaveLength(3)
  expect(metrics.map(metric => metric.get('span').text())).toEqual(['已逾期', '今日到期', '等待我审批'])
  // 已逾期 = 逾期任务 7 + 逾期采购 3 + 生产任务逾期 2；等待我审批 = 待批准采购 0 + 待核准预付款 1
  expect(wrapper.findAll('.work-metric strong').map(value => value.text())).toEqual(['12', '5', '1'])
  expect(metrics[0].element.tagName).toBe('DIV')
  const categories = wrapper.findAll('.work-category')
  expect(categories.every(entry => entry.element.tagName === 'A')).toBe(true)
  expect(categories.map(entry => entry.attributes('href'))).toEqual(['/projects', '/purchases', '/finance?section=reconciliations&project=all', '/finance?section=bank&project=all'])
  const bank = wrapper.get('[aria-label="查看全部银行待认领 / 匹配"]')
  expect(bank.text()).toContain('银行待认领 / 匹配')
  expect(bank.text()).toContain('389')
  expect(wrapper.find('[aria-label="查看全部采购草稿"]').exists()).toBe(false)
  expect(wrapper.get('.work-idle').text()).toBe('生产与售后派工 等 2 类当前没有待办')
  wrapper.unmount()
})

it('今天要处理的表格保留金额格式化并去掉页内筛选与卡片网格', async () => {
  const wrapper = await render()
  expect(wrapper.get('#priority-heading').text()).toBe('今天要处理的')
  const priority = wrapper.get('.priority-table')
  expect(priority.text()).toContain('测试客户')
  expect(priority.text()).toContain('待匹配')
  expect(priority.text()).toContain('100.00')
  expect(rows(wrapper).map((row: any) => row.get('.work-status').text())).toEqual(['已逾期', '待审批', '待核实户名'])
  for (const gone of ['.work-filters', '.work-card', '.workbench-grid', '.work-pagination', '#workbench-categories', '.work-empty-toggle']) {
    expect(wrapper.find(gone).exists()).toBe(false)
  }
  expect(wrapper.findComponent({ name: 'ElPagination' }).exists()).toBe(false)
  expect(wrapper.findComponent({ name: 'ElSwitch' }).exists()).toBe(false)
  wrapper.unmount()
})

it('优先事项按逾期、今日到期、待审批排序并最多展示 7 条', async () => {
  vi.mocked(read).mockResolvedValue({
    tasks: {
      ...bucket([
        { id: 4, project: 1, title: '逾期四', due_date: '2020-01-04' },
        { id: 1, project: 1, title: '逾期一', due_date: '2020-01-01' },
        { id: 2, project: 1, title: '逾期二', due_date: '2020-01-02' },
        { id: 3, project: 1, title: '逾期三', due_date: '2020-01-03' },
        { id: 5, project: 1, title: '今日一', due_date: day },
        { id: 6, project: 1, title: '今日二', due_date: day },
        { id: 7, project: 1, title: '下周任务', due_date: '2999-01-01' },
      ]),
      overdue_count: 4,
      today_count: 2,
    },
    approvals: bucket([{ id: 21, project: 2, code: 'PO-21' }, { id: 22, project: 2, code: 'PO-22' }]),
  })
  const wrapper = await render()
  expect(rows(wrapper).map((row: any) => row.findAll('a')[0].text())).toEqual(['逾期一', '逾期二', '逾期三', '逾期四', '今日一', '今日二', 'PO-21'])
  expect(wrapper.text()).not.toContain('下周任务')
  expect(wrapper.get('[aria-label="查看全部待批准采购"]').attributes('href')).toBe('/purchases')
  wrapper.unmount()
})

it('生产任务链接到任务，不重复列出本人和团队的同一逾期事项', async () => {
  const shared = { id: 12, project: 1, title: '装配跟进', due_date: '2020-01-01' }
  vi.mocked(read).mockResolvedValue({
    tasks: { ...bucket([shared]), overdue_count: 1, today_count: 0 },
    production_tasks: { ...bucket([shared, { id: 13, project: 2, title: '售后派工', due_date: '2020-01-02' }]), overdue_count: 2, today_count: 0 },
  })
  const wrapper = await render()
  expect(rows(wrapper)).toHaveLength(2)
  expect(wrapper.get('.priority-table').findAll('[aria-label="处理装配跟进"]')).toHaveLength(1)
  expect(rows(wrapper)[0].findAll('a')[0].attributes('href')).toBe('/projects/1?tab=tasks&resource=tasks&focus=12')
  expect(wrapper.get('[aria-label="查看全部生产与售后派工"]').attributes('href')).toBe('/projects')
  // 逾期任务 1 + 生产任务逾期 2 合并为一个指标
  expect(wrapper.findAll('.work-metric strong')[0].text()).toBe('3')
  wrapper.unmount()
})

it('逾期销售单进入优先事项并带单号跳转，分类入口清掉上次搜索', async () => {
  vi.mocked(read).mockResolvedValue({
    sales: bucket([
      { id: 31, code: 'SO-31', name: '逾期销售', customer_name: '甲客户', due_date: '2020-01-01' },
      { id: 32, code: 'SO-32', name: '未到期销售', customer_name: '乙客户', due_date: '2999-01-01' },
    ], 2),
  })
  const wrapper = await render()
  expect(rows(wrapper).map((row: any) => row.findAll('a')[0].text())).toEqual(['SO-31'])
  expect(rows(wrapper)[0].findAll('a')[0].attributes('href')).toBe('/sales?search=SO-31')
  expect(rows(wrapper)[0].get('.work-status').text()).toBe('已逾期')
  // 销售列表会恢复上次的搜索词，工作台入口必须显式清空，否则点进去是空列表
  expect(wrapper.get('[aria-label="查看全部我的销售订单"]').attributes('href')).toBe('/sales?search=')
  wrapper.unmount()
})

it('无待办时保持中性配色、空态文案与错误提示', async () => {
  vi.mocked(read).mockResolvedValue({ tasks: { ...bucket([]), overdue_count: 0, today_count: 0 } })
  const wrapper = await render()
  // 指标为 0 时不标成危险色
  expect(wrapper.findAll('.work-metric').map(metric => metric.classes().join(' '))).toEqual(['work-metric', 'work-metric'])
  expect(wrapper.get('.work-categories').text()).toContain('当前没有待处理事项。')
  expect(wrapper.find('.work-idle').exists()).toBe(false)
  expect(wrapper.text()).toContain('今天没有需要优先处理的事项')
  vi.mocked(read).mockRejectedValueOnce(new Error('网络异常'))
  await wrapper.get('.work-refresh button').trigger('click')
  await flushPromises()
  expect(wrapper.get('[role="alert"]').text()).toContain('网络异常')
  wrapper.unmount()
})

it('刷新期间禁止重复请求，过期响应不会覆盖最新数据', async () => {
  let resolve!: (value: any) => void
  vi.mocked(read).mockReturnValueOnce(new Promise(r => { resolve = r }))
  const wrapper = await render()
  expect(wrapper.find('[aria-label="正在加载工作台"]').exists()).toBe(true)
  // 加载未结束时刷新按钮禁用，界面上无法叠加请求
  expect(wrapper.get('.work-refresh button').attributes('disabled')).toBeDefined()
  vi.mocked(read).mockResolvedValueOnce({ ...data(), bank_records: bucket([{ id: 3, counterparty: '最新结果', amount: 1, remaining_amount: 1, needs_review: true }]) })
  wrapper.findComponent({ name: 'ElButton' }).vm.$emit('click', new MouseEvent('click'))
  await flushPromises()
  resolve({ ...data(), bank_records: bucket([{ id: 4, counterparty: '过期结果', amount: 1, remaining_amount: 1, needs_review: true }]) })
  await flushPromises()
  expect(read).toHaveBeenCalledTimes(2)
  expect(wrapper.text()).toContain('最新结果')
  expect(wrapper.text()).not.toContain('过期结果')
  wrapper.unmount()
})
