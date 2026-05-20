/**
 * 仪表盘 API
 */
import request from '@/utils/request'

// 管理层仪表盘
export function getExecutiveDashboard() {
  return request({
    url: '/core/dashboards/executive/',
    method: 'get'
  })
}

// 项目经理仪表盘
export function getProjectManagerDashboard() {
  return request({
    url: '/core/dashboards/project-manager/',
    method: 'get'
  })
}

// 销售仪表盘
export function getSalesDashboard() {
  return request({
    url: '/core/dashboards/sales/',
    method: 'get'
  })
}

// 生产仪表盘
export function getProductionDashboard() {
  return request({
    url: '/core/dashboards/production/',
    method: 'get'
  })
}

// 财务仪表盘
export function getFinanceDashboard() {
  return request({
    url: '/core/dashboards/finance/',
    method: 'get'
  })
}
