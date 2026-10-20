import type { Command, Field, Row } from './types'
import { sessionStore } from './utils/storage'

export function wideCommand(command: Command | null) {
  return !!command && !command.readonly && (command.fields.filter(f => !f.hidden).length > 4 || command.fields.some(f => f.type === 'rows'))
}
export function submitLabel(command: Command) {
  if (command.submitLabel) return command.submitLabel
  const labels: Record<string, string> = {
    编辑: '保存修改', 收货: '确认收货并入库', 领料: '确认领料出库', 退料: '确认退料入库', 盘点: '确认盘点结果',
    签约: '确认签约并生成项目', 报价: '保存报价', 新建销售: '保存销售草稿', 新建采购: '保存采购草稿',
    登记收付款: '登记收付款记录', 登记收款: '登记收款记录', 退款: '登记退款记录', 冲销付款: '确认冲销记录',
    提交采购: '提交采购审批', 批准采购: '确认批准采购', 完成任务: '确认完成任务',
  }
  return labels[command.title] || (/^(新增|新建|登记|上传|维护|编辑)/.test(command.title) ? `保存${command.title.replace(/^(新增|新建|登记|上传|维护|编辑)/, '')}` : `确认${command.title}`)
}
export function formSignature(value: Row) {
  return JSON.stringify(value, (_key, v) => v instanceof File ? [v.name, v.size, v.lastModified] : v)
}
function hasSecret(fields: Field[]): boolean {
  return fields.some(f => f.type === 'password' || (f.fields && hasSecret(f.fields)))
}
function draftValues(fields: Field[], data: Row): Row {
  return Object.fromEntries(fields.filter(f => !f.displayOnly && f.type !== 'file' && f.type !== 'password').map(f => [f.key,
    f.type === 'rows' ? (data[f.key] || []).map((row: Row) => draftValues(f.fields || [], row)) : data[f.key],
  ]))
}
export function draftKey(command: Command, userId: unknown) {
  if (!userId || command.readonly || hasSecret(command.fields) || !command.fields.length) return ''
  const context = command.draftScope || JSON.stringify(Object.fromEntries(['project', 'sale', 'purchase', 'entry', 'stock', 'supplier', 'month'].filter(key => command.initial?.[key] != null).map(key => [key, command.initial![key]])))
  return `erp-form-draft:${userId}:${command.method || 'post'}:${command.path}:${command.title}:${context}:${command.subject || ''}`
}
export function saveDraft(key: string, command: Command, data: Row) {
  if (!key) return false
  sessionStore.set(key, JSON.stringify({ at: Date.now(), initial: formSignature(command.initial || {}), values: draftValues(command.fields, data) }))
  const saved = loadDraft(key, command)
  return saved != null && formSignature(saved) === formSignature(draftValues(command.fields, data))
}
export function loadDraft(key: string, command: Command): Row | null {
  if (!key) return null
  try {
    const item = JSON.parse(sessionStore.get(key) || 'null')
    if (!item || Date.now() - item.at > 8 * 60 * 60 * 1000 || item.initial !== formSignature(command.initial || {})) {
      sessionStore.remove(key); return null
    }
    return draftValues(command.fields, item.values)
  } catch { sessionStore.remove(key); return null }
}
export function clearDraft(key: string) { if (key) sessionStore.remove(key) }
export function clearFormDrafts() {
  try {
    for (let i = sessionStorage.length - 1; i >= 0; i--) {
      const key = sessionStorage.key(i)
      if (key?.startsWith('erp-form-draft:')) sessionStorage.removeItem(key)
    }
  } catch { /* Storage can be unavailable; drafts are optional. */ }
}

const navigationGuards = new Set<() => Promise<boolean>>()
export function registerFormGuard(guard: () => Promise<boolean>) {
  navigationGuards.add(guard)
  return () => navigationGuards.delete(guard)
}
export async function confirmFormNavigation() {
  for (const guard of navigationGuards) if (!(await guard())) return false
  return true
}
export function savedTarget(command: Command, result: Row, _selectedId?: number | null) {
  const parts = command.path.split('/').filter(Boolean)
  let resource = parts[1] || '', id = Number(parts[2]) || Number(result.id)
  if (!['business', 'auth', 'core'].includes(parts[0] || '')) return null
  if (resource === 'entries' && ['pay', 'refund'].includes(parts[3] || '')) { resource = 'payments'; id = Number(result.id) }
  if (resource === 'sales' && parts[3] === 'sign' && result.project) return { resource: 'projects', id: Number(result.project) }
  if (!Number.isSafeInteger(id) || id <= 0) return null
  return { resource, id }
}
