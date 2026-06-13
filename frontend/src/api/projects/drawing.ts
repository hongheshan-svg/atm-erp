/**
 * 图纸管理 API
 */
import request from '@/utils/request'

// ========== 图纸 CRUD ==========
export function getDrawingList(params?: Record<string, any>) {
  return request({ url: '/projects/drawings/', method: 'get', params })
}

export function getDrawing(id: number) {
  return request({ url: `/projects/drawings/${id}/`, method: 'get' })
}

export function createDrawing(data: any) {
  return request({ url: '/projects/drawings/', method: 'post', data })
}

export function updateDrawing(id: number, data: any) {
  return request({ url: `/projects/drawings/${id}/`, method: 'put', data })
}

export function patchDrawing(id: number, data: any) {
  return request({ url: `/projects/drawings/${id}/`, method: 'patch', data })
}

// ========== 图纸工作流 ==========
export function submitDrawingReview(id: number) {
  return request({ url: `/projects/drawings/${id}/submit_review/`, method: 'post' })
}

export function approveDrawing(id: number) {
  return request({ url: `/projects/drawings/${id}/approve/`, method: 'post' })
}

export function rejectDrawing(id: number, data?: Record<string, any>) {
  return request({ url: `/projects/drawings/${id}/reject/`, method: 'post', data })
}

export function releaseDrawing(id: number) {
  return request({ url: `/projects/drawings/${id}/release/`, method: 'post' })
}

export function newDrawingRevision(id: number, data: any) {
  return request({ url: `/projects/drawings/${id}/new_revision/`, method: 'post', data })
}

// ========== 导入导出 ==========
export function exportDrawingExcel(params?: Record<string, any>) {
  return request({ url: '/projects/drawings/export_excel/', method: 'get', params, responseType: 'blob' })
}

export function exportDrawingTemplate(params?: Record<string, any>) {
  return request({ url: '/projects/drawings/export_template/', method: 'get', params, responseType: 'blob' })
}

export function importDrawingExcel(data: any, config: any) {
  return request({ url: '/projects/drawings/import_excel/', method: 'post', data, ...config })
}

// ========== 图纸导入工具 ==========
export function getDrawingImportSupportedFormats() {
  return request({ url: '/projects/drawing-import/supported_formats/', method: 'get' })
}

export function autoLinkDrawings(data: any) {
  return request({ url: '/projects/drawing-import/auto_link/', method: 'post', data })
}

export function manualLinkDrawing(data: any) {
  return request({ url: '/projects/drawing-import/manual_link/', method: 'post', data })
}

export function batchImportDrawings(data: any, config: any) {
  return request({ url: '/projects/drawing-import/batch_import/', method: 'post', data, ...config })
}

// ========== Creo BOM导入 ==========
export function getCreoBOMTree(params?: Record<string, any>) {
  return request({ url: '/projects/creo-bom-imports/bom_tree/', method: 'get', params })
}
