import { ref } from 'vue'
import { expect, it, vi } from 'vitest'
import { useBatchSelection } from './batch-selection'
import type { Row } from '../types'

it('翻页全选和取消仅影响本页，同物料不同单元按BOM行号独立选择', () => {
  const selected = ref<Row[]>([])
  const batch = useBatchSelection(selected, 'bom_line', () => 1000)
  const page1 = Array.from({ length: 10 }, (_, i) => ({ bom_line: i + 1, item: 5 }))
  const page2 = [{ bom_line: 11, item: 5 }]
  batch.togglePage(page1)
  batch.togglePage(page2)
  expect(selected.value).toHaveLength(11)
  batch.togglePage(page1)
  expect(selected.value).toEqual(page2)
  batch.toggle(page1[0]!)
  expect(batch.some(page1)).toBe(true)
  expect(batch.all(page1)).toBe(false)
  batch.toggle(page2[0]!)
  expect(selected.value).toEqual([page1[0]])
})

it('按ID去重并限制1000项，达到上限后仍能取消和补选', () => {
  const selected = ref<Row[]>([])
  const batch = useBatchSelection(selected, 'id', () => 1000)
  const rows = Array.from({ length: 1001 }, (_, i) => ({ id: i + 1 }))
  batch.replace([...rows, rows[0]!])
  expect(selected.value).toHaveLength(1000)
  expect(batch.selectable(rows[1000]!)).toBe(false)
  batch.toggle(rows[1000]!)
  expect(selected.value).toHaveLength(1000)
  batch.toggle(rows[0]!)
  batch.toggle(rows[1000]!)
  expect(selected.value).toHaveLength(1000)
  expect(batch.has(rows[0]!)).toBe(false)
  expect(batch.has(rows[1000]!)).toBe(true)
})

it('分页全选每页都按 200 条读取，上限不是 200 的倍数时截取，不重复也不漏行', async () => {
  const selected = ref<Row[]>([])
  const batch = useBatchSelection(selected, 'id', () => 250)
  const rows = Array.from({ length: 450 }, (_, i) => ({ id: i + 1 }))
  const fetch = vi.fn(async (page: number, size: number) => ({ results: rows.slice((page - 1) * size, page * size), next: page * size < rows.length ? 'more' : null }))
  await batch.replacePages(fetch, () => true)
  expect(fetch.mock.calls).toEqual([[1, 200], [2, 200]])
  expect(selected.value.map(row => row.id)).toEqual(rows.slice(0, 250).map(row => row.id))
})

it('分页全选读取失败或上下文变化时，不应用部分或迟到结果', async () => {
  const selected = ref<Row[]>([{ id: 99 }])
  const batch = useBatchSelection(selected, 'id', () => 1000)
  const fetch = vi.fn().mockResolvedValueOnce({ results: [{ id: 1 }], next: 'page2' }).mockRejectedValueOnce(new Error('网络中断'))
  await expect(batch.replacePages(fetch, () => true)).rejects.toThrow('网络中断')
  expect(selected.value).toEqual([{ id: 99 }])
  let finish!: (value: { results: Row[] }) => void
  let current = true
  const pending = batch.replacePages(() => new Promise(resolve => { finish = resolve }), () => current)
  current = false
  finish({ results: [{ id: 2 }] })
  await pending
  expect(selected.value).toEqual([{ id: 99 }])
})
