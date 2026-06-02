/**
 * Export API
 */
import type { AxiosResponse } from 'axios'

import { requestBlob } from '@/utils/request'

// Download file helper —— blob 响应保留完整 AxiosResponse，从中取 data/headers
function downloadFile(response: AxiosResponse<Blob>, filename: string): void {
  const blob = new Blob([response.data], {
    type: (response.headers['content-type'] as string) || undefined,
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

function exportBlob(url: string, filename: string, params?: Record<string, any>): Promise<void> {
  return requestBlob({ url, method: 'get', params }).then(response => downloadFile(response, filename))
}

const today = (): string => new Date().toISOString().slice(0, 10)

// Export projects
export function exportProjects(params?: Record<string, any>) {
  return exportBlob('/core/export/projects/', `projects_${today()}.xlsx`, params)
}

// Export sales orders
export function exportSalesOrders(params?: Record<string, any>) {
  return exportBlob('/core/export/sales-orders/', `sales_orders_${today()}.xlsx`, params)
}

// Export purchase orders
export function exportPurchaseOrders(params?: Record<string, any>) {
  return exportBlob('/core/export/purchase-orders/', `purchase_orders_${today()}.xlsx`, params)
}

// Export stock
export function exportStock(params?: Record<string, any>) {
  return exportBlob('/core/export/stock/', `stock_${today()}.xlsx`, params)
}

// Export expenses
export function exportExpenses(params?: Record<string, any>) {
  return exportBlob('/core/export/expenses/', `expenses_${today()}.xlsx`, params)
}

// Export AR
export function exportAR(params?: Record<string, any>) {
  return exportBlob('/core/export/ar/', `accounts_receivable_${today()}.xlsx`, params)
}

// Export AP
export function exportAP(params?: Record<string, any>) {
  return exportBlob('/core/export/ap/', `accounts_payable_${today()}.xlsx`, params)
}

// Export project profit report
export function exportProjectProfit(params?: Record<string, any>) {
  return exportBlob('/core/export/project-profit/', `project_profit_${today()}.xlsx`, params)
}
