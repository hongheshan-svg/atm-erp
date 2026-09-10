import { all } from './api'
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
export const options = (rows: Row[]): Option[] =>
  rows.map((r) => ({
    value: r.id,
    label: [r.code, r.name || r.display_name || r.username, r.specification, r.brand, r.unit].filter(Boolean).join(' · '),
  }))
