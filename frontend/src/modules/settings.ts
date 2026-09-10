import { choices } from './shared'
import { select } from './shared'
export const userFields: Field[] = [
  t('username', '用户名'),
  t('display_name', '姓名'),
  { key: 'roles', label: '角色', type: 'checks', initial: ['member'], hint: '勾选可兼任的岗位，至少选择一个。权限按业务合并，报表需单独授权；本人申请仍需他人审批。',
    options: choices({
      admin: '管理员',
      manager: '项目经理',
      sales_manager: '销售经理',
      purchaser: '采购员',
      warehouse: '仓管',
      finance: '财务',
      member: '成员',
    }),
  },
  { key: 'hourly_cost', label: '小时成本（元）', initial: '0.00' },
  { key: 'management_reports', label: '总经理报表权限（仅项目经理角色）', type: 'boolean', initial: false },
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
    { key: 'roles', label: '角色', format: r => (r.roles ?? [r.role]).map((role: string) => ({ admin: '管理员', manager: '项目经理', sales_manager: '销售经理', purchaser: '采购员', warehouse: '仓管', finance: '财务', member: '成员' }[role] || role)).join('、') },
    C('hourly_cost', '小时成本'),
    C('management_reports', '总经理报表权限'),
    C('is_active', '启用'),
  ],
  company: [C('name', '公司名称'), C('address', '地址'), C('phone', '电话'), { key: 'locked_through', label: '业务锁账至', format: r => r.locked_through || '未锁账' }],
  codes: [
    { key: 'key', label: '用途', format: r => ({ project: '项目', sale: '销售单', purchase: '采购单', delivery: '交付单', item: '物料', partner: '往来单位' }[String(r.key)] || r.key) },
    C('prefix', '前缀'), { key: 'date_format', label: '日期格式', format: r => r.date_format || '无日期' }, C('padding', '流水位数'),
    { key: 'reset_cycle', label: '重置周期', format: r => ({ never: '不重置', year: '每年', month: '每月', day: '每天' }[String(r.reset_cycle)] || r.reset_cycle) }, C('counter', '当前序号'),
  ],
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
  if (['users', 'company', 'codes'].includes(resource) && can(['admin'])) a.push('编辑')
  if (resource === 'company' && can(['admin'])) a.push('锁账与重开')
  return a
}
export async function actionCommand(resource: string, r: Row, name: string): Promise<Command> {
  if (resource === 'company' && name === '锁账与重开') return {
    title: name, path: `${endpoint(resource)}${r.id}/period-lock/`,
    fields: [{ key: 'locked_through', label: '锁账截止日期', type: 'date', optional: true, hint: '截止日及以前禁止补录。调早日期可重开部分期间，清空则全部重开。' }, t('reason', '锁账或重开原因')],
    initial: { locked_through: r.locked_through || '' },
    prepare: data => ({ ...data, locked_through: data.locked_through || null, expected_revision: r.period_revision }),
    notice: { type: 'warning', text: '锁账前请完成收退货、工时、费用及资金核对并备份。变更会记录操作者、前后日期和原因；此功能不替代法定会计结账。' },
  }
  if (name === '编辑' && resource === 'codes') return {
    title: '编辑编号规则', path: `${endpoint(resource)}${r.id}/configure/`,
    fields: [t('prefix', '前缀'), select('date_format', '日期格式', choices({ none: '无日期', YYYY: '年', YYYYMM: '年月', YYYYMMDD: '年月日' })),
      t('padding', '流水位数（1–10）'), select('reset_cycle', '重置周期', choices({ never: '不重置', year: '每年', month: '每月', day: '每天' })), t('reason', '修改原因')],
    initial: { ...r, date_format: r.date_format || 'none' }, prepare: data => ({ ...data, date_format: data.date_format === 'none' ? '' : data.date_format, expected_revision: r.revision }),
    notice: { type: 'info', text: '仅影响新编号；格式为前缀＋日期＋流水号。日期须包含重置周期。修改规则不回退当前流水，周期切换后从 1 起；重复编号自动跳过，历史编码保持不变。' },
  }
  if (name !== '编辑' || !['users', 'company'].includes(resource)) throw new Error('不支持的设置操作。')
  const fields = resource === 'company'
    ? [t('name', '公司名称'), t('address', '地址', true), t('phone', '电话', true)]
    : userFields.map(f => f.key === 'password' ? { ...f, optional: true } : f)
  return { title: name, path: endpoint(resource) + r.id + '/', fields, initial: r, method: 'patch' }
}
