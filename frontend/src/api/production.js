/**
 * 生产管理扩展 API
 * - 有限产能排程
 * - 设备能力矩阵 & OEE
 * - 看板WIP限制
 */
import request from '@/utils/request'

// ========== 有限产能排程 ==========
export function getFiniteCapacityPlans(params) {
  return request({ url: '/production/finite-capacity-plans/', method: 'get', params })
}

export function getFiniteCapacityPlan(id) {
  return request({ url: `/production/finite-capacity-plans/${id}/`, method: 'get' })
}

export function createFiniteCapacityPlan(data) {
  return request({ url: '/production/finite-capacity-plans/', method: 'post', data })
}

export function updateFiniteCapacityPlan(id, data) {
  return request({ url: `/production/finite-capacity-plans/${id}/`, method: 'put', data })
}

export function deleteFiniteCapacityPlan(id) {
  return request({ url: `/production/finite-capacity-plans/${id}/`, method: 'delete' })
}

export function runFiniteCapacitySchedule(id) {
  return request({ url: `/production/finite-capacity-plans/${id}/run_schedule/`, method: 'post' })
}

export function publishFiniteCapacitySchedule(id) {
  return request({ url: `/production/finite-capacity-plans/${id}/publish/`, method: 'post' })
}

export function getGanttData(id) {
  return request({ url: `/production/finite-capacity-plans/${id}/gantt_data/`, method: 'get' })
}

export function getScheduledTasks(params) {
  return request({ url: '/production/scheduled-tasks/', method: 'get', params })
}

// ========== 设备能力矩阵 ==========
export function getEquipmentCapabilities(params) {
  return request({ url: '/production/equipment-capabilities/', method: 'get', params })
}

export function createEquipmentCapability(data) {
  return request({ url: '/production/equipment-capabilities/', method: 'post', data })
}

export function updateEquipmentCapability(id, data) {
  return request({ url: `/production/equipment-capabilities/${id}/`, method: 'put', data })
}

export function deleteEquipmentCapability(id) {
  return request({ url: `/production/equipment-capabilities/${id}/`, method: 'delete' })
}

export function getCapabilityByProcess(params) {
  return request({ url: '/production/equipment-capabilities/by_process/', method: 'get', params })
}

export function getCapabilityMatrix() {
  return request({ url: '/production/equipment-capabilities/matrix/', method: 'get' })
}

// ========== OEE ==========
export function getOEERecords(params) {
  return request({ url: '/production/equipment-oee/', method: 'get', params })
}

export function createOEERecord(data) {
  return request({ url: '/production/equipment-oee/', method: 'post', data })
}

export function getOEEDashboard(params) {
  return request({ url: '/production/equipment-oee/dashboard/', method: 'get', params })
}

// ========== 看板WIP限制 ==========
export function getKanbanWIPRules(params) {
  return request({ url: '/production/kanban-wip-rules/', method: 'get', params })
}

export function createKanbanWIPRule(data) {
  return request({ url: '/production/kanban-wip-rules/', method: 'post', data })
}

export function updateKanbanWIPRule(id, data) {
  return request({ url: `/production/kanban-wip-rules/${id}/`, method: 'put', data })
}

export function deleteKanbanWIPRule(id) {
  return request({ url: `/production/kanban-wip-rules/${id}/`, method: 'delete' })
}

export function getKanbanWIPAlerts(params) {
  return request({ url: '/production/kanban-wip-alerts/', method: 'get', params })
}

export function resolveWIPAlert(id) {
  return request({ url: `/production/kanban-wip-alerts/${id}/resolve/`, method: 'post' })
}

export function getKanbanWIPStatus() {
  return request({ url: '/production/kanban/wip-status/', method: 'get' })
}
