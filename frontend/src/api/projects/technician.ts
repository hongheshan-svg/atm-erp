/**
 * 技术人员 API
 */
import request from '@/utils/request'

export function getTechnicianProfileList(params?: Record<string, any>) {
  return request({ url: '/projects/technician-profiles/', method: 'get', params })
}

export function createTechnicianProfile(data: any) {
  return request({ url: '/projects/technician-profiles/', method: 'post', data })
}

export function updateTechnicianProfile(id: number, data: any) {
  return request({ url: `/projects/technician-profiles/${id}/`, method: 'put', data })
}

export function deleteTechnicianProfile(id: number) {
  return request({ url: `/projects/technician-profiles/${id}/`, method: 'delete' })
}

export function scheduleTechnician(id: number, data: any) {
  return request({ url: `/projects/technician-profiles/${id}/schedule/`, method: 'post', data })
}
