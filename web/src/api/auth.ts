import request from '@/utils/request'
import type { LoginResult, UserProfile } from '@/types'

// 登录:POST /auth/login -> { access, refresh, user }。
export function login(username: string, password: string): Promise<LoginResult> {
  return request.post<LoginResult>('/auth/login', { username, password })
}

// 刷新 token:POST /auth/refresh -> { access }。
export function refresh(refreshToken: string): Promise<{ access: string }> {
  return request.post<{ access: string }>('/auth/refresh', { refresh: refreshToken })
}

// 拉取当前用户档案:GET /auth/profile -> UserProfile(含 permissions/menus/data_scopes)。
export function getProfile(): Promise<UserProfile> {
  return request.get<UserProfile>('/auth/profile')
}
