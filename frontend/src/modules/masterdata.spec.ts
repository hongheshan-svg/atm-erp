import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { ElMessage } from 'element-plus'
import ActionDialog from '../components/ActionDialog.vue'
import { installElementPlus } from '../plugins/elementPlus'
import { write } from '../api'
import { user } from '../session'
import type { Command } from '../types'
import { actionCommand, createCommand } from './masterdata'

vi.mock('../api', () => ({ write: vi.fn(), read: vi.fn(), all: vi.fn() }))

const term = '[aria-label="供应商默认采购账期"]'
const days = '[aria-label="自定义月结天数（0～365）"]'
function open(command: Command) {
  return mount(ActionDialog, {
    props: { command },
    global: {
      plugins: [{ install: installElementPlus }],
      stubs: { ElDialog: { template: '<div><slot /></div>' }, RouterLink: true },
    },
  })
}
beforeEach(() => {
  user.value = { id: 1, roles: ['admin'] }
  vi.mocked(write).mockResolvedValue({ id: 1 })
})
afterEach(() => {
  vi.resetAllMocks()
  user.value = null
  ElMessage.closeAll()
})

it('新增客户隐藏采购账期，切回客户后不校验或提交残留的供应商输入', async () => {
  const wrapper = open(await createCommand('partners'))
  expect(wrapper.find(term).exists()).toBe(false)
  await wrapper.get('[aria-label="单位名称"]').setValue('测试客户')
  await wrapper.get('[aria-label="类型"]').setValue('supplier')
  await wrapper.get(term).setValue('custom')
  await wrapper.get(days).setValue('错误天数')
  await wrapper.get('[aria-label="类型"]').setValue('customer')
  expect(wrapper.find(term).exists()).toBe(false)
  expect(wrapper.find(days).exists()).toBe(false)
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(write).toHaveBeenCalledWith('/business/partners/', {
    name: '测试客户', kind: 'customer', payment_term: 'manual', payment_days: 0,
  }, expect.any(String), undefined)
  expect(wrapper.emitted('saved')).toHaveLength(1)
  wrapper.unmount()
})

it.each(['supplier', 'both'])('%s 显示采购账期，切换类型保留未保存输入并正确提交', async kind => {
  const wrapper = open(await createCommand('partners'))
  await wrapper.get('[aria-label="单位名称"]').setValue('测试供应商')
  await wrapper.get('[aria-label="类型"]').setValue(kind)
  await wrapper.get(term).setValue('custom')
  await wrapper.get(days).setValue('45')
  await wrapper.get('[aria-label="类型"]').setValue('customer')
  await wrapper.get('[aria-label="类型"]').setValue(kind)
  expect((wrapper.get(term).element as HTMLSelectElement).value).toBe('custom')
  expect((wrapper.get(days).element as HTMLInputElement).value).toBe('45')
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(write).toHaveBeenCalledWith('/business/partners/', {
    name: '测试供应商', kind, payment_term: 'custom', payment_days: '45',
  }, expect.any(String), undefined)
  wrapper.unmount()
})

it('已有供应商改为客户时重置供应商默认账期，编辑客户也隐藏账期', async () => {
  const wrapper = open(await actionCommand('partners', {
    id: 7, name: '测试单位', kind: 'supplier', payment_term: 'month60', payment_days: 60, is_active: true,
  }, '编辑'))
  expect((wrapper.get(term).element as HTMLSelectElement).value).toBe('month60')
  await wrapper.get('[aria-label="类型"]').setValue('customer')
  expect(wrapper.find(term).exists()).toBe(false)
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(write).toHaveBeenCalledWith('/business/partners/7/', {
    name: '测试单位', kind: 'customer', is_active: true, payment_term: 'manual', payment_days: 0,
  }, expect.any(String), 'patch')
  await wrapper.setProps({ command: await actionCommand('partners', {
    id: 7, name: '测试单位', kind: 'customer', payment_term: 'manual', payment_days: 0, is_active: true,
  }, '编辑') })
  expect(wrapper.find(term).exists()).toBe(false)
  expect(wrapper.find(days).exists()).toBe(false)
  wrapper.unmount()
})

it('仅销售经理仍只能选择客户且不显示供应商账期', async () => {
  user.value = { id: 2, roles: ['sales_manager'] }
  const wrapper = open(await createCommand('partners'))
  expect(wrapper.find('[aria-label="类型"] option[value="supplier"]').exists()).toBe(false)
  expect(wrapper.find('[aria-label="类型"] option[value="both"]').exists()).toBe(false)
  await wrapper.get('[aria-label="类型"]').setValue('customer')
  expect(wrapper.find(term).exists()).toBe(false)
  expect(wrapper.find(days).exists()).toBe(false)
  wrapper.unmount()
})
