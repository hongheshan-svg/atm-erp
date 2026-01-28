/**
 * CRM API - 商机线索管理
 */
import request from '@/utils/request'

// =============== 线索来源 ===============
export function getLeadSourceList(params) {
  return request({
    url: '/sales/lead-sources/',
    method: 'get',
    params
  })
}

export function createLeadSource(data) {
  return request({
    url: '/sales/lead-sources/',
    method: 'post',
    data
  })
}

export function updateLeadSource(id, data) {
  return request({
    url: `/sales/lead-sources/${id}/`,
    method: 'put',
    data
  })
}

export function deleteLeadSource(id) {
  return request({
    url: `/sales/lead-sources/${id}/`,
    method: 'delete'
  })
}

// =============== 销售线索 ===============
export function getLeadList(params) {
  return request({
    url: '/sales/leads/',
    method: 'get',
    params
  })
}

export function getLead(id) {
  return request({
    url: `/sales/leads/${id}/`,
    method: 'get'
  })
}

export function createLead(data) {
  return request({
    url: '/sales/leads/',
    method: 'post',
    data
  })
}

export function updateLead(id, data) {
  return request({
    url: `/sales/leads/${id}/`,
    method: 'put',
    data
  })
}

export function deleteLead(id) {
  return request({
    url: `/sales/leads/${id}/`,
    method: 'delete'
  })
}

export function getLeadStatistics(params) {
  return request({
    url: '/sales/leads/statistics/',
    method: 'get',
    params
  })
}

export function convertLead(id, data) {
  return request({
    url: `/sales/leads/${id}/convert/`,
    method: 'post',
    data
  })
}

export function disqualifyLead(id, data) {
  return request({
    url: `/sales/leads/${id}/disqualify/`,
    method: 'post',
    data
  })
}

// =============== 销售商机 ===============
export function getOpportunityList(params) {
  return request({
    url: '/sales/opportunities/',
    method: 'get',
    params
  })
}

export function getOpportunity(id) {
  return request({
    url: `/sales/opportunities/${id}/`,
    method: 'get'
  })
}

export function createOpportunity(data) {
  return request({
    url: '/sales/opportunities/',
    method: 'post',
    data
  })
}

export function updateOpportunity(id, data) {
  return request({
    url: `/sales/opportunities/${id}/`,
    method: 'put',
    data
  })
}

export function deleteOpportunity(id) {
  return request({
    url: `/sales/opportunities/${id}/`,
    method: 'delete'
  })
}

export function getOpportunityStatistics(params) {
  return request({
    url: '/sales/opportunities/statistics/',
    method: 'get',
    params
  })
}

export function getOpportunityPipeline(params) {
  return request({
    url: '/sales/opportunities/pipeline/',
    method: 'get',
    params
  })
}

export function changeOpportunityStage(id, data) {
  return request({
    url: `/sales/opportunities/${id}/change_stage/`,
    method: 'post',
    data
  })
}

export function addOpportunityActivity(id, data) {
  return request({
    url: `/sales/opportunities/${id}/add_activity/`,
    method: 'post',
    data
  })
}

export function createQuotationFromOpportunity(id) {
  return request({
    url: `/sales/opportunities/${id}/create_quotation/`,
    method: 'post'
  })
}

// =============== 商机活动 ===============
export function getOpportunityActivityList(params) {
  return request({
    url: '/sales/opportunity-activities/',
    method: 'get',
    params
  })
}

// =============== 销售预测 ===============
export function getSalesForecastList(params) {
  return request({
    url: '/sales/forecasts/',
    method: 'get',
    params
  })
}

export function getSalesForecastSummary(params) {
  return request({
    url: '/sales/forecasts/summary/',
    method: 'get',
    params
  })
}

export function recalculateSalesForecast(data) {
  return request({
    url: '/sales/forecasts/recalculate/',
    method: 'post',
    data
  })
}
