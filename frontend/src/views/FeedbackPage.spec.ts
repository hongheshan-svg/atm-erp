import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import FeedbackPage from './FeedbackPage.vue'
import { feedbackPage } from '../api/feedback'
import { user } from '../session'
import { read, write } from '../api'

vi.mock('../api', () => ({ read: vi.fn(), write: vi.fn() }))
const route = { query: {} as Record<string, string> }
vi.mock('vue-router', async (original) => ({ ...(await original<typeof import('vue-router')>()), useRoute: () => route }))

const item = (id: number, mine: boolean, state = 'open') => ({
  id, category: 'bug', title: `问题${id}`, issue_number: 100 + id, issue_url: `https://github.com/hongheshan-svg/atm-erp/issues/${100 + id}`,
  state, submitter: mine ? '我' : '同事', mine, created_at: '2026-11-13T04:00:00Z',
})
const listing = (enabled = true) => ({ enabled, issues_url: 'https://github.com/hongheshan-svg/atm-erp/issues', results: [item(1, true, 'completed'), item(2, false)] })
const stubs = {
  ElButton: { props: ['disabled', 'loading', 'nativeType'], template: '<button :type="nativeType || \'button\'" :disabled="disabled"><slot /></button>' },
  ElAlert: { props: ['title'], template: '<p class="alert">{{ title }}<slot /></p>' },
}
const render = () => mount(FeedbackPage, { global: { stubs } })
async function fill(wrapper: ReturnType<typeof render>) {
  await wrapper.find('#feedback-title').setValue('收货后库存没变')
  await wrapper.find('#feedback-description').setValue('数量不对')
}
afterEach(() => { vi.clearAllMocks(); user.value = null; route.query = {} })

describe('问题反馈页面', () => {
  it('列出全部反馈并可只看自己提交的，状态显示中文', async () => {
    vi.mocked(read).mockResolvedValue(listing())
    user.value = { role: 'purchaser' }
    const wrapper = render()
    await flushPromises()
    expect(read).toHaveBeenCalledWith('/core/feedback/')
    expect(read).not.toHaveBeenCalledWith('/core/feedback/settings/')
    expect(wrapper.findAll('.feedback-list li')).toHaveLength(2)
    expect(wrapper.text()).toContain('已解决')
    expect(wrapper.text()).toContain('处理中')
    expect(wrapper.find('[aria-label="GitHub 连接"]').exists()).toBe(false)
    await wrapper.find('.feedback-mine input').setValue(true)
    expect(wrapper.findAll('.feedback-list li')).toHaveLength(1)
    expect(wrapper.find('.feedback-list a').attributes('href')).toContain('/issues/101')
  })

  it('未配置 GitHub 连接时提示并禁止提交', async () => {
    vi.mocked(read).mockResolvedValue(listing(false))
    user.value = { role: 'member' }
    const wrapper = render()
    await flushPromises()
    await fill(wrapper)
    expect(wrapper.text()).toContain('管理员尚未配置 GitHub 连接')
    expect(wrapper.find('button[type="submit"]').attributes('disabled')).toBeDefined()
  })

  it('带上来源页面与错误编号提交；失败保留内容和操作标识，成功后清空', async () => {
    route.query = { from: '/purchases?resource=purchases&search=客户A', request_id: 'req-9' }
    vi.mocked(read).mockResolvedValue(listing())
    user.value = { role: 'member' }
    const wrapper = render()
    await flushPromises()
    expect((wrapper.find('#feedback-page').element as HTMLInputElement).value).toBe('/purchases?resource=purchases')
    await fill(wrapper)
    vi.mocked(write).mockRejectedValueOnce(new Error('暂时无法连接 GitHub，内容未提交，请稍后重试。'))
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(wrapper.text()).toContain('内容未提交')
    expect((wrapper.find('#feedback-title').element as HTMLInputElement).value).toBe('收货后库存没变')
    const [path, body, key] = vi.mocked(write).mock.calls[0]!
    expect(path).toBe('/core/feedback/')
    expect(body).toMatchObject({ category: 'bug', title: '收货后库存没变', description: '数量不对', page: '/purchases?resource=purchases', request_id: 'req-9' })
    expect((body as { client: string }).client).toContain('×')
    vi.mocked(write).mockResolvedValueOnce(item(3, true))
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(vi.mocked(write).mock.calls[1]![2]).toBe(key)
    expect(wrapper.find('[role="status"]').text()).toContain('#103')
    expect((wrapper.find('#feedback-title').element as HTMLInputElement).value).toBe('')
    expect((wrapper.find('#feedback-page').element as HTMLInputElement).value).toBe('')
  })

  it('管理员可保存或停用令牌，令牌不回显', async () => {
    vi.mocked(read).mockImplementation(async (path: string) => (path === '/core/feedback/settings/' ? { configured: false, repository: 'x' } : listing(false)))
    user.value = { role: 'admin' }
    const wrapper = render()
    await flushPromises()
    const section = wrapper.find('[aria-label="GitHub 连接"]')
    expect(section.text()).toContain('未配置')
    await section.find('input[type="password"]').setValue(' github_pat_abc ')
    vi.mocked(write).mockResolvedValueOnce({ configured: true, repository: 'x' })
    await section.findAll('button').find(button => button.text() === '保存令牌')!.trigger('click')
    await flushPromises()
    expect(write).toHaveBeenCalledWith('/core/feedback/settings/', { token: 'github_pat_abc' }, expect.any(String))
    expect(section.text()).toContain('已配置')
    expect((section.find('input[type="password"]').element as HTMLInputElement).value).toBe('')
    vi.mocked(write).mockResolvedValueOnce({ configured: false, repository: 'x' })
    await section.findAll('button').find(button => button.text() === '停用')!.trigger('click')
    await flushPromises()
    expect(vi.mocked(write).mock.calls[1]![1]).toEqual({ token: '' })
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
