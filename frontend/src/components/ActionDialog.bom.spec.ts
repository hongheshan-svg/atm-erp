import { afterEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { ElMessage } from 'element-plus'
import ActionDialog from './ActionDialog.vue'
import { installElementPlus } from '../plugins/elementPlus'
import { write } from '../api'
import { user } from '../session'
import type { Command } from '../types'

vi.mock('../api', () => ({ write: vi.fn() }))
afterEach(() => { vi.resetAllMocks(); sessionStorage.clear(); user.value = null; ElMessage.closeAll() })

const bomCommand: Command = {
  title: '维护 BOM',
  path: '/business/projects/81/revise-bom/',
  previewPath: '/business/projects/81/bom-change-preview/',
  fields: [{ key: 'quantity', label: '数量' }, { key: 'change_note', label: '变更说明', optional: true }],
  initial: { quantity: '3', change_note: '' },
}
function open(command: Command = bomCommand) {
  return mount(ActionDialog, {
    props: { command },
    global: { plugins: [{ install: installElementPlus }], stubs: { ElDialog: { template: '<div><slot /></div>' }, RouterLink: { props: ['to'], template: '<a class="router-link"><slot /></a>' } } },
  })
}
const button = (wrapper: ReturnType<typeof open>, text: string) => wrapper.findAll('button').find(item => item.text().includes(text))!

it('BOM 预览先列本次提交的行并标出新增，警告新增到其他单元，保存按钮写明新增行数', async () => {
  user.value = { roles: ['mechanical_engineer'] }
  vi.mocked(write).mockResolvedValueOnce({
    can_apply: true, blockers: [], project: 81, unchanged_items: 103,
    changes: [{ item: 7, item_code: 'PKS13842', item_name: '直线导轨', assembly_unit: '', action: 'create', before: null, after: '3.000', before_unit: null }],
    warnings: ['PKS13842 直线导轨 已在 5 个单元有用料，本行将新增到「未分单元」，总需求 14.000 → 17.000。'],
    items: [{ item: 7, item_name: '直线导轨', quantity: '14.000', after: '17.000', difference: '3.000', unresolved_quantity: '0', received_in_stock: '0' }],
    purchases: [{ id: 49, code: 'PO000048', status: 'partial' }],
  })
  const wrapper = open()
  await button(wrapper, '预览变更影响').trigger('click')
  await flushPromises()
  const preview = wrapper.get('[aria-label="变更影响预览"]')
  expect(preview.text()).toContain('本次提交 1 行')
  expect(preview.text()).toContain('新增')
  expect(preview.text()).toContain('0 → 3')
  expect(preview.text()).toContain('已在 5 个单元有用料')
  expect(preview.text()).toContain('其余 103 种物料数量不变')
  // 工程师看不到采购页签：给单号、状态和该找谁，不给点了无效的链接。
  expect(preview.find('.router-link').exists()).toBe(false)
  expect(preview.text()).toContain('相关采购单 PO000048（部分收货），本次变更不需要处理')
  expect(wrapper.find('button[type="submit"]').text()).toBe('确认新增 1 行')
  await wrapper.get('input[aria-label="数量"]').setValue('4')
  expect(wrapper.text()).toContain('预览后又改过填写内容')
  expect(wrapper.find('button[type="submit"]').text()).toBe('保存 BOM')
  wrapper.unmount()
})

it('只改日期时说明没有数量变化；采购读者看到可点的采购单链接', async () => {
  user.value = { roles: ['purchaser'] }
  vi.mocked(write).mockResolvedValueOnce({
    can_apply: true, blockers: [], project: 81, unchanged_items: 3, items: [], warnings: [],
    changes: [{ item: 7, item_code: 'A1', item_name: '支架', assembly_unit: '01 上料', before_unit: '01 上料', action: 'update', before: '2.000', after: '2.000' }],
    purchases: [{ id: 49, code: 'PO000048', status: 'approved' }],
  })
  const wrapper = open()
  await button(wrapper, '预览变更影响').trigger('click')
  await flushPromises()
  expect(wrapper.text()).toContain('本次没有数量变化')
  expect(wrapper.get('.router-link').text()).toBe('PO000048（待收货）· 查看采购')
  expect(wrapper.find('button[type="submit"]').text()).toBe('保存 BOM')
  wrapper.unmount()
})

it('BOM 修订被拦截时不显示指不到原单的「打开原单据」；其他单据仍可跳转', async () => {
  const conflict = { isAxiosError: true, response: { status: 409, data: { detail: '该行关联在途采购 4（PO000048 部分收货）', actions: [{ label: '打开原单据核对并处理', path: '/projects/81' }] } } }
  vi.mocked(write).mockRejectedValue(conflict)
  let wrapper = open()
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(wrapper.text()).toContain('PO000048')
  expect(wrapper.text()).not.toContain('打开原单据核对并处理')
  wrapper.unmount()
  wrapper = open({ title: '批准采购', path: '/business/purchases/5/approve/', fields: [] })
  vi.mocked(write).mockRejectedValue({ ...conflict, response: { ...conflict.response, data: { ...conflict.response.data, actions: [{ label: '打开原单据核对并处理', path: '/purchases?resource=purchases&focus=5' }] } } })
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(wrapper.get('.recovery-action').text()).toContain('打开原单据核对并处理 →')
  wrapper.unmount()
})

it('减量需要处理已领或在途时，工程师被告知先找采购员', async () => {
  user.value = { roles: ['mechanical_engineer'] }
  vi.mocked(write).mockResolvedValueOnce({
    can_apply: false, blockers: ['PKS13842 不能低于 4.000'], project: 81, unchanged_items: 0, warnings: [],
    changes: [{ item: 7, item_code: 'PKS13842', item_name: '直线导轨', assembly_unit: '01', before_unit: '01', action: 'update', before: '4.000', after: '1.000' }],
    items: [{ item: 7, item_name: '直线导轨', quantity: '4.000', after: '1.000', difference: '-3.000', unresolved_quantity: '3.000', received_in_stock: '0' }],
    purchases: [{ id: 49, code: 'PO000048', status: 'partial' }],
  })
  const wrapper = open()
  await button(wrapper, '预览变更影响').trigger('click')
  await flushPromises()
  expect(wrapper.text()).toContain('涉及采购单 PO000048（部分收货），请联系采购员处理未收余量后再提交')
  wrapper.unmount()
})
