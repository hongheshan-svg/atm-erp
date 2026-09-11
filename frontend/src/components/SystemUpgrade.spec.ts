import { flushPromises, shallowMount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ElCheckbox } from 'element-plus'
import SystemUpgrade from './SystemUpgrade.vue'
import { user } from '../session'
import { read, write } from '../api'

vi.mock('../api', () => ({ read: vi.fn(), write: vi.fn() }))
const base = { current: '1.1.0', configured: true, runner: null, job: null }
const mount = () => shallowMount(SystemUpgrade, { global: { stubs: {
  ElDialog: { props: ['modelValue'], template: '<section v-if="modelValue"><slot /><slot name="footer" /></section>' },
  ElButton: { props: ['disabled'], template: '<button :disabled="disabled"><slot /></button>' },
  ElAlert: { props: ['title'], template: '<p>{{title}}<slot /></p>' },
} } })
afterEach(() => { vi.clearAllMocks(); vi.useRealTimers(); user.value = null })

describe('系统版本与升级', () => {
  it('断连时不把缓存心跳显示为已连接，详细步骤默认折叠', async () => {
    vi.useFakeTimers()
    vi.mocked(read).mockResolvedValue({ ...base, runner: { mode: 'docker', platform: 'macos' }, job: { status: 'downloading', target: 'v1.8.0', detail: '正在构建', created_at: new Date().toISOString() } })
    user.value = { role: 'admin' }
    const wrapper = mount()
    await flushPromises()
    await wrapper.find('.system-upgrade-entry').trigger('click')
    await flushPromises()
    expect(wrapper.find('.upgrade-stage-details').attributes('open')).toBeUndefined()
    vi.mocked(read).mockRejectedValue(new Error('offline'))
    await vi.advanceTimersByTimeAsync(3000)
    await flushPromises()
    expect(wrapper.text()).toContain('正在重新连接')
    expect(wrapper.text()).toContain('上次收到的状态')
    expect(wrapper.text()).not.toContain('执行器已连接')
    expect(wrapper.text()).not.toContain('原系统保持运行')
    wrapper.unmount()
  })
  it('后台服务恢复后自动更新连接状态，无需用户重新检查', async () => {
    vi.useFakeTimers()
    vi.mocked(read).mockResolvedValue(base)
    user.value = { role: 'admin' }
    const wrapper = mount()
    await flushPromises()
    await wrapper.find('.system-upgrade-entry').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('宿主机升级执行器未连接')
    vi.mocked(read).mockResolvedValue({ ...base, runner: { mode: 'docker', platform: 'macos' } })
    await vi.advanceTimersByTimeAsync(3000)
    await flushPromises()
    expect(wrapper.text()).toContain('执行器已连接：macos / Docker')
    expect(wrapper.text()).not.toContain('宿主机升级执行器未连接')
    wrapper.unmount()
  })
  it('显示当前步骤、构建耗时与关闭窗口后的升级状态', async () => {
    vi.mocked(read).mockResolvedValue({ ...base, job: { id: 1, target: 'v1.7.1', status: 'downloading', detail: '正在构建 Docker 镜像 · 已运行 30 秒', created_at: new Date(Date.now() - 30000).toISOString() } })
    user.value = { role: 'admin' }
    const wrapper = mount()
    await flushPromises()
    expect(wrapper.find('.system-upgrade-entry').text()).toContain('升级进行中')
    await wrapper.find('.system-upgrade-entry').trigger('click')
    await flushPromises()
    expect(wrapper.find('[aria-current="step"]').text()).toContain('下载并校验')
    expect(wrapper.text()).toContain('已运行 30 秒')
    expect(wrapper.text()).toContain('关闭窗口后仍会继续升级')
    wrapper.unmount()
  })
  it('非管理员没有入口，也不读取版本管理接口', async () => {
    user.value = { role: 'member' }
    const wrapper = mount()
    await flushPromises()
    expect(wrapper.find('.system-upgrade-entry').exists()).toBe(false)
    expect(read).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('执行器未连接时不能发起升级，检查失败可重试', async () => {
    vi.mocked(read).mockResolvedValue(base)
    user.value = { role: 'admin' }
    const wrapper = mount()
    await flushPromises()
    await wrapper.find('.system-upgrade-entry').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('宿主机升级执行器未连接')
    expect(wrapper.findAll('button').find(button => button.text() === '备份并升级')?.attributes('disabled')).toBeDefined()
    expect(write).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('有新版本且确认停机后才提交，并保留升级任务进度', async () => {
    vi.mocked(read).mockResolvedValue({ ...base, available: true, runner: { mode: 'docker', platform: 'linux' }, release: { version: 'v2.0.0', notes: '改进', url: 'https://github.com/hongheshan-svg/atm-erp/releases/tag/v2.0.0' } })
    vi.mocked(write).mockResolvedValue({ id: 1, target: 'v2.0.0', status: 'queued', detail: '等待执行' })
    user.value = { role: 'admin' }
    const wrapper = mount()
    await flushPromises()
    await wrapper.find('.system-upgrade-entry').trigger('click')
    await flushPromises()
    const submit = () => wrapper.findAll('button').find(button => button.text() === '备份并升级')!
    expect(submit().attributes('disabled')).toBeDefined()
    wrapper.findComponent(ElCheckbox).vm.$emit('update:modelValue', true)
    await flushPromises()
    expect(submit().attributes('disabled')).toBeUndefined()
    await submit().trigger('click')
    await flushPromises()
    expect(write).toHaveBeenCalledWith('/core/upgrade/', { target: 'v2.0.0', confirmed: true }, expect.any(String))
    expect(wrapper.text()).toContain('等待执行')
    expect(submit().attributes('disabled')).toBeDefined()
    wrapper.unmount()
  })
})
