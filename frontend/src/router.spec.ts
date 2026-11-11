import { afterEach, expect, it, vi } from 'vitest'
import { router } from './router'
import { user } from './session'
import { actionNames } from './modules/purchases'

// 页面组件按需加载；这里只验证路由守卫，不渲染页面。
vi.mock('./views/PurchaseContractPage.vue', () => ({ default: { template: '<div />' } }))
vi.mock('./views/PurchasesPage.vue', () => ({ default: { template: '<div />' } }))
vi.mock('./views/WorkbenchPage.vue', () => ({ default: { template: '<div />' } }))
afterEach(() => { user.value = null; localStorage.clear() })

it.each([
  { roles: ['warehouse'], path: '/workbench', entry: false },
  { roles: ['purchaser'], path: '/purchases/5/contract', entry: true },
  { roles: ['finance'], path: '/purchases/5/contract', entry: true },
  { roles: ['manager'], path: '/purchases/5/contract', entry: true },
  { roles: ['warehouse', 'purchase_manager'], path: '/purchases/5/contract', entry: true },
])('采购合同预览按后端 MONEY_READERS | PURCHASERS 放行，入口与路由一致：$roles', async ({ roles, path, entry }) => {
  localStorage.setItem('access_token', 'token')
  user.value = { id: 3, roles }
  // 每例从工作台出发，避免同一地址的重复导航跳过守卫。
  await router.push('/workbench')
  await router.push('/purchases/5/contract')
  expect(router.currentRoute.value.fullPath).toBe(path)
  expect(actionNames('purchases', { id: 5, status: 'approved' }).includes('预览采购合同')).toBe(entry)
})
