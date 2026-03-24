/**
 * 项目管理扩展 API
 * - BOM成本卷积
 * - 图纸版本管理
 * - 安装调试现场管理
 */
import request from '@/utils/request'

// ========== BOM成本卷积 ==========
export function getBOMCostSnapshots(params) {
  return request({ url: '/projects/bom-cost-snapshots/', method: 'get', params })
}

export function getBOMCostSnapshot(id) {
  return request({ url: `/projects/bom-cost-snapshots/${id}/`, method: 'get' })
}

export function calculateBOMCost(data) {
  return request({ url: '/projects/bom-cost-snapshots/calculate/', method: 'post', data })
}

export function compareBOMCost(data) {
  return request({ url: '/projects/bom-cost-snapshots/compare/', method: 'post', data })
}

export function deleteBOMCostSnapshot(id) {
  return request({ url: `/projects/bom-cost-snapshots/${id}/`, method: 'delete' })
}

export function getBOMCostDetails(params) {
  return request({ url: '/projects/bom-cost-details/', method: 'get', params })
}

// ========== 图纸版本管理 ==========
export function getDrawingVersions(params) {
  return request({ url: '/projects/drawing-versions/', method: 'get', params })
}

export function getDrawingVersion(id) {
  return request({ url: `/projects/drawing-versions/${id}/`, method: 'get' })
}

export function createDrawingVersion(data) {
  return request({ url: '/projects/drawing-versions/', method: 'post', data })
}

export function getDrawingTimeline(drawingNumber) {
  return request({ url: `/projects/drawing-versions/${drawingNumber}/timeline/`, method: 'get' })
}

export function approveDrawingVersion(id) {
  return request({ url: `/projects/drawing-versions/${id}/approve/`, method: 'post' })
}

export function rejectDrawingVersion(id, data) {
  return request({ url: `/projects/drawing-versions/${id}/reject/`, method: 'post', data })
}

export function batchUpgradeDrawings(id, data) {
  return request({ url: `/projects/drawing-versions/${id}/batch_upgrade/`, method: 'post', data })
}

export function getDrawingAffectedParts(params) {
  return request({ url: '/projects/drawing-affected-parts/', method: 'get', params })
}

// ========== 安装调试现场管理 ==========
export function getInstallationTasks(params) {
  return request({ url: '/projects/installation-tasks/', method: 'get', params })
}

export function getInstallationTask(id) {
  return request({ url: `/projects/installation-tasks/${id}/`, method: 'get' })
}

export function createInstallationTask(data) {
  return request({ url: '/projects/installation-tasks/', method: 'post', data })
}

export function updateInstallationTask(id, data) {
  return request({ url: `/projects/installation-tasks/${id}/`, method: 'put', data })
}

export function dispatchInstallationTask(id, data) {
  return request({ url: `/projects/installation-tasks/${id}/dispatch/`, method: 'post', data })
}

export function updateInstallationTaskStatus(id, data) {
  return request({ url: `/projects/installation-tasks/${id}/update_status/`, method: 'post', data })
}

export function getInstallationTaskSummary() {
  return request({ url: '/projects/installation-tasks/summary/', method: 'get' })
}

// 现场日志
export function getSiteLogs(params) {
  return request({ url: '/projects/site-logs/', method: 'get', params })
}

export function createSiteLog(data) {
  return request({ url: '/projects/site-logs/', method: 'post', data })
}

// 调试记录
export function getCommissioningRecords(params) {
  return request({ url: '/projects/commissioning-records/', method: 'get', params })
}

export function createCommissioningRecord(data) {
  return request({ url: '/projects/commissioning-records/', method: 'post', data })
}

// 现场问题
export function getSiteIssues(params) {
  return request({ url: '/projects/site-issues/', method: 'get', params })
}

export function createSiteIssue(data) {
  return request({ url: '/projects/site-issues/', method: 'post', data })
}

export function resolveSiteIssue(id, data) {
  return request({ url: `/projects/site-issues/${id}/resolve/`, method: 'post', data })
}

// 客户验收
export function getCustomerAcceptances(params) {
  return request({ url: '/projects/customer-acceptances/', method: 'get', params })
}

export function createCustomerAcceptance(data) {
  return request({ url: '/projects/customer-acceptances/', method: 'post', data })
}
