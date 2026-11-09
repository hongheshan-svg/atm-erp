import { beforeEach, expect, it, vi } from 'vitest'
import { shallowMount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import ProjectTaskSupervisors from './ProjectTaskSupervisors.vue'
import { all } from '../api'
import { user } from '../session'
vi.mock('../api', () => ({ all: vi.fn() }))
const project = { id: 1, manager: 2, manager_name: '项目经理', members: [3], can_manage: true, status: 'active', task_supervisors: { mechanical: 3 }, supervisor_revision: 2 }
beforeEach(() => {
  vi.resetAllMocks(); user.value = { id: 2, roles: ['manager'] }
  vi.mocked(all).mockResolvedValue([{ id: 2, roles: ['manager'], display_name: '项目经理' }, { id: 3, roles: ['member'], display_name: '机械主管' }, { id: 4, roles: ['purchaser'], display_name: '其他项目人员' }])
})
it('固定专业选择限制项目成员，提交版本和说明，未指定由经理代管', async () => {
  const wrapper = shallowMount(ProjectTaskSupervisors, { props: { project }, global: { plugins: [ElementPlus], renderStubDefaultSlot: true } })
  await flushPromises()
  expect(wrapper.text()).toContain('机械主管')
  expect(wrapper.text()).toContain('项目经理（项目经理代管）')
  wrapper.findComponent({ name: 'ElButton' }).vm.$emit('click')
  await flushPromises()
  const command = wrapper.findComponent({ name: 'ActionDialog' }).props('command')
  await wrapper.setProps({ project: { ...project, supervisor_revision: 3 } })
  expect(command.fields[0].options.map((option: any) => option.value)).toEqual([2, 3])
  expect(command.prepare({ mechanical: 3, reason: '确认分工' })).toEqual({ supervisors: { mechanical: 3, electrical: null, purchasing: null, production: null, delivery: null }, expected_revision: 2, reason: '确认分工' })
  wrapper.unmount()
})
it('普通员工可查看主管但不能设置', async () => {
  user.value = { id: 3, roles: ['member'] }
  const wrapper = shallowMount(ProjectTaskSupervisors, { props: { project: { ...project, can_manage: false } }, global: { plugins: [ElementPlus], renderStubDefaultSlot: true } })
  await flushPromises()
  expect(wrapper.findComponent({ name: 'ElButton' }).exists()).toBe(false)
  expect(wrapper.text()).toContain('机械主管')
  wrapper.unmount()
})
