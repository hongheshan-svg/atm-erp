/**
 * 设备管理 API
 */
import request from '@/utils/request'

// ========== 设备台账 ==========
export function getEquipmentList(params?: Record<string, any>) {
  return request({ url: '/projects/equipment/', method: 'get', params })
}
export function getEquipment(id: number) {
  return request({ url: `/projects/equipment/${id}/`, method: 'get' })
}
export function createEquipment(data: any) {
  return request({ url: '/projects/equipment/', method: 'post', data })
}
export function updateEquipment(id: number, data: any) {
  return request({ url: `/projects/equipment/${id}/`, method: 'put', data })
}
export function deleteEquipment(id: number) {
  return request({ url: `/projects/equipment/${id}/`, method: 'delete' })
}
export function getEquipmentStatistics() {
  return request({ url: '/projects/equipment/statistics/', method: 'get' })
}
export function shipEquipment(id: number, data: any) {
  return request({ url: `/projects/equipment/${id}/ship/`, method: 'post', data })
}

// ========== 检验管理 ==========
export function getInspectionTemplateList(params?: Record<string, any>) {
  return request({ url: '/projects/inspection-templates/', method: 'get', params })
}
export function getInspectionTemplate(id: number) {
  return request({ url: `/projects/inspection-templates/${id}/`, method: 'get' })
}
export function createInspectionTemplate(data: any) {
  return request({ url: '/projects/inspection-templates/', method: 'post', data })
}
export function updateInspectionTemplate(id: number, data: any) {
  return request({ url: `/projects/inspection-templates/${id}/`, method: 'put', data })
}
export function deleteInspectionTemplate(id: number) {
  return request({ url: `/projects/inspection-templates/${id}/`, method: 'delete' })
}
export function getInspectionRecordList(params?: Record<string, any>) {
  return request({ url: '/projects/inspection-records/', method: 'get', params })
}
export function createInspectionFromTemplate(data: any) {
  return request({ url: '/projects/inspection-records/create_from_template/', method: 'post', data })
}
export function submitInspectionResult(id: number, data: any) {
  return request({ url: `/projects/inspection-records/${id}/submit_result/`, method: 'post', data })
}
export function getInspectionStatistics() {
  return request({ url: '/projects/inspection-records/statistics/', method: 'get' })
}

// ========== 维保管理 ==========
export function getMaintenanceScheduleList(params?: Record<string, any>) {
  return request({ url: '/projects/maintenance-schedules/', method: 'get', params })
}
export function createMaintenanceSchedule(data: any) {
  return request({ url: '/projects/maintenance-schedules/', method: 'post', data })
}
export function updateMaintenanceSchedule(id: number, data: any) {
  return request({ url: `/projects/maintenance-schedules/${id}/`, method: 'put', data })
}
export function deleteMaintenanceSchedule(id: number) {
  return request({ url: `/projects/maintenance-schedules/${id}/`, method: 'delete' })
}
export function completeMaintenanceSchedule(id: number, data: any) {
  return request({ url: `/projects/maintenance-schedules/${id}/complete/`, method: 'post', data })
}
export function getUpcomingMaintenance(params?: Record<string, any>) {
  return request({ url: '/projects/maintenance-schedules/upcoming/', method: 'get', params })
}
export function getMaintenanceCalendar(params?: Record<string, any>) {
  return request({ url: '/projects/maintenance/calendar/', method: 'get', params })
}
export function getMaintenanceStatistics(params?: Record<string, any>) {
  return request({ url: '/projects/maintenance/statistics/', method: 'get', params })
}

// ========== 工装管理 ==========
export function getFixtureList(params?: Record<string, any>) {
  return request({ url: '/projects/fixtures/', method: 'get', params })
}
export function getFixture(id: number) {
  return request({ url: `/projects/fixtures/${id}/`, method: 'get' })
}
export function createFixture(data: any) {
  return request({ url: '/projects/fixtures/', method: 'post', data })
}
export function updateFixture(id: number, data: any) {
  return request({ url: `/projects/fixtures/${id}/`, method: 'put', data })
}
export function deleteFixture(id: number) {
  return request({ url: `/projects/fixtures/${id}/`, method: 'delete' })
}
export function checkoutFixture(id: number, data: any) {
  return request({ url: `/projects/fixtures/${id}/checkout/`, method: 'post', data })
}
export function returnFixture(id: number, data: any) {
  return request({ url: `/projects/fixtures/${id}/return_fixture/`, method: 'post', data })
}
export function getFixtureStatistics() {
  return request({ url: '/projects/fixtures/statistics/', method: 'get' })
}
export function getCalibrationDueFixtures(params?: Record<string, any>) {
  return request({ url: '/projects/fixtures/calibration_due/', method: 'get', params })
}
export function getFixtureCategoryTree() {
  return request({ url: '/projects/fixture-categories/tree/', method: 'get' })
}

// ========== OEE分析 ==========
export function getOEERecordList(params?: Record<string, any>) {
  return request({ url: '/projects/oee-records/', method: 'get', params })
}
export function getOEEByEquipment(params?: Record<string, any>) {
  return request({ url: '/projects/oee-records/by_equipment/', method: 'get', params })
}
export function getOEESummary(params?: Record<string, any>) {
  return request({ url: '/projects/oee-records/summary/', method: 'get', params })
}
export function getOEEDowntimeAnalysis(params?: Record<string, any>) {
  return request({ url: '/projects/oee-records/downtime_analysis/', method: 'get', params })
}
export function getOEEBenchmark(params?: Record<string, any>) {
  return request({ url: '/projects/oee-records/benchmark/', method: 'get', params })
}

// ========== 工装分类 ==========
export function getFixtureCategoryList(params?: Record<string, any>) {
  return request({ url: '/projects/fixture-categories/', method: 'get', params })
}
export function createFixtureCategory(data: any) {
  return request({ url: '/projects/fixture-categories/', method: 'post', data })
}
export function updateFixtureCategory(id: number, data: any) {
  return request({ url: `/projects/fixture-categories/${id}/`, method: 'patch', data })
}
export function deleteFixtureCategory(id: number) {
  return request({ url: `/projects/fixture-categories/${id}/`, method: 'delete' })
}

// ========== 工装操作 ==========
export function calibrateFixture(id: number, data: any) {
  return request({ url: `/projects/fixtures/${id}/calibrate/`, method: 'post', data })
}
export function maintainFixture(id: number, data: any) {
  return request({ url: `/projects/fixtures/${id}/maintain/`, method: 'post', data })
}

// ========== 检验记录补充 ==========
export function getInspectionRecord(id: number) {
  return request({ url: `/projects/inspection-records/${id}/`, method: 'get' })
}
export function completeInspectionRecord(id: number, data: any) {
  return request({ url: `/projects/inspection-records/${id}/complete/`, method: 'post', data })
}
export function copyInspectionTemplate(id: number, data: any) {
  return request({ url: `/projects/inspection-templates/${id}/copy/`, method: 'post', data })
}

// ========== 检验结果 ==========
export function getUnhandledAbnormal() {
  return request({ url: '/projects/inspection-results/unhandled_abnormal/', method: 'get' })
}
export function handleInspectionAbnormal(id: number, data: any) {
  return request({ url: `/projects/inspection-results/${id}/handle/`, method: 'post', data })
}

// ========== OEE补充 ==========
export function getOEERanking(params?: Record<string, any>) {
  return request({ url: '/projects/oee-records/ranking/', method: 'get', params })
}
export function getOEETrend(params?: Record<string, any>) {
  return request({ url: '/projects/oee-records/trend/', method: 'get', params })
}
export function getOEEDowntime(params?: Record<string, any>) {
  return request({ url: '/projects/oee-records/downtime/', method: 'get', params })
}
