import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { all, read } from '../api'
import { actionCommand, actionNames, columns, createCommand } from './projects'
import { milestoneTemplateCommand, taskSyncHint, taskElapsedLabel, taskVarianceLabel } from './milestones'
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
  const fields = command.fields[0]!.fields!
  const select = fields.find(field => field.key === 'milestone')!
  expect(select.optionsFor?.({ kind: 'purchase' })).toEqual([{ value: 'purchase_long_lead', label: '长交期' }])
  expect(select.optionsFor?.({ kind: 'shipping' })?.[0]?.label).toContain('业务自动同步')
  const data = payload(command.fields, { lines: [{ kind: 'site', title: '培训', assignees: [1], due_date: '2026-12-20' }] })
  expect(command.prepare?.({ ...data, project: 99 })).toEqual({ project: 7, lines: [{ kind: 'site', title: '培训', assignees: [1], due_date: '2026-12-20' }] })
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
