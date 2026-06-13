/**
 * 项目建议书 API
 */
import request from '@/utils/request'

export function getProposalList(params?: Record<string, any>) {
  return request({ url: '/projects/proposals/', method: 'get', params })
}

export function getProposal(id: number) {
  return request({ url: `/projects/proposals/${id}/`, method: 'get' })
}

export function createProposal(data: any) {
  return request({ url: '/projects/proposals/', method: 'post', data })
}

export function patchProposal(id: number, data: any) {
  return request({ url: `/projects/proposals/${id}/`, method: 'patch', data })
}

export function getProposalStatistics() {
  return request({ url: '/projects/proposals/statistics/', method: 'get' })
}

export function submitProposal(id: number) {
  return request({ url: `/projects/proposals/${id}/submit/`, method: 'post' })
}

export function startProposalReview(id: number, data: any) {
  return request({ url: `/projects/proposals/${id}/start_review/`, method: 'post', data })
}

export function approveProposal(id: number) {
  return request({ url: `/projects/proposals/${id}/approve/`, method: 'post' })
}

export function requestProposalRevision(id: number, data?: any) {
  return request({ url: `/projects/proposals/${id}/request_revision/`, method: 'post', data })
}

export function rejectProposal(id: number, data?: any) {
  return request({ url: `/projects/proposals/${id}/reject/`, method: 'post', data })
}

export function createProposalVersion(id: number) {
  return request({ url: `/projects/proposals/${id}/create_new_version/`, method: 'post' })
}
