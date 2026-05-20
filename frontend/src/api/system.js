/**
 * 系统管理 API
 */
import request from '@/utils/request'

// ========== 公告管理 ==========
export function getAnnouncementList(params) {
  return request({ url: '/core/announcements/', method: 'get', params })
}

export function createAnnouncement(data) {
  return request({ url: '/core/announcements/', method: 'post', data })
}

export function updateAnnouncement(id, data) {
  return request({ url: `/core/announcements/${id}/`, method: 'put', data })
}

export function deleteAnnouncement(id) {
  return request({ url: `/core/announcements/${id}/`, method: 'delete' })
}

export function publishAnnouncement(id) {
  return request({ url: `/core/announcements/${id}/publish/`, method: 'post' })
}

export function withdrawAnnouncement(id) {
  return request({ url: `/core/announcements/${id}/withdraw/`, method: 'post' })
}

// ========== 编码规则 ==========
export function getCodeRuleList(params) {
  return request({ url: '/core/code-rules/', method: 'get', params })
}

export function createCodeRule(data) {
  return request({ url: '/core/code-rules/', method: 'post', data })
}

export function updateCodeRule(id, data) {
  return request({ url: `/core/code-rules/${id}/`, method: 'put', data })
}

export function resetCodeRuleSequence(id) {
  return request({ url: `/core/code-rules/${id}/reset_sequence/`, method: 'post' })
}

export function getCodeRuleHistory(id) {
  return request({ url: `/core/code-rules/${id}/history/`, method: 'get' })
}

export function initDefaultCodeRules() {
  return request({ url: '/core/code-rules/init_default_rules/', method: 'post' })
}

// ========== 自定义字段 ==========
export function getCustomFieldList(params) {
  return request({ url: '/core/custom-field-definitions/', method: 'get', params })
}

export function createCustomField(data) {
  return request({ url: '/core/custom-field-definitions/', method: 'post', data })
}

export function updateCustomField(id, data) {
  return request({ url: `/core/custom-field-definitions/${id}/`, method: 'put', data })
}

export function deleteCustomField(id) {
  return request({ url: `/core/custom-field-definitions/${id}/`, method: 'delete' })
}

export function getSupportedModels() {
  return request({ url: '/core/custom-field-definitions/supported_models/', method: 'get' })
}

export function getFieldTypes() {
  return request({ url: '/core/custom-field-definitions/field_types/', method: 'get' })
}

export function toggleFieldVisible(id) {
  return request({ url: `/core/custom-field-definitions/${id}/toggle_visible/`, method: 'post' })
}

export function batchSortFields(data) {
  return request({ url: '/core/custom-field-definitions/batch_sort/', method: 'post', data })
}

// ========== 数据字典 ==========
export function getDictTypeList(params) {
  return request({ url: '/core/dict-types/', method: 'get', params })
}

export function createDictType(data) {
  return request({ url: '/core/dict-types/', method: 'post', data })
}

export function updateDictType(id, data) {
  return request({ url: `/core/dict-types/${id}/`, method: 'put', data })
}

export function deleteDictType(id) {
  return request({ url: `/core/dict-types/${id}/`, method: 'delete' })
}

export function initSystemDicts() {
  return request({ url: '/core/dict-types/init_system_dicts/', method: 'post' })
}

export function getDictItemList(params) {
  return request({ url: '/core/dict-items/', method: 'get', params })
}

export function createDictItem(data) {
  return request({ url: '/core/dict-items/', method: 'post', data })
}

export function updateDictItem(id, data) {
  return request({ url: `/core/dict-items/${id}/`, method: 'put', data })
}

export function deleteDictItem(id) {
  return request({ url: `/core/dict-items/${id}/`, method: 'delete' })
}

export function setDictItemDefault(id) {
  return request({ url: `/core/dict-items/${id}/set_default/`, method: 'post' })
}

export function toggleDictItemEnable(id) {
  return request({ url: `/core/dict-items/${id}/toggle_enable/`, method: 'post' })
}

// ========== 邮件模板 ==========
export function getEmailTemplateList(params) {
  return request({ url: '/core/email-templates/', method: 'get', params })
}

export function getEmailTemplateTypes() {
  return request({ url: '/core/email-templates/template_types/', method: 'get' })
}

export function createEmailTemplate(data) {
  return request({ url: '/core/email-templates/', method: 'post', data })
}

export function updateEmailTemplate(id, data) {
  return request({ url: `/core/email-templates/${id}/`, method: 'put', data })
}

export function deleteEmailTemplate(id) {
  return request({ url: `/core/email-templates/${id}/`, method: 'delete' })
}

export function toggleEmailTemplate(id) {
  return request({ url: `/core/email-templates/${id}/toggle_enable/`, method: 'post' })
}

export function previewEmailTemplate(id, data) {
  return request({ url: `/core/email-templates/${id}/preview/`, method: 'post', data })
}

export function testSendEmailTemplate(id, data) {
  return request({ url: `/core/email-templates/${id}/test_send/`, method: 'post', data })
}

export function initSystemEmailTemplates() {
  return request({ url: '/core/email-templates/init_system_templates/', method: 'post' })
}

// ========== 系统配置 ==========
export function getSystemConfig() {
  return request({ url: '/core/system-config/', method: 'get' })
}

export function saveSystemConfig(data) {
  return request({ url: '/core/system-config/', method: 'post', data })
}

// ========== 权限 ==========
export function getPermissionTree() {
  return request({ url: '/core/permissions/tree/', method: 'get' })
}
