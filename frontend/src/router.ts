import { createRouter, createWebHistory } from 'vue-router'
import { user, loadUser, can, contractReader } from './session'
import { navigation } from './navigation'
import { localStore } from './utils/storage'
export const router = createRouter({
  history: createWebHistory('/erp/'),
  routes: [
    { path: '/login', component: () => import('./views/LoginPage.vue') },
    { path: '/setup', component: () => import('./views/SetupPage.vue') },
    { path: '/', redirect: '/workbench' },
    { path: '/projects/:id', component: () => import('./views/ProjectPage.vue') },
    { path: '/workbench', component: () => import('./views/WorkbenchPage.vue') },
    { path: '/reports', component: () => import('./views/ReportsPage.vue') },
    { path: '/sales', component: () => import('./views/SalesPage.vue') },
    { path: '/projects', component: () => import('./views/ProjectsPage.vue') },
    { path: '/bom', component: () => import('./views/BOMPage.vue') },
    { path: '/purchases', component: () => import('./views/PurchasesPage.vue') },
    // 能看采购单不等于能预览合同（仓管）：路由与「预览采购合同」入口用同一判定，不让人进页面再被服务端拒绝。
    { path: '/purchases/:id/contract', component: () => import('./views/PurchaseContractPage.vue'), meta: { allowed: contractReader } },
    { path: '/inventory', component: () => import('./views/InventoryPage.vue') },
    { path: '/inventory/issue-slips/:id', component: () => import('./views/IssueSlipPage.vue') },
    { path: '/finance', component: () => import('./views/FinancePage.vue') },
    { path: '/masterdata', component: () => import('./views/MasterdataPage.vue') },
    { path: '/settings', component: () => import('./views/SettingsPage.vue') },
    { path: '/:pathMatch(.*)*', redirect: '/workbench' },
  ],
})
router.beforeEach(async (to) => {
  if (to.path === '/login') return
  if (!localStore.get('access_token')) return '/login'
  if (!user.value) {
    try {
      await loadUser()
    } catch {
      return '/login'
    }
  }
  if (user.value?.setup_required && to.path !== '/setup') return '/setup'
  if (to.path === '/setup') return can(['admin']) ? true : '/workbench'
  if (!navigation().some((n) => n.key === to.path.split('/')[1])) return '/workbench'
  if (typeof to.meta.allowed === 'function' && !to.meta.allowed()) return '/workbench'
})
