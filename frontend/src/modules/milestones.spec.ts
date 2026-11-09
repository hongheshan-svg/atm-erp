import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { all, read } from '../api'
import { actionCommand, actionNames, createCommand } from './projects'
import { milestoneTemplateCommand, taskSyncHint } from './milestones'
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
  expect(actionNames('tasks', row)).toEqual(['重新分配', '取消任务'])
  expect(actionNames('tasks', { ...row, status: 'done', can_cancel: false })).toEqual([])
})
it('调整负责人保留原日期，也可明确清空日期', async () => {
  const command = await actionCommand('tasks', { id: 4, project: 7, assignee: 1, due_date: '2026-12-20' }, '重新分配')
  expect(command.initial).toEqual({ assignees: [1], due_date: '2026-12-20' })
  expect(command.prepare?.({ assignees: [1], reason: '日期待定' })).toEqual({ assignees: [1], reason: '日期待定', due_date: null })
})

it('共同执行人显示完成和本人工时入口，自动汇总仍指向实际交付', async () => {
  user.value = { id: 8, roles: ['member'] }
  const row = { id: 4, project: 7, assignee: 1, assignees: [1, 8], kind: 'design', status: 'open', can_manage: false }
  expect(actionNames('tasks', row)).toEqual(['登记工时', '完成任务'])
  expect(actionNames('tasks', { ...row, assignees: [1] })).toEqual([])
  const command = await actionCommand('tasks', row, '登记工时')
  expect(command.fields.some(field => field.key === 'user')).toBe(false)
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
