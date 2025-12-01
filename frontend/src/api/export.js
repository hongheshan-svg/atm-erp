/**
 * Export API
 */
import request from '@/utils/request'

// Download file helper
const downloadFile = (response, filename) => {
  const blob = new Blob([response.data], { 
    type: response.headers['content-type'] 
  })
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename || 'export.xlsx'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.URL.revokeObjectURL(url)
}

// Export projects
export function exportProjects(params) {
  return request({
    url: '/core/export/projects/',
    method: 'get',
    params,
    responseType: 'blob'
  }).then(response => {
    downloadFile(response, `projects_${new Date().toISOString().slice(0,10)}.xlsx`)
  })
}

// Export sales orders
export function exportSalesOrders(params) {
  return request({
    url: '/core/export/sales-orders/',
    method: 'get',
    params,
    responseType: 'blob'
  }).then(response => {
    downloadFile(response, `sales_orders_${new Date().toISOString().slice(0,10)}.xlsx`)
  })
}

// Export purchase orders
export function exportPurchaseOrders(params) {
  return request({
    url: '/core/export/purchase-orders/',
    method: 'get',
    params,
    responseType: 'blob'
  }).then(response => {
    downloadFile(response, `purchase_orders_${new Date().toISOString().slice(0,10)}.xlsx`)
  })
}

// Export stock
export function exportStock(params) {
  return request({
    url: '/core/export/stock/',
    method: 'get',
    params,
    responseType: 'blob'
  }).then(response => {
    downloadFile(response, `stock_${new Date().toISOString().slice(0,10)}.xlsx`)
  })
}

// Export expenses
export function exportExpenses(params) {
  return request({
    url: '/core/export/expenses/',
    method: 'get',
    params,
    responseType: 'blob'
  }).then(response => {
    downloadFile(response, `expenses_${new Date().toISOString().slice(0,10)}.xlsx`)
  })
}

// Export AR
export function exportAR(params) {
  return request({
    url: '/core/export/ar/',
    method: 'get',
    params,
    responseType: 'blob'
  }).then(response => {
    downloadFile(response, `accounts_receivable_${new Date().toISOString().slice(0,10)}.xlsx`)
  })
}

// Export AP
export function exportAP(params) {
  return request({
    url: '/core/export/ap/',
    method: 'get',
    params,
    responseType: 'blob'
  }).then(response => {
    downloadFile(response, `accounts_payable_${new Date().toISOString().slice(0,10)}.xlsx`)
  })
}

// Export project profit report
export function exportProjectProfit(params) {
  return request({
    url: '/core/export/project-profit/',
    method: 'get',
    params,
    responseType: 'blob'
  }).then(response => {
    downloadFile(response, `project_profit_${new Date().toISOString().slice(0,10)}.xlsx`)
  })
}
