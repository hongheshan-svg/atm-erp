/**
 * 供应商评价管理 API
 */
import request from '@/utils/request'

// 评价模板
export function getEvaluationTemplateList(params?: Record<string, any>) {
  return request({
    url: '/purchase/evaluation-templates/',
    method: 'get',
    params
  })
}

export function getEvaluationTemplate(id: number) {
  return request({
    url: `/purchase/evaluation-templates/${id}/`,
    method: 'get'
  })
}

export function createEvaluationTemplate(data: any) {
  return request({
    url: '/purchase/evaluation-templates/',
    method: 'post',
    data
  })
}

export function updateEvaluationTemplate(id: number, data: any) {
  return request({
    url: `/purchase/evaluation-templates/${id}/`,
    method: 'put',
    data
  })
}

export function deleteEvaluationTemplate(id: number) {
  return request({
    url: `/purchase/evaluation-templates/${id}/`,
    method: 'delete'
  })
}

export function setDefaultTemplate(id: number) {
  return request({
    url: `/purchase/evaluation-templates/${id}/set_default/`,
    method: 'post'
  })
}

export function addCriteria(templateId: any, data: any) {
  return request({
    url: `/purchase/evaluation-templates/${templateId}/add_criteria/`,
    method: 'post',
    data
  })
}

export function copyTemplate(id: number, data: any) {
  return request({
    url: `/purchase/evaluation-templates/${id}/copy_template/`,
    method: 'post',
    data
  })
}

// 评价指标
export function getEvaluationCriteriaList(params?: Record<string, any>) {
  return request({
    url: '/purchase/evaluation-criteria/',
    method: 'get',
    params
  })
}

export function createEvaluationCriteria(data: any) {
  return request({
    url: '/purchase/evaluation-criteria/',
    method: 'post',
    data
  })
}

export function updateEvaluationCriteria(id: number, data: any) {
  return request({
    url: `/purchase/evaluation-criteria/${id}/`,
    method: 'put',
    data
  })
}

export function deleteEvaluationCriteria(id: number) {
  return request({
    url: `/purchase/evaluation-criteria/${id}/`,
    method: 'delete'
  })
}

// 供应商评价
export function getEvaluationList(params?: Record<string, any>) {
  return request({
    url: '/purchase/evaluations/',
    method: 'get',
    params
  })
}

export function getEvaluation(id: number) {
  return request({
    url: `/purchase/evaluations/${id}/`,
    method: 'get'
  })
}

export function createEvaluation(data: any) {
  return request({
    url: '/purchase/evaluations/',
    method: 'post',
    data
  })
}

export function updateEvaluation(id: number, data: any) {
  return request({
    url: `/purchase/evaluations/${id}/`,
    method: 'put',
    data
  })
}

export function deleteEvaluation(id: number) {
  return request({
    url: `/purchase/evaluations/${id}/`,
    method: 'delete'
  })
}

export function submitEvaluation(id: number) {
  return request({
    url: `/purchase/evaluations/${id}/submit/`,
    method: 'post'
  })
}

export function approveEvaluation(id: number, data: any) {
  return request({
    url: `/purchase/evaluations/${id}/approve/`,
    method: 'post',
    data
  })
}

export function rejectEvaluation(id: number, data: any) {
  return request({
    url: `/purchase/evaluations/${id}/reject/`,
    method: 'post',
    data
  })
}

export function updateEvaluationScores(id: number, data: any) {
  return request({
    url: `/purchase/evaluations/${id}/update_scores/`,
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
export function getGradeHistoryList(params?: Record<string, any>) {
  return request({
    url: '/purchase/grade-history/',
    method: 'get',
    params
  })
}

// 供应商黑名单
export function getBlacklistList(params?: Record<string, any>) {
  return request({
    url: '/purchase/blacklist/',
    method: 'get',
    params
  })
}

export function createBlacklist(data: any) {
  return request({
    url: '/purchase/blacklist/',
    method: 'post',
    data
  })
}

export function liftBlacklist(id: number, data: any) {
  return request({
    url: `/purchase/blacklist/${id}/lift/`,
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
