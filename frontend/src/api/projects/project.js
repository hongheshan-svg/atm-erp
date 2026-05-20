/**
 * 项目管理 API
 */
import request from '@/utils/request'

export function getProjectList(params) {
  return request({
    url: '/projects/projects/',
    method: 'get',
    params
  })
}

export function getProject(id) {
  return request({
    url: `/projects/projects/${id}/`,
    method: 'get'
  })
}

export function createProject(data) {
  return request({
    url: '/projects/projects/',
    method: 'post',
    data
  })
}

export function updateProject(id, data) {
  return request({
    url: `/projects/projects/${id}/`,
    method: 'put',
    data
  })
}

export function deleteProject(id) {
  return request({
    url: `/projects/projects/${id}/`,
    method: 'delete'
  })
}

export function getProjectStatistics() {
  return request({
    url: '/projects/projects/statistics/',
    method: 'get'
  })
}

export function submitProject(id) {
  return request({ url: `/projects/projects/${id}/submit/`, method: 'post' })
}

export function getProjectDashboard(id) {
  return request({ url: `/projects/dashboard/${id}/`, method: 'get' })
}

export function getProjectBOMItems(id) {
  return request({ url: `/projects/projects/${id}/bom-items/`, method: 'get' })
}

// ========== 任务管理 ==========
export function getTaskList(params) {
  return request({ url: '/projects/tasks/', method: 'get', params })
}

export function createTask(data) {
  return request({ url: '/projects/tasks/', method: 'post', data })
}

export function updateTask(id, data) {
  return request({ url: `/projects/tasks/${id}/`, method: 'put', data })
}

export function deleteTask(id) {
  return request({ url: `/projects/tasks/${id}/`, method: 'delete' })
}

export function patchTask(id, data) {
  return request({ url: `/projects/tasks/${id}/`, method: 'patch', data })
}

export function batchRecalculateHours(data) {
  return request({ url: '/projects/tasks/batch_recalculate_hours/', method: 'post', data })
}

// ========== 项目成员 ==========
export function getMemberList(params) {
  return request({ url: '/projects/members/', method: 'get', params })
}

export function createMember(data) {
  return request({ url: '/projects/members/', method: 'post', data })
}

export function updateMember(id, data) {
  return request({ url: `/projects/members/${id}/`, method: 'put', data })
}

export function deleteMember(id) {
  return request({ url: `/projects/members/${id}/`, method: 'delete' })
}

// ========== 里程碑 ==========
export function getMilestoneList(params) {
  return request({ url: '/projects/milestones/', method: 'get', params })
}

export function getMilestone(id) {
  return request({ url: `/projects/milestones/${id}/`, method: 'get' })
}

export function createMilestone(data) {
  return request({ url: '/projects/milestones/', method: 'post', data })
}

export function updateMilestone(id, data) {
  return request({ url: `/projects/milestones/${id}/`, method: 'put', data })
}

export function getMilestoneTypes() {
  return request({ url: '/projects/milestones/milestone_types/', method: 'get' })
}

export function updateMilestoneProgress(id, data) {
  return request({ url: `/projects/milestones/${id}/update_progress/`, method: 'post', data })
}

export function addMilestoneComment(id, data) {
  return request({ url: `/projects/milestones/${id}/add_comment/`, method: 'post', data })
}

export function completeMilestone(id) {
  return request({ url: `/projects/milestones/${id}/complete/`, method: 'post' })
}

export function initMilestoneTemplate(data) {
  return request({ url: '/projects/milestones/init_template/', method: 'post', data })
}

// ========== 工时记录 ==========
export function getTimeLogList(params) {
  return request({ url: '/projects/time-logs/', method: 'get', params })
}

export function createTimeLog(data) {
  return request({ url: '/projects/time-logs/', method: 'post', data })
}

export function updateTimeLog(id, data) {
  return request({ url: `/projects/time-logs/${id}/`, method: 'put', data })
}

// ========== 成本记录 ==========
export function getCostRecordList(params) {
  return request({ url: '/projects/project-cost-records/', method: 'get', params })
}

export function createCostRecord(data) {
  return request({ url: '/projects/project-cost-records/', method: 'post', data })
}

export function deleteCostRecord(id) {
  return request({ url: `/projects/project-cost-records/${id}/`, method: 'delete' })
}

// ========== 成本分析 ==========
export function getProjectCostDashboard(id) {
  return request({ url: `/projects/cost/dashboard/${id}/`, method: 'get' })
}

export function getProjectCostComparison(params) {
  return request({ url: '/projects/cost/comparison/', method: 'get', params })
}

export function getProjectCostAnalysis(id) {
  return request({ url: `/projects/cost/analysis/${id}/`, method: 'get' })
}

export function getCostDetails(params) {
  return request({ url: '/projects/cost-details/', method: 'get', params })
}
