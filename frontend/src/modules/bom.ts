import { read } from '../api'
import { bomEditor } from '../session'
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
export function actionNames(resource: string, r: Row): string[] {
  const a: string[] = []
  if (resource === 'bom' && bomEditor(r)) a.push('修改此行', '移除')
  return a
}
export async function actionCommand(resource: string, r: Row, name: string): Promise<Command> {
  // 单行修改：改一条用量不必打开整张 BOM，也不必把没动过的行一起提交。
  if (name === '修改此行') {
    const demand = await read(`/business/projects/${r.project}/demand/`)
    return {
      title: `修改 ${r.item_code} ${r.item_name}`,
      path: `/business/projects/${r.project}/revise-bom/`,
      previewPath: `/business/projects/${r.project}/bom-change-preview/`,
      fields: [
        { ...t('item_label', '物料'), readonly: true, displayOnly: true },
        qty,
        t('assembly_unit', '单元', true),
        { key: 'required_date', label: '需求日期', type: 'date', optional: true },
        { key: 'application_date', label: '申请日期', type: 'date', optional: true },
        t('applicant', '申请人', true),
        { ...t('change_note', '变更说明'), hint: 'ECN 请注明图档升级或新增及对应版本。' },
      ],
      initial: {
        item_label: [r.item_code, r.item_name, r.specification].filter(Boolean).join(' · '),
        quantity: r.quantity,
        assembly_unit: r.assembly_unit || '',
        required_date: r.required_date,
        application_date: r.application_date,
        applicant: r.applicant || '',
        change_note: '',
      },
      prepare: data => ({
        expected_revision: demand.revision,
        lines: [{
          id: r.id,
          item: r.item,
          quantity: data.quantity,
          assembly_unit: data.assembly_unit ?? '',
          change_note: data.change_note,
          required_date: data.required_date || null,
          application_date: data.application_date || null,
          applicant: data.applicant || '',
        }],
      }),
    }
  }
  return { title: name, path: `${endpoint(resource)}${r.id}/${name === '移除' ? 'remove/' : ''}`, fields: [reason] }
}
export async function bomCommand(projectId: number): Promise<Command> {
  const demand = await read(`/business/projects/${projectId}/demand/`)
  return {
    title: '新增或修改 BOM 行',
    path: `/business/projects/${projectId}/revise-bom/`,
    previewPath: `/business/projects/${projectId}/bom-change-preview/`,
    // 以前这里把整张 BOM 灌进表单，几百行的项目根本改不动，而服务端本来就只更新提交到的行。
    notice: { type: 'info', text: `本项目现有 ${demand.lines.length} 行。这里只填要新增或修改的物料，没有列出的行保持不变；改单条用量可直接在「BOM 明细」里用「修改此行」。整批替换请用导入。` },
    fields: [{ ...rows('lines', '本次变更', [item(), qty, t('assembly_unit', '单元', true), { key: 'required_date', label: '需求日期', type: 'date', optional: true }, { key: 'application_date', label: '申请日期', type: 'date', optional: true }, t('applicant', '申请人', true), { ...t('change_note', '变更说明', true), hint: 'ECN 请注明图档升级或新增及对应版本；修改已有行必填，新增行可留空。' }]), compact: true }],
    prepare: (data) => ({ ...data, lines: data.lines.map((r: Row) => ({ ...r, assembly_unit: r.assembly_unit ?? '', required_date: r.required_date || null, application_date: r.application_date || null, applicant: r.applicant || '' })), expected_revision: demand.revision }),
  }
}
