import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '@/stores/user'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { requiresAuth: false }
  },
  {
    path: '/',
    component: () => import('@/layout/MainLayout.vue'),
    meta: { requiresAuth: true },
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/Dashboard.vue'),
        meta: { title: '仪表盘', icon: 'DataAnalysis', menuId: 'dashboard' }
      },
      // User Management
      {
        path: 'users',
        name: 'UserList',
        component: () => import('@/views/system/UserList.vue'),
        meta: { title: '用户管理', icon: 'User', menuId: 'system:users' }
      },
      {
        path: 'roles',
        name: 'RoleList',
        component: () => import('@/views/system/RoleList.vue'),
        meta: { title: '角色管理', icon: 'Setting', menuId: 'system:roles' }
      },
      {
        path: 'notification-settings',
        name: 'NotificationSettings',
        component: () => import('@/views/settings/NotificationSettings.vue'),
        meta: { title: '通知设置', icon: 'Bell', menuId: 'system:notifications' }
      },
      {
        path: 'departments',
        name: 'DepartmentList',
        component: () => import('@/views/system/DepartmentList.vue'),
        meta: { title: '部门管理', icon: 'OfficeBuilding', menuId: 'system:departments' }
      },
      // Master Data
      {
        path: 'items',
        name: 'ItemList',
        component: () => import('@/views/masterdata/ItemList.vue'),
        meta: { title: '物料管理', icon: 'Box', menuId: 'masterdata:items' }
      },
      {
        path: 'customers',
        name: 'CustomerList',
        component: () => import('@/views/masterdata/CustomerList.vue'),
        meta: { title: '客户管理', icon: 'Avatar', menuId: 'masterdata:customers' }
      },
      {
        path: 'suppliers',
        name: 'SupplierList',
        component: () => import('@/views/masterdata/SupplierList.vue'),
        meta: { title: '供应商管理', icon: 'ShoppingCart', menuId: 'masterdata:suppliers' }
      },
      {
        path: 'warehouses',
        name: 'WarehouseList',
        component: () => import('@/views/masterdata/WarehouseList.vue'),
        meta: { title: '仓库管理', icon: 'House', menuId: 'masterdata:warehouses' }
      },
      {
        path: 'locations',
        name: 'LocationList',
        component: () => import('@/views/masterdata/LocationList.vue'),
        meta: { title: '库位管理', icon: 'Grid', menuId: 'masterdata:locations' }
      },
      // Projects
      {
        path: 'projects',
        name: 'ProjectList',
        component: () => import('@/views/projects/ProjectList.vue'),
        meta: { title: '项目列表', icon: 'Management', menuId: 'projects:list' }
      },
      {
        path: 'projects/:id',
        name: 'ProjectDetail',
        component: () => import('@/views/projects/ProjectDetail.vue'),
        meta: { title: '项目详情', menuId: 'projects:list' }
      },
      {
        path: 'projects/tasks',
        name: 'TaskList',
        component: () => import('@/views/projects/TaskList.vue'),
        meta: { title: '任务管理', icon: 'List', menuId: 'projects:tasks' }
      },
      {
        path: 'projects/members',
        name: 'MemberList',
        component: () => import('@/views/projects/MemberList.vue'),
        meta: { title: '成员管理', icon: 'User', menuId: 'projects:members' }
      },
      {
        path: 'projects/bom',
        name: 'BOMList',
        component: () => import('@/views/projects/BOMList.vue'),
        meta: { title: 'BOM清单', icon: 'Document', menuId: 'projects:bom' }
      },
      {
        path: 'projects/time-logs',
        name: 'TimeLogList',
        component: () => import('@/views/projects/TimeLogList.vue'),
        meta: { title: '工时填报', icon: 'Clock', menuId: 'projects:time-logs' }
      },
      {
        path: 'projects/gantt',
        name: 'ProjectGantt',
        component: () => import('@/views/projects/ProjectGantt.vue'),
        meta: { title: '甘特图', icon: 'Calendar', menuId: 'projects:gantt' }
      },
      {
        path: 'projects/ecn',
        name: 'ECNList',
        component: () => import('@/views/projects/ECNList.vue'),
        meta: { title: 'ECN变更', icon: 'Edit', menuId: 'projects:list' }  // 使用与项目列表相同的权限
      },
      // After Sales - 售后管理
      {
        path: 'aftersales/orders',
        name: 'AfterSalesOrderList',
        component: () => import('@/views/aftersales/OrderList.vue'),
        meta: { title: '售后工单', icon: 'Service', menuId: 'aftersales:orders' }
      },
      {
        path: 'aftersales/orders/:id',
        name: 'AfterSalesOrderDetail',
        component: () => import('@/views/aftersales/OrderDetail.vue'),
        meta: { title: '工单详情', menuId: 'aftersales:orders' }
      },
      // Purchase
      {
        path: 'purchase/requests',
        name: 'PurchaseRequestList',
        component: () => import('@/views/purchase/RequestList.vue'),
        meta: { title: '采购申请', icon: 'Document', menuId: 'purchase:requests' }
      },
      {
        path: 'purchase/orders',
        name: 'PurchaseOrderList',
        component: () => import('@/views/purchase/OrderList.vue'),
        meta: { title: '采购订单', icon: 'DocumentCopy', menuId: 'purchase:orders' }
      },
      {
        path: 'purchase/orders/:id',
        name: 'PurchaseOrderDetail',
        component: () => import('@/views/purchase/PurchaseOrderDetail.vue'),
        meta: { title: '采购订单详情', menuId: 'purchase:orders' }
      },
      {
        path: 'purchase/goods-receipts',
        name: 'GoodsReceiptList',
        component: () => import('@/views/purchase/GoodsReceiptList.vue'),
        meta: { title: '到货质检', icon: 'Box', menuId: 'purchase:goods-receipts' }
      },
      // Sales
      {
        path: 'sales/quotations',
        name: 'QuotationList',
        component: () => import('@/views/sales/QuotationList.vue'),
        meta: { title: '销售报价', icon: 'Document', menuId: 'sales:quotations' }
      },
      {
        path: 'sales/quotations/create',
        name: 'QuotationCreate',
        component: () => import('@/views/sales/QuotationForm.vue'),
        meta: { title: '新增报价', menuId: 'sales:quotations' }
      },
      {
        path: 'sales/quotations/:id/edit',
        name: 'QuotationEdit',
        component: () => import('@/views/sales/QuotationForm.vue'),
        meta: { title: '编辑报价', menuId: 'sales:quotations' }
      },
      {
        path: 'sales/orders',
        name: 'SalesOrderList',
        component: () => import('@/views/sales/OrderList.vue'),
        meta: { title: '销售订单', icon: 'Sell', menuId: 'sales:orders' }
      },
      {
        path: 'sales/orders/:id',
        name: 'SalesOrderDetail',
        component: () => import('@/views/sales/SalesOrderDetail.vue'),
        meta: { title: '销售订单详情', menuId: 'sales:orders' }
      },
      {
        path: 'sales/delivery-orders',
        name: 'DeliveryOrderList',
        component: () => import('@/views/sales/DeliveryOrderList.vue'),
        meta: { title: '发货单管理', icon: 'Van', menuId: 'sales:delivery-orders' }
      },
      // Inventory
      {
        path: 'inventory/stocks',
        name: 'StockList',
        component: () => import('@/views/inventory/StockList.vue'),
        meta: { title: '库存查询', icon: 'Goods', menuId: 'inventory:stocks' }
      },
      {
        path: 'inventory/batches',
        name: 'BatchList',
        component: () => import('@/views/inventory/BatchList.vue'),
        meta: { title: '批次管理', icon: 'Collection', menuId: 'inventory:batches' }
      },
      {
        path: 'inventory/transfer',
        name: 'StockTransfer',
        component: () => import('@/views/inventory/StockTransfer.vue'),
        meta: { title: '库存调拨', icon: 'Sort', menuId: 'inventory:transfer' }
      },
      {
        path: 'inventory/adjustment',
        name: 'StockAdjustmentList',
        component: () => import('@/views/inventory/StockAdjustmentList.vue'),
        meta: { title: '库存盘点', icon: 'DocumentChecked', menuId: 'inventory:adjustment' }
      },
      {
        path: 'inventory/alert',
        name: 'StockAlert',
        component: () => import('@/views/inventory/StockAlert.vue'),
        meta: { title: '库存预警', icon: 'Warning', menuId: 'inventory:alert' }
      },
      {
        path: 'inventory/moves',
        name: 'StockMoveList',
        component: () => import('@/views/inventory/StockMoveList.vue'),
        meta: { title: '库存流水', icon: 'List', menuId: 'inventory:moves' }
      },
      // Finance
      {
        path: 'finance/expenses',
        name: 'ExpenseList',
        component: () => import('@/views/finance/ExpenseList.vue'),
        meta: { title: '费用报销', icon: 'Money', menuId: 'finance:expenses' }
      },
      {
        path: 'finance/shared-expenses',
        name: 'SharedExpenseList',
        component: () => import('@/views/finance/SharedExpenseList.vue'),
        meta: { title: '公共费用分摊', icon: 'Share', menuId: 'finance:shared-expenses' }
      },
      {
        path: 'finance/ar',
        name: 'ARList',
        component: () => import('@/views/finance/ARList.vue'),
        meta: { title: '应收账款', icon: 'CreditCard', menuId: 'finance:ar' }
      },
      {
        path: 'finance/ap',
        name: 'APList',
        component: () => import('@/views/finance/APList.vue'),
        meta: { title: '应付账款', icon: 'Wallet', menuId: 'finance:ap' }
      },
      {
        path: 'finance/invoices',
        name: 'InvoiceList',
        component: () => import('@/views/finance/InvoiceList.vue'),
        meta: { title: '发票管理', icon: 'Tickets', menuId: 'finance:invoices' }
      },
      {
        path: 'finance/project-costs',
        name: 'ProjectCostList',
        component: () => import('@/views/finance/ProjectCostList.vue'),
        meta: { title: '项目成本核算', icon: 'DataAnalysis', menuId: 'finance:project-costs' }
      },
      // Reports
      {
        path: 'reports/profitability',
        name: 'ProfitabilityReport',
        component: () => import('@/views/reports/ProfitabilityReport.vue'),
        meta: { title: '项目利润分析', icon: 'TrendCharts', menuId: 'reports:profitability' }
      },
      {
        path: 'reports/inventory-turnover',
        name: 'InventoryTurnoverReport',
        component: () => import('@/views/reports/InventoryTurnoverReport.vue'),
        meta: { title: '库存周转率', icon: 'Refresh', menuId: 'reports:inventory-turnover' }
      },
      {
        path: 'reports/aging',
        name: 'AgingReport',
        component: () => import('@/views/reports/AgingReport.vue'),
        meta: { title: '账龄分析', icon: 'Calendar', menuId: 'reports:aging' }
      },
      {
        path: 'reports/purchase-price-trend',
        name: 'PurchasePriceTrendReport',
        component: () => import('@/views/reports/PurchasePriceTrendReport.vue'),
        meta: { title: '采购价格趋势', icon: 'DataLine', menuId: 'reports:purchase-price-trend' }
      },
      {
        path: 'reports/cash-flow',
        name: 'CashFlowForecast',
        component: () => import('@/views/reports/CashFlowForecast.vue'),
        meta: { title: '现金流预测', icon: 'Money', menuId: 'reports:cash-flow' }
      },
      {
        path: 'reports/slow-moving',
        name: 'SlowMovingReport',
        component: () => import('@/views/reports/SlowMovingReport.vue'),
        meta: { title: '呆滞物料分析', icon: 'Warning', menuId: 'reports:slow-moving' }
      },
      // Analytics
      {
        path: 'analytics/project',
        name: 'ProjectAnalytics',
        component: () => import('@/views/analytics/ProjectAnalytics.vue'),
        meta: { title: '项目分析', icon: 'DataLine', menuId: 'analytics:project' }
      },
      {
        path: 'analytics/inventory',
        name: 'InventoryAnalytics',
        component: () => import('@/views/analytics/InventoryAnalytics.vue'),
        meta: { title: '库存分析', icon: 'PieChart', menuId: 'analytics:inventory' }
      },
      // Workflow
      {
        path: 'workflow/tasks',
        name: 'WorkflowTasks',
        component: () => import('@/views/workflow/TaskList.vue'),
        meta: { title: '待办审批', icon: 'Checked', menuId: 'workflow:tasks' }
      },
      {
        path: 'workflow/my-submissions',
        name: 'MySubmissions',
        component: () => import('@/views/workflow/MySubmissions.vue'),
        meta: { title: '我的提交', icon: 'Document', menuId: 'workflow:my-submissions' }
      },
      {
        path: 'workflow/config',
        name: 'WorkflowConfig',
        component: () => import('@/views/workflow/WorkflowConfig.vue'),
        meta: { title: '流程配置', icon: 'Setting', menuId: 'workflow:config' }
      },
      // System
      {
        path: 'system/audit-log',
        name: 'AuditLog',
        component: () => import('@/views/AuditLog.vue'),
        meta: { title: '审计日志', icon: 'Document', menuId: 'system:audit-log' }
      },
      {
        path: 'system/notifications',
        name: 'NotificationCenter',
        component: () => import('@/views/NotificationCenter.vue'),
        meta: { title: '通知中心', icon: 'Bell', menuId: 'system:notifications' }
      },
      {
        path: 'system/login-logs',
        name: 'LoginLogs',
        component: () => import('@/views/system/LoginLogs.vue'),
        meta: { title: '登录日志', icon: 'Key', menuId: 'system:login-logs' }
      },
      {
        path: 'system/webhooks',
        name: 'WebhookList',
        component: () => import('@/views/system/WebhookList.vue'),
        meta: { title: 'Webhook管理', icon: 'Connection', menuId: 'system:webhooks' }
      },
      {
        path: 'system/dashboard-config',
        name: 'DashboardConfig',
        component: () => import('@/views/system/DashboardConfig.vue'),
        meta: { title: '仪表盘配置', icon: 'DataBoard', menuId: 'system:dashboard-config' }
      },
      // User Profile - 这些是公共页面，所有登录用户都可以访问
      {
        path: 'profile',
        name: 'Profile',
        component: () => import('@/views/Profile.vue'),
        meta: { title: '个人中心', icon: 'User', public: true }
      },
      {
        path: 'change-password',
        name: 'ChangePassword',
        component: () => import('@/views/ChangePassword.vue'),
        meta: { title: '修改密码', icon: 'Lock', public: true }
      },
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 检查用户是否有访问某个菜单的权限
const hasMenuAccess = (menuId, userStore) => {
  // 如果没有menuId或者是公共页面，允许访问
  if (!menuId) return true
  
  // 超级管理员有所有权限
  if (userStore.userInfo?.is_superuser) return true
  
  // 如果权限列表包含 *:*:* 则有所有权限
  if (userStore.permissions?.includes('*:*:*')) return true
  
  // 获取用户的菜单权限列表
  const menuIds = userStore.menuIds
  
  // 如果 menuIds 为空或未定义，表示没有配置权限，不允许访问
  if (!menuIds || menuIds.length === 0) return false
  
  // 检查是否在权限列表中
  // 对于父菜单，检查是否有任何子菜单的权限
  if (!menuId.includes(':')) {
    return menuIds.some(id => id === menuId || id.startsWith(menuId + ':'))
  }
  
  // 子菜单直接检查
  return menuIds.includes(menuId)
}

// Navigation guard
router.beforeEach(async (to, from, next) => {
  const userStore = useUserStore()
  const token = localStorage.getItem('access_token')
  
  // 未登录用户访问需要认证的页面
  if (to.meta.requiresAuth !== false && !token) {
    next('/login')
    return
  }
  
  // 已登录用户访问登录页
  if (to.path === '/login' && token) {
    next('/')
    return
  }
  
  // 如果需要认证且有token，检查权限
  if (to.meta.requiresAuth !== false && token) {
    // 确保用户信息已加载
    if (!userStore.userInfo) {
      try {
        await userStore.getProfile()
      } catch (error) {
        console.error('Failed to load user profile:', error)
        next('/login')
        return
      }
    }
    
    // 公共页面（如个人中心、修改密码）不检查权限
    if (to.meta.public) {
      next()
      return
    }
    
    // 检查菜单权限
    const menuId = to.meta.menuId
    if (menuId && !hasMenuAccess(menuId, userStore)) {
      console.warn(`Access denied to ${to.path}, missing permission for menu: ${menuId}`)
      // 如果没有权限，重定向到仪表盘或第一个有权限的页面
      if (hasMenuAccess('dashboard', userStore)) {
        next('/dashboard')
      } else {
        // 找到第一个有权限的页面
        const firstMenu = userStore.menuIds?.[0]
        if (firstMenu) {
          // 根据menuId找到对应的路由
          const menuToPath = {
            'dashboard': '/dashboard',
            'workflow:tasks': '/workflow/tasks',
            'workflow:my-submissions': '/workflow/my-submissions',
            'system:users': '/users',
            'system:roles': '/roles',
            'system:departments': '/departments',
            'masterdata:items': '/items',
            'masterdata:customers': '/customers',
            'masterdata:suppliers': '/suppliers',
            'projects:list': '/projects',
            'purchase:requests': '/purchase/requests',
            'sales:quotations': '/sales/quotations',
            'inventory:stocks': '/inventory/stocks',
            'finance:expenses': '/finance/expenses',
            'reports:profitability': '/reports/profitability',
            'analytics:project': '/analytics/project'
          }
          const targetPath = menuToPath[firstMenu] || '/profile'
          next(targetPath)
  } else {
          // 没有任何权限，跳转到个人中心
          next('/profile')
        }
      }
      return
    }
  }
  
    next()
})

export default router

