import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { DOMWrapper, flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { defineComponent, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { installElementPlus } from '../plugins/elementPlus'
import { read, write } from '../api'
import { user } from '../session'
import RemoteSelect from './RemoteSelect.vue'
import QuickReferenceCreate from './QuickReferenceCreate.vue'
import ActionDialog from './ActionDialog.vue'
import type { Row } from '../types'

vi.mock('../api', () => ({ read: vi.fn(), write: vi.fn(), all: vi.fn() }))
const wrappers: VueWrapper[] = []
const global = { plugins: [{ install: installElementPlus }], stubs: { RouterLink: true } }
const byText = (wrapper: VueWrapper, text: string) => wrapper.findAll('button').find(button => button.text() === text)!
const dialog = () => new DOMWrapper(document.body.querySelector<HTMLElement>('.action-dialog')!)
function quick(props: Record<string, unknown> = {}) {
  const wrapper = mount(QuickReferenceCreate, { props: { path: '/business/partners/', label: '客户', ...props }, global, attachTo: document.body })
  wrappers.push(wrapper)
  return wrapper
}
beforeEach(() => {
  user.value = { id: 1, roles: ['sales_manager'] }
  vi.mocked(read).mockResolvedValue({ results: [], next: null })
})
afterEach(() => {
  wrappers.splice(0).forEach(wrapper => wrapper.unmount())
  user.value = null
  vi.resetAllMocks()
  ElMessage.closeAll()
  document.body.innerHTML = ''
})

describe('选择器就近建档', () => {
  it('按已有岗位权限提供入口，销售兼任普通成员仍不能建供应商，工程师可以建物料', async () => {
    user.value = { id: 1, roles: ['sales_manager', 'member'] }
    const supplier = quick({ label: '供应商' })
    expect(supplier.find('button').exists()).toBe(false)
    expect(supplier.text()).toContain('请联系采购或项目经理维护')
    const customer = quick()
    expect(customer.text()).toContain('新增客户')
    user.value = { id: 2, roles: ['mechanical_engineer'] }
    const material = quick({ path: '/business/items/', label: '物料' })
    expect(material.text()).toContain('新增物料')
    await flushPromises()
    expect(customer.find('button').exists()).toBe(false)
    user.value = { id: 3, roles: ['warehouse'] }
    await flushPromises()
    expect(material.find('button').exists()).toBe(false)
    expect(material.text()).toContain('请联系工程师、采购或项目经理维护')
    expect(write).not.toHaveBeenCalled()
  })

  it('先查授权相似资料，可直接复用；核对失败不能直接新建', async () => {
    const existing = { id: 7, name: '客户甲', code: 'C007', kind: 'customer' }
    vi.mocked(read).mockResolvedValue({ results: [existing] })
    const wrapper = quick({ query: '客户甲' })
    await byText(wrapper, '新增客户').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('已有相似资料')
    expect(document.querySelector('.action-dialog')).toBeNull()
    await wrapper.findAll('button').find(button => button.text().includes('使用此项'))!.trigger('click')
    expect(wrapper.emitted('selected')).toEqual([[existing]])
    expect(write).not.toHaveBeenCalled()
    vi.mocked(read).mockRejectedValue(new Error('网络中断'))
    await byText(wrapper, '新增客户').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('未能核对相似资料：网络中断')
    expect(document.querySelector('.action-dialog')).toBeNull()
  })

  it('复用原客户建档命令和API，保存后选回新ID且保留父表单，子表单不提交父表单', async () => {
    const saved = { id: 19, name: '新客户', code: 'C019', kind: 'customer', is_active: true }
    vi.mocked(write).mockResolvedValue(saved)
    vi.mocked(read).mockImplementation(url => Promise.resolve(url.endsWith('/19/') ? saved : { results: [], next: null }))
    const parentSubmit = vi.fn()
    const Parent = defineComponent({
      components: { RemoteSelect },
      setup: () => ({ customer: ref(''), note: ref('父表单未保存的需求'), parentSubmit }),
      template: '<form class="parent-form" @submit.prevent="parentSubmit"><input aria-label="父表单说明" v-model="note" /><RemoteSelect v-model="customer" path="/business/partners/" label="客户" :params="{ is_active: true }" :accept="row => row.kind !== \'supplier\'" /></form>',
    })
    const wrapper = mount(Parent, { global, attachTo: document.body })
    wrappers.push(wrapper)
    await flushPromises()
    await wrapper.get('input[role="combobox"]').trigger('focus')
    await flushPromises()
    await byText(wrapper, '新增客户').trigger('click')
    await flushPromises()
    await vi.waitFor(() => expect(document.querySelector('.action-dialog')).not.toBeNull())
    const form = dialog()
    expect(form.element.closest('.parent-form')).toBeNull()
    expect(form.find('option[value="supplier"]').exists()).toBe(false)
    await form.get('input[aria-label="单位名称"]').setValue('新客户')
    await form.get('form').trigger('submit')
    await flushPromises()
    expect(write).toHaveBeenCalledWith('/business/partners/', expect.objectContaining({ name: '新客户', kind: 'customer' }), expect.any(String), undefined)
    expect(read).toHaveBeenCalledWith('/business/partners/19/', { is_active: true })
    expect(wrapper.get<HTMLInputElement>('input[role="combobox"]').element.value).toBe('新客户 · C019')
    expect(wrapper.get<HTMLInputElement>('input[role="combobox"]').element.disabled).toBe(false)
    expect(wrapper.get<HTMLInputElement>('[aria-label="父表单说明"]').element.value).toBe('父表单未保存的需求')
    expect(parentSubmit).not.toHaveBeenCalled()
  })

  it('物料保存使用原API；服务端拒绝时保留建档输入，不发出选回事件', async () => {
    user.value = { id: 4, roles: ['mechanical_engineer'] }
    vi.mocked(read).mockResolvedValue([])
    vi.mocked(write).mockRejectedValue(new Error('相同物料已存在，请填写独立编码原因'))
    const wrapper = quick({ path: '/business/items/', label: '物料', query: '伺服电机' })
    await byText(wrapper, '新增物料').trigger('click')
    await flushPromises()
    await vi.waitFor(() => expect(document.querySelector('.action-dialog')).not.toBeNull())
    const form = dialog()
    expect(form.get<HTMLInputElement>('[aria-label="物料名称"]').element.value).toBe('伺服电机')
    await form.get('form').trigger('submit')
    await flushPromises()
    expect(write).toHaveBeenCalledWith('/business/items/', expect.objectContaining({ name: '伺服电机', unit: '件' }), expect.any(String), undefined)
    expect(form.text()).toContain('相同物料已存在')
    expect(wrapper.emitted('selected')).toBeUndefined()
    expect(form.get<HTMLInputElement>('[aria-label="物料名称"]').element.value).toBe('伺服电机')
  })

  it('创建返回仍重验当前选择范围，不能把供应商或失效资料选为客户', async () => {
    const saved = { id: 19, name: '仅供应商', kind: 'supplier', is_active: true }
    vi.mocked(read).mockImplementation(url => Promise.resolve(url.endsWith('/19/') ? saved : { results: [], next: null }))
    const wrapper = mount(RemoteSelect, { props: { path: '/business/partners/', label: '客户', accept: (row: Row) => row.kind !== 'supplier' }, global })
    wrappers.push(wrapper)
    await flushPromises()
    wrapper.findComponent(QuickReferenceCreate).vm.$emit('selected', saved)
    await flushPromises()
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
    expect(wrapper.text()).toContain('已保存的资料不符合当前选择范围')
  })

  it('切换账号使在途相似项请求失效，不带出原账号资料或建档表单', async () => {
    let resolve!: (value: unknown) => void
    vi.mocked(read).mockReturnValue(new Promise(done => { resolve = done }))
    const wrapper = quick({ query: '旧客户' })
    await byText(wrapper, '新增客户').trigger('click')
    user.value = { id: 8, roles: ['sales_manager'] }
    resolve({ results: [{ id: 8, name: '旧用户客户', code: 'OLD' }] })
    await flushPromises()
    expect(wrapper.text()).not.toContain('旧用户客户')
    expect(document.querySelector('.action-dialog')).toBeNull()
  })

  it('嵌套建档弹窗按 Escape 只关闭子弹窗，保留父弹窗及原填写内容', async () => {
    const wrapper = mount(ActionDialog, { props: { command: {
      title: '新建销售', path: '/business/sales/',
      fields: [{ key: 'name', label: '销售名称' }, { key: 'customer', label: '客户', remotePath: '/business/partners/' }],
      initial: { name: '未提交销售内容' },
    } }, global, attachTo: document.body })
    wrappers.push(wrapper)
    await flushPromises()
    const parent = dialog()
    await parent.get('input[role="combobox"]').trigger('focus')
    await flushPromises()
    await parent.findAll('button').find(button => button.text() === '新增客户')!.trigger('click')
    await vi.waitFor(() => expect(document.querySelectorAll('.action-dialog')).toHaveLength(2))
    const child = new DOMWrapper(document.querySelectorAll<HTMLElement>('.action-dialog')[1]!)
    await child.get('input[aria-label="单位名称"]').trigger('keydown', { key: 'Escape', code: 'Escape' })
    await vi.waitFor(() => expect(document.querySelectorAll('.action-dialog')).toHaveLength(1))
    expect(wrapper.emitted('close')).toBeUndefined()
    expect(parent.get<HTMLInputElement>('[aria-label="销售名称"]').element.value).toBe('未提交销售内容')
  })
})
