import { afterEach, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import AttachmentDialog from './AttachmentDialog.vue'
import RecordDeletionDialog from './RecordDeletionDialog.vue'
import AttachmentRemovalDialog from './AttachmentRemovalDialog.vue'
import ListPagination from './ListPagination.vue'
import { read, write } from '../api'
import { pageSize } from '../pagination'
import { user } from '../session'

vi.mock('../api', () => ({ read: vi.fn(), download: vi.fn(), write: vi.fn(), all: vi.fn().mockResolvedValue([]) }))
const make = () => mount(AttachmentDialog, {
  props: { owner: 'sale', record: { id: 1, code: 'SO1', status: 'draft' } },
  global: { plugins: [ElementPlus], stubs: { ElDialog: { template: '<section><slot /></section>' }, ActionDialog: true, RecordDeletionDialog: true, AttachmentRemovalDialog: true } },
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

const mixed = [
  { id: 1, original_name: '比价表.png', size: 1, created_at: '2026-11-07T00:00:00Z', can_remove: true },
  { id: 2, original_name: '别人的合同.pdf', size: 1, created_at: '2026-11-07T00:00:00Z', can_remove: false },
  { id: 3, original_name: '报价.xlsx', size: 1, created_at: '2026-11-07T00:00:00Z', can_remove: true },
]

it('非管理员只能勾选自己可删除的附件，并批量提交整批共用原因', async () => {
  user.value = { roles: ['purchaser'] }
  vi.mocked(read).mockResolvedValue({ count: 3, results: mixed, next: null })
  vi.mocked(write).mockResolvedValue({ removed: 2 })
  const wrapper = make()
  await flushPromises()
  expect(wrapper.find('[aria-label="附件批量选择"]').exists()).toBe(false)
  expect(wrapper.findAll('input[type="checkbox"]')).toHaveLength(3)
  expect(wrapper.find('[aria-label="选择附件 #2 · 别人的合同.pdf"]').exists()).toBe(false)
  const removeButton = () => wrapper.findAll('button').find(button => button.text().startsWith('删除所选'))!
  expect(removeButton().attributes('disabled')).toBeDefined()
  await wrapper.get('[aria-label="选择本页附件"]').setValue(true)
  expect(removeButton().text()).toBe('删除所选（2）')
  await removeButton().trigger('click')
  expect(wrapper.getComponent(AttachmentRemovalDialog).props('rows').map(row => row.id)).toEqual([1, 3])
  wrapper.unmount()
})

it('撤回勾选跨页保留：翻到没有可删附件的一页时仍显示勾选列和「删除所选」', async () => {
  user.value = { roles: ['purchaser'] }
  pageSize.value = 10
  const others = [{ id: 11, original_name: '别人的图纸.pdf', size: 1, created_at: '2026-11-07T00:00:00Z', can_remove: false }]
  vi.mocked(read).mockImplementation(async (_path, params = {}) => Number(params.page) === 2 ? { count: 4, results: others, next: null } : { count: 4, results: mixed, next: 'next' })
  const wrapper = make()
  await flushPromises()
  const removeButton = () => wrapper.findAll('button').find(button => button.text().startsWith('删除所选'))
  await wrapper.get('[aria-label="选择附件 #1 · 比价表.png"]').setValue(true)
  wrapper.getComponent(ListPagination).vm.$emit('change', 2)
  await flushPromises()
  expect(removeButton()?.text()).toBe('删除所选（1）')
  expect(wrapper.find('[aria-label="选择本页附件"]').exists()).toBe(true)
  await removeButton()!.trigger('click')
  expect(wrapper.getComponent(AttachmentRemovalDialog).props('rows').map(row => row.id)).toEqual([1])
  // 没有勾选、本页也没有可删附件时不占勾选列。
  wrapper.getComponent(AttachmentRemovalDialog).vm.$emit('close')
  await wrapper.findAll('button').find(button => button.text() === '刷新')!.trigger('click')
  await flushPromises()
  expect(removeButton()).toBeUndefined()
  expect(wrapper.find('[aria-label="选择本页附件"]').exists()).toBe(false)
  wrapper.unmount()
})

it('附件撤回弹窗列出文件名、要求原因并提交 remove-batch', async () => {
  vi.mocked(write).mockResolvedValue({ removed: 2 })
  const wrapper = mount(AttachmentRemovalDialog, {
    props: { rows: [mixed[0], mixed[2]] },
    global: { plugins: [ElementPlus], stubs: { ElDialog: { template: '<section><slot /><slot name="footer" /></section>' } } },
  })
  expect(wrapper.get('[aria-label="将删除的附件"]').text()).toContain('比价表.png')
  expect(wrapper.get('[aria-label="将删除的附件"]').text()).toContain('报价.xlsx')
  const confirm = () => wrapper.findAll('button').find(button => button.text().includes('确认删除'))!
  expect(confirm().attributes('disabled')).toBeDefined()
  await wrapper.get('textarea').setValue(' 比价表传错了 ')
  // 与记录删除一致：只填原因还不能删，须勾选核对。
  expect(confirm().attributes('disabled')).toBeDefined()
  await confirm().trigger('click')
  expect(write).not.toHaveBeenCalled()
  await wrapper.get('input[type="checkbox"]').setValue(true)
  expect(wrapper.get('label.removal-confirm').text()).toContain('我已核对所选附件')
  expect(confirm().attributes('disabled')).toBeUndefined()
  await confirm().trigger('click')
  await flushPromises()
  expect(write).toHaveBeenCalledWith('/business/documents/remove-batch/', { documents: [1, 3], reason: '比价表传错了' }, expect.any(String))
  expect(wrapper.emitted('saved')).toHaveLength(1)
  expect(wrapper.emitted('close')).toHaveLength(1)
})

it('附件撤回提交中不能关闭，失败后保留原因与勾选并显示错误', async () => {
  let fail!: (reason: unknown) => void
  vi.mocked(write).mockImplementation(() => new Promise((_, reject) => { fail = reject }))
  const wrapper = mount(AttachmentRemovalDialog, {
    props: { rows: [mixed[0]] },
    global: { plugins: [ElementPlus], stubs: { ElDialog: { props: ['showClose', 'closeOnPressEscape'], template: '<section :data-closable="String(showClose)"><slot /><slot name="footer" /></section>' } } },
  })
  await wrapper.get('textarea').setValue('传错项目')
  await wrapper.get('input[type="checkbox"]').setValue(true)
  await wrapper.findAll('button').find(button => button.text().includes('确认删除'))!.trigger('click')
  expect(wrapper.get('section').attributes('data-closable')).toBe('false')
  await wrapper.findAll('button').find(button => button.text() === '取消')!.trigger('click')
  expect(wrapper.emitted('close')).toBeUndefined()
  fail({ response: { data: { detail: '已作为对账依据，不能删除' } } })
  await flushPromises()
  expect(wrapper.text()).toContain('已作为对账依据')
  expect((wrapper.get('input[type="checkbox"]').element as HTMLInputElement).checked).toBe(true)
  expect(wrapper.get('section').attributes('data-closable')).toBe('true')
  wrapper.unmount()
})

it('管理员仍使用原有批量删除，不出现撤回按钮', async () => {
  user.value = { roles: ['admin'] }
  vi.mocked(read).mockResolvedValue({ count: 3, results: mixed, next: null })
  const wrapper = make()
  await flushPromises()
  expect(wrapper.findAll('button').some(button => button.text().startsWith('删除所选'))).toBe(false)
  expect(wrapper.find('[aria-label="附件批量选择"]').exists()).toBe(true)
  expect(wrapper.findAll('input[type="checkbox"]')).toHaveLength(4)
  wrapper.unmount()
})
