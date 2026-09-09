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
import { all, download, read } from '../api'
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
    C('method', '结算方式'), C('account', '账户标识'), C('reference', '银行流水号'),
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
  if (resource === 'entries') a.push('查看收付流水')
  if (resource === 'payments' && r.document) a.push('下载凭证')
  if (resource === 'payments') a.push('查看凭证')
  if (resource === 'payments' && finance()) a.push('补录凭证')
  if (resource === 'entries' && finance()) {
    if (Number(r.balance) > 0) a.push('登记收付款')
    if (Number(r.balance) < 0) a.push('退款')
    if (r.kind === 'expense' && !r.cancelled) a.push('取消费用')
  }
  if (resource === 'payments' && finance() && !r.reversal_of && !r.reversed_by) a.push('冲销付款')
  return a
}
export async function actionCommand(resource: string, r: Row, name: string): Promise<Command> {
  if (name === '补录凭证') {
    const docs = await all('/business/documents/', { project: r.project, category: 'receipt' })
    return { title: name, path: `/business/payments/${r.id}/attach-evidence/`, fields: [{ key: 'document', label: '凭证（项目附件中上传）', type: 'select', options: docs.map(d => ({ value: d.id, label: d.original_name })) }, reason], notice: { type: 'info', text: '追加凭证并留痕，不覆盖原付款金额和历史凭证。' } }
  }
  if (name === '查看凭证') {
    const detail = await read(`/business/payments/${r.id}/`)
    return { title: name, path: '', readonly: true, initial: { lines: detail.evidence }, fields: [{ key: 'lines', label: '凭证记录', type: 'rows', fields: [t('name', '文件'), t('reason', '说明'), t('actor', '补录人'), t('date', '补录时间')] }], actions: detail.evidence.map((d: Row) => ({ label: `下载 ${d.name}`, run: async () => { const doc = await read(`/business/documents/${d.document}/`); await download(doc.download_url, doc.original_name) } })) }
  }
  if (name === '查看收付流水') return { title: name, path: '', readonly: true, initial: { lines: await all('/business/payments/', { entry: r.id }) }, fields: [{ key: 'lines', label: '收付流水', type: 'rows', fields: [t('id', '流水ID'), t('date', '日期'), t('amount', '金额'), t('method', '方式'), t('account', '账户'), t('reference', '银行流水号'), t('reason', '说明'), t('reversal_of', '冲销原记录'), t('document', '凭证ID')] }] }
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
    const docs = await all('/business/documents/', { project: r.project, category: 'receipt' })
    fields = [t('amount', '金额（元）'), date(), reason, { key: 'method', label: '结算方式', type: 'select', optional: true, options: [{ value: 'bank', label: '银行转账' }, { value: 'cash', label: '现金' }, { value: 'other', label: '其他' }] }, t('account', '账户标识', true), t('reference', '银行流水号', true), { key: 'document', label: '结算凭证（先在项目附件上传）', type: 'select', optional: true, options: docs.map(d => ({ value: d.id, label: d.original_name })) }]
    initial = { amount: String(r.balance).replace(/^-/, '') }
  }
  if (name === '冲销付款') fields = [date(), reason]
  return { title: name, path, fields, initial, method, readonly }
}
