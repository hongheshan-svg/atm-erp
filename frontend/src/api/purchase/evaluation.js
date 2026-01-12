/**
 * 供应商评价管理 API
 */
import request from '@/utils/request'

// 评价模板
export function getEvaluationTemplateList(params) {
  return request({
    url: '/purchase/evaluation-templates/',
    method: 'get',
    params
  })
}

export function getEvaluationTemplate(id) {
  return request({
    url: `/api/purchase/evaluation-templates/${id}/`,
    method: 'get'
  })
}

export function createEvaluationTemplate(data) {
  return request({
    url: '/purchase/evaluation-templates/',
    method: 'post',
    data
  })
}

export function updateEvaluationTemplate(id, data) {
  return request({
    url: `/api/purchase/evaluation-templates/${id}/`,
    method: 'put',
    data
  })
}

export function deleteEvaluationTemplate(id) {
  return request({
    url: `/api/purchase/evaluation-templates/${id}/`,
    method: 'delete'
  })
}

export function setDefaultTemplate(id) {
  return request({
    url: `/api/purchase/evaluation-templates/${id}/set_default/`,
    method: 'post'
  })
}

export function addCriteria(templateId, data) {
  return request({
    url: `/api/purchase/evaluation-templates/${templateId}/add_criteria/`,
    method: 'post',
    data
  })
}

export function copyTemplate(id, data) {
  return request({
    url: `/api/purchase/evaluation-templates/${id}/copy_template/`,
    method: 'post',
    data
  })
}

// 评价指标
export function getEvaluationCriteriaList(params) {
  return request({
    url: '/purchase/evaluation-criteria/',
    method: 'get',
    params
  })
}

export function createEvaluationCriteria(data) {
  return request({
    url: '/purchase/evaluation-criteria/',
    method: 'post',
    data
  })
}

export function updateEvaluationCriteria(id, data) {
  return request({
    url: `/api/purchase/evaluation-criteria/${id}/`,
    method: 'put',
    data
  })
}

export function deleteEvaluationCriteria(id) {
  return request({
    url: `/api/purchase/evaluation-criteria/${id}/`,
    method: 'delete'
  })
}

// 供应商评价
export function getEvaluationList(params) {
  return request({
    url: '/purchase/evaluations/',
    method: 'get',
    params
  })
}

export function getEvaluation(id) {
  return request({
    url: `/api/purchase/evaluations/${id}/`,
    method: 'get'
  })
}

export function createEvaluation(data) {
  return request({
    url: '/purchase/evaluations/',
    method: 'post',
    data
  })
}

export function updateEvaluation(id, data) {
  return request({
    url: `/api/purchase/evaluations/${id}/`,
    method: 'put',
    data
  })
}

export function deleteEvaluation(id) {
  return request({
    url: `/api/purchase/evaluations/${id}/`,
    method: 'delete'
  })
}

export function submitEvaluation(id) {
  return request({
    url: `/api/purchase/evaluations/${id}/submit/`,
    method: 'post'
  })
}

export function approveEvaluation(id, data) {
  return request({
    url: `/api/purchase/evaluations/${id}/approve/`,
    method: 'post',
    data
  })
}

export function rejectEvaluation(id, data) {
  return request({
    url: `/api/purchase/evaluations/${id}/reject/`,
    method: 'post',
    data
  })
}

export function updateEvaluationScores(id, data) {
  return request({
    url: `/api/purchase/evaluations/${id}/update_scores/`,
    method: 'post',
    data
  })
}

export function getEvaluationStatistics() {
  return request({
    url: '/purchase/evaluations/statistics/',
    method: 'get'
  })
}

export function getSupplierRanking() {
  return request({
    url: '/purchase/evaluations/supplier_ranking/',
    method: 'get'
  })
}

// 供应商等级历史
export function getGradeHistoryList(params) {
  return request({
    url: '/purchase/grade-history/',
    method: 'get',
    params
  })
}

// 供应商黑名单
export function getBlacklistList(params) {
  return request({
    url: '/purchase/blacklist/',
    method: 'get',
    params
  })
}

export function createBlacklist(data) {
  return request({
    url: '/purchase/blacklist/',
    method: 'post',
    data
  })
}

export function liftBlacklist(id, data) {
  return request({
    url: `/api/purchase/blacklist/${id}/lift/`,
    method: 'post',
    data
  })
}

export function getActiveBlacklist() {
  return request({
    url: '/purchase/blacklist/active_list/',
    method: 'get'
  })
}
