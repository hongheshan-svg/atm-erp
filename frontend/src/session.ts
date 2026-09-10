import { ref } from 'vue'
import { read, write } from './api'
import { resetSession } from './utils/request'
import type { Row } from './types'
export const user = ref<Row | null>(null)
export const hasRoles = (profile: Row | null | undefined, roles: string[]) => roles.some(role => (profile?.roles ?? [profile?.role]).includes(role))
export const can = (roles: string[]) => hasRoles(user.value, roles)
export const manager = () => can(['admin', 'manager'])
export const money = () => can(['admin', 'manager', 'finance'])
export const reports = () => can(['admin']) || (can(['manager']) && user.value?.management_reports === true)
export const salesOnly = () => can(['sales_manager']) && !manager()
export const customerOnly = () => can(['sales_manager']) && !can(['admin', 'manager', 'purchaser'])
export const operations = () => can(['admin', 'manager', 'purchaser', 'warehouse', 'finance', 'member'])
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
