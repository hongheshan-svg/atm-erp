import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { nextTick, ref } from 'vue'
import RemoteSelect from './RemoteSelect.vue'
import QuickReferenceCreate from './QuickReferenceCreate.vue'
import { read } from '../api'
import { user } from '../session'
import { rememberReference } from '../catalog'
import type { Row } from '../types'

vi.mock('../api', () => ({ read: vi.fn(), write: vi.fn(), all: vi.fn() }))
const wrappers: VueWrapper[] = []
const path = '/business/items/'
const item = (id: number, name = `物料${id}`): Row => ({ id, name, code: `M00${id}`, is_active: true })
function deferred() {
  let resolve!: (value: unknown) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}
function open(props: Record<string, unknown> = {}) {
  const wrapper = mount(RemoteSelect, { props: { path, label: '物料', ...props }, attachTo: document.body })
  wrappers.push(wrapper)
  return wrapper
}
const control = (wrapper: VueWrapper) => wrapper.get<HTMLInputElement>('input[role="combobox"]')
async function search(wrapper: VueWrapper, text: string) {
  await control(wrapper).setValue(text)
  await vi.advanceTimersByTimeAsync(250)
  await flushPromises()
}
beforeEach(() => {
  vi.useFakeTimers()
  user.value = { id: 1, roles: ['member'] }
  vi.mocked(read).mockResolvedValue({ results: [], next: null })
})
afterEach(() => {
  wrappers.splice(0).forEach(wrapper => wrapper.unmount())
  user.value = null
  vi.resetAllMocks()
  vi.useRealTimers()
})

describe('单一远程搜索组合框', () => {
  it('只保留一个组合框，转发字段错误属性，重名通过编号和键盘选择稳定ID', async () => {
    vi.mocked(read).mockResolvedValue({ results: [item(1, '同名电机'), item(2, '同名电机')], next: null })
    const wrapper = open({ inputId: 'line-item', invalid: true, describedBy: 'line-error' })
    await flushPromises()
    expect(wrapper.findAll('input')).toHaveLength(1)
    expect(wrapper.find('select').exists()).toBe(false)
    expect(control(wrapper).attributes('id')).toBe('line-item')
    expect(control(wrapper).attributes('aria-invalid')).toBe('true')
    expect(control(wrapper).attributes('aria-describedby')).toContain('line-error')
    await control(wrapper).trigger('focus')
    await flushPromises()
    await control(wrapper).trigger('keydown', { key: 'ArrowDown' })
    await control(wrapper).trigger('keydown', { key: 'ArrowDown' })
    const active = control(wrapper).attributes('aria-activedescendant')
    expect(wrapper.findAll('[role="option"]')[1]!.attributes('id')).toBe(active)
    expect(wrapper.findAll('[role="option"]')[1]!.text()).toContain('M002')
    await control(wrapper).trigger('keydown', { key: 'Enter' })
    expect(wrapper.emitted('update:modelValue')).toEqual([[2]])
    expect(control(wrapper).element.value).toBe('同名电机 · M002')
    expect(control(wrapper).attributes('aria-expanded')).toBe('false')
  })

  it('键入即搜索；防抖等待期间的旧响应和后返回的旧查询都不能覆盖新结果', async () => {
    const old = deferred(), current = deferred(), stale = deferred()
    vi.mocked(read).mockImplementation((_path, params) => params?.search === '旧' ? old.promise : params?.search === '新' ? current.promise : params?.search === '最后' ? stale.promise : Promise.resolve({ results: [] }))
    const wrapper = open()
    await flushPromises()
    await search(wrapper, '旧')
    await control(wrapper).setValue('新')
    old.resolve({ results: [item(1, '过时资料')] })
    await flushPromises()
    expect(wrapper.text()).not.toContain('过时资料')
    expect(wrapper.text()).toContain('正在搜索')
    await vi.advanceTimersByTimeAsync(250)
    await search(wrapper, '最后')
    stale.resolve({ results: [item(3, '最新资料')] })
    await flushPromises()
    current.resolve({ results: [item(2, '中间资料')] })
    await flushPromises()
    expect(wrapper.text()).toContain('最新资料')
    expect(wrapper.text()).not.toContain('中间资料')
    expect(read).toHaveBeenCalledWith(path, { search: '最后', page: 1, page_size: 20 })
  })

  it('嵌在标签内点击候选会阻止标签再次点击输入框，选定后保持收起', async () => {
    vi.mocked(read).mockResolvedValue({ results: [item(1)], next: null })
    const wrapper = mount({
      components: { RemoteSelect },
      template: '<label>物料<RemoteSelect path="/business/items/" label="物料" /></label>',
    }, { attachTo: document.body })
    wrappers.push(wrapper)
    await flushPromises()
    control(wrapper).element.focus()
    await flushPromises()
    const click = new MouseEvent('click', { bubbles: true, cancelable: true })
    wrapper.get('[role="option"] .remote-name').element.dispatchEvent(click)
    await flushPromises()
    expect(click.defaultPrevented).toBe(true)
    expect(control(wrapper).element.value).toBe('物料1 · M001')
    expect(control(wrapper).attributes('aria-expanded')).toBe('false')
    expect(document.activeElement).toBe(control(wrapper).element)
    expect(wrapper.getComponent(RemoteSelect).emitted('update:modelValue')).toEqual([[1]])
  })

  it.each([false, true])('父表单异步确认返回 %s 时，显示始终与父级实际接受的项目一致', async accept => {
    const confirmation = deferred()
    const project = ref(1)
    vi.mocked(read).mockImplementation(url => Promise.resolve(url === `${path}1/` ? item(1) : { results: [item(1), item(2)], next: null }))
    const wrapper = mount({
      components: { RemoteSelect },
      setup() {
        async function choose(value: number) { if (await confirmation.promise) project.value = value }
        return { project, choose }
      },
      template: '<RemoteSelect :model-value="project" @update:model-value="choose" path="/business/items/" label="项目" commit-on-select />',
    }, { attachTo: document.body })
    wrappers.push(wrapper)
    await flushPromises()
    await control(wrapper).trigger('focus')
    await flushPromises()
    await wrapper.get('[role="option"][data-value="2"]').trigger('click')
    await flushPromises()
    expect(project.value).toBe(1)
    expect(control(wrapper).element.value).toBe('物料1 · M001')
    expect(control(wrapper).attributes('aria-expanded')).toBe('false')
    confirmation.resolve(accept)
    await flushPromises()
    expect(project.value).toBe(accept ? 2 : 1)
    expect(control(wrapper).element.value).toBe(accept ? '物料2 · M002' : '物料1 · M001')
    expect(control(wrapper).element.validity.customError).toBe(false)
  })

  it('筛选模式搜索不修改父值或抢走焦点，取消搜索恢复旧项目，键盘确认仅发出候选ID', async () => {
    const choose = vi.fn()
    vi.mocked(read).mockImplementation((url, params) => Promise.resolve(url === `${path}1/` ? item(1)
      : { results: params?.search ? [item(2)] : [item(1), item(2)], next: null }))
    const wrapper = open({ modelValue: 1, 'onUpdate:modelValue': choose, commitOnSelect: true })
    await flushPromises()
    control(wrapper).element.focus()
    await search(wrapper, '物料2')
    expect(choose).not.toHaveBeenCalled()
    expect(control(wrapper).element.value).toBe('物料2')
    expect(control(wrapper).attributes('aria-expanded')).toBe('true')
    expect(document.activeElement).toBe(control(wrapper).element)
    expect(wrapper.findAll('[role="option"]')).toHaveLength(1)
    await control(wrapper).trigger('keydown', { key: 'Escape' })
    expect(control(wrapper).element.value).toBe('物料1 · M001')
    expect(choose).not.toHaveBeenCalled()
    await search(wrapper, '物料2')
    await control(wrapper).trigger('keydown', { key: 'ArrowDown' })
    await control(wrapper).trigger('keydown', { key: 'Enter' })
    await flushPromises()
    expect(choose.mock.calls).toEqual([[2]])
    expect(control(wrapper).element.value).toBe('物料1 · M001')
    await wrapper.setProps({ modelValue: 2 })
    await flushPromises()
    expect(control(wrapper).element.value).toBe('物料2 · M002')
  })

  it('筛选模式仅点击清空才请求取消选择，父级拒绝清空时恢复原值', async () => {
    const choose = vi.fn()
    vi.mocked(read).mockImplementation(url => Promise.resolve(url === `${path}1/` ? item(1) : { results: [item(1)], next: null }))
    const wrapper = open({ modelValue: 1, 'onUpdate:modelValue': choose, commitOnSelect: true })
    await flushPromises()
    await search(wrapper, '')
    expect(choose).not.toHaveBeenCalled()
    await wrapper.get('[aria-label="清空物料"]').trigger('click')
    await flushPromises()
    expect(choose.mock.calls).toEqual([['']])
    expect(control(wrapper).element.value).toBe('物料1 · M001')
    expect(control(wrapper).attributes('aria-expanded')).toBe('false')
    await wrapper.setProps({ modelValue: undefined })
    await flushPromises()
    expect(control(wrapper).element.value).toBe('')
  })

  it('继续分页累加去重并保留已选项；输入新查询立即清除旧选择', async () => {
    vi.mocked(read).mockImplementation((_path, params) => Promise.resolve(params?.search
      ? { results: [item(4)], next: null }
      : params?.page === 2 ? { results: [item(2), item(3)], next: null } : { results: [item(1), item(2)], next: '/page2' }))
    const wrapper = open()
    await flushPromises()
    await control(wrapper).trigger('focus')
    await flushPromises()
    await wrapper.findAll('[role="option"]')[0]!.trigger('click')
    await control(wrapper).trigger('click')
    await flushPromises()
    await wrapper.findAll('button').find(button => button.text() === '继续加载更多')!.trigger('click')
    await flushPromises()
    expect(wrapper.findAll('[role="option"]')).toHaveLength(3)
    expect(wrapper.find('[aria-selected="true"]').text()).toContain('物料1')
    await search(wrapper, '物料4')
    expect(wrapper.findAll('[role="option"]')).toHaveLength(1)
    expect(wrapper.find('[aria-selected="true"]').exists()).toBe(false)
    await control(wrapper).trigger('keydown', { key: 'Escape' })
    expect(control(wrapper).element.value).toBe('物料4')
    expect(wrapper.emitted('update:modelValue')).toEqual([[1], ['']])
    expect(control(wrapper).element.validity.customError).toBe(true)
  })

  it('加载、失败与空结果分别显示；失败可以重试', async () => {
    const pending = deferred()
    vi.mocked(read).mockReturnValue(pending.promise)
    const wrapper = open()
    await control(wrapper).trigger('focus')
    expect(wrapper.text()).toContain('正在搜索')
    expect(wrapper.text()).not.toContain('无匹配结果')
    pending.reject(new Error('没有读取权限，请联系管理员'))
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('没有读取权限')
    expect(wrapper.text()).not.toContain('无匹配结果')
    vi.mocked(read).mockResolvedValue({ results: [], next: null })
    await wrapper.findAll('button').find(button => button.text() === '重新加载')!.trigger('click')
    await flushPromises()
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('无匹配结果')
    expect(wrapper.text()).toContain('请联系工程师、采购或项目经理维护')
  })

  it('最近使用重新匹配当前授权结果，换用户清除选中和在途响应', async () => {
    rememberReference(path, 2)
    rememberReference(path, 3)
    vi.mocked(read).mockResolvedValue({ results: [item(1), item(2, '更新后的名称')], next: null })
    const wrapper = open()
    await flushPromises()
    expect(wrapper.findAll('[role="option"]')[0]!.text()).toContain('更新后的名称')
    expect(wrapper.findAll('[role="option"]')[0]!.text()).toContain('最近使用')
    expect(wrapper.text()).not.toContain('物料3')
    await wrapper.findAll('[role="option"]')[0]!.trigger('click')
    const old = deferred()
    vi.mocked(read).mockReturnValueOnce(old.promise)
    await search(wrapper, '旧会话')
    vi.mocked(read).mockResolvedValue({ results: [item(4, '新用户可见')] })
    user.value = { id: 99, roles: ['member'] }
    await nextTick()
    await flushPromises()
    old.resolve({ results: [item(5, '旧用户机密')] })
    await flushPromises()
    expect(control(wrapper).element.value).toBe('')
    expect(wrapper.text()).toContain('新用户可见')
    expect(wrapper.text()).not.toMatch(/更新后的名称|旧用户机密|最近使用/)
    expect(wrapper.emitted('update:modelValue')?.at(-1)).toEqual([''])
  })

  it('已选详情请求竞态不覆盖新值，筛选变化重新校验停用记录', async () => {
    const old = deferred()
    vi.mocked(read).mockImplementation((url) => url === `${path}1/` ? old.promise : Promise.resolve(url === `${path}2/` ? item(2) : { results: [] }))
    const wrapper = open({ modelValue: 1, params: { is_active: true } })
    await wrapper.setProps({ modelValue: 2 })
    await flushPromises()
    old.resolve(item(1))
    await flushPromises()
    expect(control(wrapper).element.value).toBe('物料2 · M002')
    vi.mocked(read).mockImplementation(url => Promise.resolve(url === `${path}2/` ? { ...item(2), is_active: false } : { results: [] }))
    await wrapper.setProps({ params: { is_active: true, brand: '新范围' } })
    await flushPromises()
    expect(control(wrapper).element.value).toBe('')
    expect(wrapper.text()).toContain('原选项已不在可选范围')
    expect(control(wrapper).element.checkValidity()).toBe(false)
  })

  it('输入自由文字不能冒充已选ID；IME回车不选择，清空按钮移除已选项', async () => {
    const wrapper = open({ required: true })
    await search(wrapper, '任意文字')
    expect(control(wrapper).element.checkValidity()).toBe(false)
    expect(wrapper.emitted('update:modelValue')).toEqual([['']])
    vi.mocked(read).mockResolvedValue({ results: [item(1)] })
    await search(wrapper, '物料1')
    await control(wrapper).trigger('keydown', { key: 'ArrowDown' })
    await control(wrapper).trigger('keydown', { key: 'Enter', isComposing: true })
    expect(wrapper.emitted('update:modelValue')).toEqual([['']])
    await control(wrapper).trigger('keydown', { key: 'Enter' })
    expect(control(wrapper).element.checkValidity()).toBe(true)
    await wrapper.get('[aria-label="清空物料"]').trigger('click')
    expect(wrapper.emitted('update:modelValue')?.at(-1)).toEqual([''])
    expect(control(wrapper).element.checkValidity()).toBe(false)
  })

  it('选A后输入B立即清空ID，未选候选时保持搜索词与可定位的自定义错误', async () => {
    vi.mocked(read).mockResolvedValue({ results: [item(1, '客户A')] })
    const wrapper = open()
    await flushPromises()
    await wrapper.get('[role="option"]').trigger('click')
    await control(wrapper).setValue('客户B')
    expect(wrapper.emitted('update:modelValue')).toEqual([[1], ['']])
    expect(control(wrapper).element.value).toBe('客户B')
    expect(control(wrapper).element.validity.customError).toBe(true)
    await control(wrapper).trigger('keydown', { key: 'Tab' })
    await control(wrapper).trigger('focus')
    expect(control(wrapper).element.value).toBe('客户B')
    expect(wrapper.emitted('update:modelValue')?.at(-1)).toEqual([''])
  })

  it('创建返回核对期间禁用输入，外部选择变化使旧返回失效且恢复输入', async () => {
    const pending = deferred()
    vi.mocked(read).mockImplementation(url => url === `${path}19/` ? pending.promise : Promise.resolve(url === `${path}2/` ? item(2) : { results: [] }))
    const wrapper = open({ modelValue: undefined })
    await flushPromises()
    wrapper.findComponent(QuickReferenceCreate).vm.$emit('selected', item(19))
    await nextTick()
    expect(control(wrapper).element.disabled).toBe(true)
    await wrapper.setProps({ modelValue: 2 })
    await flushPromises()
    expect(control(wrapper).element.disabled).toBe(false)
    pending.resolve(item(19, '旧创建返回'))
    await flushPromises()
    expect(control(wrapper).element.value).toBe('物料2 · M002')
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
  })
})
