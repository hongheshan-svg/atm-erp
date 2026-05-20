/**
 * 财务管理 API
 */
import request from '@/utils/request'

// ========== 应收管理 ==========
export function getReceivableList(params) {
  return request({ url: '/finance/receivables/', method: 'get', params })
}
export function getReceivable(id) {
  return request({ url: `/finance/receivables/${id}/`, method: 'get' })
}
export function createReceivable(data) {
  return request({ url: '/finance/receivables/', method: 'post', data })
}
export function updateReceivable(id, data) {
  return request({ url: `/finance/receivables/${id}/`, method: 'put', data })
}
export function deleteReceivable(id) {
  return request({ url: `/finance/receivables/${id}/`, method: 'delete' })
}
export function recordReceivablePayment(id, data) {
  return request({ url: `/finance/receivables/${id}/record_payment/`, method: 'post', data })
}
export function getOverdueReceivables(params) {
  return request({ url: '/finance/receivables/overdue/', method: 'get', params })
}
export function getReceivableAging(params) {
  return request({ url: '/finance/receivables/aging/', method: 'get', params })
}

// ========== 应付管理 ==========
export function getPayableList(params) {
  return request({ url: '/finance/payables/', method: 'get', params })
}
export function getPayable(id) {
  return request({ url: `/finance/payables/${id}/`, method: 'get' })
}
export function createPayable(data) {
  return request({ url: '/finance/payables/', method: 'post', data })
}
export function updatePayable(id, data) {
  return request({ url: `/finance/payables/${id}/`, method: 'put', data })
}
export function deletePayable(id) {
  return request({ url: `/finance/payables/${id}/`, method: 'delete' })
}
export function recordPayablePayment(id, data) {
  return request({ url: `/finance/payables/${id}/record_payment/`, method: 'post', data })
}
export function getOverduePayables(params) {
  return request({ url: '/finance/payables/overdue/', method: 'get', params })
}

// ========== 发票管理 ==========
export function getInvoiceList(params) {
  return request({ url: '/finance/invoices/', method: 'get', params })
}
export function getInvoice(id) {
  return request({ url: `/finance/invoices/${id}/`, method: 'get' })
}
export function createInvoice(data) {
  return request({ url: '/finance/invoices/', method: 'post', data })
}
export function updateInvoice(id, data) {
  return request({ url: `/finance/invoices/${id}/`, method: 'put', data })
}
export function deleteInvoice(id) {
  return request({ url: `/finance/invoices/${id}/`, method: 'delete' })
}
export function certifyInvoice(id) {
  return request({ url: `/finance/invoices/${id}/certify/`, method: 'post' })
}
export function voidInvoice(id) {
  return request({ url: `/finance/invoices/${id}/void/`, method: 'post' })
}
export function autoMatchInvoice(id) {
  return request({ url: `/finance/invoices/${id}/auto_match/`, method: 'post' })
}

// ========== 费用管理 ==========
export function getExpenseList(params) {
  return request({ url: '/finance/expenses/', method: 'get', params })
}
export function getExpense(id) {
  return request({ url: `/finance/expenses/${id}/`, method: 'get' })
}
export function createExpense(data) {
  return request({ url: '/finance/expenses/', method: 'post', data })
}
export function updateExpense(id, data) {
  return request({ url: `/finance/expenses/${id}/`, method: 'put', data })
}
export function deleteExpense(id) {
  return request({ url: `/finance/expenses/${id}/`, method: 'delete' })
}
export function reimburseExpense(id, data) {
  return request({ url: `/finance/expenses/${id}/reimburse/`, method: 'post', data })
}
export function bulkDeleteExpenses(data) {
  return request({ url: '/finance/expenses/bulk_delete/', method: 'post', data })
}

// ========== 共享费用 ==========
export function getSharedExpenseList(params) {
  return request({ url: '/finance/shared-expenses/', method: 'get', params })
}
export function getSharedExpense(id) {
  return request({ url: `/finance/shared-expenses/${id}/`, method: 'get' })
}
export function createSharedExpense(data) {
  return request({ url: '/finance/shared-expenses/', method: 'post', data })
}
export function updateSharedExpense(id, data) {
  return request({ url: `/finance/shared-expenses/${id}/`, method: 'put', data })
}
export function deleteSharedExpense(id) {
  return request({ url: `/finance/shared-expenses/${id}/`, method: 'delete' })
}
export function allocateSharedExpense(id, data) {
  return request({ url: `/finance/shared-expenses/${id}/allocate/`, method: 'post', data })
}
export function calculateAllocation(id) {
  return request({ url: `/finance/shared-expenses/${id}/calculate_allocation/`, method: 'get' })
}
export function cancelAllocation(id) {
  return request({ url: `/finance/shared-expenses/${id}/cancel_allocation/`, method: 'post' })
}
export function getAllocationMethods() {
  return request({ url: '/finance/shared-expenses/allocation_methods/', method: 'get' })
}
export function getProjectAllocationSummary(params) {
  return request({ url: '/finance/shared-expenses/project_allocation_summary/', method: 'get', params })
}

// ========== 固定资产 ==========
export function getFixedAssetList(params) {
  return request({ url: '/finance/fixed-assets/', method: 'get', params })
}
export function getFixedAsset(id) {
  return request({ url: `/finance/fixed-assets/${id}/`, method: 'get' })
}
export function createFixedAsset(data) {
  return request({ url: '/finance/fixed-assets/', method: 'post', data })
}
export function updateFixedAsset(id, data) {
  return request({ url: `/finance/fixed-assets/${id}/`, method: 'put', data })
}
export function deleteFixedAsset(id) {
  return request({ url: `/finance/fixed-assets/${id}/`, method: 'delete' })
}
export function transferAsset(id, data) {
  return request({ url: `/finance/fixed-assets/${id}/transfer/`, method: 'post', data })
}
export function disposeAsset(id, data) {
  return request({ url: `/finance/fixed-assets/${id}/dispose/`, method: 'post', data })
}
export function runDepreciation(id) {
  return request({ url: `/finance/fixed-assets/${id}/run_depreciation/`, method: 'post' })
}
export function getAssetStatistics() {
  return request({ url: '/finance/fixed-assets/statistics/', method: 'get' })
}
export function getAssetCategoryTree() {
  return request({ url: '/finance/asset-categories/tree/', method: 'get' })
}

// ========== 采购对账 ==========
export function getPurchaseReconciliationList(params) {
  return request({ url: '/finance/purchase-reconciliations/', method: 'get', params })
}
export function getPurchaseReconciliation(id) {
  return request({ url: `/finance/purchase-reconciliations/${id}/`, method: 'get' })
}
export function createPurchaseReconciliation(data) {
  return request({ url: '/finance/purchase-reconciliations/', method: 'post', data })
}
export function updatePurchaseReconciliation(id, data) {
  return request({ url: `/finance/purchase-reconciliations/${id}/`, method: 'put', data })
}
export function deletePurchaseReconciliation(id) {
  return request({ url: `/finance/purchase-reconciliations/${id}/`, method: 'delete' })
}
export function generatePurchaseReconciliationLines(id) {
  return request({ url: `/finance/purchase-reconciliations/${id}/generate_lines/`, method: 'post' })
}
export function submitPurchaseReconciliation(id) {
  return request({ url: `/finance/purchase-reconciliations/${id}/submit/`, method: 'post' })
}
export function confirmPurchaseReconciliation(id) {
  return request({ url: `/finance/purchase-reconciliations/${id}/confirm/`, method: 'post' })
}
export function getSupplierReconciliationSummary(params) {
  return request({ url: '/finance/purchase-reconciliations/supplier_summary/', method: 'get', params })
}

// ========== 销售对账 ==========
export function getSalesReconciliationList(params) {
  return request({ url: '/finance/sales-reconciliations/', method: 'get', params })
}
export function getSalesReconciliation(id) {
  return request({ url: `/finance/sales-reconciliations/${id}/`, method: 'get' })
}
export function createSalesReconciliation(data) {
  return request({ url: '/finance/sales-reconciliations/', method: 'post', data })
}
export function updateSalesReconciliation(id, data) {
  return request({ url: `/finance/sales-reconciliations/${id}/`, method: 'put', data })
}
export function deleteSalesReconciliation(id) {
  return request({ url: `/finance/sales-reconciliations/${id}/`, method: 'delete' })
}
export function generateSalesReconciliationLines(id) {
  return request({ url: `/finance/sales-reconciliations/${id}/generate_lines/`, method: 'post' })
}
export function submitSalesReconciliation(id) {
  return request({ url: `/finance/sales-reconciliations/${id}/submit/`, method: 'post' })
}
export function confirmSalesReconciliation(id) {
  return request({ url: `/finance/sales-reconciliations/${id}/confirm/`, method: 'post' })
}
export function getCustomerReconciliationSummary(params) {
  return request({ url: '/finance/sales-reconciliations/customer_summary/', method: 'get', params })
}

// ========== 项目成本 ==========
export function getProjectCostList(params) {
  return request({ url: '/projects/project-cost-records/', method: 'get', params })
}
export function getProjectCostRecord(id) {
  return request({ url: `/projects/project-cost-records/${id}/`, method: 'get' })
}
export function createProjectCostRecord(data) {
  return request({ url: '/projects/project-cost-records/', method: 'post', data })
}
export function verifyProjectCostRecord(id) {
  return request({ url: `/projects/project-cost-records/${id}/verify/`, method: 'post' })
}

// ========== 应收账款 ==========
export function getReceivables(params) {
  return request({ url: '/finance/receivables/', method: 'get', params })
}

// ========== 应付账款 ==========
export function getPayables(params) {
  return request({ url: '/finance/payables/', method: 'get', params })
}

// ========== 发票管理 ==========
export function getInvoices(params) {
  return request({ url: '/finance/invoices/', method: 'get', params })
}
export function autoMatchInvoices(data) {
  return request({ url: '/finance/invoices/auto_match/', method: 'post', data })
}
export function matchInvoiceOrder(id, data) {
  return request({ url: `/finance/invoices/${id}/match_order/`, method: 'post', data })
}
export function downloadInvoiceTemplate() {
  return request({ url: '/finance/invoices/download_template/', method: 'get', responseType: 'blob' })
}
export function exportInvoices(params, config = {}) {
  return request({ url: '/finance/invoices/export/', method: 'get', params, ...config })
}
export function bulkDeleteInvoices(data) {
  return request({ url: '/finance/invoices/bulk_delete/', method: 'post', data })
}
export function getInvoiceAttachments(id) {
  return request({ url: `/finance/invoices/${id}/attachments/`, method: 'get' })
}

// ========== 费用管理 (扩展) ==========
export function getExpenses(params) {
  return request({ url: '/finance/expenses/', method: 'get', params })
}
export function submitExpense(id) {
  return request({ url: `/finance/expenses/${id}/submit/`, method: 'post' })
}
export function approveExpense(id, data) {
  return request({ url: `/finance/expenses/${id}/approve/`, method: 'post', data })
}
export function rejectExpense(id, data) {
  return request({ url: `/finance/expenses/${id}/reject/`, method: 'post', data })
}

// ========== 共享费用 ==========
export function getSharedExpenses(params) {
  return request({ url: '/finance/shared-expenses/', method: 'get', params })
}
export function patchSharedExpense(id, data) {
  return request({ url: `/finance/shared-expenses/${id}/`, method: 'patch', data })
}
export function calculateSharedExpenseAllocation(id) {
  return request({ url: `/finance/shared-expenses/${id}/calculate/`, method: 'post' })
}
export function cancelSharedExpenseAllocation(id) {
  return request({ url: `/finance/shared-expenses/${id}/cancel_allocation/`, method: 'post' })
}

// ========== 采购对账 ==========
export function getPurchaseReconciliations(params) {
  return request({ url: '/finance/purchase-reconciliations/', method: 'get', params })
}
export function getPurchaseReconciliationOpeningBalance(params) {
  return request({ url: '/finance/purchase-reconciliations/get_opening_balance/', method: 'get', params })
}
export function getPurchaseReconciliationSupplierSummary(params) {
  return request({ url: '/finance/purchase-reconciliations/supplier_summary/', method: 'get', params })
}
export function confirmPurchaseReconciliationReceipt(id, lineId) {
  return request({ url: `/finance/purchase-reconciliations/${id}/confirm_receipt/${lineId}/`, method: 'post' })
}

// ========== 销售对账 ==========
export function getSalesReconciliations(params) {
  return request({ url: '/finance/sales-reconciliations/', method: 'get', params })
}
export function getSalesReconciliationOpeningBalance(params) {
  return request({ url: '/finance/sales-reconciliations/get_opening_balance/', method: 'get', params })
}
export function getSalesReconciliationCustomerSummary(params) {
  return request({ url: '/finance/sales-reconciliations/customer_summary/', method: 'get', params })
}
export function confirmSalesReconciliationDelivery(id, lineId) {
  return request({ url: `/finance/sales-reconciliations/${id}/confirm_delivery/${lineId}/`, method: 'post' })
}

// ========== 发票对账 ==========
export function getInvoiceReconciliations(params) {
  return request({ url: '/finance/invoice-reconciliations/', method: 'get', params })
}
export function getInvoiceReconciliation(id) {
  return request({ url: `/finance/invoice-reconciliations/${id}/`, method: 'get' })
}
export function createInvoiceReconciliation(data) {
  return request({ url: '/finance/invoice-reconciliations/', method: 'post', data })
}
export function confirmInvoiceReconciliation(id) {
  return request({ url: `/finance/invoice-reconciliations/${id}/confirm/`, method: 'post' })
}
export function generateInvoiceReconciliationLines(id) {
  return request({ url: `/finance/invoice-reconciliations/${id}/generate_lines/`, method: 'post' })
}

// ========== 银行流水 ==========
export function getBankStatements(params) {
  return request({ url: '/finance/bank-statements/', method: 'get', params })
}
export function matchBankStatement(id, data) {
  return request({ url: `/finance/bank-statements/${id}/match/`, method: 'post', data })
}
export function ignoreBankStatement(id) {
  return request({ url: `/finance/bank-statements/${id}/ignore/`, method: 'post' })
}
export function autoMatchAllBankStatements(data) {
  return request({ url: '/finance/bank-statements/auto_match_all/', method: 'post', data })
}
export function bulkDeleteBankStatements(data) {
  return request({ url: '/finance/bank-statements/bulk_delete/', method: 'post', data })
}

// ========== 固定资产 ==========
export function getFixedAssets(params) {
  return request({ url: '/finance/fixed-assets/', method: 'get', params })
}
export function patchFixedAsset(id, data) {
  return request({ url: `/finance/fixed-assets/${id}/`, method: 'patch', data })
}
export function transferFixedAsset(id, data) {
  return request({ url: `/finance/fixed-assets/${id}/transfer/`, method: 'post', data })
}
export function disposeFixedAsset(id, data) {
  return request({ url: `/finance/fixed-assets/${id}/dispose/`, method: 'post', data })
}
export function scrapFixedAsset(id, data) {
  return request({ url: `/finance/fixed-assets/${id}/dispose/`, method: 'post', data: { ...data, disposal_type: 'scrap' } })
}
export function activateFixedAsset(id) {
  return request({ url: `/finance/fixed-assets/${id}/`, method: 'patch', data: { status: 'active' } })
}
export function depreciateFixedAssets(data) {
  return request({ url: '/finance/fixed-assets/run_depreciation/', method: 'post', data })
}
export function getFixedAssetStatistics() {
  return request({ url: '/finance/fixed-assets/statistics/', method: 'get' })
}
export function inventoryFixedAssets(data) {
  return request({ url: '/finance/fixed-assets/asset_inventory/', method: 'post', data })
}
export function getAssetCategories(params) {
  return request({ url: '/finance/asset-categories/', method: 'get', params })
}
