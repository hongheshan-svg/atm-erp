import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import InitialPasswordInput from './InitialPasswordInput.vue'
import FormFields from './FormFields.vue'
import { userFields } from '../modules/settings'
import { payload } from '../forms'

describe('管理员初始密码', () => {
  it('随机生成后可查看、隐藏并改为简短自定义密码', async () => {
    const wrapper = mount(InitialPasswordInput, { props: { label: '密码', modelValue: '', required: true,
      'onUpdate:modelValue': value => wrapper.setProps({ modelValue: value }),
    } })
    expect(wrapper.get('input').attributes('type')).toBe('password')
    await wrapper.get('button').trigger('click')
    const first = (wrapper.get('input').element as HTMLInputElement).value
    expect(first).toMatch(/^[A-Za-z0-9_-]{20}$/)
    expect(wrapper.get('input').attributes('type')).toBe('text')
    expect(wrapper.get('input').attributes('minlength')).toBeUndefined()
    await wrapper.get('button').trigger('click')
    expect((wrapper.get('input').element as HTMLInputElement).value).not.toBe(first)
    await wrapper.findAll('button')[1]!.trigger('click')
    expect(wrapper.get('input').attributes('type')).toBe('password')
    await wrapper.get('input').setValue('1')
    expect(wrapper.props('modelValue')).toBe('1')
    expect(wrapper.findAll('button').every(button => button.attributes('type') === 'button')).toBe(true)
    wrapper.unmount()
  })

  it('用户表单提交随机或手动密码，编辑留空不重置密码', async () => {
    const field = userFields.find(field => field.key === 'password')!
    const data = { password: '' }
    const wrapper = mount(FormFields, { props: { fields: [field], modelValue: data } })
    await wrapper.get('button').trigger('click')
    expect(payload([field], data).password).toMatch(/^[A-Za-z0-9_-]{20}$/)
    await wrapper.get('input').setValue('123456')
    expect(payload([field], data).password).toBe('123456')
    await wrapper.get('input').setValue('')
    expect(payload([{ ...field, optional: true }], data)).toEqual({})
    await wrapper.setProps({ disabled: true })
    expect(wrapper.get('input').attributes()).toHaveProperty('disabled')
    expect(wrapper.findAll('button').every(button => button.attributes('disabled') !== undefined)).toBe(true)
    wrapper.unmount()
  })
})
