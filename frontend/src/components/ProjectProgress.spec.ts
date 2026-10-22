import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import ProjectProgress from './ProjectProgress.vue'
import { read } from '../api'

vi.mock('../api', () => ({ read: vi.fn() }))
const record = {
  id: 8, resource: 'purchases', title: 'PO-8', status_label: '待批准', pending: true,
  due_date: '2026-10-20', due_label: '交货日期', overdue: true,
  handlers: [{ id: 2, name: '张经理', active: true }], handler_label: '可审批人员',
  hint: '由其他有权限的人员审批。', record: { status: 'submitted' }, path: null,
}
const result = (changes = {}) => ({
  project: { code: 'PRJ-7', name: '自动装配线', manager: { name: '李经理' } },
  groups: [{ key: 'tasks', label: '任务执行', open: 0 }, { key: 'purchases', label: '采购到货', open: 1 }],
  count: 1, page: 1, results: [record], checked_at: '2026-10-22T10:00:00Z', ...changes,
})
function render() {
  return mount(ProjectProgress, { props: { projectId: 7, revision: 1 }, global: {
    plugins: [ElementPlus], stubs: { RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } },
  } })
}
const button = (wrapper: ReturnType<typeof render>, name: string) => wrapper.findAll('button').find(item => item.text().includes(name))!
beforeEach(() => { vi.clearAllMocks(); vi.mocked(read).mockResolvedValue(result()) })

describe('流程相关人员进度展示', () => {
  it('显示姓名、审批候选、期限和完整节点，受限人员没有原单入口', async () => {
    const wrapper = render(); await flushPromises()
    expect(wrapper.text()).toContain('项目负责人：李经理')
    expect(wrapper.text()).toContain('张经理')
    expect(wrapper.text()).toContain('可审批人员')
    expect(wrapper.text()).toContain('已逾期')
    expect(wrapper.find('a').exists()).toBe(false)
    await wrapper.get('summary').trigger('click')
    expect(wrapper.get('.process-current').text()).toContain('待批准')
    wrapper.unmount()
  })
  it('流程分类与全部记录分别请求，并提供有权限的原单入口', async () => {
    const wrapper = render(); await flushPromises()
    vi.mocked(read).mockResolvedValue(result({ results: [{ ...record, path: '/projects/7?tab=purchases' }] }))
    await button(wrapper, '采购到货').trigger('click'); await flushPromises()
    expect(read).toHaveBeenLastCalledWith('/business/projects/7/progress/', expect.objectContaining({ category: 'purchases', state: 'open', page: 1 }))
    expect(wrapper.get('a').attributes('href')).toBe('/projects/7?tab=purchases')
    await button(wrapper, '全部记录').trigger('click'); await flushPromises()
    expect(read).toHaveBeenLastCalledWith('/business/projects/7/progress/', expect.objectContaining({ category: 'purchases', state: 'all', page: 1 }))
    wrapper.unmount()
  })
  it('忽略迟到的前一项目响应，防止串项目展示', async () => {
    let resolve!: (value: ReturnType<typeof result>) => void
    vi.mocked(read).mockImplementationOnce(() => new Promise(done => { resolve = done }))
    const wrapper = render()
    vi.mocked(read).mockResolvedValue(result({ results: [{ ...record, title: '当前项目' }] }))
    await wrapper.setProps({ projectId: 9 }); await flushPromises()
    resolve(result({ results: [{ ...record, title: '前一项目' }] })); await flushPromises()
    expect(wrapper.text()).toContain('当前项目')
    expect(wrapper.text()).not.toContain('前一项目')
    wrapper.unmount()
  })
  it('失败后清除旧记录，可重试，刷新后反映最新状态', async () => {
    const wrapper = render(); await flushPromises()
    vi.mocked(read).mockRejectedValueOnce(new Error('进度暂不可用'))
    await button(wrapper, '刷新进度').trigger('click'); await flushPromises()
    expect(wrapper.findAll('article')).toHaveLength(0)
    expect(wrapper.text()).toContain('进度暂不可用')
    vi.mocked(read).mockResolvedValue(result({ count: 0, results: [] }))
    await button(wrapper, '重新加载进度').trigger('click'); await flushPromises()
    expect(wrapper.text()).toContain('本类暂无待跟进事项')
    wrapper.unmount()
  })
  it('分页不漏项，切换分类返回第一页', async () => {
    vi.mocked(read).mockResolvedValue(result({ count: 21 }))
    const wrapper = render(); await flushPromises()
    vi.mocked(read).mockResolvedValue(result({ count: 21, page: 2 }))
    await button(wrapper, '下一页').trigger('click'); await flushPromises()
    expect(read).toHaveBeenLastCalledWith(expect.anything(), expect.objectContaining({ page: 2 }))
    expect(button(wrapper, '下一页').attributes('disabled')).toBeDefined()
    await button(wrapper, '采购到货').trigger('click'); await flushPromises()
    expect(read).toHaveBeenLastCalledWith(expect.anything(), expect.objectContaining({ page: 1 }))
    wrapper.unmount()
  })
  it('只复制跟进文字、不发送通知；复制失败保留手动复制提示', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } })
    const wrapper = render(); await flushPromises()
    await button(wrapper, '复制跟进信息').trigger('click'); await flushPromises()
    expect(writeText).toHaveBeenCalledWith(expect.stringContaining('可审批人员：张经理'))
    expect(wrapper.text()).toContain('已复制')
    writeText.mockRejectedValueOnce(new Error('不可用'))
    await button(wrapper, '复制跟进信息').trigger('click'); await flushPromises()
    expect(wrapper.text()).toContain('请选中卡片上的进度文字复制')
    wrapper.unmount()
  })
  it('待检与预付款状态在流程图中同样显示，不依赖金额字段', async () => {
    vi.mocked(read).mockResolvedValue(result({ results: [{ ...record, resource: 'entries', status_label: '预付款待核准', record: { progress_status: 'pending' }, overdue: false, due_date: null, agreed_date: '2026-10-20' }] }))
    const wrapper = render(); await flushPromises()
    expect(wrapper.get('.process-current').text()).toContain('预付款待核准')
    expect(wrapper.text()).toContain('实际付款期限尚未起算')
    expect(wrapper.text()).not.toContain('已逾期')
    wrapper.unmount()
  })
})
