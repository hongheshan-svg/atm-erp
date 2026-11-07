import { afterEach, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import AttachmentDialog from './AttachmentDialog.vue'
import RecordDeletionDialog from './RecordDeletionDialog.vue'
import ListPagination from './ListPagination.vue'
import { read } from '../api'
import { pageSize } from '../pagination'
import { user } from '../session'

vi.mock('../api', () => ({ read: vi.fn(), download: vi.fn(), write: vi.fn(), all: vi.fn().mockResolvedValue([]) }))
const make = () => mount(AttachmentDialog, {
  props: { owner: 'sale', record: { id: 1, code: 'SO1', status: 'draft' } },
  global: { plugins: [ElementPlus], stubs: { ElDialog: { template: '<section><slot /></section>' }, ActionDialog: true, RecordDeletionDialog: true } },
})
afterEach(() => { user.value = null; vi.resetAllMocks() })

it('附件跨页勾选与全选仅包含当前单据，切换单据清空选择与确认', async () => {
  user.value = { roles: ['admin'] }
  pageSize.value = 10
  const rows = Array.from({ length: 21 }, (_, i) => ({ id: i + 1, original_name: '附件' + i, size: 1, created_at: '2026-11-07T00:00:00Z' }))
  vi.mocked(read).mockImplementation(async (_path, params = {}) => ({
    count: 21, results: rows.slice((Number(params.page) - 1) * Number(params.page_size), Number(params.page) * Number(params.page_size)),
    next: Number(params.page) * Number(params.page_size) < rows.length ? 'next' : null,
  }))
  const wrapper = make()
  await flushPromises()
  await wrapper.get('[aria-label="选择本页附件"]').setValue(true)
  wrapper.getComponent(ListPagination).vm.$emit('change', 2)
  await flushPromises()
  await wrapper.get('[aria-label="选择本页附件"]').setValue(true)
  expect(wrapper.get('[aria-label="附件批量选择"]').text()).toContain('已选 20')
  await wrapper.findAll('button').find(button => button.text() === '全选筛选结果（21项，跨页）')!.trigger('click')
  await flushPromises()
  expect(read).toHaveBeenLastCalledWith('/business/documents/', { sale: 1, page: 1, page_size: 200 })
  await wrapper.findAll('button').find(button => button.text() === '批量删除（21）')!.trigger('click')
  expect(wrapper.getComponent(RecordDeletionDialog).props('rows')).toHaveLength(21)
  await wrapper.setProps({ owner: 'purchase', record: { id: 2, code: 'PO2' } })
  await flushPromises()
  expect(wrapper.get('[aria-label="附件批量选择"]').text()).toContain('已选 0')
  expect(wrapper.findComponent(RecordDeletionDialog).exists()).toBe(false)
  expect(read).toHaveBeenLastCalledWith('/business/documents/', { purchase: 2, page: 1, page_size: 10 })
  user.value = { roles: ['purchaser'] }
  await flushPromises()
  expect(wrapper.find('[aria-label="附件批量选择"]').exists()).toBe(false)
  wrapper.unmount()
})

it('附件全选中切换单据时忽略旧单据的迟到结果', async () => {
  user.value = { roles: ['admin'] }
  vi.mocked(read).mockResolvedValue({ count: 21, results: [], next: null })
  const wrapper = make()
  await flushPromises()
  let finish!: (value: object) => void
  vi.mocked(read).mockImplementationOnce(() => new Promise(resolve => { finish = resolve }))
  await wrapper.findAll('button').find(button => button.text() === '全选筛选结果（21项，跨页）')!.trigger('click')
  await wrapper.setProps({ record: { id: 2, code: 'SO2' } })
  await flushPromises()
  finish({ results: [{ id: 99 }], next: null })
  await flushPromises()
  expect(wrapper.get('[aria-label="附件批量选择"]').text()).toContain('已选 0')
  wrapper.unmount()
})
