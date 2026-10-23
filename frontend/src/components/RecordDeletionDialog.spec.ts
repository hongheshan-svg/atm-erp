import { beforeEach, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import RecordDeletionDialog from './RecordDeletionDialog.vue'
import { read, write } from '../api'
import { user } from '../session'
import { deletionLabel, deletionNotice } from '../modules/deletions'

vi.mock('../api', () => ({ read: vi.fn(), write: vi.fn(), all: vi.fn().mockResolvedValue([]), download: vi.fn() }))
const props = { resource: 'items', title: '物料', rows: [{ id: 12, code: 'MAT12', name: '气缸' }, { id: 13, name: '导轨' }] }
const make = (extra = {}) => mount(RecordDeletionDialog, { props: { ...props, ...extra }, global: { plugins: [ElementPlus], stubs: { ElDialog: { template: '<section><slot /></section>' } } } })
beforeEach(() => { vi.resetAllMocks(); user.value = { id: 1, roles: ['admin'] } })

it('同物料不同单元在删除确认中可清楚区分', () => {
  const row = { id: 12, item_code: 'MAT12', item_name: '气缸', assembly_unit: '上料单元' }
  expect(deletionLabel(row)).toContain('MAT12')
  expect(deletionLabel(row)).toContain('上料单元')
  expect(deletionLabel({ ...row, assembly_unit: '检测单元' })).toContain('检测单元')
})

it('删除用户前说明停用隐藏、历史保留、不能普通编辑恢复且用户名不能复用', () => {
  const wrapper = make({ resource: 'users', title: '用户', rows: [{ id: 5, username: 'member', display_name: '成员' }] })
  for (const text of ['账号停用并从用户列表隐藏', '历史记录保留', '不能通过普通编辑恢复', '原用户名不能再次使用', '不能删除当前登录账号'])
    expect(wrapper.text()).toContain(text)
  expect(wrapper.get('.deletion-confirm').text()).toContain('原用户名不能再次使用')
  wrapper.unmount()
})

it('账款、流水、对账、银行和交付的删除说明提示在办记录会被拒绝及下一步', () => {
  const cases: Array<[string, string[]]> = [
    ['entries', ['余额未结清', '待退款', '对账单']],
    ['payments', ['所属账款尚未结清', '冲销或匹配']],
    ['reconciliations', ['待确认', '剩余核准额度', '作废']],
    ['bank-records', ['未认领', '待复核', '作废']],
    ['deliveries', ['未验收', '质保期内', '结项或取消后可整理']],
  ]
  for (const [resource, texts] of cases) {
    const notice = deletionNotice(resource)
    for (const text of [...texts, '不能删除', '已结束的记录仅移入']) expect(notice, resource).toContain(text)
  }
  expect(deletionNotice('moves')).not.toContain('不能删除')
  expect(deletionNotice('moves')).toContain('不会撤销业务')
  const wrapper = make({ resource: 'entries', title: '应收应付与费用', rows: [{ id: 3, title: '合同款' }] })
  expect(wrapper.text()).toContain('余额未结清')
  wrapper.unmount()
})

it('明确勾选记录，填写原因并确认后才提交，失败保留内容和幂等标识，重试成功后关闭', async () => {
  const wrapper = make()
  expect(wrapper.text()).toContain('MAT12')
  expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeDefined()
  await wrapper.get('textarea').setValue('测试记录清理')
  expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeDefined()
  await wrapper.get('input[type="checkbox"]').setValue(true)
  vi.mocked(write).mockRejectedValueOnce(new Error('关联记录不能删除，整批未删除。')).mockResolvedValueOnce({ count: 2 })
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(wrapper.text()).toContain('整批未删除')
  expect(wrapper.emitted('saved')).toBeUndefined()
  const key = vi.mocked(write).mock.calls[0]![2]
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(write).toHaveBeenLastCalledWith('/business/record-deletions/', { resource: 'items', ids: [12, 13], reason: '测试记录清理' }, key)
  expect(wrapper.emitted('saved')).toHaveLength(1)
  expect(wrapper.emitted('close')).toHaveLength(1)
  wrapper.unmount()
})

it('撤销管理员权限后不能提交；兼任管理员可提交', async () => {
  const wrapper = make()
  await wrapper.get('textarea').setValue('清理')
  await wrapper.get('input[type="checkbox"]').setValue(true)
  user.value = { role: 'finance' }
  await wrapper.get('form').trigger('submit')
  expect(write).not.toHaveBeenCalled()
  user.value = { roles: ['finance', 'admin'] }
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(write).toHaveBeenCalledTimes(1)
  wrapper.unmount()
})

it('已删除记录按项目过滤，显示操作原因和快照，保留原始流水入口', async () => {
  vi.mocked(read).mockResolvedValue({ count: 1, results: [{ id: 9, actor_name: '管理员', created_at: '2026-10-22T08:00:00Z', detail: { reason: '已核对', mode: 'archive', record: { id: 12, title: '合同款', amount: '500.00' } } }] })
  const wrapper = make({ resource: 'entries', rows: undefined, projectId: 3 })
  await flushPromises()
  expect(read).toHaveBeenCalledWith('/business/record-deletions/', expect.objectContaining({ resource: 'entries', project: 3 }))
  expect(wrapper.text()).toContain('管理员')
  expect(wrapper.text()).toContain('已核对')
  await wrapper.findAll('button').find(button => button.text() === '查看删除时内容')!.trigger('click')
  expect(wrapper.find('dl').text()).toContain('合同款')
  await wrapper.findAll('button').find(button => button.text() === '查看原始记录')!.trigger('click')
  expect(wrapper.emitted('open')).toEqual([[12]])
  wrapper.unmount()
})
