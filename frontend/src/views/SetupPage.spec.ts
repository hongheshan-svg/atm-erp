import { afterEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createMemoryHistory, createRouter } from 'vue-router'
import SetupPage from './SetupPage.vue'
import { read } from '../api'
import { user } from '../session'

vi.mock('../api', () => ({ read: vi.fn(), write: vi.fn() }))
afterEach(() => { vi.resetAllMocks(); user.value = null })

it('安装向导用中文在页面上列出未填项并标红字段，不依赖浏览器气泡', async () => {
  user.value = { id: 1, username: 'admin', display_name: '', roles: ['admin'] }
  vi.mocked(read).mockResolvedValue({ required: true, company: { name: '我的公司', address: '', phone: '' }, codes: [] })
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/setup', component: SetupPage }, { path: '/login', component: { template: '<div />' } }] })
  await router.push('/setup')
  const wrapper = mount(SetupPage, { global: { plugins: [ElementPlus, router] }, attachTo: document.body })
  await flushPromises()
  expect(wrapper.get('form').attributes('novalidate')).toBeDefined()
  expect(wrapper.text()).toContain('初始密码（刚才登录用的密码）')
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  const alert = wrapper.get('[role="alert"]').text()
  expect(alert).toContain('管理员姓名未填写')
  expect(alert).toContain('初始密码未填写')
  const invalid = wrapper.findAll('input[aria-invalid]')
  expect(invalid.length).toBeGreaterThanOrEqual(4)
  expect(document.activeElement).toBe(invalid[0]!.element)
  await invalid[0]!.setValue('张三')
  expect(invalid[0]!.attributes('aria-invalid')).toBeUndefined()
  expect(wrapper.find('.setup-steps li.active').text()).toContain('管理员账号')
  wrapper.unmount()
})
