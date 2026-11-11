import { money } from '../utils/money'
import { disciplineField } from './milestones'
import { codeField } from './shared'
import { today } from '../forms'
import { daysUntil, executorField, milestoneFields, personField, taskAssignees, taskElapsedLabel, taskVarianceLabel } from './milestones'
import type { Catalog } from '../catalog'
import { customer } from './shared'
import { participants } from './shared'
import { project } from './shared'
export const projectFields = (c: Catalog): Field[] => [
  t('name', '项目名称'),
  customer(),
  select('manager', '负责人', options(c.users.filter(u => hasRoles(u, ['admin', 'manager'])))),
  // 成员决定谁能看到项目、被派工和当专业主管：用可搜索的多选，单击即可增减，不会误清空原有成员。
  { key: 'members', label: '项目成员', type: 'multi', searchableMulti: true, optional: true, options: options(c.users) },
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
export const taskFields = (c: Catalog, canDesign = manager(), scope?: Row | null, metadata: Row = { stages: [], nodes: [] }): Field[] => [
  taskProject(),
  ...milestoneFields(c, metadata, scope, canDesign),
]
import { all, read } from '../api'
import { catalog } from '../catalog'
import { options } from '../catalog'
import { manager, hasRoles, production, productionProject, taskManager, taskConfirmer, timeAmender, serviceRegistrar } from '../session'
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
import { endpoint, ledgerStatus } from './shared'
import { display } from './shared'
// 列表上的任务完成进度；尚未安排任务时明确说明，而不是显示 0/0。
export function taskProgressLabel(row: Row): string {
  if (row.task_total == null) return '—'
  if (!row.task_total) return '未安排任务'
  return `${row.task_done} / ${row.task_total}（${Math.round((row.task_done / row.task_total) * 100)}%）`
}
// 执行中、交付中的项目在交期下方给出剩余天数；已逾期由列表的逾期标记显示天数。
export function projectDueFlag(row: Row) {
  if (!['active', 'delivering'].includes(row.status)) return undefined
  const left = daysUntil(row.due_date)
  if (left == null) return undefined
  return left < 0 ? { text: `已逾期 ${-left} 天`, risk: true } : left === 0 ? { text: '今天到期', risk: true } : { text: `剩 ${left} 天` }
}
// 已开工的待完成任务显示「进行中」；验收和业务同步节点没有开工动作，仍按原状态显示。
export function taskStatusLabel(row: Row): string {
  if (row.status === 'open' && row.started_date && row.kind !== 'acceptance' && !row.system_managed) return '进行中'
  return display(row.status)
}
// 逾期、延期、提前天数并进计划日期格（实际完成日期作为第二行跟在下面），不用横向滚动到「提前／延期」列。
export function taskDueFlag(row: Row) {
  if (row.status === 'done') return taskCompletionFlag(row)
  if (row.status !== 'open' || !(Number(row.schedule_variance_days) > 0)) return undefined
  return { text: `已逾期 ${row.schedule_variance_days} 天`, risk: true }
}
export function taskCompletionFlag(row: Row) {
  const days = Number(row.schedule_variance_days)
  if (row.status !== 'done' || row.schedule_variance_days == null || !days) return undefined
  return days > 0 ? { text: `延期 ${days} 天`, risk: true } : { text: `提前 ${-days} 天` }
}
// 交付批次进度由后端按本批安装、验收任务推导。
const deliveryStages: Record<string, string> = { installing: '待安装', awaiting_acceptance: '待验收', accepted: '已验收' }
export const columns: Record<string, Column[]> = {
  projects: [
    C('code', '项目编号'),
    C('name', '项目名称'),
    C('customer_name', '客户'),
    C('manager_name', '负责人'),
    C('status', '状态'),
    { key: 'task_done', label: '任务进度', format: taskProgressLabel, flag: row => Number(row.task_overdue) > 0 ? { text: `${row.task_overdue} 项逾期`, risk: true } : undefined },
    { ...C('due_date', '计划交期'), flag: projectDueFlag },
  ],
  tasks: [
    C('title', '任务名称'),
    C('project_name', '项目'),
    C('stage_label', '阶段'),
    C('milestone_label', '里程碑节点'),
    C('assignee_name', '执行人'),
    C('discipline_label', '负责专业'),
    C('supervisor_name', '负责主管'),
    { key: 'status', label: '状态', format: taskStatusLabel },
    C('logged_hours', '已登记工时'),
    { ...C('due_date', '计划完成日期'), flag: taskDueFlag },
    C('completed_date', '实际完成日期'),
    C('started_date', '实际开始日期'),
    { key: 'elapsed_days', label: '任务历时', format: taskElapsedLabel },
    { key: 'schedule_variance_days', label: '提前／延期', format: taskVarianceLabel },
  ],
  deliveries: [
    C('code', '交付批次'),
    { key: 'stage', label: '批次进度', format: row => deliveryStages[row.stage] || (row.accepted_date ? '已验收' : '待验收') },
    C('quantity', '设备数量'),
    C('shipped_date', '发货日'),
    C('installer_name', '安装人'),
    C('acceptor_name', '验收负责人'),
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
  if (resource === 'projects') fields = [codeField('项目编号'), ...projectFields(c)]
  if (resource === 'tasks') {
    const scope = projectId ? await read(`/business/projects/${projectId}/`) : null
    if (scope && !productionProject(scope)) throw new Error('没有当前项目的生产派工权限，请刷新项目后重试。')
    const canDesign = manager() && (scope ? scope.can_manage !== false : true)
    const metadata = await read('/business/tasks/milestone-template/', projectId ? { project: projectId } : {})
    fields = taskFields(c, canDesign, scope, metadata).map(field => field.key === 'project' && projectId ? { ...field, readonly: true } : field)
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
    a.push('查看工时')
    if (!r.system_managed && taskConfirmer(r) && ['open', 'done'].includes(r.status)) {
      a.push('登记工时')
      if (r.status === 'open' && r.kind !== 'acceptance' && !r.started_date) a.push('开始任务')
      if (r.status === 'open' && r.kind !== 'acceptance') a.push('完成任务')
    }
    if (taskConfirmer(r)) {
      if (['open', 'done'].includes(r.status) && !r.system_managed && r.kind !== 'acceptance') {
        if (r.started_date) a.push('更正开始日期')
        else if (r.status === 'done') a.push('补录开始日期')
      }
      if (r.status === 'done' && !r.system_managed && r.kind !== 'acceptance') a.push(r.completed_date ? '更正完成日期' : '补录完成日期')
    }
    if (taskManager(r)) {
      // 改期是最常见的调整，单独给入口；重新分配仍可同时改执行人、专业和日期。
      if (r.status === 'open') a.push('改计划日期', '重新分配')
      // 名称和完成要求写错时直接更正，不必取消重建；业务同步节点按实际记录生成，不在这里改。
      if (['open', 'done'].includes(r.status) && !r.system_managed) a.push('编辑任务')
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
// 例行动作的说明选填，留空时服务端记为动作名；更正、取消、重开等纠错动作仍必须写原因。
const optionalNote = (label: string): Field => ({ key: 'reason', label, optional: true })
type Check = { key: string; ok: boolean; label: string; detail: string; blocking?: boolean; target?: Row }
// 推进检查的跳转地址：任务类带上阶段筛选，直接落到要处理的那几条。
export function readinessPath(projectId: unknown, target: Row = {}): string {
  const query = new URLSearchParams()
  if (target.tab) query.set('tab', String(target.tab))
  if (target.tab === 'tasks') query.set('section', 'tasks')
  if (target.phase) query.set('phase', String(target.phase))
  if (target.attention) query.set('attention', String(target.attention))
  const search = query.toString()
  return `/projects/${projectId}${search ? `?${search}` : ''}`
}
// 发货成功后的应收提示：服务端只对能看金额的角色返回 receivables，其余角色不带金额也不提示。
export function shipReceivableNote(result: Row): string {
  const rows: Row[] = Array.isArray(result?.receivables) ? result.receivables : []
  if (!rows.length) return ''
  const list = rows.map(row => `${row.title} ${money(row.outstanding, { currency: true })}（${row.overdue ? '已逾期，' : ''}到期 ${row.due_date}）`).join('；')
  return `本项目有未结应收：${list}。如合同约定发货后付款，请通知财务调整到期日。`
}
// 发货、结项前先读同一组推进检查：未满足项一次列全并给出跳转，不必提交后逐条试错；读取失败时仍以服务端校验为准。
async function readinessGate(r: Row, key: 'ship' | 'close', title: string): Promise<Partial<Command>> {
  let checks: Check[]
  try {
    const result = await read(`/business/projects/${r.id}/readiness/`)
    checks = Array.isArray(result?.[key]) ? result[key] : []
  } catch { return {} }
  const missing = checks.filter(item => item.blocking !== false && !item.ok)
  const info = checks.filter(item => item.blocking === false)
  const links = [...new Map(missing.filter(item => item.target?.tab).map(item => {
    const path = readinessPath(r.id, item.target)
    return [path, { label: `查看${item.label}`, path }]
  })).values()]
  return {
    ...(missing.length ? { blocked: `${title}前还差：${missing.map(item => `${item.label}（${item.detail}）`).join('；')}`, links } : {}),
    ...(info.length ? { notice: { type: info.some(item => !item.ok) ? 'warning' as const : 'info' as const, text: info.map(item => `${item.label}：${item.detail}`).join('；') + (info.some(item => !item.ok) ? '。仅作提示，不影响发货。' : '') } } : {}),
  }
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
    开始任务: 'start',
    补录开始日期: 'start-date',
    更正开始日期: 'start-date',
    补录完成日期: 'completion-date',
    更正完成日期: 'completion-date',
    重新分配: 'assign',
    改计划日期: 'reschedule',
    取消任务: 'cancel',
    重开任务: 'reopen',
    验收: 'accept',
    更正工时: 'amend',
    编辑任务: 'edit',
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
  let gate: Partial<Command> = {}
  if (name === '发货' || name === '结项') gate = await readinessGate(r, name === '发货' ? 'ship' : 'close', name === '发货' ? '发货' : '结项')
  if (name === '发货') {
    gate = { ...gate, successNote: shipReceivableNote }
    fields = [
      codeField('交付单号'),
      qty,
      date(),
      personField(c, 'installer', '安装人', scope),
      personField(c, 'acceptor', '验收负责人', scope),
      { ...date('install_due_date', '安装完成期限', true), hint: '可选，写入本批自动生成的安装任务；不得早于发货日期，留空则不设期限。' },
      { ...date('acceptance_due_date', '验收期限', true), hint: '可选，写入本批验收任务；流程进度和工作台按期限提示逾期，不得早于发货日期。' },
      t('note', '说明', true),
      { key: 'materials', label: '本批配套物料（多单元必填；同配置可留空按比例）', type: 'rows', optional: true, fields: [{ key: 'item', label: '物料', type: 'select', options: shipMaterialOptions((await read(`/business/projects/${r.id}/demand/`)).lines) }, { ...qty, numeric: { scale: 3, min: 0.001 } }] },
    ]
    // 安装人默认取本项目生产专业主管，未指定时回落项目经理。
    const producer = r.task_supervisors?.production
    initial = { quantity: '1', installer: producer && inScope(producer) ? producer : r.manager, acceptor: r.manager, materials: [] }
  }
  if (name === '登记售后') {
    const managesProject = manager() && r.can_manage !== false
    const accepted = (await all('/business/deliveries/', { project: r.id })).filter((d) => d.accepted_date)
    // 与服务端同口径：售后日期不晚于所选批次质保到期日即为质保期内。
    const inWarranty = (data: Row) => {
      const batch = accepted.find((d) => String(d.id) === String(data.delivery))
      return Boolean(batch?.warranty_until && data.date && String(data.date) <= String(batch.warranty_until))
    }
    fields = [
      select('delivery', '交付批次', options(accepted)),
      date(),
      t('title', '售后事项'),
      t('description', '说明', true),
      personField(c, 'assignee', '执行人', scope),
      date('due_date', '维修截止日期', true),
      ...(managesProject ? [{
        key: 'fee',
        label: '收费金额（元）',
        initial: '0',
        hint: '质保内默认免费，确属客户误操作、人为损坏等非质保责任需收费时填正数并写明原因；质保外收费填正数，免费则填 0 并写明免费原因。',
      }, {
        key: 'charge_reason',
        label: '非质保责任原因',
        visibleWhen: (data: Row) => Number(data.fee) > 0 && inWarranty(data),
        hint: '质保期内收费必填，例如客户误操作、人为损坏；原因记入操作审计，应收和客户付款期限按收费售后生成。',
      }, {
        key: 'fee_due_date',
        label: '客户付款到期日',
        type: 'date' as const,
        visibleWhen: (data: Row) => Number(data.fee) > 0,
        hint: '按客户确认的付款期限填写，与维修截止日期分别维护。',
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
  if (name === '验收') {
    fields = [date(), optionalNote('验收说明')]
    if (r.stage === 'installing') gate = { blocked: '本批安装任务尚未全部完成。请先完成本批现场安装任务，再登记客户验收。', links: [{ label: '查看安装任务', path: readinessPath(r.project, { tab: 'tasks', phase: 'site' }) }] }
  }
  if (name === '编辑任务') {
    fields = [t('title', '任务名称'), { key: 'description', label: '完成要求', type: 'textarea', optional: true, hint: '写明图档版本、交付物或验收标准；修改后会通知执行人。' }, reason]
    initial = { title: r.title || '', description: r.description || '' }
  }
  if (['完成任务', '补录完成日期', '更正完成日期'].includes(name)) {
    fields = [{ ...date('completed_date', '实际完成日期'), hint: '填写实际完成当天，可补录过去的日期，不能填写未来日期；系统另行保留提交时间。' }, name === '完成任务' ? optionalNote('完成说明') : reason]
    if (name === '完成任务' && !r.started_date) fields.unshift({ ...date('started_date', '实际开始日期', true), hint: '忘记点击开始任务时可在此补录；留空则暂不计算历时，不会用任务创建日期代替。' })
    initial = { completed_date: name === '完成任务' ? today() : r.completed_date || '' }
  }
  if (['开始任务', '补录开始日期', '更正开始日期'].includes(name)) {
    fields = [{ ...date('started_date', '实际开始日期'), hint: '按真实开工日期填写，可补录过去日期，不能晚于今天或实际完成日期。' }, name === '开始任务' ? optionalNote('开始说明') : reason]
    initial = { started_date: name === '开始任务' ? today() : r.started_date || '' }
  }
  if (name === '登记工时') {
    fields = [date(), t('hours', '工时'), optionalNote('工作内容'), personField(c, 'user', '人员', scope)]
    // 原执行人若已被移出项目，就不预选一个注定被服务端拒绝的人。
    initial = { user: taskAssignees(r).includes(user.value?.id) ? user.value?.id : inScope(r.assignee) ? r.assignee : '' }
  }
  if (name === '更正工时') {
    fields = [
      date(),
      { key: 'hours', label: '更正后工时', hint: '填 0 撤销原工时，保留纠错记录。' },
      reason,
    ]
    initial = r
  }
  if (name === '改计划日期') {
    fields = [{ ...date('due_date', '新的计划完成日期'), hint: `${r.due_date ? `原计划 ${r.due_date}` : '原未设计划日期'}。执行人和专业不变，保存后通知执行人。` }, reason]
    initial = { due_date: r.due_date || '' }
  }
  if (name === '重新分配') {
    fields = [executorField(c, scope), disciplineField(), date('due_date', '计划完成日期', true), reason]
    initial = { assignees: taskAssignees(r).filter(inScope), discipline: r.discipline, due_date: r.due_date || '' }
  }
  if (name === '重开任务') {
    // 重开时必须确认执行人：原执行人可能已经被移出项目，沿用旧值只会在服务端被拒。
    fields = [executorField(c, scope), reason]
    initial = { assignees: taskAssignees(r).filter(inScope) }
  }
  return { title: name, path, fields, initial, method, readonly, ...gate,
    ...(['开始任务', '完成任务', '补录开始日期', '更正开始日期', '补录完成日期', '更正完成日期'].includes(name) ? { notice: { type: 'info' as const, text: '历时按自然日计算，包含开始和完成当天；同日完成为1天，未完成算至今天。仅统计任务进度，不自动生成工时或人工成本。' } } : {}),
    ...(['补录开始日期', '更正开始日期'].includes(name) ? { prepare: (data: Row) => ({ ...data, expected_started_date: r.started_date || null }) } : {}),
    ...(['补录完成日期', '更正完成日期'].includes(name) ? { prepare: (data: Row) => ({ ...data, expected_completed_date: r.completed_date || null }) } : {}),
    ...(name === '重新分配' ? { prepare: (data: Row) => ({ ...data, due_date: data.due_date || null }) } : {}),
    ...(name === '编辑项目' && ['draft', 'quoted'].includes(r.status) ? { notice: { type: 'warning' as const, text: '历史未签约项目修改需求后将清除原报价，请到关联销售单重新报价并签约。' } } : {}),
  }
}
