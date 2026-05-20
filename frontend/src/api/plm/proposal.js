/**
 * 项目建议书 API
 */
import request from '@/utils/request'

export function getProposalList(params) {
  return request({ url: '/projects/proposals/', method: 'get', params })
}

export function getProposal(id) {
  return request({ url: `/projects/proposals/${id}/`, method: 'get' })
}

export function createProposal(data) {
  return request({ url: '/projects/proposals/', method: 'post', data })
}

export function patchProposal(id, data) {
  return request({ url: `/projects/proposals/${id}/`, method: 'patch', data })
}

export function getProposalStatistics() {
  return request({ url: '/projects/proposals/statistics/', method: 'get' })
}

export function submitProposal(id) {
  return request({ url: `/projects/proposals/${id}/submit/`, method: 'post' })
}

export function startProposalReview(id, data) {
  return request({ url: `/projects/proposals/${id}/start_review/`, method: 'post', data })
}

export function approveProposal(id) {
  return request({ url: `/projects/proposals/${id}/approve/`, method: 'post' })
}

export function createProposalVersion(id) {
  return request({ url: `/projects/proposals/${id}/create_new_version/`, method: 'post' })
}
