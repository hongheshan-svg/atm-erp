import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

// 路由表。meta.permission 控制页面访问;懒加载视图。
const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { public: true }
  },
  {
    path: '/',
    component: () => import('@/layout/MainLayout.vue'),
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/Dashboard.vue'),
        meta: { title: '工作台' }
      },
      {
        path: 'masterdata/items',
        name: 'ItemList',
        component: () => import('@/views/masterdata/ItemList.vue'),
        meta: { title: '物料管理', permission: 'masterdata:item:view' }
      }
    ]
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/'
  }
]

const router = createRouter({
  // base '/erp/' 与 vite.config.ts、nginx 路由一致。
  history: createWebHistory('/erp/'),
  routes
})

// 全局守卫:校验登录态 + 页面权限(父码通配由 store 处理)。
router.beforeEach(async to => {
  const token = localStorage.getItem('access_token')

  if (to.meta.public) {
    // 已登录访问 /login 直接进首页。
    if (token && to.path === '/login') return '/'
    return true
  }

  if (!token) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }

  // 动态导入 store,避免与 request.ts/router 的循环依赖在模块初始化期触发。
  const { useUserStore } = await import('@/stores/user')
  const { usePermissionStore } = await import('@/stores/permission')
  const userStore = useUserStore()
  const permissionStore = usePermissionStore()

  // 刷新页面后内存档案丢失,凭 token 回灌一次。
  if (!userStore.profileReady) {
    try {
      await userStore.fetchProfile()
    } catch {
      userStore.logout()
      return { path: '/login', query: { redirect: to.fullPath } }
    }
  }

  const required = to.meta.permission as string | undefined
  if (required && !permissionStore.hasPermission(required)) {
    return '/dashboard'
  }

  return true
})

export default router
