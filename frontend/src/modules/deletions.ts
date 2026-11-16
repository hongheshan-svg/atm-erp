import { can } from '../session'
import type { Row } from '../types'

export const removableResources = new Set([
  'items', 'partners', 'sales', 'projects', 'bom', 'purchases', 'stocks', 'moves',
  'entries', 'payments', 'reconciliations', 'bank-records', 'tasks', 'deliveries', 'time', 'documents', 'users',
])
export const deletionLimit = (resource: string) => removableResources.has(resource) ? 1000 : 0
export const canDeleteRecords = (resource: string) => can(['admin']) && removableResources.has(resource)
// 与后端 services/deletions.py 的 RESTORABLE 一致：删除时只是停用并移出列表的记录才能恢复，
// 即账号，以及已有历史单据的物料和往来单位；其他已删除记录仅保留历史。
export const restorableResources = new Set(['users', 'items', 'partners'])
export const canRestoreRecords = (resource: string) => can(['admin']) && restorableResources.has(resource)
// 从未被使用的物料、往来单位是彻底删除（mode 为 soft），没有可恢复的记录。
export const canRestoreRecord = (resource: string, record: Row) => canRestoreRecords(resource) && (resource === 'users' || record?.detail?.mode === 'disable')
export const restoreNotice = (resource: string) => resource === 'users'
  ? '恢复后为停用状态，请在用户管理中确认角色后启用；原用户名、项目成员关系和历史记录保持不变。'
  : '恢复后重新出现在基础资料列表，仍为停用状态，请核对后在编辑中启用；编码和历史单据保持不变。'
// 已删除记录里的“处理方式”：让管理员看清这条记录是彻底删除、只是移出列表，还是停用归档。
export function deletionModeLabel(resource: string, mode: unknown) {
  if (mode === 'disable') return resource === 'users' ? '账号已停用并从列表隐藏' : '已停用并移出列表，编码和历史单据保留'
  if (mode === 'archive') return '已移出列表，原始记录保留'
  if (mode === 'bom') return 'BOM 行已移除'
  if (mode === 'purchase') return '草稿采购单及其明细已删除'
  return mode === 'soft' ? '未被使用，已删除' : ''
}
const cascadeLabels: Record<string, string> = { sales: '销售单', purchases: '采购单', tasks: '任务', time: '工时', entries: '款项', payments: '收付款流水', reconciliations: '对账单' }
export const cascadeText = (cascaded: unknown) => Object.entries((cascaded && typeof cascaded === 'object' ? cascaded : {}) as Record<string, unknown>)
  .filter(([, count]) => Number(count) > 0).map(([resource, count]) => `${cascadeLabels[resource] || resource} ${count}`).join('、')
export type KeptRecord = { label: string; reason: string }
// 删除成功后的附带结果：随项目移出的子单据、随单据删除的附件，以及仍在办而保留在原列表的记录。
export function deletionOutcome(result: Row | null | undefined) {
  const records: Row[] = Array.isArray(result?.records) ? result.records : []
  const cascaded: Record<string, number> = {}, kept: KeptRecord[] = []
  let documents = 0, keptCount = 0
  for (const record of records) {
    for (const [resource, count] of Object.entries((record.cascaded || {}) as Record<string, unknown>)) cascaded[resource] = (cascaded[resource] || 0) + (Number(count) || 0)
    documents += Number(record.documents) || 0
    const rows: Row[] = Array.isArray(record.kept) ? record.kept : []
    kept.push(...rows.map(row => ({ label: String(row.label || ''), reason: String(row.reason || '') })))
    keptCount += Number(record.kept_count) || rows.length
  }
  const moved = cascadeText(cascaded)
  const notes = [moved ? `随项目一并移出列表：${moved}` : '', documents ? `同时删除 ${documents} 份未被引用的附件` : ''].filter(Boolean)
  return { count: Number(result?.count) || records.length, notes, kept, keptCount }
}
export const deletionLabel = (row: Row) => [row.code || row.item_code || row.reference || `#${row.id}`, row.name || row.title || row.original_name || row.display_name || row.item_name || row.task_title || row.entry_title, row.assembly_unit ? `单元：${row.assembly_unit}` : ''].filter(Boolean).join(' · ')
// 与后端 services/deletions.py 的在办判断一致：仍在办理的记录整批拒绝，已结束的才移入历史。
const inProgressNotice: Record<string, string> = {
  entries: '余额未结清（含已取消待退款）或有待确认对账单的账款不能删除，请先收付款结清、退款，或确认/作废对账单。',
  payments: '所属账款尚未结清的收付款流水不能删除，以免之后无法冲销或匹配；请先结清账款。',
  reconciliations: '待确认或仍有剩余核准额度的对账单不能删除，请先确认或作废，已确认的请先作废剩余额度。',
  'bank-records': '仍有未认领、未匹配金额或待复核户名的银行流水不能删除，请先认领、匹配、退回或作废。',
  deliveries: '执行中项目里未验收或仍在质保期内的交付批次不能删除，请先完成验收或等质保期满；项目结项或取消后可整理。',
}
export function deletionNotice(resource: string) {
  if (resource === 'users') return '删除后账号停用并从用户列表隐藏，不能登录；姓名和历史记录保留。删除后不能通过普通编辑恢复，原用户名不能再次使用；误删可由管理员在“已删除记录”中恢复账号（恢复后仍为停用）。不能删除当前登录账号。'
  if (resource === 'stocks') return '仅可移除数量和金额均为零的库存行。库存流水仍保留；以后重新入库时会自动显示。'
  if (['moves', 'entries', 'payments', 'reconciliations', 'bank-records', 'time', 'deliveries'].includes(resource))
    return `${inProgressNotice[resource] ?? ''}已结束的记录仅移入“已删除记录”，不会撤销业务，也不会改变库存、账款余额、工时或成本。业务错误仍需通过冲销、退料或更正处理。`
  if (resource === 'items' || resource === 'partners')
    return `从未被使用的${resource === 'items' ? '物料' : '往来单位'}直接删除；已有历史单据的会停用并移出列表，编码${resource === 'items' ? '、图号' : ''}和历史单据保留，可在“已删除记录”中恢复。${resource === 'items' ? '仍在未结束项目的 BOM、未完成的采购单中，或还有库存的物料' : '仍有未结束的项目、销售单、采购单，或还有未结清款项的往来单位'}不能删除，系统会写明是哪张单据。`
  if (resource === 'projects')
    return '未使用的项目直接删除，未被引用的附件随项目一并删除。已取消或结项的项目移入“已删除记录”，它的销售单、采购单、任务、工时和款项随项目一并移出列表；仍在办的款项保留在原列表，库存流水和银行流水不受影响。执行中的项目请先取消或结项。'
  if (resource === 'sales' || resource === 'purchases')
    return '未被使用的草稿会从列表移除，草稿上未被引用的附件随单据一并删除；已有业务关联时系统会检查并写明是哪张单据。历史单据及凭证保留在“已删除记录”，不会抹掉库存或账款。'
  return '未被使用的普通记录会从业务列表移除；已有业务关联时系统会检查并写明是哪张单据。历史单据及凭证保留在“已删除记录”，不会抹掉库存或账款。'
}
