/**
 * 技术人员 API
 */
import request from '@/utils/request'

export function getTechnicianProfileList(params) {
  return request({ url: '/projects/technician-profiles/', method: 'get', params })
}

export function createTechnicianProfile(data) {
  return request({ url: '/projects/technician-profiles/', method: 'post', data })
}

export function updateTechnicianProfile(id, data) {
  return request({ url: `/projects/technician-profiles/${id}/`, method: 'put', data })
}

export function deleteTechnicianProfile(id) {
  return request({ url: `/projects/technician-profiles/${id}/`, method: 'delete' })
}

export function scheduleTechnician(id, data) {
  return request({ url: `/projects/technician-profiles/${id}/schedule/`, method: 'post', data })
}
