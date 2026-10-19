import { afterEach, expect, it, vi } from 'vitest'
import { flushPromises, shallowMount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import BOMDemand from './BOMDemand.vue'
import { user } from '../session'
import { download, write } from '../api'
vi.mock('../api', () => ({ read: vi.fn().mockResolvedValue({ lines: [] }), all: vi.fn().mockResolvedValue([]), write: vi.fn(), download: vi.fn() }))
afterEach(() => { user.value = null })

it('工程师BOM维护和导入取当前项目权限，兼采购全局可读项目不扩写权限', async () => {
  user.value = { roles: ['mechanical_engineer', 'purchaser'] }
  const wrapper = shallowMount(BOMDemand, { props: { projectId: 1, status: 'active', canEditBom: false }, global: { plugins: [ElementPlus], renderStubDefaultSlot: true, stubs: { RouterLink: true, ElTable: { template: '<div />' } } } })
  await flushPromises()
  expect(wrapper.text()).not.toContain('维护 BOM')
  expect(wrapper.text()).not.toContain('下载填写说明')
  expect(wrapper.find('input[type="file"]').exists()).toBe(false)
  await wrapper.setProps({ canEditBom: true })
  expect(wrapper.text()).toContain('维护 BOM')
  expect(wrapper.find('input[type="file"]').exists()).toBe(true)
  vi.mocked(download).mockResolvedValue(undefined)
  await wrapper.findAll('el-button-stub').find(button => button.text() === '下载填写说明')!.trigger('click')
  await flushPromises()
  expect(download).toHaveBeenCalledWith('/business/projects/bom-template/', 'bom-template-guide.html', { file_format: 'html' })
  await wrapper.setProps({ canEditBom: false })
  expect(wrapper.text()).not.toContain('维护 BOM')
  expect(wrapper.find('input[type="file"]').exists()).toBe(false)
  wrapper.unmount()
})

it('BOM导入错误逐行显示中文，保留行号且不输出原始数据字段', async () => {
  user.value = { roles: ['admin'] }
  vi.mocked(write).mockResolvedValueOnce({ lines: [], can_import: false, errors: [
    { row: 2, message: '需求数量：请输入正数。' },
    { message: '请重新上传文件。' },
  ] })
  const wrapper = shallowMount(BOMDemand, { props: { projectId: 1, status: 'active', canEditBom: true }, global: { plugins: [ElementPlus], renderStubDefaultSlot: true, stubs: { RouterLink: true, ElTable: { template: '<div />' } } } })
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
