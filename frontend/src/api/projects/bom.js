/**
 * 项目BOM管理 API
 */
import request from '@/utils/request'

export function getBOMList(params) {
  return request({ url: '/projects/bom/', method: 'get', params })
}

export function getBOM(id) {
  return request({ url: `/projects/bom/${id}/`, method: 'get' })
}

export function createBOM(data) {
  return request({ url: '/projects/bom/', method: 'post', data })
}

export function updateBOM(id, data) {
  return request({ url: `/projects/bom/${id}/`, method: 'put', data })
}

export function deleteBOM(id) {
  return request({ url: `/projects/bom/${id}/`, method: 'delete' })
}

export function bulkDeleteBOM(ids) {
  return request({ url: '/projects/bom/bulk_delete/', method: 'post', data: { ids } })
}

export function getBOMPendingQuoteCount(params) {
  return request({ url: '/projects/bom/pending_quote_count/', method: 'get', params })
}

export function exportBOMExcel(params) {
  return request({ url: '/projects/bom/export_excel/', method: 'get', params, responseType: 'blob' })
}

export function exportBOMForQuote(data) {
  return request({ url: '/projects/bom/export_for_quote/', method: 'post', data, responseType: 'blob' })
}

export function exportBOMTemplate(params) {
  return request({ url: '/projects/bom/export_template/', method: 'get', params, responseType: 'blob' })
}

export function exportQuoteBOM(params) {
  return request({ url: '/projects/bom/export_quote_bom/', method: 'get', params, responseType: 'blob' })
}

export function importQuoteBOM(data, config) {
  return request({ url: '/projects/bom/import_quote_bom/', method: 'post', data, ...config })
}

export function importBOMExcel(data, config) {
  return request({ url: '/projects/bom/import_excel/', method: 'post', data, ...config })
}

export function copyBOMFromProject(data) {
  return request({ url: '/projects/bom/copy_from_project/', method: 'post', data })
}

export function getBOMMaterialCheck(params) {
  return request({ url: '/projects/bom/material_check/', method: 'get', params })
}

export function getBOMPurchasableItems(params) {
  return request({ url: '/projects/bom/purchasable_items/', method: 'get', params })
}

export function generateBOMPurchaseRequest(data) {
  return request({ url: '/projects/bom/generate_purchase_request/', method: 'post', data })
}
