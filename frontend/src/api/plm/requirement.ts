/**
 * 需求管理 API
 */
import request from '@/utils/request'

export function getRequirementList(params?: Record<string, any>) {
  return request({ url: '/projects/requirements/', method: 'get', params })
}

export function getRequirement(id: number) {
  return request({ url: `/projects/requirements/${id}/`, method: 'get' })
}

export function createRequirement(data: any) {
  return request({ url: '/projects/requirements/', method: 'post', data })
}

export function patchRequirement(id: number, data: any) {
  return request({ url: `/projects/requirements/${id}/`, method: 'patch', data })
}

export function getRequirementStatistics() {
  return request({ url: '/projects/requirements/statistics/', method: 'get' })
}

export function submitRequirement(id: number) {
  return request({ url: `/projects/requirements/${id}/submit/`, method: 'post' })
}

export function approveRequirement(id: number) {
  return request({ url: `/projects/requirements/${id}/approve/`, method: 'post' })
}

export function decomposeRequirement(id: number, data: any) {
  return request({ url: `/projects/requirements/${id}/decompose/`, method: 'post', data })
}
