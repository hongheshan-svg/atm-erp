import { ref } from 'vue'
import { read, write } from './api'
import { resetSession } from './utils/request'
import type { Row } from './types'
export const user = ref<Row | null>(null)
export const manager = () => ['admin', 'manager'].includes(user.value?.role)
export const money = () => ['admin', 'manager', 'finance'].includes(user.value?.role)
export const can = (roles: string[]) => roles.includes(user.value?.role)
window.addEventListener('erp-session', () => {
  user.value = null
})
export async function loadUser() {
  user.value = await read('/auth/me/')
}
export async function login(username: string, password: string) {
  resetSession()
  const tokens = await write('/auth/login/', { username, password }, crypto.randomUUID())
  resetSession(tokens.access, tokens.refresh)
  await loadUser()
}
export const logout = () => resetSession()
