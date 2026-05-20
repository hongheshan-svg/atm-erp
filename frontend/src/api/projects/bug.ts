/**
 * Bug管理 API
 */
import request from '@/utils/request'

export function getBugList(params?: Record<string, any>) {
  return request({ url: '/projects/bugs/', method: 'get', params })
}

export function getBug(id: number) {
  return request({ url: `/projects/bugs/${id}/`, method: 'get' })
}

export function createBug(data: any) {
  return request({ url: '/projects/bugs/', method: 'post', data })
}

export function updateBug(id: number, data: any) {
  return request({ url: `/projects/bugs/${id}/`, method: 'put', data })
}

export function getBugStatistics(params?: Record<string, any>) {
  return request({ url: '/projects/bugs/statistics/', method: 'get', params })
}

export function assignBug(id: number, data: any) {
  return request({ url: `/projects/bugs/${id}/assign/`, method: 'post', data })
}

export function changeBugStatus(id: number, data: any) {
  return request({ url: `/projects/bugs/${id}/change_status/`, method: 'post', data })
}

export function addBugComment(id: number, data: any) {
  return request({ url: `/projects/bugs/${id}/comments/`, method: 'post', data })
}
