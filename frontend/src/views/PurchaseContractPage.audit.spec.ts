import { afterEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { installElementPlus } from '../plugins/elementPlus'
import { all, read } from '../api'
import { user } from '../session'
import PurchaseContractPage from './PurchaseContractPage.vue'
import ActionDialog from '../components/ActionDialog.vue'

vi.mock('../api', () => ({ all: vi.fn(), read: vi.fn() }))
afterEach(() => { vi.resetAllMocks(); user.value = null })
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
