/**
 * Workflow API
 */
import request from '@/utils/request'

// Workflow Definitions
export function getWorkflowDefinitions(params?: Record<string, any>) {
  return request({
    url: '/core/workflow/definitions/',
    method: 'get',
    params
  })
}

export function getWorkflowDefinition(id: number) {
  return request({
    url: `/core/workflow/definitions/${id}/`,
    method: 'get'
  })
}

export function createWorkflowDefinition(data: any) {
  return request({
    url: '/core/workflow/definitions/',
    method: 'post',
    data
  })
}

export function updateWorkflowDefinition(id: number, data: any) {
  return request({
    url: `/core/workflow/definitions/${id}/`,
    method: 'put',
    data
  })
}

export function deleteWorkflowDefinition(id: number) {
  return request({
    url: `/core/workflow/definitions/${id}/`,
    method: 'delete'
  })
}

// Workflow Steps
export function getWorkflowSteps(params?: Record<string, any>) {
  return request({
    url: '/core/workflow/steps/',
    method: 'get',
    params
  })
}

export function createWorkflowStep(data: any) {
  return request({
    url: '/core/workflow/steps/',
    method: 'post',
    data
  })
}

export function updateWorkflowStep(id: number, data: any) {
  return request({
    url: `/core/workflow/steps/${id}/`,
    method: 'put',
    data
  })
}

export function deleteWorkflowStep(id: number) {
  return request({
    url: `/core/workflow/steps/${id}/`,
    method: 'delete'
  })
}

// 交换两个审批步骤的顺序（后端单事务规避唯一约束冲突）
export function reorderWorkflowSteps(stepId: number, targetId: number) {
  return request({
    url: '/core/workflow/steps/reorder/',
    method: 'post',
    data: { step_id: stepId, target_id: targetId }
  })
}

// Workflow Instances
export function getWorkflowInstances(params?: Record<string, any>) {
  return request({
    url: '/core/workflow/instances/',
    method: 'get',
    params
  })
}


export function getWorkflowInstance(id: number) {
  return request({
    url: `/core/workflow/instances/${id}/`,
    method: 'get'
  })
}

export function getWorkflowProgress(id: number) {
  return request({
    url: `/core/workflow/instances/${id}/progress/`,
    method: 'get'
  })
}

export function getWorkflowByBusiness(businessType: any, businessId: any) {
  return request({
    url: '/core/workflow/instances/by_business/',
    method: 'get',
    params: { business_type: businessType, business_id: businessId }
  })
}
export function getMySubmittedWorkflows() {
  return request({
    url: '/core/workflow/instances/my_submitted/',
    method: 'get'
  })
}

export function getWorkflowHistory(businessType: any, businessId: any) {
  return request({
    url: '/core/workflow/instances/history/',
    method: 'get',
    params: { business_type: businessType, business_id: businessId }
  })
}

export function withdrawWorkflow(id: number) {
  return request({
    url: `/core/workflow/instances/${id}/withdraw/`,
    method: 'post'
  })
}

// Workflow Tasks
export function getWorkflowTasks(params?: Record<string, any>) {
  return request({
    url: '/core/workflow/tasks/',
    method: 'get',
    params
  })
}

export function getMyPendingTasks() {
  return request({
    url: '/core/workflow/tasks/my_pending/',
    method: 'get'
  })
}

export function getPendingTaskCount() {
  return request({
    url: '/core/workflow/tasks/pending_count/',
    method: 'get'
  })
}

export function approveTask(id: number, comment = '') {
  return request({
    url: `/core/workflow/tasks/${id}/approve/`,
    method: 'post',
    data: { comment }
  })
}

export function rejectTask(id: number, comment: any) {
  return request({
    url: `/core/workflow/tasks/${id}/reject/`,
    method: 'post',
    data: { comment }
  })
}

// Admin delete functions
export function deleteWorkflowInstance(id: number) {
  return request({
    url: `/core/workflow/instances/${id}/admin_delete/`,
    method: 'delete'
  })
}

export function batchDeleteWorkflowInstances(ids: any) {
  return request({
    url: '/core/workflow/instances/batch_delete/',
    method: 'post',
    data: { ids }
  })
}

export function deleteWorkflowTask(id: number) {
  return request({
    url: `/core/workflow/tasks/${id}/admin_delete/`,
    method: 'delete'
  })
}

export function batchDeleteWorkflowTasks(ids: any) {
  return request({
    url: '/core/workflow/tasks/batch_delete/',
    method: 'post',
    data: { ids }
  })
}
