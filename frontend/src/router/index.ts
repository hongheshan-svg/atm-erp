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
  {
    path: '/login/callback',
    name: 'LoginCallback',
    component: () => import('@/views/LoginCallback.vue'),
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
      // ====== Group 1: Dashboard ======
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/Dashboard.vue'),
        meta: { title: '工作台', icon: 'DataAnalysis', menuId: 'dashboard' }
      },

      // ====== Group 2: Projects 项目管理 ======
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
        meta: { title: '任务看板', icon: 'List', menuId: 'projects:task' }
      },
      {
        path: 'projects/members',
        name: 'MemberList',
        component: () => import('@/views/projects/MemberList.vue'),
        meta: { title: '成员管理', icon: 'User', menuId: 'projects:member' }
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
        meta: { title: '工时记录', icon: 'Clock', menuId: 'projects:timelog' }
      },
      {
        path: 'projects/gantt',
        name: 'ProjectGantt',
        component: () => import('@/views/projects/ProjectGantt.vue'),
        meta: { title: '甘特图', icon: 'Calendar', menuId: 'projects:gantt' }
      },
      // Bug跟踪
      {
        path: 'projects/bugs',
        name: 'BugList',
        component: () => import('@/views/projects/BugList.vue'),
        meta: { title: '问题追踪', icon: 'Warning', menuId: 'projects:bug' }
      },
      {
        path: 'projects/bugs/:id',
        name: 'BugDetail',
        component: () => import('@/views/projects/BugDetail.vue'),
        meta: { title: 'Bug详情', menuId: 'projects:bug' }
      },
      {
        path: 'projects/archives',
        name: 'ProjectArchiveList',
        component: () => import('@/views/projects/ArchiveList.vue'),
        meta: { title: '项目归档', icon: 'FolderChecked', menuId: 'projects:archive' }
      },
      // 项目里程碑
      {
        path: 'projects/milestones',
        name: 'ProjectMilestones',
        component: () => import('@/views/projects/MilestoneList.vue'),
        meta: { title: '项目里程碑', icon: 'Flag', menuId: 'projects:milestone' }
      },
      // 项目预警
      {
        path: 'projects/alerts',
        name: 'ProjectAlerts',
        component: () => import('@/views/projects/AlertList.vue'),
        meta: { title: '风险预警', icon: 'Warning', menuId: 'projects:alert' }
      },
      // 工单派工
      {
        path: 'projects/work-orders',
        name: 'WorkOrders',
        component: () => import('@/views/projects/WorkOrderList.vue'),
        meta: { title: '工单派工', icon: 'Tickets', menuId: 'projects:work_order' }
      },
      // 项目验收管理
      {
        path: 'projects/acceptances',
        name: 'Acceptances',
        component: () => import('@/views/projects/AcceptanceList.vue'),
        meta: { title: '项目验收', icon: 'Finished', menuId: 'projects:acceptance' }
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
      // BOM成本卷积
      {
        path: 'projects/bom-cost',
        name: 'BOMCostRollup',
        component: () => import('@/views/projects/BOMCostRollup.vue'),
        meta: { title: 'BOM成本分析', icon: 'Money', menuId: 'projects:bom' }
      },
      // 售后服务 (projects:service)
      {
        path: 'projects/service-orders',
        name: 'ServiceOrderList',
        component: () => import('@/views/projects/ServiceOrder.vue'),
        meta: { title: '售后服务', icon: 'Headset', menuId: 'projects:service' }
      },
      {
        path: 'projects/service-order/:id',
        name: 'ServiceOrderDetail',
        component: () => import('@/views/projects/ServiceOrderDetail.vue'),
        meta: { title: '服务详情', menuId: 'projects:service' }
      },
      {
        path: 'projects/technicians',
        name: 'TechnicianList',
        component: () => import('@/views/projects/TechnicianList.vue'),
        meta: { title: '技术人员', icon: 'User', menuId: 'projects:service' }
      },
      // After Sales - 售后工单
      {
        path: 'aftersales/orders',
        name: 'AfterSalesOrderList',
        component: () => import('@/views/aftersales/OrderList.vue'),
        meta: { title: '售后工单', icon: 'Service', menuId: 'projects:service' }
      },
      {
        path: 'aftersales/orders/:id',
        name: 'AfterSalesOrderDetail',
        component: () => import('@/views/aftersales/OrderDetail.vue'),
        meta: { title: '工单详情', menuId: 'projects:service' }
      },

      // ====== Group 3: Sales 销售管理 ======
      // 客户管理 (moved from masterdata)
      {
        path: 'masterdata/customers',
        name: 'CustomerList',
        component: () => import('@/views/masterdata/CustomerList.vue'),
        meta: { title: '客户管理', icon: 'Avatar', menuId: 'sales:customer' }
      },
      // 客户跟进
      {
        path: 'masterdata/customer-followups',
        name: 'CustomerFollowUp',
        component: () => import('@/views/masterdata/CustomerFollowUp.vue'),
        meta: { title: '客户跟进', icon: 'ChatDotRound', menuId: 'sales:customer' }
      },
      // 客户联系人
      {
        path: 'masterdata/customer-contacts',
        name: 'CustomerContactList',
        component: () => import('@/views/masterdata/CustomerContactList.vue'),
        meta: { title: '客户联系人', icon: 'UserFilled', menuId: 'sales:customer' }
      },
      // 客户信用管理
      {
        path: 'masterdata/customer-credit',
        name: 'CustomerCredit',
        component: () => import('@/views/masterdata/CustomerCredit.vue'),
        meta: { title: '客户信用', icon: 'CreditCard', menuId: 'sales:customer' }
      },
      // Sales - CRM
      {
        path: 'sales/crm-dashboard',
        name: 'CRMDashboard',
        component: () => import('@/views/sales/CRMDashboard.vue'),
        meta: { title: '客户总览', icon: 'DataBoard', menuId: 'sales:lead' }
      },
      {
        path: 'sales/leads',
        name: 'LeadList',
        component: () => import('@/views/sales/LeadList.vue'),
        meta: { title: '商机线索', icon: 'User', menuId: 'sales:lead' }
      },
      {
        path: 'sales/opportunities',
        name: 'OpportunityList',
        component: () => import('@/views/sales/OpportunityList.vue'),
        meta: { title: '销售机会', icon: 'Opportunity', menuId: 'sales:lead' }
      },
      // Sales - 报价
      {
        path: 'sales/quotations',
        name: 'QuotationList',
        component: () => import('@/views/sales/QuotationList.vue'),
        meta: { title: '技术报价', icon: 'Document', menuId: 'sales:quotation' }
      },
      {
        path: 'sales/quotations/create',
        name: 'QuotationCreate',
        component: () => import('@/views/sales/QuotationForm.vue'),
        meta: { title: '新增报价', menuId: 'sales:quotation' }
      },
      {
        path: 'sales/quotations/:id/edit',
        name: 'QuotationEdit',
        component: () => import('@/views/sales/QuotationForm.vue'),
        meta: { title: '编辑报价', menuId: 'sales:quotation' }
      },
      {
        path: 'sales/quote-templates',
        name: 'QuoteTemplates',
        component: () => import('@/views/sales/QuoteTemplates.vue'),
        meta: { title: '报价单模板', icon: 'Document', menuId: 'sales:quotation' }
      },
      {
        path: 'sales/quote-versions',
        name: 'QuoteVersionList',
        component: () => import('@/views/sales/QuoteVersionList.vue'),
        meta: { title: '报价版本', icon: 'PriceTag', menuId: 'sales:quotation' }
      },
      // 非标报价估算
      {
        path: 'sales/quote-estimations',
        name: 'QuoteEstimation',
        component: () => import('@/views/sales/QuoteEstimation.vue'),
        meta: { title: '报价估算', icon: 'Calculator', menuId: 'sales:quotation' }
      },
      {
        path: 'sales/quote-estimation/:id',
        name: 'QuoteEstimationDetail',
        component: () => import('@/views/sales/QuoteEstimationDetail.vue'),
        meta: { title: '估算详情', menuId: 'sales:quotation' }
      },
      // Sales - 订单
      {
        path: 'sales/orders',
        name: 'SalesOrderList',
        component: () => import('@/views/sales/OrderList.vue'),
        meta: { title: '销售订单', icon: 'Sell', menuId: 'sales:order' }
      },
      {
        path: 'sales/orders/:id',
        name: 'SalesOrderDetail',
        component: () => import('@/views/sales/SalesOrderDetail.vue'),
        meta: { title: '销售订单详情', menuId: 'sales:order' }
      },
      // Sales - 合同
      {
        path: 'sales/contracts',
        name: 'SalesContractList',
        component: () => import('@/views/sales/ContractList.vue'),
        meta: { title: '销售合同', icon: 'Document', menuId: 'sales:contract' }
      },
      {
        path: 'sales/contract-templates',
        name: 'ContractTemplates',
        component: () => import('@/views/sales/ContractTemplates.vue'),
        meta: { title: '合同模板', icon: 'Document', menuId: 'sales:contract' }
      },
      // Sales - 发货
      {
        path: 'sales/delivery-orders',
        name: 'DeliveryOrderList',
        component: () => import('@/views/sales/DeliveryOrderList.vue'),
        meta: { title: '发货管理', icon: 'Van', menuId: 'sales:delivery' }
      },
      // Sales - 分析
      {
        path: 'sales/analysis',
        name: 'SalesAnalysis',
        component: () => import('@/views/sales/SalesAnalysis.vue'),
        meta: { title: '销售分析', icon: 'DataAnalysis', menuId: 'sales:analysis' }
      },
      // 销售业绩
      {
        path: 'sales/performance',
        name: 'SalesPerformance',
        component: () => import('@/views/sales/PerformanceAnalysis.vue'),
        meta: { title: '销售业绩', icon: 'TrendCharts', menuId: 'sales:analysis' }
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

      // ====== Group 4: Design 设计管理 ======
      // ECN设计变更
      {
        path: 'projects/ecn',
        name: 'ECNList',
        component: () => import('@/views/projects/ECNList.vue'),
        meta: { title: '设计变更', icon: 'Edit', menuId: 'design:ecn' }
      },
      // 图纸管理
      {
        path: 'projects/drawings',
        name: 'DrawingList',
        component: () => import('@/views/projects/DrawingList.vue'),
        meta: { title: '图纸文档', icon: 'Picture', menuId: 'design:drawing' }
      },
      // 图纸版本管理
      {
        path: 'projects/drawing-versions',
        name: 'DrawingVersionList',
        component: () => import('@/views/projects/DrawingVersionList.vue'),
        meta: { title: '图纸版本', icon: 'Document', menuId: 'design:drawing' }
      },
      {
        path: 'projects/batch-drawing-import',
        name: 'BatchDrawingImport',
        component: () => import('@/views/projects/BatchDrawingImport.vue'),
        meta: { title: '批量图纸导入', icon: 'FolderOpened', menuId: 'design:drawing' }
      },
      {
        path: 'projects/drawing-bom-link',
        name: 'DrawingBOMLink',
        component: () => import('@/views/projects/DrawingBOMLink.vue'),
        meta: { title: '图纸-BOM关联', icon: 'Connection', menuId: 'design:drawing' }
      },
      // 技术文档
      {
        path: 'projects/tech-documents',
        name: 'TechDocumentList',
        component: () => import('@/views/projects/TechDocumentList.vue'),
        meta: { title: '技术文档', icon: 'Document', menuId: 'design:document' }
      },
      // PLM - BOM对比
      {
        path: 'plm/bom-compare',
        name: 'BOMCompare',
        component: () => import('@/views/plm/BOMCompare.vue'),
        meta: { title: 'BOM版本对比', icon: 'Connection', menuId: 'design:bom_compare' }
      },
      // PLM - CAD导入
      {
        path: 'plm/cad-bom-import',
        name: 'CADBOMImport',
        component: () => import('@/views/plm/CreoBOMImport.vue'),
        meta: { title: 'Creo导入', icon: 'Upload', menuId: 'design:cad_import' }
      },
      // PLM - 3D模型预览
      {
        path: 'plm/model-viewer',
        name: 'ModelViewer',
        component: () => import('@/views/plm/ModelViewer.vue'),
        meta: { title: '3D模型预览', icon: 'View', menuId: 'design:model_viewer' }
      },
      // PLM - 需求管理
      {
        path: 'plm/requirements',
        name: 'Requirements',
        component: () => import('@/views/plm/RequirementList.vue'),
        meta: { title: '技术需求', icon: 'Document', menuId: 'design:requirement' }
      },
      {
        path: 'plm/proposals',
        name: 'Proposals',
        component: () => import('@/views/plm/ProposalList.vue'),
        meta: { title: '方案评审', icon: 'Edit', menuId: 'design:proposal' }
      },
      // PLM - 技术协议
      {
        path: 'plm/agreements',
        name: 'TechnicalAgreements',
        component: () => import('@/views/plm/TechnicalAgreementList.vue'),
        meta: { title: '技术协议', icon: 'Document', menuId: 'design:agreement' }
      },
      // Knowledge Base - 知识库
      {
        path: 'knowledge/articles',
        name: 'KnowledgeArticleList',
        component: () => import('@/views/knowledge/ArticleList.vue'),
        meta: { title: '技术文库', icon: 'Document', menuId: 'design:knowledge' }
      },
      {
        path: 'knowledge/issues',
        name: 'TechnicalIssueList',
        component: () => import('@/views/knowledge/TechnicalIssueList.vue'),
        meta: { title: '问题库', icon: 'Warning', menuId: 'design:knowledge' }
      },
      {
        path: 'knowledge/components',
        name: 'StandardComponentList',
        component: () => import('@/views/knowledge/StandardComponentList.vue'),
        meta: { title: '标准件库', icon: 'Box', menuId: 'design:knowledge' }
      },

      // ====== Group 5: Supply Chain 供应链 ======
      // 采购申请
      {
        path: 'purchase/requests',
        name: 'PurchaseRequestList',
        component: () => import('@/views/purchase/RequestList.vue'),
        meta: { title: '采购申请', icon: 'Document', menuId: 'supply:request' }
      },
      // 采购订单
      {
        path: 'purchase/orders',
        name: 'PurchaseOrderList',
        component: () => import('@/views/purchase/OrderList.vue'),
        meta: { title: '采购订单', icon: 'DocumentCopy', menuId: 'supply:order' }
      },
      {
        path: 'purchase/orders/:id',
        name: 'PurchaseOrderDetail',
        component: () => import('@/views/purchase/PurchaseOrderDetail.vue'),
        meta: { title: '采购订单详情', menuId: 'supply:order' }
      },
      // 到货验收
      {
        path: 'purchase/goods-receipts',
        name: 'GoodsReceiptList',
        component: () => import('@/views/purchase/GoodsReceiptList.vue'),
        meta: { title: '到货验收', icon: 'Box', menuId: 'supply:receipt' }
      },
      // 询价比价
      {
        path: 'purchase/comparisons',
        name: 'ComparisonList',
        component: () => import('@/views/purchase/ComparisonList.vue'),
        meta: { title: '询价比价', icon: 'DataAnalysis', menuId: 'supply:rfq' }
      },
      {
        path: 'purchase/comparisons/:id',
        name: 'ComparisonDetail',
        component: () => import('@/views/purchase/ComparisonDetail.vue'),
        meta: { title: '比价详情', menuId: 'supply:rfq' }
      },
      // 外协加工
      {
        path: 'purchase/outsource',
        name: 'OutsourceList',
        component: () => import('@/views/purchase/OutsourceList.vue'),
        meta: { title: '外协加工', icon: 'Setting', menuId: 'supply:outsource' }
      },
      {
        path: 'purchase/outsource-tracking',
        name: 'OutsourceTracking',
        component: () => import('@/views/purchase/OutsourceTracking.vue'),
        meta: { title: '外协跟踪', icon: 'Setting', menuId: 'supply:outsource' }
      },
      {
        path: 'purchase/outsource-capabilities',
        name: 'OutsourceCapabilityList',
        component: () => import('@/views/purchase/OutsourceCapabilityList.vue'),
        meta: { title: '外协商能力', icon: 'Opportunity', menuId: 'supply:outsource' }
      },
      // 库存管理
      {
        path: 'inventory/stocks',
        name: 'StockList',
        component: () => import('@/views/inventory/StockList.vue'),
        meta: { title: '实时库存', icon: 'Goods', menuId: 'supply:stock' }
      },
      {
        path: 'inventory/batches',
        name: 'BatchList',
        component: () => import('@/views/inventory/BatchList.vue'),
        meta: { title: '批次管理', icon: 'Collection', menuId: 'supply:stock' }
      },
      {
        path: 'inventory/transfer',
        name: 'StockTransfer',
        component: () => import('@/views/inventory/StockTransfer.vue'),
        meta: { title: '调拨管理', icon: 'Sort', menuId: 'supply:stock' }
      },
      {
        path: 'inventory/adjustment',
        name: 'StockAdjustmentList',
        component: () => import('@/views/inventory/StockAdjustmentList.vue'),
        meta: { title: '盘点管理', icon: 'DocumentChecked', menuId: 'supply:stock' }
      },
      {
        path: 'inventory/alert',
        name: 'StockAlert',
        component: () => import('@/views/inventory/StockAlert.vue'),
        meta: { title: '库存预警', icon: 'Warning', menuId: 'supply:stock' }
      },
      {
        path: 'inventory/stock-alerts',
        name: 'StockAlerts',
        component: () => import('@/views/inventory/StockAlert.vue'),
        meta: { title: '库存预警', icon: 'Warning', menuId: 'supply:stock' }
      },
      // 出入明细
      {
        path: 'inventory/moves',
        name: 'StockMoveList',
        component: () => import('@/views/inventory/StockMoveList.vue'),
        meta: { title: '出入明细', icon: 'List', menuId: 'supply:move' }
      },
      {
        path: 'inventory/requisitions',
        name: 'RequisitionList',
        component: () => import('@/views/inventory/RequisitionList.vue'),
        meta: { title: '领料出库', icon: 'TakeawayBox', menuId: 'supply:move' }
      },
      {
        path: 'inventory/returns',
        name: 'ReturnList',
        component: () => import('@/views/inventory/ReturnList.vue'),
        meta: { title: '退料入库', icon: 'RefreshLeft', menuId: 'supply:move' }
      },
      // MRP
      {
        path: 'inventory/mrp',
        name: 'MRPPlan',
        component: () => import('@/views/inventory/MRPPlan.vue'),
        meta: { title: 'MRP计划', icon: 'List', menuId: 'supply:mrp' }
      },
      // 备件管理
      {
        path: 'inventory/spare-parts',
        name: 'SparePartList',
        component: () => import('@/views/inventory/SparePartList.vue'),
        meta: { title: '备件管理', icon: 'Box', menuId: 'supply:spare' }
      },
      {
        path: 'inventory/spare-part-alerts',
        name: 'SparePartAlertList',
        component: () => import('@/views/inventory/SparePartAlertList.vue'),
        meta: { title: '备件预警', icon: 'Warning', menuId: 'supply:spare' }
      },
      {
        path: 'inventory/spare-part-prediction',
        name: 'SparePartPrediction',
        component: () => import('@/views/inventory/SparePartPrediction.vue'),
        meta: { title: '备件预测', icon: 'Histogram', menuId: 'supply:spare' }
      },
      // 物料管理
      {
        path: 'masterdata/items',
        name: 'ItemList',
        component: () => import('@/views/masterdata/ItemList.vue'),
        meta: { title: '物料管理', icon: 'Box', menuId: 'supply:item' }
      },
      // 供应商管理
      {
        path: 'masterdata/suppliers',
        name: 'SupplierList',
        component: () => import('@/views/masterdata/SupplierList.vue'),
        meta: { title: '供应商管理', icon: 'ShoppingCart', menuId: 'supply:supplier' }
      },
      // 仓库管理
      {
        path: 'masterdata/warehouses',
        name: 'WarehouseList',
        component: () => import('@/views/masterdata/WarehouseList.vue'),
        meta: { title: '仓库管理', icon: 'House', menuId: 'supply:warehouse' }
      },
      {
        path: 'masterdata/locations',
        name: 'LocationList',
        component: () => import('@/views/masterdata/LocationList.vue'),
        meta: { title: '库位管理', icon: 'Grid', menuId: 'supply:warehouse' }
      },
      // 采购预算
      {
        path: 'purchase/budgets',
        name: 'PurchaseBudgets',
        component: () => import('@/views/purchase/BudgetList.vue'),
        meta: { title: '采购预算', icon: 'Wallet', menuId: 'supply:budget' }
      },
      // 供应商考核
      {
        path: 'purchase/evaluations',
        name: 'SupplierEvaluationList',
        component: () => import('@/views/purchase/SupplierEvaluationList.vue'),
        meta: { title: '供应商考核', icon: 'Star', menuId: 'supply:supplier' }
      },
      {
        path: 'purchase/blacklist',
        name: 'SupplierBlacklist',
        component: () => import('@/views/purchase/SupplierBlacklist.vue'),
        meta: { title: '供应商黑名单', icon: 'Warning', menuId: 'supply:supplier' }
      },
      // 供应链协同
      {
        path: 'purchase/rfq-collaborations',
        name: 'RFQCollaborationList',
        component: () => import('@/views/purchase/RFQCollaborationList.vue'),
        meta: { title: '询报价协同', icon: 'ChatDotSquare', menuId: 'supply:collaboration' }
      },
      {
        path: 'purchase/delivery-collaborations',
        name: 'DeliveryCollaborationList',
        component: () => import('@/views/purchase/DeliveryCollaborationList.vue'),
        meta: { title: '交期协同', icon: 'Van', menuId: 'supply:collaboration' }
      },
      // 供应商协同门户
      {
        path: 'purchase/supplier-portal',
        name: 'SupplierPortal',
        component: () => import('@/views/purchase/SupplierPortal.vue'),
        meta: { title: '供应商协同', icon: 'Connection', menuId: 'supply:portal' }
      },
      // 库存成本核算
      {
        path: 'inventory/cost-accounting',
        name: 'CostAccounting',
        component: () => import('@/views/inventory/CostAccounting.vue'),
        meta: { title: '库存成本', icon: 'Coin', menuId: 'supply:cost' }
      },
      // 进销存数据准确性
      {
        path: 'inventory/data-accuracy',
        name: 'DataAccuracy',
        component: () => import('@/views/inventory/DataAccuracy.vue'),
        meta: { title: '数据准确性', icon: 'Checked', menuId: 'supply:accuracy' }
      },
      {
        path: 'inventory/reconciliation/:id',
        name: 'ReconciliationDetail',
        component: () => import('@/views/inventory/ReconciliationDetail.vue'),
        meta: { title: '对账详情', menuId: 'supply:accuracy' }
      },

      // ====== Group 6: Manufacturing 生产制造 ======
      // 排产计划
      {
        path: 'production/plans',
        name: 'ProductionPlanList',
        component: () => import('@/views/production/PlanList.vue'),
        meta: { title: '排产计划', icon: 'Calendar', menuId: 'manufacturing:plan' }
      },
      // 工艺路线
      {
        path: 'production/routing-templates',
        name: 'RoutingTemplateList',
        component: () => import('@/views/production/RoutingTemplate.vue'),
        meta: { title: '工艺路线', icon: 'Guide', menuId: 'manufacturing:routing' }
      },
      {
        path: 'production/routing-template/:id',
        name: 'RoutingTemplateDetail',
        component: () => import('@/views/production/RoutingTemplateDetail.vue'),
        meta: { title: '工艺详情', menuId: 'manufacturing:routing' }
      },
      {
        path: 'production/processes',
        name: 'ProductionProcessList',
        component: () => import('@/views/production/ProcessList.vue'),
        meta: { title: '工艺工序', icon: 'Setting', menuId: 'manufacturing:routing' }
      },
      {
        path: 'production/work-stations',
        name: 'WorkStationList',
        component: () => import('@/views/production/WorkStationList.vue'),
        meta: { title: '工位管理', icon: 'OfficeBuilding', menuId: 'manufacturing:routing' }
      },
      // MES - APS排程
      {
        path: 'mes/scheduling',
        name: 'APSScheduling',
        component: () => import('@/views/mes/APSScheduling.vue'),
        meta: { title: '智能排程', icon: 'Calendar', menuId: 'manufacturing:aps' }
      },
      // MES - 生产看板
      {
        path: 'mes/kanban',
        name: 'ProductionKanban',
        component: () => import('@/views/mes/Kanban.vue'),
        meta: { title: '生产看板', icon: 'Monitor', menuId: 'manufacturing:kanban' }
      },
      // 看板WIP管理
      {
        path: 'production/kanban-wip',
        name: 'KanbanWIPManagement',
        component: () => import('@/views/production/KanbanWIPManagement.vue'),
        meta: { title: 'WIP管理', icon: 'Stopwatch', menuId: 'manufacturing:kanban' }
      },
      // 质检管理
      {
        path: 'production/inspections',
        name: 'QualityInspectionList',
        component: () => import('@/views/production/QualityInspectionList.vue'),
        meta: { title: '质检管理', icon: 'DocumentChecked', menuId: 'manufacturing:inspection' }
      },
      // 设备管理
      {
        path: 'equipment/list',
        name: 'EquipmentList',
        component: () => import('@/views/equipment/EquipmentList.vue'),
        meta: { title: '设备管理', icon: 'Monitor', menuId: 'manufacturing:equipment' }
      },
      {
        path: 'equipment/fixtures',
        name: 'FixtureList',
        component: () => import('@/views/equipment/FixtureList.vue'),
        meta: { title: '工装管理', icon: 'Opportunity', menuId: 'manufacturing:equipment' }
      },
      {
        path: 'equipment/inspection',
        name: 'EquipmentInspection',
        component: () => import('@/views/equipment/InspectionList.vue'),
        meta: { title: '设备点检', icon: 'Checked', menuId: 'manufacturing:equipment' }
      },
      {
        path: 'equipment/maintenance',
        name: 'MaintenanceCalendar',
        component: () => import('@/views/equipment/MaintenanceCalendar.vue'),
        meta: { title: '维护日历', icon: 'Calendar', menuId: 'manufacturing:equipment' }
      },
      {
        path: 'equipment/oee',
        name: 'EquipmentOEE',
        component: () => import('@/views/equipment/OEEAnalysis.vue'),
        meta: { title: 'OEE分析', icon: 'DataAnalysis', menuId: 'manufacturing:equipment' }
      },
      // 设备档案
      {
        path: 'projects/equipment-archives',
        name: 'EquipmentArchives',
        component: () => import('@/views/projects/EquipmentArchiveList.vue'),
        meta: { title: '设备台账', icon: 'Files', menuId: 'manufacturing:equipment' }
      },
      // 设备远程运维
      {
        path: 'projects/equipment-monitoring',
        name: 'EquipmentMonitoring',
        component: () => import('@/views/projects/EquipmentMonitoring.vue'),
        meta: { title: '设备监控', icon: 'Monitor', menuId: 'manufacturing:equipment' }
      },
      {
        path: 'projects/equipment-alarms',
        name: 'EquipmentAlarmList',
        component: () => import('@/views/projects/EquipmentAlarmList.vue'),
        meta: { title: '设备报警', icon: 'Warning', menuId: 'manufacturing:equipment' }
      },
      {
        path: 'projects/diagnostic-sessions',
        name: 'DiagnosticSessionList',
        component: () => import('@/views/projects/DiagnosticSessionList.vue'),
        meta: { title: '远程诊断', icon: 'Service', menuId: 'manufacturing:equipment' }
      },
      // 装配作业
      {
        path: 'production/assembly-guides',
        name: 'AssemblyGuideList',
        component: () => import('@/views/production/AssemblyGuideList.vue'),
        meta: { title: '装配作业', icon: 'Connection', menuId: 'manufacturing:assembly' }
      },
      {
        path: 'production/assembly-guide/:id',
        name: 'AssemblyGuideDetail',
        component: () => import('@/views/production/AssemblyGuideDetail.vue'),
        meta: { title: '装配详情', menuId: 'manufacturing:assembly' }
      },
      // 序列号管理
      {
        path: 'production/serial-numbers',
        name: 'SerialNumbers',
        component: () => import('@/views/production/SerialNumberList.vue'),
        meta: { title: '序列号管理', icon: 'List', menuId: 'manufacturing:sn' }
      },
      // 调试日志
      {
        path: 'production/debug-records',
        name: 'DebugRecordList',
        component: () => import('@/views/production/DebugRecordList.vue'),
        meta: { title: '调试日志', icon: 'Cpu', menuId: 'manufacturing:debug' }
      },
      // MES - Andon异常报警
      {
        path: 'mes/andon',
        name: 'AndonSystem',
        component: () => import('@/views/mes/AndonSystem.vue'),
        meta: { title: '异常报警', icon: 'Bell', menuId: 'manufacturing:andon' }
      },
      // MES - 数据采集
      {
        path: 'mes/data-acquisition',
        name: 'DataAcquisition',
        component: () => import('@/views/mes/DataAcquisition.vue'),
        meta: { title: '数据采集', icon: 'Connection', menuId: 'manufacturing:data_acquisition' }
      },
      // 产能规划
      {
        path: 'production/capacity-planning',
        name: 'CapacityPlanning',
        component: () => import('@/views/production/CapacityPlanning.vue'),
        meta: { title: '产能规划', icon: 'Cpu', menuId: 'manufacturing:capacity' }
      },
      {
        path: 'production/resource-types',
        name: 'ResourceTypeList',
        component: () => import('@/views/production/ResourceTypeList.vue'),
        meta: { title: '资源类型', icon: 'Files', menuId: 'manufacturing:capacity' }
      },
      // 有限产能排程
      {
        path: 'production/finite-capacity',
        name: 'FiniteCapacityList',
        component: () => import('@/views/production/FiniteCapacityList.vue'),
        meta: { title: '有限产能排程', icon: 'Timer', menuId: 'manufacturing:finite_capacity' }
      },
      // 设备能力矩阵
      {
        path: 'production/equipment-capability',
        name: 'EquipmentCapabilityMatrix',
        component: () => import('@/views/production/EquipmentCapabilityMatrix.vue'),
        meta: { title: '设备能力矩阵', icon: 'Grid', menuId: 'manufacturing:equipment_capability' }
      },

      // ====== Group 7: Finance 财务管理 ======
      {
        path: 'finance/ar',
        name: 'ARList',
        component: () => import('@/views/finance/ARList.vue'),
        meta: { title: '应收管理', icon: 'CreditCard', menuId: 'finance:receivable' }
      },
      {
        path: 'finance/ap',
        name: 'APList',
        component: () => import('@/views/finance/APList.vue'),
        meta: { title: '应付管理', icon: 'Wallet', menuId: 'finance:payable' }
      },
      {
        path: 'finance/bank-statements',
        name: 'BankStatementList',
        component: () => import('@/views/finance/BankStatementList.vue'),
        meta: { title: '银行流水', icon: 'CreditCard', menuId: 'finance:bank_statement' }
      },
      {
        path: 'finance/invoices',
        name: 'InvoiceList',
        component: () => import('@/views/finance/InvoiceList.vue'),
        meta: { title: '发票管理', icon: 'Tickets', menuId: 'finance:invoice' }
      },
      {
        path: 'finance/expenses',
        name: 'ExpenseList',
        component: () => import('@/views/finance/ExpenseList.vue'),
        meta: { title: '费用报销', icon: 'Money', menuId: 'finance:expense' }
      },
      {
        path: 'finance/shared-expenses',
        name: 'SharedExpenseList',
        component: () => import('@/views/finance/SharedExpenseList.vue'),
        meta: { title: '公共费用分摊', icon: 'Share', menuId: 'finance:expense' }
      },
      // 固定资产
      {
        path: 'finance/assets',
        name: 'FixedAssets',
        component: () => import('@/views/finance/AssetList.vue'),
        meta: { title: '固定资产', icon: 'OfficeBuilding', menuId: 'finance:asset' }
      },
      // 回款跟踪
      {
        path: 'finance/collection-plans',
        name: 'CollectionPlanList',
        component: () => import('@/views/finance/CollectionPlanList.vue'),
        meta: { title: '回款跟踪', icon: 'Money', menuId: 'finance:collection' }
      },
      // 对账
      {
        path: 'finance/sales-reconciliation',
        name: 'SalesReconciliation',
        component: () => import('@/views/finance/SalesReconciliation.vue'),
        meta: { title: '销售对账', icon: 'Document', menuId: 'finance:reconciliation' }
      },
      {
        path: 'finance/purchase-reconciliation',
        name: 'PurchaseReconciliation',
        component: () => import('@/views/finance/PurchaseReconciliation.vue'),
        meta: { title: '采购对账', icon: 'Document', menuId: 'finance:reconciliation' }
      },
      // 项目成本
      {
        path: 'finance/project-costs',
        name: 'ProjectCostList',
        component: () => import('@/views/finance/ProjectCostList.vue'),
        meta: { title: '项目成本', icon: 'DataAnalysis', menuId: 'finance:project_cost' }
      },

      // ====== Group 8: OA 办公自动化 ======
      // 审批工作流
      {
        path: 'workflow/tasks',
        name: 'WorkflowTasks',
        component: () => import('@/views/workflow/TaskList.vue'),
        meta: { title: '待我审批', icon: 'Checked', menuId: 'oa:workflow' }
      },
      {
        path: 'workflow/my-submissions',
        name: 'MySubmissions',
        component: () => import('@/views/workflow/MySubmissions.vue'),
        meta: { title: '我的申请', icon: 'Document', menuId: 'oa:workflow' }
      },
      {
        path: 'workflow/config',
        name: 'WorkflowConfig',
        component: () => import('@/views/workflow/WorkflowConfig.vue'),
        meta: { title: '审批设置', icon: 'Setting', menuId: 'oa:workflow' }
      },
      // 考勤
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
        meta: { title: '考勤导入', icon: 'Upload', menuId: 'oa:attendance' }
      },
      {
        path: 'oa/leave',
        name: 'LeaveRequest',
        component: () => import('@/views/oa/LeaveList.vue'),
        meta: { title: '请假申请', icon: 'Document', menuId: 'oa:attendance' }
      },
      {
        path: 'oa/overtime',
        name: 'OvertimeRequest',
        component: () => import('@/views/oa/OvertimeList.vue'),
        meta: { title: '加班申请', icon: 'Timer', menuId: 'oa:attendance' }
      },
      {
        path: 'attendance',
        name: 'Attendance',
        component: () => import('@/views/accounts/Attendance.vue'),
        meta: { title: '考勤管理', icon: 'Clock', menuId: 'oa:attendance' }
      },
      // 会议
      {
        path: 'oa/meeting',
        name: 'Meeting',
        component: () => import('@/views/oa/Meeting.vue'),
        meta: { title: '会议管理', icon: 'VideoCamera', menuId: 'oa:meeting' }
      },
      {
        path: 'oa/schedule',
        name: 'Schedule',
        component: () => import('@/views/oa/Schedule.vue'),
        meta: { title: '日程管理', icon: 'Calendar', menuId: 'oa:meeting' }
      },
      // 公告通知
      {
        path: 'oa/announcement',
        name: 'Announcement',
        component: () => import('@/views/oa/AnnouncementList.vue'),
        meta: { title: '公告通知', icon: 'Bell', menuId: 'oa:announcement' }
      },
      // 车辆管理
      {
        path: 'oa/vehicles',
        name: 'VehicleList',
        component: () => import('@/views/oa/VehicleList.vue'),
        meta: { title: '车辆管理', icon: 'Van', menuId: 'oa:vehicle' }
      },
      {
        path: 'oa/vehicle-request',
        name: 'VehicleRequest',
        component: () => import('@/views/oa/VehicleRequestList.vue'),
        meta: { title: '用车申请', icon: 'Tickets', menuId: 'oa:vehicle' }
      },
      // 资产管理
      {
        path: 'oa/assets',
        name: 'OAAssetList',
        component: () => import('@/views/oa/AssetList.vue'),
        meta: { title: '资产管理', icon: 'Box', menuId: 'oa:asset' }
      },
      {
        path: 'oa/asset-borrow',
        name: 'OAAssetBorrowList',
        component: () => import('@/views/oa/AssetBorrowList.vue'),
        meta: { title: '资产借用', icon: 'Tickets', menuId: 'oa:asset' }
      },
      // ====== Group 9: System 系统管理 ======
      {
        path: 'system/users',
        name: 'UserList',
        component: () => import('@/views/system/UserList.vue'),
        meta: { title: '用户管理', icon: 'User', menuId: 'system:user' }
      },
      {
        path: 'system/roles',
        name: 'RoleList',
        component: () => import('@/views/system/RoleList.vue'),
        meta: { title: '角色管理', icon: 'Setting', menuId: 'system:role' }
      },
      {
        path: 'system/departments',
        name: 'DepartmentList',
        component: () => import('@/views/system/DepartmentList.vue'),
        meta: { title: '部门管理', icon: 'OfficeBuilding', menuId: 'system:department' }
      },
      // Reports
      {
        path: 'reports/profitability',
        name: 'ProfitabilityReport',
        component: () => import('@/views/reports/ProfitabilityReport.vue'),
        meta: { title: '项目利润', icon: 'TrendCharts', menuId: 'system:report' }
      },
      {
        path: 'reports/aging',
        name: 'AgingReport',
        component: () => import('@/views/reports/AgingReport.vue'),
        meta: { title: '账龄报表', icon: 'Calendar', menuId: 'system:report' }
      },
      {
        path: 'reports/cash-flow',
        name: 'CashFlowForecast',
        component: () => import('@/views/reports/CashFlowForecast.vue'),
        meta: { title: '现金流', icon: 'Money', menuId: 'system:report' }
      },
      {
        path: 'reports/slow-moving',
        name: 'SlowMovingReport',
        component: () => import('@/views/reports/SlowMovingReport.vue'),
        meta: { title: '呆滞物料', icon: 'Warning', menuId: 'system:report' }
      },
      {
        path: 'reports/timelog',
        name: 'TimelogReport',
        component: () => import('@/views/reports/TimelogReport.vue'),
        meta: { title: '工时报表', icon: 'Clock', menuId: 'system:report' }
      },
      {
        path: 'reports/cost-analysis',
        name: 'CostAnalysis',
        component: () => import('@/views/reports/CostAnalysis.vue'),
        meta: { title: '成本报表', icon: 'Coin', menuId: 'system:report' }
      },
      {
        path: 'reports/builder',
        name: 'ReportBuilder',
        component: () => import('@/views/reports/ReportBuilder.vue'),
        meta: { title: '报表构建器', icon: 'DataBoard', menuId: 'system:report' }
      },
      {
        path: 'reports/prediction',
        name: 'PredictiveAnalysis',
        component: () => import('@/views/reports/PredictiveAnalysis.vue'),
        meta: { title: '智能预测', icon: 'TrendCharts', menuId: 'system:report' }
      },
      {
        path: 'reports/risk-alerts',
        name: 'RiskAlertList',
        component: () => import('@/views/reports/RiskAlertList.vue'),
        meta: { title: '风险预警', icon: 'WarningFilled', menuId: 'system:report' }
      },
      {
        path: 'reports/project-profitability',
        name: 'ProjectProfitabilityReport',
        component: () => import('@/views/reports/ProjectProfitabilityReport.vue'),
        meta: { title: '项目毛利分析', icon: 'TrendCharts', menuId: 'system:report' }
      },
      {
        path: 'reports/equipment-lifecycle',
        name: 'EquipmentLifecycleReport',
        component: () => import('@/views/reports/EquipmentLifecycleReport.vue'),
        meta: { title: '设备生命周期', icon: 'Timer', menuId: 'system:report' }
      },
      {
        path: 'reports/capacity-utilization',
        name: 'CapacityUtilizationReport',
        component: () => import('@/views/reports/CapacityUtilizationReport.vue'),
        meta: { title: '产能利用率', icon: 'DataAnalysis', menuId: 'system:report' }
      },
      {
        path: 'reports/customer-value',
        name: 'CustomerValueReport',
        component: () => import('@/views/reports/CustomerValueReport.vue'),
        meta: { title: '客户价值分析', icon: 'UserFilled', menuId: 'system:report' }
      },
      // Analytics
      {
        path: 'analytics/project',
        name: 'ProjectAnalytics',
        component: () => import('@/views/analytics/ProjectAnalytics.vue'),
        meta: { title: '项目分析', icon: 'DataLine', menuId: 'system:report' }
      },
      {
        path: 'analytics/inventory',
        name: 'InventoryAnalytics',
        component: () => import('@/views/analytics/InventoryAnalytics.vue'),
        meta: { title: '库存分析', icon: 'PieChart', menuId: 'system:report' }
      },
      // 数据字典
      {
        path: 'system/data-dictionary',
        name: 'DataDictionary',
        component: () => import('@/views/system/DataDictionary.vue'),
        meta: { title: '数据字典', icon: 'Collection', menuId: 'system:dict' }
      },
      // 系统配置
      {
        path: 'system/config',
        name: 'SystemConfig',
        component: () => import('@/views/system/SystemConfig.vue'),
        meta: { title: '系统配置', icon: 'Setting', menuId: 'system:config' }
      },
      {
        path: 'system/code-rules',
        name: 'CodeRuleList',
        component: () => import('@/views/system/CodeRuleList.vue'),
        meta: { title: '编号规则', icon: 'SetUp', menuId: 'system:config' }
      },
      {
        path: 'system/notification-settings',
        name: 'NotificationSettings',
        component: () => import('@/views/settings/NotificationSettings.vue'),
        meta: { title: '消息设置', icon: 'Bell', menuId: 'system:config' }
      },
      {
        path: 'system/email-templates',
        name: 'EmailTemplates',
        component: () => import('@/views/system/EmailTemplates.vue'),
        meta: { title: '邮件模板', icon: 'Message', menuId: 'system:config' }
      },
      {
        path: 'system/custom-fields',
        name: 'CustomFields',
        component: () => import('@/views/system/CustomFields.vue'),
        meta: { title: '自定义字段', icon: 'Grid', menuId: 'system:config' }
      },
      {
        path: 'system/webhooks',
        name: 'WebhookList',
        component: () => import('@/views/system/WebhookList.vue'),
        meta: { title: 'Webhook管理', icon: 'Connection', menuId: 'system:config' }
      },
      {
        path: 'system/dashboard-config',
        name: 'DashboardConfig',
        component: () => import('@/views/system/DashboardConfig.vue'),
        meta: { title: '仪表盘配置', icon: 'DataBoard', menuId: 'system:config' }
      },
      // 审计日志
      {
        path: 'system/audit-log',
        name: 'AuditLog',
        component: () => import('@/views/AuditLog.vue'),
        meta: { title: '审计日志', icon: 'Document', menuId: 'system:audit' }
      },
      {
        path: 'system/login-logs',
        name: 'LoginLogs',
        component: () => import('@/views/system/LoginLogs.vue'),
        meta: { title: '登录日志', icon: 'Key', menuId: 'system:audit' }
      },
      {
        path: 'system/audit-analytics',
        name: 'AuditAnalytics',
        component: () => import('@/views/system/AuditAnalytics.vue'),
        meta: { title: '操作日志分析', icon: 'DataAnalysis', menuId: 'system:audit' }
      },
      // 其他系统功能
      {
        path: 'system/notifications',
        name: 'NotificationCenter',
        component: () => import('@/views/NotificationCenter.vue'),
        meta: { title: '通知中心', icon: 'Bell', menuId: 'system:notification' }
      },
      {
        path: 'system/announcements',
        name: 'Announcements',
        component: () => import('@/views/system/Announcement.vue'),
        meta: { title: '系统公告', icon: 'Bell', menuId: 'system:announcement' }
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

      // ====== Public Pages (no menuId permission check) ======
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
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    redirect: '/dashboard'
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
