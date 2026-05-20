/**
 * 图纸管理 API
 */
import request from '@/utils/request'

// ========== 图纸 CRUD ==========
export function getDrawingList(params) {
  return request({ url: '/projects/drawings/', method: 'get', params })
}

export function getDrawing(id) {
  return request({ url: `/projects/drawings/${id}/`, method: 'get' })
}

export function createDrawing(data) {
  return request({ url: '/projects/drawings/', method: 'post', data })
}

export function updateDrawing(id, data) {
  return request({ url: `/projects/drawings/${id}/`, method: 'put', data })
}

export function patchDrawing(id, data) {
  return request({ url: `/projects/drawings/${id}/`, method: 'patch', data })
}

// ========== 图纸工作流 ==========
export function submitDrawingReview(id) {
  return request({ url: `/projects/drawings/${id}/submit_review/`, method: 'post' })
}

export function approveDrawing(id) {
  return request({ url: `/projects/drawings/${id}/approve/`, method: 'post' })
}

export function releaseDrawing(id) {
  return request({ url: `/projects/drawings/${id}/release/`, method: 'post' })
}

export function newDrawingRevision(id, data) {
  return request({ url: `/projects/drawings/${id}/new_revision/`, method: 'post', data })
}

// ========== 导入导出 ==========
export function exportDrawingExcel(params) {
  return request({ url: '/projects/drawings/export_excel/', method: 'get', params, responseType: 'blob' })
}

export function exportDrawingTemplate(params) {
  return request({ url: '/projects/drawings/export_template/', method: 'get', params, responseType: 'blob' })
}

export function importDrawingExcel(data, config) {
  return request({ url: '/projects/drawings/import_excel/', method: 'post', data, ...config })
}

// ========== 图纸导入工具 ==========
export function getDrawingImportSupportedFormats() {
  return request({ url: '/projects/drawing-import/supported_formats/', method: 'get' })
}

export function autoLinkDrawings(data) {
  return request({ url: '/projects/drawing-import/auto_link/', method: 'post', data })
}

export function manualLinkDrawing(data) {
  return request({ url: '/projects/drawing-import/manual_link/', method: 'post', data })
}

export function batchImportDrawings(data, config) {
  return request({ url: '/projects/drawing-import/batch_import/', method: 'post', data, ...config })
}

// ========== Creo BOM导入 ==========
export function getCreoBOMTree(params) {
  return request({ url: '/projects/creo-bom-imports/bom_tree/', method: 'get', params })
}
