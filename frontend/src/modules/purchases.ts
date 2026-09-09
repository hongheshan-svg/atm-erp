import { options } from '../catalog'
import type { Catalog } from '../catalog'
import { item } from './shared'
import { project } from './shared'
import { date } from './shared'
export const purchaseFields = (c: Catalog): Field[] => [
  project(c),
  select('supplier', '供应商', options(c.partners.filter((p) => p.kind !== 'customer'))),
  date('due_date', '交期'),
  t('note', '说明', true),
  rows('lines', '采购明细', [item(c), qty, price]),
]
import { read } from '../api'
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
    C('due_date', '交期'),
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
    a.push('查看明细')
    if (buyer() && r.status === 'draft') a.push('提交采购')
    if (manager() && r.status === 'submitted') a.push('批准采购')
    if (warehouse() && ['approved', 'partial'].includes(r.status)) a.push('收货')
    if (buyer() && ['draft', 'submitted', 'approved', 'partial'].includes(r.status))
      a.push('取消未收余量')
  }
  return a
}
export async function actionCommand(resource: string, r: Row, name: string): Promise<Command> {
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
  }
  if (routes[name]) path += routes[name] + '/'
  if (['提交采购', '批准采购'].includes(name)) fields = []
  if (['查看明细', '收货'].includes(name)) {
    const detail = await read(endpoint(resource) + r.id + '/')
    readonly = name === '查看明细'
    if (readonly) {
      fields = [
        rows('lines', '采购明细', [
          t('item_name', '物料'),
          qty,
          ...(money() || buyer() ? [price] : []),
          t('received_quantity', '已收'),
          t('cancelled_quantity', '已取消'),
          t('returned_quantity', '已退货'),
        ]),
      ]
      initial = detail
    } else {
      fields = [
        { key: 'location', label: '库位', initial: '主仓' },
        reason,
        rows('lines', '本次收货', [
          select(
            'line',
            '采购物料',
            detail.lines.map((l: Row) => ({ value: l.id, label: l.item_name })),
          ),
          qty,
        ]),
      ]
      initial = {
        lines: detail.lines
          .map((l: Row) => ({
            line: l.id,
            quantity: decimalDifference(l.quantity, l.received_quantity, l.cancelled_quantity),
          }))
          .filter((l: Row) => Number(l.quantity) > 0),
      }
    }
  }
  return { title: name, path, fields, initial, method, readonly }
}
export async function shortageCommand(projectId: number): Promise<Command> {
  const c = await catalog(['projects', 'items', 'partners'])
  const demand = await read(`/business/projects/${projectId}/demand/`)
  const lines = demand.lines.filter((r: Row) => Number(r.shortage) > 0)
  if (!lines.length) throw new Error('当前没有缺料。')
  return {
    title: '按缺料采购',
    path: '/business/purchases/',
    fields: purchaseFields(c).filter((f) => f.key !== 'project'),
    initial: {
      lines: lines.map((r: Row) => ({ item: r.item, quantity: r.shortage, unit_price: '' })),
    },
    prepare: (data) => ({
      ...data,
      project: projectId,
      from_demand: true,
      lines: data.lines.map((r: Row) => ({
        ...r,
        bom_line: lines.find((l: Row) => l.item === Number(r.item))?.bom_line,
      })),
    }),
  }
}
