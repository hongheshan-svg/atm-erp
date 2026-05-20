/**
 * 项目管理 API
 */
import request from '@/utils/request'

export function getProjectList(params?: Record<string, any>) {
  return request({
    url: '/projects/projects/',
    method: 'get',
    params
  })
}

export function getProject(id: number) {
  return request({
    url: `/projects/projects/${id}/`,
    method: 'get'
  })
}

export function createProject(data: any) {
  return request({
    url: '/projects/projects/',
    method: 'post',
    data
  })
}

export function updateProject(id: number, data: any) {
  return request({
    url: `/projects/projects/${id}/`,
    method: 'put',
    data
  })
}

export function deleteProject(id: number) {
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

export function submitProject(id: number) {
  return request({ url: `/projects/projects/${id}/submit/`, method: 'post' })
}

export function getProjectDashboard(id: number) {
  return request({ url: `/projects/dashboard/${id}/`, method: 'get' })
}

export function getProjectBOMItems(id: number) {
  return request({ url: `/projects/projects/${id}/bom-items/`, method: 'get' })
}

// ========== 任务管理 ==========
export function getTaskList(params?: Record<string, any>) {
  return request({ url: '/projects/tasks/', method: 'get', params })
}

export function createTask(data: any) {
  return request({ url: '/projects/tasks/', method: 'post', data })
}

export function updateTask(id: number, data: any) {
  return request({ url: `/projects/tasks/${id}/`, method: 'put', data })
}

export function deleteTask(id: number) {
  return request({ url: `/projects/tasks/${id}/`, method: 'delete' })
}

export function patchTask(id: number, data: any) {
  return request({ url: `/projects/tasks/${id}/`, method: 'patch', data })
}

export function batchRecalculateHours(data: any) {
  return request({ url: '/projects/tasks/batch_recalculate_hours/', method: 'post', data })
}

// ========== 项目成员 ==========
export function getMemberList(params?: Record<string, any>) {
  return request({ url: '/projects/members/', method: 'get', params })
}

export function createMember(data: any) {
  return request({ url: '/projects/members/', method: 'post', data })
}

export function updateMember(id: number, data: any) {
  return request({ url: `/projects/members/${id}/`, method: 'put', data })
}

export function deleteMember(id: number) {
  return request({ url: `/projects/members/${id}/`, method: 'delete' })
}

// ========== 里程碑 ==========
export function getMilestoneList(params?: Record<string, any>) {
  return request({ url: '/projects/milestones/', method: 'get', params })
}

export function getMilestone(id: number) {
  return request({ url: `/projects/milestones/${id}/`, method: 'get' })
}

export function createMilestone(data: any) {
  return request({ url: '/projects/milestones/', method: 'post', data })
}

export function updateMilestone(id: number, data: any) {
  return request({ url: `/projects/milestones/${id}/`, method: 'put', data })
}

export function getMilestoneTypes() {
  return request({ url: '/projects/milestones/milestone_types/', method: 'get' })
}

export function updateMilestoneProgress(id: number, data: any) {
  return request({ url: `/projects/milestones/${id}/update_progress/`, method: 'post', data })
}

export function addMilestoneComment(id: number, data: any) {
  return request({ url: `/projects/milestones/${id}/add_comment/`, method: 'post', data })
}

export function completeMilestone(id: number) {
  return request({ url: `/projects/milestones/${id}/complete/`, method: 'post' })
}

export function initMilestoneTemplate(data: any) {
  return request({ url: '/projects/milestones/init_template/', method: 'post', data })
}

// ========== 工时记录 ==========
export function getTimeLogList(params?: Record<string, any>) {
  return request({ url: '/projects/time-logs/', method: 'get', params })
}

export function createTimeLog(data: any) {
  return request({ url: '/projects/time-logs/', method: 'post', data })
}

export function updateTimeLog(id: number, data: any) {
  return request({ url: `/projects/time-logs/${id}/`, method: 'put', data })
}

// ========== 成本记录 ==========
export function getCostRecordList(params?: Record<string, any>) {
  return request({ url: '/projects/project-cost-records/', method: 'get', params })
}

export function createCostRecord(data: any) {
  return request({ url: '/projects/project-cost-records/', method: 'post', data })
}

export function deleteCostRecord(id: number) {
  return request({ url: `/projects/project-cost-records/${id}/`, method: 'delete' })
}

// ========== 成本分析 ==========
export function getProjectCostDashboard(id: number) {
  return request({ url: `/projects/cost/dashboard/${id}/`, method: 'get' })
}

export function getProjectCostComparison(params?: Record<string, any>) {
  return request({ url: '/projects/cost/comparison/', method: 'get', params })
}

export function getProjectCostAnalysis(id: number) {
  return request({ url: `/projects/cost/analysis/${id}/`, method: 'get' })
}

export function getCostDetails(params?: Record<string, any>) {
  return request({ url: '/projects/cost-details/', method: 'get', params })
}
