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
