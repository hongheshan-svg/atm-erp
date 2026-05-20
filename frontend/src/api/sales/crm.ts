/**
 * CRM API - 商机线索管理
 */
import request from '@/utils/request'

// =============== 线索来源 ===============
export function getLeadSourceList(params?: Record<string, any>) {
  return request({
    url: '/sales/lead-sources/',
    method: 'get',
    params
  })
}

export function createLeadSource(data: any) {
  return request({
    url: '/sales/lead-sources/',
    method: 'post',
    data
  })
}

export function updateLeadSource(id: number, data: any) {
  return request({
    url: `/sales/lead-sources/${id}/`,
    method: 'put',
    data
  })
}

export function deleteLeadSource(id: number) {
  return request({
    url: `/sales/lead-sources/${id}/`,
    method: 'delete'
  })
}

// =============== 销售线索 ===============
export function getLeadList(params?: Record<string, any>) {
  return request({
    url: '/sales/leads/',
    method: 'get',
    params
  })
}

export function getLead(id: number) {
  return request({
    url: `/sales/leads/${id}/`,
    method: 'get'
  })
}

export function createLead(data: any) {
  return request({
    url: '/sales/leads/',
    method: 'post',
    data
  })
}

export function updateLead(id: number, data: any) {
  return request({
    url: `/sales/leads/${id}/`,
    method: 'put',
    data
  })
}

export function deleteLead(id: number) {
  return request({
    url: `/sales/leads/${id}/`,
    method: 'delete'
  })
}

export function getLeadStatistics(params?: Record<string, any>) {
  return request({
    url: '/sales/leads/statistics/',
    method: 'get',
    params
  })
}

export function convertLead(id: number, data: any) {
  return request({
    url: `/sales/leads/${id}/convert/`,
    method: 'post',
    data
  })
}

export function disqualifyLead(id: number, data: any) {
  return request({
    url: `/sales/leads/${id}/disqualify/`,
    method: 'post',
    data
  })
}

// =============== 销售商机 ===============
export function getOpportunityList(params?: Record<string, any>) {
  return request({
    url: '/sales/opportunities/',
    method: 'get',
    params
  })
}

export function getOpportunity(id: number) {
  return request({
    url: `/sales/opportunities/${id}/`,
    method: 'get'
  })
}

export function createOpportunity(data: any) {
  return request({
    url: '/sales/opportunities/',
    method: 'post',
    data
  })
}

export function updateOpportunity(id: number, data: any) {
  return request({
    url: `/sales/opportunities/${id}/`,
    method: 'put',
    data
  })
}

export function deleteOpportunity(id: number) {
  return request({
    url: `/sales/opportunities/${id}/`,
    method: 'delete'
  })
}

export function getOpportunityStatistics(params?: Record<string, any>) {
  return request({
    url: '/sales/opportunities/statistics/',
    method: 'get',
    params
  })
}

export function getOpportunityPipeline(params?: Record<string, any>) {
  return request({
    url: '/sales/opportunities/pipeline/',
    method: 'get',
    params
  })
}

export function changeOpportunityStage(id: number, data: any) {
  return request({
    url: `/sales/opportunities/${id}/change_stage/`,
    method: 'post',
    data
  })
}

export function addOpportunityActivity(id: number, data: any) {
  return request({
    url: `/sales/opportunities/${id}/add_activity/`,
    method: 'post',
    data
  })
}

export function createQuotationFromOpportunity(id: number) {
  return request({
    url: `/sales/opportunities/${id}/create_quotation/`,
    method: 'post'
  })
}

// =============== 商机活动 ===============
export function getOpportunityActivityList(params?: Record<string, any>) {
  return request({
    url: '/sales/opportunity-activities/',
    method: 'get',
    params
  })
}

// =============== 销售预测 ===============
export function getSalesForecastList(params?: Record<string, any>) {
  return request({
    url: '/sales/forecasts/',
    method: 'get',
    params
  })
}

export function getSalesForecastSummary(params?: Record<string, any>) {
  return request({
    url: '/sales/forecasts/summary/',
    method: 'get',
    params
  })
}

export function recalculateSalesForecast(data: any) {
  return request({
    url: '/sales/forecasts/recalculate/',
    method: 'post',
    data
  })
}
