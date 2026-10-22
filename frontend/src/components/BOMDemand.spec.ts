import { afterEach, expect, it, vi } from 'vitest'
import { flushPromises, shallowMount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import BOMDemand from './BOMDemand.vue'
import { user } from '../session'
import { download, read, write } from '../api'
vi.mock('../api', () => ({ read: vi.fn().mockResolvedValue({ lines: [] }), all: vi.fn().mockResolvedValue([]), write: vi.fn(), download: vi.fn() }))
afterEach(() => { user.value = null; vi.clearAllMocks(); vi.restoreAllMocks() })

it('工程师BOM维护和导入取当前项目权限，兼采购全局可读项目不扩写权限', async () => {
  user.value = { roles: ['mechanical_engineer', 'purchaser'] }
  const wrapper = shallowMount(BOMDemand, { props: { projectId: 1, status: 'active', canEditBom: false }, global: { plugins: [ElementPlus], renderStubDefaultSlot: true, stubs: { ImportFeedback: false, RouterLink: true, ElTable: { template: '<div />' } } } })
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
    stubs: { ImportFeedback: false, RouterLink: true, ElDialog: dialogStub, ElTable: { template: '<div />' } },
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
  expect(wrapper.get('[role="status"]').text()).toContain('正在读取文件')
  expect(wrapper.findAll('el-button-stub').find(button => button.text() === '确认导入')!.attributes('disabled')).toBe('true')
  await wrapper.findAll('el-button-stub').find(button => button.text() === '关闭')!.trigger('click')
  expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
  vi.mocked(write).mockResolvedValueOnce({ can_import: true, lines: [{ row: 2 }], token: 'new-preview' })
  await uploadFile(wrapper)
  await flushPromises()
  finish({ can_import: false, lines: [], errors: [{ message: '旧请求错误' }] })
  await flushPromises()
  expect(wrapper.get('[role="status"]').text()).toContain('校验通过，共 1 条明细')
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
  const wrapper = shallowMount(BOMDemand, { props: { projectId: 1, status: 'active', canEditBom: true }, global: { plugins: [ElementPlus], renderStubDefaultSlot: true, stubs: { ImportFeedback: false, RouterLink: true, ElTable: { template: '<div />' } } } })
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
  vi.mocked(read).mockResolvedValueOnce({ lines: [
    { bom_line: 41, item_code: 'I1', item_name: '电机', assembly_unit: '单元A', quantity: '5', shortage: '2' },
    { bom_line: 42, item_code: 'I1', item_name: '电机', assembly_unit: '单元B', quantity: '3', shortage: '1' },
  ] })
  const wrapper = shallowMount(BOMDemand, { props: { projectId: 1, status: 'active', canEditBom: true }, global: {
    plugins: [ElementPlus], renderStubDefaultSlot: true,
    stubs: { RouterLink: true, ElTableColumn: { template: '<div class="col" />' } },
  } })
  await flushPromises()
  expect(wrapper.findAll('.col').filter(col => col.attributes('type') !== 'selection').slice(0, 6).map(col => col.attributes('label'))).toEqual(['物料名称 / 编码', '规格', '单元', '需求数量', '单位', '需求日期'])
  expect(wrapper.text()).not.toContain('从 BOM 多选下单')
  await wrapper.get('input[value=purchase]').setValue()
  const labels = wrapper.findAll('.col').map(col => col.attributes('label'))
  expect(labels.indexOf('需求数量')).toBeLessThan(labels.indexOf('在途'))
  expect(labels).not.toContain('图号')
  await wrapper.findAll('el-button-stub').find(button => button.text() === '全选筛选结果')!.trigger('click')
  await wrapper.findAll('el-button-stub').find(button => button.text() === '按缺料采购')!.trigger('click')
  expect(wrapper.getComponent({ name: 'BOMPurchasePicker' }).props('initialSelection')).toEqual([41, 42])
  wrapper.unmount()
})
