// 物料跟踪：跨项目「项目×物料」一行（后端 /business/material-tracking/），这里只放展示口径。
import type { Row } from '../types'
import { quantityText } from '../utils/quantity'
import { partTypeLabel } from '../product-categories'

export const trackingPath = '/business/material-tracking/'
export const trackingStatuses: Record<string, string> = { shortage: '缺料', incoming: '在途', unapproved: '待批采购', ready: '待领料', issued: '已领完' }
// 状态色：缺料醒目，在途、待批提醒，待领料为进行中，已领完为完成。
export const trackingTone: Record<string, string> = { shortage: 'danger', incoming: 'warning', unapproved: 'warning', ready: 'primary', issued: 'success' }

const amount = (value: unknown) => (value == null || value === '' ? '—' : quantityText(value))
// 不在 BOM 的物料（零星采购、改版移除后已买或已领）没有需求数量。
export const needText = (row: Row) => (row.in_bom === false ? '—' : amount(row.quantity))
export const qtyText = (row: Row, key: string) => amount(row[key])
export const partText = (row: Row) => (row.part_type ? partTypeLabel(row.part_type) : '—')
export const drawingText = (row: Row) => [row.drawing_number, row.drawing_revision ? `版本 ${row.drawing_revision}` : ''].filter(Boolean).join(' · ') || '—'
// 分几次采购、单价不同时写「多个」，完整价格放在悬停提示和导出里。
export function unitPriceText(row: Row) {
  const prices = String(row.unit_prices || '').split('、').filter(Boolean)
  if (!prices.length) return '—'
  return prices.length > 1 ? '多个' : prices[0]!
}
export const textOr = (value: unknown) => (value == null || value === '' ? '—' : String(value))
export const purchaseRoute = (ref: Row, row: Row) => ({ path: '/purchases', query: { resource: 'purchases', focus: String(ref.id), project: String(row.project) } })
export const bomRoute = (row: Row) => ({ path: '/bom', query: { project: String(row.project) } })
// 手机卡片的数量行：需求、已采购、已收、已领、缺料一眼看清；有待批采购时另写。
export function trackingSummary(row: Row) {
  const parts = [
    `需求 ${needText(row)}`,
    `已采购 ${qtyText(row, 'ordered')}`,
    ...(Number(row.unapproved) > 0 ? [`待批 ${qtyText(row, 'unapproved')}`] : []),
    `已收 ${qtyText(row, 'received')}`,
    `已领 ${qtyText(row, 'issued')}`,
    ...(row.in_bom === false ? [] : [`缺料 ${qtyText(row, 'shortage')}`]),
  ]
  return parts.join(' · ')
}
// 筛选条件 → 查询参数；空值不传，指定项目时「包括已验收、已结项」没有意义。
export function trackingParams(filters: { search?: string; status?: string; partType?: string; supplier?: string | number; outsideBom?: boolean; allProjects?: boolean }, projectId?: number): Row {
  return {
    ...(filters.search ? { search: filters.search } : {}),
    ...(filters.status ? { status: filters.status } : {}),
    ...(filters.partType ? { part_type: filters.partType } : {}),
    ...(filters.supplier != null && filters.supplier !== '' ? { supplier: filters.supplier } : {}),
    ...(filters.outsideBom ? { outside_bom: 'true' } : {}),
    ...(projectId ? { project: projectId } : filters.allProjects ? { all_projects: 'true' } : {}),
  }
}
