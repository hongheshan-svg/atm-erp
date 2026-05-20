import request from '@/utils/request'

// ========== 报价单 ==========
export function getQuotations(params) {
  return request({ url: '/sales/quotations/', method: 'get', params })
}
export function getQuotation(id) {
  return request({ url: `/sales/quotations/${id}/`, method: 'get' })
}
export function createQuotation(data) {
  return request({ url: '/sales/quotations/', method: 'post', data })
}
export function updateQuotation(id, data) {
  return request({ url: `/sales/quotations/${id}/`, method: 'put', data })
}
export function submitQuotation(id) {
  return request({ url: `/sales/quotations/${id}/submit/`, method: 'post' })
}
export function createQuotationNewVersion(id) {
  return request({ url: `/sales/quotations/${id}/create_new_version/`, method: 'post' })
}
export function convertQuotationToOrder(id) {
  return request({ url: `/sales/quotations/${id}/convert_to_order/`, method: 'post' })
}

// ========== 销售订单 ==========
export function getOrders(params) {
  return request({ url: '/sales/orders/', method: 'get', params })
}
export function getOrder(id) {
  return request({ url: `/sales/orders/${id}/`, method: 'get' })
}
export function createOrder(data) {
  return request({ url: '/sales/orders/', method: 'post', data })
}
export function updateOrder(id, data) {
  return request({ url: `/sales/orders/${id}/`, method: 'put', data })
}
export function deleteOrder(id) {
  return request({ url: `/sales/orders/${id}/`, method: 'delete' })
}
export function submitOrder(id) {
  return request({ url: `/sales/orders/${id}/submit/`, method: 'post' })
}
export function confirmOrder(id) {
  return request({ url: `/sales/orders/${id}/confirm/`, method: 'post' })
}
export function cancelOrder(id) {
  return request({ url: `/sales/orders/${id}/cancel/`, method: 'post' })
}
export function returnOrderToDraft(id) {
  return request({ url: `/sales/orders/${id}/return_to_draft/`, method: 'post' })
}
export function downloadOrderTemplate() {
  return request({ url: '/sales/orders/download_template/', method: 'get', responseType: 'blob' })
}
export function importOrders(data) {
  return request({ url: '/sales/orders/import/', method: 'post', data })
}
export function exportOrders(params) {
  return request({ url: '/sales/orders/export/', method: 'get', params, responseType: 'blob' })
}
export function bulkDeleteOrders(ids) {
  return request({ url: '/sales/orders/bulk_delete/', method: 'post', data: { ids } })
}
export function getOrdersForLinking(params) {
  return request({ url: '/sales/orders/for_linking/', method: 'get', params })
}

// ========== 发货单 ==========
export function getDeliveryOrders(params) {
  return request({ url: '/sales/deliveries/', method: 'get', params })
}
export function getDeliveryOrder(id) {
  return request({ url: `/sales/deliveries/${id}/`, method: 'get' })
}
export function createDeliveryOrder(data) {
  return request({ url: '/sales/deliveries/', method: 'post', data })
}
export function submitDeliveryOrder(id) {
  return request({ url: `/sales/deliveries/${id}/submit/`, method: 'post' })
}
export function confirmDeliveryPrepared(id) {
  return request({ url: `/sales/deliveries/${id}/confirm_prepared/`, method: 'post' })
}
export function confirmDeliveryLogistics(id, data) {
  return request({ url: `/sales/deliveries/${id}/confirm_logistics/`, method: 'post', data })
}
export function confirmDeliverySigned(id, data) {
  return request({ url: `/sales/deliveries/${id}/confirm_signed/`, method: 'post', data })
}
export function uploadDeliveryReceipt(id, data) {
  return request({ url: `/sales/deliveries/${id}/upload_receipt/`, method: 'post', data })
}
export function projectConfirmDelivery(id) {
  return request({ url: `/sales/deliveries/${id}/project_confirm/`, method: 'post' })
}
export function rejectDelivery(id, data) {
  return request({ url: `/sales/deliveries/${id}/reject/`, method: 'post', data })
}

// ========== 合同 ==========
export function getContracts(params) {
  return request({ url: '/sales/contracts/', method: 'get', params })
}
export function getContract(id) {
  return request({ url: `/sales/contracts/${id}/`, method: 'get' })
}
export function createContractFromSO(data) {
  return request({ url: '/sales/contracts/create_from_so/', method: 'post', data })
}
export function updateContract(id, data) {
  return request({ url: `/sales/contracts/${id}/`, method: 'patch', data })
}
export function submitContract(id) {
  return request({ url: `/sales/contracts/${id}/submit/`, method: 'post' })
}
export function approveContract(id) {
  return request({ url: `/sales/contracts/${id}/approve/`, method: 'post' })
}
export function signContract(id, data) {
  return request({ url: `/sales/contracts/${id}/sign/`, method: 'post', data })
}
export function printPreviewContract(id) {
  return request({ url: `/sales/contracts/${id}/print_preview/`, method: 'get' })
}

// ========== 合同模板 ==========
export function getContractTemplates(params) {
  return request({ url: '/sales/contract-templates/', method: 'get', params })
}
export function getContractTypes() {
  return request({ url: '/sales/contract-templates/contract_types/', method: 'get' })
}
export function createContractTemplate(data) {
  return request({ url: '/sales/contract-templates/', method: 'post', data })
}
export function updateContractTemplate(id, data) {
  return request({ url: `/sales/contract-templates/${id}/`, method: 'put', data })
}
export function deleteContractTemplate(id) {
  return request({ url: `/sales/contract-templates/${id}/`, method: 'delete' })
}
export function previewContractTemplate(id) {
  return request({ url: `/sales/contract-templates/${id}/preview/`, method: 'post' })
}
export function setDefaultContractTemplate(id) {
  return request({ url: `/sales/contract-templates/${id}/set_default/`, method: 'post' })
}
export function generateContract(data) {
  return request({ url: '/sales/contract-templates/generate/', method: 'post', data })
}

// ========== 合同条款 ==========
export function getContractClauses(params) {
  return request({ url: '/sales/contract-clauses/', method: 'get', params })
}
export function createContractClause(data) {
  return request({ url: '/sales/contract-clauses/', method: 'post', data })
}
export function updateContractClause(id, data) {
  return request({ url: `/sales/contract-clauses/${id}/`, method: 'put', data })
}
export function deleteContractClause(id) {
  return request({ url: `/sales/contract-clauses/${id}/`, method: 'delete' })
}

// ========== 已生成合同 ==========
export function getGeneratedContracts(params) {
  return request({ url: '/sales/generated-contracts/', method: 'get', params })
}
export function getGeneratedContract(id) {
  return request({ url: `/sales/generated-contracts/${id}/`, method: 'get' })
}

// ========== CRM仪表盘 ==========
export function getCRMDashboardStats() {
  return request({ url: '/sales/crm-dashboard/stats/', method: 'get' })
}

// ========== 销售分析 ==========
export function getAnalysisStages() {
  return request({ url: '/sales/analysis/stages/', method: 'get' })
}
export function getAnalysisRanking(params) {
  return request({ url: '/sales/analysis/ranking/', method: 'get', params })
}
export function getAnalysisFunnel(params) {
  return request({ url: '/sales/analysis/funnel/', method: 'get', params })
}
export function getAnalysisTrend(params) {
  return request({ url: '/sales/analysis/trend/', method: 'get', params })
}

// ========== 客户RFM分析 ==========
export function getRFMSegmentSummary() {
  return request({ url: '/sales/customer-rfm/segment_summary/', method: 'get' })
}
export function getRFMTopCustomers() {
  return request({ url: '/sales/customer-rfm/top_customers/', method: 'get' })
}
export function analyzeRFM() {
  return request({ url: '/sales/customer-rfm/analyze/', method: 'post' })
}

// ========== 销售业绩 ==========
export function getMyPerformance(params) {
  return request({ url: '/sales/performance/my_performance/', method: 'get', params })
}
export function getTeamRanking(params) {
  return request({ url: '/sales/performance/team_ranking/', method: 'get', params })
}
export function getMonthlyTrend(params) {
  return request({ url: '/sales/performance/monthly_trend/', method: 'get', params })
}
export function getCustomerAnalysis(params) {
  return request({ url: '/sales/performance/customer_analysis/', method: 'get', params })
}
export function getPipelineAnalysis(params) {
  return request({ url: '/sales/performance/pipeline_analysis/', method: 'get', params })
}

// ========== 销售目标 ==========
export function getMyTargets() {
  return request({ url: '/sales/targets/my_targets/', method: 'get' })
}
export function refreshTarget(id) {
  return request({ url: `/sales/targets/${id}/refresh/`, method: 'post' })
}

// ========== 销售提成 ==========
export function getMyCommissions() {
  return request({ url: '/sales/commissions/my_commissions/', method: 'get' })
}

// ========== 知识库 ==========
export function getKnowledgeArticles(params) {
  return request({ url: '/sales/knowledge-base/', method: 'get', params })
}
export function getKnowledgeArticle(id) {
  return request({ url: `/sales/knowledge-base/${id}/`, method: 'get' })
}
export function getPopularArticles() {
  return request({ url: '/sales/knowledge-base/popular/', method: 'get' })
}
export function getKnowledgeTags() {
  return request({ url: '/sales/knowledge-base/tags/', method: 'get' })
}
export function createKnowledgeArticle(data) {
  return request({ url: '/sales/knowledge-base/', method: 'post', data })
}
export function viewKnowledgeArticle(id) {
  return request({ url: `/sales/knowledge-base/${id}/view/`, method: 'post' })
}
export function feedbackKnowledgeArticle(id, data) {
  return request({ url: `/sales/knowledge-base/${id}/feedback/`, method: 'post', data })
}

// ========== 服务合同 ==========
export function getServiceContracts(params) {
  return request({ url: '/sales/service-contracts/', method: 'get', params })
}
export function getServiceContract(id) {
  return request({ url: `/sales/service-contracts/${id}/`, method: 'get' })
}
export function createServiceContract(data) {
  return request({ url: '/sales/service-contracts/', method: 'post', data })
}
export function getExpiringSoonServiceContracts(params) {
  return request({ url: '/sales/service-contracts/expiring_soon/', method: 'get', params })
}
export function activateServiceContract(id) {
  return request({ url: `/sales/service-contracts/${id}/activate/`, method: 'post' })
}
export function getServiceHistory(id) {
  return request({ url: `/sales/service-contracts/${id}/service_history/`, method: 'get' })
}

// ========== 服务请求 ==========
export function getServiceRequests(params) {
  return request({ url: '/sales/service-requests/', method: 'get', params })
}
export function getServiceRequest(id) {
  return request({ url: `/sales/service-requests/${id}/`, method: 'get' })
}
export function createServiceRequest(data) {
  return request({ url: '/sales/service-requests/', method: 'post', data })
}
export function assignServiceRequest(id, data) {
  return request({ url: `/sales/service-requests/${id}/assign/`, method: 'post', data })
}
export function completeServiceRequest(id, data) {
  return request({ url: `/sales/service-requests/${id}/complete/`, method: 'post', data })
}

// ========== 预防性维护 ==========
export function getPreventiveMaintenances(params) {
  return request({ url: '/sales/preventive-maintenance/', method: 'get', params })
}
export function getPreventiveMaintenance(id) {
  return request({ url: `/sales/preventive-maintenance/${id}/`, method: 'get' })
}
export function createPreventiveMaintenance(data) {
  return request({ url: '/sales/preventive-maintenance/', method: 'post', data })
}
export function getUpcomingMaintenance(params) {
  return request({ url: '/sales/preventive-maintenance/upcoming/', method: 'get', params })
}
export function getOverdueMaintenance() {
  return request({ url: '/sales/preventive-maintenance/overdue/', method: 'get' })
}
export function startMaintenance(id) {
  return request({ url: `/sales/preventive-maintenance/${id}/start/`, method: 'post' })
}
export function completeMaintenance(id, data) {
  return request({ url: `/sales/preventive-maintenance/${id}/complete/`, method: 'post', data })
}

// ========== 培训课程 ==========
export function getTrainingCourses(params) {
  return request({ url: '/sales/training-courses/', method: 'get', params })
}
export function createTrainingCourse(data) {
  return request({ url: '/sales/training-courses/', method: 'post', data })
}
export function updateTrainingCourse(id, data) {
  return request({ url: `/sales/training-courses/${id}/`, method: 'put', data })
}

// ========== 培训计划 ==========
export function getTrainingPlans(params) {
  return request({ url: '/sales/training-plans/', method: 'get', params })
}
export function getTrainingPlan(id) {
  return request({ url: `/sales/training-plans/${id}/`, method: 'get' })
}
export function createTrainingPlan(data) {
  return request({ url: '/sales/training-plans/', method: 'post', data })
}
export function updateTrainingPlan(id, data) {
  return request({ url: `/sales/training-plans/${id}/`, method: 'put', data })
}

// ========== 报价估算 ==========
export function getQuoteEstimation(id) {
  return request({ url: `/sales/quote-estimations/${id}/`, method: 'get' })
}
export function calculateQuoteEstimation(id) {
  return request({ url: `/sales/quote-estimations/${id}/calculate/`, method: 'post' })
}
export function submitQuoteEstimation(id) {
  return request({ url: `/sales/quote-estimations/${id}/submit/`, method: 'post' })
}

// ========== 报价版本 ==========
export function getQuoteVersions(params) {
  return request({ url: '/sales/quote-versions/', method: 'get', params })
}
export function getQuoteVersion(id) {
  return request({ url: `/sales/quote-versions/${id}/`, method: 'get' })
}
export function createQuoteVersion(data) {
  return request({ url: '/sales/quote-versions/', method: 'post', data })
}
export function createQuoteVersionNewVersion(id) {
  return request({ url: `/sales/quote-versions/${id}/create_new_version/`, method: 'post' })
}
export function getQuoteVersionProfitPrediction(id) {
  return request({ url: `/sales/quote-versions/${id}/profit_prediction/`, method: 'get' })
}
export function estimateFromReference(id, data) {
  return request({ url: `/sales/quote-versions/${id}/estimate_from_reference/`, method: 'post', data })
}
export function findSimilarQuotes(data) {
  return request({ url: '/sales/quote-versions/find_similar/', method: 'post', data })
}

// ========== 报价模板 ==========
export function getQuoteTemplates(params) {
  return request({ url: '/sales/quote-templates/', method: 'get', params })
}
export function createQuoteTemplate(data) {
  return request({ url: '/sales/quote-templates/', method: 'post', data })
}
export function updateQuoteTemplate(id, data) {
  return request({ url: `/sales/quote-templates/${id}/`, method: 'put', data })
}
export function setDefaultQuoteTemplate(id) {
  return request({ url: `/sales/quote-templates/${id}/set_default/`, method: 'post' })
}
export function generateQuoteFromTemplate(data) {
  return request({ url: '/sales/quote-templates/generate/', method: 'post', data })
}

// ========== 报价单动作 ==========
// ========== 销售订单动作 ==========
export function submitSalesOrder(id) {
  return request({ url: `/sales/orders/${id}/submit/`, method: 'post' })
}
export function confirmSalesOrder(id) {
  return request({ url: `/sales/orders/${id}/confirm/`, method: 'post' })
}
export function cancelSalesOrder(id) {
  return request({ url: `/sales/orders/${id}/cancel/`, method: 'post' })
}
export function returnSalesOrderToDraft(id) {
  return request({ url: `/sales/orders/${id}/return_to_draft/`, method: 'post' })
}
export function getSalesOrdersForLinking(params) {
  return request({ url: '/sales/orders/for_linking/', method: 'get', params })
}
export function downloadSalesOrderTemplate() {
  return request({ url: '/sales/orders/download_template/', method: 'get', responseType: 'blob' })
}
export function importSalesOrders(data) {
  return request({ url: '/sales/orders/import/', method: 'post', data, headers: { 'Content-Type': 'multipart/form-data' } })
}
export function exportSalesOrders(params) {
  return request({ url: '/sales/orders/export/', method: 'get', params, responseType: 'blob' })
}
export function bulkDeleteSalesOrders(data) {
  return request({ url: '/sales/orders/bulk_delete/', method: 'post', data })
}

// ========== 发货单动作 ==========
export function confirmPreparedDelivery(id) {
  return request({ url: `/sales/deliveries/${id}/confirm_prepared/`, method: 'post' })
}
export function confirmLogisticsDelivery(id, data) {
  return request({ url: `/sales/deliveries/${id}/confirm_logistics/`, method: 'post', data })
}
export function confirmSignedDelivery(id, data) {
  return request({ url: `/sales/deliveries/${id}/confirm_signed/`, method: 'post', data })
}
// ========== 销售合同动作 ==========
export function patchSalesContract(id, data) {
  return request({ url: `/sales/contracts/${id}/`, method: 'patch', data })
}
export function submitSalesContract(id) {
  return request({ url: `/sales/contracts/${id}/submit/`, method: 'post' })
}
export function approveSalesContract(id) {
  return request({ url: `/sales/contracts/${id}/approve/`, method: 'post' })
}
export function signSalesContract(id, data) {
  return request({ url: `/sales/contracts/${id}/sign/`, method: 'post', data })
}
export function printPreviewSalesContract(id) {
  return request({ url: `/sales/contracts/${id}/print_preview/`, method: 'get' })
}
// ========== 合同模板 ==========
// ========== 合同条款 ==========
// ========== 已生成合同 ==========
// ========== CRM 仪表盘 & 分析 ==========
// ========== 线索 & 商机 ==========
export function getLeads(params) {
  return request({ url: '/sales/leads/', method: 'get', params })
}
export function getOpportunities(params) {
  return request({ url: '/sales/opportunities/', method: 'get', params })
}

// ========== 知识库 ==========
export function getKnowledgeBaseArticles(params) {
  return request({ url: '/sales/knowledge-base/', method: 'get', params })
}
export function getKnowledgeBaseArticle(id) {
  return request({ url: `/sales/knowledge-base/${id}/`, method: 'get' })
}
export function getKnowledgeBaseTags() {
  return request({ url: '/sales/knowledge-base/tags/', method: 'get' })
}
export function viewKnowledgeBaseArticle(id) {
  return request({ url: `/sales/knowledge-base/${id}/view/`, method: 'post' })
}
export function createKnowledgeBaseArticle(data) {
  return request({ url: '/sales/knowledge-base/', method: 'post', data })
}
export function feedbackKnowledgeBaseArticle(id, data) {
  return request({ url: `/sales/knowledge-base/${id}/feedback/`, method: 'post', data })
}

// ========== 业绩 ==========
// ========== 报价估算 ==========
export function getQuoteEstimations(params) {
  return request({ url: '/sales/quote-estimations/', method: 'get', params })
}
export function createQuoteEstimation(data) {
  return request({ url: '/sales/quote-estimations/', method: 'post', data })
}
export function patchQuoteEstimation(id, data) {
  return request({ url: `/sales/quote-estimations/${id}/`, method: 'patch', data })
}
export function submitQuoteEstimationReview(id) {
  return request({ url: `/sales/quote-estimations/${id}/submit_review/`, method: 'post' })
}
export function approveQuoteEstimation(id) {
  return request({ url: `/sales/quote-estimations/${id}/approve/`, method: 'post' })
}
export function createQuotationFromEstimation(id) {
  return request({ url: `/sales/quote-estimations/${id}/create_quotation/`, method: 'post' })
}

// ========== 报价模板 ==========
// ========== 报价版本 ==========
export function createNewQuoteVersion(id) {
  return request({ url: `/sales/quote-versions/${id}/create_new_version/`, method: 'post' })
}
// ========== 客户RFM分析 ==========
export function getCustomerRFMSegmentSummary() {
  return request({ url: '/sales/customer-rfm/segment_summary/', method: 'get' })
}
export function getTopCustomers() {
  return request({ url: '/sales/customer-rfm/top_customers/', method: 'get' })
}
export function analyzeCustomerRFM() {
  return request({ url: '/sales/customer-rfm/analyze/', method: 'post' })
}

// ========== 服务合同 ==========
export function getServiceContractHistory(id) {
  return request({ url: `/sales/service-contracts/${id}/service_history/`, method: 'get' })
}
export function getExpiringSoonContracts(params) {
  return request({ url: '/sales/service-contracts/expiring_soon/', method: 'get', params })
}

// ========== 服务请求 ==========
// ========== 预防性维护 ==========
export function getPreventiveMaintenanceItem(id) {
  return request({ url: `/sales/preventive-maintenance/${id}/`, method: 'get' })
}
// ========== 培训课程 ==========
// ========== 培训计划 ==========
// ========== 销售合同操作 ==========
export function createContractFromSalesOrder(data) {
  return request({ url: '/sales/contracts/create_from_so/', method: 'post', data })
}
// ========== 合同模板 ==========
// ========== 合同条款 ==========
// ========== 生成的合同 ==========
// ========== CRM仪表盘 ==========
export function getSalesAnalysisStages() {
  return request({ url: '/sales/analysis/stages/', method: 'get' })
}
export function getSalesAnalysisRanking(params) {
  return request({ url: '/sales/analysis/ranking/', method: 'get', params })
}

// ========== 发货单操作 ==========
export function uploadReceiptDelivery(id, data, config) {
  return request({ url: `/sales/deliveries/${id}/upload_receipt/`, method: 'post', data, ...config })
}
export function rejectDeliveryOrder(id, data) {
  return request({ url: `/sales/deliveries/${id}/reject/`, method: 'post', data })
}

// ========== 知识库 ==========
export function getKnowledgeBaseList(params) {
  return request({ url: '/sales/knowledge-base/', method: 'get', params })
}
// ========== 销售订单操作 ==========
// ========== 业绩分析 ==========
export function refreshSalesTarget(id) {
  return request({ url: `/sales/targets/${id}/refresh/`, method: 'post' })
}

// ========== 报价单操作 ==========
export function createNewQuotationVersion(id) {
  return request({ url: `/sales/quotations/${id}/create_new_version/`, method: 'post' })
}
// ========== 预防维护 ==========
export function getPreventiveMaintenanceList(params) {
  return request({ url: '/sales/preventive-maintenance/', method: 'get', params })
}
export function startPreventiveMaintenance(id) {
  return request({ url: `/sales/preventive-maintenance/${id}/start/`, method: 'post' })
}
export function completePreventiveMaintenance(id, data) {
  return request({ url: `/sales/preventive-maintenance/${id}/complete/`, method: 'post', data })
}

// ========== 服务合同 ==========
// ========== 销售订单 (别名兼容) ==========
export function getSalesOrders(params) {
  return request({ url: '/sales/orders/', method: 'get', params })
}
export function getSalesOrder(id) {
  return request({ url: `/sales/orders/${id}/`, method: 'get' })
}
export function createSalesOrder(data) {
  return request({ url: '/sales/orders/', method: 'post', data })
}
export function updateSalesOrder(id, data) {
  return request({ url: `/sales/orders/${id}/`, method: 'put', data })
}
export function deleteSalesOrder(id) {
  return request({ url: `/sales/orders/${id}/`, method: 'delete' })
}

// ========== 销售合同 (别名兼容) ==========
export function getSalesContracts(params) {
  return request({ url: '/sales/contracts/', method: 'get', params })
}
export function getSalesContract(id) {
  return request({ url: `/sales/contracts/${id}/`, method: 'get' })
}

// ========== CRM ==========
export function getSalesRanking(params) {
  return request({ url: '/sales/crm-dashboard/sales_ranking/', method: 'get', params })
}

// ========== 报价版本 ==========
export function createQuotationVersion(id, data) {
  return request({ url: `/sales/quotations/${id}/create_version/`, method: 'post', data })
}
