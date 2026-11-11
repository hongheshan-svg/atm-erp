import { beforeEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createRouter, createMemoryHistory } from 'vue-router'
import WorkbenchPage from './WorkbenchPage.vue'
import TaskNotices from '../components/TaskNotices.vue'
import { read } from '../api'
import { today } from '../forms'
import { user } from '../session'
vi.mock('../api', () => ({ read: vi.fn() }))
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
  const wrapper = mount(WorkbenchPage, { global: { plugins: [ElementPlus, router], stubs: { TaskNotices: true } } })
  await flushPromises()
  return wrapper
}
const rows = (wrapper: any) => wrapper.get('.priority-table').findAll('.el-table__body-wrapper tbody tr')
beforeEach(() => { vi.clearAllMocks(); localStorage.clear(); user.value = { id: 7, roles: ['member'], display_name: '测试用户' }; vi.mocked(read).mockResolvedValue(data()) })

it.each([
  { roles: ['sales_manager'], visible: false },
  { roles: ['sales_manager', 'member'], visible: true },
  { roles: ['sales_manager', 'purchaser'], visible: true },
])('任务提醒仅向可访问项目的岗位展示，兼岗按并集判断：$roles', async ({ roles, visible }) => {
  user.value = { id: 7, roles }
  const wrapper = await render()
  expect(wrapper.findComponent(TaskNotices).exists()).toBe(visible)
  wrapper.unmount()
})

it('三个指标合并全部风险提示，分类入口直达完整列表', async () => {
  const wrapper = await render()
  expect(read).toHaveBeenCalledWith('/business/workbench/', { page_size: 5 })
  const metrics = wrapper.findAll('.work-metric')
  expect(metrics).toHaveLength(3)
  expect(metrics.map(metric => metric.get('span').text())).toEqual(['任务 / 到货逾期', '我的任务今日截止', '等待我审批'])
  // 已逾期 = 逾期任务 7 + 逾期采购 3 + 生产任务逾期 2；等待我审批 = 待批准采购 0 + 待核准预付款 1
  expect(wrapper.findAll('.work-metric strong').map(value => value.text())).toEqual(['12', '5', '1'])
  expect(metrics[0].element.tagName).toBe('DIV')
  const categories = wrapper.findAll('.work-category')
  expect(categories.every(entry => entry.element.tagName === 'A')).toBe(true)
  // 「我的待办」落到项目页的任务清单，不再只是一张项目列表。
  expect(categories.map(entry => entry.attributes('href'))).toEqual(['/projects?section=tasks', '/purchases', '/finance?section=reconciliations&project=all', '/finance?section=bank&project=all'])
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
  expect(wrapper.get('.priority-table').text()).not.toContain('下周任务')
  expect(wrapper.get('.work-ongoing').text()).toContain('下周任务')
  expect(wrapper.get('[aria-label="查看全部待批准采购"]').attributes('href')).toBe('/purchases')
  wrapper.unmount()
})

it('未到期任务直接展示项目、计划完成日期和继续处理入口，工程师不出现仓储资金入口', async () => {
  user.value = { id: 9, roles: ['mechanical_engineer'] }
  vi.mocked(read).mockResolvedValue({ tasks: bucket([{ id: 8, project: 4, project_name: '自动检测线', title: '机械设计', due_date: '2999-10-30' }]) })
  const wrapper = await render()
  expect(wrapper.get('.work-ongoing').text()).toContain('自动检测线')
  expect(wrapper.get('.work-ongoing').text()).toContain('计划完成日期：2999-10-30')
  expect(wrapper.get('[aria-label="继续处理机械设计"]').attributes('href')).toBe('/projects/4?tab=tasks&resource=tasks&focus=8')
  expect(wrapper.find('[aria-label="日常库存入口"]').exists()).toBe(false)
  expect(wrapper.text()).not.toContain('登记收付款')
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
  expect(wrapper.get('[aria-label="查看全部生产与售后派工"]').attributes('href')).toBe('/projects?section=tasks')
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

it('已结项/已验收项目的销售单不按交期标逾期，未签约与执行中仍标', async () => {
  vi.mocked(read).mockResolvedValue({
    sales: bucket([
      { id: 41, code: 'SO-41', name: '未签约', due_date: '2020-01-01', project_status: null },
      { id: 42, code: 'SO-42', name: '执行中', due_date: '2020-01-01', project_status: 'active' },
      { id: 43, code: 'SO-43', name: '已验收', due_date: '2020-01-01', project_status: 'warranty' },
      { id: 44, code: 'SO-44', name: '已结项', due_date: '2020-01-01', project_status: 'closed' },
    ]),
  })
  const wrapper = await render()
  expect(rows(wrapper).map((row: any) => row.findAll('a')[0].text())).toEqual(['SO-41', 'SO-42'])
  wrapper.unmount()
})

it('待结算优先显示到期金额并同时给出余额，本人申请的审批给出提示', async () => {
  user.value = { id: 7, roles: ['finance'], display_name: '测试用户' }
  vi.mocked(read).mockResolvedValue({
    settlements: bucket([
      { id: 1, title: '货款', kind: 'payable', balance: '1000.00', due_amount: '300.00', due_date: '2020-01-01', project_name: 'P' },
    ]),
    approvals: bucket([{ id: 3, code: 'PO-3', self_requested: true, due_date: '2020-01-01' }]),
  })
  const wrapper = await render()
  const text = wrapper.get('.priority-table').text()
  expect(text).toContain('到期待付 ¥ 300.00 · 余额 ¥ 1,000.00')
  expect(text).toContain('本人申请，需填写例外原因')
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

it('交接待办：待启动项目、已批准待下单、缺料项目与逾期任务合计', async () => {
  vi.mocked(read).mockResolvedValue({
    tasks: { ...bucket([]), overdue_count: 0, overdue_total: 1, today_count: 0 },
    supervised_tasks: bucket([{ id: 21, project: 5, title: '电气图纸确认', due_date: '2020-01-01' }]),
    handover_projects: bucket([{ id: 82, project: 82, code: 'ATM2682', title: 'ATM2682 新上料线', project_name: '新上料线', due_date: '2999-01-01', missing: ['任务计划', 'BOM', '预算'] }]),
    approved_purchases: bucket([{ id: 49, code: 'PO000049', project: 82, project_name: '新上料线', status: 'approved' }]),
    shortage_projects: bucket([{ id: 81, project: 81, code: 'ATM2681', title: 'ATM2681 旧线', project_name: '旧线', shortage_lines: 3, due_date: '2999-02-01' }]),
  })
  const wrapper = await render()
  // 我负责确认的逾期任务计入「任务逾期」，与「今天要处理的」一致。
  expect(wrapper.findAll('.work-metric strong')[0]!.text()).toBe('1')
  expect(wrapper.findAll('.work-metric small')[0]!.text()).toContain('我负责确认的任务')
  const items = rows(wrapper).map((row: any) => [row.findAll('a')[0].text(), row.get('.work-status').text(), row.findAll('a')[0].attributes('href')])
  expect(items).toEqual([
    ['电气图纸确认', '已逾期', '/projects/5?tab=tasks&resource=tasks&focus=21'],
    ['ATM2682 新上料线', '待启动', '/projects/82'],
    ['PO000049', '待下单', '/projects/82?tab=purchases&resource=purchases&focus=49'],
    ['ATM2681 旧线', '缺料', '/bom?project=81&view=purchase'],
  ])
  expect(wrapper.text()).toContain('缺任务计划、BOM、预算')
  expect(wrapper.text()).toContain('缺料 3 行')
  for (const label of ['待启动项目', '已批准待下单', '缺料待采购项目']) expect(wrapper.find(`[aria-label="查看全部${label}"]`).exists()).toBe(true)
  wrapper.unmount()
})

it('销售经理看到本人合同的逾期应收和已报价待签约，同一销售单只列一次', async () => {
  user.value = { id: 7, roles: ['sales_manager'], display_name: '销售' }
  const quoted = { id: 51, code: 'SO-51', name: '报价单', customer_name: '丙客户', status: 'quoted', due_date: '2999-01-01' }
  vi.mocked(read).mockResolvedValue({
    sales: bucket([quoted]),
    quoted_sales: bucket([quoted]),
    sale_receivables: bucket([{ id: 9, kind: 'receivable', title: '预付款', sale_code: 'SO-50', partner_name: '宁德客户', project_name: '上料线', balance: '150000.00', due_date: '2020-01-01' }]),
  })
  const wrapper = await render()
  const items = rows(wrapper).map((row: any) => [row.findAll('a')[0].text(), row.get('.work-status').text(), row.findAll('a')[0].attributes('href')])
  expect(items).toEqual([
    ['预付款', '已逾期', '/sales?search=SO-50'],
    ['SO-51', '待签约', '/sales?search=SO-51'],
  ])
  expect(wrapper.text()).toContain('宁德客户 · 上料线 · 待收余额 ¥ 150,000.00')
  expect(wrapper.get('[aria-label="查看全部我的合同逾期应收"]').attributes('href')).toBe('/sales?search=')
  wrapper.unmount()
})

it('手机宽度：待办表不渲染序号和类型列，类型并入事项副行，且不设最大高度', async () => {
  const original = window.matchMedia
  window.matchMedia = ((query: string) => ({ matches: true, media: query, addEventListener: vi.fn(), removeEventListener: vi.fn() })) as unknown as typeof window.matchMedia
  try {
    user.value = { id: 7, roles: ['admin'], display_name: '测试用户' }
    const wrapper = await render()
    const table = wrapper.get('.priority-table')
    const headers = table.findAll('.el-table__header th').map((th: any) => th.text())
    expect(headers).not.toContain('类型')
    expect(headers).not.toContain('序号')
    expect(headers).not.toContain('截止 / 到期日期')
    expect(table.find('.el-table__body-wrapper').text()).toContain('采购明细逾期')
    wrapper.unmount()
  } finally { window.matchMedia = original }
})
