import { ref } from 'vue'
import { clearFormDrafts } from './form-experience'
import { read, write } from './api'
import { resetSession, requestKey } from './utils/request'
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
// 生产经理管理的任务类型（装配、调试、安装、售后），与后端 PRODUCTION_TASK_KINDS 同一份。
export const productionTaskKinds = ['assembly', 'test', 'install', 'service']
export const taskManager = (record: Row) => manager() ? record.can_manage !== false : production() && productionTaskKinds.includes(record.kind) && record.can_manage === true
export const timeAmender = (record: Row) => record.can_amend === true
export const taskConfirmer = (record: Row) => record.can_confirm === true
export const serviceRegistrar = (record: Row) => manager() ? (record.can_register_service ?? record.can_manage !== false) : production() && record.can_register_service === true
export const purchasing = () => can(['admin', 'manager', 'purchase_manager', 'purchaser'])
export const purchaseReader = () => purchasing() || can(['warehouse', 'finance'])
export const materialEditor = () => purchasing() || engineer()
export const partnerEditor = () => purchasing() || can(['sales_manager'])
export const bomEditor = (record?: Row) => manager() ? record?.can_edit_bom !== false : engineer() && record?.can_edit_bom === true
export const purchaseApprover = (record: Row) => can(['admin', 'manager', 'purchase_manager']) && (record.can_approve ?? (manager() && record.can_manage !== false))
export const money = () => can(['admin', 'manager', 'finance'])
// 采购合同预览：与后端 purchase_contract.preview 的 MONEY_READERS | PURCHASERS 一致；仓管可读采购单但不能预览合同。
export const contractReader = () => purchasing() || money()
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
    projects: ['admin', 'manager'], tasks: ['admin', 'manager', 'production_manager'], stocks: ['admin'],
    reconciliations: ['admin', 'finance'], entries: ['admin', 'finance'], payments: ['admin', 'finance'],
    moves: ['admin', 'warehouse'], deliveries: ['admin', 'manager'],
  }
  return !!roles[resource] && can(roles[resource]!)
}
window.addEventListener('erp-session', () => {
  clearFormDrafts()
  user.value = null
})
// 其他标签页换成另一账号登录（见 utils/request.ts 的 syncSession）：原账号的资料与暂存已随 erp-session 清掉，
// 整页载入新账号的工作台，菜单、权限和各模块缓存全部按新账号重建；原页面地址可能是新账号无权查看的单据。
window.addEventListener('erp-session-replaced', () => window.location.replace(import.meta.env.BASE_URL))
export async function loadUser() {
  user.value = await read('/auth/me/')
}
export async function login(username: string, password: string) {
  resetSession()
  const tokens = await write('/auth/login/', { username, password }, requestKey())
  resetSession(tokens.access, tokens.refresh)
  await loadUser()
}
export const logout = () => resetSession()
