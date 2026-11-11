import { computed, type Ref } from 'vue'
import type { Row } from '../types'

// Use stable record IDs, so equal materials in different BOM units remain separate.
export function useBatchSelection(rows: Ref<Row[]>, key: string, limit: () => number) {
  const ids = computed(() => new Set(rows.value.map(row => row[key])))
  const has = (row: Row) => ids.value.has(row[key])
  const all = (page: Row[]) => page.length > 0 && page.every(has)
  const some = (page: Row[]) => page.some(has) && !all(page)
  const selectable = (row: Row) => has(row) || rows.value.length < limit()
  function replace(next: Row[]) {
    rows.value = [...new Map(next.map(row => [row[key], row])).values()].slice(0, limit())
  }
  function toggle(row: Row) {
    if (has(row)) rows.value = rows.value.filter(current => current[key] !== row[key])
    else if (selectable(row)) rows.value = [...rows.value, row]
  }
  function togglePage(page: Row[]) {
    if (all(page)) {
      const pageIds = new Set(page.map(row => row[key]))
      rows.value = rows.value.filter(row => !pageIds.has(row[key]))
    } else replace([...rows.value, ...page])
  }
  async function replacePages(
    fetchPage: (page: number, size: number) => Promise<{ results: Row[]; next?: unknown }>,
    isCurrent: () => boolean,
  ) {
    const result: Row[] = []
    const maximum = limit()
    // 每页固定 200 条（服务端上限）：中途改小页大小会让 page 编号错位，重复或漏掉记录；超出部分在最后截掉。
    for (let page = 1; result.length < maximum; page++) {
      const data = await fetchPage(page, 200)
      if (!isCurrent()) return
      result.push(...data.results)
      if (!data.next || !data.results.length) break
    }
    if (isCurrent()) replace(result.slice(0, maximum))
  }
  return { has, all, some, selectable, replace, toggle, togglePage, replacePages }
}
