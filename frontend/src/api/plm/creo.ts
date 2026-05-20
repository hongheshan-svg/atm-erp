/**
 * Creo BOM导入 API
 */
import request from '@/utils/request'

export function getCreoBOMImportList(params?: Record<string, any>) {
  return request({ url: '/projects/creo-bom-imports/', method: 'get', params })
}

export function getCreoBOMImport(id: number) {
  return request({ url: `/projects/creo-bom-imports/${id}/`, method: 'get' })
}

export function uploadCreoBOM(data: any, config: any) {
  return request({ url: '/projects/creo-bom-imports/upload/', method: 'post', data, ...config })
}

export function createCreoBOMItems(id: number, data: any) {
  return request({ url: `/projects/creo-bom-imports/${id}/create_items/`, method: 'post', data })
}

export function importCreoBOM(id: number, data: any) {
  return request({ url: `/projects/creo-bom-imports/${id}/import_bom/`, method: 'post', data })
}

export function importCreoBOMHierarchy(id: number, data: any) {
  return request({ url: `/projects/creo-bom-imports/${id}/import_hierarchy/`, method: 'post', data })
}

export function manualMatchCreoBOM(id: number, data: any) {
  return request({ url: `/projects/creo-bom-imports/${id}/manual_match/`, method: 'post', data })
}
