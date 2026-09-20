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
  it('管理员进入页面即检查缓存版本并显示更新圆点', async () => {
    vi.mocked(read).mockResolvedValue({ ...base, available: true, release: { version: 'v2.0.0' } })
    user.value = { role: 'admin' }
    const wrapper = mount()
    await flushPromises()
    expect(read).toHaveBeenCalledWith('/core/upgrade/', { check: '1' })
    expect(wrapper.find('[aria-label="有新版本"]').exists()).toBe(true)
    wrapper.unmount()
  })
  it('容器下载不要求停机确认；等待重启持久显示，确认后才调用重启接口', async () => {
    const ready = { ...base, execution: 'container', available: true, runner: { execution: 'container' }, release: { version: 'v2.0.0' } }
    vi.mocked(read).mockResolvedValue(ready)
    vi.mocked(write).mockResolvedValue({ id: 7, status: 'ready', target: 'v2.0.0', need_restart: true })
    user.value = { role: 'admin' }
    const wrapper = mount()
    await flushPromises()
    await wrapper.find('.system-upgrade-entry').trigger('click')
    await flushPromises()
    expect(wrapper.findComponent(ElCheckbox).exists()).toBe(false)
    await wrapper.findAll('button').find(button => button.text() === '立即更新')!.trigger('click')
    await flushPromises()
    expect(write).toHaveBeenCalledWith('/core/upgrade/', { target: 'v2.0.0', confirmed: true }, expect.any(String))
    expect(wrapper.find('[aria-label="等待重启"]').text()).toContain('当前仍运行 v1.1.0')
    const restart = () => wrapper.findAll('button').find(button => button.text() === '重启服务')!
    expect(restart().attributes('disabled')).toBeDefined()
    wrapper.findComponent(ElCheckbox).vm.$emit('update:modelValue', true)
    await flushPromises()
    vi.mocked(write).mockResolvedValue({ id: 7, status: 'restarting', target: 'v2.0.0', need_restart: false })
    await restart().trigger('click')
    await flushPromises()
    expect(write).toHaveBeenLastCalledWith('/core/upgrade/restart/', { id: 7, confirmed: true }, expect.any(String))
    expect(wrapper.text()).toContain('重启生效中')
    wrapper.unmount()
  })
  it('刷新页面可恢复待重启；心跳过期不能重启，也不受版本检查失败影响', async () => {
    vi.useFakeTimers()
    const ready = { ...base, execution: 'container', runner: { execution: 'container' }, check_error: '发布网络暂不可用',
      job: { id: 7, status: 'ready', target: 'v2.0.0', need_restart: true } }
    vi.mocked(read).mockResolvedValue(ready)
    user.value = { role: 'admin' }
    const wrapper = mount()
    await flushPromises()
    await wrapper.find('.system-upgrade-entry').trigger('click')
    await flushPromises()
    wrapper.findComponent(ElCheckbox).vm.$emit('update:modelValue', true)
    await flushPromises()
    const restart = () => wrapper.findAll('button').find(button => button.text() === '重启服务')!
    expect(restart().attributes('disabled')).toBeUndefined()
    await vi.advanceTimersByTimeAsync(3000)
    expect(restart().attributes('disabled')).toBeUndefined()
    vi.mocked(read).mockResolvedValue({ ...ready, runner: null })
    await vi.advanceTimersByTimeAsync(3000)
    expect(restart().attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('等待升级服务连接')
    expect(write).not.toHaveBeenCalled()
    wrapper.unmount()
  })
  it('Compose 容器内执行器就绪时不要求安装宿主机服务', async () => {
    vi.mocked(read).mockResolvedValue({ ...base, execution: 'container', runner: { execution: 'container', mode: 'native', platform: 'linux' } })
    user.value = { role: 'admin' }
    const wrapper = mount()
    await flushPromises()
    await wrapper.find('.system-upgrade-entry').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('容器内升级已就绪')
    expect(wrapper.text()).not.toContain('原生部署执行器')
    expect(wrapper.text()).not.toContain('网页一键升级未启用')
    expect(wrapper.text()).not.toContain('宿主机升级执行器未连接')
    wrapper.unmount()
  })
  it('检查失败保留上次说明，但轮询不能消除警告或恢复升级按钮', async () => {
    vi.useFakeTimers()
    const release = { version: 'v2.0.0', notes: '上次说明' }
    vi.mocked(read).mockResolvedValue({ ...base, available: true, runner: { mode: 'docker' }, release })
    user.value = { role: 'admin' }
    const wrapper = mount()
    await flushPromises()
    await wrapper.find('.system-upgrade-entry').trigger('click')
    await flushPromises()
    vi.mocked(read).mockResolvedValue({ ...base, release, available: false, check_error: '网络检查失败' })
    await wrapper.findAll('button').find(button => button.text() === '检查新版本')!.trigger('click')
    await flushPromises()
    expect(read).toHaveBeenLastCalledWith('/core/upgrade/', { check: '1', force: '1' })
    vi.mocked(read).mockResolvedValue(base)
    await vi.advanceTimersByTimeAsync(3000)
    expect(wrapper.text()).toContain('网络检查失败')
    expect(wrapper.text()).not.toContain('当前已是最新版本')
    expect(wrapper.text()).toContain('上次说明')
    expect(wrapper.findComponent(ElCheckbox).exists()).toBe(false)
    wrapper.unmount()
  })
  it('目标变化需要重新确认，失去连接后不能使用旧心跳提交', async () => {
    vi.useFakeTimers()
    const ready = { ...base, available: true, runner: { mode: 'docker' }, release: { version: 'v2.0.0' } }
    vi.mocked(read).mockResolvedValue(ready)
    user.value = { role: 'admin' }
    const wrapper = mount()
    await flushPromises()
    await wrapper.find('.system-upgrade-entry').trigger('click')
    await flushPromises()
    wrapper.findComponent(ElCheckbox).vm.$emit('update:modelValue', true)
    await flushPromises()
    vi.mocked(read).mockResolvedValue({ ...ready, release: { version: 'v2.0.1' } })
    await wrapper.findAll('button').find(button => button.text() === '检查新版本')!.trigger('click')
    await flushPromises()
    const submit = () => wrapper.findAll('button').find(button => button.text() === '备份并升级')!
    expect(submit().attributes('disabled')).toBeDefined()
    wrapper.findComponent(ElCheckbox).vm.$emit('update:modelValue', true)
    await flushPromises()
    vi.mocked(read).mockRejectedValue(new Error('offline'))
    await vi.advanceTimersByTimeAsync(3000)
    expect(submit().attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('连接中断')
    expect(write).not.toHaveBeenCalled()
    wrapper.unmount()
  })
  it('成功且运行版本已达标时提供刷新，手动部署方式可切换', async () => {
    vi.mocked(read).mockResolvedValue({ ...base, job: { status: 'succeeded', target: 'v1.1.0' } })
    user.value = { role: 'admin' }
    const wrapper = mount()
    await flushPromises()
    await wrapper.find('.system-upgrade-entry').trigger('click')
    await flushPromises()
    expect(wrapper.find('[aria-label="升级成功"]').text()).toContain('刷新页面')
    await wrapper.findAll('button').find(button => button.text() === '原生部署')!.trigger('click')
    expect(wrapper.find('.upgrade-manual').text()).toContain('systemd')
    expect(wrapper.find('.upgrade-manual').text()).not.toContain('镜像 digest')
    wrapper.unmount()
  })
  it('未配置可选升级服务时不报断连故障，仍可查看版本', async () => {
    vi.mocked(read).mockResolvedValue({ ...base, configured: false })
    user.value = { role: 'admin' }
    const wrapper = mount()
    await flushPromises()
    await wrapper.find('.system-upgrade-entry').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('网页一键升级未启用')
    expect(wrapper.text()).not.toContain('宿主机升级执行器未连接')
    expect(wrapper.findAll('button').find(button => button.text() === '备份并升级')?.attributes('disabled')).toBeDefined()
    expect(write).not.toHaveBeenCalled()
    wrapper.unmount()
  })
  it.each(['1.8.7', '1.8.8', '1.10.0'])('当前 %s 时将旧失败折叠为历史，不篡改任务', async current => {
    vi.mocked(read).mockResolvedValue({ ...base, current, job: { status: 'failed', target: 'v1.8.7', detail: '旧失败原因' } })
    user.value = { role: 'admin' }
    const wrapper = mount()
    await flushPromises()
    await wrapper.find('.system-upgrade-entry').trigger('click')
    await flushPromises()
    expect(wrapper.find('.upgrade-history').attributes('open')).toBeUndefined()
    expect(wrapper.text()).toContain('历史升级记录')
    expect(wrapper.text()).not.toContain('本次自动升级未完成')
    expect(wrapper.find('[aria-label="升级进度"]').exists()).toBe(false)
    expect(write).not.toHaveBeenCalled()
    wrapper.unmount()
  })
  it('尚未达到目标的失败继续显示，版本按数值比较', async () => {
    vi.mocked(read).mockResolvedValue({ ...base, current: '1.8.8', job: { status: 'failed', target: 'v1.10.0', detail: '安装失败' } })
    user.value = { role: 'admin' }
    const wrapper = mount()
    await flushPromises()
    await wrapper.find('.system-upgrade-entry').trigger('click')
    await flushPromises()
    expect(wrapper.find('.upgrade-history').exists()).toBe(false)
    expect(wrapper.text()).toContain('本次自动升级未完成')
    wrapper.unmount()
  })
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
