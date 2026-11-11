import { afterEach, expect, it, vi } from 'vitest'
import { flushPromises, shallowMount, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import BOMDemand from './BOMDemand.vue'
import { user } from '../session'
import ListPagination from './ListPagination.vue'
import RecordDeletionDialog from './RecordDeletionDialog.vue'
import { pageSize } from '../pagination'
import { batchMode } from '../batch-mode'
import { download, read, write } from '../api'
import { downloadBOM } from '../api/bom'
vi.mock('../api/bom', () => ({ downloadBOM: vi.fn() }))
vi.mock('../api', () => ({ read: vi.fn().mockResolvedValue({ lines: [] }), all: vi.fn().mockResolvedValue([]), write: vi.fn(), download: vi.fn() }))
// 删除入口默认收起；这里的用例验证的是开启「批量管理」后的选择与删除，并按每页 10 条构造跨页场景。
batchMode.value = true
pageSize.value = 10
afterEach(() => { user.value = null; vi.clearAllMocks(); vi.restoreAllMocks() })

it('采购视图导出缺料清单：筛选跨页81项及所选子集，不夹带非标件；切换类别明确提示筛选外选择', async () => {
  user.value = { roles: ['purchaser'] }
  const standards = Array.from({ length: 81 }, (_, i) => ({ bom_line: i + 1, item_code: `S${i}`, item_name: '标准件', part_type: 'standard', brand: '品牌A', assembly_unit: i % 2 ? '单元A' : '单元B', shortage: '1' }))
  vi.mocked(read).mockResolvedValueOnce({ lines: [...standards, { bom_line: 90, part_type: 'custom', item_code: 'C1', shortage: '1' }, { bom_line: 91, part_type: 'standard', item_code: 'S91', shortage: '0' }] })
  const wrapper = shallowMount(BOMDemand, { props: { projectId: 1, status: 'active' }, global: { plugins: [ElementPlus], renderStubDefaultSlot: true, stubs: { BusinessTable: { template: '<div />' } } } })
  await flushPromises()
  await wrapper.get('[aria-label="筛选类别"]').setValue('standard')
  expect(wrapper.get('[aria-label="BOM导出范围"]').text()).toContain('当前筛选 81 项')
  const dropdown = wrapper.getComponent({ name: 'ElDropdown' })
  dropdown.vm.$emit('command', 'filtered:xlsx')
  await flushPromises()
  expect(downloadBOM).toHaveBeenLastCalledWith(1, standards.map(row => row.bom_line), 'xlsx', '缺料清单_筛选结果81项.xlsx', 'purchase')
  await wrapper.findAll('el-button-stub').find(button => button.text() === '全选筛选结果')!.trigger('click')
  dropdown.vm.$emit('command', 'selected:csv')
  await flushPromises()
  expect(downloadBOM).toHaveBeenLastCalledWith(1, standards.map(row => row.bom_line), 'csv', '缺料清单_已选81项.csv', 'purchase')
  await wrapper.get('[aria-label="筛选类别"]').setValue('custom')
  expect(wrapper.get('[aria-label="BOM导出范围"]').text()).toContain('81 项在当前筛选外')
  dropdown.vm.$emit('command', 'filtered:csv')
  await flushPromises()
  expect(downloadBOM).toHaveBeenLastCalledWith(1, [90], 'csv', '缺料清单_筛选结果1项.csv', 'purchase')
  await wrapper.get('[aria-label="搜索 BOM 物料"]').setValue('不存在')
  dropdown.vm.$emit('command', 'filtered:xlsx')
  await flushPromises()
  expect(downloadBOM).toHaveBeenCalledTimes(3)
  await wrapper.setProps({ projectId: 2 })
  expect(wrapper.get('[aria-label="BOM导出范围"]').text()).not.toContain('已选 81')
  wrapper.unmount()
})

it('工程师BOM维护和导入取当前项目权限，兼采购全局可读项目不扩写权限', async () => {
  user.value = { roles: ['mechanical_engineer', 'purchaser'] }
  const wrapper = shallowMount(BOMDemand, { props: { projectId: 1, status: 'active', canEditBom: false }, global: { plugins: [ElementPlus], renderStubDefaultSlot: true, stubs: { ImportFeedback: false, RouterLink: true, BusinessTable: { template: '<div />' } } } })
  await flushPromises()
  expect(wrapper.text()).not.toContain('维护 BOM')
  expect(wrapper.text()).not.toContain('下载填写说明')
  expect(wrapper.find('input[type="file"]').exists()).toBe(false)
  await wrapper.setProps({ canEditBom: true })
  await wrapper.get('input[value=prepare]').setValue()
  expect(wrapper.text()).toContain('维护 BOM')
  expect(wrapper.find('input[type="file"]').exists()).toBe(false)
  await wrapper.findAll('el-button-stub').find(button => button.text() === '导入 BOM')!.trigger('click')
  await flushPromises()
  expect(wrapper.find('input[type="file"]').exists()).toBe(true)
  vi.mocked(download).mockResolvedValue(undefined)
  await wrapper.findAll('el-button-stub').find(button => button.text() === '下载填写说明')!.trigger('click')
  await flushPromises()
  expect(download).toHaveBeenCalledWith('/business/projects/bom-template/', 'BOM导入填写说明.html', { file_format: 'html' })
  await wrapper.setProps({ canEditBom: false })
  expect(wrapper.text()).not.toContain('维护 BOM')
  expect(wrapper.find('input[type="file"]').exists()).toBe(false)
  wrapper.unmount()
})

const dialogStub = {
  props: ['modelValue', 'title'],
  template: '<div v-if="modelValue" role="dialog" :aria-label="title"><div class="el-dialog__body"><slot /></div><footer><slot name="footer" /></footer></div>',
}
function mountImport() {
  user.value = { roles: ['admin'] }
  return shallowMount(BOMDemand, { props: { projectId: 1, revision: 1, status: 'active', canEditBom: true }, global: {
    plugins: [ElementPlus], renderStubDefaultSlot: true,
    stubs: { ImportFeedback: false, RouterLink: true, ElDialog: dialogStub, BusinessTable: { template: '<div />' } },
  } })
}
async function uploadFile(wrapper: ReturnType<typeof mountImport>) {
  if (!wrapper.find('input[type="file"]').exists()) {
    await wrapper.findAll('el-button-stub').find(button => button.text() === '导入 BOM')!.trigger('click')
    await flushPromises()
  }
  const input = wrapper.get('input[type="file"]')
  Object.defineProperty(input.element, 'files', { configurable: true, value: [new File(['数据'], 'bom.csv')] })
  await input.trigger('change')
}
it('选择文件立即打开预览并显示处理状态，取消后重新选同一文件不接收旧响应', async () => {
  let finish!: (value: object) => void
  vi.mocked(write).mockImplementationOnce(() => new Promise(resolve => { finish = resolve }))
  const wrapper = mountImport()
  await uploadFile(wrapper)
  expect(wrapper.get('[role="dialog"]').attributes('aria-label')).toBe('导入BOM')
  expect(wrapper.get('[role="dialog"] [role="status"]').text()).toContain('正在读取文件')
  expect(wrapper.findAll('el-button-stub').find(button => button.text() === '确认导入')!.attributes('disabled')).toBe('true')
  await wrapper.findAll('el-button-stub').find(button => button.text() === '关闭')!.trigger('click')
  expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
  vi.mocked(write).mockResolvedValueOnce({ can_import: true, lines: [{ row: 2 }], token: 'new-preview' })
  await uploadFile(wrapper)
  await flushPromises()
  finish({ can_import: false, lines: [], errors: [{ message: '旧请求错误' }] })
  await flushPromises()
  expect(wrapper.get('[role="dialog"] [role="status"]').text()).toContain('校验通过，共 1 条明细')
  expect(wrapper.text()).not.toContain('旧请求错误')
  await wrapper.findAll('el-button-stub').find(button => button.text() === '确认导入')!.trigger('click')
  expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
  const action = wrapper.getComponent({ name: 'ActionDialog' })
  expect(action.props('command').prepare()).toEqual({ token: 'new-preview' })
  action.vm.$emit('close')
  await flushPromises()
  expect(wrapper.find('[role="dialog"]').exists()).toBe(true)
  wrapper.unmount()
})

it.each(['projectId', 'revision'])('切换%s时关闭预览，晚到的请求错误不会显示到新状态', async key => {
  let fail!: (error: Error) => void
  vi.mocked(write).mockImplementationOnce(() => new Promise((_, reject) => { fail = reject }))
  const wrapper = mountImport()
  await uploadFile(wrapper)
  await wrapper.setProps({ [key]: 2 })
  fail(new Error('旧文件读取失败'))
  await flushPromises()
  expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
  expect(wrapper.text()).not.toContain('旧文件读取失败')
  expect(wrapper.findAll('el-button-stub').find(button => button.text() === '导入 BOM')!.attributes('disabled')).toBe('false')
  wrapper.unmount()
})

it('读取失败在预览窗口明确显示，确认按钮保持禁用', async () => {
  vi.mocked(write).mockRejectedValueOnce(new Error('文件表头不正确，请使用 BOM 模板。'))
  const wrapper = mountImport()
  await uploadFile(wrapper)
  await flushPromises()
  expect(wrapper.get('[role="dialog"] [role="alert"]').attributes('title')).toContain('文件表头不正确')
  expect(wrapper.findAll('el-button-stub').find(button => button.text() === '确认导入')!.attributes('disabled')).toBe('true')
  wrapper.unmount()
})

it.each(['invalid', 'valid', 'file-error'])('上传%s结果后滚动弹窗正文到校验结果，固定操作区不随正文滚动', async outcome => {
  let finish!: (value: object) => void
  let fail!: (error: Error) => void
  vi.mocked(write).mockImplementationOnce(() => new Promise((resolve, reject) => { finish = resolve; fail = reject }))
  const wrapper = mountImport()
  await uploadFile(wrapper)
  const importDialog = () => wrapper.findAllComponents(dialogStub).find(dialog => dialog.props('title') === '导入BOM')!
  const body = wrapper.get<HTMLElement>('.el-dialog__body').element
  body.scrollTop = 45 // The user has scrolled the preparation instructions before uploading.
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (this: HTMLElement) {
    if (this.classList.contains('el-dialog__body')) return new DOMRect(0, 100, 340, 500)
    if (this.classList.contains('bom-import-result')) {
      return new DOMRect(0, 640 - this.closest<HTMLElement>('.el-dialog__body')!.scrollTop, 340, 800)
    }
    return new DOMRect()
  })
  const lines = Array.from({ length: 120 }, (_, i) => ({ row: i + 2, item_name: '测试滑块' }))
  if (outcome === 'file-error') fail(new Error('文件表头不正确'))
  else finish({ can_import: outcome === 'valid', lines, token: outcome === 'valid' ? 'preview-token' : undefined,
    errors: outcome === 'invalid' ? lines.map(line => ({ row: line.row, message: '产品编码类别不正确' })) : [],
  })
  await flushPromises()
  expect(body.scrollTop).toBe(540)
  const confirm = wrapper.findAll('el-button-stub').find(button => button.text() === '确认导入')!
  expect(body.contains(confirm.element)).toBe(false)
  expect(confirm.attributes('disabled')).toBe(String(outcome !== 'valid'))
  // Dialog opening/transition must not double-scroll an already visible result.
  importDialog().vm.$emit('opened')
  await flushPromises()
  expect(body.scrollTop).toBe(540)
  if (outcome === 'valid') {
    await confirm.trigger('click')
    wrapper.getComponent({ name: 'ActionDialog' }).vm.$emit('close')
    await flushPromises()
    const reopened = wrapper.get<HTMLElement>('.el-dialog__body').element
    expect(reopened.scrollTop).toBe(0)
    expect(wrapper.get('.bom-import-result').element.getBoundingClientRect().top).toBe(640)
    importDialog().vm.$emit('opened')
    await flushPromises()
    expect(reopened.scrollTop).toBe(540)
  }
  wrapper.unmount()
})

it('BOM导入错误逐行显示中文，保留行号且不输出原始数据字段', async () => {
  user.value = { roles: ['admin'] }
  vi.mocked(write).mockResolvedValueOnce({ lines: [], can_import: false, errors: [
    { row: 2, message: '需求数量：请输入正数。' },
    { message: '请重新上传文件。' },
  ] })
  const wrapper = shallowMount(BOMDemand, { props: { projectId: 1, status: 'active', canEditBom: true }, global: { plugins: [ElementPlus], renderStubDefaultSlot: true, stubs: { ImportFeedback: false, RouterLink: true, BusinessTable: { template: '<div />' } } } })
  await flushPromises()
  await wrapper.findAll('el-button-stub').find(button => button.text() === '导入 BOM')!.trigger('click')
  await flushPromises()
  const upload = wrapper.find('input[type="file"]')
  Object.defineProperty(upload.element, 'files', { value: [new File(['错误数量'], 'bom.csv')] })
  await upload.trigger('change')
  await flushPromises()
  expect(wrapper.get('[role="alert"]').text()).toContain('第 2 行：需求数量：请输入正数。')
  expect(wrapper.get('[role="alert"]').text()).toContain('请重新上传文件。')
  expect(wrapper.text()).not.toContain('"message"')
  expect(wrapper.text()).not.toContain('"row"')
  wrapper.unmount()
})


it('编制与采购视图使用相同BOM行，关键列优先且选择保留稳定行号', async () => {
  user.value = { roles: ['admin'] }
  // 采购勾选与批量删除互斥，这里验证的是平时的采购下单。
  batchMode.value = false
  vi.mocked(read).mockResolvedValueOnce({ lines: [
    { bom_line: 41, item_code: 'I1', item_name: '电机', assembly_unit: '单元A', quantity: '5', shortage: '2' },
    { bom_line: 42, item_code: 'I1', item_name: '电机', assembly_unit: '单元B', quantity: '3', shortage: '1' },
  ] })
  const wrapper = shallowMount(BOMDemand, { props: { projectId: 1, status: 'active', canEditBom: true }, global: {
    plugins: [ElementPlus], renderStubDefaultSlot: true,
    stubs: { RouterLink: true, ElTableColumn: { template: '<div class="col" />' } },
  } })
  await flushPromises()
  expect(wrapper.findAll('.col').filter(col => col.attributes('label') !== '选择').slice(0, 6).map(col => col.attributes('label'))).toEqual(['物料名称 / 编码', '规格', '单元', '需求数量', '单位', '需求日期'])
  expect(wrapper.text()).not.toContain('从 BOM 多选下单')
  await wrapper.get('input[value=purchase]').setValue()
  const labels = wrapper.findAll('.col').map(col => col.attributes('label'))
  expect(labels.indexOf('需求数量')).toBeLessThan(labels.indexOf('在途'))
  expect(labels).not.toContain('图号')
  await wrapper.findAll('el-button-stub').find(button => button.text() === '全选筛选结果')!.trigger('click')
  await wrapper.findAll('el-button-stub').find(button => button.text() === '从 BOM 多选下单')!.trigger('click')
  expect(wrapper.getComponent({ name: 'BOMPurchasePicker' }).props('initialSelection')).toEqual([41, 42])
  wrapper.unmount()
  batchMode.value = true
})

it('管理员跨页选择427项BOM，切换筛选或项目清空旧选择', async () => {
  user.value = { roles: ['admin'] }
  pageSize.value = 10
  const lines = Array.from({ length: 427 }, (_, i) => ({ bom_line: i + 1, item_code: 'I1', item_name: '同一物料', assembly_unit: '单元' + i, quantity: '1', part_type: i === 426 ? 'custom' : 'standard' }))
  vi.mocked(read).mockResolvedValue({ lines })
  const wrapper = mount(BOMDemand, { props: { projectId: 1, status: 'active', canEditBom: true }, global: {
    plugins: [ElementPlus], stubs: { RecordDeletionDialog: true, ActionDialog: true, BOMPurchasePicker: true, ImportFeedback: true, RouterLink: true },
  } })
  await flushPromises()
  await wrapper.get('[aria-label="选择本页BOM明细"]').setValue(true)
  wrapper.getComponent(ListPagination).vm.$emit('change', 2)
  await flushPromises()
  await wrapper.get('[aria-label="选择本页BOM明细"]').setValue(true)
  expect(wrapper.get('[aria-label="BOM批量选择"]').text()).toContain('20')
  wrapper.getComponent(ListPagination).vm.$emit('change', 1)
  await flushPromises()
  expect((wrapper.get('[aria-label="选择本页BOM明细"]').element as HTMLInputElement).checked).toBe(true)
  await wrapper.get('[aria-label="选择本页BOM明细"]').setValue(false)
  expect(wrapper.get('[aria-label="BOM批量选择"]').text()).toContain('10')
  await wrapper.findAll('button').find(b => b.text() === '全选筛选结果（427项，跨页）')!.trigger('click')
  await wrapper.findAll('button').find(b => b.text() === '批量删除（427）')!.trigger('click')
  expect(wrapper.getComponent(RecordDeletionDialog).props('rows')!.map(row => row.id)).toEqual(lines.map(row => row.bom_line))
  wrapper.getComponent(RecordDeletionDialog).vm.$emit('close')
  await wrapper.get('[aria-label="筛选类别"]').setValue('custom')
  expect(wrapper.get('[aria-label="BOM批量选择"]').text()).toContain('已选 0')
  await wrapper.findAll('button').find(b => b.text() === '全选筛选结果（1项，跨页）')!.trigger('click')
  await wrapper.setProps({ projectId: 2 })
  await flushPromises()
  expect(wrapper.get('[aria-label="BOM批量选择"]').text()).toContain('已选 0')
  wrapper.unmount()
  vi.mocked(read).mockResolvedValue({ lines: [] })
})

it('搜索覆盖图号和品牌，编制视图说明行内可改单行', async () => {
  user.value = { roles: ['mechanical_engineer'] }
  vi.mocked(read).mockResolvedValueOnce({ lines: [
    { bom_line: 1, item_code: 'A1', item_name: '支架', specification: 'Q235', drawing_number: 'DWG-7788', brand: '自制', shortage: '0' },
    { bom_line: 2, item_code: 'B2', item_name: '气缸', specification: 'SC50', drawing_number: '', brand: '亚德客', shortage: '0' },
  ] })
  const wrapper = shallowMount(BOMDemand, { props: { projectId: 1, status: 'active', canEditBom: true }, global: { plugins: [ElementPlus], renderStubDefaultSlot: true, stubs: { BusinessTable: { template: '<div />' } } } })
  await flushPromises()
  const scope = () => wrapper.get('[aria-label="BOM导出范围"]').text()
  expect(scope()).toContain('当前筛选 2 项')
  await wrapper.get('[aria-label="搜索 BOM 物料"]').setValue('dwg-7788')
  expect(scope()).toContain('当前筛选 1 项')
  await wrapper.get('[aria-label="搜索 BOM 物料"]').setValue('亚德客')
  expect(scope()).toContain('当前筛选 1 项')
  // 桌面端视图说明收进切换按钮旁的「?」悬停提示，不再单占一行；读屏从按钮名称读到全文，随视图切换。
  expect(wrapper.text()).not.toContain('行尾「操作」可改单行或移除')
  expect(wrapper.get('.bom-view-switch .bom-help-icon').attributes('aria-label')).toBe('视图说明：按单元核对规格、数量和需求日期；行尾「操作」可改单行或移除。')
  await wrapper.get('.bom-view-switch input[value="purchase"]').setValue()
  expect(wrapper.get('.bom-help-icon').attributes('aria-label')).toContain('库存为共享库存，不预留')
  // 「展开完整列」在页头工具栏里（导出旁边），不用滚到表格底部。
  const full = () => wrapper.get('.bom-panel-heading .toolbar').findAll('el-button-stub').find(button => button.attributes('aria-pressed') !== undefined && button.text().includes('完整列'))!
  expect(full().attributes('aria-label')).toBe('展开完整列（图号、品牌等）')
  expect(full().text()).toBe('展开完整列')
  await full().trigger('click')
  expect(full().text()).toBe('收起完整列')
  expect(full().attributes('aria-pressed')).toBe('true')
})

afterEach(() => { vi.mocked(read).mockReset(); vi.mocked(read).mockResolvedValue({ lines: [] }) })
function mountFull(lines: object[], props: object = {}, stubs: object = {}) {
  vi.mocked(read).mockResolvedValue({ revision: 'r1', lines })
  return mount(BOMDemand, { props: { projectId: 81, status: 'active', canEditBom: true, ...props }, global: {
    plugins: [ElementPlus], stubs: { RecordDeletionDialog: true, ActionDialog: true, BOMPurchasePicker: true, ImportFeedback: true, RouterLink: { props: ['to'], template: '<a class="router-link" :data-to="JSON.stringify(to)"><slot /></a>' }, ...stubs },
  } })
}
const names = (wrapper: ReturnType<typeof mountFull>) => wrapper.findAll('.bom-details-table tbody tr').map(row => row.find('strong').text())

it('采购草稿照常扣缺料但在途只算已批准，单独标「待批」，仅看缺料默认仍保留这些行', async () => {
  user.value = { roles: ['purchaser'] }
  batchMode.value = false
  const wrapper = mountFull([
    { bom_line: 1, item: 7, item_code: 'PKS', item_name: '直线导轨', assembly_unit: '01', quantity: '2', issued: '0', incoming: '2.000', unapproved: '2.000', available: '0', shortage: '0', required_date: '2026-01-06' },
    { bom_line: 2, item: 7, item_code: 'PKS', item_name: '直线导轨已到', assembly_unit: '03', quantity: '2', issued: '0', incoming: '2.000', unapproved: '0', available: '0', shortage: '0', required_date: '2026-01-06' },
    { bom_line: 3, item: 8, item_code: 'BRG', item_name: '轴承', assembly_unit: '03', quantity: '4', issued: '0', incoming: '0', unapproved: '0', available: '0', shortage: '4', required_date: '2026-01-07' },
    { bom_line: 4, item: 9, item_code: 'OK', item_name: '已配齐', assembly_unit: '03', quantity: '1', issued: '0', incoming: '0', unapproved: '0', available: '1', shortage: '0', required_date: '2026-01-01' },
  ], { canEditBom: false })
  await flushPromises()
  expect(names(wrapper)).toEqual(['直线导轨', '轴承'])
  const draft = wrapper.findAll('.bom-details-table tbody tr')[0]!
  expect(draft.text()).toContain('0待批 2')
  expect(draft.text()).toContain('已逾期·采购待批')
  expect(wrapper.findAll('.bom-details-table tbody tr')[1]!.text()).toContain('已逾期·缺料')
  await wrapper.findAll('label').find(label => label.text() === '含待批采购')!.get('input').setValue(false)
  expect(names(wrapper)).toEqual(['轴承'])
  await wrapper.findAll('label').find(label => label.text() === '仅看缺料')!.get('input').setValue(false)
  // 已批准未到货的过期行显示「在途未到」；已配齐的不提示。
  const rows = wrapper.findAll('.bom-details-table tbody tr')
  expect(rows.find(row => row.text().includes('直线导轨已到'))!.text()).toContain('已逾期·在途未到')
  expect(rows.find(row => row.text().includes('已配齐'))!.text()).not.toContain('已逾期')
  await wrapper.findAll('label').find(label => label.text() === '仅看逾期')!.get('input').setValue(true)
  expect(names(wrapper)).not.toContain('已配齐')
  wrapper.unmount()
  batchMode.value = true
})

it('工作台缺料直达：带 initialView=purchase 时兼任工程师的管理员也直接落在采购缺料视图', async () => {
  user.value = { roles: ['admin'] }
  const lines = [
    { bom_line: 1, item: 1, item_code: 'A', item_name: '缺料件', assembly_unit: '01', quantity: '2', issued: '0', incoming: '0', unapproved: '0', available: '0', shortage: '2', required_date: '2999-01-01' },
    { bom_line: 2, item: 2, item_code: 'B', item_name: '已配齐', assembly_unit: '01', quantity: '1', issued: '0', incoming: '0', unapproved: '0', available: '1', shortage: '0', required_date: '2999-01-01' },
  ]
  const direct = mountFull(lines, { initialView: 'purchase' })
  await flushPromises()
  expect((direct.get('input[type=radio][value="purchase"]').element as HTMLInputElement).checked).toBe(true)
  expect(names(direct)).toEqual(['缺料件'])
  direct.unmount()
  const normal = mountFull(lines)
  await flushPromises()
  expect((normal.get('input[type=radio][value="prepare"]').element as HTMLInputElement).checked).toBe(true)
  normal.unmount()
})

it('编制视图按单元自然排序，单元概览可点筛选，表头可按需求日期排序', async () => {
  user.value = { roles: ['mechanical_engineer'] }
  const wrapper = mountFull([
    { bom_line: 1, item: 1, item_code: 'B', item_name: '十单元件', assembly_unit: '10 下料', quantity: '1', shortage: '1', required_date: '2026-12-03' },
    { bom_line: 2, item: 2, item_code: 'A', item_name: '二单元件', assembly_unit: '2 检测', quantity: '1', shortage: '0', required_date: '2026-12-09' },
    { bom_line: 3, item: 3, item_code: 'C', item_name: '未分件', assembly_unit: '', quantity: '1', shortage: '0', required_date: '2026-12-01' },
    { bom_line: 4, item: 4, item_code: 'A', item_name: '十单元另一件', assembly_unit: '10 下料', quantity: '1', shortage: '1', required_date: '2026-12-02' },
  ])
  await flushPromises()
  expect(names(wrapper)).toEqual(['二单元件', '十单元另一件', '十单元件', '未分件'])
  const chips = wrapper.findAll('.bom-unit-chip')
  expect(chips.map(chip => chip.text())).toEqual(['2 检测1 行 · 缺 0', '10 下料2 行 · 缺 2', '未分单元1 行 · 缺 0'])
  await chips[1]!.trigger('click')
  expect(names(wrapper)).toEqual(['十单元另一件', '十单元件'])
  await chips[1]!.trigger('click')
  await wrapper.findAll('.sort-header').find(button => button.text().startsWith('需求日期'))!.trigger('click')
  expect(names(wrapper)).toEqual(['未分件', '十单元另一件', '十单元件', '二单元件'])
  wrapper.unmount()
})

it('工程师勾选筛选结果后批量改需求日期或移除，一次提交所选行', async () => {
  user.value = { roles: ['mechanical_engineer'] }
  const wrapper = mountFull([
    { bom_line: 11, item: 1, item_code: 'A', item_name: '支架', assembly_unit: '03 检测', quantity: '2', shortage: '0' },
    { bom_line: 12, item: 2, item_code: 'B', item_name: '气缸', assembly_unit: '03 检测', quantity: '1.5', shortage: '0' },
    { bom_line: 13, item: 3, item_code: 'C', item_name: '电机', assembly_unit: '01 上料', quantity: '1', shortage: '0' },
  ])
  await flushPromises()
  expect(wrapper.text()).not.toContain('批量删除（管理员）')
  await wrapper.get('[aria-label="筛选单元"]').setValue('03 检测')
  // 没勾选时不占一行；勾选本页后才出现批量栏和「选择筛选结果」。
  expect(wrapper.find('[aria-label="BOM批量修订"]').exists()).toBe(false)
  await wrapper.get('input[aria-label="选择本页BOM行"]').setValue(true)
  await wrapper.findAll('button').find(button => button.text() === '选择筛选结果（2 行）')!.trigger('click')
  expect(wrapper.get('[aria-label="BOM批量修订"]').text()).toContain('已选 2 行')
  await wrapper.findAll('button').find(button => button.text() === '批量改需求日期')!.trigger('click')
  const action = wrapper.getComponent({ name: 'ActionDialog' })
  const command = action.props('command')
  expect(command.title).toBe('批量改需求日期（2 行）')
  expect(command.prepare({ required_date: '2026-12-20', change_note: '03 单元延期' })).toEqual({
    expected_revision: 'r1',
    lines: [
      { id: 11, item: 1, quantity: '2', change_note: '03 单元延期', required_date: '2026-12-20' },
      { id: 12, item: 2, quantity: '1.5', change_note: '03 单元延期', required_date: '2026-12-20' },
    ],
  })
  await wrapper.findAll('button').find(button => button.text() === '批量移除')!.trigger('click')
  const remove = wrapper.getComponent({ name: 'ActionDialog' }).props('command')
  expect(remove.path).toBe('/business/bom/remove-batch/')
  expect(remove.prepare({ reason: '作废' })).toEqual({ project: 81, ids: [11, 12], reason: '作废' })
  wrapper.unmount()
})

it('变更记录从更多菜单打开，按项目分页读取并显示改前改后', async () => {
  user.value = { roles: ['manager'] }
  const wrapper = mountFull([{ bom_line: 1, item: 1, item_code: 'A', item_name: '支架', assembly_unit: '01', quantity: '2', shortage: '0' }])
  await flushPromises()
  vi.mocked(read).mockResolvedValueOnce({ count: 1, results: [
    { id: 5, created_at: '2026-11-10T09:30:12+08:00', actor: '张工', action: 'update', item_code: 'A', item_name: '支架', assembly_unit: '01', before: '2.000', after: '3.000', reason: 'ECN-12', details: ['需求日期 2026-11-06 → 2026-11-20'] },
  ] })
  wrapper.findAllComponents({ name: 'ElDropdown' }).find(dropdown => dropdown.text().includes('更多'))!.vm.$emit('command', 'changes')
  await flushPromises()
  expect(read).toHaveBeenLastCalledWith('/business/bom/changes/', { project: 81, page: 1, page_size: pageSize.value })
  const dialog = wrapper.findAllComponents({ name: 'ElDialog' }).find(item => item.props('title') === 'BOM 变更记录')!
  expect(dialog.text()).toContain('2026-11-10 09:30')
  expect(dialog.text()).toContain('2.000 → 3.000')
  expect(dialog.text()).toContain('需求日期 2026-11-06 → 2026-11-20')
  wrapper.unmount()
})

it('仓管在 BOM 页可直接进入按 BOM 领料', async () => {
  user.value = { roles: ['warehouse'] }
  const wrapper = mountFull([{ bom_line: 1, item: 1, item_code: 'A', item_name: '支架', assembly_unit: '01', quantity: '2', shortage: '0' }], { canEditBom: false })
  await flushPromises()
  const link = wrapper.findAll('.router-link').find(item => item.text() === '按 BOM 领料')!
  expect(JSON.parse(link.attributes('data-to')!)).toEqual({ path: '/inventory', query: { project: '81', issue: 'bom' } })
  wrapper.unmount()
  user.value = { roles: ['purchaser'] }
  const other = mountFull([], { canEditBom: false })
  await flushPromises()
  expect(other.text()).not.toContain('按 BOM 领料')
  other.unmount()
})

it('导入预览区分新增、修改、不变，列出文件外现有行，确认按钮不重复「确认」', async () => {
  vi.mocked(write).mockResolvedValueOnce({ can_import: true, token: 't1', note: '预览不占用编号。',
    lines: [{ row: 2, item_code: 'A', bom_action: 'update', before_quantity: '2.000', quantity: '3.000', product_category: '21' }, { row: 3, item_code: 'B', bom_action: 'unchanged', quantity: '1.000', material_action: '沿用已有物料，补填品牌' }, { row: 4, item_code: 'N', bom_action: 'create', quantity: '1.000', new_material: true }],
    summary: { create: 1, update: 1, unchanged: 1, untouched: 1 }, untouched: [{ item_code: 'Z', item_name: '旧件', assembly_unit: '05', quantity: '2.000' }], errors: [] })
  const wrapper = mountImport()
  await uploadFile(wrapper)
  await flushPromises()
  expect(wrapper.text()).toContain('新增 1 行、修改 1 行、不变 1 行')
  expect(wrapper.text()).toContain('；为 1 行已有物料补填品牌。')
  expect(wrapper.text()).toContain('文件中未出现的现有行 1 条：导入不会移除这些行')
  expect(wrapper.text()).toContain('下载并填写模板（需要时可重新下载）')
  const rows = wrapper.getComponent({ name: 'ImportFeedback' }).props('rows')
  expect(rows.map((row: { data: { bom_change: string } }) => row.data.bom_change)).toEqual(['修改 2 → 3', '不变', '新增'])
  expect(rows[0].data.product_category).toBe('无图·标准件')
  await wrapper.findAll('el-button-stub').find(button => button.text() === '确认导入')!.trigger('click')
  const command = wrapper.getComponent({ name: 'ActionDialog' }).props('command')
  expect(command.submitLabel).toBe('确认导入')
  expect(command.notice.text).toContain('将新增 1 行、修改 1 行，与现有一致的 1 行跳过，新建物料 1 个，为 1 行已有物料补填品牌。')
  wrapper.unmount()
})

it('手机窄屏只留勾选、物料摘要和操作，筛选收起显示生效数，采购选择栏压成一行', async () => {
  vi.stubGlobal('matchMedia', vi.fn().mockReturnValue({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() }))
  user.value = { roles: ['mechanical_engineer'] }
  const lines = [
    { bom_line: 1, item: 1, item_code: 'A1', item_name: '支架', specification: 'SUS304', assembly_unit: '01 上料', quantity: '2', unit: '件', issued: '0', incoming: '1', unapproved: '1', available: '0', shortage: '1', required_date: '2026-01-06' },
    { bom_line: 2, item: 2, item_code: 'B2', item_name: '气缸', specification: 'CDQ2B', assembly_unit: '02 检测', quantity: '1', unit: '个', issued: '0', incoming: '0', unapproved: '0', available: '1', shortage: '0', required_date: '2099-01-01' },
  ]
  let wrapper = mountFull(lines)
  await flushPromises()
  const headers = wrapper.findAll('.bom-details-table thead th').map(th => th.text()).filter(Boolean)
  expect(headers).toEqual(['物料', '操作'])
  const first = wrapper.findAll('.bom-details-table tbody tr')[0]!
  expect(first.get('.bom-mobile-summary').text()).toContain('SUS304 · 01 上料')
  expect(first.get('.bom-mobile-summary').text()).toContain('需求 2 件 · 缺 1 · 2026-01-06')
  expect(first.text()).toContain('已逾期·缺料')
  expect(wrapper.text()).not.toContain('展开完整列')
  // 次级筛选收起，只留搜索框和「筛选 ▾」；点单元概览后显示生效数。
  const toggle = wrapper.get('.bom-filter-toggle')
  expect(toggle.text()).toBe('筛选 ▾')
  expect(wrapper.get('.bom-filter-group').classes()).toContain('is-collapsed')
  await wrapper.findAll('.bom-unit-chip')[0]!.trigger('click')
  expect(toggle.text()).toBe('筛选 · 1 ▾')
  await toggle.trigger('click')
  expect(wrapper.get('.bom-filter-group').classes()).not.toContain('is-collapsed')
  expect(wrapper.find('[aria-label="排序方式"]').exists()).toBe(true)
  // 说明默认收起。
  expect(wrapper.text()).not.toContain('按单元核对规格')
  await wrapper.get('.bom-help-toggle').trigger('click')
  expect(wrapper.text()).toContain('按单元核对规格')
  wrapper.unmount()

  user.value = { roles: ['purchaser'] }
  wrapper = mountFull(lines, { canEditBom: false })
  await flushPromises()
  const summary = wrapper.findAll('.bom-details-table tbody tr')[0]!.get('.bom-mobile-summary').text()
  expect(summary).toContain('缺 1 · 在途 0（待批 1） · 可用 0')
  expect(summary).toContain('01 上料 · 需 2026-01-06')
  const bar = wrapper.get('.bom-selection-bar')
  expect(bar.findAll('button').map(button => button.attributes('aria-label') || button.text())).toEqual(['全选筛选结果', '清空选择', '从 BOM 多选下单'])
  expect(bar.text()).toContain('全选')
  wrapper.unmount()
  vi.unstubAllGlobals()
})

it('停用物料整页提示并行内标出，采购复选框说明原因，修改此行置灰只留替换或移除', async () => {
  user.value = { roles: ['mechanical_engineer'] }
  const lines = [
    { bom_line: 1, item: 1, item_code: 'S1', item_name: '光电传感器', assembly_unit: '01', quantity: '6', shortage: '6', is_active: false },
    { bom_line: 2, item: 2, item_code: 'A2', item_name: '支架', assembly_unit: '01', quantity: '2', shortage: '2', is_active: true },
  ]
  let wrapper = mountFull(lines, {}, {
    ElDropdown: { template: '<div><slot /><slot name="dropdown" /></div>' },
    ElDropdownMenu: { template: '<div><slot /></div>' },
    ElDropdownItem: { props: ['command', 'disabled'], template: '<div class="menu-item" :data-command="command" :data-disabled="String(!!disabled)"><slot /></div>' },
  })
  await flushPromises()
  expect(wrapper.get('.bom-inactive-note').text()).toContain('1 行物料已停用')
  expect(wrapper.get('.bom-inactive-note').text()).toContain('替换物料')
  const rows = wrapper.findAll('.bom-details-table tbody tr')
  expect(rows.find(row => row.text().includes('光电传感器'))!.text()).toContain('已停用')
  expect(rows.find(row => row.text().includes('支架'))!.text()).not.toContain('已停用')
  await wrapper.get('.bom-inactive-note button').trigger('click')
  expect(names(wrapper)).toEqual(['光电传感器'])
  const edits = wrapper.findAll('.bom-details-table tbody tr .menu-item[data-command="修改此行"]')
  expect(edits.map(item => [item.attributes('data-disabled'), item.text()])).toEqual([['true', '修改此行（物料已停用，请替换）']])
  await wrapper.findAll('.bom-inactive-note button').at(-1)!.trigger('click')
  const active = wrapper.findAll('.bom-details-table tbody tr').find(row => row.text().includes('支架'))!
  expect(active.get('.menu-item[data-command="修改此行"]').attributes('data-disabled')).toBe('false')
  wrapper.unmount()

  user.value = { roles: ['purchaser'] }
  wrapper = mountFull(lines, { canEditBom: false })
  await flushPromises()
  expect(wrapper.get('.bom-inactive-note').text()).toContain('不能采购')
  const box = wrapper.get('input[aria-label="选择 S1 01"]')
  expect(box.attributes('disabled')).toBeDefined()
  expect(box.attributes('title')).toContain('物料已停用')
  expect(wrapper.get('input[aria-label="选择 A2 01"]').attributes('title')).toBeUndefined()
  wrapper.unmount()
})

it('管理员在采购视图开批量删除：改用删除勾选，采购勾选和下单栏让出，退出后恢复', async () => {
  user.value = { roles: ['admin'] }
  const lines = [
    { bom_line: 1, item: 1, item_code: 'A', item_name: '缺料件', assembly_unit: '01', quantity: '2', issued: '0', incoming: '0', unapproved: '0', available: '0', shortage: '2', required_date: '2999-01-01' },
    { bom_line: 2, item: 2, item_code: 'B', item_name: '另一缺料件', assembly_unit: '02', quantity: '1', issued: '0', incoming: '0', unapproved: '0', available: '0', shortage: '1', required_date: '2999-01-01' },
  ]
  const wrapper = mountFull(lines, { initialView: 'purchase' })
  await flushPromises()
  // 两套勾选不并排：采购勾选列、底部下单栏和行尾「操作」列都让出，1280 宽不再横向滚动。
  expect(wrapper.find('[aria-label="选择 A 01"]').exists()).toBe(false)
  expect(wrapper.find('.bom-selection-bar').exists()).toBe(false)
  expect(wrapper.findAll('.bom-details-table th').map(th => th.text())).not.toContain('操作')
  await wrapper.get('[aria-label="选择BOM明细 B 02"]').setValue(true)
  expect(wrapper.get('[aria-label="BOM批量选择"]').text()).toContain('已选 1')
  await wrapper.findAll('button').find(b => b.text() === '批量删除（1）')!.trigger('click')
  expect(wrapper.getComponent(RecordDeletionDialog).props('rows')!.map(row => row.id)).toEqual([2])
  batchMode.value = false
  await flushPromises()
  expect(wrapper.find('[aria-label="选择 A 01"]').exists()).toBe(true)
  expect(wrapper.find('.bom-selection-bar').exists()).toBe(true)
  expect(wrapper.find('[aria-label="BOM批量选择"]').exists()).toBe(false)
  wrapper.unmount()
  batchMode.value = true
})
