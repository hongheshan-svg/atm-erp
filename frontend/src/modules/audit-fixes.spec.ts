import { beforeEach, expect, it, vi } from 'vitest'
import { read } from '../api'
import { actionCommand, actionNames } from '../business'
import { bomCommand } from './bom'
import { participants } from './shared'
import { actionGroup } from '../row-actions'
import { user } from '../session'

vi.mock('../api', () => ({ all: vi.fn(), read: vi.fn(), write: vi.fn(), download: vi.fn() }))
beforeEach(() => { vi.resetAllMocks(); user.value = { id: 1, roles: ['admin'] } })

it('执行人下拉只留项目成员和跨项目岗位', () => {
  const people = [
    { id: 1, roles: ['manager'] },
    { id: 2, roles: ['member'] },
    { id: 3, roles: ['mechanical_engineer'] },
    { id: 4, roles: ['warehouse'] },
    { id: 5, roles: ['sales_manager'] },
  ]
  const scope = { manager: 1, members: [2] }
  expect(participants(people, scope).map(p => p.id)).toEqual([1, 2, 4])
  // 没有项目上下文时（例如还没选项目）不做裁剪，交给服务端按字段报错。
  expect(participants(people, null).map(p => p.id)).toEqual([1, 2, 3, 4, 5])
})

it('维护 BOM 只提交本次变更，不再把整张 BOM 灌进表单', async () => {
  vi.mocked(read).mockResolvedValue({ revision: 'rev-1', lines: [{ bom_line: 1 }, { bom_line: 2 }] })
  const command = await bomCommand(7)
  expect(command.initial).toBeUndefined()
  expect(command.notice?.text).toContain('本项目现有 2 行')
  expect(command.fields[0]?.fields?.find(f => f.key === 'item')?.remotePath).toBe('/business/items/')
  expect(command.prepare?.({ lines: [{ item: 3, quantity: '2', change_note: '新增' }] })).toEqual({
    expected_revision: 'rev-1',
    lines: [{ item: 3, quantity: '2', change_note: '新增', assembly_unit: '', required_date: null, application_date: null, applicant: '' }],
  })
})

it('BOM 单行修改只提交这一行并带上当前版本', async () => {
  vi.mocked(read).mockResolvedValue({ revision: 'rev-9', lines: [] })
  const row = { id: 5, project: 7, item: 3, item_code: 'M1', item_name: '导轨', quantity: '4.000', assembly_unit: '主机' }
  expect(actionNames('bom', { ...row, can_edit_bom: true })).toEqual(['修改此行', '移除'])
  const command = await actionCommand('bom', row, '修改此行')
  expect(command.path).toBe('/business/projects/7/revise-bom/')
  expect(command.initial?.quantity).toBe('4.000')
  expect(command.prepare?.({ quantity: '6', assembly_unit: '主机', change_note: 'ECN-3', applicant: '' })).toEqual({
    expected_revision: 'rev-9',
    lines: [{ id: 5, item: 3, quantity: '6', assembly_unit: '主机', change_note: 'ECN-3', required_date: null, application_date: null, applicant: '' }],
  })
})

it('附件可由上传者撤回，被引用时由服务端拦截', async () => {
  expect(actionNames('documents', { id: 1, can_remove: false })).toEqual(['下载'])
  expect(actionNames('documents', { id: 1, can_remove: true })).toEqual(['下载', '删除附件'])
  const command = await actionCommand('documents', { id: 1, can_remove: true, original_name: '图纸.pdf' }, '删除附件')
  expect(command.path).toBe('/business/documents/1/remove/')
  expect(command.fields.map(f => f.key)).toEqual(['reason'])
  expect(command.notice?.text).toContain('图纸.pdf')
})

it('取消、作废、撤销、删除归入更正组，不和推进单据混在一起', () => {
  for (const name of ['取消未收余量', '作废对账', '撤销银行匹配', '删除附件', '冲销付款', '退回修改'])
    expect(actionGroup(name)).toBe('correct')
  for (const name of ['提交采购', '收货', '登记收付款']) expect(actionGroup(name)).toBe('advance')
  for (const name of ['查看明细', '处理记录', '附件']) expect(actionGroup(name)).toBe('reference')
  expect(actionGroup('登记采购质保')).toBe('warranty')
})
