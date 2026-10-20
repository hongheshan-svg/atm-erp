import { canImportResource, engineer, manager } from '../session'

export const importTitles: Record<string, string> = {
  items: '物料', partners: '往来单位', sales: '销售', projects: '项目', tasks: '项目任务',
  purchases: '采购', stocks: '期初库存', moves: '项目领料', entries: '费用', payments: '收付款',
  time: '工时', deliveries: '发货', bom: 'BOM', 'bank-records': '银行流水',
}

export function importDestination(resource: string, project?: number) {
  if (resource === 'bom') return manager() || engineer() ? { path: '/bom' } : null
  if (!canImportResource(resource)) return null
  if (resource === 'stocks') return { path: '/settings', query: { section: 'initialization' } }
  if (['tasks', 'time', 'deliveries'].includes(resource) && project) {
    return { path: `/projects/${project}`, query: { tab: resource === 'deliveries' ? 'deliveries' : 'tasks', resource } }
  }
  const paths: Record<string, string> = {
    items: '/masterdata', partners: '/masterdata', projects: '/projects', tasks: '/projects', time: '/projects',
    sales: '/sales', purchases: '/purchases', moves: '/inventory',
    entries: '/finance', payments: '/finance',
  }
  return paths[resource] ? { path: paths[resource], query: { resource } } : null
}

export function templateMismatch(error: unknown) {
  const data = (error as { response?: { data?: { template_hint?: { code: string; title: string; entry: string }; file?: string } } })?.response?.data
  return data?.template_hint ? { resource: data.template_hint.code, title: data.template_hint.title, entry: data.template_hint.entry, message: data.file || '请使用对应导入入口。' } : null
}
