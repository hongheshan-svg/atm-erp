import { read } from '../api'
import { catalog } from '../catalog'
import { manager } from '../session'
import type { Command } from '../types'
import type { Field } from '../types'
import type { Row } from '../types'
import type { Column } from '../types'
import { t } from './shared'
import { rows } from './shared'
import { reason } from './shared'
import { qty } from './shared'
import { C } from './shared'
import { item } from './shared'
import { endpoint } from './shared'
import { productCategories } from '../product-categories'
export const columns: Record<string, Column[]> = {
  bom: [
    C('item_code', '物料编码'),
    C('item_name', '物料名称'),
    C('specification', '规格'), C('drawing_number', '图号'), C('drawing_revision', '图档版本'),
    { key: 'product_category', label: '产品编码类别', format: r => productCategories[r.product_category] || '未分类' },
    C('brand', '品牌'),
    C('assembly_unit', '单元'),
    C('quantity', '需求数量'),
    C('required_date', '需求日期'), C('application_date', '申请日期'), C('applicant', '申请人'),
    C('unit', '单位'),
    C('change_note', '变更说明'),
  ],
}
export function createLabel(resource: string) {
  return ({} as Record<string, string | boolean>)[resource] || ''
}
export async function createCommand(resource: string, projectId?: number): Promise<Command> {
  let fields: Field[] = []
  let path = endpoint(resource)

  return {
    title: String(createLabel(resource)),
    path,
    fields,
    initial: projectId ? { project: projectId } : {},
  }
}
export function actionNames(resource: string, _r: Row): string[] {
  const a: string[] = []
  if (resource === 'bom' && manager()) a.push('移除')
  return a
}
export async function actionCommand(resource: string, r: Row, name: string): Promise<Command> {
  let path = endpoint(resource) + r.id + '/'
  let fields: Field[] = [reason]
  let initial: Row = {}
  let method: 'post' | 'patch' = 'post'
  let readonly = false
  const routes: Record<string, string> = { 移除: 'remove' }
  if (routes[name]) path += routes[name] + '/'

  return { title: name, path, fields, initial, method, readonly }
}
export async function bomCommand(projectId: number): Promise<Command> {
  const [c, demand] = await Promise.all([
    catalog(['items']),
    read(`/business/projects/${projectId}/demand/`),
  ])
  return {
    title: '维护 BOM',
    path: `/business/projects/${projectId}/revise-bom/`,
    previewPath: `/business/projects/${projectId}/bom-change-preview/`,
    fields: [rows('lines', 'BOM 明细', [{ key: 'id', label: 'BOM 行', hidden: true, optional: true }, item(c), qty, t('assembly_unit', '单元', true), { key: 'required_date', label: '需求日期', type: 'date', optional: true }, { key: 'application_date', label: '申请日期', type: 'date', optional: true }, t('applicant', '申请人', true), { ...t('change_note', '变更说明'), hint: 'ECN 请注明图档升级或新增及对应版本。' }])],
    initial: {
      lines: demand.lines.map((r: Row) => ({
        id: r.bom_line,
        item: r.item,
        quantity: r.quantity,
        assembly_unit: r.assembly_unit || '',
        required_date: r.required_date, application_date: r.application_date, applicant: r.applicant || '',
        change_note: '',
      })),
    },
    prepare: (data) => ({ ...data, lines: data.lines.map((r: Row) => ({ ...r, assembly_unit: r.assembly_unit ?? '', required_date: r.required_date || null, application_date: r.application_date || null, applicant: r.applicant || '' })), expected_revision: demand.revision }),
  }
}
