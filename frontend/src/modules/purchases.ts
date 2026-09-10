import type { Catalog } from '../catalog'
import { item } from './shared'
import { project } from './shared'
import { date } from './shared'
import { termFields, termLabel } from './payment-terms'
export const purchaseFields = (c: Catalog): Field[] => [
  project(c),
  select('supplier', '供应商', c.partners.filter(p => p.kind !== 'customer').map(p => ({ value: p.id, label: `${p.code} · ${p.name} · ${termLabel(p)}` }))),
  date('due_date', '交期'),
  ...termFields(true),
  { ...date('payment_due_date', '付款到期日'), optional: true, initial: '', hint: '仅指定日期账期填写；现付/月结请留空，实际到期明细在应收应付中查看。历史手工账期留空仍沿用订单交期。' },
  t('note', '说明', true),
  rows('lines', '采购明细', [item(c), qty, price, { ...date('due_date', '明细交期'), optional: true }]),
]
import { all, read } from '../api'
import { manager } from '../session'
import { money } from '../session'
import { decimalDifference } from '../forms'
import type { Command } from '../types'
import type { Field } from '../types'
import type { Row } from '../types'
import type { Column } from '../types'
import { t } from './shared'
import { select } from './shared'
import { rows } from './shared'
import { reason } from './shared'
import { qty } from './shared'
import { price } from './shared'
import { buyer } from './shared'
import { warehouse } from './shared'
import { C } from './shared'
import { endpoint } from './shared'
export const columns: Record<string, Column[]> = {
  purchases: [
    C('code', '采购编号'),
    C('project_name', '项目'),
    C('supplier_name', '供应商'),
    { key: 'payment_term', label: '采购账期', format: termLabel },
    C('status', '状态'),
    C('next_delivery_date', '最近待到货日'), C('payment_due_date', '付款到期日'),
  ],
}
export function createLabel(resource: string) {
  return ({ purchases: buyer() && '新建采购' } as Record<string, string | boolean>)[resource] || ''
}
export async function createCommand(resource: string, projectId?: number): Promise<Command> {
  const c: Catalog = { projects: [], partners: [], items: [], users: [] }
  let fields: Field[] = []
  let path = endpoint(resource)
  if (resource === 'purchases') fields = purchaseFields(c)
  for (const field of fields) {
    if (field.key === 'project') { field.remotePath = '/business/projects/'; field.remoteFilter = r => !['draft', 'quoted', 'closed', 'cancelled'].includes(r.status) }
    if (field.key === 'supplier') { field.remotePath = '/business/partners/'; field.remoteParams = { is_active: true }; field.remoteFilter = r => r.kind !== 'customer' }
    if (field.key === 'lines') field.fields = field.fields!.map(f => f.key === 'item' ? { ...f, remotePath: '/business/items/', remoteParams: { is_active: true } } : f)
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
  if (resource === 'purchases') {
    a.push('查看明细', '处理记录')
    if (['approved', 'partial', 'received'].includes(r.status)) {
      a.push('质保记录')
      if (buyer() || warehouse()) a.push('登记采购质保', '处理采购质保')
    }
    if (buyer() || money()) a.push('附件')
    if (buyer() || money()) a.push('预览采购合同')
    if (buyer() && r.status === 'draft') a.push('修改采购', '提交采购')
    if (manager() && r.can_manage !== false && r.status === 'submitted') a.push('批准采购', '退回修改')
    if (warehouse() && ['approved', 'partial'].includes(r.status)) a.push('收货')
    if (buyer() && ['approved', 'partial'].includes(r.status)) a.push('更新到货计划')
    if (warehouse() && r.lines?.some((l: Row) => Number(l.pending_quantity) > 0)) a.push('隔离品合格入库', '隔离品退回供应商')
    if (buyer() && ['draft', 'submitted', 'approved', 'partial'].includes(r.status))
      a.push('取消未收余量')
  }
  return a
}
export async function actionCommand(resource: string, r: Row, name: string): Promise<Command> {
  if (['质保记录', '登记采购质保', '处理采购质保'].includes(name)) {
    const path = `/business/purchases/${r.id}/warranty/`, info = await read(path)
    if (name === '质保记录') return { title: name, path, readonly: true, initial: { cases: info.cases }, fields: [rows('cases', '质保记录', [t('id', '编号'), t('item', '物料'), t('date', '报修日期'), t('quantity', '数量'), t('description', '故障'), t('status', '状态'), t('response', '供应商响应与处理'), t('warranty_end', '一年质保截止'), t('within_warranty', '报修时在保'), t('replacement', '换货收货流水'), t('returned', '退货流水'), t('expense', '费用原单')])] }
    if (name === '登记采购质保') return { title: name, path, fields: [select('receipt', '原收货批次', info.receipts.map((x: Row) => ({ value: x.id, label: `批次${x.id} · ${x.item} · 数量${x.quantity} · 质保至${x.warranty_end}` }))), date('date', '报修日期'), qty, { key: 'description', label: '故障描述', type: 'textarea' }], notice: { type: 'info', text: '逐批按合格收货日起一年提示质保。登记不改变库存和成本；退换货复用原库存业务，费用由财务登记后关联。' } }
    const moves = await all('/business/moves/', { project: r.project })
    const expenses = money() ? await all('/business/entries/', { project: r.project, kind: 'expense', cancelled: false }) : []
    return { title: name, path, fields: [select('case', '质保事项', info.cases.filter((x: Row) => ['待响应', '维修中'].includes(x.status)).map((x: Row) => ({ value: x.id, label: `${x.id} · ${x.item} · ${x.description}` }))), select('status', '处理结果', [{ value: 'repairing', label: '维修中' }, { value: 'replaced', label: '已更换' }, { value: 'closed', label: '已关闭' }]), { key: 'response', label: '供应商响应、责任与处理说明', type: 'textarea' }, select('replacement', '补换货收货流水', moves.filter(x => x.kind === 'receipt').map(x => ({ value: x.id, label: `${x.id} · ${x.item_name} · ${x.quantity}` })), true), select('returned', '原批次退货流水', moves.filter(x => x.kind === 'purchase_return').map(x => ({ value: x.id, label: `${x.id} · ${x.item_name} · ${x.quantity}` })), true), ...(money() ? [select('expense', '关联已登记费用', expenses.map(x => ({ value: x.id, label: `${x.title} · ${x.amount}` })), true)] : [])], prepare: values => ({ ...values, expected_updated_at: info.cases.find((x: Row) => x.id === Number(values.case))?.updated_at }) }
  }
  if (name === '更新到货计划') {
    const detail = await read(`${endpoint(resource)}${r.id}/`)
    return { title: name, path: `${endpoint(resource)}${r.id}/delivery-plan/`, fields: [reason, { ...rows('lines', '未完成明细', [{ key: 'id', label: '明细ID', hidden: true }, { ...t('item_name', '物料'), readonly: true }, date('due_date', '承诺到货日期')]), readonly: true }], initial: { lines: detail.lines.filter((l: Row) => Number(decimalDifference(l.quantity, l.received_quantity, l.cancelled_quantity)) > 0).map((l: Row) => ({ ...l, due_date: l.due_date || detail.due_date })) }, prepare: data => ({ reason: data.reason, expected_updated_at: detail.updated_at, lines: data.lines.map((l: Row) => ({ id: l.id, due_date: l.due_date })) }), notice: { type: 'info', text: '更新供应商承诺到货日期并留记录，不改变原应付期限。' } }
  }
  if (name === '处理记录') return { title: name, path: '', readonly: true, initial: { lines: (await all(`/business/purchases/${r.id}/handling-history/`)).map(l => ({ ...l, quantity_summary: l.lines.map((row: Row) => `明细${row.line || row.id}：数量 ${row.quantity || '0'}，隔离 ${row.pending_quantity || '0'}`).join('；'), operation: ({ 'purchase.reject': '退回修改', 'purchase.edit': '修改采购', 'purchase.receive': '到货登记', 'purchase.quality_accept': '隔离品合格入库', 'purchase.quality_return': '隔离品退回供应商', 'purchase.delivery_plan': '更新到货计划' } as Record<string, string>)[l.operation] || l.operation })) }, fields: [rows('lines', '处理记录', [t('date', '时间'), t('actor', '操作人'), t('operation', '操作'), t('reason', '原因'), t('quantity_summary', '明细与数量'), t('next_step', '后续处理')])] }
  if (name === '修改采购') {
    const detail = await read(`${endpoint(resource)}${r.id}/`)
    return { title: name, path: `${endpoint(resource)}${r.id}/edit/`, fields: [date('due_date', '交期'), { ...date('payment_due_date', '付款到期日'), optional: true, initial: '' }, t('note', '说明', true), reason, { ...rows('lines', '采购明细', [{ key: 'id', label: '明细ID', hidden: true }, { ...t('item_name', '物料'), readonly: true }, qty, price, date('due_date', '明细交期')]), readonly: true }], initial: { ...detail, lines: detail.lines.map((l: Row) => ({ ...l, due_date: l.due_date || detail.due_date })) }, prepare: data => ({ due_date: data.due_date, payment_due_date: data.payment_due_date, note: data.note, reason: data.reason, expected_updated_at: detail.updated_at, lines: data.lines.map((l: Row) => ({ id: l.id, quantity: l.quantity, unit_price: l.unit_price, due_date: l.due_date })) }) }
  }
  if (name === '批准采购') {
    const check = await read(`/business/purchases/${r.id}/budget-check/`)
    const summary = `本单 ¥${check.purchase_amount}；批准后实际＋在途 ¥${check.occupied_total}；累计采购净额 ¥${check.purchase_net}。`
    if (check.over_budget) return {
      title: '超预算采购审批', path: `/business/purchases/${r.id}/approve-over-budget/`,
      notice: { type: 'warning', text: `${check.warnings.join('；')}。${summary}` },
      fields: [{ ...reason, label: '超预算批准原因', type: 'textarea' }, { key: 'confirmed', label: '确认承担本次超预算采购', type: 'boolean', initial: false }],
      prepare: data => ({ reason: data.reason, confirmed: data.confirmed, expected_snapshot: check.snapshot }),
    }
    return {
      title: name, path: `/business/purchases/${r.id}/approve/`, fields: [{ ...reason, optional: true, hint: '申请人不可自行审批；管理员例外处理本人申请时必填。' }],
      notice: { type: check.configured ? 'info' : 'warning', text: check.configured ? `预算检查通过。${summary}` : `项目未设置预算，本次批准不进行预算拦截。${summary}` },
    }
  }
  let path = endpoint(resource) + r.id + '/'
  let fields: Field[] = [reason]
  let initial: Row = {}
  let method: 'post' | 'patch' = 'post'
  let readonly = false
  const routes: Record<string, string> = {
    提交采购: 'submit',
    批准采购: 'approve',
    收货: 'receive',
    取消未收余量: 'cancel-remainder',
    退回修改: 'reject',
    隔离品合格入库: 'quality-accept',
    隔离品退回供应商: 'quality-return',
  }
  if (routes[name]) path += routes[name] + '/'
  if (['提交采购', '批准采购'].includes(name)) fields = []
  if (['查看明细', '收货', '隔离品合格入库', '隔离品退回供应商'].includes(name)) {
    const detail = await read(endpoint(resource) + r.id + '/')
    readonly = name === '查看明细'
    if (readonly) {
      fields = [
        { key: 'payment_term_label', label: '采购账期' },
        rows('lines', '采购明细', [
          t('item_name', '物料'),
          t('assembly_unit', '单元'),
          t('due_date', '明细交期'),
          qty,
          ...(money() || buyer() ? [price] : []),
          t('received_quantity', '已收'),
          t('cancelled_quantity', '已取消'),
          t('returned_quantity', '已退货'),
          t('pending_quantity', '隔离待处理'),
        ]),
      ]
      initial = { ...detail, payment_term_label: termLabel(detail) }
    } else {
      fields = [
        ...(name === '隔离品退回供应商' ? [] : [{ key: 'location', label: '库位', initial: '主仓' }]),
        ...(name === '隔离品退回供应商' ? [] : [date('received_date', '实际合格收货日期')]),
        reason,
        { ...rows('lines', '本次收货', [
          { key: 'line', label: '明细ID', hidden: true },
          { key: 'item_label', label: '采购物料', readonly: true, displayOnly: true },
          qty,
          ...(name === '收货' ? [{ key: 'pending_quantity', label: '不合格隔离数量', initial: '0' }] : []),
        ]), readonly: true },
      ]
      initial = {
        lines: detail.lines
          .map((l: Row) => ({
            line: l.id,
            item_label: `${l.item_name} · ${l.assembly_unit || '未分单元'}`,
            quantity: name === '收货' ? decimalDifference(l.quantity, l.received_quantity, l.cancelled_quantity, l.pending_quantity || '0') : l.pending_quantity,
            ...(name === '收货' ? { pending_quantity: '0' } : {}),
          }))
          .filter((l: Row) => Number(l.quantity) > 0),
      }
    }
  }
  return { title: name, path, fields, initial, method, readonly }
}
export async function shortageCommand(projectId: number, selectedBomLines?: number[]): Promise<Command> {
  const demand = await read(`/business/projects/${projectId}/demand/`)
  const lines = demand.lines.filter((r: Row) => Number(r.shortage) > 0 && r.is_active !== false && (selectedBomLines === undefined || selectedBomLines.includes(r.bom_line)))
  if (selectedBomLines && lines.length !== new Set(selectedBomLines).size) throw new Error('所选 BOM 的缺口或物料状态已变化，请刷新后重新勾选。')
  if (!lines.length) throw new Error('当前没有缺料。')
  const fields = (await createCommand('purchases', projectId)).fields.filter((f) => f.key !== 'project')
  const detail = fields.find(f => f.key === 'lines')!
  detail.readonly = true
  detail.fields = detail.fields!.flatMap(f => f.key === 'item' ? [{ key: 'item', label: '物料ID', hidden: true }, { key: 'item_label', label: '物料', readonly: true, displayOnly: true }] : [f])
  return {
    title: '按缺料采购',
    path: '/business/purchases/',
    fields,
    notice: { type: 'info', text: `已选 ${lines.length} 项 BOM；数量可调小。保存时重新校验缺口，采购草稿仍需提交审批。` },
    initial: {
      lines: lines.map((r: Row) => ({ item: r.item, item_label: r.item_name || r.name || r.item, bom_line: r.bom_line, quantity: r.shortage, unit_price: '' })),
    },
    prepare: (data) => ({
      ...data,
      project: projectId,
      from_demand: true,
      lines: data.lines.map((r: Row, index: number) => ({
        ...r,
        bom_line: lines[index]?.bom_line,
      })),
    }),
  }
}
