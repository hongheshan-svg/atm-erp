import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import Upgrade from '../Upgrade.vue'

vi.mock('@/api/system', () => ({
  getSystemVersion: vi.fn().mockResolvedValue({ version: '0.2.0', deploy_mode: 'docker' }),
  checkUpdate: vi.fn().mockResolvedValue({
    current_version: '0.2.0',
    latest_version: '0.3.0',
    has_update: true,
    release_notes_md: '## 0.3.0',
    deploy_mode: 'docker',
    warning: '',
  }),
  performUpgrade: vi.fn(),
  getUpgradeJob: vi.fn(),
  listUpgradeJobs: vi.fn().mockResolvedValue([]),
  rollbackUpgrade: vi.fn(),
}))

vi.mock('element-plus', () => ({
  ElMessage: { success: vi.fn(), warning: vi.fn(), error: vi.fn() },
  ElMessageBox: { confirm: vi.fn().mockResolvedValue('confirm') },
}))

// Stub Element Plus components to avoid import issues in test env
const globalStubs = {
  'el-card': { template: '<div><slot name="header" /><slot /></div>' },
  'el-button': { template: '<button @click="$emit(\'click\')"><slot /></button>', emits: ['click'] },
  'el-tag': { template: '<span><slot /></span>' },
  'el-table': true,
  'el-table-column': true,
}

describe('Upgrade.vue', () => {
  it('shows current version on mount', async () => {
    const wrapper = mount(Upgrade, { global: { stubs: globalStubs } })
    await flushPromises()
    expect(wrapper.text()).toContain('0.2.0')
  })

  it('detects update when check-btn clicked', async () => {
    const wrapper = mount(Upgrade, { global: { stubs: globalStubs } })
    await flushPromises()
    await wrapper.find('[data-test="check-btn"]').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('0.3.0')
  })
})
