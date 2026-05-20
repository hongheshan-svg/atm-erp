/**
 * 数据分析 API
 */
import request from '@/utils/request'

export function getAnalyticsDashboard(params) {
  return request({ url: '/analytics/dashboard/', method: 'get', params })
}
export function getCashFlowForecast(params) {
  return request({ url: '/analytics/cash_flow_forecast/', method: 'get', params })
}
export function getInventoryTurnover(params) {
  return request({ url: '/analytics/inventory_turnover/', method: 'get', params })
}
export function getSlowMovingItems(params) {
  return request({ url: '/analytics/slow_moving_items/', method: 'get', params })
}
export function getProjectCosts(params) {
  return request({ url: '/analytics/project_costs/', method: 'get', params })
}
export function recalculateCosts(data) {
  return request({ url: '/analytics/recalculate_costs/', method: 'post', data })
}
export function getManagementDashboard(params) {
  return request({ url: '/analytics/management_dashboard/', method: 'get', params })
}
export function getInventoryStocks(params) {
  return request({ url: '/inventory/stocks/', method: 'get', params })
}
export function getProjectProfitability(params) {
  return request({ url: '/reports/profitability/', method: 'get', params })
}
