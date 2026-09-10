import type { Catalog } from '../catalog'
import { project } from './shared'
import { choices } from './shared'
export const projectFields = (c: Catalog): Field[] => [
  t('name', '项目名称'),
  select('customer', '客户', options(c.partners.filter((p) => p.kind !== 'supplier'))),
  select('manager', '负责人', options(c.users.filter(u => hasRoles(u, ['admin', 'manager'])))),
  { key: 'members', label: '项目成员', type: 'multi', optional: true, options: options(c.users) },
  t('requirements', '需求说明', true),
  date('due_date', '计划交期', true),
  { ...qty, key: 'equipment_quantity', label: '设备数量', initial: 1 },
  { key: 'warranty_months', label: '质保月数', initial: 12 },
]
export const taskFields = (c: Catalog): Field[] => [
  project(c),
  select('kind', '阶段', choices({ design: '设计', assembly: '装配', test: '调试' })),
  t('title', '任务名称'),
  t('description', '说明', true),
  person(c),
  date('due_date', '期限', true),
]
import { all, read } from '../api'
import { catalog } from '../catalog'
import { options } from '../catalog'
import { manager, hasRoles } from '../session'
import { user } from '../session'
import type { Command } from '../types'
import type { Field } from '../types'
import type { Row } from '../types'
import type { Column } from '../types'
import { t } from './shared'
import { date } from './shared'
import { select } from './shared'
import { reason } from './shared'
import { qty } from './shared'
import { C } from './shared'
import { person } from './shared'
import { endpoint, ledgerStatus } from './shared'
export const columns: Record<string, Column[]> = {
  projects: [
    C('code', '项目编号'),
    C('name', '项目名称'),
    C('customer_name', '客户'),
    C('manager_name', '负责人'),
    C('status', '状态'),
    C('due_date', '计划交期'),
  ],
  tasks: [
    C('title', '任务名称'),
    C('kind', '阶段'),
    C('assignee_name', '执行人'),
    C('status', '状态'),
    C('due_date', '期限'),
  ],
  deliveries: [
    C('code', '交付批次'),
    C('quantity', '设备数量'),
    C('shipped_date', '发货日'),
    C('accepted_date', '验收日'),
    C('warranty_until', '质保截止'),
  ],
  time: [
    C('task_title', '任务'),
    C('user_name', '人员'),
    C('date', '日期'),
    C('hours', '工时'),
    C('reason', '说明'),
    C('reversal_of', '冲销原记录'),
    { key: 'reversed_by', label: '记录状态', format: ledgerStatus },
  ],
}
export function createLabel(resource: string) {
  return (
    (
      { projects: manager() && '新建项目', tasks: manager() && '新建任务' } as Record<
        string,
        string | boolean
      >
    )[resource] || ''
  )
}
export async function createCommand(resource: string, projectId?: number): Promise<Command> {
  const c = await catalog(['projects', 'partners', 'users'])
  let fields: Field[] = []
  let path = endpoint(resource)
  if (resource === 'projects') fields = projectFields(c)
  if (resource === 'tasks') fields = taskFields(c)
  return {
    title: String(createLabel(resource)),
    path,
    fields,
    initial: projectId ? { project: projectId } : {},
  }
}
export function actionNames(resource: string, r: Row): string[] {
  const a: string[] = []
  if (resource === 'deliveries') a.push('查看配套清单')
  if (resource === 'projects') {
    if (manager() && r.can_manage !== false) {
      if (!['closed', 'cancelled'].includes(r.status)) a.push('编辑项目')
      if (['draft', 'quoted', 'active'].includes(r.status)) a.push('取消项目')
      if (['active', 'delivering'].includes(r.status)) a.push('发货')
      if (['delivering', 'warranty'].includes(r.status)) a.push('登记售后')
      if (r.status === 'warranty') a.push('结项')
      if (['closed', 'cancelled'].includes(r.status)) a.push('重新打开')
    }
  }
  if (resource === 'tasks') {
    if ((manager() || r.assignee === user.value?.id) && ['open', 'done'].includes(r.status)) {
      a.push('登记工时')
      if (r.status === 'open' && r.kind !== 'acceptance') a.push('完成任务')
    }
    if (manager()) {
      if (r.status === 'open') a.push('重新分配')
      if (r.status === 'open' && !['install', 'acceptance'].includes(r.kind)) a.push('取消任务')
      if (r.status !== 'open' && r.kind !== 'acceptance') a.push('重开任务')
    }
  }
  if (resource === 'deliveries' && manager() && !r.accepted_date) a.push('验收')
  if (
    resource === 'time' &&
    (manager() || r.user === user.value?.id) &&
    !r.reversal_of &&
    !r.reversed_by &&
    Number(r.hours) > 0
  )
    a.push('更正工时')
  return a
}
export async function actionCommand(resource: string, r: Row, name: string): Promise<Command> {
  if (name === '查看配套清单') {
    const detail = await read(`/business/deliveries/${r.id}/`)
    const demand = await read(`/business/projects/${r.project}/demand/`)
    return { title: name, path: '', readonly: true, notice: { type: 'info', text: detail.material_requirements == null ? '历史批次沿用当时按设备数量比例交付的规则，未补造物料快照。' : '本批实际核对的配套数量；退料检查会保留已交付用量。' }, initial: { lines: (detail.material_requirements || []).map((line: Row) => ({ ...line, item_name: demand.lines.find((item: Row) => item.item === line.item)?.item_name || `物料${line.item}` })) }, fields: [{ key: 'lines', label: '配套物料', type: 'rows', fields: [t('item_name', '物料'), t('quantity', '配套数量')] }] }
  }
  const c = await catalog(['projects', 'partners', 'users'])
  let path = endpoint(resource) + r.id + '/'
  let fields: Field[] = [reason]
  let initial: Row = {}
  let method: 'post' | 'patch' = 'post'
  let readonly = false
  const routes: Record<string, string> = {
    编辑项目: 'edit',
    取消项目: 'cancel',
    发货: 'ship',
    登记售后: 'service',
    结项: 'close',
    重新打开: 'reopen',
    登记工时: 'time',
    完成任务: 'complete',
    重新分配: 'assign',
    取消任务: 'cancel',
    重开任务: 'reopen',
    验收: 'accept',
    更正工时: 'amend',
  }
  if (routes[name]) path += routes[name] + '/'
  if (name === '编辑项目') {
    fields = [
      ...projectFields(c).filter(
        (f) =>
          !(r.contract_date || ['delivering', 'warranty'].includes(r.status)) ||
          !['customer', 'equipment_quantity', 'warranty_months'].includes(f.key),
      ),
      reason,
    ]
    initial = r
  }
  if (name === '发货') {
    fields = [
      qty,
      date(),
      person(c, 'installer', '安装人'),
      person(c, 'acceptor', '验收负责人'),
      t('note', '说明', true),
      { key: 'materials', label: '本批配套物料（多单元必填；同配置可留空按比例）', type: 'rows', optional: true, fields: [{ key: 'item', label: '物料', type: 'select', options: [...new Map((await read(`/business/projects/${r.id}/demand/`)).lines.map((line: Row) => [line.item, { value: line.item, label: `${line.item_code} · ${line.item_name} · ${line.assembly_unit || '未分单元'}` }])).values()] as { value: number; label: string }[] }, qty] },
    ]
    initial = { quantity: '1', installer: r.manager, acceptor: r.manager, materials: [] }
  }
  if (name === '登记售后')
    fields = [
      select(
        'delivery',
        '交付批次',
        options(
          (await all('/business/deliveries/', { project: r.id })).filter((d) => d.accepted_date),
        ),
      ),
      date(),
      t('title', '售后事项'),
      t('description', '说明', true),
      person(c),
      date('due_date', '期限', true),
      {
        key: 'fee',
        label: '收费金额（元）',
        initial: '0',
        hint: '质保内免费，质保外需登记正数费用。',
      },
    ]
  if (name === '验收') fields = [date(), reason]
  if (name === '登记工时') {
    fields = [date(), t('hours', '工时'), reason, ...(manager() ? [person(c, 'user', '人员')] : [])]
    initial = { user: r.assignee }
  }
  if (name === '更正工时') {
    fields = [
      date(),
      { key: 'hours', label: '更正后工时', hint: '填 0 撤销原工时，保留纠错记录。' },
      reason,
    ]
    initial = r
  }
  if (name === '重新分配') fields = [person(c), reason]
  return { title: name, path, fields, initial, method, readonly }
}
