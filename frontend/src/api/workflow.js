/**
 * Workflow API
 */
import request from '@/utils/request'

// Workflow Definitions
export function getWorkflowDefinitions(params) {
  return request({
    url: '/core/workflow/definitions/',
    method: 'get',
    params
  })
}

export function getWorkflowDefinition(id) {
  return request({
    url: `/core/workflow/definitions/${id}/`,
    method: 'get'
  })
}

export function createWorkflowDefinition(data) {
  return request({
    url: '/core/workflow/definitions/',
    method: 'post',
    data
  })
}

export function updateWorkflowDefinition(id, data) {
  return request({
    url: `/core/workflow/definitions/${id}/`,
    method: 'put',
    data
  })
}

// Workflow Steps
export function getWorkflowSteps(params) {
  return request({
    url: '/core/workflow/steps/',
    method: 'get',
    params
  })
}

export function createWorkflowStep(data) {
  return request({
    url: '/core/workflow/steps/',
    method: 'post',
    data
  })
}

export function updateWorkflowStep(id, data) {
  return request({
    url: `/core/workflow/steps/${id}/`,
    method: 'put',
    data
  })
}

export function deleteWorkflowStep(id) {
  return request({
    url: `/core/workflow/steps/${id}/`,
    method: 'delete'
  })
}

// Workflow Instances
export function getWorkflowInstances(params) {
  return request({
    url: '/core/workflow/instances/',
    method: 'get',
    params
  })
}

export function getMySubmittedWorkflows() {
  return request({
    url: '/core/workflow/instances/my_submitted/',
    method: 'get'
  })
}

export function getWorkflowHistory(businessType, businessId) {
  return request({
    url: '/core/workflow/instances/history/',
    method: 'get',
    params: { business_type: businessType, business_id: businessId }
  })
}

export function withdrawWorkflow(id) {
  return request({
    url: `/core/workflow/instances/${id}/withdraw/`,
    method: 'post'
  })
}

// Workflow Tasks
export function getWorkflowTasks(params) {
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

export function approveTask(id, comment = '') {
  return request({
    url: `/core/workflow/tasks/${id}/approve/`,
    method: 'post',
    data: { comment }
  })
}

export function rejectTask(id, comment) {
  return request({
    url: `/core/workflow/tasks/${id}/reject/`,
    method: 'post',
    data: { comment }
  })
}
