import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import MainLayout from '../MainLayout.vue'

const { loadCompanyConfig, logout, routerPush } = vi.hoisted(() => ({
  loadCompanyConfig: vi.fn().mockResolvedValue(undefined),
  logout: vi.fn(),
  routerPush: vi.fn()
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: routerPush })
}))

vi.mock('@/stores/user', () => ({
  useUserStore: () => ({
    profileReady: true,
    userInfo: { username: 'admin' },
    logout
  })
}))

vi.mock('@/stores/permission', () => ({
  usePermissionStore: () => ({ menus: [] })
}))

vi.mock('@/stores/companyConfig', () => ({
  useCompanyConfig: () => ({
    companyName: 'Test Company',
    companyShortName: 'ERP',
    loadCompanyConfig
  })
}))

vi.mock('@/utils/theme', () => ({
  useTheme: () => ({
    isDark: false,
    toggleTheme: vi.fn()
  })
}))

const setViewportWidth = (width: number) => {
  Object.defineProperty(window, 'innerWidth', {
    configurable: true,
    writable: true,
    value: width
  })
  window.dispatchEvent(new Event('resize'))
}

const mountLayout = () => mount(MainLayout, {
  global: {
    mocks: {
      $route: { path: '/dashboard', meta: { title: '工作台' } },
      $router: { push: routerPush }
    },
    stubs: {
      ElContainer: { template: '<div><slot /></div>' },
      ElAside: {
        props: ['width'],
        template: '<aside :style="{ width }"><slot /></aside>'
      },
      ElHeader: { template: '<header><slot /></header>' },
      ElMain: { template: '<main><slot /></main>' },
      ElFooter: { template: '<footer><slot /></footer>' },
      ElBreadcrumb: { template: '<nav data-testid="breadcrumbs"><slot /></nav>' },
      ElBreadcrumbItem: { template: '<span><slot /></span>' },
      ElDropdown: { template: '<div><slot /><slot name="dropdown" /></div>' },
      ElDropdownMenu: { template: '<div><slot /></div>' },
      ElDropdownItem: { template: '<button><slot /></button>' },
      ElAvatar: { template: '<span><slot /></span>' },
      ElTooltip: { template: '<span><slot /></span>' },
      ElMenu: { template: '<nav><slot /></nav>' },
      ElIcon: { template: '<i><slot /></i>' },
      RouterView: { template: '<section data-testid="route-view" />' },
      DynamicMenu: true,
      GlobalSearch: true,
      VersionBadge: true,
      Fold: true,
      Expand: true,
      Menu: true,
      User: true,
      Lock: true,
      SwitchButton: true,
      FullScreen: true,
      ArrowDown: true,
      Moon: true,
      Sunny: true
    }
  }
})

describe('MainLayout responsive sidebar', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    setViewportWidth(1024)
  })

  it('hides the sidebar by default on mobile and opens it as an overlay', async () => {
    setViewportWidth(390)
    const wrapper = mountLayout()
    await flushPromises()

    const sidebar = wrapper.get('.sidebar')
    const main = wrapper.get('.main-container')

    expect(sidebar.attributes('style')).toContain('display: none')
    expect(main.attributes('style')).toContain('width: 100%')
    expect(wrapper.find('[data-testid="breadcrumbs"]').exists()).toBe(false)

    await wrapper.get('.mobile-menu-trigger').trigger('click')

    expect(wrapper.get('.sidebar').attributes('style')).not.toContain('display: none')
    expect(wrapper.get('.sidebar').classes()).toContain('is-mobile-open')
    expect(wrapper.find('.sidebar-backdrop').exists()).toBe(true)

    await wrapper.get('.sidebar-backdrop').trigger('click')
    expect(wrapper.get('.sidebar').attributes('style')).toContain('display: none')
  })

  it('keeps the existing expanded and collapsed widths on desktop', async () => {
    setViewportWidth(1280)
    const wrapper = mountLayout()
    await flushPromises()

    expect(wrapper.get('.sidebar').attributes('style')).not.toContain('display: none')
    expect(wrapper.get('.sidebar').attributes('style')).toContain('width: 240px')
    expect(wrapper.find('.mobile-menu-trigger').exists()).toBe(false)
    expect(wrapper.find('[data-testid="breadcrumbs"]').exists()).toBe(true)

    await wrapper.get('.sidebar-footer').trigger('click')

    expect(wrapper.get('.sidebar').attributes('style')).toContain('width: 64px')
  })

  it('opens an expanded mobile drawer after the desktop sidebar was collapsed', async () => {
    setViewportWidth(1280)
    const wrapper = mountLayout()
    await flushPromises()
    await wrapper.get('.sidebar-footer').trigger('click')
    expect(wrapper.get('.sidebar').attributes('style')).toContain('width: 64px')

    setViewportWidth(390)
    await wrapper.vm.$nextTick()
    await wrapper.get('.mobile-menu-trigger').trigger('click')

    expect(wrapper.get('.sidebar').attributes('style')).toContain('width: 240px')
    expect(wrapper.find('.logo-meta').exists()).toBe(true)
    expect(wrapper.find('.collapse-label').exists()).toBe(true)
  })
})
