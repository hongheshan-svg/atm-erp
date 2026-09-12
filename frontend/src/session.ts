import { ref } from 'vue'
import { read, write } from './api'
import { resetSession } from './utils/request'
import type { Row } from './types'
export const user = ref<Row | null>(null)
export const roleLabels: Record<string, string> = {
  admin: '管理员', manager: '项目经理', sales_manager: '销售经理',
  purchase_manager: '采购经理', purchaser: '采购员',
  mechanical_engineer: '机械工程师', electrical_engineer: '电气工程师',
  production_manager: '生产经理',
  warehouse: '仓管', finance: '财务', member: '普通成员',
}
export const hasRoles = (profile: Row | null | undefined, roles: string[]) => roles.some(role => (profile?.roles ?? [profile?.role]).includes(role))
export const can = (roles: string[]) => hasRoles(user.value, roles)
export const manager = () => can(['admin', 'manager'])
export const engineer = () => can(['mechanical_engineer', 'electrical_engineer'])
export const production = () => can(['production_manager'])
export const productionProject = (record?: Row) => manager() ? record?.can_manage_production !== false : production() && record?.can_manage_production === true
export const taskManager = (record: Row) => manager() ? record.can_manage !== false : production() && ['assembly', 'test', 'install', 'service'].includes(record.kind) && record.can_manage === true
export const timeAmender = (record: Row) => {
  const own = user.value?.id != null && record.user === user.value.id
  return (manager() || production() || own) && (record.can_amend ?? (manager() || own))
}
export const serviceRegistrar = (record: Row) => manager() ? (record.can_register_service ?? record.can_manage !== false) : production() && record.can_register_service === true
export const purchasing = () => can(['admin', 'manager', 'purchase_manager', 'purchaser'])
export const purchaseReader = () => purchasing() || can(['warehouse', 'finance'])
export const materialEditor = () => purchasing() || engineer()
export const partnerEditor = () => purchasing() || can(['sales_manager'])
export const bomEditor = (record?: Row) => manager() ? record?.can_edit_bom !== false : engineer() && record?.can_edit_bom === true
export const purchaseApprover = (record: Row) => can(['admin', 'manager', 'purchase_manager']) && (record.can_approve ?? (manager() && record.can_manage !== false))
export const money = () => can(['admin', 'manager', 'finance'])
export const reports = () => can(['admin']) || (can(['manager']) && user.value?.management_reports === true)
export const salesOnly = () => can(['sales_manager']) && !manager()
export const customerOnly = () => can(['sales_manager']) && !purchasing()
export const operations = () => purchaseReader() || can(['member']) || engineer() || production()
export function canImportResource(resource: string) {
  if (resource === 'items') return materialEditor()
  if (resource === 'partners') return partnerEditor()
  if (resource === 'purchases') return purchasing()
  if (resource === 'time') return operations()
  const roles: Record<string, string[]> = {
    'bank-records': ['admin', 'finance'], sales: ['admin', 'manager', 'sales_manager'],
    projects: ['admin', 'manager'], tasks: ['admin', 'manager'], stocks: ['admin'],
    entries: ['admin', 'finance'], payments: ['admin', 'finance'],
    moves: ['admin', 'warehouse'], deliveries: ['admin', 'manager'],
  }
  return !!roles[resource] && can(roles[resource]!)
}
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
