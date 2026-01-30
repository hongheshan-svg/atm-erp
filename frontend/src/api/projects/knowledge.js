/**
 * 知识库管理 API
 */
import request from '@/utils/request'

// =============== 知识分类 ===============
export function getKnowledgeCategoryList(params) {
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

export function createKnowledgeCategory(data) {
  return request({
    url: '/projects/knowledge-categories/',
    method: 'post',
    data
  })
}

export function updateKnowledgeCategory(id, data) {
  return request({
    url: `/projects/knowledge-categories/${id}/`,
    method: 'put',
    data
  })
}

export function deleteKnowledgeCategory(id) {
  return request({
    url: `/projects/knowledge-categories/${id}/`,
    method: 'delete'
  })
}

// =============== 知识文章 ===============
export function getKnowledgeArticleList(params) {
  return request({
    url: '/projects/knowledge-articles/',
    method: 'get',
    params
  })
}

export function getKnowledgeArticle(id) {
  return request({
    url: `/projects/knowledge-articles/${id}/`,
    method: 'get'
  })
}

export function createKnowledgeArticle(data) {
  return request({
    url: '/projects/knowledge-articles/',
    method: 'post',
    data
  })
}

export function updateKnowledgeArticle(id, data) {
  return request({
    url: `/projects/knowledge-articles/${id}/`,
    method: 'put',
    data
  })
}

export function deleteKnowledgeArticle(id) {
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

export function publishKnowledgeArticle(id) {
  return request({
    url: `/projects/knowledge-articles/${id}/publish/`,
    method: 'post'
  })
}

export function likeKnowledgeArticle(id) {
  return request({
    url: `/projects/knowledge-articles/${id}/like/`,
    method: 'post'
  })
}

export function searchKnowledgeArticles(keyword) {
  return request({
    url: '/projects/knowledge-articles/search/',
    method: 'get',
    params: { q: keyword }
  })
}

// =============== 项目归档 ===============
export function getProjectArchiveList(params) {
  return request({
    url: '/projects/project-archives/',
    method: 'get',
    params
  })
}

export function getProjectArchive(id) {
  return request({
    url: `/projects/project-archives/${id}/`,
    method: 'get'
  })
}

export function createProjectArchive(data) {
  return request({
    url: '/projects/project-archives/',
    method: 'post',
    data
  })
}

export function updateProjectArchive(id, data) {
  return request({
    url: `/projects/project-archives/${id}/`,
    method: 'put',
    data
  })
}

export function submitProjectArchiveReview(id) {
  return request({
    url: `/projects/project-archives/${id}/submit_review/`,
    method: 'post'
  })
}

export function approveProjectArchive(id, data) {
  return request({
    url: `/projects/project-archives/${id}/approve/`,
    method: 'post',
    data
  })
}

export function rejectProjectArchive(id, data) {
  return request({
    url: `/projects/project-archives/${id}/reject/`,
    method: 'post',
    data
  })
}

export function generateKnowledgeFromArchive(id) {
  return request({
    url: `/projects/project-archives/${id}/generate_knowledge/`,
    method: 'post'
  })
}

// =============== 技术问题 ===============
export function getTechnicalIssueList(params) {
  return request({
    url: '/projects/technical-issues/',
    method: 'get',
    params
  })
}

export function getTechnicalIssue(id) {
  return request({
    url: `/projects/technical-issues/${id}/`,
    method: 'get'
  })
}

export function createTechnicalIssue(data) {
  return request({
    url: '/projects/technical-issues/',
    method: 'post',
    data
  })
}

export function updateTechnicalIssue(id, data) {
  return request({
    url: `/projects/technical-issues/${id}/`,
    method: 'put',
    data
  })
}

export function resolveTechnicalIssue(id, data) {
  return request({
    url: `/projects/technical-issues/${id}/resolve/`,
    method: 'post',
    data
  })
}

export function convertIssueToKnowledge(id) {
  return request({
    url: `/projects/technical-issues/${id}/convert_to_knowledge/`,
    method: 'post'
  })
}

// =============== 标准部件 ===============
export function getStandardComponentList(params) {
  return request({
    url: '/projects/standard-components/',
    method: 'get',
    params
  })
}

export function getStandardComponent(id) {
  return request({
    url: `/projects/standard-components/${id}/`,
    method: 'get'
  })
}

export function createStandardComponent(data) {
  return request({
    url: '/projects/standard-components/',
    method: 'post',
    data
  })
}

export function updateStandardComponent(id, data) {
  return request({
    url: `/projects/standard-components/${id}/`,
    method: 'put',
    data
  })
}

export function useStandardComponent(id) {
  return request({
    url: `/projects/standard-components/${id}/use/`,
    method: 'post'
  })
}

export function activateStandardComponent(id) {
  return request({
    url: `/projects/standard-components/${id}/activate/`,
    method: 'post'
  })
}

export function deprecateStandardComponent(id) {
  return request({
    url: `/projects/standard-components/${id}/deprecate/`,
    method: 'post'
  })
}
