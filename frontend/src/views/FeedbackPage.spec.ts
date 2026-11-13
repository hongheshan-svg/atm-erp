import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import FeedbackPage from './FeedbackPage.vue'
import { checkFiles, feedbackPage } from '../api/feedback'
import { user } from '../session'
import { read, write } from '../api'

vi.mock('../api', () => ({ read: vi.fn(), write: vi.fn() }))
const route = { query: {} as Record<string, string> }
vi.mock('vue-router', async (original) => ({ ...(await original<typeof import('vue-router')>()), useRoute: () => route }))

const item = (id: number, mine: boolean, state = 'open', attachments: unknown[] = []) => ({
  id, category: 'bug', title: `问题${id}`, issue_number: 100 + id, issue_url: `https://github.com/hongheshan-svg/atm-erp-feedback/issues/${100 + id}`,
  state, attachments, submitter: mine ? '我' : '同事', mine, created_at: '2026-11-13T04:00:00Z',
})
const FILE = 'https://github.com/hongheshan-svg/atm-erp-feedback/blob/main/files/a.png?raw=true'
const listing = (enabled = true) => ({
  enabled, limits: { files: 6, file_mb: 10, total_mb: 20 },
  issues_url: 'https://github.com/hongheshan-svg/atm-erp-feedback/issues',
  results: [item(1, true, 'completed', [{ name: 'a.png', url: FILE, image: true }]), item(2, false)],
})
const stubs = {
  ElButton: { props: ['disabled', 'loading', 'nativeType'], template: '<button :type="nativeType || \'button\'" :disabled="disabled"><slot /></button>' },
  ElAlert: { props: ['title'], template: '<p class="alert">{{ title }}<slot /></p>' },
}
const render = () => mount(FeedbackPage, { global: { stubs } })
const png = (name = 'shot.png', size = 10) => new File([new Uint8Array(size)], name, { type: 'image/png' })
async function fill(wrapper: ReturnType<typeof render>) {
  await wrapper.find('#feedback-title').setValue('收货后库存没变')
  await wrapper.find('#feedback-description').setValue('数量不对')
}
async function choose(wrapper: ReturnType<typeof render>, files: File[]) {
  const input = wrapper.find('#feedback-files')
  Object.defineProperty(input.element, 'files', { value: files, configurable: true })
  await input.trigger('change')
}
const submitButton = (wrapper: ReturnType<typeof render>) => wrapper.find('button[type="submit"]')
beforeEach(() => {
  URL.createObjectURL = vi.fn(() => 'blob:preview')
  URL.revokeObjectURL = vi.fn()
})
afterEach(() => { vi.clearAllMocks(); user.value = null; route.query = {} })

describe('问题反馈页面', () => {
  it('列出全部反馈和附件名，可只看自己提交的；私有仓库链接只给管理员', async () => {
    vi.mocked(read).mockResolvedValue(listing())
    user.value = { role: 'purchaser' }
    const wrapper = render()
    await flushPromises()
    expect(read).toHaveBeenCalledWith('/core/feedback/')
    expect(read).not.toHaveBeenCalledWith('/core/feedback/settings/')
    expect(wrapper.findAll('.feedback-list > li')).toHaveLength(2)
    expect(wrapper.text()).toContain('已解决')
    expect(wrapper.text()).toContain('处理中')
    expect(wrapper.text()).toContain('只有系统维护者能看到')
    expect(wrapper.find('.feedback-attachments').text()).toContain('a.png')
    expect(wrapper.findAll('a[href*="github.com"]')).toHaveLength(0)
    expect(wrapper.find('[aria-label="GitHub 连接"]').exists()).toBe(false)
    await wrapper.find('.feedback-mine input').setValue(true)
    expect(wrapper.findAll('.feedback-list > li')).toHaveLength(1)
    expect(wrapper.find('.feedback-title').text()).toContain('#101')

    vi.mocked(read).mockImplementation(async (path: string) =>
      (path === '/core/feedback/settings/' ? { configured: true, repository: 'r' } : listing()))
    user.value = { role: 'admin' }
    const admin = render()
    await flushPromises()
    expect(admin.find('.feedback-attachments a').attributes('href')).toBe(FILE)
    expect(admin.find('.feedback-title a').attributes('href')).toContain('/atm-erp-feedback/issues/101')
    expect(admin.find('a[href="https://github.com/hongheshan-svg/atm-erp-feedback/issues"]').exists()).toBe(true)
  })

  it('未配置 GitHub 连接时提示并禁止提交和选择附件', async () => {
    vi.mocked(read).mockResolvedValue(listing(false))
    user.value = { role: 'member' }
    const wrapper = render()
    await flushPromises()
    await fill(wrapper)
    expect(wrapper.text()).toContain('管理员尚未配置 GitHub 连接')
    expect(submitButton(wrapper).attributes('disabled')).toBeDefined()
    expect(wrapper.find('#feedback-files').attributes('disabled')).toBeDefined()
  })

  it('带上来源页面、错误编号和详细描述提交；失败保留内容和操作标识，成功后清空', async () => {
    route.query = { from: '/purchases?resource=purchases&search=客户A', request_id: 'req-9' }
    vi.mocked(read).mockResolvedValue(listing())
    user.value = { role: 'member' }
    const wrapper = render()
    await flushPromises()
    expect((wrapper.find('#feedback-page').element as HTMLInputElement).value).toBe('/purchases?resource=purchases')
    await fill(wrapper)
    await wrapper.find('#feedback-expected').setValue('库存增加')
    await wrapper.find('#feedback-impact').setValue('blocked')
    await wrapper.find('#feedback-frequency').setValue('always')
    vi.mocked(write).mockRejectedValueOnce(new Error('暂时无法连接 GitHub，内容未提交，请稍后重试。'))
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(wrapper.text()).toContain('内容未提交')
    expect((wrapper.find('#feedback-title').element as HTMLInputElement).value).toBe('收货后库存没变')
    const [path, body, key] = vi.mocked(write).mock.calls[0]!
    expect(path).toBe('/core/feedback/')
    expect(body).toMatchObject({
      category: 'bug', title: '收货后库存没变', description: '数量不对', expected: '库存增加', impact: 'blocked', frequency: 'always',
      page: '/purchases?resource=purchases', request_id: 'req-9',
    })
    expect((body as { client: string }).client).toContain('×')
    vi.mocked(write).mockResolvedValueOnce(item(3, true))
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(vi.mocked(write).mock.calls[1]![2]).toBe(key)
    expect(wrapper.find('[role="status"]').text()).toContain('#103')
    expect(wrapper.find('[role="status"] a').exists()).toBe(false)
    expect((wrapper.find('#feedback-title').element as HTMLInputElement).value).toBe('')
    expect((wrapper.find('#feedback-page').element as HTMLInputElement).value).toBe('')
  })

  it('选择或粘贴截图后预览，可移除，附件随表单上传', async () => {
    vi.mocked(read).mockResolvedValue(listing())
    user.value = { role: 'member' }
    const wrapper = render()
    await flushPromises()
    await fill(wrapper)
    await choose(wrapper, [png(), new File(['x'], '导入.xlsx')])
    await wrapper.find('.feedback-form').trigger('paste', { clipboardData: { files: [png('image.png')] } })
    const names = wrapper.findAll('.feedback-file-name').map(node => node.text())
    expect(names.slice(0, 2)).toEqual(['shot.png', '导入.xlsx'])
    expect(names[2]).toMatch(/^截图-\d{14}\.png$/)
    expect(wrapper.findAll('.feedback-files img')).toHaveLength(2)
    await wrapper.find('[aria-label="移除 导入.xlsx"]').trigger('click')
    expect(submitButton(wrapper).attributes('disabled')).toBeUndefined()
    vi.mocked(write).mockResolvedValueOnce(item(4, true))
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    const form = vi.mocked(write).mock.calls[0]![1] as FormData
    expect(form).toBeInstanceOf(FormData)
    expect((form.getAll('files') as File[]).map(file => file.name)).toEqual(['shot.png', names[2]])
    expect(form.get('title')).toBe('收货后库存没变')
    expect(wrapper.find('.feedback-files').exists()).toBe(false)
    expect(URL.revokeObjectURL).toHaveBeenCalled()
  })

  it('不支持的格式和超限附件在本地就提示', async () => {
    vi.mocked(read).mockResolvedValue(listing())
    user.value = { role: 'member' }
    const wrapper = render()
    await flushPromises()
    await choose(wrapper, [new File(['x'], 'tool.exe')])
    expect(wrapper.find('.field-error').text()).toContain('格式不支持')
    expect(wrapper.find('.feedback-files').exists()).toBe(false)
    expect(checkFiles(Array.from({ length: 7 }, () => png()))).toContain('最多上传 6 个')
    expect(checkFiles([png('big.png', 11 * 1024 * 1024)])).toContain('不能超过 10 MB')
    expect(checkFiles([png('empty.png', 0)])).toContain('空文件')
    expect(checkFiles([png(), new File(['x'], 'a.CSV')])).toBe('')
  })

  it('管理员保存或停用令牌，令牌不回显', async () => {
    const settings = { configured: false, repository: 'hongheshan-svg/atm-erp-feedback' }
    vi.mocked(read).mockImplementation(async (path: string) => (path === '/core/feedback/settings/' ? settings : listing(false)))
    user.value = { role: 'admin' }
    const wrapper = render()
    await flushPromises()
    const section = wrapper.find('[aria-label="GitHub 连接"]')
    expect(section.text()).toContain('hongheshan-svg/atm-erp-feedback')
    expect(section.text()).toContain('Contents：Read and write')
    expect(section.text()).toContain('未配置')
    expect(section.findAll('button').some(button => button.text() === '停用')).toBe(false)
    await section.find('input[aria-label="GitHub 令牌"]').setValue(' github_pat_abc ')
    vi.mocked(write).mockResolvedValueOnce({ ...settings, configured: true })
    await section.findAll('button').find(button => button.text() === '保存')!.trigger('click')
    await flushPromises()
    expect(write).toHaveBeenCalledWith('/core/feedback/settings/', { token: 'github_pat_abc' }, expect.any(String))
    expect(section.text()).toContain('已配置')
    expect((section.find('input[aria-label="GitHub 令牌"]').element as HTMLInputElement).value).toBe('')
    vi.mocked(write).mockResolvedValueOnce(settings)
    await section.findAll('button').find(button => button.text() === '停用')!.trigger('click')
    await flushPromises()
    expect(vi.mocked(write).mock.calls[1]![1]).toEqual({ token: '' })
    expect(vi.mocked(write).mock.calls[1]![2]).not.toBe(vi.mocked(write).mock.calls[0]![2])
  })
})

describe('反馈页面路径', () => {
  it('只保留路径与定位参数，不带搜索词、锚点和反馈页自身', () => {
    expect(feedbackPage('/purchases?resource=purchases&search=客户A#top')).toBe('/purchases?resource=purchases')
    expect(feedbackPage('/inventory?section=stocks&project=all')).toBe('/inventory?section=stocks')
    expect(feedbackPage('/projects/12')).toBe('/projects/12')
    expect(feedbackPage('/feedback?from=/x')).toBe('')
    expect(feedbackPage('https://example.com/x')).toBe('')
    expect(feedbackPage('')).toBe('')
  })
})
