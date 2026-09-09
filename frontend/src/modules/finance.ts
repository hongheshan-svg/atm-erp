import { catalog } from '../catalog'
import type { Command } from '../types'
import type { Field } from '../types'
import type { Row } from '../types'
import type { Column } from '../types'
import { t } from './shared'
import { date } from './shared'
import { reason } from './shared'
import { finance } from './shared'
import { C } from './shared'
import { project } from './shared'
import { endpoint } from './shared'
import { ledgerStatus } from './shared'
export const columns: Record<string, Column[]> = {
  entries: [
    C('project_name', '项目'),
    C('title', '款项'),
    C('kind', '类型'),
    C('amount', '原金额'),
    C('credit_amount', '冲减'),
    C('paid_amount', '已结算'),
    C('balance', '待结算'),
    C('due_date', '期限'),
  ],
  payments: [
    C('entry_title', '款项'),
    C('amount', '金额'),
    C('date', '日期'),
    C('reason', '说明'),
    C('reversal_of', '冲销原记录'),
    { key: 'reversed_by', label: '记录状态', format: ledgerStatus },
  ],
}
export function createLabel(resource: string) {
  return ({ entries: finance() && '登记费用' } as Record<string, string | boolean>)[resource] || ''
}
export async function createCommand(resource: string, projectId?: number): Promise<Command> {
  const c = await catalog(['projects'])
  let fields: Field[] = []
  let path = endpoint(resource)
  if (resource === 'entries') {
    path += 'expense/'
    fields = [
      project(c),
      t('title', '费用名称'),
      t('amount', '金额（元）'),
      date('due_date', '期限'),
    ]
  }
  return {
    title: String(createLabel(resource)),
    path,
    fields,
    initial: projectId ? { project: projectId } : {},
  }
}
export function actionNames(resource: string, r: Row): string[] {
  const a: string[] = []
  if (resource === 'entries' && finance()) {
    if (Number(r.balance) > 0) a.push('登记收付款')
    if (Number(r.balance) < 0) a.push('退款')
    if (r.kind === 'expense' && !r.cancelled) a.push('取消费用')
  }
  if (resource === 'payments' && finance() && !r.reversal_of && !r.reversed_by) a.push('冲销付款')
  return a
}
export async function actionCommand(resource: string, r: Row, name: string): Promise<Command> {
  let path = endpoint(resource) + r.id + '/'
  let fields: Field[] = [reason]
  let initial: Row = {}
  let method: 'post' | 'patch' = 'post'
  let readonly = false
  const routes: Record<string, string> = {
    登记收付款: 'pay',
    退款: 'refund',
    取消费用: 'cancel-expense',
    冲销付款: 'reverse',
  }
  if (routes[name]) path += routes[name] + '/'
  if (['登记收付款', '退款'].includes(name)) {
    fields = [t('amount', '金额（元）'), date(), reason]
    initial = { amount: String(r.balance).replace(/^-/, '') }
  }
  if (name === '冲销付款') fields = [date(), reason]
  return { title: name, path, fields, initial, method, readonly }
}
