/**
 * 项目管理扩展 API
 * - BOM成本卷积
 * - 图纸版本管理
 * - 安装调试现场管理
 */
import request from '@/utils/request'

// ========== BOM成本卷积 ==========
export function getBOMCostSnapshots(params?: Record<string, any>) {
  return request({ url: '/projects/bom-cost-snapshots/', method: 'get', params })
}

export function getBOMCostSnapshot(id: number) {
  return request({ url: `/projects/bom-cost-snapshots/${id}/`, method: 'get' })
}

export function calculateBOMCost(data: any) {
  return request({ url: '/projects/bom-cost-snapshots/calculate/', method: 'post', data })
}

export function compareBOMCost(data: any) {
  return request({ url: '/projects/bom-cost-snapshots/compare/', method: 'post', data })
}

export function deleteBOMCostSnapshot(id: number) {
  return request({ url: `/projects/bom-cost-snapshots/${id}/`, method: 'delete' })
}

export function getBOMCostDetails(params?: Record<string, any>) {
  return request({ url: '/projects/bom-cost-details/', method: 'get', params })
}

// ========== 图纸版本管理 ==========
export function getDrawingVersions(params?: Record<string, any>) {
  return request({ url: '/projects/drawing-versions/', method: 'get', params })
}

export function getDrawingVersion(id: number) {
  return request({ url: `/projects/drawing-versions/${id}/`, method: 'get' })
}

export function createDrawingVersion(data: any) {
  return request({ url: '/projects/drawing-versions/', method: 'post', data })
}

export function getDrawingTimeline(drawingNumber: any) {
  return request({ url: `/projects/drawing-versions/${drawingNumber}/timeline/`, method: 'get' })
}

export function submitDrawingReview(id: number) {
  return request({ url: `/projects/drawing-versions/${id}/submit_review/`, method: 'post' })
}

export function approveDrawingVersion(id: number) {
  return request({ url: `/projects/drawing-versions/${id}/approve/`, method: 'post' })
}

export function rejectDrawingVersion(id: number, data: any) {
  return request({ url: `/projects/drawing-versions/${id}/reject/`, method: 'post', data })
}

export function batchUpgradeDrawings(id: number, data: any) {
  return request({ url: `/projects/drawing-versions/${id}/batch_upgrade/`, method: 'post', data })
}

export function getDrawingAffectedParts(params?: Record<string, any>) {
  return request({ url: '/projects/drawing-affected-parts/', method: 'get', params })
}

// ========== 安装调试现场管理 ==========
export function getInstallationTasks(params?: Record<string, any>) {
  return request({ url: '/projects/installation-tasks/', method: 'get', params })
}

export function getInstallationTask(id: number) {
  return request({ url: `/projects/installation-tasks/${id}/`, method: 'get' })
}

export function createInstallationTask(data: any) {
  return request({ url: '/projects/installation-tasks/', method: 'post', data })
}

export function updateInstallationTask(id: number, data: any) {
  return request({ url: `/projects/installation-tasks/${id}/`, method: 'put', data })
}

export function dispatchInstallationTask(id: number, data: any) {
  return request({ url: `/projects/installation-tasks/${id}/dispatch/`, method: 'post', data })
}

export function updateInstallationTaskStatus(id: number, data: any) {
  return request({ url: `/projects/installation-tasks/${id}/update_status/`, method: 'post', data })
}

export function getInstallationTaskSummary() {
  return request({ url: '/projects/installation-tasks/summary/', method: 'get' })
}

// 现场日志
export function getSiteLogs(params?: Record<string, any>) {
  return request({ url: '/projects/site-logs/', method: 'get', params })
}

export function createSiteLog(data: any) {
  return request({ url: '/projects/site-logs/', method: 'post', data })
}

// 调试记录
export function getCommissioningRecords(params?: Record<string, any>) {
  return request({ url: '/projects/commissioning-records/', method: 'get', params })
}

export function createCommissioningRecord(data: any) {
  return request({ url: '/projects/commissioning-records/', method: 'post', data })
}

// 现场问题
export function getSiteIssues(params?: Record<string, any>) {
  return request({ url: '/projects/site-issues/', method: 'get', params })
}

export function createSiteIssue(data: any) {
  return request({ url: '/projects/site-issues/', method: 'post', data })
}

export function resolveSiteIssue(id: number, data: any) {
  return request({ url: `/projects/site-issues/${id}/resolve/`, method: 'post', data })
}

// 客户验收
export function getCustomerAcceptances(params?: Record<string, any>) {
  return request({ url: '/projects/customer-acceptances/', method: 'get', params })
}

export function createCustomerAcceptance(data: any) {
  return request({ url: '/projects/customer-acceptances/', method: 'post', data })
}
