import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { all } from '../api'
import { actionCommand, actionNames, createCommand } from '../business'
import { user } from '../session'

vi.mock('../api', () => ({ all: vi.fn(), read: vi.fn(), write: vi.fn() }))

beforeEach(() => {
  vi.clearAllMocks()
  user.value = { id: 8, roles: ['production_manager', 'purchaser'] }
  vi.mocked(all).mockImplementation(async path => path === '/business/projects/' ? [
    { id: 1, name: '参与项目', can_manage_production: true, can_manage: false },
    { id: 2, name: '采购可读项目', can_manage_production: false },
    { id: 3, name: '缺少权限标记项目' },
  ] : path === '/auth/directory/' ? [{ id: 9, display_name: '装配员' }] : [])
})
afterEach(() => { user.value = null })

describe('生产经理任务与售后权限', () => {
  it('新建仅列授权项目与装配调试阶段，兼职采购项目不能成为派工目标', async () => {
    const command = await createCommand('tasks', 1)
    expect(command.initial).toEqual({ project: 1 })
    expect(command.fields.find(field => field.key === 'project')?.options?.map(option => option.value)).toEqual([1])
    expect(command.fields.find(field => field.key === 'project')?.readonly).toBe(true)
    expect(command.prepare?.({ project: 2, kind: 'assembly' })).toEqual({ project: 1, kind: 'assembly' })
    expect(command.fields.find(field => field.key === 'kind')?.options?.map(option => option.value)).toEqual(['assembly', 'test'])
    await expect(createCommand('tasks', 2)).rejects.toThrow('没有当前项目的生产派工权限')
    user.value = { id: 8, roles: ['manager', 'production_manager'] }
    const limited = await createCommand('tasks', 1)
    expect(limited.fields.find(field => field.key === 'kind')?.options?.map(option => option.value)).toEqual(['assembly', 'test'])
    vi.mocked(all).mockResolvedValue([{ id: 4, name: '负责项目', can_manage: true, can_manage_production: true }])
    const managerCommand = await createCommand('tasks', 4)
    expect(managerCommand.fields.find(field => field.key === 'kind')?.options?.map(option => option.value)).toEqual(['design', 'assembly', 'test'])
  })

  it('可为授权生产任务派工完成和补团队工时，不能操作其他项目或设计验收任务', async () => {
    const row = { id: 2, assignee: 9, kind: 'assembly', status: 'open', can_manage: true, can_cancel: true, can_reopen: false }
    expect(actionNames('tasks', row)).toEqual(['登记工时', '完成任务', '重新分配', '取消任务'])
    const command = await actionCommand('tasks', row, '登记工时')
    expect(command.fields.find(field => field.key === 'user')?.options).toEqual([{ value: 9, label: '装配员' }])
    expect(command.initial).toEqual({ user: 9 })
    expect(command.fields.map(field => field.key)).not.toContain('hourly_cost')
    expect(actionNames('tasks', { ...row, can_manage: false })).toEqual([])
    expect(actionNames('tasks', { ...row, kind: 'design', can_manage: false })).toEqual([])
    expect(actionNames('tasks', { ...row, kind: 'acceptance', can_manage: false })).toEqual([])
    const own = { ...row, kind: 'design', assignee: 8, can_manage: false }
    expect(actionNames('tasks', own)).toEqual(['登记工时', '完成任务'])
    expect((await actionCommand('tasks', own, '登记工时')).fields.some(field => field.key === 'user')).toBe(false)
    user.value = { id: 8, roles: ['manager', 'purchaser'] }
    expect(actionNames('tasks', { ...row, can_manage: false })).toEqual([])
    await expect(createCommand('tasks', 2)).rejects.toThrow('没有当前项目的生产派工权限')
  })

  it('收费售后可派工完成但不能取消或重开；普通生产任务遵循独立状态标记', () => {
    const charged = { kind: 'service', status: 'open', assignee: 9, can_manage: true, can_cancel: false, can_reopen: false }
    expect(actionNames('tasks', charged)).toEqual(['登记工时', '完成任务', '重新分配'])
    expect(actionNames('tasks', { ...charged, status: 'done' })).toEqual(['登记工时'])
    expect(actionNames('tasks', { ...charged, kind: 'test', status: 'done', can_reopen: true })).toEqual(['登记工时', '重开任务'])
    expect(actionNames('tasks', { ...charged, kind: 'test', status: 'done', can_cancel: true, can_reopen: true })).toEqual(['登记工时', '取消任务', '重开任务'])
    expect(actionNames('tasks', { ...charged, kind: 'install' })).not.toContain('取消任务')
    expect(actionNames('time', { user: 9, hours: '2', can_amend: true })).toEqual(['更正工时'])
    expect(actionNames('time', { user: 9, hours: '2', can_amend: false })).toEqual([])
    expect(actionNames('time', { user: 9, hours: '2', can_amend: true, reversed_by: 3 })).toEqual([])
  })

  it('仅参与项目提供免费售后登记，不允许通过输入收费金额创建应收', async () => {
    const project = { id: 1, status: 'warranty', can_manage: false, can_register_service: true }
    expect(actionNames('projects', project)).toEqual(['登记售后'])
    expect(actionNames('projects', { ...project, can_register_service: false })).toEqual([])
    expect(actionNames('projects', { ...project, can_register_service: undefined })).toEqual([])
    const command = await actionCommand('projects', project, '登记售后')
    expect(command.path).toBe('/business/projects/1/service/')
    expect(command.fields.some(field => field.key === 'fee')).toBe(false)
    expect(command.notice?.text).toContain('质保内免费')
    expect(command.prepare?.({ title: '安装维护', fee: '900' })).toEqual({ title: '安装维护', fee: '0' })
    user.value = { id: 8, roles: ['manager', 'production_manager'] }
    const limited = await actionCommand('projects', project, '登记售后')
    expect(limited.fields.some(field => field.key === 'fee')).toBe(false)
    expect(limited.prepare?.({ fee: '900' })).toEqual({ fee: '0' })
    user.value = { id: 8, roles: ['manager'] }
    const managerCommand = await actionCommand('projects', { ...project, can_manage: true }, '登记售后')
    expect(managerCommand.fields.some(field => field.key === 'fee')).toBe(true)
  })
})
