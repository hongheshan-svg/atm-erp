import { read } from '../api'
import { bomEditor } from '../session'
import type { Command } from '../types'
import type { Field } from '../types'
import type { Row } from '../types'
import type { Column } from '../types'
import { t } from './shared'
import { rows } from './shared'
import { reason } from './shared'
import { qty as baseQty } from './shared'
import { C } from './shared'
import { item } from './shared'
import { endpoint } from './shared'
import { productCategories } from '../product-categories'
import { quantityText } from '../utils/quantity'
const qty: Field = { ...baseQty, numeric: { scale: 3, min: 0.001 } }
export const columns: Record<string, Column[]> = {
  bom: [
    C('item_code', '物料编码'),
    C('item_name', '物料名称'),
    C('specification', '规格'), C('drawing_number', '图号'), C('drawing_revision', '图档版本'),
    { key: 'product_category', label: '产品编码类别', format: r => productCategories[r.product_category] || '未分类' },
    C('brand', '品牌'),
    C('assembly_unit', '单元'),
    { key: 'quantity', label: '需求数量', format: r => quantityText(r.quantity) },
    C('required_date', '需求日期'), C('application_date', '申请日期'), C('applicant', '申请人'),
    C('unit', '单位'),
    C('change_note', '变更说明'),
  ],
}
// 本项目已用的单元名做输入候选：同一工位只差一个空格也会被当成新单元，新增一行、需求虚增。
export const unitNames = (lines: Row[]) => [...new Set<string>(lines.map(line => String(line.assembly_unit || '')).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'zh-CN', { numeric: true }))
const unitField = (lines: Row[], optional = true): Field => ({ ...t('assembly_unit', '单元', optional), suggestions: unitNames(lines), placeholder: '可下拉选择现有单元' })
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
  // 带图号的非标件可一步升版：自动建新版本物料并换版；其他物料换型号用「替换物料」。
  if (resource === 'bom' && bomEditor(r)) a.push('修改此行', ...(r.drawing_number ? ['升版'] : []), '替换物料', '移除')
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
        unitField(demand.lines),
        { key: 'required_date', label: '需求日期', type: 'date', optional: true },
        { key: 'application_date', label: '申请日期', type: 'date', optional: true },
        t('applicant', '申请人', true),
        { ...t('change_note', '变更说明'), hint: 'ECN 请注明图档升级或新增及对应版本。' },
      ],
      initial: {
        item_label: [r.item_code, r.item_name, r.specification].filter(Boolean).join(' · '),
        quantity: quantityText(r.quantity, ''),
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
  // 升版或换型：一次提交在原单元新增新物料并移除原行，不出现新旧两行同时算缺料的中间状态。
  if (name === '替换物料') {
    return {
      title: `替换 ${r.item_code} ${r.item_name}`,
      submitLabel: '确认替换',
      path: `/business/bom/${r.id}/replace/`,
      notice: { type: 'info', text: revisionNotice(r) },
      successNote: revisionResult,
      fields: [
        { ...t('item_label', '原物料'), readonly: true, displayOnly: true },
        item({ label: '新物料', hint: r.drawing_number ? '同图号升版可直接用「升版」，不必先新建物料。' : '换成另一个型号的在用物料。' }),
        qty,
        { key: 'required_date', label: '需求日期', type: 'date', optional: true },
        { key: 'application_date', label: '申请日期', type: 'date', optional: true },
        t('applicant', '申请人', true),
        { ...t('change_note', '变更说明'), hint: '写明替换原因，如 ECN 编号、图档版本或停产替代。' },
      ],
      initial: {
        item_label: [r.item_code, r.item_name, r.specification, r.assembly_unit || '未分单元'].filter(Boolean).join(' · '),
        quantity: quantityText(r.quantity, ''),
        required_date: r.required_date,
        application_date: r.application_date,
        applicant: r.applicant || '',
        change_note: '',
      },
      prepare: data => ({ ...data, required_date: data.required_date || null, application_date: data.application_date || null, applicant: data.applicant || '' }),
    }
  }
  // 一步升版：复制原物料资料建新版本物料（同图号同版本已有则复用），在原单元换版；可勾选同物料的其他项目一并换版。
  if (name === '升版') {
    const scope = await read(`/business/bom/${r.id}/upgrade-scope/`) as Row[]
    const writable = scope.filter(row => row.writable)
    const locked = scope.filter(row => !row.writable)
    return {
      title: `升版 ${r.item_code} ${r.item_name}`,
      submitLabel: '确认升版',
      path: `/business/bom/${r.id}/upgrade/`,
      notice: { type: 'info', text: revisionNotice(r) + (locked.length ? ` 项目 ${locked.map(row => row.code).join('、')} 也在用此物料，需由该项目的工程师或项目经理换版。` : '') },
      successNote: revisionResult,
      fields: [
        { ...t('item_label', '原物料'), readonly: true, displayOnly: true },
        { ...t('drawing_revision', '新图档版本'), hint: `原版本 ${r.drawing_revision || '（空）'}。同图号、同版本的物料已存在时直接使用，否则自动新建物料编码。` },
        { ...t('name', '物料名称', true), hint: '留空沿用原名称。' },
        { ...t('specification', '规格', true), hint: '新版规格有变化时填写，留空沿用原规格。' },
        qty,
        { ...t('change_note', '变更说明'), hint: '写明 ECN 编号、改了什么。' },
        ...(writable.length ? [{
          key: 'projects',
          label: '同时换版的其他项目',
          type: 'checks' as const,
          optional: true,
          options: writable.map(row => ({ value: row.id, label: `${row.code} ${row.name}（${row.units.join('、')}，共 ${quantityText(row.quantity)}）` })),
          hint: '默认只改本项目。勾选的项目里该物料的所有单元都换成新版，数量不变，在途同样按新图改单。',
        }] : []),
      ],
      initial: {
        item_label: [r.item_code, r.item_name, r.specification, `图号 ${r.drawing_number}`, r.drawing_revision ? `版本 ${r.drawing_revision}` : '', r.assembly_unit || '未分单元'].filter(Boolean).join(' · '),
        drawing_revision: '',
        name: '',
        specification: '',
        quantity: quantityText(r.quantity, ''),
        change_note: '',
        projects: [],
      },
      prepare: data => {
        const payload: Row = { drawing_revision: data.drawing_revision, quantity: data.quantity, change_note: data.change_note, projects: data.projects || [] }
        if (data.name) payload.name = data.name
        if (data.specification) payload.specification = data.specification
        return payload
      },
    }
  }
  // 移除前写明是哪一行：同一物料常分布在多个单元，标题和提示里给出编码、名称、单元和数量。
  if (name === '移除') {
    const unitName = r.assembly_unit || '未分单元'
    return {
      title: `移除 ${r.item_code} ${r.item_name}（${unitName}）`,
      submitLabel: '确认移除',
      path: `${endpoint(resource)}${r.id}/remove/`,
      notice: { type: 'warning', text: `将从本项目 BOM 移除「${unitName}」的这一行：${r.item_code} ${r.item_name}，需求 ${quantityText(r.quantity)}${r.unit ? ` ${r.unit}` : ''}。该行有在途采购，或移除后其余单元不够覆盖已领时会被拦截。` },
      fields: [reason],
    }
  }
  return { title: name, path: `${endpoint(resource)}${r.id}/`, fields: [reason] }
}
function revisionNotice(r: Row): string {
  return `将在「${r.assembly_unit || '未分单元'}」换成新物料并移除原行。原物料未到货的采购会按新图改单（已批准的需采购向供应商确认后才能收货）；已到货、已领用超出需求的原物料进入「旧版待处理」，由仓管报废或留作备件、采购开返修单。`
}
// 换版提交后说明在途采购怎么处理了，让工程师知道要通知谁。
export function revisionResult(result: Row): string {
  const converted = [...(result.converted || []), ...(result.projects || []).flatMap((row: Row) => row.changes.flatMap((change: Row) => change.converted))]
  const pending = converted.filter((row: Row) => row.pending).map((row: Row) => row.code)
  const changed = converted.filter((row: Row) => !row.pending).map((row: Row) => row.code)
  const others = (result.projects || []).map((row: Row) => row.code)
  return [
    result.item_code ? `新版物料 ${result.item_code}${result.created_item ? '（新建）' : ''}。` : '',
    others.length ? `已同时换版：${others.join('、')}。` : '',
    changed.length ? `未批准的采购 ${[...new Set(changed)].join('、')} 已直接改成新版。` : '',
    pending.length ? `已批准的采购 ${[...new Set(pending)].join('、')} 已转新版，待采购向供应商确认。` : '',
  ].join('')
}
export async function bomCommand(projectId: number): Promise<Command> {
  const demand = await read(`/business/projects/${projectId}/demand/`)
  return {
    title: '维护 BOM',
    path: `/business/projects/${projectId}/revise-bom/`,
    previewPath: `/business/projects/${projectId}/bom-change-preview/`,
    // 以前这里把整张 BOM 灌进表单，几百行的项目根本改不动，而服务端本来就只更新提交到的行。
    notice: { type: 'info', text: `本项目现有 ${demand.lines.length} 行。这里只填要新增或修改的物料，没有列出的行保持不变；改单条用量可直接在列表行尾「操作」里用「修改此行」。批量新增或修改请用导入（不会移除未列出的行）。单元可下拉选现有单元：填现有单元名即修改该行，填新单元名才新增一行；单元留空＝沿用该物料原单元，物料已在多个单元有用料时不能留空。` },
    fields: [{ ...rows('lines', '本次变更', [item(), qty, unitField(demand.lines), { key: 'required_date', label: '需求日期', type: 'date', optional: true }, { key: 'application_date', label: '申请日期', type: 'date', optional: true }, t('applicant', '申请人', true), t('change_note', '变更说明', true)]), dense: true, hint: '数量填整个项目本单元的总需求（含全部设备，系统不再乘设备台数）；同一项目统一单元名称。变更说明：ECN 请注明图档升级或新增及对应版本，修改已有行必填，新增行可留空。' }],
    prepare: (data) => ({ ...data, lines: data.lines.map(({ assembly_unit, ...r }: Row) => ({ ...r, ...(assembly_unit ? { assembly_unit } : {}), required_date: r.required_date || null, application_date: r.application_date || null, applicant: r.applicant || '' })), expected_revision: demand.revision }),
  }
}
// 工程师按筛选结果批量改需求日期或单元：前端把所选行组成一次修订提交，一次预览、一次说明。
export function batchReviseCommand(projectId: number, revision: string, lines: Row[], kind: 'date' | 'unit', units: string[] = []): Command {
  const field: Field = kind === 'date'
    ? { key: 'required_date', label: '新的需求日期', type: 'date' }
    : { ...t('assembly_unit', '新的单元'), suggestions: units, placeholder: '可下拉选择现有单元' }
  return {
    title: kind === 'date' ? `批量改需求日期（${lines.length} 行）` : `批量改单元（${lines.length} 行）`,
    submitLabel: `确认修改 ${lines.length} 行`,
    path: `/business/projects/${projectId}/revise-bom/`,
    previewPath: `/business/projects/${projectId}/bom-change-preview/`,
    notice: { type: 'info', text: `只改所选 ${lines.length} 行的${kind === 'date' ? '需求日期' : '单元'}，数量和其他信息不变；变更说明对每行生效并记入变更记录。` },
    fields: [field, { ...t('change_note', '变更说明'), hint: '如“03 单元整体延期两周”。' }],
    prepare: data => ({
      expected_revision: revision,
      lines: lines.map(line => ({
        id: line.bom_line,
        item: line.item,
        quantity: line.quantity,
        change_note: data.change_note,
        ...(kind === 'date' ? { required_date: data.required_date || null } : { assembly_unit: data.assembly_unit }),
      })),
    }),
  }
}
export function batchRemoveCommand(projectId: number, lines: Row[]): Command {
  return {
    title: `批量移除 BOM（${lines.length} 行）`,
    submitLabel: `确认移除 ${lines.length} 行`,
    path: '/business/bom/remove-batch/',
    notice: { type: 'warning', text: '所选行在一次提交中移除；任一行关联在途采购或移除后其余单元不够覆盖已领时，整批不移除并逐行说明原因。' },
    fields: [reason],
    prepare: data => ({ project: projectId, ids: lines.map(line => line.bom_line), reason: data.reason }),
  }
}
