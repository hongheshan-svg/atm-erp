import { roleLabels } from './session'
// Only expose filters implemented by the corresponding list API.
// `params`：个别选项需要带多个查询参数（如「进行中」= 待完成且已开始），没有时就是 { [key]: 选项值 }。
export type ResourceFilter = { key: string; label: string; options: Record<string, string>; params?: Record<string, Record<string, string>> }
export const resourceFilters: Record<string, ResourceFilter> = {
  users: { key: 'role', label: '用户角色', options: roleLabels },
  stocks: { key: 'item__part_type', label: '物料类别', options: { standard: '标准件', custom: '非标件' } },
  sales: { key: 'status', label: '销售状态', options: { draft: '草稿', quoted: '已报价', signed: '已签约', cancelled: '已取消' } },
  projects: { key: 'status', label: '项目状态', options: { active: '执行中', delivering: '交付中', warranty: '已验收', closed: '已结项', cancelled: '已取消' } },
  purchases: { key: 'status', label: '采购状态', options: { draft: '草稿', submitted: '待批准', approved: '待收货', partial: '部分收货', received: '已收货', cancelled: '已取消' } },
  tasks: { key: 'status', label: '任务状态', options: { open: '待完成', started: '进行中', done: '已完成' }, params: { started: { status: 'open', started: 'true' } } },
  items: { key: 'part_type', label: '物料类别', options: { standard: '标准件', custom: '非标件' } },
  partners: { key: 'kind', label: '往来类型', options: { customer: '客户', supplier: '供应商', both: '客户及供应商' } },
  entries: { key: 'kind', label: '款项类型', options: { receivable: '应收', payable: '应付', expense: '费用' } },
  moves: { key: 'kind', label: '流水类型', options: { opening: '期初', receipt: '采购收货', issue: '项目领料', return: '项目退料', purchase_return: '采购退货', count: '盘点' } },
}
export function filterQuery(config: ResourceFilter | undefined, value: string): Record<string, string> {
  if (!config || !value) return {}
  return config.params?.[value] || { [config.key]: value }
}
// 搜索条上的附加筛选/排序（可选）：person = 从用户目录选一人，check = 勾选，sort = 排序下拉；值直接作为查询参数。
export type ExtraFilter = { key: string; label: string; kind: 'person' | 'check' | 'sort'; roles?: string[]; value?: string; options?: Record<string, string> }
export const extraFilters: Record<string, ExtraFilter[]> = {
  projects: [
    { key: 'manager', label: '负责人', kind: 'person', roles: ['manager', 'admin'] },
    { key: 'overdue', label: '只看有逾期', kind: 'check', value: 'true' },
    { key: 'ordering', label: '排序', kind: 'sort', options: { '': '默认排序', due_date: '计划交期最近', '-due_date': '计划交期最远', '-task_overdue': '逾期任务最多' } },
  ],
}
export const searchableResources = ['sales', 'projects', 'tasks', 'purchases', 'items', 'partners', 'documents', 'reconciliations', 'bank-records', 'users', 'stocks', 'entries', 'audit']
export const sidePanelResources = ['sales', 'purchases', 'items', 'partners', 'users', 'company', 'codes', 'audit', 'stocks', 'tasks', 'deliveries', 'entries', 'reconciliations', 'bank-records', 'payments']

// 未完成且早于今天（上海业务日期）的计划日期，与工作台逾期口径一致；只改展示，不改数据。
export function isOverdueCell(resource: string, key: string, row: Record<string, unknown>, day: string) {
  const date = String(row[key] || '')
  if (!date || date >= day) return false
  if (resource === 'purchases' && key === 'next_delivery_date') return !['received', 'cancelled', 'void'].includes(String(row.status))
  if (resource === 'tasks' && key === 'due_date') return row.status === 'open'
  // 项目交期：验收前（执行中、交付中）才算逾期；草稿、已验收、结项、取消不提示。
  if (resource === 'projects' && key === 'due_date') return ['active', 'delivering'].includes(String(row.status))
  return false
}
