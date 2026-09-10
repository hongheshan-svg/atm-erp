import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import FormFields from './FormFields.vue'

describe('明细表单编辑', () => {
  it('在分页列表添加行后显示新增行，保留已有页的数据', async () => {
    const data = { lines: Array.from({ length: 21 }, (_, i) => ({ quantity: String(i + 1) })) }
    const wrapper = mount(FormFields, {
      props: { modelValue: data, fields: [{ key: 'lines', label: '明细', type: 'rows', fields: [{ key: 'quantity', label: '数量' }] }] },
      global: { stubs: { ElButton: { template: '<button type="button"><slot /></button>' } } },
    })
    expect(wrapper.findAll('input')).toHaveLength(20)
    await wrapper.findAll('button').find(button => button.text() === '添加行')!.trigger('click')
    expect(data.lines).toHaveLength(22)
    expect(wrapper.text()).toContain('第 22 行')
    expect(wrapper.findAll('input')).toHaveLength(2)
    expect((wrapper.findAll('input')[1]!.element as HTMLInputElement).value).toBe('')
    expect(data.lines[0]?.quantity).toBe('1')
  })

  it('只读说明不能编辑，银行金额键盘保留负号输入能力', () => {
    const wrapper = mount(FormFields, { props: { modelValue: { note: '已归档说明', amount: '-10' }, fields: [
      { key: 'note', label: '说明', type: 'textarea', readonly: true },
      { key: 'amount', label: '银行金额', numeric: { scale: 2, signed: true } },
    ] } })
    expect(wrapper.get('textarea').attributes()).toHaveProperty('disabled')
    expect(wrapper.get('input').attributes('inputmode')).toBe('text')
  })
})
