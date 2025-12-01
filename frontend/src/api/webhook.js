/**
 * Webhook API - Endpoint management and delivery tracking
 */
import request from '@/utils/request'

// Webhook Endpoints
export function getWebhooks(params) {
  return request({
    url: '/core/webhooks/',
    method: 'get',
    params
  })
}

export function getWebhook(id) {
  return request({
    url: `/core/webhooks/${id}/`,
    method: 'get'
  })
}

export function createWebhook(data) {
  return request({
    url: '/core/webhooks/',
    method: 'post',
    data
  })
}

export function updateWebhook(id, data) {
  return request({
    url: `/core/webhooks/${id}/`,
    method: 'put',
    data
  })
}

export function deleteWebhook(id) {
  return request({
    url: `/core/webhooks/${id}/`,
    method: 'delete'
  })
}

export function testWebhook(id) {
  return request({
    url: `/core/webhooks/${id}/test/`,
    method: 'post'
  })
}

export function toggleWebhook(id) {
  return request({
    url: `/core/webhooks/${id}/toggle/`,
    method: 'post'
  })
}

export function getEventTypes() {
  return request({
    url: '/core/webhooks/event_types/',
    method: 'get'
  })
}

// Webhook Deliveries
export function getDeliveries(params) {
  return request({
    url: '/core/webhook-deliveries/',
    method: 'get',
    params
  })
}

export function getDelivery(id) {
  return request({
    url: `/core/webhook-deliveries/${id}/`,
    method: 'get'
  })
}

export function retryDelivery(id) {
  return request({
    url: `/core/webhook-deliveries/${id}/retry/`,
    method: 'post'
  })
}

export function getDeliveryStatistics(days = 7) {
  return request({
    url: '/core/webhook-deliveries/statistics/',
    method: 'get',
    params: { days }
  })
}
