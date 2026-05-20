/**
 * 财务管理 API
 */
import request from '@/utils/request'

// ========== 应收管理 ==========
export function getReceivableList(params?: Record<string, any>) {
  return request({ url: '/finance/receivables/', method: 'get', params })
}
export function getReceivable(id: number) {
  return request({ url: `/finance/receivables/${id}/`, method: 'get' })
}
export function createReceivable(data: any) {
  return request({ url: '/finance/receivables/', method: 'post', data })
}
export function updateReceivable(id: number, data: any) {
  return request({ url: `/finance/receivables/${id}/`, method: 'put', data })
}
export function deleteReceivable(id: number) {
  return request({ url: `/finance/receivables/${id}/`, method: 'delete' })
}
export function recordReceivablePayment(id: number, data: any) {
  return request({ url: `/finance/receivables/${id}/record_payment/`, method: 'post', data })
}
export function getOverdueReceivables(params?: Record<string, any>) {
  return request({ url: '/finance/receivables/overdue/', method: 'get', params })
}
export function getReceivableAging(params?: Record<string, any>) {
  return request({ url: '/finance/receivables/aging/', method: 'get', params })
}

// ========== 应付管理 ==========
export function getPayableList(params?: Record<string, any>) {
  return request({ url: '/finance/payables/', method: 'get', params })
}
export function getPayable(id: number) {
  return request({ url: `/finance/payables/${id}/`, method: 'get' })
}
export function createPayable(data: any) {
  return request({ url: '/finance/payables/', method: 'post', data })
}
export function updatePayable(id: number, data: any) {
  return request({ url: `/finance/payables/${id}/`, method: 'put', data })
}
export function deletePayable(id: number) {
  return request({ url: `/finance/payables/${id}/`, method: 'delete' })
}
export function recordPayablePayment(id: number, data: any) {
  return request({ url: `/finance/payables/${id}/record_payment/`, method: 'post', data })
}
export function getOverduePayables(params?: Record<string, any>) {
  return request({ url: '/finance/payables/overdue/', method: 'get', params })
}

// ========== 发票管理 ==========
export function getInvoiceList(params?: Record<string, any>) {
  return request({ url: '/finance/invoices/', method: 'get', params })
}
export function getInvoice(id: number) {
  return request({ url: `/finance/invoices/${id}/`, method: 'get' })
}
export function createInvoice(data: any) {
  return request({ url: '/finance/invoices/', method: 'post', data })
}
export function updateInvoice(id: number, data: any) {
  return request({ url: `/finance/invoices/${id}/`, method: 'put', data })
}
export function deleteInvoice(id: number) {
  return request({ url: `/finance/invoices/${id}/`, method: 'delete' })
}
export function certifyInvoice(id: number) {
  return request({ url: `/finance/invoices/${id}/certify/`, method: 'post' })
}
export function voidInvoice(id: number) {
  return request({ url: `/finance/invoices/${id}/void/`, method: 'post' })
}
export function autoMatchInvoice(id: number) {
  return request({ url: `/finance/invoices/${id}/auto_match/`, method: 'post' })
}

// ========== 费用管理 ==========
export function getExpenseList(params?: Record<string, any>) {
  return request({ url: '/finance/expenses/', method: 'get', params })
}
export function getExpense(id: number) {
  return request({ url: `/finance/expenses/${id}/`, method: 'get' })
}
export function createExpense(data: any) {
  return request({ url: '/finance/expenses/', method: 'post', data })
}
export function updateExpense(id: number, data: any) {
  return request({ url: `/finance/expenses/${id}/`, method: 'put', data })
}
export function deleteExpense(id: number) {
  return request({ url: `/finance/expenses/${id}/`, method: 'delete' })
}
export function reimburseExpense(id: number, data: any) {
  return request({ url: `/finance/expenses/${id}/reimburse/`, method: 'post', data })
}
export function bulkDeleteExpenses(data: any) {
  return request({ url: '/finance/expenses/bulk_delete/', method: 'post', data })
}

// ========== 共享费用 ==========
export function getSharedExpenseList(params?: Record<string, any>) {
  return request({ url: '/finance/shared-expenses/', method: 'get', params })
}
export function getSharedExpense(id: number) {
  return request({ url: `/finance/shared-expenses/${id}/`, method: 'get' })
}
export function createSharedExpense(data: any) {
  return request({ url: '/finance/shared-expenses/', method: 'post', data })
}
export function updateSharedExpense(id: number, data: any) {
  return request({ url: `/finance/shared-expenses/${id}/`, method: 'put', data })
}
export function deleteSharedExpense(id: number) {
  return request({ url: `/finance/shared-expenses/${id}/`, method: 'delete' })
}
export function allocateSharedExpense(id: number, data: any) {
  return request({ url: `/finance/shared-expenses/${id}/allocate/`, method: 'post', data })
}
export function calculateAllocation(id: number) {
  return request({ url: `/finance/shared-expenses/${id}/calculate_allocation/`, method: 'get' })
}
export function cancelAllocation(id: number) {
  return request({ url: `/finance/shared-expenses/${id}/cancel_allocation/`, method: 'post' })
}
export function getAllocationMethods() {
  return request({ url: '/finance/shared-expenses/allocation_methods/', method: 'get' })
}
export function getProjectAllocationSummary(params?: Record<string, any>) {
  return request({ url: '/finance/shared-expenses/project_allocation_summary/', method: 'get', params })
}

// ========== 固定资产 ==========
export function getFixedAssetList(params?: Record<string, any>) {
  return request({ url: '/finance/fixed-assets/', method: 'get', params })
}
export function getFixedAsset(id: number) {
  return request({ url: `/finance/fixed-assets/${id}/`, method: 'get' })
}
export function createFixedAsset(data: any) {
  return request({ url: '/finance/fixed-assets/', method: 'post', data })
}
export function updateFixedAsset(id: number, data: any) {
  return request({ url: `/finance/fixed-assets/${id}/`, method: 'put', data })
}
export function deleteFixedAsset(id: number) {
  return request({ url: `/finance/fixed-assets/${id}/`, method: 'delete' })
}
export function transferAsset(id: number, data: any) {
  return request({ url: `/finance/fixed-assets/${id}/transfer/`, method: 'post', data })
}
export function disposeAsset(id: number, data: any) {
  return request({ url: `/finance/fixed-assets/${id}/dispose/`, method: 'post', data })
}
export function runDepreciation(id: number) {
  return request({ url: `/finance/fixed-assets/${id}/run_depreciation/`, method: 'post' })
}
export function getAssetStatistics() {
  return request({ url: '/finance/fixed-assets/statistics/', method: 'get' })
}
export function getAssetCategoryTree() {
  return request({ url: '/finance/asset-categories/tree/', method: 'get' })
}

// ========== 采购对账 ==========
export function getPurchaseReconciliationList(params?: Record<string, any>) {
  return request({ url: '/finance/purchase-reconciliations/', method: 'get', params })
}
export function getPurchaseReconciliation(id: number) {
  return request({ url: `/finance/purchase-reconciliations/${id}/`, method: 'get' })
}
export function createPurchaseReconciliation(data: any) {
  return request({ url: '/finance/purchase-reconciliations/', method: 'post', data })
}
export function updatePurchaseReconciliation(id: number, data: any) {
  return request({ url: `/finance/purchase-reconciliations/${id}/`, method: 'put', data })
}
export function deletePurchaseReconciliation(id: number) {
  return request({ url: `/finance/purchase-reconciliations/${id}/`, method: 'delete' })
}
export function generatePurchaseReconciliationLines(id: number) {
  return request({ url: `/finance/purchase-reconciliations/${id}/generate_lines/`, method: 'post' })
}
export function submitPurchaseReconciliation(id: number) {
  return request({ url: `/finance/purchase-reconciliations/${id}/submit/`, method: 'post' })
}
export function confirmPurchaseReconciliation(id: number) {
  return request({ url: `/finance/purchase-reconciliations/${id}/confirm/`, method: 'post' })
}
export function getSupplierReconciliationSummary(params?: Record<string, any>) {
  return request({ url: '/finance/purchase-reconciliations/supplier_summary/', method: 'get', params })
}

// ========== 销售对账 ==========
export function getSalesReconciliationList(params?: Record<string, any>) {
  return request({ url: '/finance/sales-reconciliations/', method: 'get', params })
}
export function getSalesReconciliation(id: number) {
  return request({ url: `/finance/sales-reconciliations/${id}/`, method: 'get' })
}
export function createSalesReconciliation(data: any) {
  return request({ url: '/finance/sales-reconciliations/', method: 'post', data })
}
export function updateSalesReconciliation(id: number, data: any) {
  return request({ url: `/finance/sales-reconciliations/${id}/`, method: 'put', data })
}
export function deleteSalesReconciliation(id: number) {
  return request({ url: `/finance/sales-reconciliations/${id}/`, method: 'delete' })
}
export function generateSalesReconciliationLines(id: number) {
  return request({ url: `/finance/sales-reconciliations/${id}/generate_lines/`, method: 'post' })
}
export function submitSalesReconciliation(id: number) {
  return request({ url: `/finance/sales-reconciliations/${id}/submit/`, method: 'post' })
}
export function confirmSalesReconciliation(id: number) {
  return request({ url: `/finance/sales-reconciliations/${id}/confirm/`, method: 'post' })
}
export function getCustomerReconciliationSummary(params?: Record<string, any>) {
  return request({ url: '/finance/sales-reconciliations/customer_summary/', method: 'get', params })
}

// ========== 项目成本 ==========
export function getProjectCostList(params?: Record<string, any>) {
  return request({ url: '/projects/project-cost-records/', method: 'get', params })
}
export function getProjectCostRecord(id: number) {
  return request({ url: `/projects/project-cost-records/${id}/`, method: 'get' })
}
export function createProjectCostRecord(data: any) {
  return request({ url: '/projects/project-cost-records/', method: 'post', data })
}
export function verifyProjectCostRecord(id: number) {
  return request({ url: `/projects/project-cost-records/${id}/verify/`, method: 'post' })
}

// ========== 应收账款 ==========
export function getReceivables(params?: Record<string, any>) {
  return request({ url: '/finance/receivables/', method: 'get', params })
}

// ========== 应付账款 ==========
export function getPayables(params?: Record<string, any>) {
  return request({ url: '/finance/payables/', method: 'get', params })
}

// ========== 发票管理 ==========
export function getInvoices(params?: Record<string, any>) {
  return request({ url: '/finance/invoices/', method: 'get', params })
}
export function autoMatchInvoices(data: any) {
  return request({ url: '/finance/invoices/auto_match/', method: 'post', data })
}
export function matchInvoiceOrder(id: number, data: any) {
  return request({ url: `/finance/invoices/${id}/match_order/`, method: 'post', data })
}
export function downloadInvoiceTemplate() {
  return request({ url: '/finance/invoices/download_template/', method: 'get', responseType: 'blob' })
}
export function exportInvoices(params?: Record<string, any>, config = {}) {
  return request({ url: '/finance/invoices/export/', method: 'get', params, ...config })
}
export function bulkDeleteInvoices(data: any) {
  return request({ url: '/finance/invoices/bulk_delete/', method: 'post', data })
}
export function getInvoiceAttachments(id: number) {
  return request({ url: `/finance/invoices/${id}/attachments/`, method: 'get' })
}

// ========== 费用管理 (扩展) ==========
export function getExpenses(params?: Record<string, any>) {
  return request({ url: '/finance/expenses/', method: 'get', params })
}
export function submitExpense(id: number) {
  return request({ url: `/finance/expenses/${id}/submit/`, method: 'post' })
}
export function approveExpense(id: number, data: any) {
  return request({ url: `/finance/expenses/${id}/approve/`, method: 'post', data })
}
export function rejectExpense(id: number, data: any) {
  return request({ url: `/finance/expenses/${id}/reject/`, method: 'post', data })
}

// ========== 共享费用 ==========
export function getSharedExpenses(params?: Record<string, any>) {
  return request({ url: '/finance/shared-expenses/', method: 'get', params })
}
export function patchSharedExpense(id: number, data: any) {
  return request({ url: `/finance/shared-expenses/${id}/`, method: 'patch', data })
}
export function calculateSharedExpenseAllocation(id: number) {
  return request({ url: `/finance/shared-expenses/${id}/calculate/`, method: 'post' })
}
export function cancelSharedExpenseAllocation(id: number) {
  return request({ url: `/finance/shared-expenses/${id}/cancel_allocation/`, method: 'post' })
}

// ========== 采购对账 ==========
export function getPurchaseReconciliations(params?: Record<string, any>) {
  return request({ url: '/finance/purchase-reconciliations/', method: 'get', params })
}
export function getPurchaseReconciliationOpeningBalance(params?: Record<string, any>) {
  return request({ url: '/finance/purchase-reconciliations/get_opening_balance/', method: 'get', params })
}
export function getPurchaseReconciliationSupplierSummary(params?: Record<string, any>) {
  return request({ url: '/finance/purchase-reconciliations/supplier_summary/', method: 'get', params })
}
export function confirmPurchaseReconciliationReceipt(id: number, lineId: any) {
  return request({ url: `/finance/purchase-reconciliations/${id}/confirm_receipt/${lineId}/`, method: 'post' })
}

// ========== 销售对账 ==========
export function getSalesReconciliations(params?: Record<string, any>) {
  return request({ url: '/finance/sales-reconciliations/', method: 'get', params })
}
export function getSalesReconciliationOpeningBalance(params?: Record<string, any>) {
  return request({ url: '/finance/sales-reconciliations/get_opening_balance/', method: 'get', params })
}
export function getSalesReconciliationCustomerSummary(params?: Record<string, any>) {
  return request({ url: '/finance/sales-reconciliations/customer_summary/', method: 'get', params })
}
export function confirmSalesReconciliationDelivery(id: number, lineId: any) {
  return request({ url: `/finance/sales-reconciliations/${id}/confirm_delivery/${lineId}/`, method: 'post' })
}

// ========== 发票对账 ==========
export function getInvoiceReconciliations(params?: Record<string, any>) {
  return request({ url: '/finance/invoice-reconciliations/', method: 'get', params })
}
export function getInvoiceReconciliation(id: number) {
  return request({ url: `/finance/invoice-reconciliations/${id}/`, method: 'get' })
}
export function createInvoiceReconciliation(data: any) {
  return request({ url: '/finance/invoice-reconciliations/', method: 'post', data })
}
export function confirmInvoiceReconciliation(id: number) {
  return request({ url: `/finance/invoice-reconciliations/${id}/confirm/`, method: 'post' })
}
export function generateInvoiceReconciliationLines(id: number) {
  return request({ url: `/finance/invoice-reconciliations/${id}/generate_lines/`, method: 'post' })
}

// ========== 银行流水 ==========
export function getBankStatements(params?: Record<string, any>) {
  return request({ url: '/finance/bank-statements/', method: 'get', params })
}
export function matchBankStatement(id: number, data: any) {
  return request({ url: `/finance/bank-statements/${id}/match/`, method: 'post', data })
}
export function ignoreBankStatement(id: number) {
  return request({ url: `/finance/bank-statements/${id}/ignore/`, method: 'post' })
}
export function autoMatchAllBankStatements(data: any) {
  return request({ url: '/finance/bank-statements/auto_match_all/', method: 'post', data })
}
export function bulkDeleteBankStatements(data: any) {
  return request({ url: '/finance/bank-statements/bulk_delete/', method: 'post', data })
}

// ========== 固定资产 ==========
export function getFixedAssets(params?: Record<string, any>) {
  return request({ url: '/finance/fixed-assets/', method: 'get', params })
}
export function patchFixedAsset(id: number, data: any) {
  return request({ url: `/finance/fixed-assets/${id}/`, method: 'patch', data })
}
export function transferFixedAsset(id: number, data: any) {
  return request({ url: `/finance/fixed-assets/${id}/transfer/`, method: 'post', data })
}
export function disposeFixedAsset(id: number, data: any) {
  return request({ url: `/finance/fixed-assets/${id}/dispose/`, method: 'post', data })
}
export function scrapFixedAsset(id: number, data: any) {
  return request({ url: `/finance/fixed-assets/${id}/dispose/`, method: 'post', data: { ...data, disposal_type: 'scrap' } })
}
export function activateFixedAsset(id: number) {
  return request({ url: `/finance/fixed-assets/${id}/`, method: 'patch', data: { status: 'active' } })
}
export function depreciateFixedAssets(data: any) {
  return request({ url: '/finance/fixed-assets/run_depreciation/', method: 'post', data })
}
export function getFixedAssetStatistics() {
  return request({ url: '/finance/fixed-assets/statistics/', method: 'get' })
}
export function inventoryFixedAssets(data: any) {
  return request({ url: '/finance/fixed-assets/asset_inventory/', method: 'post', data })
}
export function getAssetCategories(params?: Record<string, any>) {
  return request({ url: '/finance/asset-categories/', method: 'get', params })
}
