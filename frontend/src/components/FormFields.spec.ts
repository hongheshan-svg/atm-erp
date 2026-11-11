import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import FormFields from './FormFields.vue'
import { ElSelect } from 'element-plus'
import { reactive } from 'vue'
import { wideCommand } from '../form-experience'

describe('明细表单编辑', () => {
  it('多人选项联动保留仍在范围内的执行人，只清除失效人员', async () => {
    const data = { project: 1, assignees: [1, 2] }
    const wrapper = mount(FormFields, { props: { modelValue: data, fields: [{
      key: 'assignees', label: '执行人', type: 'multi', optionsFor: row => row.project === 1
        ? [{ value: 1, label: '张工' }, { value: 2, label: '李工' }]
        : [{ value: 2, label: '李工' }, { value: 3, label: '王工' }],
    }] } })
    expect(data.assignees).toEqual([1, 2])
    const changed = { project: 2, assignees: [1, 2] }
    await wrapper.setProps({ modelValue: changed })
    expect(changed.assignees).toEqual([2])
    wrapper.unmount()
  })
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

  it('紧凑模式也显示行号，仍可正常编辑与移除', async () => {
    const data = { lines: [{ item_name: '伺服电机', quantity: '2' }] }
    const wrapper = mount(FormFields, {
      props: { modelValue: data, fields: [{ key: 'lines', label: '采购明细', type: 'rows', compact: true, fields: [
        { key: 'item_name', label: '物料', readonly: true },
        { key: 'quantity', label: '数量' },
      ] }] },
      global: { stubs: { ElButton: { template: '<button type="button"><slot /></button>' } } },
    })
    expect(wrapper.find('.line-fields-compact').exists()).toBe(true)
    expect(wrapper.get('.line-number').text()).toBe('第 1 行')
    await wrapper.get('input[aria-label="数量"]').setValue('5')
    expect(data.lines[0]?.quantity).toBe('5')
    await wrapper.findAll('button').find(button => button.text() === '移除此行')!.trigger('click')
    expect(data.lines).toHaveLength(0)
  })

  it('只读说明不能编辑，银行金额键盘保留负号输入能力', () => {
    const wrapper = mount(FormFields, { props: { modelValue: { note: '已归档说明', amount: '-10' }, fields: [
      { key: 'note', label: '说明', type: 'textarea', readonly: true },
      { key: 'amount', label: '银行金额', numeric: { scale: 2, signed: true } },
    ] } })
    expect(wrapper.get('textarea').attributes()).toHaveProperty('disabled')
    expect(wrapper.get('input').attributes('inputmode')).toBe('text')
  })
  it('可搜索的单选渲染为可过滤的 ElSelect，选中值写回模型；未设置时仍是原生下拉', async () => {
    const data = reactive<Record<string, unknown>>({ manager: 2, other: '' })
    const options = [{ value: 1, label: '张工' }, { value: 2, label: '李工' }]
    const wrapper = mount(FormFields, { props: { modelValue: data, fields: [
      { key: 'manager', label: '负责人', type: 'select', searchable: true, options },
      { key: 'other', label: '其他', type: 'select', options },
    ] } })
    const select = wrapper.findComponent(ElSelect)
    expect(select.exists()).toBe(true)
    expect(select.props('filterable')).toBe(true)
    expect(select.props('clearable')).toBe(false)
    expect(wrapper.findAll('select')).toHaveLength(1)
    select.vm.$emit('update:modelValue', 1)
    expect(data.manager).toBe(1)
    wrapper.unmount()
  })
  it('选填的可搜索单选可清空；dense 行字段宽度写入 CSS 变量', () => {
    const data = reactive<Record<string, unknown>>({ rows: [{ a: '', b: '' }] })
    const wrapper = mount(FormFields, { props: { modelValue: data, fields: [{ key: 'rows', label: '明细', type: 'rows', dense: true, fields: [
      { key: 'a', label: '甲', type: 'select', searchable: true, optional: true, options: [], width: 220 },
      { key: 'b', label: '乙', width: '30%' },
    ] }] }, global: { stubs: { ElButton: { template: '<button type="button"><slot /></button>' } } } })
    expect(wrapper.findComponent(ElSelect).props('clearable')).toBe(true)
    const fields = wrapper.findAll('.field-sized')
    expect(fields.map(f => f.attributes('style'))).toEqual(['--field-width: 220px;', '--field-width: 30%;'])
    wrapper.unmount()
  })
  it('只读详情含明细表时占满工作区，普通只读详情仍用侧栏', () => {
    const base = { title: '查看明细', path: '', readonly: true, initial: {} }
    expect(wideCommand({ ...base, fields: [{ key: 'a', label: 'A' }, { key: 'lines', label: '明细', type: 'rows' }] })).toBe(true)
    expect(wideCommand({ ...base, fields: [{ key: 'a', label: 'A' }] })).toBe(false)
  })
})
