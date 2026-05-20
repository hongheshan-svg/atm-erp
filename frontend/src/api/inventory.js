/**
 * 库存管理扩展 API
 * - MRP增强
 * - 备件预测
 */
import request from '@/utils/request'

// ========== MRP增强 ==========
export function runMRPExplosion(data) {
  return request({ url: '/inventory/mrp/explosion/', method: 'post', data })
}

export function runMRPAutoGenerate(data) {
  return request({ url: '/inventory/mrp/auto-generate/', method: 'post', data })
}

// ========== 备件智能预测 ==========
export function getSparePartLifecyclePrediction(params) {
  return request({ url: '/inventory/spare-parts/lifecycle-prediction/', method: 'get', params })
}

export function getSparePartPurchaseSuggestions(params) {
  return request({ url: '/inventory/spare-parts/purchase-suggestions/', method: 'get', params })
}

export function generatePurchaseSuggestions(data) {
  return request({ url: '/inventory/spare-parts/purchase-suggestions/', method: 'post', data })
}

export function getSparePartCostAnalysis(params) {
  return request({ url: '/inventory/spare-parts/cost-analysis/', method: 'get', params })
}

// ========== 库存/移动/调整 ==========
export function getStockValuation(params) {
  return request({ url: '/inventory/stocks/valuation/', method: 'get', params })
}

export function getStockMoveList(params) {
  return request({ url: '/inventory/stock-moves/', method: 'get', params })
}

export function createStockAdjustment(data) {
  return request({ url: '/inventory/stock-adjustments/', method: 'post', data })
}

export function createStockTransfer(data) {
  return request({ url: '/inventory/stock-moves/create_transfer/', method: 'post', data })
}

// ========== 库存 ==========
export function getStocks(params) {
  return request({ url: '/inventory/stocks/', method: 'get', params })
}
export function getStockMoves(params) {
  return request({ url: '/inventory/stock-moves/', method: 'get', params })
}
export function getInventoryValuation(params) {
  return request({ url: '/inventory/period-summaries/inventory_valuation/', method: 'get', params })
}

// ========== 库存移动 ==========
export function getMoves(params) {
  return request({ url: '/inventory/moves/', method: 'get', params })
}
export function createTransfer(data) {
  return request({ url: '/inventory/moves/transfer/', method: 'post', data })
}

// ========== 库存调整 ==========
export function getAdjustments(params) {
  return request({ url: '/inventory/adjustments/', method: 'get', params })
}
export function getAdjustment(id) {
  return request({ url: `/inventory/adjustments/${id}/`, method: 'get' })
}
export function createAdjustment(data) {
  return request({ url: '/inventory/adjustments/', method: 'post', data })
}
export function submitAdjustment(id) {
  return request({ url: `/inventory/adjustments/${id}/submit/`, method: 'post' })
}
export function confirmAdjustment(id) {
  return request({ url: `/inventory/adjustments/${id}/confirm/`, method: 'post' })
}

// ========== 批次管理 ==========
export function getBatches(params) {
  return request({ url: '/inventory/batches/', method: 'get', params })
}
export function createBatch(data) {
  return request({ url: '/inventory/batches/', method: 'post', data })
}
export function updateBatch(id, data) {
  return request({ url: `/inventory/batches/${id}/`, method: 'patch', data })
}
export function adjustBatchQty(id, data) {
  return request({ url: `/inventory/batches/${id}/adjust_qty/`, method: 'post', data })
}
export function getBatchesExpiringSoon(params) {
  return request({ url: '/inventory/batches/expiring_soon/', method: 'get', params })
}
export function getBatchesExpired(params) {
  return request({ url: '/inventory/batches/expired/', method: 'get', params })
}
export function getBatchMovesByBatch(params) {
  return request({ url: '/inventory/batch-moves/by_batch/', method: 'get', params })
}

// ========== 领料申请 ==========
export function getRequisitions(params) {
  return request({ url: '/inventory/requisitions/', method: 'get', params })
}
export function getRequisition(id) {
  return request({ url: `/inventory/requisitions/${id}/`, method: 'get' })
}
export function createRequisition(data) {
  return request({ url: '/inventory/requisitions/', method: 'post', data })
}
export function updateRequisition(id, data) {
  return request({ url: `/inventory/requisitions/${id}/`, method: 'put', data })
}
export function submitRequisition(id) {
  return request({ url: `/inventory/requisitions/${id}/submit/`, method: 'post' })
}
export function approveRequisition(id) {
  return request({ url: `/inventory/requisitions/${id}/approve/`, method: 'post' })
}
export function rejectRequisition(id, data) {
  return request({ url: `/inventory/requisitions/${id}/reject/`, method: 'post', data })
}
export function startPreparingRequisition(id) {
  return request({ url: `/inventory/requisitions/${id}/start_preparing/`, method: 'post' })
}
export function readyRequisition(id) {
  return request({ url: `/inventory/requisitions/${id}/ready/`, method: 'post' })
}
export function issueRequisition(id, data) {
  return request({ url: `/inventory/requisitions/${id}/issue/`, method: 'post', data })
}

// ========== 退料管理 ==========
export function getReturns(params) {
  return request({ url: '/inventory/returns/', method: 'get', params })
}
export function getReturn(id) {
  return request({ url: `/inventory/returns/${id}/`, method: 'get' })
}
export function createReturn(data) {
  return request({ url: '/inventory/returns/', method: 'post', data })
}
export function updateReturn(id, data) {
  return request({ url: `/inventory/returns/${id}/`, method: 'put', data })
}
export function submitReturn(id) {
  return request({ url: `/inventory/returns/${id}/submit/`, method: 'post' })
}
export function startInspectReturn(id) {
  return request({ url: `/inventory/returns/${id}/start_inspect/`, method: 'post' })
}
export function receiveReturn(id, data) {
  return request({ url: `/inventory/returns/${id}/receive/`, method: 'post', data })
}
export function rejectReturn(id, data) {
  return request({ url: `/inventory/returns/${id}/reject/`, method: 'post', data })
}

// ========== 成本管理 ==========
export function getCostConfigs(params) {
  return request({ url: '/inventory/cost-configs/', method: 'get', params })
}
export function createCostConfig(data) {
  return request({ url: '/inventory/cost-configs/', method: 'post', data })
}
export function updateCostConfig(id, data) {
  return request({ url: `/inventory/cost-configs/${id}/`, method: 'put', data })
}
export function setCostConfigDefault(id) {
  return request({ url: `/inventory/cost-configs/${id}/set_default/`, method: 'post' })
}
export function getCostRecords(params) {
  return request({ url: '/inventory/cost-records/', method: 'get', params })
}
export function generatePeriodSummary(data) {
  return request({ url: '/inventory/period-summaries/generate/', method: 'post', data })
}

// ========== MRP计划 ==========
export function getMRPPlans(params) {
  return request({ url: '/inventory/mrp-plans/', method: 'get', params })
}
export function getMRPPlan(id) {
  return request({ url: `/inventory/mrp-plans/${id}/`, method: 'get' })
}
export function createMRPPlan(data) {
  return request({ url: '/inventory/mrp-plans/', method: 'post', data })
}
export function calculateMRPPlan(id) {
  return request({ url: `/inventory/mrp-plans/${id}/calculate/`, method: 'post' })
}
export function approveMRPPlan(id) {
  return request({ url: `/inventory/mrp-plans/${id}/approve/`, method: 'post' })
}
export function generateMRPPlanPR(id) {
  return request({ url: `/inventory/mrp-plans/${id}/generate_pr/`, method: 'post' })
}

// ========== 库存预警 ==========
export function getStockAlertRules(params) {
  return request({ url: '/inventory/stock-alert-rules/', method: 'get', params })
}
export function initStockAlertRules() {
  return request({ url: '/inventory/stock-alert-rules/init_rules/', method: 'post' })
}
export function getStockAlerts(params) {
  return request({ url: '/inventory/stock-alerts/', method: 'get', params })
}
export function getStockAlertsSummary() {
  return request({ url: '/inventory/stock-alerts/summary/', method: 'get' })
}
export function checkAllStockAlerts() {
  return request({ url: '/inventory/stock-alerts/check_all/', method: 'post' })
}
export function acknowledgeStockAlert(id) {
  return request({ url: `/inventory/stock-alerts/${id}/acknowledge/`, method: 'post' })
}
export function resolveStockAlert(id, data) {
  return request({ url: `/inventory/stock-alerts/${id}/resolve/`, method: 'post', data })
}
export function ignoreStockAlert(id) {
  return request({ url: `/inventory/stock-alerts/${id}/ignore/`, method: 'post' })
}

// ========== 备件管理 ==========
export function getSparePartCategories(params) {
  return request({ url: '/inventory/spare-part-categories/', method: 'get', params })
}
export function getSpareParts(params) {
  return request({ url: '/inventory/spare-parts/', method: 'get', params })
}
export function createSparePart(data) {
  return request({ url: '/inventory/spare-parts/', method: 'post', data })
}
export function updateSparePart(id, data) {
  return request({ url: `/inventory/spare-parts/${id}/`, method: 'put', data })
}
export function deleteSparePart(id) {
  return request({ url: `/inventory/spare-parts/${id}/`, method: 'delete' })
}
export function consumeSparePart(id, data) {
  return request({ url: `/inventory/spare-part-consumptions/`, method: 'post', data })
}
export function getSparePartAlerts(params) {
  return request({ url: '/inventory/spare-part-alerts/', method: 'get', params })
}
export function resolveSparePartAlert(id) {
  return request({ url: `/inventory/spare-part-alerts/${id}/resolve/`, method: 'post' })
}

// ========== 数据校验 ==========
export function getValidationRules(params) {
  return request({ url: '/inventory/validation-rules/', method: 'get', params })
}
export function updateValidationRule(id, data) {
  return request({ url: `/inventory/validation-rules/${id}/`, method: 'put', data })
}
export function initDefaultValidationRules() {
  return request({ url: '/inventory/validation-rules/init_default_rules/', method: 'post' })
}
export function getValidationResults(params) {
  return request({ url: '/inventory/validation-results/', method: 'get', params })
}
export function handleValidationResult(id, data) {
  return request({ url: `/inventory/validation-results/${id}/handle/`, method: 'post', data })
}
export function runValidationChecks(data) {
  return request({ url: '/inventory/validation-results/run_checks/', method: 'post', data })
}

// ========== 盘点 ==========
export function getReconciliationSessions(params) {
  return request({ url: '/inventory/reconciliation-sessions/', method: 'get', params })
}
export function getReconciliationSession(id) {
  return request({ url: `/inventory/reconciliation-sessions/${id}/`, method: 'get' })
}
export function createAndRunReconciliation(data) {
  return request({ url: '/inventory/reconciliation-sessions/create_and_run/', method: 'post', data })
}
export function getAccuracyReport(params) {
  return request({ url: '/inventory/accuracy-report/', method: 'get', params })
}
