/**
 * 数据分析 API
 */
import request from '@/utils/request'

export function getAnalyticsDashboard(params?: Record<string, any>) {
  return request({ url: '/analytics/dashboard/', method: 'get', params })
}
export function getCashFlowForecast(params?: Record<string, any>) {
  return request({ url: '/analytics/cash_flow_forecast/', method: 'get', params })
}
export function getInventoryTurnover(params?: Record<string, any>) {
  return request({ url: '/analytics/inventory_turnover/', method: 'get', params })
}
export function getSlowMovingItems(params?: Record<string, any>) {
  return request({ url: '/analytics/slow_moving_items/', method: 'get', params })
}
export function getProjectCosts(params?: Record<string, any>) {
  return request({ url: '/analytics/project_costs/', method: 'get', params })
}
export function recalculateCosts(data: any) {
  return request({ url: '/analytics/recalculate_costs/', method: 'post', data })
}
export function getManagementDashboard(params?: Record<string, any>) {
  return request({ url: '/analytics/management_dashboard/', method: 'get', params })
}
export function getInventoryStocks(params?: Record<string, any>) {
  return request({ url: '/inventory/stocks/', method: 'get', params })
}
export function getProjectProfitability(params?: Record<string, any>) {
  return request({ url: '/reports/profitability/', method: 'get', params })
}
