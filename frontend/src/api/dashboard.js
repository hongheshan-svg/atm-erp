/**
 * Dashboard API - Configurable widgets and user dashboard
 */
import request from '@/utils/request'

// Dashboard Widgets
export function getWidgets(params) {
  return request({
    url: '/core/dashboard-widgets/',
    method: 'get',
    params
  })
}

export function getWidget(id) {
  return request({
    url: `/core/dashboard-widgets/${id}/`,
    method: 'get'
  })
}

export function createWidget(data) {
  return request({
    url: '/core/dashboard-widgets/',
    method: 'post',
    data
  })
}

export function updateWidget(id, data) {
  return request({
    url: `/core/dashboard-widgets/${id}/`,
    method: 'put',
    data
  })
}

export function deleteWidget(id) {
  return request({
    url: `/core/dashboard-widgets/${id}/`,
    method: 'delete'
  })
}

export function getWidgetData(id, params) {
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

// User Dashboard
export function getUserDashboard() {
  return request({
    url: '/core/user-dashboard/',
    method: 'get'
  })
}

export function updateDashboardLayout(layout, theme) {
  return request({
    url: '/core/user-dashboard/update_layout/',
    method: 'put',
    data: { layout, theme }
  })
}

export function resetDashboard() {
  return request({
    url: '/core/user-dashboard/reset/',
    method: 'post'
  })
}

export function getAllDashboardData(params) {
  return request({
    url: '/core/user-dashboard/all_data/',
    method: 'get',
    params
  })
}
