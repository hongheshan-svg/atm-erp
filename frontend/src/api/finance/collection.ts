/**
 * 回款计划管理 API
 */
import request from '@/utils/request'

// =============== 回款计划 ===============
export function getCollectionPlanList(params?: Record<string, any>) {
  return request({
    url: '/finance/collection-plans/',
    method: 'get',
    params
  })
}

export function getCollectionPlan(id: number) {
  return request({
    url: `/finance/collection-plans/${id}/`,
    method: 'get'
  })
}

export function createCollectionPlan(data: any) {
  return request({
    url: '/finance/collection-plans/',
    method: 'post',
    data
  })
}

export function updateCollectionPlan(id: number, data: any) {
  return request({
    url: `/finance/collection-plans/${id}/`,
    method: 'put',
    data
  })
}

export function deleteCollectionPlan(id: number) {
  return request({
    url: `/finance/collection-plans/${id}/`,
    method: 'delete'
  })
}

export function getCollectionPlanStatistics(params?: Record<string, any>) {
  return request({
    url: '/finance/collection-plans/statistics/',
    method: 'get',
    params
  })
}

export function getOverdueCollections(params?: Record<string, any>) {
  return request({
    url: '/finance/collection-plans/overdue/',
    method: 'get',
    params
  })
}

export function getUpcomingCollections(params?: Record<string, any>) {
  return request({
    url: '/finance/collection-plans/upcoming/',
    method: 'get',
    params
  })
}

export function confirmCollectionPlan(id: number) {
  return request({
    url: `/finance/collection-plans/${id}/confirm/`,
    method: 'post'
  })
}

export function addMilestones(id: number, data: any) {
  return request({
    url: `/finance/collection-plans/${id}/add_milestones/`,
    method: 'post',
    data
  })
}

export function createStandardMilestones(id: number, data: any) {
  return request({
    url: `/finance/collection-plans/${id}/create_from_contract/`,
    method: 'post',
    data
  })
}

// =============== 回款节点 ===============
export function getCollectionMilestoneList(params?: Record<string, any>) {
  return request({
    url: '/finance/collection-milestones/',
    method: 'get',
    params
  })
}

export function getCollectionMilestone(id: number) {
  return request({
    url: `/finance/collection-milestones/${id}/`,
    method: 'get'
  })
}

export function updateCollectionMilestone(id: number, data: any) {
  return request({
    url: `/finance/collection-milestones/${id}/`,
    method: 'put',
    data
  })
}

export function addCollectionRecord(id: number, data: any) {
  return request({
    url: `/finance/collection-milestones/${id}/add_record/`,
    method: 'post',
    data
  })
}

export function triggerMilestone(id: number) {
  return request({
    url: `/finance/collection-milestones/${id}/trigger/`,
    method: 'post'
  })
}

export function sendMilestoneReminder(id: number, data: any) {
  return request({
    url: `/finance/collection-milestones/${id}/send_reminder/`,
    method: 'post',
    data
  })
}

// =============== 收款记录 ===============
export function getCollectionRecordList(params?: Record<string, any>) {
  return request({
    url: '/finance/collection-records/',
    method: 'get',
    params
  })
}

export function createCollectionRecord(data: any) {
  return request({
    url: '/finance/collection-records/',
    method: 'post',
    data
  })
}

export function confirmCollectionRecord(id: number) {
  return request({
    url: `/finance/collection-records/${id}/confirm/`,
    method: 'post'
  })
}
