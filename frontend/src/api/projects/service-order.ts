/**
 * 服务工单 API
 */
import request from '@/utils/request'

export function getServiceOrderList(params?: Record<string, any>) {
  return request({ url: '/projects/service-orders/', method: 'get', params })
}

export function getServiceOrder(id: number) {
  return request({ url: `/projects/service-orders/${id}/`, method: 'get' })
}

export function createServiceOrder(data: any) {
  return request({ url: '/projects/service-orders/', method: 'post', data })
}

export function getServiceOrderDashboard() {
  return request({ url: '/projects/service-orders/dashboard/', method: 'get' })
}

export function completeServiceOrder(id: number) {
  return request({ url: `/projects/service-orders/${id}/complete/`, method: 'post' })
}

export function dispatchServiceOrder(id: number, data: any) {
  return request({ url: `/projects/service-orders/${id}/dispatch/`, method: 'post', data })
}
