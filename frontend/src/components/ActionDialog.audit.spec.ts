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
