import { choices } from './shared'
import { select } from './shared'
export const userFields: Field[] = [
  t('username', '用户名'),
  t('display_name', '姓名'),
  { key: 'roles', label: '角色', type: 'checks', initial: ['member'], hint: '勾选可兼任的岗位，至少选择一个。权限按业务合并，报表需单独授权；本人申请仍需他人审批。',
    options: choices(roleLabels),
  },
  { key: 'hourly_cost', label: '小时成本（元）', initial: '0.00' },
  { key: 'management_reports', label: '总经理报表权限（仅项目经理角色）', type: 'boolean', initial: false },
  { key: 'password', label: '密码', type: 'password' },
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
const auditObjects: Record<string, string> = { sale: '销售', project: '项目', purchase: '采购', purchaseorder: '采购单', task: '任务', bom: 'BOM', document: '附件', stock: '库存', payment: '收付款', entry: '款项', reconciliation: '对账', user: '用户', company: '公司', code: '编号' }
const auditActions: Record<string, string> = { create: '新增', update: '修改', delete: '删除', quote: '报价', sign: '签约', submit: '提交', approve: '批准', reject: '退回', receive: '收货', cancel: '取消', complete: '完成', revise: '变更', upload: '上传', download: '下载', confirm: '确认', void: '冲销' }
function auditOperation(operation: string) {
  const [object, action] = operation.split('.')
  return auditObjects[object!] && auditActions[action!] ? `${auditObjects[object!]} · ${auditActions[action!]}` : operation
}
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
    { key: 'key', label: '用途', format: r => ({ project: '项目', sale: '销售单', purchase: '采购单', delivery: '交付单', item: '物料', partner: '往来单位', reconciliation: '对账单' }[String(r.key)] || r.key) },
    C('prefix', '前缀'), { key: 'date_format', label: '日期格式', format: r => r.date_format || '无日期' }, C('padding', '流水位数'),
    { key: 'reset_cycle', label: '重置周期', format: r => ({ never: '不重置', year: '每年', month: '每月', day: '每天' }[String(r.reset_cycle)] || r.reset_cycle) }, C('counter', '当前序号'),
  ],
  audit: [
    { key: 'actor', label: '操作人', format: r => r.actor ? `用户 #${r.actor}` : '系统' },
    { key: 'operation', label: '操作', format: r => auditOperation(r.operation) },
    C('resource', '对象'),
    C('detail', '详情'),
    { key: 'created_at', label: '时间', format: r => new Date(r.created_at).toLocaleString('zh-CN', { hour12: false }) },
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
    fields: [t('prefix', '前缀'), select('date_format', '日期格式', choices({ none: '无日期', YY: '两位年', YYYY: '年', YYYYMM: '年月', YYYYMMDD: '年月日' })),
      t('padding', '流水位数（1–10）'), select('reset_cycle', '重置周期', choices({ never: '不重置', year: '每年', month: '每月', day: '每天' })), t('reason', '修改原因')],
    initial: { ...r, date_format: r.date_format || 'none' }, prepare: data => ({ ...data, date_format: data.date_format === 'none' ? '' : data.date_format, expected_revision: r.revision }),
    notice: { type: 'info', text: '项目规范：ATM＋两位年＋两位流水，按年重置。物料选择产品编码类别后按类别＋年份（无图固定99）＋六位流水生成，未分类才使用这里的普通规则。修改不改变历史编码或回退当前流水。' },
  }
  if (name !== '编辑' || !['users', 'company'].includes(resource)) throw new Error('不支持的设置操作。')
  const fields = resource === 'company'
    ? [t('name', '公司名称'), t('address', '地址', true), t('phone', '电话', true)]
    : userFields.map(f => f.key === 'password' ? { ...f, optional: true } : f)
  return { title: name, path: endpoint(resource) + r.id + '/', fields, initial: r, method: 'patch' }
}
