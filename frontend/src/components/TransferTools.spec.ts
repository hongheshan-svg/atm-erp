import { describe, it, expect, vi } from 'vitest'
import { shallowMount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import TransferTools from './TransferTools.vue'
import { read, write } from '../api'
import { user } from '../session'

vi.mock('../api', () => ({ read: vi.fn(), write: vi.fn(), download: vi.fn() }))

describe('导入模板与预览', () => {
  it('使用后端模板列逐列显示，采购保留文件行号且不展示分组 JSON', async () => {
    user.value = { role: 'admin' }
    const columns = [
      { key: 'group', label: '分组号', table_keys: ['group'], hint: '同组合单' },
      { key: 'item', label: '物料编码', table_keys: ['item_code'], hint: '填写物料编码' },
      { key: 'quantity', label: '数量', table_keys: ['quantity'], hint: '填写数量' },
    ]
    vi.mocked(read).mockResolvedValue({ columns, note: '生成采购草稿' })
    vi.mocked(write).mockResolvedValue({ columns, rows: [
      { row: 2, data: { group: 'G', item: 'A', quantity: '2' } },
      { row: 3, data: { group: 'G', item: 'B', quantity: '3' } },
    ], count: 1, row_count: 2, can_import: true, errors: [], token: 'signed-token' })
    const wrapper = shallowMount(TransferTools, {
      props: { resource: 'purchases', path: '/business/purchases/', tableColumns: [{ key: 'code', label: '采购编号' }] },
      global: { plugins: [ElementPlus], renderStubDefaultSlot: true, stubs: { ElDialog: { template: '<div><slot /><slot name="footer" /></div>' }, ElTableColumn: { template: '<div class="column-stub" />' } } },
    })
    await wrapper.findAll('el-button-stub').find(b => b.text() === '导入')!.trigger('click')
    await flushPromises()
    expect(read).toHaveBeenCalledWith('/business/purchases/import-schema/')
    expect(wrapper.text()).toContain('采购编号 由系统生成')
    const input = wrapper.get('input[type=file]')
    Object.defineProperty(input.element, 'files', { value: [new File(['csv'], 'rows.csv')], configurable: true })
    await input.trigger('change')
    await flushPromises()
    const tables = wrapper.findAll('el-table-stub')
    const preview = tables[tables.length - 1]!
    expect(preview.findAll('.column-stub').map(c => c.attributes('label'))).toEqual(['文件行号', '分组号', '物料编码', '数量'])
    expect(wrapper.text()).toContain('文件 2 行明细合并为 1 张采购草稿')
    vi.mocked(write).mockRejectedValue(new Error('格式不正确'))
    await input.trigger('change')
    await flushPromises()
    expect(wrapper.text()).not.toContain('文件 2 行明细')
    expect(wrapper.findAll('el-button-stub').find(b => b.text() === '确认导入')!.attributes('disabled')).toBe('true')
    wrapper.unmount()
  })
})

it('银行原始文件先预览汇总，确认时提交凭据并显示去重结果', async () => {
  vi.clearAllMocks()
  user.value = { role: 'admin' }
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
