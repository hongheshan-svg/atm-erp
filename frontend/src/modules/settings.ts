import { choices } from './shared'
import { select } from './shared'
export const userFields: Field[] = [
  t('username', '用户名'),
  t('display_name', '姓名'),
  select(
    'role',
    '角色',
    choices({
      admin: '管理员',
      manager: '项目经理',
      purchaser: '采购员',
      warehouse: '仓管',
      finance: '财务',
      member: '成员',
    }),
  ),
  { key: 'hourly_cost', label: '小时成本（元）', initial: '0.00' },
  { key: 'password', label: '密码', type: 'password' },
  { key: 'is_active', label: '启用', type: 'boolean' },
]
import { can } from '../session'
import type { Command } from '../types'
import type { Field } from '../types'
import type { Row } from '../types'
import type { Column } from '../types'
import { t } from './shared'
import { C } from './shared'
import { endpoint } from './shared'
export const columns: Record<string, Column[]> = {
  users: [
    C('username', '用户名'),
    C('display_name', '姓名'),
    C('role', '角色'),
    C('hourly_cost', '小时成本'),
    C('is_active', '启用'),
  ],
  company: [C('name', '公司名称'), C('address', '地址'), C('phone', '电话')],
  codes: [C('key', '用途'), C('prefix', '前缀'), C('counter', '已用序号')],
  audit: [
    C('actor', '操作人'),
    C('operation', '操作'),
    C('resource', '对象'),
    C('detail', '详情'),
    C('created_at', '时间'),
  ],
}
export function createLabel(resource: string) {
  return (
    ({ users: can(['admin']) && '新增用户' } as Record<string, string | boolean>)[resource] || ''
  )
}
export async function createCommand(resource: string, projectId?: number): Promise<Command> {
  let fields: Field[] = []
  let path = endpoint(resource)
  if (resource === 'users') fields = userFields
  return {
    title: String(createLabel(resource)),
    path,
    fields,
    initial: projectId ? { project: projectId } : {},
  }
}
export function actionNames(resource: string, _r: Row): string[] {
  const a: string[] = []
  if (['users', 'company'].includes(resource) && can(['admin'])) a.push('编辑')
  return a
}
export async function actionCommand(resource: string, r: Row, name: string): Promise<Command> {
  if (name !== '编辑' || !['users', 'company'].includes(resource)) throw new Error('不支持的设置操作。')
  const fields = resource === 'company'
    ? [t('name', '公司名称'), t('address', '地址', true), t('phone', '电话', true)]
    : userFields.map(f => f.key === 'password' ? { ...f, optional: true } : f)
  return { title: name, path: endpoint(resource) + r.id + '/', fields, initial: r, method: 'patch' }
}
