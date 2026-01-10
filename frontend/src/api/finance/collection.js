/**
 * 回款计划管理 API
 */
import request from '@/utils/request'

// =============== 回款计划 ===============
export function getCollectionPlanList(params) {
  return request({
    url: '/api/finance/collection-plans/',
    method: 'get',
    params
  })
}

export function getCollectionPlan(id) {
  return request({
    url: `/api/finance/collection-plans/${id}/`,
    method: 'get'
  })
}

export function createCollectionPlan(data) {
  return request({
    url: '/api/finance/collection-plans/',
    method: 'post',
    data
  })
}

export function updateCollectionPlan(id, data) {
  return request({
    url: `/api/finance/collection-plans/${id}/`,
    method: 'put',
    data
  })
}

export function deleteCollectionPlan(id) {
  return request({
    url: `/api/finance/collection-plans/${id}/`,
    method: 'delete'
  })
}

export function getCollectionPlanStatistics(params) {
  return request({
    url: '/api/finance/collection-plans/statistics/',
    method: 'get',
    params
  })
}

export function getOverdueCollections(params) {
  return request({
    url: '/api/finance/collection-plans/overdue/',
    method: 'get',
    params
  })
}

export function getUpcomingCollections(params) {
  return request({
    url: '/api/finance/collection-plans/upcoming/',
    method: 'get',
    params
  })
}

export function confirmCollectionPlan(id) {
  return request({
    url: `/api/finance/collection-plans/${id}/confirm/`,
    method: 'post'
  })
}

export function addMilestones(id, data) {
  return request({
    url: `/api/finance/collection-plans/${id}/add_milestones/`,
    method: 'post',
    data
  })
}

export function createStandardMilestones(id, data) {
  return request({
    url: `/api/finance/collection-plans/${id}/create_from_contract/`,
    method: 'post',
    data
  })
}

// =============== 回款节点 ===============
export function getCollectionMilestoneList(params) {
  return request({
    url: '/api/finance/collection-milestones/',
    method: 'get',
    params
  })
}

export function getCollectionMilestone(id) {
  return request({
    url: `/api/finance/collection-milestones/${id}/`,
    method: 'get'
  })
}

export function updateCollectionMilestone(id, data) {
  return request({
    url: `/api/finance/collection-milestones/${id}/`,
    method: 'put',
    data
  })
}

export function addCollectionRecord(id, data) {
  return request({
    url: `/api/finance/collection-milestones/${id}/add_record/`,
    method: 'post',
    data
  })
}

export function triggerMilestone(id) {
  return request({
    url: `/api/finance/collection-milestones/${id}/trigger/`,
    method: 'post'
  })
}

export function sendMilestoneReminder(id, data) {
  return request({
    url: `/api/finance/collection-milestones/${id}/send_reminder/`,
    method: 'post',
    data
  })
}

// =============== 收款记录 ===============
export function getCollectionRecordList(params) {
  return request({
    url: '/api/finance/collection-records/',
    method: 'get',
    params
  })
}

export function createCollectionRecord(data) {
  return request({
    url: '/api/finance/collection-records/',
    method: 'post',
    data
  })
}

export function confirmCollectionRecord(id) {
  return request({
    url: `/api/finance/collection-records/${id}/confirm/`,
    method: 'post'
  })
}
