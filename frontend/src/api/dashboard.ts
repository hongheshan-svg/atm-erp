/**
 * Dashboard API - Configurable widgets and user dashboard
 */
import request from '@/utils/request'

// Dashboard Widgets
export function getWidgets(params?: Record<string, any>) {
  return request({
    url: '/core/dashboard-widgets/',
    method: 'get',
    params
  })
}

export function getWidget(id: number) {
  return request({
    url: `/core/dashboard-widgets/${id}/`,
    method: 'get'
  })
}

export function createWidget(data: any) {
  return request({
    url: '/core/dashboard-widgets/',
    method: 'post',
    data
  })
}

export function updateWidget(id: number, data: any) {
  return request({
    url: `/core/dashboard-widgets/${id}/`,
    method: 'put',
    data
  })
}

export function deleteWidget(id: number) {
  return request({
    url: `/core/dashboard-widgets/${id}/`,
    method: 'delete'
  })
}

export function getWidgetData(id: number, params?: Record<string, any>) {
  return request({
    url: `/core/dashboard-widgets/${id}/data/`,
    method: 'get',
    params
  })
}

export function getWidgetTypes() {
  return request({
    url: '/core/dashboard-widgets/widget_types/',
    method: 'get'
  })
}

export function getDataSources() {
  return request({
    url: '/core/dashboard-widgets/data_sources/',
    method: 'get'
  })
}

export function getAvailableWidgets() {
  return request({
    url: '/core/dashboard-widgets/available/',
    method: 'get'
  })
}

// User Dashboard
export function getUserDashboard() {
  return request({
    url: '/core/user-dashboard/',
    method: 'get'
  })
}

export function updateDashboardLayout(layout: any, theme?: any) {
  return request({
    url: '/core/user-dashboard/save_layout/',
    method: 'post',
    data: { layout, theme }
  })
}

export function getMyDashboard() {
  return request({
    url: '/core/user-dashboard/my_dashboard/',
    method: 'get'
  })
}

export function resetDashboard() {
  return request({
    url: '/core/user-dashboard/reset/',
    method: 'post'
  })
}
