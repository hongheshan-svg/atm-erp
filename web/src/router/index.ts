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
      },
      {
        path: 'masterdata/customers',
        name: 'CustomerList',
        component: () => import('@/views/masterdata/CustomerList.vue'),
        meta: { title: '客户管理', permission: 'masterdata:customer:view' }
      },
      {
        path: 'masterdata/suppliers',
        name: 'SupplierList',
        component: () => import('@/views/masterdata/SupplierList.vue'),
        meta: { title: '供应商管理', permission: 'masterdata:supplier:view' }
      },
      {
        path: 'masterdata/warehouses',
        name: 'WarehouseList',
        component: () => import('@/views/masterdata/WarehouseList.vue'),
        meta: { title: '仓库管理', permission: 'masterdata:warehouse:view' }
      },
      {
        path: 'sales/quotations',
        name: 'QuotationList',
        component: () => import('@/views/sales/QuotationList.vue'),
        meta: { title: '销售报价', permission: 'sales:quotation:view' }
      },
      {
        path: 'purchase/orders',
        name: 'PurchaseOrderList',
        component: () => import('@/views/purchase/PurchaseOrderList.vue'),
        meta: { title: '采购订单', permission: 'purchase:order:view' }
      },
      {
        path: 'inventory/stocks',
        name: 'StockList',
        component: () => import('@/views/inventory/StockList.vue'),
        meta: { title: '库存查询', permission: 'inventory:stock:view' }
      },
      {
        path: 'inventory/stock-moves',
        name: 'StockMoveList',
        component: () => import('@/views/inventory/StockMoveList.vue'),
        meta: { title: '库存移动', permission: 'inventory:stock_move:view' }
      },
      {
        path: 'projects/projects',
        name: 'ProjectList',
        component: () => import('@/views/projects/ProjectList.vue'),
        meta: { title: '项目管理', permission: 'projects:project:view' }
      },
      {
        path: 'production/work-orders',
        name: 'WorkOrderList',
        component: () => import('@/views/production/WorkOrderList.vue'),
        meta: { title: '生产工单', permission: 'production:work_order:view' }
      },
      {
        path: 'finance/receivables',
        name: 'ReceivableList',
        component: () => import('@/views/finance/ReceivableList.vue'),
        meta: { title: '应收账款', permission: 'finance:receivable:view' }
      },
      {
        path: 'oa/vehicles',
        name: 'VehicleList',
        component: () => import('@/views/oa/VehicleList.vue'),
        meta: { title: '车辆管理', permission: 'oa:vehicle:view' }
      },
      {
        path: 'accounts/users',
        name: 'UserList',
        component: () => import('@/views/accounts/UserList.vue'),
        meta: { title: '用户列表', permission: 'accounts:user:view' }
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
