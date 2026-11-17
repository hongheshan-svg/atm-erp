import { afterEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { ElMessage } from 'element-plus'
import ActionDialog from './ActionDialog.vue'
import { installElementPlus } from '../plugins/elementPlus'
import { write } from '../api'

vi.mock('../api', () => ({ write: vi.fn() }))
afterEach(() => { vi.resetAllMocks(); sessionStorage.clear(); ElMessage.closeAll() })
it('嵌套服务端错误含行号，点击汇总可翻页定位实际数量输入', async () => {
  vi.mocked(write).mockRejectedValue({ response: { data: { lines: { 21: { quantity: ['数量超出允许范围。'] } } } } })
  const wrapper = mount(ActionDialog, {
    props: { inline: true, command: {
      title: '修改采购', path: '/business/purchases/1/edit/',
      fields: [{ key: 'lines', label: '采购明细', type: 'rows', readonly: true, fields: [{ key: 'quantity', label: '数量' }] }],
      initial: { lines: Array.from({ length: 22 }, () => ({ quantity: '1' })) },
    } }, global: { plugins: [{ install: installElementPlus }] }, attachTo: document.body,
  })
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(wrapper.get('.field-issues').text()).toContain('采购明细第 22 行 · 数量')
  await wrapper.get('.field-issues button').trigger('click')
  await flushPromises()
  const input = wrapper.get('[data-field-path="lines.21.quantity"] input')
  expect(input.attributes('aria-invalid')).toBe('true')
  expect(document.activeElement).toBe(input.element)
  await input.setValue('2')
  expect(wrapper.find('.field-issues').exists()).toBe(false)
  wrapper.unmount()
})
it('服务端错误全部落到字段时不再另起顶部红条，非字段错误仍在顶部提示', async () => {
  const mountWith = () => mount(ActionDialog, {
    props: { inline: true, command: { title: '报价', path: '/business/sales/1/quote/', fields: [{ key: 'amount', label: '报价金额（元）' }], initial: { amount: '5' } } },
    global: { plugins: [{ install: installElementPlus }] }, attachTo: document.body,
  })
  vi.mocked(write).mockRejectedValue({ response: { data: { amount: ['请输入大于 0 的数字，最多 2 位小数。'] } } })
  const wrapper = mountWith()
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(wrapper.find('.el-alert').exists()).toBe(false)
  expect(wrapper.get('.field-issues').text()).toContain('报价金额（元）：请输入大于 0 的数字')
  wrapper.unmount()
  vi.mocked(write).mockRejectedValue({ response: { data: { detail: '销售已签约，不能再报价。' } } })
  const other = mountWith()
  await other.get('form').trigger('submit')
  await flushPromises()
  expect(other.get('.el-alert').text()).toContain('销售已签约')
  other.unmount()
})
