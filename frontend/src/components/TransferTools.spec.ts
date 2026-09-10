import { flushPromises, shallowMount } from '@vue/test-utils'
import { beforeEach, expect, it, vi } from 'vitest'
import TransferTools from './TransferTools.vue'
import { write } from '../api'

vi.mock('../api', () => ({ write: vi.fn(), download: vi.fn() }))
vi.mock('../session', () => ({ can: () => true }))

beforeEach(() => vi.resetAllMocks())

it('银行原始文件先预览汇总，确认时提交凭据并显示去重结果', async () => {
  const wrapper = shallowMount(TransferTools, {
    props: { resource: 'bank-records', path: '/business/bank-records/' },
    global: { stubs: {
      ElTable: true,
      ElTableColumn: true,
      ElDialog: { template: '<section><slot /><slot name="footer" /></section>' },
      ElButton: { template: '<button><slot /></button>' },
      ElAlert: { props: ['title'], template: '<p>{{ title }}</p>' },
    } },
  })
  expect(wrapper.find('input[type=file]').attributes('accept')).toBe('.xls,.xlsx')
  expect(wrapper.text()).not.toContain('下载模板')
  vi.mocked(write).mockResolvedValueOnce({ token: 'signed-preview', count: 2, rows: [], errors: [], can_import: true, summary: { income_count: 1, income: '100.00', expense_count: 1, expense: '20.00', check: '汇总一致' } })
  const input = wrapper.find('input[type=file]')
  Object.defineProperty(input.element, 'files', { value: [new File(['sample'], '华夏.xls')], configurable: true })
  await input.trigger('change')
  await flushPromises()
  expect(vi.mocked(write).mock.calls[0]?.[0]).toBe('/business/bank-records/import-file/')
  expect(vi.mocked(write).mock.calls[0]?.[1]).toBeInstanceOf(FormData)
  expect(wrapper.text()).toContain('收入 1 笔 / 100.00 元')
  expect(wrapper.text()).toContain('汇总一致')
  vi.mocked(write).mockResolvedValueOnce({ count: 1, skipped: 1 })
  await wrapper.findAll('button').find(button => button.text() === '确认导入')!.trigger('click')
  await flushPromises()
  expect(vi.mocked(write).mock.calls[1]?.slice(0, 2)).toEqual(['/business/bank-records/import-confirm/', { token: 'signed-preview' }])
  expect(wrapper.text()).toContain('成功导入 1 条记录，跳过已导入 1 条')
  expect(wrapper.emitted('changed')).toHaveLength(1)
})
