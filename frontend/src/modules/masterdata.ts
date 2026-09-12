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
import { materialEditor, partnerEditor, customerOnly } from '../session'
import { termFields, termLabel } from './payment-terms'
import { productCategories } from '../product-categories'
export const columns: Record<string, Column[]> = {
  items: [
    C('code', '物料编码'),
    C('name', '物料名称'),
    C('specification', '规格'),
    C('drawing_number', '图号'), C('drawing_revision', '图档版本'),
    { key: 'product_category', label: '产品编码类别', format: r => productCategories[r.product_category] || '未分类' },
    C('brand', '品牌'),
    { key: 'part_type', label: '物料类别', format: r => ({ standard: '标准件', custom: '非标件' }[String(r.part_type)] || '未分类') },
    C('unit', '单位'),
    C('is_active', '启用'),
  ],
  partners: [
    C('code', '编码'),
    C('name', '往来单位'),
    C('kind', '类型'),
    C('contact', '联系人'),
    C('phone', '电话'),
    { key: 'payment_term', label: '采购账期', format: r => r.kind === 'customer' ? '—' : termLabel(r) },
    C('address', '地址'),
    C('is_active', '启用'),
  ],
}
export function createLabel(resource: string) {
  return (
    (
      { items: materialEditor() && '新增物料', partners: partnerEditor() && '新增往来单位' } as Record<
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
      t('code', '物料编码（留空自动生成）', true),
      t('name', '物料名称'),
      t('specification', '规格', true),
      { ...t('drawing_number', '图号', true), hint: '有图产品必填；工程图示例 A26-E-05-P-000001，模具子图 ATM-T1-P-000001。历史图号可保留。' },
      t('drawing_revision', '图档版本', true),
      { ...select('product_category', '产品编码类别', choices(productCategories), true), hint: '选择类别后自动生成10位编码：有图使用当年年份，无图固定99，流水六位。未分类沿用普通编号规则；版本升级须新增物料。' },
      t('brand', '品牌', true),
      select('part_type', '物料类别', choices({ standard: '标准件', custom: '非标件' }), true),
      { key: 'unit', label: '单位', initial: '件' },
      { ...t('duplicate_reason', '相同物料独立编码原因', true), hint: '名称、规格、品牌、单位和类别完全相同时必填；优先使用现有编码。' },
    ]
  if (resource === 'partners')
    fields = [
      t('name', '单位名称'),
      select(
        'kind',
        '类型',
        choices(customerOnly() ? { customer: '客户' } : { customer: '客户', supplier: '供应商', both: '客户及供应商' }),
      ),
      t('contact', '联系人', true),
      t('phone', '电话', true),
      t('address', '地址', true),
      ...(!customerOnly() ? termFields() : []),
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
  if (resource === 'items' && materialEditor()) a.push('编辑')
  if (resource === 'partners' && buyer()) a.push('编辑')
  if (resource === 'partners' && customerOnly() && _r.kind === 'customer') a.push('编辑')
  return a
}
export async function actionCommand(resource: string, r: Row, name: string): Promise<Command> {
  if (name !== '编辑' || !['items', 'partners'].includes(resource)) throw new Error('不支持的基础资料操作。')
  return {
    title: name, path: endpoint(resource) + r.id + '/', method: 'patch', initial: r,
    fields: [...(await createCommand(resource)).fields.filter(f => f.key !== 'code').map(f => resource === 'items' && r.product_category && ['product_category', 'specification', 'drawing_number', 'drawing_revision'].includes(f.key) ? { ...f, readonly: true, displayOnly: true } : f), { key: 'is_active', label: '启用', type: 'boolean' }],
    prepare: data => resource === 'items' ? { ...data, brand: data.brand ?? '', part_type: data.part_type ?? '' } : data,
  }
}
