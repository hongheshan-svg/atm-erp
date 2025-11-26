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
        meta: { title: '仪表盘', icon: 'DataAnalysis' }
      },
      // User Management
      {
        path: 'users',
        name: 'UserList',
        component: () => import('@/views/system/UserList.vue'),
        meta: { title: '用户管理', icon: 'User' }
      },
      {
        path: 'roles',
        name: 'RoleList',
        component: () => import('@/views/system/RoleList.vue'),
        meta: { title: '角色管理', icon: 'Setting' }
      },
      {
        path: 'notification-settings',
        name: 'NotificationSettings',
        component: () => import('@/views/settings/NotificationSettings.vue'),
        meta: { title: '通知设置', icon: 'Bell' }
      },
      {
        path: 'departments',
        name: 'DepartmentList',
        component: () => import('@/views/system/DepartmentList.vue'),
        meta: { title: '部门管理', icon: 'OfficeBuilding' }
      },
      // Master Data
      {
        path: 'items',
        name: 'ItemList',
        component: () => import('@/views/masterdata/ItemList.vue'),
        meta: { title: '物料管理', icon: 'Box' }
      },
      {
        path: 'customers',
        name: 'CustomerList',
        component: () => import('@/views/masterdata/CustomerList.vue'),
        meta: { title: '客户管理', icon: 'Avatar' }
      },
      {
        path: 'suppliers',
        name: 'SupplierList',
        component: () => import('@/views/masterdata/SupplierList.vue'),
        meta: { title: '供应商管理', icon: 'ShoppingCart' }
      },
      {
        path: 'warehouses',
        name: 'WarehouseList',
        component: () => import('@/views/masterdata/WarehouseList.vue'),
        meta: { title: '仓库管理', icon: 'House' }
      },
      {
        path: 'locations',
        name: 'LocationList',
        component: () => import('@/views/masterdata/LocationList.vue'),
        meta: { title: '库位管理', icon: 'Grid' }
      },
      // Projects
      {
        path: 'projects',
        name: 'ProjectList',
        component: () => import('@/views/projects/ProjectList.vue'),
        meta: { title: '项目列表', icon: 'Management' }
      },
      {
        path: 'projects/:id',
        name: 'ProjectDetail',
        component: () => import('@/views/projects/ProjectDetail.vue'),
        meta: { title: '项目详情' }
      },
      {
        path: 'projects/tasks',
        name: 'TaskList',
        component: () => import('@/views/projects/TaskList.vue'),
        meta: { title: '任务管理', icon: 'List' }
      },
      {
        path: 'projects/members',
        name: 'MemberList',
        component: () => import('@/views/projects/MemberList.vue'),
        meta: { title: '成员管理', icon: 'User' }
      },
      {
        path: 'projects/bom',
        name: 'BOMList',
        component: () => import('@/views/projects/BOMList.vue'),
        meta: { title: 'BOM清单', icon: 'Document' }
      },
      {
        path: 'projects/time-logs',
        name: 'TimeLogList',
        component: () => import('@/views/projects/TimeLogList.vue'),
        meta: { title: '工时填报', icon: 'Clock' }
      },
      {
        path: 'projects/gantt',
        name: 'ProjectGantt',
        component: () => import('@/views/projects/ProjectGantt.vue'),
        meta: { title: '甘特图', icon: 'Calendar' }
      },
      // Purchase
      {
        path: 'purchase/requests',
        name: 'PurchaseRequestList',
        component: () => import('@/views/purchase/RequestList.vue'),
        meta: { title: '采购申请', icon: 'Document' }
      },
      {
        path: 'purchase/orders',
        name: 'PurchaseOrderList',
        component: () => import('@/views/purchase/OrderList.vue'),
        meta: { title: '采购订单', icon: 'DocumentCopy' }
      },
      {
        path: 'purchase/orders/:id',
        name: 'PurchaseOrderDetail',
        component: () => import('@/views/purchase/PurchaseOrderDetail.vue'),
        meta: { title: '采购订单详情' }
      },
      {
        path: 'purchase/goods-receipts',
        name: 'GoodsReceiptList',
        component: () => import('@/views/purchase/GoodsReceiptList.vue'),
        meta: { title: '到货质检', icon: 'Box' }
      },
      // Sales
      {
        path: 'sales/quotations',
        name: 'QuotationList',
        component: () => import('@/views/sales/QuotationList.vue'),
        meta: { title: '销售报价', icon: 'Document' }
      },
      {
        path: 'sales/quotations/create',
        name: 'QuotationCreate',
        component: () => import('@/views/sales/QuotationForm.vue'),
        meta: { title: '新增报价' }
      },
      {
        path: 'sales/quotations/:id/edit',
        name: 'QuotationEdit',
        component: () => import('@/views/sales/QuotationForm.vue'),
        meta: { title: '编辑报价' }
      },
      {
        path: 'sales/orders',
        name: 'SalesOrderList',
        component: () => import('@/views/sales/OrderList.vue'),
        meta: { title: '销售订单', icon: 'Sell' }
      },
      {
        path: 'sales/orders/:id',
        name: 'SalesOrderDetail',
        component: () => import('@/views/sales/SalesOrderDetail.vue'),
        meta: { title: '销售订单详情' }
      },
      {
        path: 'sales/delivery-orders',
        name: 'DeliveryOrderList',
        component: () => import('@/views/sales/DeliveryOrderList.vue'),
        meta: { title: '发货单管理', icon: 'Van' }
      },
      // Inventory
      {
        path: 'inventory/stocks',
        name: 'StockList',
        component: () => import('@/views/inventory/StockList.vue'),
        meta: { title: '库存查询', icon: 'Goods' }
      },
      {
        path: 'inventory/batches',
        name: 'BatchList',
        component: () => import('@/views/inventory/BatchList.vue'),
        meta: { title: '批次管理', icon: 'Collection' }
      },
      {
        path: 'inventory/transfer',
        name: 'StockTransfer',
        component: () => import('@/views/inventory/StockTransfer.vue'),
        meta: { title: '库存调拨', icon: 'Sort' }
      },
      {
        path: 'inventory/adjustment',
        name: 'StockAdjustmentList',
        component: () => import('@/views/inventory/StockAdjustmentList.vue'),
        meta: { title: '库存盘点', icon: 'DocumentChecked' }
      },
      {
        path: 'inventory/alert',
        name: 'StockAlert',
        component: () => import('@/views/inventory/StockAlert.vue'),
        meta: { title: '库存预警', icon: 'Warning' }
      },
      {
        path: 'inventory/moves',
        name: 'StockMoveList',
        component: () => import('@/views/inventory/StockMoveList.vue'),
        meta: { title: '库存流水', icon: 'List' }
      },
      // Finance
      {
        path: 'finance/expenses',
        name: 'ExpenseList',
        component: () => import('@/views/finance/ExpenseList.vue'),
        meta: { title: '费用报销', icon: 'Money' }
      },
      {
        path: 'finance/shared-expenses',
        name: 'SharedExpenseList',
        component: () => import('@/views/finance/SharedExpenseList.vue'),
        meta: { title: '公共费用分摊', icon: 'Share' }
      },
      {
        path: 'finance/ar',
        name: 'ARList',
        component: () => import('@/views/finance/ARList.vue'),
        meta: { title: '应收账款', icon: 'CreditCard' }
      },
      {
        path: 'finance/ap',
        name: 'APList',
        component: () => import('@/views/finance/APList.vue'),
        meta: { title: '应付账款', icon: 'Wallet' }
      },
      {
        path: 'finance/invoices',
        name: 'InvoiceList',
        component: () => import('@/views/finance/InvoiceList.vue'),
        meta: { title: '发票管理', icon: 'Tickets' }
      },
      {
        path: 'finance/project-costs',
        name: 'ProjectCostList',
        component: () => import('@/views/finance/ProjectCostList.vue'),
        meta: { title: '项目成本核算', icon: 'DataAnalysis' }
      },
      // Reports
      {
        path: 'reports/profitability',
        name: 'ProfitabilityReport',
        component: () => import('@/views/reports/ProfitabilityReport.vue'),
        meta: { title: '项目利润分析', icon: 'TrendCharts' }
      },
      {
        path: 'reports/inventory-turnover',
        name: 'InventoryTurnoverReport',
        component: () => import('@/views/reports/InventoryTurnoverReport.vue'),
        meta: { title: '库存周转率', icon: 'Refresh' }
      },
      {
        path: 'reports/aging',
        name: 'AgingReport',
        component: () => import('@/views/reports/AgingReport.vue'),
        meta: { title: '账龄分析', icon: 'Calendar' }
      },
      {
        path: 'reports/purchase-price-trend',
        name: 'PurchasePriceTrendReport',
        component: () => import('@/views/reports/PurchasePriceTrendReport.vue'),
        meta: { title: '采购价格趋势', icon: 'DataLine' }
      },
      {
        path: 'reports/cash-flow',
        name: 'CashFlowForecast',
        component: () => import('@/views/reports/CashFlowForecast.vue'),
        meta: { title: '现金流预测', icon: 'Money' }
      },
      {
        path: 'reports/slow-moving',
        name: 'SlowMovingReport',
        component: () => import('@/views/reports/SlowMovingReport.vue'),
        meta: { title: '呆滞物料分析', icon: 'Warning' }
      },
      // Analytics
      {
        path: 'analytics/project',
        name: 'ProjectAnalytics',
        component: () => import('@/views/analytics/ProjectAnalytics.vue'),
        meta: { title: '项目分析', icon: 'DataLine' }
      },
      {
        path: 'analytics/inventory',
        name: 'InventoryAnalytics',
        component: () => import('@/views/analytics/InventoryAnalytics.vue'),
        meta: { title: '库存分析', icon: 'PieChart' }
      },
      // System
      {
        path: 'system/audit-log',
        name: 'AuditLog',
        component: () => import('@/views/AuditLog.vue'),
        meta: { title: '审计日志', icon: 'Document' }
      },
      {
        path: 'system/notifications',
        name: 'NotificationCenter',
        component: () => import('@/views/NotificationCenter.vue'),
        meta: { title: '通知中心', icon: 'Bell' }
      },
      // User Profile
      {
        path: 'profile',
        name: 'Profile',
        component: () => import('@/views/Profile.vue'),
        meta: { title: '个人中心', icon: 'User' }
      },
      {
        path: 'change-password',
        name: 'ChangePassword',
        component: () => import('@/views/ChangePassword.vue'),
        meta: { title: '修改密码', icon: 'Lock' }
      },
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// Navigation guard
router.beforeEach((to, from, next) => {
  const userStore = useUserStore()
  const token = localStorage.getItem('access_token')
  
  if (to.meta.requiresAuth !== false && !token) {
    next('/login')
  } else if (to.path === '/login' && token) {
    next('/')
  } else {
    next()
  }
})

export default router

