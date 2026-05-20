/**
 * Bug管理 API
 */
import request from '@/utils/request'

export function getBugList(params) {
  return request({ url: '/projects/bugs/', method: 'get', params })
}

export function getBug(id) {
  return request({ url: `/projects/bugs/${id}/`, method: 'get' })
}

export function createBug(data) {
  return request({ url: '/projects/bugs/', method: 'post', data })
}

export function updateBug(id, data) {
  return request({ url: `/projects/bugs/${id}/`, method: 'put', data })
}

export function getBugStatistics(params) {
  return request({ url: '/projects/bugs/statistics/', method: 'get', params })
}

export function assignBug(id, data) {
  return request({ url: `/projects/bugs/${id}/assign/`, method: 'post', data })
}

export function changeBugStatus(id, data) {
  return request({ url: `/projects/bugs/${id}/change_status/`, method: 'post', data })
}

export function addBugComment(id, data) {
  return request({ url: `/projects/bugs/${id}/comments/`, method: 'post', data })
}
