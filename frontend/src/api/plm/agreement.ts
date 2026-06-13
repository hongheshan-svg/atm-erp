/**
 * 技术协议 API
 */
import request from '@/utils/request'

export function getAgreementList(params?: Record<string, any>) {
  return request({ url: '/projects/agreements/', method: 'get', params })
}

export function getAgreement(id: number) {
  return request({ url: `/projects/agreements/${id}/`, method: 'get' })
}

export function createAgreement(data: any) {
  return request({ url: '/projects/agreements/', method: 'post', data })
}

export function updateAgreement(id: number, data: any) {
  return request({ url: `/projects/agreements/${id}/`, method: 'patch', data })
}

export function createAgreementFromTemplate(id: number, data: any) {
  return request({ url: `/projects/agreements/${id}/create_from_template/`, method: 'post', data })
}

export function submitAgreementReview(id: number) {
  return request({ url: `/projects/agreements/${id}/submit_review/`, method: 'post' })
}

export function sendAgreementToCustomer(id: number) {
  return request({ url: `/projects/agreements/${id}/send_to_customer/`, method: 'post' })
}

export function confirmAgreement(id: number, data: any) {
  return request({ url: `/projects/agreements/${id}/customer_confirm/`, method: 'post', data })
}

export function signAgreement(id: number, data: any) {
  return request({ url: `/projects/agreements/${id}/sign/`, method: 'post', data })
}

export function makeAgreementEffective(id: number) {
  return request({ url: `/projects/agreements/${id}/make_effective/`, method: 'post' })
}

export function getActiveAgreementTemplates() {
  return request({ url: '/projects/agreement-templates/active_templates/', method: 'get' })
}
