import request from '@/utils/request'

export function login(username: string, password: string) {
  return request({
    url: '/auth/login/',
    method: 'post',
    data: { username, password }
  })
}

export function getUserProfile() {
  return request({ url: '/auth/users/profile/', method: 'get' })
}

// ===== 企业 IM 扫码登录(企业微信/钉钉/飞书)=====

export interface OAuthProvider {
  platform: 'wecom' | 'dingtalk' | 'feishu'
  name: string
  enabled: boolean
}

export interface OAuthBinding {
  platform: 'wecom' | 'dingtalk' | 'feishu'
  name: string
  enabled: boolean
  bound: boolean
}

export function getOAuthProviders() {
  return request({ url: '/auth/oauth/providers', method: 'get' })
}

// mode='bind' 用于「鉴权态自助绑定」(回调走绑定而非登录);默认登录。
export function getOAuthLoginUrl(platform: string, mode: 'login' | 'bind' = 'login') {
  return request({ url: `/auth/oauth/${platform}/login-url`, method: 'get', params: mode === 'bind' ? { mode } : {} })
}

export function oauthCallback(platform: string, data: { code: string; state: string }) {
  return request({ url: `/auth/oauth/${platform}/callback`, method: 'post', data })
}

// ===== 自助绑定(需登录)=====

export function getOAuthBindings() {
  return request({ url: '/auth/oauth/bindings', method: 'get' })
}

export function oauthBind(platform: string, data: { code: string; state: string }) {
  return request({ url: `/auth/oauth/${platform}/bind`, method: 'post', data })
}

export function oauthUnbind(platform: string) {
  return request({ url: `/auth/oauth/${platform}/bind`, method: 'delete' })
}

export function updateProfile(data: any) {
  return request({ url: '/auth/users/update_profile/', method: 'put', data })
}

export function changePassword(data: { old_password: string; new_password: string }) {
  return request({ url: '/auth/users/change_password/', method: 'post', data })
}

export function getUsers(params?: Record<string, any>) {
  return request({ url: '/auth/users/', method: 'get', params })
}

export function createUser(data: any) {
  return request({ url: '/auth/users/', method: 'post', data })
}

export function updateUser(id: number, data: any) {
  return request({ url: `/auth/users/${id}/`, method: 'put', data })
}

export function deleteUser(id: number) {
  return request({ url: `/auth/users/${id}/`, method: 'delete' })
}

export function getRoles(params?: Record<string, any>) {
  return request({ url: '/auth/roles/', method: 'get', params })
}

export function getDepartments(params?: Record<string, any>) {
  return request({ url: '/auth/departments/', method: 'get', params })
}

export function getDepartmentTree() {
  return request({ url: '/auth/departments/tree/', method: 'get' })
}

export function createRole(data: any) {
  return request({ url: '/auth/roles/', method: 'post', data })
}

export function updateRole(id: number, data: any) {
  return request({ url: `/auth/roles/${id}/`, method: 'put', data })
}

export function deleteRole(id: number) {
  return request({ url: `/auth/roles/${id}/`, method: 'delete' })
}

export function createDepartment(data: any) {
  return request({ url: '/auth/departments/', method: 'post', data })
}

export function updateDepartment(id: number, data: any) {
  return request({ url: `/auth/departments/${id}/`, method: 'put', data })
}

export function deleteDepartment(id: number) {
  return request({ url: `/auth/departments/${id}/`, method: 'delete' })
}

export function getDepartmentUsers(deptId: number) {
  return request({ url: '/auth/users/', method: 'get', params: { department: deptId } })
}
