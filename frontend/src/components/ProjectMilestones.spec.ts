import { beforeEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import ProjectMilestones from './ProjectMilestones.vue'
import { read } from '../api'
import { milestoneTemplateCommand } from '../modules/milestones'
vi.mock('../api', () => ({ read: vi.fn() }))
vi.mock('../modules/milestones', async importOriginal => ({
  ...(await importOriginal<typeof import('../modules/milestones')>()),
  milestoneTemplateCommand: vi.fn(async () => ({ title: '补充', path: '', fields: [] })),
}))
const stage = (key: string, label: string, extra = {}) => ({ key, label, total: 0, done: 0, overdue: 0, ...extra })
const summary = (extra = {}) => ({
  stages: [
    stage('design', '设计阶段', { total: 7, done: 7 }),
    stage('purchase', '采购阶段'),
    stage('assembly', '装配阶段', { total: 2, done: 1, overdue: 1 }),
    stage('test', '调试阶段'),
    stage('shipping', '发货阶段', { shipped: 2, equipment: 2 }),
    stage('site', '客户终验收阶段', { total: 4, done: 4 }),
  ],
  milestones: 20, missing: 0, can_generate: true, ...extra,
})
function render(phase = '') {
  return mount(ProjectMilestones, { props: { projectId: 7, revision: 1, phase }, global: { plugins: [ElementPlus], stubs: { ActionDialog: true } } })
}
beforeEach(() => { vi.clearAllMocks(); vi.mocked(read).mockResolvedValue(summary()) })
it('阶段卡与任务列表同口径，发货按实际交付显示，逾期标出', async () => {
  const wrapper = render(); await flushPromises()
  const cards = wrapper.findAll('.phase-card').map(card => card.text())
  expect(cards).toHaveLength(6)
  expect(cards[0]).toContain('7 / 7')
  expect(cards[2]).toContain('1 项逾期')
  expect(cards[4]).toContain('已发货 2 / 2 台')
  expect(cards[5]).toContain('4 / 4')
  expect(cards[1]).toContain('未安排')
})
it('节点已全部生成时不再打开 0 行的生成对话框', async () => {
  const wrapper = render(); await flushPromises()
  expect(wrapper.text()).toContain('节点已全部生成')
  expect(wrapper.findAll('button').some(button => button.text().includes('里程碑'))).toBe(false)
  expect(milestoneTemplateCommand).not.toHaveBeenCalled()
})
it('缺节点时按钮写明缺几个，首次生成仍是主按钮', async () => {
  vi.mocked(read).mockResolvedValue(summary({ missing: 3 }))
  const wrapper = render(); await flushPromises()
  const supplement = wrapper.findAll('button').find(button => button.text() === '补充里程碑节点（缺 3 个）')!
  await supplement.trigger('click'); await flushPromises()
  expect(milestoneTemplateCommand).toHaveBeenCalledWith(7)
  vi.mocked(read).mockResolvedValue(summary({ milestones: 0, missing: 20 }))
  const first = render(); await flushPromises()
  expect(first.findAll('button').some(button => button.text() === '一键生成里程碑')).toBe(true)
})
it('「全部」常驻并清除阶段筛选', async () => {
  const wrapper = render('assembly'); await flushPromises()
  const all = wrapper.get('[aria-label="查看全部阶段"]')
  expect(all.attributes('aria-pressed')).toBe('false')
  await all.trigger('click')
  expect(wrapper.emitted('phase')).toEqual([['']])
  await wrapper.findAll('.phase-card')[2]!.trigger('click')
  expect(wrapper.emitted('phase')!.at(-1)).toEqual([''])
  await wrapper.findAll('.phase-card')[1]!.trigger('click')
  expect(wrapper.emitted('phase')!.at(-1)).toEqual(['purchase'])
})
