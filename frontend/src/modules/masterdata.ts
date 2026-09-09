import type { Command } from '../types'
import type { Field } from '../types'
import type { Row } from '../types'
import type { Column } from '../types'
import { t } from './shared'
import { select } from './shared'
import { choices } from './shared'
import { buyer } from './shared'
import { C } from './shared'
import { endpoint } from './shared'
export const columns: Record<string, Column[]> = {
  items: [
    C('code', '编码'),
    C('name', '物料'),
    C('specification', '规格'),
    C('unit', '单位'),
    C('is_active', '启用'),
  ],
  partners: [
    C('code', '编码'),
    C('name', '往来单位'),
    C('kind', '类型'),
    C('contact', '联系人'),
    C('phone', '电话'),
    C('is_active', '启用'),
  ],
}
export function createLabel(resource: string) {
  return (
    (
      { items: buyer() && '新增物料', partners: buyer() && '新增往来单位' } as Record<
        string,
        string | boolean
      >
    )[resource] || ''
  )
}
export async function createCommand(resource: string, projectId?: number): Promise<Command> {
  let fields: Field[] = []
  let path = endpoint(resource)
  if (resource === 'items')
    fields = [
      t('name', '物料名称'),
      t('specification', '规格', true),
      { key: 'unit', label: '单位', initial: '件' },
    ]
  if (resource === 'partners')
    fields = [
      t('name', '单位名称'),
      select(
        'kind',
        '类型',
        choices({ customer: '客户', supplier: '供应商', both: '客户及供应商' }),
      ),
      t('contact', '联系人', true),
      t('phone', '电话', true),
      t('address', '地址', true),
    ]
  return {
    title: String(createLabel(resource)),
    path,
    fields,
    initial: projectId ? { project: projectId } : {},
  }
}
export function actionNames(resource: string, _r: Row): string[] {
  const a: string[] = []
  if (['items', 'partners'].includes(resource) && buyer()) a.push('编辑')
  return a
}
export async function actionCommand(resource: string, r: Row, name: string): Promise<Command> {
  if (name !== '编辑' || !['items', 'partners'].includes(resource)) throw new Error('不支持的基础资料操作。')
  return {
    title: name, path: endpoint(resource) + r.id + '/', method: 'patch', initial: r,
    fields: [...(await createCommand(resource)).fields, { key: 'is_active', label: '启用', type: 'boolean' }],
  }
}
