/**
 * 客户管理 API
 */
import request from '@/utils/request'

export function getCustomerList(params?: Record<string, any>) {
  return request({
    url: '/masterdata/customers/',
    method: 'get',
    params
  })
}

export function getCustomer(id: number) {
  return request({
    url: `/masterdata/customers/${id}/`,
    method: 'get'
  })
}

export function createCustomer(data: any) {
  return request({
    url: '/masterdata/customers/',
    method: 'post',
    data
  })
}

export function updateCustomer(id: number, data: any) {
  return request({
    url: `/masterdata/customers/${id}/`,
    method: 'put',
    data
  })
}

export function deleteCustomer(id: number) {
  return request({
    url: `/masterdata/customers/${id}/`,
    method: 'delete'
  })
}
