import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '@/stores/user'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { requiresAuth: false }
  },
  // 兼容旧链接（避免用户误以为路径错了）
  {
    path: '/masterdata/items',
    redirect: '/items'
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
      {
        path: 'code-rules',
        name: 'CodeRuleList',
        component: () => import('@/views/system/CodeRuleList.vue'),
        meta: { title: '编码规则', icon: 'SetUp', menuId: 'system:code-rules' }
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
      // Bug跟踪
      {
        path: 'projects/bugs',
        name: 'BugList',
        component: () => import('@/views/projects/BugList.vue'),
        meta: { title: 'Bug跟踪', icon: 'Warning', menuId: 'projects:bugs' }
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
        meta: { title: '图纸管理', icon: 'Picture', menuId: 'projects:drawings' }
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
        meta: { title: '比价分析', icon: 'DataAnalysis', menuId: 'purchase:comparisons' }
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
        meta: { title: '供应商评价', icon: 'Star', menuId: 'purchase:evaluations' }
      },
      {
        path: 'purchase/blacklist',
        name: 'SupplierBlacklist',
        component: () => import('@/views/purchase/SupplierBlacklist.vue'),
        meta: { title: '供应商黑名单', icon: 'Warning', menuId: 'purchase:blacklist' }
      },
      // Sales - CRM
      {
        path: 'sales/leads',
        name: 'LeadList',
        component: () => import('@/views/sales/LeadList.vue'),
        meta: { title: '销售线索', icon: 'User', menuId: 'sales:leads' }
      },
      {
        path: 'sales/opportunities',
        name: 'OpportunityList',
        component: () => import('@/views/sales/OpportunityList.vue'),
        meta: { title: '销售商机', icon: 'Opportunity', menuId: 'sales:opportunities' }
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
      {
        path: 'inventory/requisitions',
        name: 'RequisitionList',
        component: () => import('@/views/inventory/RequisitionList.vue'),
        meta: { title: '生产领料', icon: 'TakeawayBox', menuId: 'inventory:requisitions' }
      },
      {
        path: 'inventory/returns',
        name: 'ReturnList',
        component: () => import('@/views/inventory/ReturnList.vue'),
        meta: { title: '生产退料', icon: 'RefreshLeft', menuId: 'inventory:returns' }
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
      {
        path: 'finance/collection-plans',
        name: 'CollectionPlanList',
        component: () => import('@/views/finance/CollectionPlanList.vue'),
        meta: { title: '回款计划', icon: 'Money', menuId: 'finance:collection' }
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
      {
        path: 'reports/timelog',
        name: 'TimelogReport',
        component: () => import('@/views/reports/TimelogReport.vue'),
        meta: { title: '工时统计', icon: 'Clock', menuId: 'reports:timelog' }
      },
      {
        path: 'reports/cost-analysis',
        name: 'CostAnalysis',
        component: () => import('@/views/reports/CostAnalysis.vue'),
        meta: { title: '项目成本分析', icon: 'Coin', menuId: 'reports:cost-analysis' }
      },
      // Production - 生产管理
      {
        path: 'production/processes',
        name: 'ProductionProcessList',
        component: () => import('@/views/production/ProcessList.vue'),
        meta: { title: '生产工序', icon: 'Setting', menuId: 'production:processes' }
      },
      {
        path: 'production/plans',
        name: 'ProductionPlanList',
        component: () => import('@/views/production/PlanList.vue'),
        meta: { title: '生产计划', icon: 'Calendar', menuId: 'production:plans' }
      },
      {
        path: 'production/debug-records',
        name: 'DebugRecordList',
        component: () => import('@/views/production/DebugRecordList.vue'),
        meta: { title: '调试记录', icon: 'Cpu', menuId: 'production:debug-records' }
      },
      {
        path: 'production/inspections',
        name: 'QualityInspectionList',
        component: () => import('@/views/production/QualityInspectionList.vue'),
        meta: { title: '质量检验', icon: 'DocumentChecked', menuId: 'production:inspections' }
      },
      // Equipment - 设备台账
      {
        path: 'equipment/list',
        name: 'EquipmentList',
        component: () => import('@/views/equipment/EquipmentList.vue'),
        meta: { title: '设备台账', icon: 'Monitor', menuId: 'equipment:list' }
      },
      {
        path: 'equipment/fixtures',
        name: 'FixtureList',
        component: () => import('@/views/equipment/FixtureList.vue'),
        meta: { title: '工装夹具', icon: 'Opportunity', menuId: 'equipment:fixtures' }
      },
      // Knowledge Base - 知识库
      {
        path: 'knowledge/articles',
        name: 'KnowledgeArticleList',
        component: () => import('@/views/knowledge/ArticleList.vue'),
        meta: { title: '知识文章', icon: 'Document', menuId: 'knowledge:articles' }
      },
      {
        path: 'knowledge/issues',
        name: 'TechnicalIssueList',
        component: () => import('@/views/knowledge/TechnicalIssueList.vue'),
        meta: { title: '技术问题', icon: 'Warning', menuId: 'knowledge:issues' }
      },
      {
        path: 'knowledge/components',
        name: 'StandardComponentList',
        component: () => import('@/views/knowledge/StandardComponentList.vue'),
        meta: { title: '标准部件库', icon: 'Box', menuId: 'knowledge:components' }
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
        meta: { title: '工单管理', icon: 'Tickets', menuId: 'projects:work-orders' }
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
        meta: { title: '项目预警', icon: 'Warning', menuId: 'projects:alerts' }
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
        meta: { title: '需求管理', icon: 'Document', menuId: 'plm:requirements' }
      },
      {
        path: 'plm/proposals',
        name: 'Proposals',
        component: () => import('@/views/plm/ProposalList.vue'),
        meta: { title: '方案设计', icon: 'Edit', menuId: 'plm:proposals' }
      },
      {
        path: 'plm/configurator',
        name: 'ProductConfigurator',
        component: () => import('@/views/plm/ProductConfigurator.vue'),
        meta: { title: '产品配置器', icon: 'Setting', menuId: 'plm:configurator' }
      },
      // MES - APS排程
      {
        path: 'mes/scheduling',
        name: 'APSScheduling',
        component: () => import('@/views/mes/APSScheduling.vue'),
        meta: { title: 'APS排程', icon: 'Calendar', menuId: 'mes:scheduling' }
      },
      {
        path: 'mes/kanban',
        name: 'ProductionKanban',
        component: () => import('@/views/mes/Kanban.vue'),
        meta: { title: '电子看板', icon: 'Monitor', menuId: 'mes:kanban' }
      },
      {
        path: 'mes/traceability',
        name: 'Traceability',
        component: () => import('@/views/mes/Traceability.vue'),
        meta: { title: '追溯管理', icon: 'Search', menuId: 'mes:traceability' }
      },
      {
        path: 'mes/spc',
        name: 'SPCControl',
        component: () => import('@/views/mes/SPCControl.vue'),
        meta: { title: 'SPC统计过程控制', icon: 'DataLine', menuId: 'mes:spc' }
      },
      {
        path: 'mes/andon',
        name: 'AndonSystem',
        component: () => import('@/views/mes/AndonSystem.vue'),
        meta: { title: '安灯系统', icon: 'Bell', menuId: 'mes:andon' }
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
      // 系统公告
      {
        path: 'system/announcements',
        name: 'Announcements',
        component: () => import('@/views/system/Announcement.vue'),
        meta: { title: '系统公告', icon: 'Bell', menuId: 'system:announcements' }
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
            'system:code-rules': '/code-rules',
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

