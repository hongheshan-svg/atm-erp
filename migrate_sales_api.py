#!/usr/bin/env python3
"""Migrate 20 sales Vue files from raw request to API wrappers."""
import os

BASE = '/home/administrator/erp/frontend/src'
VIEWS = f'{BASE}/views/sales'

# ============================================================
# Step 1: Create frontend/src/api/sales.js
# ============================================================
SALES_API = r"""import request from '@/utils/request'

// ========== 报价单 Quotations ==========
export function getQuotations(params) {
  return request.get('/sales/quotations/', { params })
}
export function getQuotation(id) {
  return request.get(`/sales/quotations/${id}/`)
}
export function createQuotation(data) {
  return request.post('/sales/quotations/', data)
}
export function updateQuotation(id, data) {
  return request.put(`/sales/quotations/${id}/`, data)
}
export function submitQuotation(id) {
  return request.post(`/sales/quotations/${id}/submit/`)
}
export function createNewQuotationVersion(id) {
  return request.post(`/sales/quotations/${id}/create_new_version/`)
}
export function convertQuotationToOrder(id) {
  return request.post(`/sales/quotations/${id}/convert_to_order/`)
}

// ========== 销售订单 Orders ==========
export function getSalesOrders(params) {
  return request.get('/sales/orders/', { params })
}
export function getSalesOrder(id) {
  return request.get(`/sales/orders/${id}/`)
}
export function createSalesOrder(data) {
  return request.post('/sales/orders/', data)
}
export function updateSalesOrder(id, data) {
  return request.put(`/sales/orders/${id}/`, data)
}
export function deleteSalesOrder(id) {
  return request.delete(`/sales/orders/${id}/`)
}
export function submitSalesOrder(id) {
  return request.post(`/sales/orders/${id}/submit/`)
}
export function confirmSalesOrder(id) {
  return request.post(`/sales/orders/${id}/confirm/`)
}
export function cancelSalesOrder(id) {
  return request.post(`/sales/orders/${id}/cancel/`)
}
export function returnOrderToDraft(id) {
  return request.post(`/sales/orders/${id}/return_to_draft/`)
}
export function getOrdersForLinking(params) {
  return request.get('/sales/orders/for_linking/', { params })
}
export function downloadOrderTemplate(config) {
  return request.get('/sales/orders/download-template/', config)
}
export function importSalesOrders(data, config) {
  return request.post('/sales/orders/import/', data, config)
}
export function exportSalesOrders(config) {
  return request.get('/sales/orders/export/', config)
}
export function bulkDeleteOrders(data) {
  return request.post('/sales/orders/bulk-delete/', data)
}

// ========== 发货单 Deliveries ==========
export function getDeliveryOrders(params) {
  return request.get('/sales/deliveries/', { params })
}
export function getDeliveryOrder(id) {
  return request.get(`/sales/deliveries/${id}/`)
}
export function createDeliveryOrder(data) {
  return request.post('/sales/deliveries/', data)
}
export function submitDeliveryOrder(id) {
  return request.post(`/sales/deliveries/${id}/submit/`)
}
export function confirmPreparedDelivery(id) {
  return request.post(`/sales/deliveries/${id}/confirm_prepared/`)
}
export function confirmLogisticsDelivery(id, data) {
  return request.post(`/sales/deliveries/${id}/confirm_logistics/`, data)
}
export function confirmSignedDelivery(id, data) {
  return request.post(`/sales/deliveries/${id}/confirm_signed/`, data)
}
export function uploadDeliveryReceipt(id, data, config) {
  return request.post(`/sales/deliveries/${id}/upload_receipt/`, data, config)
}
export function projectConfirmDelivery(id) {
  return request.post(`/sales/deliveries/${id}/project_confirm/`)
}
export function rejectDelivery(id, data) {
  return request.post(`/sales/deliveries/${id}/reject/`, data)
}

// ========== 销售合同 Contracts ==========
export function getContracts(params) {
  return request.get('/sales/contracts/', { params })
}
export function getContract(id) {
  return request.get(`/sales/contracts/${id}/`)
}
export function patchContract(id, data) {
  return request.patch(`/sales/contracts/${id}/`, data)
}
export function createContractFromSO(data) {
  return request.post('/sales/contracts/create_from_so/', data)
}
export function submitContract(id) {
  return request.post(`/sales/contracts/${id}/submit/`)
}
export function approveContract(id) {
  return request.post(`/sales/contracts/${id}/approve/`)
}
export function signContract(id, data) {
  return request.post(`/sales/contracts/${id}/sign/`, data)
}
export function printPreviewContract(id) {
  return request.get(`/sales/contracts/${id}/print_preview/`)
}

// ========== 合同模板 Contract Templates ==========
export function getContractTemplates() {
  return request.get('/sales/contract-templates/')
}
export function createContractTemplate(data) {
  return request.post('/sales/contract-templates/', data)
}
export function updateContractTemplate(id, data) {
  return request.put(`/sales/contract-templates/${id}/`, data)
}
export function deleteContractTemplate(id) {
  return request.delete(`/sales/contract-templates/${id}/`)
}
export function previewContractTemplate(id) {
  return request.post(`/sales/contract-templates/${id}/preview/`)
}
export function setDefaultContractTemplate(id) {
  return request.post(`/sales/contract-templates/${id}/set_default/`)
}
export function getContractTypes() {
  return request.get('/sales/contract-templates/contract_types/')
}
export function generateContract(data) {
  return request.post('/sales/contract-templates/generate/', data)
}

// ========== 合同条款 Contract Clauses ==========
export function getContractClauses() {
  return request.get('/sales/contract-clauses/')
}
export function createContractClause(data) {
  return request.post('/sales/contract-clauses/', data)
}
export function updateContractClause(id, data) {
  return request.put(`/sales/contract-clauses/${id}/`, data)
}
export function deleteContractClause(id) {
  return request.delete(`/sales/contract-clauses/${id}/`)
}

// ========== 生成的合同 Generated Contracts ==========
export function getGeneratedContracts() {
  return request.get('/sales/generated-contracts/')
}
export function getGeneratedContract(id) {
  return request.get(`/sales/generated-contracts/${id}/`)
}

// ========== CRM 仪表盘 ==========
export function getCRMDashboardStats() {
  return request.get('/sales/crm-dashboard/stats/')
}

// ========== 销售分析 Analysis ==========
export function getSalesStages() {
  return request.get('/sales/analysis/stages/')
}
export function getSalesRanking(params) {
  return request.get('/sales/analysis/ranking/', { params })
}
export function getSalesFunnel(params) {
  return request.get('/sales/analysis/funnel/', { params })
}
export function getSalesTrend(params) {
  return request.get('/sales/analysis/trend/', { params })
}

// ========== 客户RFM分析 ==========
export function getRFMSegmentSummary() {
  return request.get('/sales/customer-rfm/segment_summary/')
}
export function getRFMTopCustomers() {
  return request.get('/sales/customer-rfm/top_customers/')
}
export function analyzeRFM() {
  return request.post('/sales/customer-rfm/analyze/')
}

// ========== 知识库 Knowledge Base ==========
export function getKnowledgeArticles(params) {
  return request.get('/sales/knowledge-base/', { params })
}
export function getKnowledgeArticle(id) {
  return request.get(`/sales/knowledge-base/${id}/`)
}
export function createKnowledgeArticle(data) {
  return request.post('/sales/knowledge-base/', data)
}
export function getPopularArticles() {
  return request.get('/sales/knowledge-base/popular/')
}
export function getKnowledgeTags() {
  return request.get('/sales/knowledge-base/tags/')
}
export function viewKnowledgeArticle(id) {
  return request.post(`/sales/knowledge-base/${id}/view/`)
}
export function feedbackKnowledgeArticle(id, data) {
  return request.post(`/sales/knowledge-base/${id}/feedback/`, data)
}

// ========== 服务合同 Service Contracts ==========
export function getServiceContracts(params) {
  return request.get('/sales/service-contracts/', { params })
}
export function getServiceContract(id) {
  return request.get(`/sales/service-contracts/${id}/`)
}
export function createServiceContract(data) {
  return request.post('/sales/service-contracts/', data)
}
export function activateServiceContract(id) {
  return request.post(`/sales/service-contracts/${id}/activate/`)
}
export function getServiceContractHistory(id) {
  return request.get(`/sales/service-contracts/${id}/service_history/`)
}
export function getExpiringServiceContracts(params) {
  return request.get('/sales/service-contracts/expiring_soon/', { params })
}

// ========== 服务请求 Service Requests ==========
export function getServiceRequests(params) {
  return request.get('/sales/service-requests/', { params })
}
export function getServiceRequest(id) {
  return request.get(`/sales/service-requests/${id}/`)
}
export function createServiceRequest(data) {
  return request.post('/sales/service-requests/', data)
}
export function assignServiceRequest(id, data) {
  return request.post(`/sales/service-requests/${id}/assign/`, data)
}
export function completeServiceRequest(id, data) {
  return request.post(`/sales/service-requests/${id}/complete/`, data)
}

// ========== 预防性维护 Preventive Maintenance ==========
export function getPreventiveMaintenanceList(params) {
  return request.get('/sales/preventive-maintenance/', { params })
}
export function getPreventiveMaintenance(id) {
  return request.get(`/sales/preventive-maintenance/${id}/`)
}
export function createPreventiveMaintenance(data) {
  return request.post('/sales/preventive-maintenance/', data)
}
export function startPreventiveMaintenance(id) {
  return request.post(`/sales/preventive-maintenance/${id}/start/`)
}
export function completePreventiveMaintenance(id, data) {
  return request.post(`/sales/preventive-maintenance/${id}/complete/`, data)
}
export function getUpcomingMaintenance(params) {
  return request.get('/sales/preventive-maintenance/upcoming/', { params })
}
export function getOverdueMaintenance() {
  return request.get('/sales/preventive-maintenance/overdue/')
}

// ========== 培训课程 Training Courses ==========
export function getTrainingCourses(params) {
  return request.get('/sales/training-courses/', { params })
}
export function createTrainingCourse(data) {
  return request.post('/sales/training-courses/', data)
}
export function updateTrainingCourse(id, data) {
  return request.put(`/sales/training-courses/${id}/`, data)
}

// ========== 培训计划 Training Plans ==========
export function getTrainingPlans(params) {
  return request.get('/sales/training-plans/', { params })
}
export function getTrainingPlan(id) {
  return request.get(`/sales/training-plans/${id}/`)
}
export function createTrainingPlan(data) {
  return request.post('/sales/training-plans/', data)
}
export function updateTrainingPlan(id, data) {
  return request.put(`/sales/training-plans/${id}/`, data)
}

// ========== 绩效分析 Performance ==========
export function getMyPerformance(params) {
  return request.get('/sales/performance/my_performance/', { params })
}
export function getTeamRanking(params) {
  return request.get('/sales/performance/team_ranking/', { params })
}
export function getMonthlyTrend(params) {
  return request.get('/sales/performance/monthly_trend/', { params })
}
export function getCustomerAnalysis(params) {
  return request.get('/sales/performance/customer_analysis/', { params })
}
export function getPipelineAnalysis(params) {
  return request.get('/sales/performance/pipeline_analysis/', { params })
}
export function getMyTargets() {
  return request.get('/sales/targets/my_targets/')
}
export function getMyCommissions() {
  return request.get('/sales/commissions/my_commissions/')
}
export function refreshTarget(id) {
  return request.post(`/sales/targets/${id}/refresh/`)
}

// ========== 报价估算 Quote Estimations ==========
export function getQuoteEstimations(params) {
  return request.get('/sales/quote-estimations/', { params })
}
export function getQuoteEstimation(id) {
  return request.get(`/sales/quote-estimations/${id}/`)
}
export function createQuoteEstimation(data) {
  return request.post('/sales/quote-estimations/', data)
}
export function patchQuoteEstimation(id, data) {
  return request.patch(`/sales/quote-estimations/${id}/`, data)
}
export function calculateQuoteEstimation(id) {
  return request.post(`/sales/quote-estimations/${id}/calculate/`)
}
export function submitQuoteEstimation(id) {
  return request.post(`/sales/quote-estimations/${id}/submit/`)
}
export function submitQuoteEstimationReview(id) {
  return request.post(`/sales/quote-estimations/${id}/submit_review/`)
}
export function approveQuoteEstimation(id) {
  return request.post(`/sales/quote-estimations/${id}/approve/`)
}
export function createQuotationFromEstimation(id) {
  return request.post(`/sales/quote-estimations/${id}/create_quotation/`)
}

// ========== 报价模板 Quote Templates ==========
export function getQuoteTemplates() {
  return request.get('/sales/quote-templates/')
}
export function createQuoteTemplate(data) {
  return request.post('/sales/quote-templates/', data)
}
export function updateQuoteTemplate(id, data) {
  return request.put(`/sales/quote-templates/${id}/`, data)
}
export function setDefaultQuoteTemplate(id) {
  return request.post(`/sales/quote-templates/${id}/set_default/`)
}
export function generateQuote(data) {
  return request.post('/sales/quote-templates/generate/', data)
}

// ========== 报价版本 Quote Versions ==========
export function getQuoteVersions(params) {
  return request.get('/sales/quote-versions/', { params })
}
export function getQuoteVersion(id) {
  return request.get(`/sales/quote-versions/${id}/`)
}
export function createQuoteVersion(data) {
  return request.post('/sales/quote-versions/', data)
}
export function createNewQuoteVersion(id) {
  return request.post(`/sales/quote-versions/${id}/create_new_version/`)
}
export function getQuoteVersionProfitPrediction(id) {
  return request.get(`/sales/quote-versions/${id}/profit_prediction/`)
}
export function estimateFromReference(id, data) {
  return request.post(`/sales/quote-versions/${id}/estimate_from_reference/`, data)
}
export function findSimilarQuotes(data) {
  return request.post('/sales/quote-versions/find_similar/', data)
}
"""

api_path = os.path.join(BASE, 'api', 'sales.js')
with open(api_path, 'w') as f:
    f.write(SALES_API)
print(f"Created {api_path}")
print(f"  → {len(SALES_API.splitlines())} lines")
