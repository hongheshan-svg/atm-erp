import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { all, read } from '../api'
import { actionCommand, actionNames, columns, createCommand, projectDueFlag, readinessPath, taskCompletionFlag, taskDueFlag, taskProgressLabel, taskStatusLabel } from './projects'
import { addDays, backSchedule, daysUntil, milestoneTemplateCommand, taskSyncHint, taskElapsedLabel, taskVarianceLabel } from './milestones'
import { today } from '../forms'
import { user } from '../session'
import { payload } from '../forms'
vi.mock('../api', () => ({ all: vi.fn(), read: vi.fn() }))
const stages = ['design', 'purchase', 'assembly', 'test', 'shipping', 'site'].map(value => ({ value, label: value }))
const nodes = [
  { kind: 'design', milestone: 'design_3d', title: '3D画图', description: '图档' },
  { kind: 'purchase', milestone: 'purchase_long_lead', title: '长交期', description: '交期确认' },
  { kind: 'shipping', milestone: 'shipping_dispatch', title: '发货', description: '实际发货', system_managed: true },
]
beforeEach(() => {
  vi.clearAllMocks()
  user.value = { id: 1, roles: ['manager'] }
  vi.mocked(all).mockResolvedValue([{ id: 1, username: 'manager', display_name: '张工', roles: ['manager'] }])
  vi.mocked(read).mockImplementation(async path => path.includes('milestone-template') ? {
    stages, nodes, existing: ['design_3d'], can_generate: true, assignee: 1,
  } : { id: 7, manager: 1, members: [], can_manage: true, status: 'active' })
})
afterEach(() => { user.value = null })
it('生成模板只补缺失节点，允许移除和新增自定义任务并锁定项目', async () => {
  const command = await milestoneTemplateCommand(7)
  expect(command.initial?.lines.map((row: any) => row.milestone)).toEqual(['purchase_long_lead', 'shipping_dispatch'])
  const lines = command.fields.find(field => field.key === 'lines')!
  expect(lines.dense).toBe(true)
  const fields = lines.fields!
  // 批量工具只列还有待生成节点的阶段；已存在的 design 阶段不再给日期框。
  expect(command.fields.filter(field => field.key.startsWith('stage_due_')).map(field => field.key)).toEqual(['stage_due_purchase', 'stage_due_shipping'])
  const select = fields.find(field => field.key === 'milestone')!
  expect(select.optionsFor?.({ kind: 'purchase' })).toEqual([{ value: 'purchase_long_lead', label: '长交期' }])
  expect(select.optionsFor?.({ kind: 'shipping' })?.[0]?.label).toContain('业务自动同步')
  const data = payload(command.fields, { lines: [{ kind: 'site', title: '培训', assignees: [1], due_date: '2026-12-20' }] })
  expect(command.prepare?.({ ...data, project: 99 })).toEqual({ project: 7, lines: [{ kind: 'site', title: '培训', assignees: [1], due_date: '2026-12-20' }] })
  // 阶段日期只补空行；统一执行人只替换仍是默认（项目经理）的行，批量字段本身不提交。
  expect(command.prepare?.({
    stage_due_purchase: '2026-11-30', batch_assignees: [5, 6],
    lines: [
      { kind: 'purchase', milestone: 'purchase_long_lead', assignees: [1], due_date: '' },
      { kind: 'purchase', title: '自定义', assignees: [9], due_date: '2026-12-01' },
      { kind: 'shipping', milestone: 'shipping_dispatch', assignees: [1], due_date: '' },
    ],
  })).toEqual({ project: 7, lines: [
    { kind: 'purchase', milestone: 'purchase_long_lead', assignees: [5, 6], due_date: '2026-11-30' },
    { kind: 'purchase', title: '自定义', assignees: [9], due_date: '2026-12-01' },
    { kind: 'shipping', milestone: 'shipping_dispatch', assignees: [5, 6], due_date: '' },
  ] })
  expect(() => command.prepare?.({ lines: [] })).toThrow('至少保留')
})
it('单项任务支持六阶段和联动节点，自动节点不显示手动完成及工时', async () => {
  const command = await createCommand('tasks', 7)
  expect(command.fields.find(field => field.key === 'kind')?.options).toEqual(stages)
  expect(command.fields.find(field => field.key === 'milestone')?.optionsFor?.({ kind: 'design' })).toHaveLength(1)
  const row = { id: 1, status: 'open', kind: 'shipping', system_managed: true, can_manage: true, can_cancel: true, can_reopen: false }
  expect(actionNames('tasks', row)).toEqual(['查看工时', '重新分配', '取消任务'])
  expect(actionNames('tasks', { ...row, status: 'done', can_cancel: false })).toEqual(['查看工时'])
})
it('调整负责人保留原日期，也可明确清空日期', async () => {
  const command = await actionCommand('tasks', { id: 4, project: 7, assignee: 1, due_date: '2026-12-20' }, '重新分配')
  expect(command.initial).toEqual({ assignees: [1], due_date: '2026-12-20' })
  expect(command.prepare?.({ assignees: [1], reason: '日期待定' })).toEqual({ assignees: [1], reason: '日期待定', due_date: null })
})

it('共同执行人只查看，指定主管有完成和工时入口，自动汇总仍指向实际交付', async () => {
  user.value = { id: 8, roles: ['member'] }
  const row = { id: 4, project: 7, assignee: 1, assignees: [1, 8], kind: 'design', status: 'open', can_manage: false, can_confirm: true }
  expect(actionNames('tasks', row)).toEqual(['查看工时', '登记工时', '开始任务', '完成任务'])
  expect(actionNames('tasks', { ...row, can_confirm: false })).toEqual(['查看工时'])
  const command = await actionCommand('tasks', row, '登记工时')
  expect(command.fields.some(field => field.key === 'user')).toBe(true)
  expect(command.initial?.user).toBe(8)
  expect(taskSyncHint({ system_managed: true, milestone: 'shipping_dispatch' })).toContain('实际发货')
  expect(taskSyncHint({ system_managed: true, milestone: 'site_install' })).toContain('批次安装')
  expect(taskSyncHint({ system_managed: true, milestone: 'site_acceptance' })).toContain('实际验收')
  expect(taskSyncHint(row)).toBe('')
})
it('重新分配保留所有当前执行人且使用可搜索多选', async () => {
  vi.mocked(all).mockResolvedValue([
    { id: 1, roles: ['manager'], display_name: '张工' },
    { id: 2, roles: ['admin'], display_name: '李工' },
  ])
  const command = await actionCommand('tasks', { id: 4, project: 7, assignee: 1, assignees: [1, 2] }, '重新分配')
  expect(command.initial?.assignees).toEqual([1, 2])
  expect(command.fields.find(field => field.key === 'assignees')).toMatchObject({ type: 'multi', searchableMulti: true })
  const template = await milestoneTemplateCommand(7)
  expect(template.initial?.lines.every((row: any) => row.assignees.length === 1 && row.assignees[0] === 1)).toBe(true)
})

it('计划与实际日期分列，完成只提交日期不要求工时，历史补录保留空值', async () => {
  const task = { id: 4, project: 7, assignee: 1, kind: 'design', status: 'open', can_manage: true, can_confirm: true }
  const command = await actionCommand('tasks', task, '完成任务')
  expect(command.fields.map(field => field.key)).toEqual(['started_date', 'completed_date', 'reason'])
  expect(command.initial?.completed_date).toMatch(/^\d{4}-\d{2}-\d{2}$/)
  const plan = columns.tasks!.findIndex(column => column.key === 'due_date')
  expect(columns.tasks![plan]?.label).toBe('计划完成日期')
  expect(columns.tasks![plan + 1]?.label).toBe('实际完成日期')
  const done = { ...task, status: 'done', completed_date: null }
  expect(actionNames('tasks', done)).toContain('补录完成日期')
  const backfill = await actionCommand('tasks', done, '补录完成日期')
  expect(backfill.initial?.completed_date).toBe('')
  expect(backfill.prepare?.({ completed_date: '2026-11-01', reason: '核对图纸' })).toEqual({ completed_date: '2026-11-01', expected_completed_date: null, reason: '核对图纸' })
  expect(actionNames('tasks', { ...done, completed_date: '2026-11-01' })).toContain('更正完成日期')
  expect(actionNames('tasks', { ...done, system_managed: true })).not.toContain('补录完成日期')
  user.value = { id: 1, roles: ['member'] }
  expect(actionNames('tasks', { ...done, can_manage: false, can_confirm: false })).not.toContain('补录完成日期')
})

it('开始后显示进行历时，补录与更正有明确入口且不生成工时', async () => {
  const row = { id: 4, project: 7, assignee: 1, kind: 'design', status: 'open', can_manage: true, can_confirm: true }
  const start = await actionCommand('tasks', row, '开始任务')
  expect(start.path).toBe('/business/tasks/4/start/')
  expect(start.fields.map(field => field.key)).toEqual(['started_date', 'reason'])
  const started = { ...row, started_date: '2026-11-01', elapsed_days: 9, schedule_variance_days: 2 }
  expect(actionNames('tasks', started)).not.toContain('开始任务')
  expect(actionNames('tasks', started)).toContain('更正开始日期')
  expect(taskElapsedLabel(started)).toBe('9 天（进行中）')
  expect(taskVarianceLabel(started)).toBe('已逾期 2 天')
  expect(taskVarianceLabel({ ...started, status: 'done', schedule_variance_days: -2 })).toBe('提前 2 天')
  expect(taskVarianceLabel({ ...started, status: 'done', schedule_variance_days: 0 })).toBe('按期完成')
  expect(taskElapsedLabel({ ...row, status: 'done' })).toBe('待补开始日期')
  const amend = await actionCommand('tasks', started, '更正开始日期')
  expect(amend.prepare?.({ started_date: '2026-10-31', reason: '核对' })).toMatchObject({ expected_started_date: '2026-11-01' })
  expect((await actionCommand('tasks', started, '完成任务')).fields.map(field => field.key)).toEqual(['completed_date', 'reason'])
  expect(actionNames('tasks', { ...row, system_managed: true })).not.toContain('开始任务')
})
it('项目列表任务进度：给出完成数与百分比，未安排或无统计时不显示 0/0', () => {
  expect(columns.projects!.map(column => column.label)).toContain('任务进度')
  expect(taskProgressLabel({ task_total: 20, task_done: 5 })).toBe('5 / 20（25%）')
  expect(taskProgressLabel({ task_total: 3, task_done: 3 })).toBe('3 / 3（100%）')
  expect(taskProgressLabel({ task_total: 0, task_done: 0 })).toBe('未安排任务')
  expect(taskProgressLabel({})).toBe('—')
})
it('首次生成与补充分开命名，节点已全部生成时不再给出可提交的对话框', async () => {
  const template = (existing: string[]) => vi.mocked(read).mockImplementation(async path => path.includes('milestone-template')
    ? { stages, nodes, existing, can_generate: true, assignee: 1 }
    : { id: 7, manager: 1, members: [], can_manage: true, status: 'active' })
  template([])
  const first = await milestoneTemplateCommand(7)
  expect([first.title, first.submitLabel, first.blocked]).toEqual(['生成六阶段里程碑', '确认生成里程碑', undefined])
  template(['design_3d'])
  const supplement = await milestoneTemplateCommand(7)
  expect([supplement.title, supplement.submitLabel]).toEqual(['补充里程碑节点（缺 2 个）', '确认补充节点'])
  template(nodes.map(node => node.milestone))
  const complete = await milestoneTemplateCommand(7)
  expect(complete.blocked).toContain('请用「新建任务」')
  expect(complete.alternatives).toBeUndefined()
})
it('里程碑行固定列宽，并可按计划交期倒排各阶段日期且不晚于交期', async () => {
  const due = addDays(today(), 80)
  vi.mocked(read).mockImplementation(async path => path.includes('milestone-template')
    ? { stages, nodes, existing: [], can_generate: true, assignee: 1 }
    : { id: 7, manager: 1, members: [], can_manage: true, status: 'active', due_date: due })
  const command = await milestoneTemplateCommand(7)
  const widths = Object.fromEntries(command.fields.find(field => field.key === 'lines')!.fields!.map(field => [field.key, field.width]))
  expect(widths).toEqual({ kind: 110, milestone: 130, title: 150, discipline: 100, assignees: 200, due_date: 150, description: undefined })
  const alternative = command.alternatives?.find(item => item.label === '按计划交期倒排')
  expect(alternative).toBeTruthy()
  const scheduled = await alternative!.open()
  expect(scheduled.initial?.lines).toEqual(command.initial?.lines)
  // 阶段按设计→采购→发货累计推进，最后一个阶段不晚于项目计划交期。
  expect(scheduled.initial?.stage_due_design).toBe(addDays(today(), 20))
  expect(scheduled.initial?.stage_due_purchase).toBe(addDays(today(), 40))
  expect(scheduled.initial?.stage_due_shipping).toBe(addDays(today(), 74))
  expect(scheduled.initial?.stage_due_shipping <= due).toBe(true)
  expect(scheduled.notice?.text).toContain(due)
  expect(backSchedule('2026-03-11', ['design', 'site'], '2026-01-01')).toEqual({ stage_due_design: '2026-01-18', stage_due_site: '2026-03-11' })
  expect(backSchedule('2025-12-31', ['design'], '2026-01-01')).toEqual({})
  // 交期已过或未设置时不提供倒排。
  vi.mocked(read).mockImplementation(async path => path.includes('milestone-template')
    ? { stages, nodes, existing: [], can_generate: true, assignee: 1 }
    : { id: 7, manager: 1, members: [], can_manage: true, status: 'active', due_date: addDays(today(), -1) })
  expect((await milestoneTemplateCommand(7)).alternatives).toBeUndefined()
})
it('已开工任务显示进行中，逾期与延期天数并入日期格，未逾期给出剩余天数', () => {
  const open = { status: 'open', kind: 'design', due_date: addDays(today(), 5), schedule_variance_days: 0 }
  expect(taskStatusLabel(open)).toBe('待完成')
  expect(taskStatusLabel({ ...open, started_date: today() })).toBe('进行中')
  expect(taskStatusLabel({ ...open, started_date: today(), system_managed: true })).toBe('待完成')
  expect(taskStatusLabel({ ...open, status: 'done', started_date: today() })).toBe('已完成')
  expect(taskVarianceLabel(open)).toBe('剩 5 天')
  expect(taskVarianceLabel({ ...open, due_date: today() })).toBe('今天到期')
  expect(taskDueFlag(open)).toBeUndefined()
  expect(taskDueFlag({ ...open, schedule_variance_days: 10 })).toEqual({ text: '已逾期 10 天', risk: true })
  expect(taskCompletionFlag({ status: 'done', schedule_variance_days: 10 })).toEqual({ text: '延期 10 天', risk: true })
  expect(taskCompletionFlag({ status: 'done', schedule_variance_days: -3 })).toEqual({ text: '提前 3 天' })
  expect(taskCompletionFlag({ status: 'done', schedule_variance_days: 0 })).toBeUndefined()
  // 实际完成日期在计划日期格的第二行，延期/提前跟在它后面。
  expect(taskDueFlag({ status: 'done', schedule_variance_days: 10 })).toEqual({ text: '延期 10 天', risk: true })
  const status = columns.tasks!.find(column => column.key === 'status')!
  expect(status.format?.({ ...open, started_date: today() })).toBe('进行中')
  expect(daysUntil('2026-03-01', '2026-02-27')).toBe(2)
})
it('项目列表在进度下标出逾期任务数，交期下给出剩余或逾期天数', () => {
  const progress = columns.projects!.find(column => column.key === 'task_done')!
  expect(progress.flag?.({ task_total: 2, task_done: 0, task_overdue: 2 })).toEqual({ text: '2 项逾期', risk: true })
  expect(progress.flag?.({ task_total: 2, task_done: 0, task_overdue: 0 })).toBeUndefined()
  expect(projectDueFlag({ status: 'active', due_date: addDays(today(), 75) })).toEqual({ text: '剩 75 天' })
  expect(projectDueFlag({ status: 'delivering', due_date: addDays(today(), -3) })).toEqual({ text: '已逾期 3 天', risk: true })
  expect(projectDueFlag({ status: 'closed', due_date: addDays(today(), -3) })).toBeUndefined()
})
it('开始、完成、登记工时和验收的说明选填且不预填，纠错动作仍必须写原因', async () => {
  const row = { id: 4, project: 7, assignee: 1, kind: 'design', status: 'open', can_manage: true, can_confirm: true }
  const start = await actionCommand('tasks', row, '开始任务')
  expect(start.fields.find(field => field.key === 'reason')).toMatchObject({ label: '开始说明', optional: true })
  expect(start.initial?.reason).toBeUndefined()
  const complete = await actionCommand('tasks', row, '完成任务')
  expect(complete.fields.find(field => field.key === 'reason')).toMatchObject({ label: '完成说明', optional: true })
  const time = await actionCommand('tasks', row, '登记工时')
  expect(time.fields.find(field => field.key === 'reason')).toMatchObject({ label: '工作内容', optional: true })
  const accept = await actionCommand('deliveries', { id: 3, project: 7, stage: 'awaiting_acceptance' }, '验收')
  expect(accept.fields.find(field => field.key === 'reason')).toMatchObject({ label: '验收说明', optional: true })
  expect(accept.blocked).toBeUndefined()
  const amend = await actionCommand('tasks', { ...row, status: 'done', completed_date: '2026-11-01' }, '更正完成日期')
  expect(amend.fields.find(field => field.key === 'reason')).toMatchObject({ label: '原因 / 说明', optional: false })
  const installing = await actionCommand('deliveries', { id: 3, project: 7, stage: 'installing' }, '验收')
  expect(installing.blocked).toContain('安装任务尚未全部完成')
  expect(installing.links).toEqual([{ label: '查看安装任务', path: '/projects/7?tab=tasks&section=tasks&phase=site' }])
})
it('项目经理可编辑任务名称和完成要求，业务同步节点不提供', async () => {
  const row = { id: 4, project: 7, title: '3D画图', description: '图档', kind: 'design', status: 'open', can_manage: true }
  expect(actionNames('tasks', row)).toContain('编辑任务')
  expect(actionNames('tasks', { ...row, status: 'cancelled' })).not.toContain('编辑任务')
  expect(actionNames('tasks', { ...row, system_managed: true })).not.toContain('编辑任务')
  const command = await actionCommand('tasks', row, '编辑任务')
  expect(command.path).toBe('/business/tasks/4/edit/')
  expect(command.fields.map(field => field.key)).toEqual(['title', 'description', 'reason'])
  expect(command.initial).toEqual({ title: '3D画图', description: '图档' })
  user.value = { id: 8, roles: ['member'] }
  expect(actionNames('tasks', { ...row, can_manage: false })).not.toContain('编辑任务')
})
it('发货、结项前读取推进检查：缺项一次列全并给出跳转，应收逾期只提示不阻断', async () => {
  const project = { id: 7, manager: 1, members: [], can_manage: true, status: 'active', equipment_quantity: 1 }
  vi.mocked(read).mockImplementation(async path => {
    if (path.endsWith('/readiness/')) return { status: 'active', ship: [
      { key: 'stage_assembly', ok: false, label: '组装阶段', detail: '已完成 0 / 2', blocking: true, target: { tab: 'tasks', phase: 'assembly' } },
      { key: 'stage_test', ok: false, label: '调试阶段', detail: '已完成 0 / 3', blocking: true, target: { tab: 'tasks', phase: 'test' } },
      { key: 'bom', ok: true, label: '设备 BOM', detail: '已登记 3 种物料', blocking: true, target: { tab: 'bom' } },
      { key: 'receivable', ok: false, label: '应收状态', detail: '未收 1 笔，共 ¥100.00；其中已逾期 1 笔', blocking: false, target: { tab: 'finance' } },
    ], accept: [], close: [] }
    if (path.endsWith('/demand/')) return { lines: [] }
    return project
  })
  const ship = await actionCommand('projects', project, '发货')
  expect(ship.blocked).toBe('发货前还差：组装阶段（已完成 0 / 2）；调试阶段（已完成 0 / 3）')
  expect(ship.links).toEqual([
    { label: '查看组装阶段', path: '/projects/7?tab=tasks&section=tasks&phase=assembly' },
    { label: '查看调试阶段', path: '/projects/7?tab=tasks&section=tasks&phase=test' },
  ])
  expect(ship.notice).toEqual({ type: 'warning', text: '应收状态：未收 1 笔，共 ¥100.00；其中已逾期 1 笔。仅作提示，不影响发货。' })
  vi.mocked(read).mockImplementation(async path => {
    if (path.endsWith('/readiness/')) return { status: 'warranty', ship: [], accept: [], close: [
      { key: 'tasks', ok: true, label: '任务全部完成或取消', detail: '全部任务已结束', blocking: true, target: { tab: 'tasks' } },
    ] }
    return project
  })
  const close = await actionCommand('projects', { ...project, status: 'warranty' }, '结项')
  expect(close.blocked).toBeUndefined()
  expect(close.fields.map(field => field.key)).toEqual(['reason'])
  // 推进检查读取失败时不拦截，仍以服务端校验为准。
  vi.mocked(read).mockImplementation(async path => { if (path.endsWith('/readiness/')) throw new Error('网络错误'); return project })
  expect((await actionCommand('projects', { ...project, status: 'warranty' }, '结项')).blocked).toBeUndefined()
  expect(readinessPath(7, { tab: 'tasks', attention: 'open-tasks' })).toBe('/projects/7?tab=tasks&section=tasks&attention=open-tasks')
})

