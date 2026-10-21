import { afterEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import InlineDocumentField from './InlineDocumentField.vue'
import { read, readBlob, write } from '../api'

vi.mock('../api', () => ({ write: vi.fn(), read: vi.fn(), readBlob: vi.fn(), download: vi.fn() }))
afterEach(() => { vi.resetAllMocks() })
function open() {
  return mount(InlineDocumentField, { props: { field: { key: 'document', label: '结算凭证', upload: { context: { project: 8 }, category: 'receipt' } } }, global: { stubs: { ElButton: { template: '<button><slot /></button>' }, ElDialog: true } } })
}
it('就地上传关联当前项目，成功后选中；失败保留原选择且解除忙碌', async () => {
  const wrapper = open()
  const input = wrapper.get('input[type=file]')
  Object.defineProperty(input.element, 'files', { value: [new File(['evidence'], '回单.pdf', { type: 'application/pdf' })], configurable: true })
  vi.mocked(write).mockResolvedValue({ id: 18, original_name: '回单.pdf' })
  await input.trigger('change')
  await flushPromises()
  const body = vi.mocked(write).mock.calls[0]![1] as FormData
  expect(body.get('project')).toBe('8')
  expect(body.get('category')).toBe('receipt')
  expect(wrapper.emitted('update:modelValue')).toEqual([[18]])
  await wrapper.setProps({ modelValue: 18 })
  vi.mocked(write).mockRejectedValue(new Error('上传失败'))
  await input.trigger('change')
  await flushPromises()
  expect(wrapper.text()).toContain('上传失败')
  expect(wrapper.emitted('update:modelValue')).toHaveLength(1)
  expect(wrapper.emitted('busy')?.at(-1)).toEqual([false])
  wrapper.unmount()
})
it('附件预览通过鉴权下载，不直接嵌入原下载地址；不支持格式给出下载说明', async () => {
  const wrapper = open()
  await wrapper.setProps({ modelValue: 18 })
  vi.mocked(read).mockResolvedValue({ download_url: '/api/business/documents/18/download/', original_name: '图纸.dwg' })
  vi.mocked(readBlob).mockResolvedValue(new Blob(['drawing'], { type: 'application/octet-stream' }))
  await wrapper.findAll('button').find(b => b.text() === '预览附件')!.trigger('click')
  await flushPromises()
  expect(readBlob).toHaveBeenCalledWith('/api/business/documents/18/download/')
  expect(wrapper.text()).toContain('该格式请下载')
  expect(wrapper.find('iframe').exists()).toBe(false)
  wrapper.unmount()
})
it('同一文件上传失败后重传复用同一幂等键，成功后与换文件均使用新键', async () => {
  const wrapper = open()
  const input = wrapper.get('input[type=file]')
  const pick = async (file: File) => { Object.defineProperty(input.element, 'files', { value: [file], configurable: true }); await input.trigger('change'); await flushPromises() }
  const a = new File(['a'], '回单.pdf', { type: 'application/pdf', lastModified: 1 })
  const b = new File(['bb'], '回单2.pdf', { type: 'application/pdf', lastModified: 2 })
  vi.mocked(write).mockRejectedValueOnce(new Error('timeout')).mockRejectedValueOnce(new Error('timeout')).mockResolvedValue({ id: 1, original_name: '回单.pdf' })
  await pick(a)
  await pick(a)
  const keys = () => vi.mocked(write).mock.calls.map(call => call[2])
  expect(keys()[1]).toBe(keys()[0])
  await pick(b)
  expect(keys()[2]).not.toBe(keys()[0])
  await pick(b)
  expect(keys()[3]).not.toBe(keys()[2])
  wrapper.unmount()
})
