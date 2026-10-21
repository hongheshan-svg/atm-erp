import { canImportResource, engineer, manager } from '../session'
import type { Row } from '../types'

export const importTitles: Record<string, string> = {
  items: '物料', partners: '往来单位', sales: '销售', projects: '项目', tasks: '项目任务',
  purchases: '采购', stocks: '期初库存', moves: '项目领料', entries: '费用', payments: '收付款',
  time: '工时', deliveries: '发货', bom: 'BOM', 'bank-records': '银行流水',
}

export function scopedImportProject(params?: Row, projectId?: number) {
  const value = Number(projectId ?? params?.project ?? params?.task__project ?? params?.entry__project)
  return Number.isSafeInteger(value) && value > 0 ? value : undefined
}

const exportTitles: Record<string, string> = {
  ...importTitles, stocks: '现有库存', moves: '库存流水', entries: '应收应付与费用', payments: '收付款流水',
  time: '工时记录', deliveries: '交付批次', reconciliations: '业务对账', documents: '附件资料', reports: '经营报表',
  'bank-claims': '银行认领', 'bank-matches': '银行匹配', 'bank-offsets': '银行冲抵',
}

export function exportFilename(resource: string, format: string, now = new Date()) {
  const date = [now.getFullYear(), String(now.getMonth() + 1).padStart(2, '0'), String(now.getDate()).padStart(2, '0')].join('-')
  return `${exportTitles[resource] || '业务记录'}导出_${date}.${format}`
}

export function importResultDestination(resource: string, result: Row) {
  // Opening inventory returns StockMove IDs, not Stock IDs. Never guess from a bare ID.
  const target = resource === 'stocks' ? 'moves' : resource
  const paths: Record<string, string> = {
    items: '/masterdata', partners: '/masterdata', sales: '/sales', projects: '/projects',
    tasks: '/projects', time: '/projects', purchases: '/purchases', moves: '/inventory',
    entries: '/finance', payments: '/finance', 'bank-records': '/finance',
  }
  const id = Number(result.results?.[0]?.id)
  const hasRecord = result.resource === target && Number.isSafeInteger(id) && id > 0
  if (resource === 'projects' && hasRecord) return { path: `/projects/${id}` }
  // Deliveries only have a project-specific view; require an actual project from the result.
  if (resource === 'deliveries') {
    const project = Number(result.results?.[0]?.project)
    return Number.isSafeInteger(project) && project > 0
      ? { path: `/projects/${project}`, query: { tab: 'deliveries', section: 'deliveries', resource: target, ...(hasRecord ? { focus: id } : {}) } }
      : null
  }
  return paths[target] ? { path: paths[target], query: {
    section: target === 'bank-records' ? 'bank' : target, resource: target, project: 'all',
    ...(hasRecord ? { focus: id } : {}),
  } } : null
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
