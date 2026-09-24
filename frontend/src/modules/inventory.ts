import { all, read } from '../api'
import { can } from '../session'
import type { Command } from '../types'
import type { Field } from '../types'
import type { Row } from '../types'
import type { Column } from '../types'
import { t } from './shared'
import { display } from './shared'
import { select } from './shared'
import { reason } from './shared'
import { qty } from './shared'
import { warehouse } from './shared'
import { C } from './shared'
import { project } from './shared'
import { item } from './shared'
import { endpoint } from './shared'
export const columns: Record<string, Column[]> = {
  stocks: [
    C('item_code', '物料编码'),
    C('item_name', '物料名称'),
    C('specification', '规格'), C('brand', '品牌'),
    { key: 'part_type', label: '类别', format: row => (({ standard: '标准件', custom: '非标件' } as Record<string, string>)[row.part_type] || '未分类') },
    C('location', '库位'),
    { key: 'quantity', label: '库存数量', format: row => (row.quantity == null ? display(row.quantity) : `${row.quantity}${row.unit ? ` ${row.unit}` : ''}`) },
  ],
  moves: [
    C('item_name', '物料'),
    C('location', '库位'),
    C('kind', '类型'),
    C('quantity', '数量'),
    C('reason', '说明'),
    C('created_at', '时间'),
  ],
}
export function createLabel(resource: string) {
  return (
    ({ stocks: can(['admin']) && '期初入库' } as Record<string, string | boolean>)[resource] || ''
  )
}
export async function createCommand(resource: string, projectId?: number): Promise<Command> {
  let fields: Field[] = []
  let path = endpoint(resource)
  if (resource === 'stocks') {
    path += 'opening/'
    const locations: string[] = await read('/business/stocks/locations/')
    fields = [
      item(),
      { key: 'location', label: '库位', initial: '主仓', suggestions: locations, hint: '期初可建立新库位；全角字符和多余空格会自动统一。' },
      qty,
      t('unit_cost', '单位成本（元）'),
      reason,
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
  if (resource === 'stocks' && warehouse()) a.push('领料', '盘点')
  if (resource === 'moves' && warehouse()) {
    if (r.kind === 'issue') a.push('退料')
    if (r.kind === 'receipt') a.push('采购退货')
  }
  return a
}
export async function actionCommand(resource: string, r: Row, name: string): Promise<Command> {
  let path = endpoint(resource) + r.id + '/'
  let fields: Field[] = [reason]
  let initial: Row = {}
  let method: 'post' | 'patch' = 'post'
  let readonly = false
  let prepare: Command['prepare']
  const routes: Record<string, string> = {
    盘点: 'count',
    退料: 'return-material',
    采购退货: 'return-purchase',
  }
  if (routes[name]) path += routes[name] + '/'
  if (name === '领料') {
    path = '/business/stocks/issue/'
    const tasks = await all('/business/tasks/', { kind: 'service', status: 'open' })
    fields = [
      project(),
      {
        ...select('task', '售后任务（生产领料留空）', [], true),
        // 只列所选项目的售后任务；别的项目的任务选了也会被服务端拒绝。
        optionsFor: (data) => tasks.filter((task) => String(task.project) === String(data.project)).map((task) => ({ value: task.id, label: task.title })),
      },
      qty,
      reason,
      {
        key: 'confirm_shared',
        label: '确认占用其他项目到货',
        type: 'boolean',
        initial: false,
        optional: true,
        hint: '库存不按项目预留。系统提示本次领料会用到其他项目已到货、未领用的物料时，确认挪用再勾选，并通知相关项目补采。',
      },
    ]
    prepare = (data) => ({ ...data, stock: r.id })
  }
  if (name === '盘点') {
    fields = [
      { ...qty, label: '实盘数量' },
      ...(Number(r.quantity) === 0 && can(['admin']) ? [t('unit_cost', '盘盈单位成本（元）')] : []),
      reason,
    ]
    initial = { quantity: r.quantity }
    prepare = (data) => ({
      ...data,
      expected_quantity: r.quantity,
      expected_updated_at: r.updated_at,
    })
  }
  if (['退料', '采购退货'].includes(name)) fields = [qty, reason]
  return { title: name, path, fields, initial, method, readonly, prepare }
}
