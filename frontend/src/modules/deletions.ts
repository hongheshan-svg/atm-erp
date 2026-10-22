import { can } from '../session'
import type { Row } from '../types'

export const removableResources = new Set([
  'items', 'partners', 'sales', 'projects', 'bom', 'purchases', 'stocks', 'moves',
  'entries', 'payments', 'reconciliations', 'bank-records', 'tasks', 'deliveries', 'time', 'documents', 'users',
])
export const canDeleteRecords = (resource: string) => can(['admin']) && removableResources.has(resource)
export const deletionLabel = (row: Row) => [row.code || row.item_code || row.reference || `#${row.id}`, row.name || row.title || row.original_name || row.display_name || row.item_name || row.task_title || row.entry_title, row.assembly_unit ? `单元：${row.assembly_unit}` : ''].filter(Boolean).join(' · ')
export function deletionNotice(resource: string) {
  if (resource === 'users') return '删除后账号停用，不能登录。姓名和历史业务记录保留；不能删除当前登录账号。'
  if (resource === 'stocks') return '仅可移除数量和金额均为零的库存行。库存流水仍保留；以后重新入库时会自动显示。'
  if (['moves', 'entries', 'payments', 'reconciliations', 'bank-records', 'time', 'deliveries'].includes(resource))
    return '仅移入“已删除记录”，不会撤销业务，也不会改变库存、账款余额、工时或成本。业务错误仍需通过冲销、退料或更正处理。'
  return '未被使用的普通记录会从业务列表移除；已有业务关联时系统会检查并提示处理顺序。历史单据及凭证保留在“已删除记录”，不会抹掉库存或账款。'
}
