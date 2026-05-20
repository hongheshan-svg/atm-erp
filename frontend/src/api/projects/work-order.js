/**
 * 工单管理 API
 */
import request from '@/utils/request'

export function getWorkOrderList(params) {
  return request({ url: '/projects/work-orders/', method: 'get', params })
}

export function getWorkOrder(id) {
  return request({ url: `/projects/work-orders/${id}/`, method: 'get' })
}

export function createWorkOrder(data) {
  return request({ url: '/projects/work-orders/', method: 'post', data })
}

export function updateWorkOrder(id, data) {
  return request({ url: `/projects/work-orders/${id}/`, method: 'put', data })
}

export function getWorkOrderStatistics() {
  return request({ url: '/projects/work-orders/statistics/', method: 'get' })
}

export function getWorkOrderTypes() {
  return request({ url: '/projects/work-orders/order_types/', method: 'get' })
}

export function dispatchWorkOrder(id, data) {
  return request({ url: `/projects/work-orders/${id}/dispatch/`, method: 'post', data })
}

export function startWorkOrder(id) {
  return request({ url: `/projects/work-orders/${id}/start/`, method: 'post' })
}

export function completeWorkOrder(id) {
  return request({ url: `/projects/work-orders/${id}/complete/`, method: 'post' })
}
