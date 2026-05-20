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

// ========== 装配指导 ==========
export function getAssemblyGuides(params) {
  return request({ url: '/production/assembly-guides/', method: 'get', params })
}

export function getAssemblyGuide(id) {
  return request({ url: `/production/assembly-guides/${id}/`, method: 'get' })
}

export function createAssemblyGuide(data) {
  return request({ url: '/production/assembly-guides/', method: 'post', data })
}

export function updateAssemblyGuide(id, data) {
  return request({ url: `/production/assembly-guides/${id}/`, method: 'put', data })
}

// ========== 产能规划 ==========
export function getCapacityDashboard(params) {
  return request({ url: '/production/capacity/dashboard/', method: 'get', params })
}

export function getResources(params) {
  return request({ url: '/production/resources/', method: 'get', params })
}

export function createResource(data) {
  return request({ url: '/production/resources/', method: 'post', data })
}

export function getResourceLoad(id) {
  return request({ url: `/production/resources/${id}/load/`, method: 'get' })
}

export function getResourceConflicts(id) {
  return request({ url: `/production/resources/${id}/conflicts/`, method: 'get' })
}

export function getResourceAllocations(params) {
  return request({ url: '/production/resource-allocations/', method: 'get', params })
}

export function checkResourceAvailability(data) {
  return request({ url: '/production/resource-allocations/check_availability/', method: 'post', data })
}

export function createResourceAllocation(data) {
  return request({ url: '/production/resource-allocations/', method: 'post', data })
}

// ========== 资源类型 ==========
export function getResourceTypes(params) {
  return request({ url: '/production/resource-types/', method: 'get', params })
}

export function createResourceType(data) {
  return request({ url: '/production/resource-types/', method: 'post', data })
}

export function updateResourceType(id, data) {
  return request({ url: `/production/resource-types/${id}/`, method: 'put', data })
}

export function patchResourceType(id, data) {
  return request({ url: `/production/resource-types/${id}/`, method: 'patch', data })
}

// ========== 调试记录 ==========
export function getDebugRecords(params) {
  return request({ url: '/production/debug-records/', method: 'get', params })
}

export function getDebugRecord(id) {
  return request({ url: `/production/debug-records/${id}/`, method: 'get' })
}

export function createDebugRecord(data) {
  return request({ url: '/production/debug-records/', method: 'post', data })
}

export function updateDebugRecord(id, data) {
  return request({ url: `/production/debug-records/${id}/`, method: 'put', data })
}

export function startDebug(id) {
  return request({ url: `/production/debug-records/${id}/start_debug/`, method: 'post' })
}

export function completeDebug(id, data) {
  return request({ url: `/production/debug-records/${id}/complete_debug/`, method: 'post', data })
}

export function addDebugCheckItems(id, data) {
  return request({ url: `/production/debug-records/${id}/add_check_items/`, method: 'post', data })
}

// ========== 生产计划 ==========
export function getPlans(params) {
  return request({ url: '/production/plans/', method: 'get', params })
}

export function getPlan(id) {
  return request({ url: `/production/plans/${id}/`, method: 'get' })
}

export function createPlan(data) {
  return request({ url: '/production/plans/', method: 'post', data })
}

export function updatePlan(id, data) {
  return request({ url: `/production/plans/${id}/`, method: 'put', data })
}

export function confirmPlan(id) {
  return request({ url: `/production/plans/${id}/confirm/`, method: 'post' })
}

export function startPlan(id) {
  return request({ url: `/production/plans/${id}/start/`, method: 'post' })
}

export function completePlan(id) {
  return request({ url: `/production/plans/${id}/complete/`, method: 'post' })
}

export function addPlanProcesses(id, data) {
  return request({ url: `/production/plans/${id}/add_processes/`, method: 'post', data })
}

// ========== 工序 ==========
export function getProcesses(params) {
  return request({ url: '/production/processes/', method: 'get', params })
}

export function createProcess(data) {
  return request({ url: '/production/processes/', method: 'post', data })
}

export function updateProcess(id, data) {
  return request({ url: `/production/processes/${id}/`, method: 'put', data })
}

// ========== 计划工序 ==========
export function startPlanProcess(id) {
  return request({ url: `/production/plan-processes/${id}/start/`, method: 'post' })
}

export function completePlanProcess(id) {
  return request({ url: `/production/plan-processes/${id}/complete/`, method: 'post' })
}

export function updatePlanProcessProgress(id, data) {
  return request({ url: `/production/plan-processes/${id}/update_progress/`, method: 'post', data })
}

// ========== 质量检验 ==========
export function getInspections(params) {
  return request({ url: '/production/inspections/', method: 'get', params })
}

export function getInspection(id) {
  return request({ url: `/production/inspections/${id}/`, method: 'get' })
}

export function createInspection(data) {
  return request({ url: '/production/inspections/', method: 'post', data })
}

export function updateInspection(id, data) {
  return request({ url: `/production/inspections/${id}/`, method: 'put', data })
}

export function startInspection(id) {
  return request({ url: `/production/inspections/${id}/start_inspection/`, method: 'post' })
}

export function completeInspection(id, data) {
  return request({ url: `/production/inspections/${id}/complete_inspection/`, method: 'post', data })
}

export function addInspectionItems(id, data) {
  return request({ url: `/production/inspections/${id}/add_items/`, method: 'post', data })
}

// ========== 工艺路线模板 ==========
export function getRoutingTemplates(params) {
  return request({ url: '/production/routing-templates/', method: 'get', params })
}

export function getRoutingTemplate(id) {
  return request({ url: `/production/routing-templates/${id}/`, method: 'get' })
}

export function createRoutingTemplate(data) {
  return request({ url: '/production/routing-templates/', method: 'post', data })
}

export function updateRoutingTemplate(id, data) {
  return request({ url: `/production/routing-templates/${id}/`, method: 'patch', data })
}

export function approveRoutingTemplate(id) {
  return request({ url: `/production/routing-templates/${id}/approve/`, method: 'post' })
}

export function createRoutingTemplateVersion(id) {
  return request({ url: `/production/routing-templates/${id}/create_version/`, method: 'post' })
}

export function applyRoutingTemplateToProject(id, data) {
  return request({ url: `/production/routing-templates/${id}/apply_to_project/`, method: 'post', data })
}

// ========== 序列号 ==========
export function getSerialNumbers(params) {
  return request({ url: '/production/serial-numbers/', method: 'get', params })
}

export function getSerialNumberStatistics() {
  return request({ url: '/production/serial-numbers/statistics/', method: 'get' })
}

export function searchSerialNumbers(params) {
  return request({ url: '/production/serial-numbers/search/', method: 'get', params })
}

export function generateSerialNumberBatch(data) {
  return request({ url: '/production/serial-numbers/generate_batch/', method: 'post', data })
}

export function getSerialNumberFullTrace(id) {
  return request({ url: `/production/serial-numbers/${id}/full_trace/`, method: 'get' })
}

export function addSerialNumberTrace(id, data) {
  return request({ url: `/production/serial-numbers/${id}/add_trace/`, method: 'post', data })
}

export function getSnRules(params) {
  return request({ url: '/production/sn-rules/', method: 'get', params })
}

// ========== 工位 ==========
export function getWorkStations(params) {
  return request({ url: '/production/work-stations/', method: 'get', params })
}

export function createWorkStation(data) {
  return request({ url: '/production/work-stations/', method: 'post', data })
}

export function updateWorkStation(id, data) {
  return request({ url: `/production/work-stations/${id}/`, method: 'put', data })
}

export function deleteWorkStation(id) {
  return request({ url: `/production/work-stations/${id}/`, method: 'delete' })
}

export function getWorkCenters(params) {
  return request({ url: '/production/work-centers/', method: 'get', params })
}
