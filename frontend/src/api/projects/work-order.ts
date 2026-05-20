/**
 * 工单管理 API
 */
import request from '@/utils/request'

export function getWorkOrderList(params?: Record<string, any>) {
  return request({ url: '/projects/work-orders/', method: 'get', params })
}

export function getWorkOrder(id: number) {
  return request({ url: `/projects/work-orders/${id}/`, method: 'get' })
}

export function createWorkOrder(data: any) {
  return request({ url: '/projects/work-orders/', method: 'post', data })
}

export function updateWorkOrder(id: number, data: any) {
  return request({ url: `/projects/work-orders/${id}/`, method: 'put', data })
}

export function getWorkOrderStatistics() {
  return request({ url: '/projects/work-orders/statistics/', method: 'get' })
}

export function getWorkOrderTypes() {
  return request({ url: '/projects/work-orders/order_types/', method: 'get' })
}

export function dispatchWorkOrder(id: number, data: any) {
  return request({ url: `/projects/work-orders/${id}/dispatch/`, method: 'post', data })
}

export function startWorkOrder(id: number) {
  return request({ url: `/projects/work-orders/${id}/start/`, method: 'post' })
}

export function completeWorkOrder(id: number) {
  return request({ url: `/projects/work-orders/${id}/complete/`, method: 'post' })
}
