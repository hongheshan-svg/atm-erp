/**
 * 工时费率 API
 */
import request from '@/utils/request'

export function getLaborRateList(params?: Record<string, any>) {
  return request({ url: '/projects/labor-rates/', method: 'get', params })
}

export function createLaborRate(data: any) {
  return request({ url: '/projects/labor-rates/', method: 'post', data })
}

export function updateLaborRate(id: number, data: any) {
  return request({ url: `/projects/labor-rates/${id}/`, method: 'put', data })
}
