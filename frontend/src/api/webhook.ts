import request from '@/utils/request'

export function getWebhooks(params?: Record<string, any>) {
  return request({ url: '/core/webhooks/', method: 'get', params })
}

export function getWebhook(id: number) {
  return request({ url: `/core/webhooks/${id}/`, method: 'get' })
}

export function createWebhook(data: any) {
  return request({ url: '/core/webhooks/', method: 'post', data })
}

export function updateWebhook(id: number, data: any) {
  return request({ url: `/core/webhooks/${id}/`, method: 'put', data })
}

export function deleteWebhook(id: number) {
  return request({ url: `/core/webhooks/${id}/`, method: 'delete' })
}

export function toggleWebhook(id: number) {
  return request({ url: `/core/webhooks/${id}/toggle/`, method: 'post' })
}

export function testWebhook(id: number) {
  return request({ url: `/core/webhooks/${id}/test/`, method: 'post' })
}

export function getEventTypes() {
  return request({ url: '/core/webhooks/event_types/', method: 'get' })
}
