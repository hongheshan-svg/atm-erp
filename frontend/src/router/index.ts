import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { usePermissionStore } from '@/stores/permission'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { requiresAuth: false }
  },
  // 基础资料旧路径兼容重定向
  { path: '/items', redirect: '/masterdata/items' },
  { path: '/customers', redirect: '/masterdata/customers' },
  { path: '/suppliers', redirect: '/masterdata/suppliers' },
  { path: '/warehouses', redirect: '/masterdata/warehouses' },
  { path: '/locations', redirect: '/masterdata/locations' },
  // 系统管理旧路径兼容重定向
  { path: '/users', redirect: '/system/users' },
  { path: '/roles', redirect: '/system/roles' },
  { path: '/departments', redirect: '/system/departments' },
  { path: '/code-rules', redirect: '/system/code-rules' },
  { path: '/notification-settings', redirect: '/system/notification-settings' },
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
        meta: { title: '工作台', icon: 'DataAnalysis', menuId: 'dashboard' }
      },
      // System Management - 系统管理
      {
        path: 'system/users',
        name: 'UserList',
        component: () => import('@/views/system/UserList.vue'),
        meta: { title: '用户管理', icon: 'User', menuId: 'system:users' }
      },
      {
        path: 'system/roles',
        name: 'RoleList',
        component: () => import('@/views/system/RoleList.vue'),
        meta: { title: '角色管理', icon: 'Setting', menuId: 'system:roles' }
      },
      {
        path: 'system/departments',
        name: 'DepartmentList',
        component: () => import('@/views/system/DepartmentList.vue'),
        meta: { title: '部门管理', icon: 'OfficeBuilding', menuId: 'system:departments' }
      },
      {
        path: 'system/code-rules',
        name: 'CodeRuleList',
        component: () => import('@/views/system/CodeRuleList.vue'),
        meta: { title: '编号规则', icon: 'SetUp', menuId: 'system:code-rules' }
      },
      {
        path: 'system/notification-settings',
        name: 'NotificationSettings',
        component: () => import('@/views/settings/NotificationSettings.vue'),
        meta: { title: '消息设置', icon: 'Bell', menuId: 'system:notification-settings' }
      },
      // Master Data - 基础资料
      {
        path: 'masterdata/items',
        name: 'ItemList',
        component: () => import('@/views/masterdata/ItemList.vue'),
        meta: { title: '物料管理', icon: 'Box', menuId: 'masterdata:items' }
      },
      {
        path: 'masterdata/customers',
        name: 'CustomerList',
        component: () => import('@/views/masterdata/CustomerList.vue'),
        meta: { title: '客户管理', icon: 'Avatar', menuId: 'masterdata:customers' }
      },
      {
        path: 'masterdata/suppliers',
        name: 'SupplierList',
        component: () => import('@/views/masterdata/SupplierList.vue'),
        meta: { title: '供应商管理', icon: 'ShoppingCart', menuId: 'masterdata:suppliers' }
      },
      {
        path: 'masterdata/warehouses',
        name: 'WarehouseList',
        component: () => import('@/views/masterdata/WarehouseList.vue'),
        meta: { title: '仓库管理', icon: 'House', menuId: 'masterdata:warehouses' }
      },
      {
        path: 'masterdata/locations',
        name: 'LocationList',
        component: () => import('@/views/masterdata/LocationList.vue'),
        meta: { title: '库位管理', icon: 'Grid', menuId: 'masterdata:locations' }
      },
      // Projects
      {
        path: 'projects',
        name: 'ProjectList',
        component: () => import('@/views/projects/ProjectList.vue'),
        meta: { title: '项目总览', icon: 'Management', menuId: 'projects:list' }
      },
      {
        path: 'projects/list',
        redirect: '/projects'
      },
      {
        path: 'projects/dashboard',
        name: 'ProjectDashboard',
        component: () => import('@/views/projects/ProjectDashboard.vue'),
        meta: { title: '项目看板', icon: 'DataAnalysis', menuId: 'projects:dashboard' }
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
        meta: { title: '任务看板', icon: 'List', menuId: 'projects:tasks' }
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
        meta: { title: 'BOM管理', icon: 'Document', menuId: 'projects:bom' }
      },
      {
        path: 'projects/time-logs',
        name: 'TimeLogList',
        component: () => import('@/views/projects/TimeLogList.vue'),
        meta: { title: '工时记录', icon: 'Clock', menuId: 'projects:time-logs' }
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
        meta: { title: '设计变更', icon: 'Edit', menuId: 'design:ecn' }
      },
      // Bug跟踪
      {
        path: 'projects/bugs',
        name: 'BugList',
        component: () => import('@/views/projects/BugList.vue'),
        meta: { title: '问题追踪', icon: 'Warning', menuId: 'projects:bugs' }
      },
      {
        path: 'projects/bugs/:id',
        name: 'BugDetail',
        component: () => import('@/views/projects/BugDetail.vue'),
        meta: { title: 'Bug详情', menuId: 'projects:bugs' }
      },
      // 图纸管理
      {
        path: 'projects/drawings',
        name: 'DrawingList',
        component: () => import('@/views/projects/DrawingList.vue'),
        meta: { title: '图纸文档', icon: 'Picture', menuId: 'design:drawings' }
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
        meta: { title: '到货验收', icon: 'Box', menuId: 'purchase:goods-receipts' }
      },
      // 询价管理已移除，询价功能整合到采购申请页面
      // {
      //   path: 'purchase/rfqs',
      //   name: 'RFQList',
      //   component: () => import('@/views/purchase/RFQList.vue'),
      //   meta: { title: '询价管理', icon: 'ChatDotSquare', menuId: 'purchase:rfqs' }
      // },
      {
        path: 'purchase/outsource',
        name: 'OutsourceList',
        component: () => import('@/views/purchase/OutsourceList.vue'),
        meta: { title: '外协加工', icon: 'Setting', menuId: 'purchase:outsource' }
      },
      {
        path: 'purchase/comparisons',
        name: 'ComparisonList',
        component: () => import('@/views/purchase/ComparisonList.vue'),
        meta: { title: '询价比价', icon: 'DataAnalysis', menuId: 'purchase:comparisons' }
      },
      {
        path: 'purchase/comparisons/:id',
        name: 'ComparisonDetail',
        component: () => import('@/views/purchase/ComparisonDetail.vue'),
        meta: { title: '比价详情', menuId: 'purchase:comparisons' }
      },
      {
        path: 'purchase/evaluations',
        name: 'SupplierEvaluationList',
        component: () => import('@/views/purchase/SupplierEvaluationList.vue'),
        meta: { title: '供应商考核', icon: 'Star', menuId: 'purchase:evaluations' }
      },
      {
        path: 'purchase/blacklist',
        name: 'SupplierBlacklist',
        component: () => import('@/views/purchase/SupplierBlacklist.vue'),
        meta: { title: '供应商黑名单', icon: 'Warning', menuId: 'purchase:blacklist' }
      },
      // Sales - CRM
      {
        path: 'sales/crm-dashboard',
        name: 'CRMDashboard',
        component: () => import('@/views/sales/CRMDashboard.vue'),
        meta: { title: '客户总览', icon: 'DataBoard', menuId: 'sales:crm-dashboard' }
      },
      {
        path: 'sales/leads',
        name: 'LeadList',
        component: () => import('@/views/sales/LeadList.vue'),
        meta: { title: '商机线索', icon: 'User', menuId: 'sales:leads' }
      },
      {
        path: 'sales/opportunities',
        name: 'OpportunityList',
        component: () => import('@/views/sales/OpportunityList.vue'),
        meta: { title: '销售机会', icon: 'Opportunity', menuId: 'sales:opportunities' }
      },
      // Sales
      {
        path: 'sales/quotations',
        name: 'QuotationList',
        component: () => import('@/views/sales/QuotationList.vue'),
        meta: { title: '技术报价', icon: 'Document', menuId: 'sales:quotations' }
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
        meta: { title: '发货管理', icon: 'Van', menuId: 'sales:delivery-orders' }
      },
      {
        path: 'sales/contracts',
        name: 'SalesContractList',
        component: () => import('@/views/sales/ContractList.vue'),
        meta: { title: '销售合同', icon: 'Document', menuId: 'sales:contracts' }
      },
      // Inventory
      {
        path: 'inventory/stocks',
        name: 'StockList',
        component: () => import('@/views/inventory/StockList.vue'),
        meta: { title: '实时库存', icon: 'Goods', menuId: 'inventory:stocks' }
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
        meta: { title: '调拨管理', icon: 'Sort', menuId: 'inventory:transfer' }
      },
      {
        path: 'inventory/adjustment',
        name: 'StockAdjustmentList',
        component: () => import('@/views/inventory/StockAdjustmentList.vue'),
        meta: { title: '盘点管理', icon: 'DocumentChecked', menuId: 'inventory:adjustment' }
      },
      {
        path: 'inventory/alert',
        name: 'StockAlert',
        component: () => import('@/views/inventory/StockAlert.vue'),
        meta: { title: '库存预警', icon: 'Warning', menuId: 'inventory:alerts' }
      },
      {
        path: 'inventory/moves',
        name: 'StockMoveList',
        component: () => import('@/views/inventory/StockMoveList.vue'),
        meta: { title: '出入明细', icon: 'List', menuId: 'inventory:moves' }
      },
      {
        path: 'inventory/requisitions',
        name: 'RequisitionList',
        component: () => import('@/views/inventory/RequisitionList.vue'),
        meta: { title: '领料出库', icon: 'TakeawayBox', menuId: 'inventory:requisitions' }
      },
      {
        path: 'inventory/returns',
        name: 'ReturnList',
        component: () => import('@/views/inventory/ReturnList.vue'),
        meta: { title: '退料入库', icon: 'RefreshLeft', menuId: 'inventory:returns' }
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
        meta: { title: '应收管理', icon: 'CreditCard', menuId: 'finance:ar' }
      },
      {
        path: 'finance/ap',
        name: 'APList',
        component: () => import('@/views/finance/APList.vue'),
        meta: { title: '应付管理', icon: 'Wallet', menuId: 'finance:ap' }
      },
      {
        path: 'finance/sales-reconciliation',
        name: 'SalesReconciliation',
        component: () => import('@/views/finance/SalesReconciliation.vue'),
        meta: { title: '销售对账', icon: 'Document', menuId: 'finance:sales-reconciliation' }
      },
      {
        path: 'finance/purchase-reconciliation',
        name: 'PurchaseReconciliation',
        component: () => import('@/views/finance/PurchaseReconciliation.vue'),
        meta: { title: '采购对账', icon: 'Document', menuId: 'finance:purchase-reconciliation' }
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
        meta: { title: '项目成本', icon: 'DataAnalysis', menuId: 'finance:project-costs' }
      },
      {
        path: 'finance/collection-plans',
        name: 'CollectionPlanList',
        component: () => import('@/views/finance/CollectionPlanList.vue'),
        meta: { title: '回款跟踪', icon: 'Money', menuId: 'finance:collection' }
      },
      // Reports
      {
        path: 'reports/profitability',
        name: 'ProfitabilityReport',
        component: () => import('@/views/reports/ProfitabilityReport.vue'),
        meta: { title: '项目利润', icon: 'TrendCharts', menuId: 'reports:profitability' }
      },
      {
        path: 'reports/aging',
        name: 'AgingReport',
        component: () => import('@/views/reports/AgingReport.vue'),
        meta: { title: '账龄报表', icon: 'Calendar', menuId: 'reports:aging' }
      },
      {
        path: 'reports/cash-flow',
        name: 'CashFlowForecast',
        component: () => import('@/views/reports/CashFlowForecast.vue'),
        meta: { title: '现金流', icon: 'Money', menuId: 'reports:cash-flow' }
      },
      {
        path: 'reports/slow-moving',
        name: 'SlowMovingReport',
        component: () => import('@/views/reports/SlowMovingReport.vue'),
        meta: { title: '呆滞物料', icon: 'Warning', menuId: 'reports:slow-moving' }
      },
      {
        path: 'reports/timelog',
        name: 'TimelogReport',
        component: () => import('@/views/reports/TimelogReport.vue'),
        meta: { title: '工时报表', icon: 'Clock', menuId: 'reports:timelog' }
      },
      {
        path: 'reports/cost-analysis',
        name: 'CostAnalysis',
        component: () => import('@/views/reports/CostAnalysis.vue'),
        meta: { title: '成本报表', icon: 'Coin', menuId: 'reports:cost-analysis' }
      },
      // Production - 生产管理
      {
        path: 'production/processes',
        name: 'ProductionProcessList',
        component: () => import('@/views/production/ProcessList.vue'),
        meta: { title: '工艺工序', icon: 'Setting', menuId: 'production:processes' }
      },
      {
        path: 'production/plans',
        name: 'ProductionPlanList',
        component: () => import('@/views/production/PlanList.vue'),
        meta: { title: '排产计划', icon: 'Calendar', menuId: 'production:plans' }
      },
      {
        path: 'production/debug-records',
        name: 'DebugRecordList',
        component: () => import('@/views/production/DebugRecordList.vue'),
        meta: { title: '调试日志', icon: 'Cpu', menuId: 'production:debug-records' }
      },
      {
        path: 'production/inspections',
        name: 'QualityInspectionList',
        component: () => import('@/views/production/QualityInspectionList.vue'),
        meta: { title: '质检管理', icon: 'DocumentChecked', menuId: 'production:inspections' }
      },
      // Equipment - 设备台账
      {
        path: 'equipment/list',
        name: 'EquipmentList',
        component: () => import('@/views/equipment/EquipmentList.vue'),
        meta: { title: '设备管理', icon: 'Monitor', menuId: 'equipment:list' }
      },
      {
        path: 'equipment/fixtures',
        name: 'FixtureList',
        component: () => import('@/views/equipment/FixtureList.vue'),
        meta: { title: '工装管理', icon: 'Opportunity', menuId: 'equipment:fixtures' }
      },
      // Knowledge Base - 知识库
      {
        path: 'knowledge/articles',
        name: 'KnowledgeArticleList',
        component: () => import('@/views/knowledge/ArticleList.vue'),
        meta: { title: '技术文库', icon: 'Document', menuId: 'knowledge:articles' }
      },
      {
        path: 'knowledge/issues',
        name: 'TechnicalIssueList',
        component: () => import('@/views/knowledge/TechnicalIssueList.vue'),
        meta: { title: '问题库', icon: 'Warning', menuId: 'knowledge:issues' }
      },
      {
        path: 'knowledge/components',
        name: 'StandardComponentList',
        component: () => import('@/views/knowledge/StandardComponentList.vue'),
        meta: { title: '标准件库', icon: 'Box', menuId: 'knowledge:components' }
      },
      {
        path: 'projects/archives',
        name: 'ProjectArchiveList',
        component: () => import('@/views/projects/ArchiveList.vue'),
        meta: { title: '项目归档', icon: 'FolderChecked', menuId: 'projects:archives' }
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
        meta: { title: '待我审批', icon: 'Checked', menuId: 'workflow:tasks' }
      },
      {
        path: 'workflow/my-submissions',
        name: 'MySubmissions',
        component: () => import('@/views/workflow/MySubmissions.vue'),
        meta: { title: '我的申请', icon: 'Document', menuId: 'workflow:my-submissions' }
      },
      {
        path: 'workflow/config',
        name: 'WorkflowConfig',
        component: () => import('@/views/workflow/WorkflowConfig.vue'),
        meta: { title: '审批设置', icon: 'Setting', menuId: 'workflow:config' }
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
      {
        path: 'system/config',
        name: 'SystemConfig',
        component: () => import('@/views/system/SystemConfig.vue'),
        meta: { title: '系统配置', icon: 'Setting', menuId: 'system:config' }
      },
      {
        path: 'system/monitor',
        name: 'SystemMonitor',
        component: () => import('@/views/system/SystemMonitor.vue'),
        meta: { title: '系统监控', icon: 'Monitor', menuId: 'system:monitor' }
      },
      {
        path: 'system/backup',
        name: 'BackupManagement',
        component: () => import('@/views/system/BackupManagement.vue'),
        meta: { title: '数据备份', icon: 'FolderOpened', menuId: 'system:backup' }
      },
      {
        path: 'system/audit-analytics',
        name: 'AuditAnalytics',
        component: () => import('@/views/system/AuditAnalytics.vue'),
        meta: { title: '操作日志分析', icon: 'DataAnalysis', menuId: 'system:audit-analytics' }
      },
      {
        path: 'system/data-dictionary',
        name: 'DataDictionary',
        component: () => import('@/views/system/DataDictionary.vue'),
        meta: { title: '数据字典', icon: 'Collection', menuId: 'system:data-dictionary' }
      },
      {
        path: 'system/email-templates',
        name: 'EmailTemplates',
        component: () => import('@/views/system/EmailTemplates.vue'),
        meta: { title: '邮件模板', icon: 'Message', menuId: 'system:email-templates' }
      },
      {
        path: 'system/custom-fields',
        name: 'CustomFields',
        component: () => import('@/views/system/CustomFields.vue'),
        meta: { title: '自定义字段', icon: 'Grid', menuId: 'system:custom-fields' }
      },
      {
        path: 'sales/quote-templates',
        name: 'QuoteTemplates',
        component: () => import('@/views/sales/QuoteTemplates.vue'),
        meta: { title: '报价单模板', icon: 'Document', menuId: 'sales:quote-templates' }
      },
      {
        path: 'sales/contract-templates',
        name: 'ContractTemplates',
        component: () => import('@/views/sales/ContractTemplates.vue'),
        meta: { title: '合同模板', icon: 'Document', menuId: 'sales:contract-templates' }
      },
      // 客户跟进
      {
        path: 'masterdata/customer-followups',
        name: 'CustomerFollowUp',
        component: () => import('@/views/masterdata/CustomerFollowUp.vue'),
        meta: { title: '客户跟进', icon: 'ChatDotRound', menuId: 'masterdata:customer-followups' }
      },
      // 客户联系人
      {
        path: 'masterdata/customer-contacts',
        name: 'CustomerContactList',
        component: () => import('@/views/masterdata/CustomerContactList.vue'),
        meta: { title: '客户联系人', icon: 'UserFilled', menuId: 'masterdata:customer-contacts' }
      },
      // 采购预算
      {
        path: 'purchase/budgets',
        name: 'PurchaseBudgets',
        component: () => import('@/views/purchase/BudgetList.vue'),
        meta: { title: '采购预算', icon: 'Wallet', menuId: 'purchase:budgets' }
      },
      // 库存成本核算
      {
        path: 'inventory/cost-accounting',
        name: 'CostAccounting',
        component: () => import('@/views/inventory/CostAccounting.vue'),
        meta: { title: '库存成本', icon: 'Coin', menuId: 'inventory:cost-accounting' }
      },
      // 项目里程碑
      {
        path: 'projects/milestones',
        name: 'ProjectMilestones',
        component: () => import('@/views/projects/MilestoneList.vue'),
        meta: { title: '项目里程碑', icon: 'Flag', menuId: 'projects:milestones' }
      },
      // 销售业绩
      {
        path: 'sales/performance',
        name: 'SalesPerformance',
        component: () => import('@/views/sales/PerformanceAnalysis.vue'),
        meta: { title: '销售业绩', icon: 'TrendCharts', menuId: 'sales:performance' }
      },
      // 工单派工
      {
        path: 'projects/work-orders',
        name: 'WorkOrders',
        component: () => import('@/views/projects/WorkOrderList.vue'),
        meta: { title: '工单派工', icon: 'Tickets', menuId: 'projects:work-orders' }
      },
      // 设备点检
      {
        path: 'equipment/inspection',
        name: 'EquipmentInspection',
        component: () => import('@/views/equipment/InspectionList.vue'),
        meta: { title: '设备点检', icon: 'Checked', menuId: 'equipment:inspection' }
      },
      // 考勤管理
      {
        path: 'attendance',
        name: 'Attendance',
        component: () => import('@/views/accounts/Attendance.vue'),
        meta: { title: '考勤管理', icon: 'Clock', menuId: 'accounts:attendance' }
      },
      // 客户信用管理
      {
        path: 'masterdata/customer-credit',
        name: 'CustomerCredit',
        component: () => import('@/views/masterdata/CustomerCredit.vue'),
        meta: { title: '客户信用', icon: 'CreditCard', menuId: 'masterdata:credit' }
      },
      // MRP物料需求计划
      {
        path: 'inventory/mrp',
        name: 'MRPPlan',
        component: () => import('@/views/inventory/MRPPlan.vue'),
        meta: { title: 'MRP计划', icon: 'List', menuId: 'inventory:mrp' }
      },
      // 项目预警
      {
        path: 'projects/alerts',
        name: 'ProjectAlerts',
        component: () => import('@/views/projects/AlertList.vue'),
        meta: { title: '风险预警', icon: 'Warning', menuId: 'projects:alerts' }
      },
      // 库存预警
      {
        path: 'inventory/stock-alerts',
        name: 'StockAlerts',
        component: () => import('@/views/inventory/StockAlert.vue'),
        meta: { title: '库存预警', icon: 'Warning', menuId: 'inventory:alerts' }
      },
      // 销售分析
      {
        path: 'sales/analysis',
        name: 'SalesAnalysis',
        component: () => import('@/views/sales/SalesAnalysis.vue'),
        meta: { title: '销售分析', icon: 'DataAnalysis', menuId: 'sales:analysis' }
      },
      // PLM - 需求管理
      {
        path: 'plm/requirements',
        name: 'Requirements',
        component: () => import('@/views/plm/RequirementList.vue'),
        meta: { title: '技术需求', icon: 'Document', menuId: 'plm:requirements' }
      },
      {
        path: 'plm/proposals',
        name: 'Proposals',
        component: () => import('@/views/plm/ProposalList.vue'),
        meta: { title: '方案评审', icon: 'Edit', menuId: 'plm:proposals' }
      },
      // PLM - 技术协议
      {
        path: 'plm/agreements',
        name: 'TechnicalAgreements',
        component: () => import('@/views/plm/TechnicalAgreementList.vue'),
        meta: { title: '技术协议', icon: 'Document', menuId: 'plm:agreements' }
      },
      // 项目 - 设备档案
      {
        path: 'projects/equipment-archives',
        name: 'EquipmentArchives',
        component: () => import('@/views/projects/EquipmentArchiveList.vue'),
        meta: { title: '设备台账', icon: 'Files', menuId: 'equipment:archives' }
      },
      // 项目 - 验收管理
      {
        path: 'projects/acceptances',
        name: 'Acceptances',
        component: () => import('@/views/projects/AcceptanceList.vue'),
        meta: { title: '项目验收', icon: 'Finished', menuId: 'projects:acceptances' }
      },
      // 生产 - 序列号管理
      {
        path: 'production/serial-numbers',
        name: 'SerialNumbers',
        component: () => import('@/views/production/SerialNumberList.vue'),
        meta: { title: '序列号管理', icon: 'List', menuId: 'production:serial-numbers' }
      },
      // MES - APS排程
      {
        path: 'mes/scheduling',
        name: 'APSScheduling',
        component: () => import('@/views/mes/APSScheduling.vue'),
        meta: { title: '智能排程', icon: 'Calendar', menuId: 'mes:scheduling' }
      },
      {
        path: 'mes/kanban',
        name: 'ProductionKanban',
        component: () => import('@/views/mes/Kanban.vue'),
        meta: { title: '生产看板', icon: 'Monitor', menuId: 'mes:kanban' }
      },
      {
        path: 'mes/andon',
        name: 'AndonSystem',
        component: () => import('@/views/mes/AndonSystem.vue'),
        meta: { title: '异常报警', icon: 'Bell', menuId: 'mes:andon' }
      },
      {
        path: 'mes/data-acquisition',
        name: 'DataAcquisition',
        component: () => import('@/views/mes/DataAcquisition.vue'),
        meta: { title: '数据采集', icon: 'Connection', menuId: 'mes:data-acquisition' }
      },
      // PLM - 3D模型预览
      {
        path: 'plm/model-viewer',
        name: 'ModelViewer',
        component: () => import('@/views/plm/ModelViewer.vue'),
        meta: { title: '3D模型预览', icon: 'View', menuId: 'plm:model-viewer' }
      },
      {
        path: 'plm/cad-bom-import',
        name: 'CADBOMImport',
        component: () => import('@/views/plm/CreoBOMImport.vue'),
        meta: { title: 'Creo导入', icon: 'Upload', menuId: 'plm:cad-bom' }
      },
      {
        path: 'plm/bom-compare',
        name: 'BOMCompare',
        component: () => import('@/views/plm/BOMCompare.vue'),
        meta: { title: 'BOM版本对比', icon: 'Connection', menuId: 'plm:bom-compare' }
      },
      {
        path: 'projects/batch-drawing-import',
        name: 'BatchDrawingImport',
        component: () => import('@/views/projects/BatchDrawingImport.vue'),
        meta: { title: '批量图纸导入', icon: 'FolderOpened', menuId: 'design:batch-drawing' }
      },
      {
        path: 'projects/drawing-bom-link',
        name: 'DrawingBOMLink',
        component: () => import('@/views/projects/DrawingBOMLink.vue'),
        meta: { title: '图纸-BOM关联', icon: 'Connection', menuId: 'design:drawing-bom-link' }
      },
      // OA - 日程会议
      {
        path: 'oa/schedule',
        name: 'Schedule',
        component: () => import('@/views/oa/Schedule.vue'),
        meta: { title: '日程管理', icon: 'Calendar', menuId: 'oa:schedule' }
      },
      {
        path: 'oa/meeting',
        name: 'Meeting',
        component: () => import('@/views/oa/Meeting.vue'),
        meta: { title: '会议管理', icon: 'VideoCamera', menuId: 'oa:meeting' }
      },
      {
        path: 'oa/im',
        name: 'InstantMessage',
        component: () => import('@/views/oa/IMChat.vue'),
        meta: { title: '即时通讯', icon: 'ChatDotRound', menuId: 'oa:im' }
      },
      // OA - 考勤管理
      {
        path: 'oa/attendance',
        name: 'OaAttendance',
        component: () => import('@/views/oa/Attendance.vue'),
        meta: { title: '考勤打卡', icon: 'Clock', menuId: 'oa:attendance' }
      },
      {
        path: 'oa/attendance-import',
        name: 'AttendanceImport',
        component: () => import('@/views/oa/AttendanceImport.vue'),
        meta: { title: '考勤导入', icon: 'Upload', menuId: 'oa:attendance-import' }
      },
      {
        path: 'oa/leave',
        name: 'LeaveRequest',
        component: () => import('@/views/oa/LeaveList.vue'),
        meta: { title: '请假申请', icon: 'Document', menuId: 'oa:leave' }
      },
      // OA - 公告通知
      {
        path: 'oa/announcement',
        name: 'Announcement',
        component: () => import('@/views/oa/AnnouncementList.vue'),
        meta: { title: '公告通知', icon: 'Bell', menuId: 'oa:announcement' }
      },
      // OA - 车辆管理
      {
        path: 'oa/vehicles',
        name: 'VehicleList',
        component: () => import('@/views/oa/VehicleList.vue'),
        meta: { title: '车辆管理', icon: 'Van', menuId: 'oa:vehicles' }
      },
      {
        path: 'oa/vehicle-request',
        name: 'VehicleRequest',
        component: () => import('@/views/oa/VehicleRequestList.vue'),
        meta: { title: '用车申请', icon: 'Tickets', menuId: 'oa:vehicle-request' }
      },
      // OA - 资产管理
      {
        path: 'oa/assets',
        name: 'OAAssetList',
        component: () => import('@/views/oa/AssetList.vue'),
        meta: { title: '资产管理', icon: 'Box', menuId: 'oa:assets' }
      },
      // 固定资产
      {
        path: 'finance/assets',
        name: 'FixedAssets',
        component: () => import('@/views/finance/AssetList.vue'),
        meta: { title: '固定资产', icon: 'OfficeBuilding', menuId: 'finance:assets' }
      },
      // 设备维护日历
      {
        path: 'equipment/maintenance',
        name: 'MaintenanceCalendar',
        component: () => import('@/views/equipment/MaintenanceCalendar.vue'),
        meta: { title: '维护日历', icon: 'Calendar', menuId: 'equipment:maintenance' }
      },
      // 设备OEE
      {
        path: 'equipment/oee',
        name: 'EquipmentOEE',
        component: () => import('@/views/equipment/OEEAnalysis.vue'),
        meta: { title: 'OEE分析', icon: 'DataAnalysis', menuId: 'equipment:oee' }
      },
      // 图纸版本管理
      {
        path: 'projects/drawing-versions',
        name: 'DrawingVersionList',
        component: () => import('@/views/projects/DrawingVersionList.vue'),
        meta: { title: '图纸版本', icon: 'Document', menuId: 'projects:drawing-versions' }
      },
      // BOM成本卷积
      {
        path: 'projects/bom-cost',
        name: 'BOMCostRollup',
        component: () => import('@/views/projects/BOMCostRollup.vue'),
        meta: { title: 'BOM成本分析', icon: 'Money', menuId: 'projects:bom-cost' }
      },
      // 安装调试任务
      {
        path: 'projects/installation-tasks',
        name: 'InstallationTaskList',
        component: () => import('@/views/projects/InstallationTaskList.vue'),
        meta: { title: '安装调试', icon: 'SetUp', menuId: 'projects:installation' }
      },
      {
        path: 'projects/installation-task/:id',
        name: 'InstallationTaskDetail',
        component: () => import('@/views/projects/InstallationTaskDetail.vue'),
        meta: { title: '安装详情', menuId: 'projects:installation' }
      },
      // 可配置报表
      {
        path: 'reports/builder',
        name: 'ReportBuilder',
        component: () => import('@/views/reports/ReportBuilder.vue'),
        meta: { title: '报表构建器', icon: 'DataBoard', menuId: 'reports:builder' }
      },
      // 预测分析
      {
        path: 'reports/prediction',
        name: 'PredictiveAnalysis',
        component: () => import('@/views/reports/PredictiveAnalysis.vue'),
        meta: { title: '智能预测', icon: 'TrendCharts', menuId: 'reports:prediction' }
      },
      // 风险预警
      {
        path: 'reports/risk-alerts',
        name: 'RiskAlertList',
        component: () => import('@/views/reports/RiskAlertList.vue'),
        meta: { title: '风险预警', icon: 'WarningFilled', menuId: 'reports:risk-alerts' }
      },
      // 备件预测
      {
        path: 'inventory/spare-part-prediction',
        name: 'SparePartPrediction',
        component: () => import('@/views/inventory/SparePartPrediction.vue'),
        meta: { title: '备件预测', icon: 'Histogram', menuId: 'inventory:spare-part-prediction' }
      },
      // 系统公告
      {
        path: 'system/announcements',
        name: 'Announcements',
        component: () => import('@/views/system/Announcement.vue'),
        meta: { title: '系统公告', icon: 'Bell', menuId: 'system:announcements' }
      },
      // 非标自动化行业增强功能
      // 非标报价估算
      {
        path: 'sales/quote-estimations',
        name: 'QuoteEstimation',
        component: () => import('@/views/sales/QuoteEstimation.vue'),
        meta: { title: '报价估算', icon: 'Calculator', menuId: 'sales:quote-estimation' }
      },
      {
        path: 'sales/quote-estimation/:id',
        name: 'QuoteEstimationDetail',
        component: () => import('@/views/sales/QuoteEstimationDetail.vue'),
        meta: { title: '估算详情', menuId: 'sales:quote-estimation' }
      },
      // 客户培训管理
      {
        path: 'sales/training-plans',
        name: 'TrainingPlanList',
        component: () => import('@/views/sales/TrainingPlanList.vue'),
        meta: { title: '培训计划', icon: 'Reading', menuId: 'sales:training' }
      },
      {
        path: 'sales/training-courses',
        name: 'TrainingCourseList',
        component: () => import('@/views/sales/TrainingCourseList.vue'),
        meta: { title: '培训课程', icon: 'Notebook', menuId: 'sales:training' }
      },
      // 现场服务派工
      {
        path: 'projects/service-orders',
        name: 'ServiceOrderList',
        component: () => import('@/views/projects/ServiceOrder.vue'),
        meta: { title: '售后服务', icon: 'Van', menuId: 'aftersales:service' }
      },
      {
        path: 'projects/service-order/:id',
        name: 'ServiceOrderDetail',
        component: () => import('@/views/projects/ServiceOrderDetail.vue'),
        meta: { title: '服务详情', menuId: 'aftersales:service' }
      },
      {
        path: 'projects/technicians',
        name: 'TechnicianList',
        component: () => import('@/views/projects/TechnicianList.vue'),
        meta: { title: '技术人员', icon: 'User', menuId: 'aftersales:service' }
      },
      // 项目成本看板
      {
        path: 'projects/cost-dashboard',
        name: 'ProjectCostDashboard',
        component: () => import('@/views/projects/CostDashboard.vue'),
        meta: { title: '成本分析', icon: 'Coin', menuId: 'projects:cost' }
      },
      {
        path: 'projects/cost-records',
        name: 'ProjectCostRecords',
        component: () => import('@/views/projects/CostRecordList.vue'),
        meta: { title: '成本记录', icon: 'Document', menuId: 'projects:cost' }
      },
      // 高级成本分析（非标增强）
      {
        path: 'projects/advanced-cost-analysis',
        name: 'AdvancedCostAnalysis',
        component: () => import('@/views/projects/AdvancedCostAnalysis.vue'),
        meta: { title: '成本分析', icon: 'TrendCharts', menuId: 'projects:cost' }
      },
      {
        path: 'projects/cost-comparison',
        name: 'CostComparison',
        component: () => import('@/views/projects/CostComparison.vue'),
        meta: { title: '成本对比', icon: 'DataAnalysis', menuId: 'projects:cost' }
      },
      {
        path: 'projects/labor-rates',
        name: 'LaborRates',
        component: () => import('@/views/projects/LaborRateList.vue'),
        meta: { title: '工时费率', icon: 'Money', menuId: 'projects:cost' }
      },
      // 设备远程运维
      {
        path: 'projects/equipment-monitoring',
        name: 'EquipmentMonitoring',
        component: () => import('@/views/projects/EquipmentMonitoring.vue'),
        meta: { title: '设备监控', icon: 'Monitor', menuId: 'equipment:monitoring' }
      },
      {
        path: 'projects/equipment-alarms',
        name: 'EquipmentAlarmList',
        component: () => import('@/views/projects/EquipmentAlarmList.vue'),
        meta: { title: '设备报警', icon: 'Warning', menuId: 'equipment:monitoring' }
      },
      {
        path: 'projects/diagnostic-sessions',
        name: 'DiagnosticSessionList',
        component: () => import('@/views/projects/DiagnosticSessionList.vue'),
        meta: { title: '远程诊断', icon: 'Service', menuId: 'equipment:monitoring' }
      },
      // 工艺路线管理
      {
        path: 'production/routing-templates',
        name: 'RoutingTemplateList',
        component: () => import('@/views/production/RoutingTemplate.vue'),
        meta: { title: '工艺路线', icon: 'Guide', menuId: 'production:routing' }
      },
      {
        path: 'production/routing-template/:id',
        name: 'RoutingTemplateDetail',
        component: () => import('@/views/production/RoutingTemplateDetail.vue'),
        meta: { title: '工艺详情', menuId: 'production:routing' }
      },
      {
        path: 'production/work-stations',
        name: 'WorkStationList',
        component: () => import('@/views/production/WorkStationList.vue'),
        meta: { title: '工位管理', icon: 'OfficeBuilding', menuId: 'production:workstations' }
      },
      // 3D装配指导
      {
        path: 'production/assembly-guides',
        name: 'AssemblyGuideList',
        component: () => import('@/views/production/AssemblyGuideList.vue'),
        meta: { title: '装配作业', icon: 'Connection', menuId: 'production:assembly' }
      },
      {
        path: 'production/assembly-guide/:id',
        name: 'AssemblyGuideDetail',
        component: () => import('@/views/production/AssemblyGuideDetail.vue'),
        meta: { title: '装配详情', menuId: 'production:assembly' }
      },
      // 备件管理
      {
        path: 'inventory/spare-parts',
        name: 'SparePartList',
        component: () => import('@/views/inventory/SparePartList.vue'),
        meta: { title: '备件管理', icon: 'Box', menuId: 'inventory:spare-parts' }
      },
      {
        path: 'inventory/spare-part-alerts',
        name: 'SparePartAlertList',
        component: () => import('@/views/inventory/SparePartAlertList.vue'),
        meta: { title: '备件预警', icon: 'Warning', menuId: 'inventory:spare-parts' }
      },
      // 进销存数据准确性
      {
        path: 'inventory/data-accuracy',
        name: 'DataAccuracy',
        component: () => import('@/views/inventory/DataAccuracy.vue'),
        meta: { title: '数据准确性', icon: 'Checked', menuId: 'inventory:data-accuracy' }
      },
      {
        path: 'inventory/reconciliation/:id',
        name: 'ReconciliationDetail',
        component: () => import('@/views/inventory/ReconciliationDetail.vue'),
        meta: { title: '对账详情', menuId: 'inventory:data-accuracy' }
      },
      // 外协加工增强
      {
        path: 'purchase/outsource-tracking',
        name: 'OutsourceTracking',
        component: () => import('@/views/purchase/OutsourceTracking.vue'),
        meta: { title: '外协跟踪', icon: 'Setting', menuId: 'purchase:outsource' }
      },
      {
        path: 'purchase/outsource-capabilities',
        name: 'OutsourceCapabilityList',
        component: () => import('@/views/purchase/OutsourceCapabilityList.vue'),
        meta: { title: '外协商能力', icon: 'Opportunity', menuId: 'purchase:outsource' }
      },
      // 供应链协同
      {
        path: 'purchase/rfq-collaborations',
        name: 'RFQCollaborationList',
        component: () => import('@/views/purchase/RFQCollaborationList.vue'),
        meta: { title: '询报价协同', icon: 'ChatDotSquare', menuId: 'purchase:collaboration' }
      },
      {
        path: 'purchase/delivery-collaborations',
        name: 'DeliveryCollaborationList',
        component: () => import('@/views/purchase/DeliveryCollaborationList.vue'),
        meta: { title: '交期协同', icon: 'Van', menuId: 'purchase:collaboration' }
      },
      // 行业报表
      {
        path: 'reports/project-profitability',
        name: 'ProjectProfitabilityReport',
        component: () => import('@/views/reports/ProjectProfitabilityReport.vue'),
        meta: { title: '项目毛利分析', icon: 'TrendCharts', menuId: 'reports:project-profitability' }
      },
      {
        path: 'reports/equipment-lifecycle',
        name: 'EquipmentLifecycleReport',
        component: () => import('@/views/reports/EquipmentLifecycleReport.vue'),
        meta: { title: '设备生命周期', icon: 'Timer', menuId: 'reports:equipment-lifecycle' }
      },
      {
        path: 'reports/capacity-utilization',
        name: 'CapacityUtilizationReport',
        component: () => import('@/views/reports/CapacityUtilizationReport.vue'),
        meta: { title: '产能利用率', icon: 'DataAnalysis', menuId: 'reports:capacity-utilization' }
      },
      {
        path: 'reports/customer-value',
        name: 'CustomerValueReport',
        component: () => import('@/views/reports/CustomerValueReport.vue'),
        meta: { title: '客户价值分析', icon: 'UserFilled', menuId: 'reports:customer-value' }
      },
      // 供应商协同门户
      {
        path: 'purchase/supplier-portal',
        name: 'SupplierPortal',
        component: () => import('@/views/purchase/SupplierPortal.vue'),
        meta: { title: '供应商协同', icon: 'Connection', menuId: 'purchase:portal' }
      },
      // 技术文档协同
      {
        path: 'projects/tech-documents',
        name: 'TechDocumentList',
        component: () => import('@/views/projects/TechDocumentList.vue'),
        meta: { title: '技术文档', icon: 'Document', menuId: 'design:documents' }
      },
      // 售后服务管理
      {
        path: 'sales/service-contracts',
        name: 'ServiceContractList',
        component: () => import('@/views/sales/ServiceContractList.vue'),
        meta: { title: '服务合同', icon: 'Tickets', menuId: 'sales:service' }
      },
      {
        path: 'sales/service-requests',
        name: 'ServiceRequestList',
        component: () => import('@/views/sales/ServiceRequestList.vue'),
        meta: { title: '服务请求', icon: 'Service', menuId: 'sales:service' }
      },
      {
        path: 'sales/preventive-maintenance',
        name: 'PreventiveMaintenanceList',
        component: () => import('@/views/sales/PreventiveMaintenanceList.vue'),
        meta: { title: '预防维护', icon: 'Tools', menuId: 'sales:service' }
      },
      {
        path: 'sales/knowledge-base',
        name: 'KnowledgeBaseList',
        component: () => import('@/views/sales/KnowledgeBaseList.vue'),
        meta: { title: '知识库', icon: 'Reading', menuId: 'sales:service' }
      },
      // 报价版本管理
      {
        path: 'sales/quote-versions',
        name: 'QuoteVersionList',
        component: () => import('@/views/sales/QuoteVersionList.vue'),
        meta: { title: '报价版本', icon: 'PriceTag', menuId: 'sales:quote' }
      },
      // 产能资源规划
      {
        path: 'production/capacity-planning',
        name: 'CapacityPlanning',
        component: () => import('@/views/production/CapacityPlanning.vue'),
        meta: { title: '产能规划', icon: 'Cpu', menuId: 'production:capacity' }
      },
      {
        path: 'production/resource-types',
        name: 'ResourceTypeList',
        component: () => import('@/views/production/ResourceTypeList.vue'),
        meta: { title: '资源类型', icon: 'Files', menuId: 'production:resources' }
      },
      // ====== 非标自动化行业增强 ======
      // 有限产能排程
      {
        path: 'production/finite-capacity',
        name: 'FiniteCapacityList',
        component: () => import('@/views/production/FiniteCapacityList.vue'),
        meta: { title: '有限产能排程', icon: 'Timer', menuId: 'production:finite-capacity' }
      },
      // 设备能力矩阵
      {
        path: 'production/equipment-capability',
        name: 'EquipmentCapabilityMatrix',
        component: () => import('@/views/production/EquipmentCapabilityMatrix.vue'),
        meta: { title: '设备能力矩阵', icon: 'Grid', menuId: 'production:equipment-capability' }
      },
      // 看板WIP管理
      {
        path: 'production/kanban-wip',
        name: 'KanbanWIPManagement',
        component: () => import('@/views/production/KanbanWIPManagement.vue'),
        meta: { title: 'WIP管理', icon: 'Stopwatch', menuId: 'production:kanban-wip' }
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
  history: createWebHistory('/erp'),
  routes
})

// Navigation guard
router.beforeEach(async (to, from, next) => {
  const userStore = useUserStore()
  const permissionStore = usePermissionStore()
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
        // 清理无效状态
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        next('/login')
        return
      }
    }

    // 二次验证：确认 profile 确实加载成功
    if (!userStore.userInfo) {
      next('/login')
      return
    }

    // 公共页面（如个人中心、修改密码）不检查权限
    if (to.meta.public) {
      next()
      return
    }

    // 超级管理员跳过权限检查
    if (userStore.userInfo?.is_superuser) {
      next()
      return
    }

    // 检查权限：优先使用 permission 字段，回退到 menuId 保持兼容
    const requiredPermission = to.meta.permission || to.meta.menuId
    if (requiredPermission && !permissionStore.hasPermission(requiredPermission)) {
      console.warn(`Access denied to ${to.path}, missing permission: ${requiredPermission}`)
      // 避免无限重定向：dashboard是默认落地页，无权限时直接放行
      if (to.path === '/dashboard') { next(); return }
      next('/dashboard')
      return
    }
  }

  next()
})

// 当懒加载组件的 chunk 文件加载失败时（通常因为新版本部署后旧 chunk 不存在），
// 自动刷新页面以获取最新的 index.html 和正确的 chunk 引用
router.onError((error) => {
  const isChunkError = error.message && (
    error.message.includes('Failed to fetch dynamically imported module') ||
    error.message.includes('Loading chunk') ||
    error.message.includes('Loading CSS chunk') ||
    error.message.includes('Unable to preload CSS')
  )
  if (isChunkError) {
    console.warn('Chunk load error detected, reloading page...', error.message)
    window.location.reload()
  }
})

export default router

