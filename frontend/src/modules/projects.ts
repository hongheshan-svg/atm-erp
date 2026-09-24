import type { Catalog } from '../catalog'
import { customer } from './shared'
import { participants } from './shared'
import { project } from './shared'
import { choices } from './shared'
export const projectFields = (c: Catalog): Field[] => [
  t('name', '项目名称'),
  customer(),
  select('manager', '负责人', options(c.users.filter(u => hasRoles(u, ['admin', 'manager'])))),
  { key: 'members', label: '项目成员', type: 'multi', optional: true, options: options(c.users) },
  t('requirements', '需求说明', true),
  date('due_date', '计划交期', true),
  { ...qty, key: 'equipment_quantity', label: '设备数量', initial: 1 },
  { key: 'warranty_months', label: '质保月数', initial: 12 },
]
// 派工只能落在自己有生产管理权限、且仍在执行或交付中的项目上。
const taskProject = (): Field =>
  project({
    remoteFilter: (row: Row) => ['active', 'delivering'].includes(String(row.status)) && productionProject(row),
  })
export const taskFields = (c: Catalog, canDesign = manager(), scope?: Row | null): Field[] => [
  taskProject(),
  select('kind', '阶段', choices(canDesign ? { design: '设计', assembly: '装配', test: '调试' } : { assembly: '装配', test: '调试' })),
  t('title', '任务名称'),
  t('description', '说明', true),
  person(c, 'assignee', '执行人', scope),
  date('due_date', '期限', true),
]
import { all, read } from '../api'
import { catalog } from '../catalog'
import { options } from '../catalog'
import { manager, hasRoles, production, productionProject, taskManager, timeAmender, serviceRegistrar } from '../session'
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
    C('project_name', '项目'),
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
    C('project_name', '项目'),
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
      { projects: manager() && '新建项目', tasks: (manager() || production()) && '新建任务' } as Record<
        string,
        string | boolean
      >
    )[resource] || ''
  )
}
export async function createCommand(resource: string, projectId?: number): Promise<Command> {
  // 人员名单很短，仍然一次取回；项目、客户和物料改走远程分页。
  const c = await catalog(['users'])
  let fields: Field[] = []
  const path = endpoint(resource)
  if (resource === 'projects') fields = projectFields(c)
  if (resource === 'tasks') {
    const scope = projectId ? await read(`/business/projects/${projectId}/`) : null
    if (scope && !productionProject(scope)) throw new Error('没有当前项目的生产派工权限，请刷新项目后重试。')
    const canDesign = manager() && (scope ? scope.can_manage !== false : true)
    fields = taskFields(c, canDesign, scope).map(field => field.key === 'project' && projectId ? { ...field, readonly: true } : field)
  }
  return {
    title: String(createLabel(resource)),
    path,
    fields,
    initial: projectId ? { project: projectId } : {},
    ...(resource === 'tasks' && projectId ? { prepare: (data: Row) => ({ ...data, project: projectId }) } : {}),
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
      if (r.status === 'warranty') a.push('结项')
      if (['closed', 'cancelled'].includes(r.status)) a.push('重新打开')
    }
    if (serviceRegistrar(r) && ['delivering', 'warranty'].includes(r.status)) a.push('登记售后')
  }
  if (resource === 'tasks') {
    if ((taskManager(r) || r.assignee === user.value?.id) && ['open', 'done'].includes(r.status)) {
      a.push('登记工时')
      if (r.status === 'open' && r.kind !== 'acceptance') a.push('完成任务')
    }
    if (taskManager(r)) {
      if (r.status === 'open') a.push('重新分配')
      if (!['install', 'acceptance'].includes(r.kind) && (r.can_cancel ?? (manager() && r.status === 'open'))) a.push('取消任务')
      if (r.kind !== 'acceptance' && (r.can_reopen ?? (manager() && r.status !== 'open'))) a.push('重开任务')
    }
  }
  if (resource === 'deliveries' && manager() && !r.accepted_date) a.push('验收')
  if (
    resource === 'time' &&
    timeAmender(r) &&
    !r.reversal_of &&
    !r.reversed_by &&
    Number(r.hours) > 0
  )
    a.push('更正工时')
  return a
}
// 发货配套按物料合计校验，同一物料在多个单元出现时合并成一项，并列出全部单元和 BOM 合计，免得只看到其中一个单元。
const thousandths = (value: unknown) => {
  const [whole = '0', fraction = ''] = String(value ?? '0').split('.')
  return BigInt(whole || '0') * 1000n + BigInt((fraction + '000').slice(0, 3))
}
export function shipMaterialOptions(lines: Row[]) {
  type Material = { code: string; name: string; units: string[]; total: bigint }
  const grouped = new Map<number, Material>()
  for (const line of lines) {
    const current: Material = grouped.get(line.item) ?? { code: line.item_code, name: line.item_name, units: [], total: 0n }
    const unit = line.assembly_unit || '未分单元'
    if (!current.units.includes(unit)) current.units.push(unit)
    current.total += thousandths(line.quantity)
    grouped.set(line.item, current)
  }
  return [...grouped].map(([value, row]) => ({
    value,
    label: `${row.code} · ${row.name} · ${row.units.join('、')} · BOM 合计 ${row.total / 1000n}.${String(row.total % 1000n).padStart(3, '0')}`,
  }))
}
export async function actionCommand(resource: string, r: Row, name: string): Promise<Command> {
  if (name === '查看配套清单') {
    const detail = await read(`/business/deliveries/${r.id}/`)
    const demand = await read(`/business/projects/${r.project}/demand/`)
    return { title: name, path: '', readonly: true, notice: { type: 'info', text: detail.material_requirements == null ? '历史批次沿用当时按设备数量比例交付的规则，未补造物料快照。' : '本批实际核对的配套数量；退料检查会保留已交付用量。' }, initial: { lines: (detail.material_requirements || []).map((line: Row) => ({ ...line, item_name: demand.lines.find((item: Row) => item.item === line.item)?.item_name || `物料${line.item}` })) }, fields: [{ key: 'lines', label: '配套物料', type: 'rows', fields: [t('item_name', '物料'), t('quantity', '配套数量')] }] }
  }
  // 只有真正要选人的操作才取人员名单；任务行只带项目 ID，缺成员名单时补读一次项目。
  const needsPeople = ['编辑项目', '发货', '登记售后', '登记工时', '重新分配', '重开任务'].includes(name)
  const c = needsPeople ? await catalog(['users']) : { projects: [], items: [], partners: [], users: [] }
  const scope =
    !needsPeople || name === '编辑项目'
      ? null
      : resource === 'projects'
        ? r
        : r.project
          ? await read(`/business/projects/${r.project}/`)
          : null
  const inScope = (id: unknown) => participants(c.users, scope).some(u => u.id === id)
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
      person(c, 'installer', '安装人', scope),
      person(c, 'acceptor', '验收负责人', scope),
      t('note', '说明', true),
      { key: 'materials', label: '本批配套物料（多单元必填；同配置可留空按比例）', type: 'rows', optional: true, fields: [{ key: 'item', label: '物料', type: 'select', options: shipMaterialOptions((await read(`/business/projects/${r.id}/demand/`)).lines) }, qty] },
    ]
    initial = { quantity: '1', installer: r.manager, acceptor: r.manager, materials: [] }
  }
  if (name === '登记售后') {
    const managesProject = manager() && r.can_manage !== false
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
      person(c, 'assignee', '执行人', scope),
      date('due_date', '期限', true),
      ...(managesProject ? [{
        key: 'fee',
        label: '收费金额（元）',
        initial: '0',
        hint: '质保内免费；质保外收费填正数，免费则填 0 并写明免费原因。',
      }, {
        key: 'free_reason',
        label: '过保免费原因',
        optional: true,
        hint: '仅质保外免费时必填，例如商务赠送、延保约定。',
      }] : []),
    ]
    if (!managesProject) return {
      title: name, path, fields,
      notice: { type: 'info', text: '生产经理仅登记质保内免费售后。质保外或收费事项请由项目经理确认创建，再安排执行人员。' },
      prepare: data => ({ ...data, fee: '0' }),
    }
  }
  if (name === '验收') fields = [date(), reason]
  if (name === '登记工时') {
    fields = [date(), t('hours', '工时'), reason, ...(taskManager(r) ? [person(c, 'user', '人员', scope)] : [])]
    // 原执行人若已被移出项目，就不预选一个注定被服务端拒绝的人。
    initial = { user: inScope(r.assignee) ? r.assignee : '' }
  }
  if (name === '更正工时') {
    fields = [
      date(),
      { key: 'hours', label: '更正后工时', hint: '填 0 撤销原工时，保留纠错记录。' },
      reason,
    ]
    initial = r
  }
  if (name === '重新分配') fields = [person(c, 'assignee', '执行人', scope), reason]
  if (name === '重开任务') {
    // 重开时必须确认执行人：原执行人可能已经被移出项目，沿用旧值只会在服务端被拒。
    fields = [person(c, 'assignee', '执行人', scope), reason]
    initial = { assignee: inScope(r.assignee) ? r.assignee : '' }
  }
  return { title: name, path, fields, initial, method, readonly }
}
