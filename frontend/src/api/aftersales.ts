/**
 * 售后服务 API
 */
import request from '@/utils/request'

export function getAfterSalesOrderList(params?: Record<string, any>) {
  return request({ url: '/projects/aftersales/', method: 'get', params })
}
export function getAfterSalesOrder(id: number) {
  return request({ url: `/projects/aftersales/${id}/`, method: 'get' })
}
export function createAfterSalesOrder(data: any) {
  return request({ url: '/projects/aftersales/', method: 'post', data })
}
export function updateAfterSalesOrder(id: number, data: any) {
  return request({ url: `/projects/aftersales/${id}/`, method: 'put', data })
}
export function deleteAfterSalesOrder(id: number) {
  return request({ url: `/projects/aftersales/${id}/`, method: 'delete' })
}
export function assignAfterSalesOrder(id: number, data: any) {
  return request({ url: `/projects/aftersales/${id}/assign/`, method: 'post', data })
}
export function startService(id: number) {
  return request({ url: `/projects/aftersales/${id}/start_service/`, method: 'post' })
}
export function onSiteService(id: number, data: any) {
  return request({ url: `/projects/aftersales/${id}/on_site/`, method: 'post', data })
}
export function waitingParts(id: number) {
  return request({ url: `/projects/aftersales/${id}/waiting_parts/`, method: 'post' })
}
export function resolveAfterSalesOrder(id: number, data: any) {
  return request({ url: `/projects/aftersales/${id}/resolve/`, method: 'post', data })
}
export function closeAfterSalesOrder(id: number, data: any) {
  return request({ url: `/projects/aftersales/${id}/close/`, method: 'post', data })
}
export function cancelAfterSalesOrder(id: number) {
  return request({ url: `/projects/aftersales/${id}/cancel/`, method: 'post' })
}
export function updateAfterSalesCost(id: number, data: any) {
  return request({ url: `/projects/aftersales/${id}/update_cost/`, method: 'post', data })
}
export function getServiceRecordList(params?: Record<string, any>) {
  return request({ url: '/projects/service-records/', method: 'get', params })
}
export function createServiceRecord(data: any) {
  return request({ url: '/projects/service-records/', method: 'post', data })
}
export function deleteServiceRecord(id: number) {
  return request({ url: `/projects/service-records/${id}/`, method: 'delete' })
}
export function getAfterSalesStatistics() {
  return request({ url: '/projects/aftersales/statistics/', method: 'get' })
}
export function createSparePart(data: any) {
  return request({ url: '/projects/spare-parts/', method: 'post', data })
}
export function deleteSparePart(id: number) {
  return request({ url: `/projects/spare-parts/${id}/`, method: 'delete' })
}
