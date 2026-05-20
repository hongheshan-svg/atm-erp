/**
 * 报表与预测分析 API
 * - 可配置报表
 * - 预测分析
 * - 风险预警
 */
import request from '@/utils/request'

// ========== 可配置报表 ==========
export function getReportTemplates(params) {
  return request({ url: '/reports/report-templates/', method: 'get', params })
}

export function getReportTemplate(id) {
  return request({ url: `/reports/report-templates/${id}/`, method: 'get' })
}

export function createReportTemplate(data) {
  return request({ url: '/reports/report-templates/', method: 'post', data })
}

export function updateReportTemplate(id, data) {
  return request({ url: `/reports/report-templates/${id}/`, method: 'put', data })
}

export function deleteReportTemplate(id) {
  return request({ url: `/reports/report-templates/${id}/`, method: 'delete' })
}

export function executeReportTemplate(id, data) {
  return request({ url: `/reports/report-templates/${id}/execute/`, method: 'post', data })
}

export function favoriteReportTemplate(id) {
  return request({ url: `/reports/report-templates/${id}/favorite/`, method: 'post' })
}

export function getMyFavoriteReports(params) {
  return request({ url: '/reports/report-templates/my_favorites/', method: 'get', params })
}

export function getDataSourceFields(params) {
  return request({ url: '/reports/report-templates/data_source_fields/', method: 'get', params })
}

export function getReportExecutions(params) {
  return request({ url: '/reports/report-executions/', method: 'get', params })
}

// ========== 预测分析 ==========
export function getPredictionModels(params) {
  return request({ url: '/reports/prediction-models/', method: 'get', params })
}

export function getPredictionResults(params) {
  return request({ url: '/reports/prediction-results/', method: 'get', params })
}

export function getCostTrend(params) {
  return request({ url: '/reports/prediction/cost-trend/', method: 'get', params })
}

export function getDeliveryRisk(params) {
  return request({ url: '/reports/prediction/delivery-risk/', method: 'get', params })
}

export function getCapacityLoad(params) {
  return request({ url: '/reports/prediction/capacity-load/', method: 'get', params })
}

// ========== 风险预警 ==========
export function getRiskAlerts(params) {
  return request({ url: '/reports/risk-alerts/', method: 'get', params })
}

export function acknowledgeRiskAlert(id) {
  return request({ url: `/reports/risk-alerts/${id}/acknowledge/`, method: 'post' })
}

export function resolveRiskAlert(id, data) {
  return request({ url: `/reports/risk-alerts/${id}/resolve/`, method: 'post', data })
}

// ========== 行业报表 ==========
export function getAgingReport(params) {
  return request({ url: '/reports/aging/', method: 'get', params })
}

export function getCapacityUtilizationReport(params) {
  return request({ url: '/reports/industry/capacity-utilization/', method: 'get', params })
}

export function getCustomerValueReport(params) {
  return request({ url: '/reports/industry/customer-value/', method: 'get', params })
}

export function getEquipmentLifecycleReport(params) {
  return request({ url: '/reports/industry/equipment-lifecycle/', method: 'get', params })
}

export function getProfitabilityReport(params) {
  return request({ url: '/reports/profitability/', method: 'get', params })
}

export function getProjectProfitabilityReport(params) {
  return request({ url: '/reports/industry/project-profitability/', method: 'get', params })
}

export function exportProjectProfitabilityReport(params) {
  return request({ url: '/reports/project-profitability/export/', method: 'get', params, responseType: 'blob' })
}

export function exportTimelogReport(params) {
  return request({ url: '/reports/timelog-report/export/', method: 'get', params, responseType: 'blob' })
}
