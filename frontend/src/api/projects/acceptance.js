/**
 * 验收管理 API
 */
import request from '@/utils/request'

export function getAcceptanceList(params) {
  return request({ url: '/projects/acceptances/', method: 'get', params })
}

export function getAcceptance(id) {
  return request({ url: `/projects/acceptances/${id}/`, method: 'get' })
}

export function createAcceptance(data) {
  return request({ url: '/projects/acceptances/', method: 'post', data })
}

export function updateAcceptance(id, data) {
  return request({ url: `/projects/acceptances/${id}/`, method: 'put', data })
}

export function getAcceptanceStatistics() {
  return request({ url: '/projects/acceptances/statistics/', method: 'get' })
}

export function getAcceptanceReport(id) {
  return request({ url: `/projects/acceptances/${id}/report/`, method: 'get' })
}

export function applyAcceptanceTemplate(id, data) {
  return request({ url: `/projects/acceptances/${id}/apply_template/`, method: 'post', data })
}

export function startAcceptance(id) {
  return request({ url: `/projects/acceptances/${id}/start/`, method: 'post' })
}

export function getActiveAcceptanceTemplates(params) {
  return request({ url: '/projects/acceptance-templates/', method: 'get', params })
}

export function getEquipmentArchiveList(params) {
  return request({ url: '/projects/equipment-archives/', method: 'get', params })
}
