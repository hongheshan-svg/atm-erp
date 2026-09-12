import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, shallowMount } from '@vue/test-utils'
import { ref } from 'vue'
import ElementPlus from 'element-plus'
import ResourcePanel from './ResourcePanel.vue'
import ActionDialog from './ActionDialog.vue'
import SupplierMonthly from './SupplierMonthly.vue'
import FormFields from './FormFields.vue'
import RemoteSelect from './RemoteSelect.vue'
import SalesPage from '../views/SalesPage.vue'
import ProjectPage from '../views/ProjectPage.vue'
import { actionCommand as purchaseAction, createCommand } from '../modules/purchases'
import { actionCommand } from '../business'
import { defaults, payload } from '../forms'
import { read } from '../api'
import { user } from '../session'
vi.mock('vue-router', () => ({ useRoute: () => ({ query: {}, params: { id: '1' } }), useRouter: () => ({ replace: vi.fn(), push: vi.fn() }) }))
vi.mock('../api', () => ({ read: vi.fn(), all: vi.fn().mockResolvedValue([{ id: 1, name: '甲', kind: 'supplier' }, { id: 2, name: '乙', kind: 'supplier' }]), write: vi.fn(), download: vi.fn() }))
vi.mock('../business', () => ({ columns: {}, endpoint: (r: string) => `/business/${r}/`, display: String, createLabel: () => '', createCommand: vi.fn(), actionNames: () => [], actionCommand: vi.fn() }))
beforeEach(() => { vi.clearAllMocks(); user.value = { role: 'admin' }; vi.mocked(read).mockResolvedValue({ count: 0, results: [] }) })
const global = { plugins: [ElementPlus], stubs: { RouterLink: true, ElTable: { template: '<div />' } } }

describe('审查问题回归', () => {
  it('生产经理兼采购时任务创建仍取当前项目生产授权', async () => {
    user.value = { id: 8, roles: ['production_manager', 'purchaser'] }
    const project = { id: 1, name: '采购可读项目', status: 'active', can_manage_production: false }
    vi.mocked(read).mockResolvedValueOnce(project)
    const wrapper = shallowMount(ProjectPage, { global: { ...global, renderStubDefaultSlot: true, stubs: { ...global.stubs, ModuleTabs: { template: '<div><slot name="tasks" /></div>' } } } })
    await flushPromises()
    expect(wrapper.findComponent(ResourcePanel).props('allowCreate')).toBe(false)
    vi.mocked(read).mockResolvedValueOnce({ ...project, can_manage_production: true })
    await wrapper.findAllComponents({ name: 'ElButton' }).find(button => button.text() === '刷新')!.trigger('click')
    await flushPromises()
    expect(wrapper.findComponent(ResourcePanel).props('allowCreate')).toBe(true)
    wrapper.unmount()
  })
  it('项目刷新失败后重试成功清除旧错误并显示最新数据', async () => {
    vi.mocked(read).mockResolvedValueOnce({ id: 1, name: '原项目名称', status: 'active' })
    const wrapper = shallowMount(ProjectPage, { global: { ...global, renderStubDefaultSlot: true, stubs: { ...global.stubs, ElAlert: { props: ['title'], template: '<p role="alert">{{ title }}</p>' } } } })
    await flushPromises()
    const refresh = () => wrapper.findAllComponents({ name: 'ElButton' }).find(button => button.text() === '刷新')!
    vi.mocked(read).mockRejectedValueOnce(new Error('临时连接失败'))
    await refresh().trigger('click')
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('临时连接失败')
    vi.mocked(read).mockResolvedValueOnce({ id: 1, name: '恢复后的项目', status: 'active' })
    await refresh().trigger('click')
    await flushPromises()
    expect(wrapper.get('h1').text()).toBe('恢复后的项目')
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    wrapper.unmount()
  })
  it('销售保存通过页面刷新负责人更新列表一次', async () => {
    const wrapper = mount(SalesPage, { global: { ...global, stubs: { ...global.stubs, ActionDialog: true, TransferTools: true, ListPagination: true } } })
    await flushPromises()
    expect(read).toHaveBeenCalledTimes(1)
    wrapper.findComponent(ActionDialog).vm.$emit('saved', {})
    await flushPromises()
    expect(read).toHaveBeenCalledTimes(2)
    wrapper.unmount()
  })
  it('父级统一刷新一次，隐藏标签只在重新激活后加载', async () => {
    const active = ref(true)
    const wrapper = shallowMount(ResourcePanel, { props: { resource: 'entries', title: '款项', revision: 0 }, global: { ...global, provide: { panelActive: active } } })
    await flushPromises()
    expect(read).toHaveBeenCalledTimes(1)
    await wrapper.setProps({ params: {} })
    await flushPromises()
    expect(read).toHaveBeenCalledTimes(1)
    wrapper.findComponent(ActionDialog).vm.$emit('saved', {})
    await flushPromises()
    expect(read).toHaveBeenCalledTimes(1)
    await wrapper.setProps({ revision: 1 })
    await flushPromises()
    expect(read).toHaveBeenCalledTimes(2)
    active.value = false
    await wrapper.setProps({ revision: 2 })
    await flushPromises()
    expect(read).toHaveBeenCalledTimes(2)
    active.value = true
    await flushPromises()
    expect(read).toHaveBeenCalledTimes(3)
    wrapper.unmount()
  })

  it('旧操作晚返回不会替换最新弹窗', async () => {
    const resolvers: ((r: any) => void)[] = []
    vi.mocked(actionCommand).mockImplementation(() => new Promise(resolve => resolvers.push(resolve)))
    const wrapper = shallowMount(ResourcePanel, { props: { resource: 'purchases', title: '采购' }, global })
    void (wrapper.vm as any).action({ id: 1, code: 'PO-A' }, '收货')
    void (wrapper.vm as any).action({ id: 2, code: 'PO-B' }, '收货')
    resolvers[1]!({ title: '收货', path: '/B', fields: [] })
    await flushPromises()
    resolvers[0]!({ title: '收货', path: '/A', fields: [] })
    await flushPromises()
    expect(wrapper.findComponent(ActionDialog).props('command')?.path).toBe('/B')
    expect(wrapper.findComponent(ActionDialog).props('command')?.subject).toBe('PO-B')
    wrapper.unmount()
  })

  it('月度选择变更清除旧报告及确认入口', async () => {
    vi.mocked(read).mockResolvedValue({ supplier: 1, month: '2026-09', through: '2026-09-10', rows: [{ entry: 1 }], totals: { opening: '0', received: '10', returned: '0', paid: '0', closing: '10' } })
    const wrapper = shallowMount(SupplierMonthly, { global })
    await flushPromises()
    await wrapper.get('select').setValue('1')
    await wrapper.get('input[type=month]').setValue('2026-09')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.text()).toContain('当前报告：甲')
    await wrapper.get('select').setValue('2')
    expect(wrapper.text()).not.toContain('当前报告')
    expect(wrapper.findComponent(ActionDialog).props('command')).toBeNull()
    wrapper.unmount()
  })

  it('1000行收货只渲染20行，无重复物料选项且翻页保留输入', async () => {
    vi.mocked(read).mockResolvedValue({ lines: Array.from({ length: 1000 }, (_, i) => ({ id: i + 1, item_name: `物料${i}`, quantity: '1', received_quantity: '0', cancelled_quantity: '0', pending_quantity: '0' })) })
    const command = await purchaseAction('purchases', { id: 1 }, '收货')
    const model = defaults(command.fields, command.initial)
    const wrapper = mount(FormFields, { props: { fields: command.fields, modelValue: model }, global })
    expect(wrapper.findAll('.line-fields')).toHaveLength(20)
    expect(wrapper.findAll('option')).toHaveLength(0)
    await wrapper.findAll('.line-fields')[0]!.get('input[aria-label="数量"]').setValue('0.5')
    const next = wrapper.findAll('button').find(b => b.text() === '下一页明细')!
    await next.trigger('click')
    expect(wrapper.findAll('.line-fields')).toHaveLength(20)
    expect(payload(command.fields, model).lines[0].quantity).toBe('0.5')
    expect(payload(command.fields, model).lines[0]).not.toHaveProperty('item_label')
    wrapper.unmount()
  })

  it('新建采购不预先下载目录，远程选项按20条分页', async () => {
    const command = await createCommand('purchases')
    expect(read).not.toHaveBeenCalled()
    expect(command.fields.find(f => f.key === 'supplier')?.remotePath).toBe('/business/partners/')
    const wrapper = mount(RemoteSelect, { props: { path: '/business/items/', label: '物料' } })
    await flushPromises()
    expect(read).toHaveBeenCalledExactlyOnceWith('/business/items/', { search: '', page: 1, page_size: 20 })
    wrapper.unmount()
  })
})
