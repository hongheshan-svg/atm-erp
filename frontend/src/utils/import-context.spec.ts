import { afterEach, expect, it } from 'vitest'
import { user } from '../session'
import { importDestination, templateMismatch } from './import-context'

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
