import { can } from '../session'
import type { Row } from '../types'

export const removableResources = new Set([
  'items', 'partners', 'sales', 'projects', 'bom', 'purchases', 'stocks', 'moves',
  'entries', 'payments', 'reconciliations', 'bank-records', 'tasks', 'deliveries', 'time', 'documents', 'users',
])
export const canDeleteRecords = (resource: string) => can(['admin']) && removableResources.has(resource)
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
  if (resource === 'users') return '删除后账号停用并从用户列表隐藏，不能登录；姓名和历史记录保留。删除后不能通过普通编辑恢复，原用户名不能再次使用；不能删除当前登录账号。'
  if (resource === 'stocks') return '仅可移除数量和金额均为零的库存行。库存流水仍保留；以后重新入库时会自动显示。'
  if (['moves', 'entries', 'payments', 'reconciliations', 'bank-records', 'time', 'deliveries'].includes(resource))
    return `${inProgressNotice[resource] ?? ''}已结束的记录仅移入“已删除记录”，不会撤销业务，也不会改变库存、账款余额、工时或成本。业务错误仍需通过冲销、退料或更正处理。`
  return '未被使用的普通记录会从业务列表移除；已有业务关联时系统会检查并提示处理顺序。历史单据及凭证保留在“已删除记录”，不会抹掉库存或账款。'
}
