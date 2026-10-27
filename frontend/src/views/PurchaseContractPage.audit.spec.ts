import { afterEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { installElementPlus } from '../plugins/elementPlus'
import { all, read } from '../api'
import { user } from '../session'
import PurchaseContractPage from './PurchaseContractPage.vue'
import ActionDialog from '../components/ActionDialog.vue'
import type { Row } from '../types'

vi.mock('../api', () => ({ all: vi.fn(), read: vi.fn() }))
afterEach(() => { vi.restoreAllMocks(); vi.resetAllMocks(); user.value = null })

const complete = {
  code: 'PO-COMPLETE', draft: true, status: 'draft', payment_term: 'month30', payment_days: 30,
  warranty_months: 12, due_date: '2026-12-31', total: '320.00',
  buyer: { name: '采购方', address: '完整采购地址'.repeat(30) },
  supplier: { name: '非标加工供应商'.repeat(12), address: '完整供货地址'.repeat(30), contact: '联系人'.repeat(15) },
  project: '非标自动化装配线'.repeat(12), note: '补充约定完整保留。\n'.repeat(40), versions: [],
  clauses: { technical: ['确认图纸版本'], quality: ['按约验收', '验收合格之日起12个月'], automation: ['控制程序备份与接口要求'], liability: ['按约承担违约责任'] },
  lines: Array.from({ length: 32 }, (_, index) => ({ number: index + 1, code: `CODE-${index + 1}`, name: `物料${index + 1}`, specification: '完整规格'.repeat(30), drawing_number: 'DRW-1', drawing_revision: 'B', brand: '品牌', unit: '件', quantity: '1.000', unit_price: '10.00', amount: '10.00', due_date: '2026-12-31' })),
}
async function mountContract() {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/purchases/:id/contract', component: PurchaseContractPage }] })
  await router.push('/purchases/1/contract')
  const wrapper = mount(PurchaseContractPage, { global: { plugins: [{ install: installElementPlus }, router], stubs: { ActionDialog: true } } })
  await flushPromises()
  return { wrapper, router }
}

it('一份合同同时完整显示32项明细、长资料、全部条款及签章，打印无需切换或勾选', async () => {
  vi.mocked(read).mockResolvedValue(complete)
  const print = vi.spyOn(window, 'print').mockImplementation(() => {})
  const { wrapper } = await mountContract()
  const article = wrapper.get('article')
  expect(wrapper.findAll('article')).toHaveLength(1)
  expect(article.findAll('tbody tr')).toHaveLength(32)
  for (const value of [complete.buyer.address, complete.supplier.name, complete.supplier.address, complete.project, complete.lines[0]!.specification, '确认图纸版本', '控制程序备份与接口要求', '质量、验收与12个月质保', '验收合格之日起12个月', '月结30天', '甲方签字', '乙方签字']) expect(article.text()).toContain(value)
  expect(wrapper.get('.contract-note').element.textContent).toBe(complete.note)
  expect(wrapper.text()).not.toContain('查看完整附件')
  expect(wrapper.text()).not.toContain('详见同编号合同附件')
  expect(wrapper.find('input[type="checkbox"]').exists()).toBe(false)
  await wrapper.findAll('button').find(button => button.text() === '打印 / 另存为 PDF')!.trigger('click')
  expect(print).toHaveBeenCalledOnce()
  expect(wrapper.findAll('article')).toHaveLength(1)
  wrapper.unmount()
})

it('历史归档完整显示旧条款，新行业条款仅显示在有对应快照的版本中', async () => {
  vi.mocked(read).mockImplementation(async (_path, params) => params?.version === 'current' ? complete : {
    ...complete, archived_version: 1, versions: [{ version: 1 }],
    clauses: { quality: ['历史质量约定'], liability: ['历史违约约定'] },
  })
  const { wrapper } = await mountContract()
  expect(wrapper.get('article').text()).toContain('历史质量约定')
  expect(wrapper.get('article').text()).not.toContain('控制程序备份与接口要求')
  expect(wrapper.findAll('tbody tr')).toHaveLength(32)
  await wrapper.get('select[aria-label="合同版本"]').setValue('current')
  await flushPromises()
  expect(wrapper.get('article').text()).toContain('控制程序备份与接口要求')
  expect(wrapper.get('article').text()).not.toContain('历史质量约定')
  wrapper.unmount()
})

it('切换采购单后忽略旧单迟到响应，避免显示或打印错合同', async () => {
  let resolveOld!: (value: Row) => void
  vi.mocked(read).mockImplementation(path => path.includes('/1/') ? new Promise(resolve => { resolveOld = resolve }) : Promise.resolve({ ...complete, code: 'PO-NEW' }))
  const { wrapper, router } = await mountContract()
  await router.push('/purchases/2/contract')
  await flushPromises()
  expect(wrapper.get('article').text()).toContain('PO-NEW')
  resolveOld({ ...complete, code: 'PO-OLD' })
  await flushPromises()
  expect(wrapper.get('article').text()).toContain('PO-NEW')
  expect(wrapper.get('article').text()).not.toContain('PO-OLD')
  wrapper.unmount()
})
it('已有归档可直接归档新版本，切回历史预览不改变已打开表单的当前快照', async () => {
  user.value = { id: 1, roles: ['purchaser'] }
  const common = { code: 'PO-1', draft: false, status: 'approved', buyer: {}, supplier: {}, lines: [], clauses: { quality: [], liability: [] }, versions: [{ version: 1 }] }
  vi.mocked(read).mockImplementation(async (_path, params) => params?.version === 'current'
    ? { ...common, archived_version: null, snapshot_hash: 'current-snapshot' }
    : { ...common, archived_version: 1, snapshot_hash: 'history-view-snapshot' })
  vi.mocked(all).mockResolvedValue([{ id: 8, original_name: '签署合同.pdf' }])
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/purchases/:id/contract', component: PurchaseContractPage }] })
  await router.push('/purchases/1/contract')
  const wrapper = mount(PurchaseContractPage, { global: { plugins: [{ install: installElementPlus }, router], stubs: { ActionDialog: true } } })
  await flushPromises()
  await wrapper.findAll('button').find(button => button.text() === '归档新版本')!.trigger('click')
  await flushPromises()
  expect(read).toHaveBeenCalledWith('/business/purchases/1/contract-preview/', { version: 'current' })
  const command = wrapper.findComponent(ActionDialog).props('command')!
  expect(command.prepare?.({ document: 8 }).expected_snapshot).toBe('current-snapshot')
  await wrapper.get('select[aria-label="合同版本"]').setValue('1')
  await flushPromises()
  expect(command.prepare?.({ document: 8 }).expected_snapshot).toBe('current-snapshot')
  wrapper.unmount()
})
