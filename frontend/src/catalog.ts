import { all } from './api'
import { computed, watch } from 'vue'
import { user } from './session'
import type { Row, Option } from './types'
export type Catalog = { projects: Row[]; items: Row[]; partners: Row[]; users: Row[] }
export async function catalog(
  keys: (keyof Catalog)[] = ['projects', 'items', 'partners', 'users'],
): Promise<Catalog> {
  const result: Catalog = { projects: [], items: [], partners: [], users: [] }
  const paths = {
    projects: '/business/projects/',
    items: '/business/items/',
    partners: '/business/partners/',
    users: '/auth/directory/',
  }
  await Promise.all(
    keys.map(async (key) => {
      result[key] = await all(
        paths[key],
        ['items', 'partners'].includes(key) ? { is_active: true } : {},
      )
    }),
  )
  return result
}
export function referenceLabel(row: Row): { name: string; detail: string } {
  const name = row.name || row.display_name || row.username || row.code || `记录 ${row.id}`
  return {
    name,
    detail: [row.username !== name ? row.username : '', row.code !== name ? row.code : '', row.specification,
      row.drawing_number, row.drawing_revision, row.brand, row.unit].filter(Boolean).join(' · '),
  }
}
export const options = (rows: Row[]): Option[] => rows.map(row => {
  const { name, detail } = referenceLabel(row)
  // 人员选项沿用「姓名（账号）」，同名时不猜测匹配。
  return { value: row.id, label: row.username && !row.name
    ? [name !== row.username ? `${name}（${row.username}）` : name, row.code].filter(Boolean).join(' · ')
    : [name, detail].filter(Boolean).join(' · ') }
})

export const referenceSession = computed(() => user.value?.id == null ? '' : JSON.stringify([
  user.value.id, user.value.roles ?? [user.value.role],
]))
// 仅在本次登录会话内记 ID；不向共享电脑的持久化存储写入名称或历史。
const recent = new Map<string, string[]>()
watch(referenceSession, () => recent.clear(), { flush: 'sync' })
window.addEventListener('erp-session', () => recent.clear())
export function rememberReference(path: string, id: string | number) {
  if (!referenceSession.value) return
  recent.set(path, [String(id), ...(recent.get(path) ?? []).filter(value => value !== String(id))].slice(0, 5))
}
export function recentReferences(path: string, authorizedRows: Row[]): Row[] {
  if (!referenceSession.value) return []
  // 只从刚取回、已按当前权限与筛选校验的结果中重建，绝不展示缓存快照。
  return (recent.get(path) ?? []).flatMap(id => {
    const row = authorizedRows.find(value => String(value.id) === id)
    return row ? [row] : []
  })
}
