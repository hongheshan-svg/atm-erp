/**
 * 技术文档 API
 */
import request from '@/utils/request'

export function getTechDocumentList(params?: Record<string, any>) {
  return request({ url: '/projects/tech-documents/', method: 'get', params })
}

export function getTechDocument(id: number) {
  return request({ url: `/projects/tech-documents/${id}/`, method: 'get' })
}

export function createTechDocument(data: any, config: any) {
  return request({ url: '/projects/tech-documents/', method: 'post', data, ...config })
}

export function getTechDocCategoryTree() {
  return request({ url: '/projects/tech-doc-categories/tree/', method: 'get' })
}

export function logTechDocAccess(id: number, data: any) {
  return request({ url: `/projects/tech-documents/${id}/log_access/`, method: 'post', data })
}

export function submitTechDocReview(id: number, data: any) {
  return request({ url: `/projects/tech-documents/${id}/submit_review/`, method: 'post', data })
}

export function approveTechDocument(id: number) {
  return request({ url: `/projects/tech-documents/${id}/approve/`, method: 'post' })
}

export function releaseTechDocument(id: number) {
  return request({ url: `/projects/tech-documents/${id}/release/`, method: 'post' })
}

export function newTechDocRevision(id: number, data: any) {
  return request({ url: `/projects/tech-documents/${id}/new_revision/`, method: 'post', data })
}

export function getTechDocAccessLog(id: number) {
  return request({ url: `/projects/tech-documents/${id}/access_log/`, method: 'get' })
}

export function distributeTechDocument(id: number, data: any) {
  return request({ url: `/projects/tech-documents/${id}/distribute/`, method: 'post', data })
}
