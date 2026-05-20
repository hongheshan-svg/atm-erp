/**
 * 诊断会话 API
 */
import request from '@/utils/request'

export function getDiagnosticSessionList(params?: Record<string, any>) {
  return request({ url: '/projects/diagnostic-sessions/', method: 'get', params })
}

export function getDiagnosticSession(id: number) {
  return request({ url: `/projects/diagnostic-sessions/${id}/`, method: 'get' })
}

export function createDiagnosticSession(data: any) {
  return request({ url: '/projects/diagnostic-sessions/', method: 'post', data })
}
