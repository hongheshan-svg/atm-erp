/**
 * ECN工程变更 API
 */
import request from '@/utils/request'

export function getECNList(params) {
  return request({ url: '/projects/ecn/', method: 'get', params })
}

export function getECN(id) {
  return request({ url: `/projects/ecn/${id}/`, method: 'get' })
}

export function createECN(data) {
  return request({ url: '/projects/ecn/', method: 'post', data })
}

export function updateECN(id, data) {
  return request({ url: `/projects/ecn/${id}/`, method: 'put', data })
}

export function submitECN(id) {
  return request({ url: `/projects/ecn/${id}/submit/`, method: 'post' })
}

export function startECNImplementation(id) {
  return request({ url: `/projects/ecn/${id}/start_implementation/`, method: 'post' })
}

export function approveECN(id, data) {
  return request({ url: `/projects/ecn/${id}/approve/`, method: 'post', data })
}

export function rejectECN(id, data) {
  return request({ url: `/projects/ecn/${id}/reject/`, method: 'post', data })
}

export function completeECN(id, data) {
  return request({ url: `/projects/ecn/${id}/complete/`, method: 'post', data })
}
