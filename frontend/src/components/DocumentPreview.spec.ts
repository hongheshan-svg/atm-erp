import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import DocumentPreview from './DocumentPreview.vue'
import { download, read, readBlob } from '../api'
vi.mock('../api', () => ({ read: vi.fn(), readBlob: vi.fn(), download: vi.fn() }))
const wrappers: ReturnType<typeof mount>[] = []
beforeEach(() => { vi.clearAllMocks(); vi.stubGlobal('URL', { createObjectURL: vi.fn(() => 'blob:private-image'), revokeObjectURL: vi.fn() }) })
afterEach(() => { wrappers.splice(0).forEach(wrapper => wrapper.unmount()); vi.unstubAllGlobals() })
function open(id = 8) {
  const wrapper = mount(DocumentPreview, { props: { document: { id, name: '比价表.xlsx' } }, global: { stubs: { ElDialog: { template: '<div><slot /><slot name="footer" /></div>' }, ElButton: { template: '<button><slot /></button>' }, PdfPreview: true } } })
  wrappers.push(wrapper); return wrapper
}
function table(page = 1, sheet = 0) {
  return { kind: 'spreadsheet', name: '比价表.xlsx', sheet, sheets: [{ index: 0, name: '比价' }, { index: 2, name: '技术资料' }], page, total_pages: 2, total_rows: 101, columns: ['A', 'B'], rows: [{ number: page === 1 ? 1 : 101, cells: [sheet === 0 ? `000${page}` : '另一工作表', '<img src=x onerror=alert(1)>'] }], warnings: ['公式显示已保存的结果。'] }
}
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>(done => { resolve = done }); return { promise, resolve } }
it('表格保留文本编码，内容安全显示；翻页和切工作表不改变原附件', async () => {
  vi.mocked(read).mockImplementation(async (_path, params) => table(params?.page, params?.sheet))
  const wrapper = open(); await flushPromises()
  expect(wrapper.text()).toContain('0001'); expect(wrapper.find('img').exists()).toBe(false)
  await wrapper.findAll('button').find(button => button.text() === '下一页内容')!.trigger('click'); await flushPromises()
  expect(read).toHaveBeenLastCalledWith('/business/documents/8/preview/', { page: 2, sheet: 0 })
  expect(wrapper.text()).toContain('0002'); expect(wrapper.text()).not.toContain('0001')
  await wrapper.get('select[aria-label="工作表"]').setValue('2'); await flushPromises()
  expect(read).toHaveBeenLastCalledWith('/business/documents/8/preview/', { page: 1, sheet: 2 })
  expect(wrapper.text()).toContain('另一工作表')
  await wrapper.get('input[type=search]').setValue('没有匹配内容')
  expect(wrapper.text()).toContain('本页未找到匹配内容')
  await wrapper.findAll('button').find(button => button.text() === '下载原文件')!.trigger('click'); await flushPromises()
  expect(download).toHaveBeenCalledWith('/business/documents/8/download/', '比价表.xlsx')
})
it('切换附件后旧请求不能覆盖新文件，加载中不残留旧文件内容', async () => {
  const old = deferred<object>()
  vi.mocked(read).mockReturnValueOnce(old.promise).mockResolvedValue({ kind: 'text', name: '新文件.txt', text: '当前文件内容' })
  const wrapper = open(); await wrapper.setProps({ document: { id: 9 } }); await flushPromises()
  expect(wrapper.text()).toContain('当前文件内容')
  old.resolve({ kind: 'text', text: '旧合同内容' }); await flushPromises()
  expect(wrapper.text()).not.toContain('旧合同内容')
})
it('图像走鉴权接口并释放临时URL；切换中迟到的图像不泄漏到新文件', async () => {
  const old = deferred<Blob>()
  vi.mocked(read).mockResolvedValueOnce({ kind: 'image', name: '旧图.png', file_url: '/api/business/documents/8/preview-file/' }).mockResolvedValue({ kind: 'image', name: '新图.png', file_url: '/api/business/documents/9/preview-file/' })
  vi.mocked(readBlob).mockReturnValueOnce(old.promise).mockResolvedValue(new Blob(['new'], { type: 'image/png' }))
  const wrapper = open(); await flushPromises()
  await wrapper.setProps({ document: { id: 9 } }); await flushPromises()
  expect(readBlob).toHaveBeenLastCalledWith('/api/business/documents/9/preview-file/')
  expect(wrapper.get('img').attributes('src')).toBe('blob:private-image')
  old.resolve(new Blob(['old'])); await flushPromises()
  expect(URL.createObjectURL).toHaveBeenCalledTimes(1)
  await wrapper.setProps({ document: { id: 10 } }); await flushPromises()
  expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:private-image')
})
it('权限失效或文件异常给出可重试中文提示，退出登录关闭预览', async () => {
  vi.mocked(read).mockRejectedValueOnce(new Error('没有附件查看权限')).mockResolvedValue({ kind: 'unsupported', name: '图纸.dwg', message: '请下载后用CAD软件打开，或提供PDF版本。' })
  const wrapper = open(); await flushPromises()
  expect(wrapper.text()).toContain('没有附件查看权限')
  await wrapper.findAll('button').find(button => button.text() === '重试预览')!.trigger('click'); await flushPromises()
  expect(wrapper.text()).toContain('提供PDF版本')
  expect(wrapper.text()).not.toContain('没有附件查看权限')
  window.dispatchEvent(new Event('erp-session'))
  expect(wrapper.emitted('close')).toHaveLength(1)
})
