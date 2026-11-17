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
    { path: '/feedback', component: () => import('./views/FeedbackPage.vue') },
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
// 每页一个标签页标题（「库存 · 项目 ERP」），同时开多个页面时能分清；项目详情加载后由项目页换成项目名称。
const pageTitles: Record<string, string> = {
  login: '登录', setup: '初次安装', workbench: '工作台', reports: '经营报表', sales: '销售', projects: '项目', bom: 'BOM',
  purchases: '采购', inventory: '库存', finance: '收付款', masterdata: '基础资料', settings: '设置', feedback: '问题反馈',
}
export function pageTitle(path: string) {
  const [section, id, child] = path.split('/').filter(Boolean)
  const name = section === 'projects' && id ? '项目详情' : section === 'purchases' && child === 'contract' ? '采购合同' : section === 'inventory' && id === 'issue-slips' ? '领料单' : pageTitles[section || ''] || ''
  return name ? `${name} · 项目 ERP` : '项目 ERP'
}
// 只在换页面时改：页签切换只改查询参数，不能把项目页已换上的项目名称冲掉。
router.afterEach((to, from) => { if (to.path !== from.path) document.title = pageTitle(to.path) })
