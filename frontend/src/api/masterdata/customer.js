/**
 * 客户管理 API
 */
import request from '@/utils/request'

export function getCustomerList(params) {
  return request({
    url: '/api/masterdata/customers/',
    method: 'get',
    params
  })
}

export function getCustomer(id) {
  return request({
    url: `/api/masterdata/customers/${id}/`,
    method: 'get'
  })
}

export function createCustomer(data) {
  return request({
    url: '/api/masterdata/customers/',
    method: 'post',
    data
  })
}

export function updateCustomer(id, data) {
  return request({
    url: `/api/masterdata/customers/${id}/`,
    method: 'put',
    data
  })
}

export function deleteCustomer(id) {
  return request({
    url: `/api/masterdata/customers/${id}/`,
    method: 'delete'
  })
}
