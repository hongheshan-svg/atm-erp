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

describe('项目上下文与确认失败回填', () => {
  async function openImport(resource: string, params: Record<string, unknown>) {
    vi.clearAllMocks()
    user.value = { roles: ['admin'] }
    vi.mocked(read).mockImplementation(async (url: string) => url.includes('import-schema')
      ? { title: '工时', columns: [], entry: '入口', note: '' }
      : { id: 7, name: '示例项目', code: 'ATM2601' })
    const wrapper = shallowMount(TransferTools, { props: { resource, path: `/business/${resource}/`, params }, global: {
      plugins: [ElementPlus], renderStubDefaultSlot: true,
      stubs: { RouterLink: RouterLinkStub, ElDialog: { template: '<section><slot /><slot name="footer" /></section>' }, ElTableColumn: true },
    } })
    wrapper.findComponent({ name: 'ElDropdown' }).vm.$emit('command', 'import')
    await flushPromises()
    return wrapper
  }

  it.each([['time', { task__project: 7 }], ['payments', { entry__project: 7 }]])('项目内%s导入显示当前项目上下文', async (resource, params) => {
    const wrapper = await openImport(resource, params)
    expect(wrapper.find('.import-context').text()).toContain('示例项目（ATM2601）')
    expect(vi.mocked(read).mock.calls.some(call => call[0] === '/business/projects/7/')).toBe(true)
    wrapper.unmount()
  })

  it('确认时整批重新校验失败：错误行回填预览、禁用确认并提示重新上传', async () => {
    const wrapper = await openImport('moves', { project: 7 })
    vi.mocked(write).mockResolvedValueOnce({
      can_import: true, token: 'tok', count: 1, columns: [{ key: 'stock', label: '库存ID' }],
      rows: [{ row: 2, data: { stock: '9' } }], errors: [],
    })
    const input = wrapper.get('input[type=file]')
    Object.defineProperty(input.element, 'files', { value: [new File(['x'], 'moves.csv')] })
    await input.trigger('change')
    await flushPromises()
    const confirmButton = () => wrapper.findAll('el-button-stub').find(button => button.text() === '确认导入')!
    expect(confirmButton().attributes('disabled')).not.toBe('true')
    vi.mocked(write).mockRejectedValueOnce({ isAxiosError: true, response: { status: 400, data: { rows: [{ row: '2', message: '可用库存不足，请刷新后重试。', fields: ['stock'] }], error_file: { name: '待修改.xlsx', content: 'base64' } } } })
    await confirmButton().trigger('click')
    await flushPromises()
    const feedback = wrapper.getComponent({ name: 'ImportFeedback' })
    expect(feedback.props('errors')).toEqual([{ row: 2, message: '可用库存不足，请刷新后重试。', fields: ['stock'] }])
    expect(feedback.props('errorFile')).toEqual({ name: '待修改.xlsx', content: 'base64' })
    expect(confirmButton().attributes('disabled')).toBe('true')
    expect(wrapper.getComponent({ name: 'ElAlert' }).props('title')).toContain('数据已变化，请修改文件后重新上传预览')
    wrapper.unmount()
  })

  it('已导入内容须明确勾选，成功提供准确记录入口；再次上传清除确认', async () => {
    const wrapper = await openImport('entries', { project: 7 })
    const data = { token: 'repeat-token', can_import: true, count: 1, rows: [], columns: [], errors: [], duplicate_import: { message: '相同业务归属和内容已成功导入' } }
    vi.mocked(write).mockResolvedValueOnce(data)
    const input = wrapper.get('input[type=file]')
    Object.defineProperty(input.element, 'files', { value: [new File(['x'], 'renamed.csv')] })
    await input.trigger('change'); await flushPromises()
    const confirm = () => wrapper.findAll('el-button-stub').find(b => b.text() === '确认导入')!
    expect(confirm().attributes('disabled')).toBe('true')
    await confirm().trigger('click')
    expect(write).toHaveBeenCalledTimes(1)
    await wrapper.get('input[type=checkbox]').setValue(true)
    expect(confirm().attributes('disabled')).not.toBe('true')
    vi.mocked(write).mockResolvedValueOnce({ count: 1, resource: 'entries', results: [{ id: 42 }] })
    await confirm().trigger('click'); await flushPromises()
    expect(vi.mocked(write).mock.calls[1]?.[1]).toEqual({ token: 'repeat-token', allow_duplicate: true })
    expect(wrapper.getComponent(RouterLinkStub).props('to')).toEqual({ path: '/finance', query: { section: 'entries', resource: 'entries', project: 'all', focus: 42 } })
    expect(wrapper.text()).toContain('查看导入记录')
    expect(wrapper.emitted('changed')).toHaveLength(1)
    vi.mocked(write).mockResolvedValueOnce(data)
    await input.trigger('change'); await flushPromises()
    expect(wrapper.get('input[type=checkbox]').element).toHaveProperty('checked', false)
    expect(confirm().attributes('disabled')).toBe('true')
    wrapper.unmount()
  })

  it('确认时发现其他批次已成功：保留预览要求勾选，网络重试使用同一操作键', async () => {
    const wrapper = await openImport('entries', {})
    vi.mocked(write).mockResolvedValueOnce({ token: 'race-token', can_import: true, count: 1, rows: [], errors: [] })
    const input = wrapper.get('input[type=file]')
    Object.defineProperty(input.element, 'files', { value: [new File(['x'], 'expenses.csv')] })
    await input.trigger('change'); await flushPromises()
    const confirm = () => wrapper.findAll('el-button-stub').find(b => b.text() === '确认导入')!
    vi.mocked(write).mockRejectedValueOnce({ response: { status: 409, data: { duplicate_import: { message: '已经成功导入' } } } })
    await confirm().trigger('click'); await flushPromises()
    expect(confirm().attributes('disabled')).toBe('true')
    await wrapper.get('input[type=checkbox]').setValue(true)
    vi.mocked(write).mockRejectedValueOnce(new Error('网络暂不可用'))
    await confirm().trigger('click'); await flushPromises()
    vi.mocked(write).mockResolvedValueOnce({ count: 1, resource: 'entries', results: [{ id: 42 }] })
    await confirm().trigger('click'); await flushPromises()
    const calls = vi.mocked(write).mock.calls.filter(call => call[0].endsWith('import-confirm/'))
    expect(new Set(calls.map(call => call[2])).size).toBe(1)
    expect(wrapper.text()).toContain('查看导入记录')
    wrapper.unmount()
  })

  it('导出采用中文文件名并保留当前列表筛选', async () => {
    const wrapper = await openImport('entries', { project: 7, search: '差旅' })
    wrapper.findComponent({ name: 'ElDropdown' }).vm.$emit('command', 'xlsx')
    await flushPromises()
    expect(download).toHaveBeenCalledWith('/business/entries/export/', expect.stringMatching(/^应收应付与费用导出_\d{4}-\d{2}-\d{2}\.xlsx$/), { project: 7, search: '差旅', file_format: 'xlsx' })
    wrapper.unmount()
  })
})
