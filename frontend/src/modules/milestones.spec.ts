import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { all, read } from '../api'
import { actionCommand, actionNames, createCommand } from './projects'
import { milestoneTemplateCommand } from './milestones'
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
  const data = payload(command.fields, { lines: [{ kind: 'site', title: '培训', assignee: 1, due_date: '2026-12-20' }] })
  expect(command.prepare?.({ ...data, project: 99 })).toEqual({ project: 7, lines: [{ kind: 'site', title: '培训', assignee: 1, due_date: '2026-12-20' }] })
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
  expect(command.initial).toEqual({ assignee: 1, due_date: '2026-12-20' })
  expect(command.prepare?.({ assignee: 1, reason: '日期待定' })).toEqual({ assignee: 1, reason: '日期待定', due_date: null })
})
