/**
 * 项目BOM管理 API
 */
import request from '@/utils/request'

export function getBOMList(params?: Record<string, any>) {
  return request({ url: '/projects/bom/', method: 'get', params })
}

export function getBOM(id: number) {
  return request({ url: `/projects/bom/${id}/`, method: 'get' })
}

export function createBOM(data: any) {
  return request({ url: '/projects/bom/', method: 'post', data })
}

export function updateBOM(id: number, data: any) {
  return request({ url: `/projects/bom/${id}/`, method: 'put', data })
}

export function deleteBOM(id: number) {
  return request({ url: `/projects/bom/${id}/`, method: 'delete' })
}

export function bulkDeleteBOM(ids: any) {
  return request({ url: '/projects/bom/bulk_delete/', method: 'post', data: { ids } })
}

export function getBOMPendingQuoteCount(params?: Record<string, any>) {
  return request({ url: '/projects/bom/pending_quote_count/', method: 'get', params })
}

export function exportBOMExcel(params?: Record<string, any>) {
  return request({ url: '/projects/bom/export_excel/', method: 'get', params, responseType: 'blob' })
}

export function exportBOMForQuote(data: any) {
  return request({ url: '/projects/bom/export_for_quote/', method: 'post', data, responseType: 'blob' })
}

export function exportBOMTemplate(params?: Record<string, any>) {
  return request({ url: '/projects/bom/export_template/', method: 'get', params, responseType: 'blob' })
}

export function exportQuoteBOM(params?: Record<string, any>) {
  return request({ url: '/projects/bom/export_quote_bom/', method: 'get', params, responseType: 'blob' })
}

export function importQuoteBOM(data: any, config: any) {
  return request({ url: '/projects/bom/import_quote_bom/', method: 'post', data, ...config })
}

export function importBOMExcel(data: any, config: any) {
  return request({ url: '/projects/bom/import_excel/', method: 'post', data, ...config })
}

export function copyBOMFromProject(data: any) {
  return request({ url: '/projects/bom/copy_from_project/', method: 'post', data })
}

export function getBOMMaterialCheck(params?: Record<string, any>) {
  return request({ url: '/projects/bom/material_check/', method: 'get', params })
}

export function getBOMPurchasableItems(params?: Record<string, any>) {
  return request({ url: '/projects/bom/purchasable_items/', method: 'get', params })
}

export function generateBOMPurchaseRequest(data: any) {
  return request({ url: '/projects/bom/generate_purchase_request/', method: 'post', data })
}
