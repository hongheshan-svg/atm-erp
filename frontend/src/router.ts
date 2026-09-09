import { createRouter, createWebHistory } from 'vue-router'
import { user, loadUser } from './session'
import { navigation } from './navigation'
export const router = createRouter({
  history: createWebHistory('/erp/'),
  routes: [
    { path: '/login', component: () => import('./views/LoginPage.vue') },
    { path: '/', redirect: '/workbench' },
    { path: '/projects/:id', component: () => import('./views/ProjectPage.vue') },
    { path: '/workbench', component: () => import('./views/WorkbenchPage.vue') },
    { path: '/sales', component: () => import('./views/SalesPage.vue') },
    { path: '/projects', component: () => import('./views/ProjectsPage.vue') },
    { path: '/bom', component: () => import('./views/BOMPage.vue') },
    { path: '/purchases', component: () => import('./views/PurchasesPage.vue') },
    { path: '/inventory', component: () => import('./views/InventoryPage.vue') },
    { path: '/finance', component: () => import('./views/FinancePage.vue') },
    { path: '/masterdata', component: () => import('./views/MasterdataPage.vue') },
    { path: '/settings', component: () => import('./views/SettingsPage.vue') },
    { path: '/:pathMatch(.*)*', redirect: '/workbench' },
  ],
})
router.beforeEach(async (to) => {
  if (to.path === '/login') return
  if (!localStorage.getItem('access_token')) return '/login'
  if (!user.value) {
    try {
      await loadUser()
    } catch {
      return '/login'
    }
  }
  if (!navigation().some((n) => n.key === to.path.split('/')[1])) return '/workbench'
})
