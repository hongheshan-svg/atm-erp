/**
 * Security API - Login logs, password policy, sensitive operations
 */
import request from '@/utils/request'

// Login Logs
export function getLoginLogs(params) {
  return request({
    url: '/core/login-logs/',
    method: 'get',
    params
  })
}

export function getMyLoginHistory() {
  return request({
    url: '/core/login-logs/my_history/',
    method: 'get'
  })
}

export function getLoginStatistics(days = 7) {
  return request({
    url: '/core/login-logs/statistics/',
    method: 'get',
    params: { days }
  })
}

// Sensitive Operations
export function getSensitiveOperations(params) {
  return request({
    url: '/core/sensitive-operations/',
    method: 'get',
    params
  })
}

// Password Policy
export function getPasswordPolicy() {
  return request({
    url: '/core/password-policy/policy/',
    method: 'get'
  })
}

export function validatePassword(password) {
  return request({
    url: '/core/password-policy/validate/',
    method: 'post',
    data: { password }
  })
}

export function checkPasswordExpiry() {
  return request({
    url: '/core/password-policy/check_expiry/',
    method: 'get'
  })
}
