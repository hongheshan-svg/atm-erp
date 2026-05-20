/**
 * 项目预警 API
 */
import request from '@/utils/request'

export function getAlertList(params) {
  return request({ url: '/projects/alerts/', method: 'get', params })
}

export function getAlert(id) {
  return request({ url: `/projects/alerts/${id}/`, method: 'get' })
}

export function getAlertSummary() {
  return request({ url: '/projects/alerts/summary/', method: 'get' })
}

export function checkAllAlerts() {
  return request({ url: '/projects/alerts/check_all/', method: 'post' })
}

export function acknowledgeAlert(id) {
  return request({ url: `/projects/alerts/${id}/acknowledge/`, method: 'post' })
}

export function resolveAlert(id, data) {
  return request({ url: `/projects/alerts/${id}/resolve/`, method: 'post', data })
}

export function ignoreAlert(id) {
  return request({ url: `/projects/alerts/${id}/ignore/`, method: 'post' })
}
