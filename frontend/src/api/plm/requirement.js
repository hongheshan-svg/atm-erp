/**
 * 需求管理 API
 */
import request from '@/utils/request'

export function getRequirementList(params) {
  return request({ url: '/projects/requirements/', method: 'get', params })
}

export function getRequirement(id) {
  return request({ url: `/projects/requirements/${id}/`, method: 'get' })
}

export function createRequirement(data) {
  return request({ url: '/projects/requirements/', method: 'post', data })
}

export function patchRequirement(id, data) {
  return request({ url: `/projects/requirements/${id}/`, method: 'patch', data })
}

export function getRequirementStatistics() {
  return request({ url: '/projects/requirements/statistics/', method: 'get' })
}

export function submitRequirement(id) {
  return request({ url: `/projects/requirements/${id}/submit/`, method: 'post' })
}

export function approveRequirement(id) {
  return request({ url: `/projects/requirements/${id}/approve/`, method: 'post' })
}

export function decomposeRequirement(id, data) {
  return request({ url: `/projects/requirements/${id}/decompose/`, method: 'post', data })
}
