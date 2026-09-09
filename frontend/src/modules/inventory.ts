import { all } from '../api'
import { catalog } from '../catalog'
import { can } from '../session'
import type { Command } from '../types'
import type { Field } from '../types'
import type { Row } from '../types'
import type { Column } from '../types'
import { t } from './shared'
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
    C('item_code', '编码'),
    C('item_name', '物料'),
    C('location', '库位'),
    C('quantity', '库存数量'),
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
  const c = await catalog(['projects', 'items'])
  let fields: Field[] = []
  let path = endpoint(resource)
  if (resource === 'stocks') {
    path += 'opening/'
    fields = [
      item(c),
      { key: 'location', label: '库位', initial: '主仓' },
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
  const c = await catalog(['projects', 'items'])
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
    fields = [
      project(c),
      select(
        'task',
        '售后任务（生产领料留空）',
        (await all('/business/tasks/', { kind: 'service', status: 'open' })).map((r) => ({
          value: r.id,
          label: r.title,
        })),
        true,
      ),
      qty,
      reason,
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
