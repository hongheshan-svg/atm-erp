import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { ElMessage } from 'element-plus'
import ActionDialog from '../components/ActionDialog.vue'
import { installElementPlus } from '../plugins/elementPlus'
import { write } from '../api'
import { user } from '../session'
import type { Command } from '../types'
import { actionCommand, createCommand } from './masterdata'

vi.mock('../api', () => ({ write: vi.fn(), read: vi.fn(), all: vi.fn() }))

const term = '[aria-label="供应商默认采购账期"]'
const days = '[aria-label="自定义月结天数（0～365）"]'
function open(command: Command) {
  return mount(ActionDialog, {
    props: { command },
    global: {
      plugins: [{ install: installElementPlus }],
      stubs: { ElDialog: { template: '<div><slot /></div>' }, RouterLink: true },
    },
  })
}
beforeEach(() => {
  user.value = { id: 1, roles: ['admin'] }
  vi.mocked(write).mockResolvedValue({ id: 1 })
})
afterEach(() => {
  vi.resetAllMocks()
  user.value = null
  ElMessage.closeAll()
})

it('新增客户隐藏采购账期，切回客户后不校验或提交残留的供应商输入', async () => {
  const wrapper = open(await createCommand('partners'))
  expect(wrapper.find(term).exists()).toBe(false)
  await wrapper.get('[aria-label="单位名称"]').setValue('测试客户')
  await wrapper.get('[aria-label="类型"]').setValue('supplier')
  await wrapper.get(term).setValue('custom')
  await wrapper.get(days).setValue('错误天数')
  await wrapper.get('[aria-label="类型"]').setValue('customer')
  expect(wrapper.find(term).exists()).toBe(false)
  expect(wrapper.find(days).exists()).toBe(false)
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(write).toHaveBeenCalledWith('/business/partners/', {
    name: '测试客户', kind: 'customer', payment_term: 'manual', payment_days: 0,
  }, expect.any(String), undefined)
  expect(wrapper.emitted('saved')).toHaveLength(1)
  wrapper.unmount()
})

it.each(['supplier', 'both'])('%s 显示采购账期，切换类型保留未保存输入并正确提交', async kind => {
  const wrapper = open(await createCommand('partners'))
  await wrapper.get('[aria-label="单位名称"]').setValue('测试供应商')
  await wrapper.get('[aria-label="类型"]').setValue(kind)
  await wrapper.get(term).setValue('custom')
  await wrapper.get(days).setValue('45')
  await wrapper.get('[aria-label="类型"]').setValue('customer')
  await wrapper.get('[aria-label="类型"]').setValue(kind)
  expect((wrapper.get(term).element as HTMLSelectElement).value).toBe('custom')
  expect((wrapper.get(days).element as HTMLInputElement).value).toBe('45')
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(write).toHaveBeenCalledWith('/business/partners/', {
    name: '测试供应商', kind, payment_term: 'custom', payment_days: '45',
  }, expect.any(String), undefined)
  wrapper.unmount()
})

it('已有供应商改为客户时重置供应商默认账期，编辑客户也隐藏账期', async () => {
  const wrapper = open(await actionCommand('partners', {
    id: 7, name: '测试单位', kind: 'supplier', payment_term: 'month60', payment_days: 60, is_active: true,
  }, '编辑'))
  expect((wrapper.get(term).element as HTMLSelectElement).value).toBe('month60')
  await wrapper.get('[aria-label="类型"]').setValue('customer')
  expect(wrapper.find(term).exists()).toBe(false)
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  // 选填的联系人、电话、地址也提交空串，清空后服务端才会真正清除。
  expect(write).toHaveBeenCalledWith('/business/partners/7/', {
    name: '测试单位', kind: 'customer', is_active: true, payment_term: 'manual', payment_days: 0, contact: '', phone: '', address: '',
  }, expect.any(String), 'patch')
  await wrapper.setProps({ command: await actionCommand('partners', {
    id: 7, name: '测试单位', kind: 'customer', payment_term: 'manual', payment_days: 0, is_active: true,
  }, '编辑') })
  expect(wrapper.find(term).exists()).toBe(false)
  expect(wrapper.find(days).exists()).toBe(false)
  wrapper.unmount()
})

it('仅销售经理仍只能选择客户且不显示供应商账期', async () => {
  user.value = { id: 2, roles: ['sales_manager'] }
  const wrapper = open(await createCommand('partners'))
  expect(wrapper.find('[aria-label="类型"] option[value="supplier"]').exists()).toBe(false)
  expect(wrapper.find('[aria-label="类型"] option[value="both"]').exists()).toBe(false)
  await wrapper.get('[aria-label="类型"]').setValue('customer')
  expect(wrapper.find(term).exists()).toBe(false)
  expect(wrapper.find(days).exists()).toBe(false)
  wrapper.unmount()
})

it('已编码的物料编辑对话框说明类别、规格、图号、版本为何不可改', async () => {
  const { actionCommand } = await import('./masterdata')
  const coded = await actionCommand('items', { id: 1, name: '导轨', product_category: '1M', specification: 'A' }, '编辑')
  expect(coded.notice?.text).toContain('版本升级请新增物料编码')
  const free = await actionCommand('items', { id: 2, name: '螺钉', product_category: '' }, '编辑')
  expect(free.notice).toBeUndefined()
})

it('有图号的物料可查版本记录：列出同图号全部版本和参与项目的换版原因，旧版在列表里注明已有新版', async () => {
  const { read } = await import('../api')
  const { actionNames, columns } = await import('./masterdata')
  user.value = { roles: ['member'] }
  const old = { id: 7, code: 'JG-001', name: '夹爪安装板', drawing_number: 'DWG-001', drawing_revision: 'A', newer_revision: { id: 8, code: 'JG-001B', drawing_revision: 'B' } }
  expect(actionNames('items', old)).toEqual(['版本记录'])
  expect(actionNames('items', { ...old, drawing_number: '' })).toEqual([])
  expect(columns.items!.find(column => column.key === 'drawing_revision')!.format!(old)).toBe('A · 已有新版 B')
  vi.mocked(read).mockResolvedValue({
    drawing_number: 'DWG-001',
    versions: [
      { id: 7, code: 'JG-001', name: '夹爪安装板', drawing_revision: 'A', is_active: true, superseded_by: 'JG-001B', latest: false },
      { id: 8, code: 'JG-001B', name: '夹爪安装板', drawing_revision: 'B', is_active: true, superseded_by: '', latest: true },
    ],
    changes: [{ id: 3, created_at: '2026-11-17T01:30:00Z', created_by: '机械工程师', project_code: 'ATM2681', project_name: '上料线', assembly_unit: '01 上料', old_item_code: 'JG-001', old_revision: 'A', new_item_code: 'JG-001B', new_revision: 'B', old_quantity: '10.000', new_quantity: '10.000', converted_quantity: '2.000', reason: 'ECN-01 孔位调整' }],
  })
  const command = await actionCommand('items', old, '版本记录')
  expect(read).toHaveBeenCalledWith('/business/items/7/revisions/')
  expect(command.readonly).toBe(true)
  expect(command.notice!.text).toContain('当前最新为 B 版（JG-001B）')
  expect(command.initial!.versions.map((row: Record<string, string>) => row.state)).toEqual(['已由 JG-001B 取代', '最新'])
  expect(command.initial!.changes[0]).toMatchObject({ time: '2026-11-17 09:30', project: 'ATM2681 上料线', change: 'JG-001（A） → JG-001B（B）', amount: '10 → 10，在途 2 改单' })
})

it('物料表单可填购买链接，编辑时清空也提交空串；列表按网店显示可点开的链接', async () => {
  const { columns } = await import('./masterdata')
  const column = columns.items!.find(col => col.key === 'purchase_url')!
  expect(column.format!({ purchase_url: 'https://item.taobao.com/item.htm?id=1' })).toBe('淘宝 ↗')
  expect(column.href!({ purchase_url: 'https://item.taobao.com/item.htm?id=1' })).toBe('https://item.taobao.com/item.htm?id=1')
  expect(column.format!({ purchase_url: '' })).toBe('—')
  expect(column.href!({ purchase_url: 'javascript:alert(1)' })).toBe('')
  const created = await createCommand('items')
  const field = created.fields.find(f => f.key === 'purchase_url')!
  expect(field.optional).toBe(true)
  expect(field.hint).toContain('分享 → 复制链接')
  const edit = await actionCommand('items', { id: 7, name: '膨胀螺栓', unit: 'PCS', purchase_url: 'https://item.taobao.com/item.htm?id=1' }, '编辑')
  expect(edit.prepare!({ name: '膨胀螺栓', unit: 'PCS' }).purchase_url).toBe('')
  expect(edit.prepare!({ name: '膨胀螺栓', unit: 'PCS', purchase_url: 'https://item.jd.com/1.html' }).purchase_url).toBe('https://item.jd.com/1.html')
})
