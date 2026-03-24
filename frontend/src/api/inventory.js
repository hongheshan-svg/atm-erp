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
