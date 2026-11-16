import { beforeEach, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import RecordDeletionDialog from './RecordDeletionDialog.vue'
import { read, write } from '../api'
import { user } from '../session'
import { deletionLabel, deletionNotice, deletionLimit, deletionOutcome, removableResources } from '../modules/deletions'

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

it('失败按记录ID定位而非第几项，搜索后可重新定位且整批选择与删除原因保留', async () => {
  const rows = Array.from({ length: 150 }, (_, i) => ({ id: i === 149 ? 133 : 1000 + i, item_code: 'MAT12', item_name: '气缸', assembly_unit: `单元${i + 1}` }))
  const wrapper = make({ resource: 'bom', rows })
  const target = wrapper.get('[data-record-id="133"]')
  const scroll = vi.fn()
  Object.defineProperty(target.element, 'scrollIntoView', { configurable: true, value: scroll })
  await wrapper.get('input[type="search"]').setValue('单元1')
  await wrapper.get('textarea').setValue('清理误录')
  await wrapper.get('input[type="checkbox"]').setValue(true)
  vi.mocked(write).mockRejectedValue({ isAxiosError: true, response: { status: 409, data: { detail: 'BOM明细「MAT12 · 气缸 · 单元：单元150」不能删除：已有在途采购。整批未删除。', blocked_id: '133' } } })
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(wrapper.get('.deletion-blocked').attributes('data-record-id')).toBe('133')
  expect(wrapper.get('.deletion-blocked').attributes('value')).toBe('150')
  expect(wrapper.get('.deletion-blocked').text()).toContain('单元150')
  expect(scroll).toHaveBeenCalled()
  expect(wrapper.get('textarea').element.value).toBe('清理误录')
  expect(vi.mocked(write).mock.calls[0]![1]).toEqual({ resource: 'bom', ids: rows.map(row => row.id), reason: '清理误录' })
  expect(wrapper.emitted('saved')).toBeUndefined()
  await wrapper.get('input[type="search"]').setValue('不存在')
  expect(wrapper.text()).toContain('没有匹配的已选记录')
  await wrapper.findAll('button').find(button => button.text() === '定位不能删除的记录')!.trigger('click')
  await flushPromises()
  expect(wrapper.findAll('.deletion-records li')).toHaveLength(150)
  expect(wrapper.get('.deletion-blocked').attributes('data-record-id')).toBe('133')
  wrapper.unmount()
})

it.each(['999', 'not-an-id', undefined])('错误返回的非本次记录ID %s 不会错误高亮', async blocked_id => {
  const wrapper = make()
  await wrapper.get('textarea').setValue('清理误录')
  await wrapper.get('input[type="checkbox"]').setValue(true)
  vi.mocked(write).mockRejectedValue({ isAxiosError: true, response: { status: 409, data: { detail: '整批未删除。', blocked_id } } })
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(wrapper.find('.deletion-blocked').exists()).toBe(false)
  expect(wrapper.text()).not.toContain('定位不能删除的记录')
  expect(wrapper.text()).toContain('整批未删除')
  wrapper.unmount()
})

it('删除用户前说明停用隐藏、历史保留、不能普通编辑恢复且用户名不能复用', () => {
  const wrapper = make({ resource: 'users', title: '用户', rows: [{ id: 5, username: 'member', display_name: '成员' }] })
  for (const text of ['账号停用并从用户列表隐藏', '历史记录保留', '不能通过普通编辑恢复', '原用户名不能再次使用', '“已删除记录”中恢复账号', '不能删除当前登录账号'])
    expect(wrapper.text()).toContain(text)
  expect(wrapper.get('.deletion-confirm').text()).toContain('原用户名不能再次使用')
  expect(wrapper.get('.deletion-confirm').text()).toContain('恢复账号')
  wrapper.unmount()
})

const removedUsers = () => ({ count: 2, results: [
  { id: 21, actor_name: '管理员', created_at: '2026-10-22T08:00:00Z', restored: false, restored_at: null, restored_by: null, detail: { reason: '误删', mode: 'disable', record: { id: 5, username: 'member', display_name: '成员' } } },
  { id: 20, actor_name: '管理员', created_at: '2026-10-21T08:00:00Z', restored: true, restored_at: '2026-10-21T09:00:00Z', restored_by: '审核管理员', detail: { reason: '离职', mode: 'disable', record: { id: 6, username: 'old', display_name: '旧账号' } } },
] })
const buttons = (wrapper: ReturnType<typeof make>, text: string) => wrapper.findAll('button').filter(button => button.text() === text)

it('已删除账号显示是否已恢复；未恢复的可填写原因恢复，失败保留幂等标识，成功后刷新列表', async () => {
  vi.mocked(read).mockResolvedValue(removedUsers())
  const wrapper = make({ resource: 'users', title: '用户', rows: undefined })
  await flushPromises()
  expect(wrapper.text()).toContain('已恢复 · 审核管理员')
  expect(buttons(wrapper, '恢复账号')).toHaveLength(1)
  await buttons(wrapper, '恢复账号')[0]!.trigger('click')
  expect(wrapper.text()).toContain('恢复后为停用状态，请在用户管理中确认角色后启用')
  expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeDefined()
  await wrapper.get('textarea').setValue('误删，核对后恢复')
  vi.mocked(write).mockRejectedValueOnce(new Error('该账号未处于已删除状态')).mockResolvedValueOnce({ id: 5, is_active: false })
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(wrapper.text()).toContain('未处于已删除状态')
  expect(wrapper.emitted('saved')).toBeUndefined()
  const key = vi.mocked(write).mock.calls[0]![2]
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(write).toHaveBeenLastCalledWith('/business/record-deletions/restore/', { resource: 'users', id: 5, reason: '误删，核对后恢复' }, key)
  expect(wrapper.emitted('saved')).toHaveLength(1)
  expect(wrapper.emitted('close')).toBeUndefined()
  expect(read).toHaveBeenCalledTimes(2)
  expect(wrapper.find('form').exists()).toBe(false)
  wrapper.unmount()
})

it('恢复账号仅管理员可见，其他资源的已删除记录不提供恢复', async () => {
  vi.mocked(read).mockResolvedValue(removedUsers())
  user.value = { roles: ['finance'] }
  const finance = make({ resource: 'users', title: '用户', rows: undefined })
  await flushPromises()
  expect(buttons(finance, '恢复账号')).toHaveLength(0)
  expect(finance.text()).toContain('已恢复')
  finance.unmount()
  user.value = { roles: ['finance', 'admin'] }
  const entries = make({ resource: 'entries', title: '应收应付与费用', rows: undefined })
  await flushPromises()
  expect(buttons(entries, '恢复账号')).toHaveLength(0)
  entries.unmount()
  const admin = make({ resource: 'users', title: '用户', rows: undefined })
  await flushPromises()
  expect(buttons(admin, '恢复账号')).toHaveLength(1)
  admin.unmount()
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

it.each([['items', 1000], ['bom', 1000], ['partners', 1000]] as const)('%s确认删除遵守数量上限，超限不提交', async (resource, limit) => {
  const rows = Array.from({ length: limit + 1 }, (_, i) => ({ id: i + 1, name: '待核对记录' + i }))
  const wrapper = make({ resource, rows })
  await wrapper.get('textarea').setValue('批量清理测试')
  await wrapper.get('input[type="checkbox"]').setValue(true)
  await wrapper.get('form').trigger('submit')
  expect(write).not.toHaveBeenCalled()
  expect(wrapper.get('[role="alert"]').text()).toContain('每批最多删除 ' + limit + ' 条')
  await wrapper.setProps({ rows: rows.slice(0, limit) })
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(write).toHaveBeenCalledTimes(1)
  expect(vi.mocked(write).mock.calls[0]![1]).toEqual({ resource, ids: rows.slice(0, limit).map(row => row.id), reason: '批量清理测试' })
  wrapper.unmount()
})

it('全部可删除表单统一1000项，公司、编号及审计不提供批量删除', () => {
  for (const resource of removableResources) expect(deletionLimit(resource)).toBe(1000)
  for (const resource of ['company', 'codes', 'audit']) expect(deletionLimit(resource)).toBe(0)
})

const rejectedBatch = () => ({ isAxiosError: true, response: { status: 409, data: {
  detail: '往来单位「USED1 · 甲」不能删除：往来单位仍有未结束的销售单（SO-1）。另有 1 条也不能删除，整批未删除。', blocked_id: '12',
  blocked: [{ id: '12', label: 'USED1 · 甲', reason: '往来单位仍有未结束的销售单（SO-1）。' }, { id: '14', label: 'USED2 · 乙', reason: '往来单位还有未结清或待退款的款项（货款）。' }, { id: '999', label: '不在本批', reason: '忽略' }],
} } })
const fill = async (wrapper: ReturnType<typeof make>) => { await wrapper.get('textarea').setValue('清理误建'); await wrapper.get('input[type="checkbox"]').setValue(true) }

it('一次列出全部不能删除的记录和原因，去掉它们后只删其余记录', async () => {
  const rows = [{ id: 12, code: 'USED1', name: '甲' }, { id: 13, code: 'FREE', name: '丙' }, { id: 14, code: 'USED2', name: '乙' }]
  const wrapper = make({ resource: 'partners', title: '往来单位', rows })
  await fill(wrapper)
  vi.mocked(write).mockRejectedValueOnce(rejectedBatch()).mockResolvedValueOnce({ count: 1, records: [{ id: 13, mode: 'soft' }] })
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  const panel = wrapper.get('[aria-label="不能删除的记录"]')
  expect(panel.text()).toContain('2 条不能删除，其余 1 条可以删除')
  for (const text of ['USED1 · 甲', 'SO-1', 'USED2 · 乙', '未结清或待退款']) expect(panel.text()).toContain(text)
  expect(panel.text()).not.toContain('不在本批')
  expect(wrapper.findAll('.deletion-blocked').map(row => row.attributes('data-record-id'))).toEqual(['12', '14'])
  const firstKey = vi.mocked(write).mock.calls[0]![2]
  await buttons(wrapper, '去掉这 2 条，只删其余 1 条')[0]!.trigger('click')
  expect(wrapper.find('[aria-label="不能删除的记录"]').exists()).toBe(false)
  expect(wrapper.text()).not.toContain('整批未删除。')
  expect(wrapper.findAll('.deletion-records li').map(row => row.attributes('data-record-id'))).toEqual(['13'])
  expect(wrapper.text()).toContain('已从本批去掉 2 条不能删除的记录')
  expect(wrapper.get('button[type="submit"]').text()).toBe('确认删除 1 条')
  expect(wrapper.get('textarea').element.value).toBe('清理误建')
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  const [, payload, secondKey] = vi.mocked(write).mock.calls[1]!
  expect(payload).toEqual({ resource: 'partners', ids: [13], reason: '清理误建' })
  expect(secondKey).not.toBe(firstKey)
  expect(wrapper.emitted('saved')).toHaveLength(1)
  expect(wrapper.emitted('close')).toHaveLength(1)
  wrapper.unmount()
})

it('整批都不能删除时只列原因，不提供删除其余记录', async () => {
  const wrapper = make({ resource: 'partners', title: '往来单位', rows: [{ id: 12, code: 'USED1', name: '甲' }, { id: 14, code: 'USED2', name: '乙' }] })
  await fill(wrapper)
  vi.mocked(write).mockRejectedValue(rejectedBatch())
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(wrapper.get('[aria-label="不能删除的记录"]').text()).toContain('2 条不能删除：')
  expect(wrapper.findAll('button').some(button => button.text().startsWith('去掉这'))).toBe(false)
  wrapper.unmount()
})

it('项目连带移出子单据后，仍在办的记录留在结果页，关闭时才刷新列表', async () => {
  const wrapper = make({ resource: 'projects', title: '项目', rows: [{ id: 12, code: 'PRJ1', name: '已取消项目' }] })
  expect(wrapper.text()).toContain('销售单、采购单、任务、工时和款项随项目一并移出列表')
  await fill(wrapper)
  vi.mocked(write).mockResolvedValue({ count: 1, records: [{ id: 12, mode: 'archive', cascaded: { sales: 1, tasks: 3 }, kept_count: 2,
    kept: [{ resource: 'entries', label: '应收应付与费用「合同款」', reason: '账款还有待退款 300.00 元，请先完成退款对账和退款后再删除。' }, { resource: 'payments', label: '收付款流水「记录编号：7」', reason: '所属账款尚未结清。' }] }] })
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(wrapper.text()).toContain('已删除 1 条项目。随项目一并移出列表：销售单 1、任务 3')
  const kept = wrapper.get('[aria-label="保留在原列表的记录"]')
  expect(kept.text()).toContain('2 条仍在办，保留在原列表')
  expect(kept.text()).toContain('应收应付与费用「合同款」')
  expect(kept.text()).toContain('待退款 300.00 元')
  expect(wrapper.find('form').exists()).toBe(false)
  expect(wrapper.emitted('saved')).toBeUndefined()
  await buttons(wrapper, '知道了')[0]!.trigger('click')
  expect(wrapper.emitted('saved')).toHaveLength(1)
  expect(wrapper.emitted('close')).toHaveLength(1)
  wrapper.unmount()
})

it('没有保留记录时照常关闭，附带结果只作提示', async () => {
  const wrapper = make({ resource: 'sales', title: '销售订单', rows: [{ id: 12, code: 'SO1', name: '误建' }] })
  expect(wrapper.text()).toContain('草稿上未被引用的附件随单据一并删除')
  await fill(wrapper)
  vi.mocked(write).mockResolvedValue({ count: 1, records: [{ id: 12, mode: 'soft', documents: 2 }] })
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(wrapper.emitted('saved')).toHaveLength(1)
  expect(wrapper.emitted('close')).toHaveLength(1)
  expect(deletionOutcome({ count: 1, records: [{ id: 12, mode: 'soft', documents: 2 }] }).notes).toEqual(['同时删除 2 份未被引用的附件'])
  expect(deletionOutcome({ count: 2, records: [{ id: 1, mode: 'soft' }, { id: 2, mode: 'soft' }] })).toEqual({ count: 2, notes: [], kept: [], keptCount: 0 })
  wrapper.unmount()
})

it('停用归档的物料和往来单位可恢复到列表，彻底删除的不提供恢复', async () => {
  for (const [resource, texts] of [['items', ['停用并移出列表', '编码、图号和历史单据保留', '还有库存']], ['partners', ['停用并移出列表', '未结清款项']]] as const)
    for (const text of texts) expect(deletionNotice(resource), resource).toContain(text)
  vi.mocked(read).mockResolvedValue({ count: 3, results: [
    { id: 31, actor_name: '管理员', created_at: '2026-11-16T08:00:00Z', restored: false, detail: { reason: '不再使用', mode: 'disable', record: { id: 5, code: 'MAT5', name: '旧气缸' } } },
    { id: 30, actor_name: '管理员', created_at: '2026-11-16T07:00:00Z', restored: false, detail: { reason: '误建', mode: 'soft', record: { id: 6, code: 'MAT6', name: '误建物料' } } },
    { id: 29, actor_name: '管理员', created_at: '2026-11-16T06:00:00Z', restored: true, restored_at: '2026-11-16T09:00:00Z', restored_by: '管理员', detail: { reason: '停用', mode: 'disable', record: { id: 7, code: 'MAT7', name: '已恢复物料' } } },
  ] })
  const wrapper = make({ resource: 'items', title: '物料', rows: undefined })
  await flushPromises()
  expect(wrapper.text()).toContain('处理方式：已停用并移出列表，编码和历史单据保留')
  expect(wrapper.text()).toContain('处理方式：未被使用，已删除')
  expect(buttons(wrapper, '恢复到列表')).toHaveLength(1)
  await buttons(wrapper, '恢复到列表')[0]!.trigger('click')
  expect(wrapper.text()).toContain('仍为停用状态，请核对后在编辑中启用')
  await wrapper.get('textarea').setValue('仍要使用')
  vi.mocked(write).mockResolvedValue({ id: 5, is_active: false })
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(write).toHaveBeenCalledWith('/business/record-deletions/restore/', { resource: 'items', id: 5, reason: '仍要使用' }, expect.any(String))
  expect(wrapper.emitted('saved')).toHaveLength(1)
  wrapper.unmount()
})

it('已删除记录说明随哪个项目或单据一并处理，以及项目连带移出的子单据', async () => {
  vi.mocked(read).mockResolvedValue({ count: 1, results: [{ id: 40, actor_name: '管理员', created_at: '2026-11-16T08:00:00Z', restored: false,
    detail: { reason: '项目取消', mode: 'archive', via: { resource: 'projects', id: 3, label: 'PRJ3 · 已取消项目' }, record: { id: 8, code: 'SO8', name: '销售' } } }] })
  const sales = make({ resource: 'sales', title: '销售订单', rows: undefined })
  await flushPromises()
  expect(sales.text()).toContain('处理方式：已移出列表，原始记录保留（随「PRJ3 · 已取消项目」一并处理）')
  sales.unmount()
  vi.mocked(read).mockResolvedValue({ count: 1, results: [{ id: 41, actor_name: '管理员', created_at: '2026-11-16T08:00:00Z', restored: false,
    detail: { reason: '项目取消', mode: 'archive', cascaded: { sales: 1, purchases: 2, payments: 4 }, record: { id: 3, code: 'PRJ3', name: '已取消项目' } } }] })
  const projects = make({ resource: 'projects', title: '项目', rows: undefined })
  await flushPromises()
  expect(projects.text()).toContain('随项目一并移出列表：销售单 1、采购单 2、收付款流水 4')
  projects.unmount()
})
