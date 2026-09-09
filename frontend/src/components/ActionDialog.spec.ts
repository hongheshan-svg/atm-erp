import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { ElMessage } from 'element-plus'
import ActionDialog from './ActionDialog.vue'
import { installElementPlus } from '../plugins/elementPlus'
import { write } from '../api'

vi.mock('../api', () => ({ write: vi.fn() }))

function open() {
  return mount(ActionDialog, {
    props: {
      command: {
        title: '登记收款',
        path: '/business/entries/1/pay/',
        fields: [{ key: 'amount', label: '金额' }],
        initial: { amount: '10.00' },
      },
    },
    global: {
      plugins: [{ install: installElementPlus }],
      stubs: { ElDialog: { template: '<div><slot /></div>' } },
    },
  })
}

afterEach(() => {
  vi.resetAllMocks()
  ElMessage.closeAll()
})

describe('业务表单失败与重试', () => {
  it('网络失败保留输入，相同数据重试沿用操作标识，修改数据后换标识', async () => {
    vi.mocked(write).mockRejectedValue(new Error('网络中断'))
    const wrapper = open()
    const fields = wrapper.get('.action-fields').element as HTMLElement
    fields.scrollTop = 120
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.text()).toContain('网络中断')
    expect(fields.scrollTop).toBe(0)
    expect(wrapper.emitted('close')).toBeUndefined()
    expect((wrapper.get('input').element as HTMLInputElement).value).toBe('10.00')
    const firstKey = vi.mocked(write).mock.calls[0]![2]
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(vi.mocked(write).mock.calls[1]![2]).toBe(firstKey)
    await wrapper.get('input').setValue('11.00')
    vi.mocked(write).mockResolvedValue({ id: 9 })
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(vi.mocked(write).mock.calls[2]![1]).toEqual({ amount: '11.00' })
    expect(vi.mocked(write).mock.calls[2]![2]).not.toBe(firstKey)
    expect(wrapper.emitted('saved')).toEqual([[{ id: 9 }]])
    expect(wrapper.emitted('close')).toHaveLength(1)
    wrapper.unmount()
  })

  it('请求未结束时连续提交只发送一次', async () => {
    let resolve!: (value: { id: number }) => void
    vi.mocked(write).mockImplementation(() => new Promise((done) => { resolve = done }))
    const wrapper = open()
    await wrapper.get('form').trigger('submit')
    await wrapper.get('form').trigger('submit')
    expect(write).toHaveBeenCalledTimes(1)
    resolve({ id: 10 })
    await flushPromises()
    expect(wrapper.emitted('saved')).toEqual([[{ id: 10 }]])
    wrapper.unmount()
  })
})
