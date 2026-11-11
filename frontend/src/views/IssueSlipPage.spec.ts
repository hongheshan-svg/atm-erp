import { expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import IssueSlipPage from './IssueSlipPage.vue'
import { read } from '../api'

vi.mock('vue-router', () => ({ useRoute: () => ({ params: { id: '5' } }) }))
vi.mock('../api', () => ({ read: vi.fn() }))

it('按领料单号读取服务端单据并打印：单头、逐行明细与签字栏', async () => {
  vi.mocked(read).mockResolvedValue({
    id: 5, code: 'LL000005', company_name: '示例自动化', project: 7, project_code: 'ATM2601', project_name: '上料线',
    task: 3, task_title: '现场换件', reason: '售后领料', created_by_name: '王仓管', created_at: '2026-11-11T02:30:00Z',
    lines: [
      { id: 21, item_code: 'M-1', item_name: '伺服电机', specification: '750W', brand: '安川', drawing_number: '', drawing_revision: '', location: '主仓', quantity: '2.000', unit: '台', remark: '' },
      { id: 22, item_code: 'M-2', item_name: '气缸', specification: '', brand: '', drawing_number: 'D-9', drawing_revision: 'B', location: '二号仓', quantity: '1.500', unit: '个', remark: '夹爪' },
    ],
  })
  const print = vi.spyOn(window, 'print').mockImplementation(() => {})
  const wrapper = mount(IssueSlipPage, { global: { plugins: [ElementPlus], stubs: { RouterLink: { template: '<a><slot /></a>' } } } })
  await flushPromises()
  expect(read).toHaveBeenCalledWith('/business/issue-slips/5/')
  const paper = wrapper.find('article.slip-paper')
  expect(paper.text()).toContain('示例自动化')
  for (const text of ['LL000005', 'ATM2601 · 上料线', '现场换件', '售后领料', '王仓管', '2 行']) expect(paper.text()).toContain(text)
  const rows = paper.findAll('tbody tr')
  expect(rows).toHaveLength(2)
  expect(rows[0]!.text()).toContain('750W / 安川')
  expect(rows[1]!.text()).toContain('图号 D-9；版本 B')
  expect(rows[1]!.text()).toContain('1.5')
  expect(rows[1]!.text()).toContain('夹爪')
  expect(paper.text()).toContain('领料人签字')
  expect(paper.text()).toContain('仓管签字')
  await wrapper.findAllComponents({ name: 'ElButton' }).find(button => button.text().includes('打印'))!.trigger('click')
  expect(print).toHaveBeenCalled()
  wrapper.unmount()
})
