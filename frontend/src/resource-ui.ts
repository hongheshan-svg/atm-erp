// Only expose filters implemented by the corresponding list API.
export const resourceFilters: Record<string, { key: string; label: string; options: Record<string, string> }> = {
  users: { key: 'role', label: '用户角色', options: { admin: '管理员', manager: '项目经理', sales_manager: '销售经理', purchaser: '采购员', warehouse: '仓管', finance: '财务', member: '成员' } },
  stocks: { key: 'item__part_type', label: '物料类别', options: { standard: '标准件', custom: '非标件' } },
  sales: { key: 'status', label: '销售状态', options: { draft: '草稿', quoted: '已报价', signed: '已签约', cancelled: '已取消' } },
  projects: { key: 'status', label: '项目状态', options: { active: '执行中', delivering: '交付中', warranty: '已验收', closed: '已结项', cancelled: '已取消' } },
  purchases: { key: 'status', label: '采购状态', options: { draft: '草稿', submitted: '待批准', approved: '待收货', partial: '部分收货', received: '已收货', cancelled: '已取消' } },
  tasks: { key: 'status', label: '任务状态', options: { open: '待完成', done: '已完成' } },
  items: { key: 'part_type', label: '物料类别', options: { standard: '标准件', custom: '非标件' } },
  partners: { key: 'kind', label: '往来类型', options: { customer: '客户', supplier: '供应商', both: '客户及供应商' } },
  entries: { key: 'kind', label: '款项类型', options: { receivable: '应收', payable: '应付', expense: '费用' } },
  moves: { key: 'kind', label: '流水类型', options: { opening: '期初', receipt: '采购收货', issue: '项目领料', return: '项目退料', purchase_return: '采购退货', count: '盘点' } },
}
export const searchableResources = ['sales', 'projects', 'purchases', 'items', 'partners', 'documents', 'reconciliations', 'bank-records', 'users', 'stocks', 'entries']
export const sidePanelResources = ['sales', 'purchases', 'items', 'partners', 'users', 'company', 'codes', 'audit', 'stocks', 'tasks', 'entries', 'reconciliations', 'bank-records', 'payments']
