/**
 * ECN工程变更 API
 */
import request from '@/utils/request'

export function getECNList(params?: Record<string, any>) {
  return request({ url: '/projects/ecn/', method: 'get', params })
}

export function getECN(id: number) {
  return request({ url: `/projects/ecn/${id}/`, method: 'get' })
}

export function createECN(data: any) {
  return request({ url: '/projects/ecn/', method: 'post', data })
}

export function updateECN(id: number, data: any) {
  return request({ url: `/projects/ecn/${id}/`, method: 'put', data })
}

export function submitECN(id: number) {
  return request({ url: `/projects/ecn/${id}/submit/`, method: 'post' })
}

export function startECNImplementation(id: number) {
  return request({ url: `/projects/ecn/${id}/start_implementation/`, method: 'post' })
}

export function approveECN(id: number, data: any) {
  return request({ url: `/projects/ecn/${id}/approve/`, method: 'post', data })
}

export function rejectECN(id: number, data: any) {
  return request({ url: `/projects/ecn/${id}/reject/`, method: 'post', data })
}

export function completeECN(id: number, data: any) {
  return request({ url: `/projects/ecn/${id}/complete/`, method: 'post', data })
}
