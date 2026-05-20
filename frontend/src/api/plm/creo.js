/**
 * Creo BOM导入 API
 */
import request from '@/utils/request'

export function getCreoBOMImportList(params) {
  return request({ url: '/projects/creo-bom-imports/', method: 'get', params })
}

export function getCreoBOMImport(id) {
  return request({ url: `/projects/creo-bom-imports/${id}/`, method: 'get' })
}

export function uploadCreoBOM(data, config) {
  return request({ url: '/projects/creo-bom-imports/upload/', method: 'post', data, ...config })
}

export function createCreoBOMItems(id, data) {
  return request({ url: `/projects/creo-bom-imports/${id}/create_items/`, method: 'post', data })
}

export function importCreoBOM(id, data) {
  return request({ url: `/projects/creo-bom-imports/${id}/import_bom/`, method: 'post', data })
}

export function importCreoBOMHierarchy(id, data) {
  return request({ url: `/projects/creo-bom-imports/${id}/import_hierarchy/`, method: 'post', data })
}

export function manualMatchCreoBOM(id, data) {
  return request({ url: `/projects/creo-bom-imports/${id}/manual_match/`, method: 'post', data })
}
