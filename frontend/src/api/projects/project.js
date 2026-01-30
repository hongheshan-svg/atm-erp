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
