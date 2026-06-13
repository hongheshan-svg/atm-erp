import request from '@/utils/request'

// ==================== 采购申请 ====================

export function getPurchaseRequests(params?: Record<string, any>) {
  return request({ url: '/purchase/requests/', method: 'get', params })
}

export function getPurchaseRequest(id: number) {
  return request({ url: `/purchase/requests/${id}/`, method: 'get' })
}

export function createPurchaseRequest(data: any) {
  return request({ url: '/purchase/requests/', method: 'post', data })
}

export function updatePurchaseRequest(id: number, data: any) {
  return request({ url: `/purchase/requests/${id}/`, method: 'put', data })
}

export function submitPurchaseRequest(id: number) {
  return request({ url: `/purchase/requests/${id}/submit/`, method: 'post' })
}

export function approvePurchaseRequest(id: number, data: any) {
  return request({ url: `/purchase/requests/${id}/approve/`, method: 'post', data })
}

export function rejectPurchaseRequest(id: number, data: any) {
  return request({ url: `/purchase/requests/${id}/reject/`, method: 'post', data })
}

export function withdrawPurchaseRequest(id: number) {
  return request({ url: `/purchase/requests/${id}/withdraw/`, method: 'post' })
}

export function convertRequestToPO(id: number, data: any) {
  return request({ url: `/purchase/requests/${id}/convert_to_po/`, method: 'post', data })
}

export function importPurchaseRequests(data: any) {
  return request({ url: '/purchase/requests/import_data/', method: 'post', data })
}

export function exportPurchaseRequestTemplate() {
  return request({ url: '/purchase/requests/export_template/', method: 'get', responseType: 'blob' })
}

// ==================== 采购订单 ====================

export function getPurchaseOrders(params?: Record<string, any>) {
  return request({ url: '/purchase/orders/', method: 'get', params })
}

export function getPurchaseOrder(id: number) {
  return request({ url: `/purchase/orders/${id}/`, method: 'get' })
}

export function createPurchaseOrder(data: any) {
  return request({ url: '/purchase/orders/', method: 'post', data })
}

export function updatePurchaseOrder(id: number, data: any) {
  return request({ url: `/purchase/orders/${id}/`, method: 'put', data })
}

export function deletePurchaseOrder(id: number) {
  return request({ url: `/purchase/orders/${id}/`, method: 'delete' })
}

export function submitPurchaseOrder(id: number) {
  return request({ url: `/purchase/orders/${id}/submit/`, method: 'post' })
}

export function confirmPurchaseOrder(id: number) {
  return request({ url: `/purchase/orders/${id}/confirm/`, method: 'post' })
}

export function cancelPurchaseOrder(id: number) {
  return request({ url: `/purchase/orders/${id}/cancel/`, method: 'post' })
}

export function withdrawPurchaseOrder(id: number) {
  return request({ url: `/purchase/orders/${id}/withdraw/`, method: 'post' })
}

export function createContractFromPO(id: number) {
  return request({ url: `/purchase/orders/${id}/create_contract/`, method: 'post' })
}

export function printPreviewContract(id: number) {
  return request({ url: `/purchase/orders/${id}/print_preview/`, method: 'get' })
}

// ==================== 收货 ====================

export function getGoodsReceipts(params?: Record<string, any>) {
  return request({ url: '/purchase/receipts/', method: 'get', params })
}

export function getGoodsReceipt(id: number) {
  return request({ url: `/purchase/receipts/${id}/`, method: 'get' })
}

export function createGoodsReceipt(data: any) {
  return request({ url: '/purchase/receipts/', method: 'post', data })
}

export function updateGoodsReceipt(id: number, data: any) {
  return request({ url: `/purchase/receipts/${id}/`, method: 'put', data })
}

export function confirmGoodsReceipt(id: number) {
  return request({ url: `/purchase/receipts/${id}/confirm/`, method: 'post' })
}

// ==================== 采购合同 ====================

export function getPurchaseContracts(params?: Record<string, any>) {
  return request({ url: '/purchase/contracts/', method: 'get', params })
}

// ==================== RFQ询价 ====================

export function getRFQs(params?: Record<string, any>) {
  return request({ url: '/purchase/rfqs/', method: 'get', params })
}

export function getRFQ(id: number) {
  return request({ url: `/purchase/rfqs/${id}/`, method: 'get' })
}

export function createRFQ(data: any) {
  return request({ url: '/purchase/rfqs/', method: 'post', data })
}

export function createRFQFromBOM(data: any) {
  return request({ url: '/purchase/rfqs/create_from_bom/', method: 'post', data })
}

export function createRFQFromTemplate(data: any) {
  return request({ url: '/purchase/rfqs/create_from_template/', method: 'post', data })
}

export function sendRFQToSuppliers(id: number, data: any) {
  return request({ url: `/purchase/rfqs/${id}/send_to_suppliers/`, method: 'post', data })
}

export function matchRFQSuppliers(id: number) {
  return request({ url: `/purchase/rfqs/${id}/match_suppliers/`, method: 'post' })
}

export function createRFQLine(data: any) {
  return request({ url: '/purchase/rfq-lines/', method: 'post', data })
}

export function getRFQTemplates(params?: Record<string, any>) {
  return request({ url: '/purchase/rfq-templates/', method: 'get', params })
}

// ==================== 比价 ====================

export function getComparisons(params?: Record<string, any>) {
  return request({ url: '/purchase/comparisons/', method: 'get', params })
}

export function getComparison(id: number) {
  return request({ url: `/purchase/comparisons/${id}/`, method: 'get' })
}

export function getComparisonReport(id: number) {
  return request({ url: `/purchase/comparisons/${id}/report/`, method: 'get' })
}

export function createComparisonFromRFQ(data: any) {
  return request({ url: '/purchase/comparisons/create_comparison/', method: 'post', data })
}

export function getAvailableRFQsForComparison() {
  return request({ url: '/purchase/comparisons/available_rfqs/', method: 'get' })
}

export function approveComparison(id: number, data: any) {
  return request({ url: `/purchase/comparisons/${id}/approve/`, method: 'post', data })
}

export function completeComparison(id: number) {
  return request({ url: `/purchase/comparisons/${id}/complete/`, method: 'post' })
}

export function convertComparisonToPO(id: number, data: any) {
  return request({ url: `/purchase/comparisons/${id}/convert_to_po/`, method: 'post', data })
}

export function updateComparisonWeights(id: number, data: any) {
  return request({ url: `/purchase/comparisons/${id}/update_weights/`, method: 'post', data })
}

export function updateComparisonScore(id: number, data: any) {
  return request({ url: `/purchase/comparisons/${id}/update_score/`, method: 'post', data })
}

export function autoScoreComparison(id: number) {
  return request({ url: `/purchase/comparisons/${id}/auto_score/`, method: 'post' })
}

export function applyComparisonTemplate(id: number, data: any) {
  return request({ url: `/purchase/comparisons/${id}/apply_template/`, method: 'post', data })
}

export function batchDeleteComparisons(data: any) {
  return request({ url: '/purchase/comparisons/batch_delete/', method: 'post', data })
}

// ==================== 采购预算 ====================

export function getPurchaseBudgets(params?: Record<string, any>) {
  return request({ url: '/purchase/budgets/', method: 'get', params })
}

export function getPurchaseBudget(id: number) {
  return request({ url: `/purchase/budgets/${id}/`, method: 'get' })
}

export function createPurchaseBudget(data: any) {
  return request({ url: '/purchase/budgets/', method: 'post', data })
}

export function updatePurchaseBudget(id: number, data: any) {
  return request({ url: `/purchase/budgets/${id}/`, method: 'put', data })
}

export function deletePurchaseBudget(id: number) {
  return request({ url: `/purchase/budgets/${id}/`, method: 'delete' })
}

export function approvePurchaseBudget(id: number) {
  return request({ url: `/purchase/budgets/${id}/approve/`, method: 'post' })
}

export function activatePurchaseBudget(id: number) {
  return request({ url: `/purchase/budgets/${id}/activate/`, method: 'post' })
}

export function getPurchaseBudgetStatistics() {
  return request({ url: '/purchase/budgets/statistics/', method: 'get' })
}

export function getPurchaseBudgetUsageRecords(id: number) {
  return request({ url: `/purchase/budgets/${id}/usage_records/`, method: 'get' })
}

// ==================== 委外订单 ====================

export function getOutsourceOrders(params?: Record<string, any>) {
  return request({ url: '/purchase/outsource-orders/', method: 'get', params })
}

export function getOutsourceOrder(id: number) {
  return request({ url: `/purchase/outsource-orders/${id}/`, method: 'get' })
}

export function createOutsourceOrder(data: any) {
  return request({ url: '/purchase/outsource-orders/', method: 'post', data })
}

export function updateOutsourceOrder(id: number, data: any) {
  return request({ url: `/purchase/outsource-orders/${id}/`, method: 'put', data })
}

export function confirmOutsourceOrder(id: number) {
  return request({ url: `/purchase/outsource-orders/${id}/confirm/`, method: 'post' })
}

export function cancelOutsourceOrder(id: number) {
  return request({ url: `/purchase/outsource-orders/${id}/cancel/`, method: 'post' })
}

// ==================== 委外发料与收货 = ===================

export function createOutsourceIssue(data) {
  return request({ url: '/purchase/outsource-issues/', method: 'post', data })
}

export function confirmOutsourceIssue(id: number) {
  return request({ url: `/purchase/outsource-issues/${id}/confirm/`, method: 'post' })
}

export function createOutsourceReceipt(data: any) {
  return request({ url: '/purchase/outsource-receipts/', method: 'post', data })
}

export function confirmOutsourceReceipt(id: number) {
  return request({ url: `/purchase/outsource-receipts/${id}/confirm/`, method: 'post' })
}

// ==================== 委外能力与进度 ====================

export function getOutsourceCapabilities(params?: Record<string, any>) {
  return request({ url: '/purchase/outsource-capabilities/', method: 'get', params })
}

export function createOutsourceCapability(data: any) {
  return request({ url: '/purchase/outsource-capabilities/', method: 'post', data })
}

export function updateOutsourceCapability(id: number, data: any) {
  return request({ url: `/purchase/outsource-capabilities/${id}/`, method: 'put', data })
}

export function deleteOutsourceCapability(id: number) {
  return request({ url: `/purchase/outsource-capabilities/${id}/`, method: 'delete' })
}

export function getOutsourceProgress(params?: Record<string, any>) {
  return request({ url: '/purchase/outsource-progress/', method: 'get', params })
}

export function getOutsourceProgressStatistics() {
  return request({ url: '/purchase/outsource-progress/statistics/', method: 'get' })
}

export function updateOutsourceProgress(id: number, data: any) {
  return request({ url: `/purchase/outsource-progress/${id}/`, method: 'patch', data })
}

// ==================== 供应链协同 ====================

export function getRFQCollaborations(params?: Record<string, any>) {
  return request({ url: '/purchase/rfq-collaborations/', method: 'get', params })
}

export function getRFQCollaboration(id: number) {
  return request({ url: `/purchase/rfq-collaborations/${id}/`, method: 'get' })
}

export function createRFQCollaboration(data: any) {
  return request({ url: '/purchase/rfq-collaborations/', method: 'post', data })
}

export function compareRFQCollaboration(id: number) {
  return request({ url: `/purchase/rfq-collaborations/${id}/compare/`, method: 'post' })
}

export function selectRFQCollaborationSupplier(id: number, data: any) {
  return request({ url: `/purchase/rfq-collaborations/${id}/select_supplier/`, method: 'post', data })
}

export function getDeliveryCollaborations(params?: Record<string, any>) {
  return request({ url: '/purchase/delivery-collaborations/', method: 'get', params })
}

export function getDeliveryCollaboration(id: number) {
  return request({ url: `/purchase/delivery-collaborations/${id}/`, method: 'get' })
}

export function confirmDeliveryCollaboration(id: number) {
  return request({ url: `/purchase/delivery-collaborations/${id}/confirm/`, method: 'post' })
}

// ==================== 供应商门户 ====================

export function getSupplierAccounts(params?: Record<string, any>) {
  return request({ url: '/purchase/supplier-accounts/', method: 'get', params })
}

export function createSupplierAccount(data: any) {
  return request({ url: '/purchase/supplier-accounts/', method: 'post', data })
}

export function resetSupplierAccountPassword(id: number) {
  return request({ url: `/purchase/supplier-accounts/${id}/reset_password/`, method: 'post' })
}

export function toggleSupplierAccountActive(id: number) {
  return request({ url: `/purchase/supplier-accounts/${id}/toggle_active/`, method: 'post' })
}

export function getSupplierOrderViews(params?: Record<string, any>) {
  return request({ url: '/purchase/supplier-order-views/', method: 'get', params })
}

export function getSupplierPortalDashboard() {
  return request({ url: '/purchase/supplier-portal/dashboard/', method: 'get' })
}
