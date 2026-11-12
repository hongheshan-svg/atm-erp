import { choices } from './shared'
import { dateTimeText } from '../utils/datetime'
import { select } from './shared'
export const userFields: Field[] = [
  t('username', '用户名'),
  t('display_name', '姓名'),
  { key: 'roles', label: '角色', type: 'checks', initial: ['member'], hint: '勾选可兼任的岗位，至少选择一个。权限按业务合并，报表需单独授权；本人申请仍需他人审批。',
    options: choices(roleLabels),
  },
  { key: 'hourly_cost', label: '小时成本（元）', initial: '0.00' },
  { key: 'management_reports', label: '总经理报表权限（仅项目经理角色）', type: 'boolean', initial: false },
  { key: 'password', label: '密码', type: 'password', randomPassword: true, hint: '可随机生成或自行设置，不限制长度和字符组合。请通知用户登录后在“设置 → 我的账户”修改密码；编辑时留空则不修改。' },
  { key: 'is_active', label: '启用', type: 'boolean' },
]
import { can, roleLabels } from '../session'
import type { Command } from '../types'
import type { Field } from '../types'
import type { Row } from '../types'
import type { Column } from '../types'
import { t } from './shared'
import { C } from './shared'
import { endpoint } from './shared'
// 审计操作名为「对象.动作」，对象是后端模型名（小写），动作可能含连字符或多段（如 bank.return-unclaimed.reverse）。
const auditObjects: Record<string, string> = {
  record: '业务记录', sale: '销售', salesorder: '销售单', project: '项目', purchase: '采购', purchaseorder: '采购单', purchaseline: '采购行', purchasewarranty: '质保',
  task: '任务', tasknotice: '任务提醒', bom: 'BOM', bomline: 'BOM 行', document: '附件', stock: '库存', stockmove: '出入库流水', payment: '收付款', paymentevidence: '收付凭证',
  entry: '款项', delivery: '交付单', reconciliation: '对账', bankrecord: '银行流水', bankmatch: '银行匹配', bankoffset: '银行冲抵', timeentry: '工时', contractamendment: '合同变更',
  item: '物料', partner: '往来单位', supplier: '供应商', user: '用户', company: '公司', code: '编号', period: '锁账', import: '导入',
}
const auditActions: Record<string, string> = {
  create: '新增', update: '修改', edit: '编辑', delete: '删除', restore: '恢复', quote: '报价', invalidate_quote: '需求变更后重新报价', sign: '签约', amend: '变更合同', transfer: '转交',
  submit: '提交', approve: '批准', reject: '退回', receive: '收货', quality_accept: '质量验收', quality_return: '质量退货', warranty: '质保登记', cancel: '取消', cancel_remainder: '取消未收余量',
  complete: '完成', start: '开始', 'start-date': '补录或更正开始日期', 'completion-date': '补录或更正完成日期', revise: '变更', milestones: '调整里程碑', supervisors: '调整负责人',
  close: '结项', reopen: '重开', budget: '调整预算', delivery_plan: '交付计划', notice_read: '已读提醒', 'notice-read': '已读提醒', ship: '发货', accept: '验收', pay: '登记收付款', reverse: '冲销',
  evidence: '上传付款凭证', match: '匹配', unmatch: '取消匹配', void: '作废', review: '复核', issue: '领料', return_material: '项目退料', return_purchase: '采购退货', opening: '期初入库', count: '盘点',
  upload: '上传', download: '下载', remove: '移除', confirm: '确认', monthly_confirm: '月度对账确认', configure: '修改规则', lock: '锁账', partners: '往来单位导入', entries: '款项导入',
  'import-evidence': '导入凭证', 'return-unclaimed.reverse': '退回未认领款项冲销', 'return-unclaimed': '退回未认领款项',
}
const auditFields: Record<string, string> = {
  reason: '原因', note: '备注', name: '名称', code: '编号', date: '日期', status: '状态', amount: '金额', quantity: '数量', unit_price: '单价', locked_through: '锁账截止',
  before: '修改前', after: '修改后', from: '原', to: '新', kind: '类型', title: '标题', operation: '操作',
}
const auditHidden = new Set(['expected_revision', 'revision', 'period_revision', 'fingerprint'])
export function auditOperation(operation: string) {
  const dot = operation.indexOf('.')
  if (dot < 0) return operation
  const object = operation.slice(0, dot), action = operation.slice(dot + 1)
  return auditObjects[object] && auditActions[action] ? `${auditObjects[object]} · ${auditActions[action]}` : operation
}
// 对象显示为「类型 + 业务编号」（后端附带 resource_label），没有编号时显示类型与序号。
export function auditObject(row: Row) {
  const [model = '', id = ''] = String(row.resource ?? '').split(':')
  const name = auditObjects[model]
  if (!name) return String(row.resource ?? '')
  return `${name} ${row.resource_label || `#${id}`}`
}
// 详情原样是 JSON 对象；这里按「字段：值」逐项展示，未知字段保留原名，避免整段截断的花括号。
export function auditDetail(detail: unknown) {
  if (!detail || typeof detail !== 'object') return detail == null || detail === '' ? '—' : String(detail)
  const entries = Object.entries(detail as Row).filter(([key]) => !auditHidden.has(key))
  if (!entries.length) return '—'
  return entries.map(([key, value]) => {
    const text = value == null || value === '' ? '空' : typeof value === 'boolean' ? (value ? '是' : '否') : typeof value === 'object' ? JSON.stringify(value) : String(value)
    return `${auditFields[key] || key}：${text}`
  }).join('；')
}
// 编号规则的用途、日期格式与重置周期名称，设置页与初次安装向导共用。
export const codeRuleNames: Record<string, string> = { project: '项目', sale: '销售单', purchase: '采购单', delivery: '交付单', item: '物料', partner: '往来单位', reconciliation: '对账单', issue_slip: '领料单' }
export const codeDateFormats: Record<string, string> = { YY: '两位年', YYYY: '年', YYYYMM: '年月', YYYYMMDD: '年月日' }
export const codeResetCycles: Record<string, string> = { never: '不重置', year: '每年', month: '每月', day: '每天' }
export const columns: Record<string, Column[]> = {
  users: [
    C('username', '用户名'),
    C('display_name', '姓名'),
    { key: 'roles', label: '角色', format: r => (r.roles ?? [r.role]).map((role: string) => roleLabels[role] || role).join('、') },
    C('hourly_cost', '小时成本'),
    C('management_reports', '总经理报表权限'),
    C('is_active', '启用'),
  ],
  company: [C('name', '公司名称'), C('address', '地址'), C('phone', '电话'), { key: 'locked_through', label: '业务锁账至', format: r => r.locked_through || '未锁账' }],
  codes: [
    { key: 'key', label: '用途', format: r => codeRuleNames[String(r.key)] || r.key },
    C('prefix', '前缀'), { key: 'date_format', label: '日期格式', format: r => r.date_format || '无日期' }, C('padding', '流水位数'),
    { key: 'reset_cycle', label: '重置周期', format: r => codeResetCycles[String(r.reset_cycle)] || r.reset_cycle }, C('counter', '当前序号'),
  ],
  audit: [
    { key: 'actor', label: '操作人', format: r => r.actor_name || (r.actor ? `用户 #${r.actor}` : '系统') },
    { key: 'operation', label: '操作', format: r => auditOperation(r.operation) },
    { key: 'resource', label: '对象', format: r => auditObject(r) },
    { key: 'detail', label: '详情', format: r => auditDetail(r.detail) },
    { key: 'created_at', label: '时间', format: r => dateTimeText(r.created_at) },
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
export function actionNames(resource: string, r: Row): string[] {
  const a: string[] = []
  if (['users', 'company', 'codes'].includes(resource) && can(['admin'])) a.push('编辑')
  if (resource === 'codes' && r.key === 'project' && can(['admin']) && !(r.prefix === 'ATM' && r.date_format === 'YY' && Number(r.padding) === 2 && r.reset_cycle === 'year')) a.push('应用项目规范')
  if (resource === 'company' && can(['admin'])) a.push('锁账与重开')
  return a
}
export async function actionCommand(resource: string, r: Row, name: string): Promise<Command> {
  if (resource === 'codes' && r.key === 'project' && name === '应用项目规范' && can(['admin'])) return {
    title: '应用项目编号规范', path: `${endpoint(resource)}${r.id}/configure/`,
    fields: [t('reason', '应用原因')],
    prepare: data => ({ prefix: 'ATM', date_format: 'YY', padding: 2, reset_cycle: 'year', reason: data.reason, expected_revision: r.revision }),
    notice: { type: 'warning', text: `设置为 ATM＋两位年＋两位流水，每年01–99。当前已用流水为 ${r.counter ?? 0}，不会重置或改写历史项目编号。当前序号达到99后，本年度将无法继续取号；请先核对实际项目数量。` },
  }
  if (resource === 'company' && name === '锁账与重开') return {
    title: name, path: `${endpoint(resource)}${r.id}/period-lock/`,
    fields: [{ key: 'locked_through', label: '锁账截止日期', type: 'date', optional: true, hint: '截止日及以前禁止补录。调早日期可重开部分期间，清空则全部重开。' }, t('reason', '锁账或重开原因')],
    initial: { locked_through: r.locked_through || '' },
    prepare: data => ({ ...data, locked_through: data.locked_through || null, expected_revision: r.period_revision }),
    notice: { type: 'warning', text: '锁账前请完成收退货、工时、费用及资金核对并备份。变更会记录操作者、前后日期和原因；此功能不替代法定会计结账。' },
  }
  if (name === '编辑' && resource === 'codes') return {
    title: '编辑编号规则', path: `${endpoint(resource)}${r.id}/configure/`,
    fields: [t('prefix', '前缀'), select('date_format', '日期格式', choices({ none: '无日期', ...codeDateFormats })),
      t('padding', '流水位数（1–10）'), select('reset_cycle', '重置周期', choices(codeResetCycles)), t('reason', '修改原因')],
    initial: { ...r, date_format: r.date_format || 'none' }, prepare: data => ({ ...data, date_format: data.date_format === 'none' ? '' : data.date_format, expected_revision: r.revision }),
    notice: { type: 'info', text: '项目规范：ATM＋两位年＋两位流水，按年重置。物料选择产品编码类别后按类别＋年份（无图固定99）＋六位流水生成，未分类才使用这里的普通规则。修改不改变历史编码或回退当前流水。' },
  }
  if (name !== '编辑' || !['users', 'company'].includes(resource)) throw new Error('不支持的设置操作。')
  const fields = resource === 'company'
    ? [t('name', '公司名称'), t('address', '地址', true), t('phone', '电话', true)]
    : userFields.map(f => f.key === 'password' ? { ...f, optional: true } : f)
  return { title: name, path: endpoint(resource) + r.id + '/', fields, initial: r, method: 'patch',
    // 公司地址、电话清空后也提交空串，否则 PATCH 不带该字段会保留原值。
    ...(resource === 'company' ? { prepare: (data: Row) => ({ ...data, address: data.address ?? '', phone: data.phone ?? '' }) } : {}) }
}
