import { afterEach, expect, it } from 'vitest'
import { user } from '../session'
import { exportFilename, importDestination, importResultDestination, scopedImportProject, templateMismatch } from './import-context'

afterEach(() => { user.value = null })
it('错模板入口按岗位限制并保留已有项目上下文', () => {
  user.value = { roles: ['admin'] }
  expect(importDestination('stocks')).toEqual({ path: '/settings', query: { section: 'initialization' } })
  user.value = { roles: ['manager'] }
  expect(importDestination('stocks')).toBeNull()
  expect(importDestination('tasks', 7)).toEqual({ path: '/projects/7', query: { tab: 'tasks', resource: 'tasks' } })
  expect(importDestination('projects')).toEqual({ path: '/projects', query: { resource: 'projects' } })
  user.value = { roles: ['mechanical_engineer', 'purchaser'] }
  expect(importDestination('tasks', 7)).toBeNull()
  expect(importDestination('bom')).toEqual({ path: '/bom' })
  user.value = { roles: ['purchaser'] }
  expect(importDestination('bom')).toBeNull()
  expect(importDestination('unexpected')).toBeNull()
})
it('只识别服务端结构化模板提示', () => {
  expect(templateMismatch(new Error('这是任务模板'))).toBeNull()
  expect(templateMismatch({ response: { data: { file: '请到任务入口', template_hint: { code: 'tasks', title: '项目任务', entry: '项目任务导入' } } } })).toEqual({ resource: 'tasks', title: '项目任务', entry: '项目任务导入', message: '请到任务入口' })
})

it('项目上下文支持关系筛选并拒绝无效编号', () => {
  expect(scopedImportProject({ task__project: '7' })).toBe(7)
  expect(scopedImportProject({ entry__project: 8 })).toBe(8)
  expect(scopedImportProject({ project: 7 }, 9)).toBe(9)
  expect(scopedImportProject({ project: 'all' })).toBeUndefined()
  expect(scopedImportProject({ project: -7 })).toBeUndefined()
})

it('导出文件使用中文业务名称和本地日期', () => {
  const date = new Date(2026, 9, 22)
  expect(exportFilename('entries', 'xlsx', date)).toBe('应收应付与费用导出_2026-10-22.xlsx')
  expect(exportFilename('moves', 'csv', date)).toBe('库存流水导出_2026-10-22.csv')
  expect(exportFilename('time', 'xlsx', date)).toBe('工时记录导出_2026-10-22.xlsx')
  expect(exportFilename('reports', 'xlsx', date)).toBe('经营报表导出_2026-10-22.xlsx')
})

it('成功入口仅聚焦服务端明确资源的真实记录，不把期初流水ID当库存ID', () => {
  expect(importResultDestination('stocks', { resource: 'moves', results: [{ id: 23 }] })).toEqual({
    path: '/inventory', query: { section: 'moves', resource: 'moves', project: 'all', focus: 23 },
  })
  expect(importResultDestination('entries', { resource: 'payments', results: [{ id: 99 }] })?.query).not.toHaveProperty('focus')
  expect(importResultDestination('bank-records', { count: 2, skipped: 1 })).toEqual({
    path: '/finance', query: { section: 'bank', resource: 'bank-records', project: 'all' },
  })
  expect(importResultDestination('deliveries', { resource: 'deliveries', results: [{ id: 23, project: 7 }] })).toEqual({
    path: '/projects/7', query: { tab: 'deliveries', section: 'deliveries', resource: 'deliveries', focus: 23 },
  })
  expect(importResultDestination('deliveries', { results: [{ id: 23 }] })).toBeNull()
})
