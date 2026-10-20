import { describe, it, expect, vi } from 'vitest'
import { shallowMount, flushPromises, RouterLinkStub } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import TransferTools from './TransferTools.vue'
import { download, read, write } from '../api'
import { user } from '../session'

vi.mock('../api', () => ({ read: vi.fn(), write: vi.fn(), download: vi.fn() }))

it('选择文件前显示导入对象，错模板提供主动跳转且不会跨入口写入', async () => {
  vi.clearAllMocks()
  user.value = { roles: ['admin'] }
  vi.mocked(read).mockResolvedValue({ title: '项目', columns: [] })
  vi.mocked(write).mockRejectedValue({ response: { data: {
    file: '这是项目任务模板，请到项目任务导入入口。',
    template_hint: { code: 'tasks', title: '项目任务', entry: '项目任务 → 导入' },
  } } })
  const wrapper = shallowMount(TransferTools, { props: { resource: 'projects', path: '/business/projects/' }, global: {
    plugins: [ElementPlus], renderStubDefaultSlot: true,
    stubs: { RouterLink: RouterLinkStub, ElDialog: { props: ['title'], template: '<section :aria-label="title"><slot /><slot name="footer" /></section>' }, ElTableColumn: true },
  } })
  expect(wrapper.get('section').attributes('aria-label')).toBe('导入项目')
  wrapper.findComponent({ name: 'ElDropdown' }).vm.$emit('command', 'import')
  await flushPromises()
  const input = wrapper.get('input[type=file]')
  Object.defineProperty(input.element, 'files', { value: [new File(['任务模板'], 'tasks.csv')] })
  await input.trigger('change')
  await flushPromises()
  expect(wrapper.getComponent({ name: 'ElAlert' }).props('title')).toContain('这是项目任务模板')
  expect(wrapper.getComponent(RouterLinkStub).props('to')).toEqual({ path: '/projects', query: { resource: 'tasks' } })
  expect(write).toHaveBeenCalledOnce()
  expect(vi.mocked(write).mock.calls[0]?.[0]).toBe('/business/projects/import-file/')
  expect(wrapper.findAll('el-button-stub').find(button => button.text() === '确认导入')!.attributes('disabled')).toBe('true')
  wrapper.unmount()
})

it('切换导入资源时忽略旧文件响应，旧凭据不能出现在新入口', async () => {
  vi.clearAllMocks()
  user.value = { roles: ['admin'] }
  vi.mocked(read).mockResolvedValue({ title: '项目', columns: [] })
  let resolve!: (value: object) => void
  vi.mocked(write).mockImplementationOnce(() => new Promise(done => { resolve = done }))
  const wrapper = shallowMount(TransferTools, { props: { resource: 'projects', path: '/business/projects/' }, global: {
    plugins: [ElementPlus], renderStubDefaultSlot: true,
    stubs: { RouterLink: RouterLinkStub, ElDialog: { template: '<section><slot /><slot name="footer" /></section>' }, ElTableColumn: true },
  } })
  wrapper.findComponent({ name: 'ElDropdown' }).vm.$emit('command', 'import')
  await flushPromises()
  const input = wrapper.get('input[type=file]')
  Object.defineProperty(input.element, 'files', { value: [new File(['数据'], 'projects.csv')] })
  await input.trigger('change')
  await wrapper.setProps({ resource: 'tasks', path: '/business/tasks/' })
  resolve({ can_import: true, token: 'old-resource-token', rows: [], count: 1 })
  await flushPromises()
  expect(wrapper.findComponent({ name: 'ImportFeedback' }).exists()).toBe(false)
  expect(wrapper.findAll('el-button-stub').find(button => button.text() === '确认导入')!.attributes('disabled')).toBe('true')
  wrapper.unmount()
})

describe('导入模板与预览', () => {
  it('使用后端模板列逐列显示，采购保留文件行号且不展示分组 JSON', async () => {
    user.value = { role: 'admin' }
    const columns = [
      { key: 'group', label: '分组号', table_keys: ['group'], hint: '同组合单' },
      { key: 'item', label: '物料编码', table_keys: ['item_code'], hint: '填写物料编码' },
      { key: 'quantity', label: '数量', table_keys: ['quantity'], hint: '填写数量' },
    ]
    vi.mocked(read).mockResolvedValue({ columns, note: '生成采购草稿', title: '采购', entry: '采购 → 导入导出 → 导入',
      quick_start: { prepare: '准备已建档物料编码', minimum: '同张单的分组号相同', example: '两种物料分两行' } })
    vi.mocked(download).mockResolvedValue(undefined)
    vi.mocked(write).mockResolvedValue({ columns, rows: [
      { row: 2, data: { group: 'G', item: 'A', quantity: '2' } },
      { row: 3, data: { group: 'G', item: 'B', quantity: '3' } },
    ], count: 1, row_count: 2, can_import: true, errors: [], token: 'signed-token' })
    const wrapper = shallowMount(TransferTools, {
      props: { resource: 'purchases', path: '/business/purchases/', tableColumns: [{ key: 'code', label: '采购编号' }] },
      global: { plugins: [ElementPlus], renderStubDefaultSlot: true, stubs: { RouterLink: RouterLinkStub, ImportFeedback: false, ElDialog: { template: '<div><slot /><slot name="footer" /></div>' }, ElTableColumn: { template: '<div class="column-stub" />' } } },
    })
    const openImport = async () => wrapper.findComponent({ name: 'ElDropdown' }).vm.$emit('command', 'import')
    await openImport()
    await flushPromises()
    expect(read).toHaveBeenCalledWith('/business/purchases/import-schema/')
    expect(wrapper.text()).toContain('采购编号 由系统生成')
    expect(wrapper.text()).toContain('采购 → 导入导出 → 导入')
    expect(wrapper.text()).toContain('准备已建档物料编码')
    expect(wrapper.text()).toContain('② 最少填什么：同张单的分组号相同')
    expect(wrapper.text()).toContain('再点右侧▼')
    await wrapper.findAll('el-button-stub').find(b => b.text() === '下载模板')!.trigger('click')
    await flushPromises()
    expect(download).toHaveBeenCalledWith('/business/purchases/import-template/', '采购导入模板.xlsx', { file_format: 'xlsx' })
    await wrapper.findAll('el-button-stub').find(b => b.text() === '下载填写说明')!.trigger('click')
    await flushPromises()
    expect(download).toHaveBeenCalledWith('/business/purchases/import-template/', '采购导入填写说明.html', { file_format: 'html' })
    const input = wrapper.get('input[type=file]')
    Object.defineProperty(input.element, 'files', { value: [new File(['csv'], 'rows.csv')], configurable: true })
    await input.trigger('change')
    await flushPromises()
    const tables = wrapper.findAll('el-table-stub')
    const preview = tables[tables.length - 1]!
    expect(preview.findAll('.column-stub').map(c => c.attributes('label'))).toEqual(['文件行号', '分组号', '物料编码', '数量'])
    expect(wrapper.text()).toContain('文件 2 行明细合并为 1 张采购草稿')
    await wrapper.findAll('el-button-stub').find(b => b.text() === '关闭')!.trigger('click')
    await openImport()
    await flushPromises()
    expect(wrapper.text()).not.toContain('文件 2 行明细')
    expect(wrapper.findAll('el-button-stub').find(b => b.text() === '确认导入')!.attributes('disabled')).toBe('true')
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
      RouterLink: RouterLinkStub,
      ElTable: true,
      ElTableColumn: true,
      ElDialog: { template: '<section><slot /><slot name="footer" /></section>' },
      ElButton: { template: '<button><slot /></button>' },
      ElAlert: { props: ['title'], template: '<p>{{ title }}</p>' },
    } },
  })
  expect(wrapper.find('input[type=file]').attributes('accept')).toBe('.xls,.xlsx')
  expect(wrapper.text()).not.toContain('下载模板')
  expect(wrapper.text()).not.toContain('下载填写说明')
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


it('allowImport默认开启，库存日常关闭后仅提供导出并阻止打开导入', async () => {
  user.value = { roles: ['admin'] }
  vi.mocked(read).mockClear()
  const wrapper = shallowMount(TransferTools, { props: { resource: 'stocks', path: '/business/stocks/', allowImport: false }, global: {
    plugins: [ElementPlus], renderStubDefaultSlot: true, stubs: { RouterLink: RouterLinkStub },
  } })
  expect(wrapper.findComponent({ name: 'ElButton' }).text()).toBe('导出 ▾')
  wrapper.findComponent({ name: 'ElDropdown' }).vm.$emit('command', 'import')
  await flushPromises()
  expect(read).not.toHaveBeenCalled()
  await wrapper.setProps({ allowImport: true })
  expect(wrapper.findComponent({ name: 'ElButton' }).text()).toBe('导入导出 ▾')
  wrapper.unmount()
})
