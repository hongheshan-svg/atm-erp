/**
 * MES 制造执行系统 API
 */
import request from '@/utils/request'

// ========== Andon系统 ==========
export function getAndonTypeList(params) {
  return request({ url: '/production/andon-types/', method: 'get', params })
}
export function getAndonStationList(params) {
  return request({ url: '/production/andon-stations/', method: 'get', params })
}
export function getAndonStatusBoard() {
  return request({ url: '/production/andon-stations/status_board/', method: 'get' })
}
export function getAndonCallList(params) {
  return request({ url: '/production/andon-calls/', method: 'get', params })
}
export function createAndonCall(data) {
  return request({ url: '/production/andon-calls/', method: 'post', data })
}
export function respondAndon(id) {
  return request({ url: `/production/andon-calls/${id}/respond/`, method: 'post' })
}
export function startProcessAndon(id) {
  return request({ url: `/production/andon-calls/${id}/start_process/`, method: 'post' })
}
export function resolveAndon(id, data) {
  return request({ url: `/production/andon-calls/${id}/resolve/`, method: 'post', data })
}
export function escalateAndon(id, data) {
  return request({ url: `/production/andon-calls/${id}/escalate/`, method: 'post', data })
}
export function getAndonStatistics(params) {
  return request({ url: '/production/andon-calls/statistics/', method: 'get', params })
}
export function getPendingAndonCalls() {
  return request({ url: '/production/andon-calls/pending/', method: 'get' })
}
export function getAndonCallDetail(id) {
  return request({ url: `/production/andon-calls/${id}/`, method: 'get' })
}

// ========== APS排程 ==========
export function getScheduleOrderList(params) {
  return request({ url: '/production/schedule-orders/', method: 'get', params })
}
export function autoSchedule(data) {
  return request({ url: '/production/schedule-orders/auto_schedule/', method: 'post', data })
}
export function startScheduleOrder(id) {
  return request({ url: `/production/schedule-orders/${id}/start/`, method: 'post' })
}
export function completeScheduleOrder(id, data) {
  return request({ url: `/production/schedule-orders/${id}/complete/`, method: 'post', data })
}
export function getScheduleGantt(id) {
  return request({ url: `/production/schedule-orders/${id}/gantt/`, method: 'get' })
}
export function getScheduleGanttList(params) {
  return request({ url: '/production/schedule-orders/gantt/', method: 'get', params })
}
export function getScheduleCapacity(params) {
  return request({ url: '/production/schedule-orders/capacity/', method: 'get', params })
}
export function getScheduleTaskList(params) {
  return request({ url: '/production/schedule-tasks/', method: 'get', params })
}
export function startScheduleTask(id) {
  return request({ url: `/production/schedule-tasks/${id}/start/`, method: 'post' })
}
export function completeScheduleTask(id) {
  return request({ url: `/production/schedule-tasks/${id}/complete/`, method: 'post' })
}

// ========== 数据采集 ==========
export function getDataSourceList(params) {
  return request({ url: '/production/data-sources/', method: 'get', params })
}
export function createDataSource(data) {
  return request({ url: '/production/data-sources/', method: 'post', data })
}
export function updateDataSource(id, data) {
  return request({ url: `/production/data-sources/${id}/`, method: 'put', data })
}
export function deleteDataSource(id) {
  return request({ url: `/production/data-sources/${id}/`, method: 'delete' })
}
export function startDataSource(id) {
  return request({ url: `/production/data-sources/${id}/start/`, method: 'post' })
}
export function stopDataSource(id) {
  return request({ url: `/production/data-sources/${id}/stop/`, method: 'post' })
}
export function testDataSourceConnection(id) {
  return request({ url: `/production/data-sources/${id}/test_connection/`, method: 'post' })
}
export function getDataPointList(params) {
  return request({ url: '/production/data-points/', method: 'get', params })
}
export function createDataPoint(data) {
  return request({ url: '/production/data-points/', method: 'post', data })
}
export function updateDataPoint(id, data) {
  return request({ url: `/production/data-points/${id}/`, method: 'put', data })
}
export function deleteDataPoint(id) {
  return request({ url: `/production/data-points/${id}/`, method: 'delete' })
}
export function patchDataPoint(id, data) {
  return request({ url: `/production/data-points/${id}/`, method: 'patch', data })
}
export function getDataPointDetailHistory(id, params) {
  return request({ url: `/production/data-points/${id}/history/`, method: 'get', params })
}
export function getRealtimeData(params) {
  return request({ url: '/production/data-points/realtime/', method: 'get', params })
}
export function getDataPointHistory(params) {
  return request({ url: '/production/data-points/history/', method: 'get', params })
}
export function getDataAlarmList(params) {
  return request({ url: '/production/data-alarms/', method: 'get', params })
}
export function getActiveAlarms() {
  return request({ url: '/production/data-alarms/active/', method: 'get' })
}
export function acknowledgeAlarm(id) {
  return request({ url: `/production/data-alarms/${id}/acknowledge/`, method: 'post' })
}
export function resolveAlarm(id, data) {
  return request({ url: `/production/data-alarms/${id}/resolve/`, method: 'post', data })
}
export function getAlarmStatistics(params) {
  return request({ url: '/production/data-alarms/statistics/', method: 'get', params })
}

// ========== 看板 ==========
export function getKanbanData() {
  return request({ url: '/production/kanban/', method: 'get' })
}
export function getWorkCenterKanban(id) {
  return request({ url: `/production/kanban/work-center/${id}/`, method: 'get' })
}
export function getProductionTrend(params) {
  return request({ url: '/production/kanban/trend/', method: 'get', params })
}
export function getAndonAlerts() {
  return request({ url: '/production/kanban/alerts/', method: 'get' })
}
