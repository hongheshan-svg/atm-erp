import { materialDetails, warehouseLines } from './warehouse-lines'
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
import { optionalReason } from './shared'
import { projectLink } from './shared'
import { purchaseLink } from './shared'
import { qty } from './shared'
import { warehouse } from './shared'
import { C } from './shared'
import { project } from './shared'
import { quantityText } from '../utils/quantity'
import { dateTimeText } from '../utils/datetime'
import { item } from './shared'
import { endpoint } from './shared'
const positiveQuantity: Field = { ...qty, numeric: { scale: 3, min: 0.001 } }
// 领料单打印页；领料成功提示、领料单列表和库存流水都链到这里。
export const slipRoute = (id: number | string) => ({ path: `/inventory/issue-slips/${id}` })
export const columns: Record<string, Column[]> = {
  stocks: [
    C('item_code', '物料编码'),
    C('item_name', '物料名称'),
    C('specification', '规格'), C('brand', '品牌'),
    { key: 'part_type', label: '类别', format: row => (({ standard: '标准件', custom: '非标件' } as Record<string, string>)[row.part_type] || '未分类') },
    C('location', '库位'),
    { key: 'quantity', label: '库存数量', format: row => (row.quantity == null ? display(row.quantity) : `${quantityText(row.quantity)}${row.unit ? ` ${row.unit}` : ''}`) },
  ],
  // 领料领给了哪个项目、收货来自哪张采购单、谁在什么时候操作，都直接在流水里看到并可跳转。
  moves: [
    { key: 'item_name', label: '物料', format: row => [row.item_code, row.item_name].filter(Boolean).join(' · ') || '—' },
    C('kind', '类型'),
    { key: 'quantity', label: '数量', format: row => (row.quantity == null ? '—' : `${quantityText(row.quantity)}${row.unit ? ` ${row.unit}` : ''}`) },
    { key: 'project_name', label: '项目', format: row => [row.project_code, row.project_name].filter(Boolean).join(' · ') || '—', link: projectLink },
    // 收货、采购退货链到采购单，领料链到所属领料单；列数不变，1366 宽不出横向滚动。
    { key: 'purchase_code', label: '关联单据', format: row => row.purchase_code || row.slip_code || '—', link: row => purchaseLink(row) || (row.slip ? slipRoute(row.slip) : undefined) },
    C('location', '库位'),
    C('reason', '说明'),
    { key: 'created_at', label: '时间', format: row => dateTimeText(row.created_at) },
    C('created_by_name', '操作人'),
    C('remark', '备注'),
  ],
  'issue-slips': [
    { key: 'code', label: '领料单号', link: row => slipRoute(row.id) },
    { key: 'project_name', label: '项目', format: row => [row.project_code, row.project_name].filter(Boolean).join(' · ') || '—', link: projectLink },
    { key: 'items_summary', label: '物料', format: row => row.items_summary ? `${row.items_summary}（${row.line_count} 行）` : '—' },
    { key: 'task_title', label: '售后/任务', format: row => row.task_title || '—' },
    C('reason', '领料说明'),
    C('created_by_name', '经办人'),
    { key: 'created_at', label: '领料时间', format: row => dateTimeText(row.created_at) },
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
      positiveQuantity,
      t('unit_cost', '单位成本（元）'),
      optionalReason(undefined, '选填；不填按「期初库存」记录'),
    ]
  }
  return {
    title: String(createLabel(resource)),
    path,
    fields,
    initial: projectId ? { project: projectId } : {},
  }
}
const sharedArrival: Field = { key: 'confirm_shared', label: '确认占用其他项目到货', type: 'boolean', initial: false, optional: true }
const sharedHint = '库存不按项目预留。系统提示本次领料会用到其他项目已到货、未领用的物料时，确认挪用再勾选，并通知相关项目补采。'
// 领料关联的售后任务：只列所选项目未完成的售后任务；别的项目的任务选了也会被服务端拒绝。
function serviceTask(tasks: Row[]): Field {
  return {
    ...select('task', '售后任务（生产领料留空）', [], true),
    optionsFor: (data) => tasks.filter((task) => String(task.project) === String(data.project)).map((task) => ({ value: task.id, label: task.title })),
  }
}
// 库存页勾选批量领料：一页最多勾 100 行，一张领料单打印出来仍便于核对签字。
export const issueSelectionLimit = 100
export const issueSelectable = (row: Row) => Number(row.quantity) > 0
// 勾选的库存行一次领出、生成一张领料单（与按 BOM 领料同一接口，可选售后任务）。
// 本次数量默认留空、逐行按实物填写：共享库存不按项目预留，预填可用量容易把整库位误领出；需要全领时点「全部按可用填入」。
export async function stockIssueCommand(selected: Row[]): Promise<Command> {
  const path = '/business/stocks/bom-issue/'
  const ids = [...new Set(selected.map(row => row.id))]
  const base = { title: '批量领料', path }
  if (!ids.length) return { ...base, fields: [], blocked: '请先在现有库存里勾选要领的物料。' }
  // 打开时按勾选重读一次当前库存，翻页或刷新期间被领走的行不再按旧数量显示。
  const [fresh, tasks] = await Promise.all([
    read('/business/stocks/', { id__in: ids.join(','), page_size: ids.length }),
    all('/business/tasks/', { kind: 'service', status: 'open' }),
  ])
  const current = new Map<number, Row>((fresh.results || []).map((stock: Row) => [stock.id, stock]))
  const usable = ids.map(id => current.get(id)).filter((stock): stock is Row => !!stock && issueSelectable(stock))
  const dropped = ids.length - usable.length
  const lines: Row[] = usable.map(stock => ({ ...materialDetails(stock), stock: stock.id, remaining: stock.quantity, quantity: '', remark: '' }))
  const droppedText = dropped ? `另有 ${dropped} 行已无可用库存，已从本次领料中去掉。` : ''
  if (!lines.length) return { ...base, fields: [], blocked: `勾选的物料当前都没有可用库存。${droppedText}请刷新列表后重新勾选。` }
  return {
    ...base,
    submitLabel: `确认领料出库（${lines.length} 行）`,
    fields: [
      project(),
      serviceTask(tasks),
      warehouseLines('issue', lines, { location: true }),
      optionalReason('领料说明', '选填，如使用工位；不填按「项目领料」记录，选售后任务按「售后领料」'),
      { ...sharedArrival, hint: sharedHint },
    ],
    initial: { lines },
    notice: { type: droppedText ? 'warning' : 'info', text: `${droppedText}已勾选 ${lines.length} 行，逐行填写本次领料数量后一次出库，生成一张领料单；任一行不通过则整单不出库。已验收项目须选该项目的售后任务。` },
    prepare: ({ lines: rows, ...rest }) => {
      const picked: Row[] = rows || []
      picked.forEach((row, index) => {
        const line = lines.find(item => item.stock === row.stock)
        if (line && Number(row.quantity) > Number(line.remaining)) throw new Error(`第 ${index + 1} 行 ${line.item_name}（${line.location}）：本次领料 ${row.quantity} 超过本库位可用 ${line.remaining}。`)
      })
      return { ...rest, lines: picked.map(row => ({ stock: row.stock, quantity: row.quantity, ...(row.remark ? { remark: row.remark } : {}) })) }
    },
  }
}
// 按项目 BOM 一次领多行（库存页 /inventory?project=<id>&issue=bom 直接打开）：服务端按 BOM 未领数量和库位预填，
// 一次事务出库，任一行不通过整单不出库。
export async function bomIssueCommand(projectId?: number): Promise<Command> {
  const path = '/business/stocks/bom-issue/'
  const base = { title: '按 BOM 领料', path, submitLabel: '确认按 BOM 领料出库' }
  if (!projectId) return { ...base, fields: [], blocked: '请先在上方「项目筛选」选择项目，系统会列出该项目 BOM 未领完且有库存的物料。' }
  const data = await read(path, { project: projectId })
  const lines = (data.lines || []).map((line: Row) => ({
    ...materialDetails(line), project_code: data.project_code, project_name: data.project_name,
    assembly_unit: line.assembly_units, remaining: line.available, remark: '',
  }))
  const missing = data.missing_items ? `其中 ${data.missing_items} 种当前无库存，需采购或等待到货。` : ''
  if (!lines.length) return {
    ...base, fields: [], subject: data.project_code,
    blocked: data.pending_items ? `本项目还有 ${data.pending_items} 种 BOM 物料未领完，但都没有可用库存。${missing}` : '本项目 BOM 物料已全部领完，无需再领。',
  }
  return {
    ...base, subject: [data.project_code, data.project_name].filter(Boolean).join(' · '),
    fields: [
      { key: 'project', label: '项目', hidden: true },
      warehouseLines('issue', lines, { batch: true }),
      optionalReason(undefined, '选填；不填按「项目领料」记录'),
      { ...sharedArrival, hint: sharedHint },
    ],
    initial: { project: projectId, lines },
    notice: { type: 'info', text: `本项目 BOM 还有 ${data.pending_items} 种物料未领完。${missing}已按 BOM 未领数量和库位预填本次领料，可改小或清零；整单一次出库，任一行不通过则全部不出库。` },
    prepare: ({ lines: rows, ...rest }) => {
      const selected = (rows || []).filter((row: Row) => Number(row.quantity || 0) > 0)
      if (!selected.length) throw new Error('请至少填写一行本次领料数量。')
      return { ...rest, project: projectId, lines: selected.map((row: Row) => ({ stock: row.stock, quantity: row.quantity, ...(row.remark ? { remark: row.remark } : {}) })) }
    },
  }
}
export function actionNames(resource: string, r: Row): string[] {
  const a: string[] = []
  if (resource === 'stocks' && warehouse()) a.push('领料', '盘点')
  if (resource === 'issue-slips') a.push('查看 / 打印')
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
    const stock = await read(`/business/stocks/${r.id}/`)
    const lines = [{ ...materialDetails(stock), stock: stock.id, remaining: stock.quantity, quantity: '', remark: '' }]
    initial = { stock: stock.id, lines }
    const tasks = await all('/business/tasks/', { kind: 'service', status: 'open' })
    fields = [
      project(),
      serviceTask(tasks),
      warehouseLines('issue', lines),
      optionalReason(undefined, '选填，如使用工位；不填按「项目领料」记录'),
      { ...sharedArrival, hint: sharedHint },
    ]
    prepare = ({ lines, ...data }) => ({ ...data, stock: r.id, quantity: lines[0].quantity, ...(lines[0].remark ? { remark: lines[0].remark } : {}) })
  }
  if (name === '盘点') {
    fields = [
      { ...qty, label: '实盘数量', ...(Number(r.quantity) === 0 ? { hint: '当前库存为零。若有盘盈，请联系管理员在库存页面盘点并填写单位成本；仓管不能提交零库存盘盈。' } : {}) },
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
  if (name === '退料') fields = [positiveQuantity, reason]
  if (name === '采购退货') fields = [positiveQuantity, reason, { ...sharedArrival, hint: '库存不按项目预留。系统提示本次退货会用到其他项目已到货、未领用的物料时，确认挪用再勾选，并通知相关项目补采。' }]
  return { title: name, path, fields, initial, method, readonly, prepare }
}
