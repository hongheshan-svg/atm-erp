/**
 * 诊断会话 API
 */
import request from '@/utils/request'

export function getDiagnosticSessionList(params) {
  return request({ url: '/projects/diagnostic-sessions/', method: 'get', params })
}

export function getDiagnosticSession(id) {
  return request({ url: `/projects/diagnostic-sessions/${id}/`, method: 'get' })
}

export function createDiagnosticSession(data) {
  return request({ url: '/projects/diagnostic-sessions/', method: 'post', data })
}
