/**
 * 核心功能 API - 附件管理、导出等
 */
import request from '@/utils/request'

// ========== 附件管理 ==========
export function getAttachmentList(params?: Record<string, any>) {
  return request({ url: '/core/attachments/', method: 'get', params })
}

export function uploadAttachment(data: any, config: any) {
  return request({ url: '/core/attachments/', method: 'post', data, ...config })
}

export function batchUploadAttachments(data: any, config: any) {
  return request({ url: '/core/attachments/batch_upload/', method: 'post', data, ...config })
}

export function deleteAttachment(id: number) {
  return request({ url: `/core/attachments/${id}/`, method: 'delete' })
}

export function downloadAttachment(id: number) {
  return request({ url: `/core/attachments/${id}/download/`, method: 'get', responseType: 'blob' })
}

// ========== 导出 ==========
export function exportARReport(params?: Record<string, any>) {
  return request({ url: '/core/export/ar/', method: 'get', params, responseType: 'blob' })
}

export function exportAPReport(params?: Record<string, any>) {
  return request({ url: '/core/export/ap/', method: 'get', params, responseType: 'blob' })
}

// ========== 物料分类 ==========
export function getItemCategoryTree(params?: Record<string, any>) {
  return request({ url: '/masterdata/item-categories/', method: 'get', params })
}

// ========== 通知渠道 ==========
export function getNotificationChannelStatus() {
  return request({ url: '/core/notification-channels/status/', method: 'get' })
}

export function testDingTalk(data: any) {
  return request({ url: '/core/notification-channels/test_dingtalk/', method: 'post', data })
}

export function testWeChatWork(data: any) {
  return request({ url: '/core/notification-channels/test_wechat_work/', method: 'post', data })
}

export function broadcastNotification(data: any) {
  return request({ url: '/core/notification-channels/broadcast/', method: 'post', data })
}

// ========== 通知 ==========
export function getNotifications(params?: Record<string, any>) {
  return request({ url: '/core/notifications/', method: 'get', params })
}
export function markNotificationRead(id: number) {
  return request({ url: `/core/notifications/${id}/mark_read/`, method: 'post' })
}
export function markAllNotificationsRead() {
  return request({ url: '/core/notifications/mark_all_read/', method: 'post' })
}
export function getUnreadCount() {
  return request({ url: '/core/notifications/unread_count/', method: 'get' })
}

// ========== 审计日志 ==========
export function getAuditLogs(params?: Record<string, any>) {
  return request({ url: '/core/audit-logs/', method: 'get', params })
}
