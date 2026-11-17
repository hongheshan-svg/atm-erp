import { afterEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import BOMRevisionPanel from './BOMRevisionPanel.vue'
import { read } from '../api'
import { user } from '../session'
import type { Command } from '../types'

vi.mock('../api', () => ({ read: vi.fn() }))
afterEach(() => { user.value = null; vi.resetAllMocks() })

const part = {
  change: 3, old_item: 7, old_item_code: 'JG-001', old_item_name: '夹爪安装板', old_revision: 'A', new_item_code: 'JG-001B', new_revision: 'B', new_line: 12,
  assembly_unit: '01 上料', reason: 'ECN-01 孔位调整', pending_stock: '3.000', pending_issued: '2.000', scrapped_stock: '1.000', kept: '0.000', rework_stock: '0.000', scrapped_issued: '0.000', rework_issued: '0.000', open: true,
}
const change = { id: 3, old_item_code: 'JG-001', old_revision: 'A', new_item_code: 'JG-001B', new_revision: 'B', assembly_unit: '01 上料', old_quantity: '10.000', new_quantity: '10.000', converted_quantity: '4.000', reason: 'ECN-01 孔位调整', created_at: '2026-11-17T09:30:00+08:00', created_by: '机械工程师' }

async function render(props: Record<string, unknown> = {}) {
  vi.mocked(read).mockResolvedValue({ parts: [part], changes: [change] })
  const wrapper = mount(BOMRevisionPanel, { props: { projectId: 81, status: 'active', ...props }, global: { plugins: [ElementPlus] } })
  await flushPromises()
  return wrapper
}

it('列出旧版待处理与换版记录：在库和已装机数量、已处理汇总、在途按新图改单', async () => {
  user.value = { roles: ['warehouse'] }
  const wrapper = await render()
  expect(read).toHaveBeenCalledWith('/business/projects/81/obsolete-parts/')
  const text = wrapper.text()
  expect(text).toContain('旧版待处理')
  expect(text).toContain('JG-001（A 版） → JG-001B（B 版）')
  expect(text).toContain('在库 3')
  expect(text).toContain('已装机 2')
  expect(text).toContain('已处理：在库报废 1')
  expect(text).toContain('换版记录（1）')
  expect(text).toContain('在途 4 按新图改单')
})

it('按岗位给处理入口：仓管报废或留用在库、登记已装机报废；采购开返修单；只读角色不显示', async () => {
  user.value = { roles: ['warehouse'] }
  let wrapper = await render()
  expect((wrapper.vm as any).$.setupState.actions(part)).toEqual(['在库报废', '留作备件', '已装机报废'])
  ;(wrapper.vm as any).$.setupState.act(part, '在库报废')
  const scrap = wrapper.emitted('command')![0]![0] as Command
  expect(scrap.path).toBe('/business/revision-changes/3/dispose/')
  expect(scrap.initial).toMatchObject({ quantity: '3' })
  expect(scrap.prepare!({ quantity: '2', reason: '孔位不对' })).toEqual({ source: 'stock', kind: 'scrap', quantity: '2', reason: '孔位不对' })
  ;(wrapper.vm as any).$.setupState.act(part, '留作备件')
  expect(((wrapper.emitted('command')![1]![0]) as Command).prepare!({ quantity: '1', reason: '公用' })).toMatchObject({ source: 'stock', kind: 'keep' })
  wrapper.unmount()

  user.value = { roles: ['mechanical_engineer'] }
  wrapper = await render({ canEditBom: true })
  expect((wrapper.vm as any).$.setupState.actions(part)).toEqual(['已装机报废'])
  wrapper.unmount()

  user.value = { roles: ['purchaser'] }
  wrapper = await render()
  expect((wrapper.vm as any).$.setupState.actions(part)).toEqual(['开返修单'])
  ;(wrapper.vm as any).$.setupState.act(part, '开返修单')
  const rework = wrapper.emitted('command')![0]![0] as Command
  expect(rework.path).toBe('/business/revision-changes/3/rework/')
  expect(rework.fields.find(field => field.key === 'source')!.options!.map(option => option.value)).toEqual(['stock', 'issued'])
  expect(rework.initial).toMatchObject({ source: 'stock', quantity: '3' })
  // 已结项或取消的项目不再给处理入口。
  await wrapper.setProps({ status: 'closed' })
  expect((wrapper.vm as any).$.setupState.actions(part)).toEqual([])
  wrapper.unmount()

  user.value = { roles: ['finance'] }
  vi.mocked(read).mockClear()
  wrapper = await render()
  expect(read).not.toHaveBeenCalled()
  expect(wrapper.find('.bom-revision-panel').exists()).toBe(false)
})
