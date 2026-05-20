/**
 * 设备监控/连接/报警/PM API
 */
import request from '@/utils/request'

// ========== 设备报警 ==========
export function getEquipmentAlarmList(params?: Record<string, any>) {
  return request({ url: '/projects/equipment-alarms/', method: 'get', params })
}

export function acknowledgeEquipmentAlarm(id: number) {
  return request({ url: `/projects/equipment-alarms/${id}/acknowledge/`, method: 'post' })
}

// ========== 设备档案 ==========
export function getEquipmentArchiveList(params?: Record<string, any>) {
  return request({ url: '/projects/equipment-archives/', method: 'get', params })
}

export function getEquipmentArchive(id: number) {
  return request({ url: `/projects/equipment-archives/${id}/`, method: 'get' })
}

export function createEquipmentArchive(data: any) {
  return request({ url: '/projects/equipment-archives/', method: 'post', data })
}

export function updateEquipmentArchive(id: number, data: any) {
  return request({ url: `/projects/equipment-archives/${id}/`, method: 'put', data })
}

export function getEquipmentArchiveStatistics() {
  return request({ url: '/projects/equipment-archives/statistics/', method: 'get' })
}

export function getEquipmentArchiveNameplate(id: number) {
  return request({ url: `/projects/equipment-archives/${id}/nameplate/`, method: 'get' })
}

export function getEquipmentArchiveMaintenanceRecords(id: number) {
  return request({ url: `/projects/equipment-archives/${id}/maintenance-records/`, method: 'get' })
}

// ========== 监控看板 ==========
export function getMonitoringDashboard() {
  return request({ url: '/projects/monitoring/dashboard/', method: 'get' })
}

// ========== 设备连接 ==========
export function getEquipmentConnectionList(params?: Record<string, any>) {
  return request({ url: '/projects/equipment-connections/', method: 'get', params })
}

export function patchEquipmentConnection(id: number, data: any) {
  return request({ url: `/projects/equipment-connections/${id}/`, method: 'patch', data })
}

export function testEquipmentConnection(id: number) {
  return request({ url: `/projects/equipment-connections/${id}/test_connection/`, method: 'post' })
}

// ========== PM结果 ==========
export function takePMAction(id: number, data: any) {
  return request({ url: `/projects/pm-results/${id}/take_action/`, method: 'post', data })
}

// ========== 设备列表(ServiceOrder用) ==========
export function getProjectEquipmentList(params?: Record<string, any>) {
  return request({ url: '/projects/equipment/', method: 'get', params })
}
