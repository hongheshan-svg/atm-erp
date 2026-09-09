import { options } from '../catalog'
import type { Catalog } from '../catalog'
import { item } from './shared'
import { project } from './shared'
import { date } from './shared'
export const purchaseFields = (c: Catalog): Field[] => [
  project(c),
  select('supplier', '供应商', options(c.partners.filter((p) => p.kind !== 'customer'))),
  date('due_date', '交期'),
  { ...date('payment_due_date', '付款到期日'), optional: true, hint: '独立于到货日期；留空沿用订单交期，批准前请核对。' },
  t('note', '说明', true),
  rows('lines', '采购明细', [item(c), qty, price, { ...date('due_date', '明细交期'), optional: true }]),
]
import { all, read } from '../api'
import { catalog } from '../catalog'
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
    C('status', '状态'),
    C('next_delivery_date', '最近待到货日'), C('payment_due_date', '付款到期日'),
  ],
}
export function createLabel(resource: string) {
  return ({ purchases: buyer() && '新建采购' } as Record<string, string | boolean>)[resource] || ''
}
export async function createCommand(resource: string, projectId?: number): Promise<Command> {
  const c = await catalog(['projects', 'partners', 'items'])
  let fields: Field[] = []
  let path = endpoint(resource)
  if (resource === 'purchases') fields = purchaseFields(c)
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
    if (buyer() || money()) a.push('附件')
    if (buyer() && r.status === 'draft') a.push('修改采购', '提交采购')
    if (manager() && r.status === 'submitted') a.push('批准采购', '退回修改')
    if (warehouse() && ['approved', 'partial'].includes(r.status)) a.push('收货')
    if (buyer() && ['approved', 'partial'].includes(r.status)) a.push('更新到货计划')
    if (warehouse() && r.lines?.some((l: Row) => Number(l.pending_quantity) > 0)) a.push('隔离品合格入库', '隔离品退回供应商')
    if (buyer() && ['draft', 'submitted', 'approved', 'partial'].includes(r.status))
      a.push('取消未收余量')
  }
  return a
}
export async function actionCommand(resource: string, r: Row, name: string): Promise<Command> {
  if (name === '更新到货计划') {
    const detail = await read(`${endpoint(resource)}${r.id}/`)
    return { title: name, path: `${endpoint(resource)}${r.id}/delivery-plan/`, fields: [reason, { ...rows('lines', '未完成明细', [{ key: 'id', label: '明细ID', hidden: true }, { ...t('item_name', '物料'), readonly: true }, date('due_date', '承诺到货日期')]), readonly: true }], initial: { lines: detail.lines.filter((l: Row) => Number(decimalDifference(l.quantity, l.received_quantity, l.cancelled_quantity)) > 0).map((l: Row) => ({ ...l, due_date: l.due_date || detail.due_date })) }, prepare: data => ({ reason: data.reason, expected_updated_at: detail.updated_at, lines: data.lines.map((l: Row) => ({ id: l.id, due_date: l.due_date })) }), notice: { type: 'info', text: '更新供应商承诺到货日期并留记录，不改变原应付期限。' } }
  }
  if (name === '处理记录') return { title: name, path: '', readonly: true, initial: { lines: (await all(`/business/purchases/${r.id}/handling-history/`)).map(l => ({ ...l, quantity_summary: l.lines.map((row: Row) => `明细${row.line || row.id}：数量 ${row.quantity || '0'}，隔离 ${row.pending_quantity || '0'}`).join('；'), operation: ({ 'purchase.reject': '退回修改', 'purchase.edit': '修改采购', 'purchase.receive': '到货登记', 'purchase.quality_accept': '隔离品合格入库', 'purchase.quality_return': '隔离品退回供应商', 'purchase.delivery_plan': '更新到货计划' } as Record<string, string>)[l.operation] || l.operation })) }, fields: [rows('lines', '处理记录', [t('date', '时间'), t('actor', '操作人'), t('operation', '操作'), t('reason', '原因'), t('quantity_summary', '明细与数量'), t('next_step', '后续处理')])] }
  if (name === '修改采购') {
    const detail = await read(`${endpoint(resource)}${r.id}/`)
    return { title: name, path: `${endpoint(resource)}${r.id}/edit/`, fields: [date('due_date', '交期'), { ...date('payment_due_date', '付款到期日'), optional: true }, t('note', '说明', true), reason, { ...rows('lines', '采购明细', [{ key: 'id', label: '明细ID', hidden: true }, { ...t('item_name', '物料'), readonly: true }, qty, price, date('due_date', '明细交期')]), readonly: true }], initial: { ...detail, lines: detail.lines.map((l: Row) => ({ ...l, due_date: l.due_date || detail.due_date })) }, prepare: data => ({ due_date: data.due_date, payment_due_date: data.payment_due_date, note: data.note, reason: data.reason, expected_updated_at: detail.updated_at, lines: data.lines.map((l: Row) => ({ id: l.id, quantity: l.quantity, unit_price: l.unit_price, due_date: l.due_date })) }) }
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
      title: name, path: `/business/purchases/${r.id}/approve/`, fields: [],
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
      initial = detail
    } else {
      fields = [
        ...(name === '隔离品退回供应商' ? [] : [{ key: 'location', label: '库位', initial: '主仓' }]),
        reason,
        rows('lines', '本次收货', [
          select(
            'line',
            '采购物料',
            detail.lines.map((l: Row) => ({ value: l.id, label: `${l.item_name} · ${l.assembly_unit || '未分单元'}` })),
          ),
          qty,
          ...(name === '收货' ? [{ key: 'pending_quantity', label: '不合格隔离数量', initial: '0' }] : []),
        ]),
      ]
      initial = {
        lines: detail.lines
          .map((l: Row) => ({
            line: l.id,
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
  const c = await catalog(['projects', 'items', 'partners'])
  const demand = await read(`/business/projects/${projectId}/demand/`)
  const lines = demand.lines.filter((r: Row) => Number(r.shortage) > 0 && r.is_active !== false && (selectedBomLines === undefined || selectedBomLines.includes(r.bom_line)))
  if (selectedBomLines && lines.length !== new Set(selectedBomLines).size) throw new Error('所选 BOM 的缺口或物料状态已变化，请刷新后重新勾选。')
  if (!lines.length) throw new Error('当前没有缺料。')
  const fields = purchaseFields(c).filter((f) => f.key !== 'project')
  const detail = fields.find(f => f.key === 'lines')!
  detail.readonly = true
  detail.fields = detail.fields!.map(f => f.key === 'item' ? { ...f, readonly: true, options: f.options?.filter(o => lines.some((r: Row) => r.item === o.value)) } : f)
  return {
    title: '按缺料采购',
    path: '/business/purchases/',
    fields,
    notice: { type: 'info', text: `已选 ${lines.length} 项 BOM；数量可调小。保存时重新校验缺口，采购草稿仍需提交审批。` },
    initial: {
      lines: lines.map((r: Row) => ({ item: r.item, bom_line: r.bom_line, quantity: r.shortage, unit_price: '' })),
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
