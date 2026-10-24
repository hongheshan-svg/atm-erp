import { beforeEach, expect, it, vi } from 'vitest'
import { flushPromises, mount, RouterLinkStub, shallowMount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import DataChecks from './DataChecks.vue'
import TransferTools from './TransferTools.vue'
import SettingsPage from '../views/SettingsPage.vue'
import { read } from '../api'
import { user } from '../session'
import { exportFilename } from '../utils/import-context'

vi.mock('../api', () => ({ read: vi.fn(), write: vi.fn(), all: vi.fn().mockResolvedValue([]), download: vi.fn() }))
const categories = [
  { key: 'duplicate-payments', label: '同一款项重复登记的银行收付款', count: 2 },
  { key: 'deleted-open', label: '已删除但仍在办的记录', count: 1 },
]
const page = (category: string, results: object[]) => ({ count: results.length, next: null, previous: null, results, category, categories, notice: '' })
const payment = { category: 'duplicate-payments', record_type: 'payments', record_type_label: '收付款流水', record_id: 7, title: '合同款 · 流水号 DUP-1', project_code: 'ATM2601', amount: '100.00', problem: '可能重复登记；请核对银行流水后对重复的一笔使用“冲销”。', path: '/finance?section=payments&resource=payments&focus=7&project=all' }
const delivery = { category: 'deleted-open', record_type: 'deliveries', record_type_label: '交付记录', record_id: 3, title: 'DEL-1', project_code: 'ATM2601', amount: null, problem: '已移入“已删除记录”，但按现行在办规则仍在办：交付批次尚未验收', path: '/projects/1?tab=deliveries&section=deliveries&resource=deliveries&focus=3' }
const make = () => mount(DataChecks, { global: { plugins: [ElementPlus], stubs: { RouterLink: RouterLinkStub, TransferTools: true } } })
beforeEach(() => { vi.resetAllMocks(); user.value = { id: 1, roles: ['admin'] } })

it('管理员按类别查看计数与明细，可打开原单并导出当前类别，说明只读不改数据', async () => {
  vi.mocked(read).mockResolvedValueOnce(page('duplicate-payments', [payment])).mockResolvedValueOnce(page('deleted-open', [delivery]))
  const wrapper = make()
  await flushPromises()
  expect(read).toHaveBeenLastCalledWith('/business/data-checks/', { page: 1, page_size: 10 })
  expect(wrapper.text()).toContain('只读核查，不会修改任何数据；请用原单上的冲销、作废、取消等动作处理。')
  expect(wrapper.text()).toContain('同一款项重复登记的银行收付款（2）')
  expect(wrapper.text()).toContain('已删除但仍在办的记录（1）')
  expect(wrapper.text()).toContain('合同款 · 流水号 DUP-1')
  expect(wrapper.text()).toContain('100.00')
  expect(wrapper.getComponent(RouterLinkStub).props('to')).toBe(payment.path)
  expect(wrapper.getComponent(TransferTools).props()).toMatchObject({ resource: 'data-checks', exportPath: '/business/data-checks/', params: { category: 'duplicate-payments' }, allowImport: false })
  await wrapper.findAll('button').find(button => button.text().startsWith('已删除但仍在办的记录'))!.trigger('click')
  await flushPromises()
  expect(read).toHaveBeenLastCalledWith('/business/data-checks/', { category: 'deleted-open', page: 1, page_size: 10 })
  expect(wrapper.text()).toContain('交付批次尚未验收')
  expect(wrapper.find('.data-check-amount').text()).toBe('—')
  expect(wrapper.getComponent(TransferTools).props('params')).toEqual({ category: 'deleted-open' })
  expect(exportFilename('data-checks', 'xlsx', new Date(2026, 9, 24))).toBe('历史数据核查导出_2026-10-24.xlsx')
  wrapper.unmount()
})

it('读取失败显示中文原因，非管理员不请求也不显示', async () => {
  vi.mocked(read).mockRejectedValueOnce({ response: { status: 403, data: { detail: '没有此操作权限。' } } })
  const wrapper = make()
  await flushPromises()
  expect(wrapper.find('[role="alert"]').exists()).toBe(true)
  wrapper.unmount()
  vi.mocked(read).mockClear()
  user.value = { id: 2, roles: ['finance'] }
  const hidden = make()
  await flushPromises()
  expect(read).not.toHaveBeenCalled()
  expect(hidden.text()).not.toContain('历史数据核查')
  hidden.unmount()
})

it('设置页仅向管理员显示历史数据核查入口', () => {
  const tabs = (roles: string[]) => {
    user.value = { id: 1, roles }
    const wrapper = shallowMount(SettingsPage, { global: { plugins: [ElementPlus], stubs: { RouterLink: RouterLinkStub } } })
    const keys = (wrapper.findComponent({ name: 'ModuleTabs' }).props('tabs') as { key: string; label: string }[])
    wrapper.unmount()
    return keys
  }
  expect(tabs(['admin'])).toContainEqual({ key: 'data-checks', label: '历史数据核查' })
  expect(tabs(['finance', 'manager']).map(tab => tab.key)).not.toContain('data-checks')
})
