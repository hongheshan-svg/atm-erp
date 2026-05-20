/**
 * 知识库管理 API
 */
import request from '@/utils/request'

// =============== 知识分类 ===============
export function getKnowledgeCategoryList(params?: Record<string, any>) {
  return request({
    url: '/projects/knowledge-categories/',
    method: 'get',
    params
  })
}

export function getKnowledgeCategoryTree() {
  return request({
    url: '/projects/knowledge-categories/tree/',
    method: 'get'
  })
}

export function createKnowledgeCategory(data: any) {
  return request({
    url: '/projects/knowledge-categories/',
    method: 'post',
    data
  })
}

export function updateKnowledgeCategory(id: number, data: any) {
  return request({
    url: `/projects/knowledge-categories/${id}/`,
    method: 'put',
    data
  })
}

export function deleteKnowledgeCategory(id: number) {
  return request({
    url: `/projects/knowledge-categories/${id}/`,
    method: 'delete'
  })
}

// =============== 知识文章 ===============
export function getKnowledgeArticleList(params?: Record<string, any>) {
  return request({
    url: '/projects/knowledge-articles/',
    method: 'get',
    params
  })
}

export function getKnowledgeArticle(id: number) {
  return request({
    url: `/projects/knowledge-articles/${id}/`,
    method: 'get'
  })
}

export function createKnowledgeArticle(data: any) {
  return request({
    url: '/projects/knowledge-articles/',
    method: 'post',
    data
  })
}

export function updateKnowledgeArticle(id: number, data: any) {
  return request({
    url: `/projects/knowledge-articles/${id}/`,
    method: 'put',
    data
  })
}

export function deleteKnowledgeArticle(id: number) {
  return request({
    url: `/projects/knowledge-articles/${id}/`,
    method: 'delete'
  })
}

export function getKnowledgeArticleStatistics() {
  return request({
    url: '/projects/knowledge-articles/statistics/',
    method: 'get'
  })
}

export function publishKnowledgeArticle(id: number) {
  return request({
    url: `/projects/knowledge-articles/${id}/publish/`,
    method: 'post'
  })
}

export function likeKnowledgeArticle(id: number) {
  return request({
    url: `/projects/knowledge-articles/${id}/like/`,
    method: 'post'
  })
}

export function searchKnowledgeArticles(keyword: any) {
  return request({
    url: '/projects/knowledge-articles/search/',
    method: 'get',
    params: { q: keyword }
  })
}

// =============== 项目归档 ===============
export function getProjectArchiveList(params?: Record<string, any>) {
  return request({
    url: '/projects/project-archives/',
    method: 'get',
    params
  })
}

export function getProjectArchive(id: number) {
  return request({
    url: `/projects/project-archives/${id}/`,
    method: 'get'
  })
}

export function createProjectArchive(data: any) {
  return request({
    url: '/projects/project-archives/',
    method: 'post',
    data
  })
}

export function updateProjectArchive(id: number, data: any) {
  return request({
    url: `/projects/project-archives/${id}/`,
    method: 'put',
    data
  })
}

export function submitProjectArchiveReview(id: number) {
  return request({
    url: `/projects/project-archives/${id}/submit_review/`,
    method: 'post'
  })
}

export function approveProjectArchive(id: number, data: any) {
  return request({
    url: `/projects/project-archives/${id}/approve/`,
    method: 'post',
    data
  })
}

export function rejectProjectArchive(id: number, data: any) {
  return request({
    url: `/projects/project-archives/${id}/reject/`,
    method: 'post',
    data
  })
}

export function generateKnowledgeFromArchive(id: number) {
  return request({
    url: `/projects/project-archives/${id}/generate_knowledge/`,
    method: 'post'
  })
}

// =============== 技术问题 ===============
export function getTechnicalIssueList(params?: Record<string, any>) {
  return request({
    url: '/projects/technical-issues/',
    method: 'get',
    params
  })
}

export function getTechnicalIssue(id: number) {
  return request({
    url: `/projects/technical-issues/${id}/`,
    method: 'get'
  })
}

export function createTechnicalIssue(data: any) {
  return request({
    url: '/projects/technical-issues/',
    method: 'post',
    data
  })
}

export function updateTechnicalIssue(id: number, data: any) {
  return request({
    url: `/projects/technical-issues/${id}/`,
    method: 'put',
    data
  })
}

export function resolveTechnicalIssue(id: number, data: any) {
  return request({
    url: `/projects/technical-issues/${id}/resolve/`,
    method: 'post',
    data
  })
}

export function convertIssueToKnowledge(id: number) {
  return request({
    url: `/projects/technical-issues/${id}/convert_to_knowledge/`,
    method: 'post'
  })
}

// =============== 标准部件 ===============
export function getStandardComponentList(params?: Record<string, any>) {
  return request({
    url: '/projects/standard-components/',
    method: 'get',
    params
  })
}

export function getStandardComponent(id: number) {
  return request({
    url: `/projects/standard-components/${id}/`,
    method: 'get'
  })
}

export function createStandardComponent(data: any) {
  return request({
    url: '/projects/standard-components/',
    method: 'post',
    data
  })
}

export function updateStandardComponent(id: number, data: any) {
  return request({
    url: `/projects/standard-components/${id}/`,
    method: 'put',
    data
  })
}

export function useStandardComponent(id: number) {
  return request({
    url: `/projects/standard-components/${id}/use/`,
    method: 'post'
  })
}

export function activateStandardComponent(id: number) {
  return request({
    url: `/projects/standard-components/${id}/activate/`,
    method: 'post'
  })
}

export function deprecateStandardComponent(id: number) {
  return request({
    url: `/projects/standard-components/${id}/deprecate/`,
    method: 'post'
  })
}
