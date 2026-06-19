// 全局共享类型定义。后端契约对齐 server/internal/* 与旧前端 profile 结构。

// DRF 风格分页信封 {count,next,previous,results}(httpx.Page)。
export interface PageResult<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

// 后端错误体 {detail}(httpx.Error)。
export interface ApiError {
  detail?: string
  error?: string
}

// ===== 回款核销(finance/collection)。金额字段后端为 decimal,序列化为字符串。 =====
export interface CollectionPlan {
  id: number
  plan_no: string
  name: string
  customer_id: number
  total_amount: string
  planned_amount: string
  collected_amount: string
  status: string
  notes?: string
}
export interface CollectionMilestone {
  id: number
  plan_id: number
  milestone_type: string
  name: string
  planned_amount: string
  collected_amount: string
  planned_date: string
  status: string
}
export interface CollectionPlanDetail {
  plan: CollectionPlan
  milestones: CollectionMilestone[]
}
export interface CollectionPlanCreateInput {
  name: string
  customer_id: number
  total_amount?: number
  notes?: string
}
export interface CollectionMilestoneCreateInput {
  name: string
  milestone_type?: string
  planned_amount?: number
  planned_date?: string
}
export interface CollectionRecordCreateInput {
  amount: number
  collection_date?: string
  payment_method?: string
  notes?: string
}
export interface CollectionPlanListQuery {
  keyword?: string
  status?: string
  page?: number
  page_size?: number
}

// 站内信(notify)。命名 App 前缀避开浏览器全局 Notification。
export interface AppNotification {
  id: number
  user_id: number
  type: string
  title: string
  message: string
  is_read: boolean
  created_at: string
  read_at?: string | null
}

// 用户档案。刷新/登录后由后端回灌 permissions/menus/data_scopes。
export interface UserProfile {
  id: number
  username: string
  name?: string
  email?: string
  permissions?: string[]
  menus?: string[]
  data_scopes?: Record<string, string>
}

// 登录响应。token + 内联用户档案。
export interface LoginResult {
  access: string
  refresh: string
  user: UserProfile
}

// 物料,对齐 server/internal/masterdata/item Item(真实 item 表列:sku/specification/...)。
export interface Item {
  id: number
  sku: string
  name: string
  specification: string
  brand?: string
  model?: string
  category_id?: number | null
  unit: string
  standard_cost: number
  purchase_price?: number
  sale_price?: number
  is_active?: boolean
  created_at?: string
  updated_at?: string
}

// 物料创建入参(对齐 CreateInput)。
export interface ItemCreateInput {
  sku: string
  name: string
  specification?: string
  brand?: string
  model?: string
  category_id?: number | null
  unit?: string
  standard_cost?: number
  purchase_price?: number
  sale_price?: number
}

// 物料更新入参(对齐 UpdateInput,局部更新)。
export interface ItemUpdateInput {
  name?: string
  specification?: string
  brand?: string
  model?: string
  category_id?: number | null
  unit?: string
  standard_cost?: number
  purchase_price?: number
  sale_price?: number
}

// 物料列表查询条件。
export interface ItemListQuery {
  keyword?: string
  category_id?: string
  page?: number
  page_size?: number
}

// 公共分页查询基类(各模块列表查询继承)。
export interface BaseListQuery {
  page?: number
  page_size?: number
}

// ===== sales 报价(Quotation),对齐 server/internal/sales Quotation =====

export interface Quotation {
  id: number
  quote_no: string
  customer_id: number
  project_id?: number
  quote_date?: string
  valid_until?: string
  status: string
  version: number
  tax_rate: number
  total_amount: number
  tax_amount: number
  total_with_tax: number
  notes: string
  created_at?: string
  updated_at?: string
}

export interface QuotationCreateInput {
  customer_id: number
  project_id?: number | null
  valid_until?: string | null
  tax_rate?: number | null
  notes?: string
}

export interface QuotationUpdateInput {
  customer_id?: number | null
  project_id?: number | null
  valid_until?: string | null
  tax_rate?: number | null
  status?: string | null
  notes?: string | null
}

export interface QuotationListQuery extends BaseListQuery {
  keyword?: string
  status?: string
  customer?: string
}

// ===== purchase 采购订单(PurchaseOrder),对齐 server/internal/purchase PurchaseOrder =====

export interface PurchaseOrder {
  id: number
  order_no: string
  supplier_id: number
  project_id?: number
  order_date: string
  delivery_date: string
  status: string
  tax_rate: number
  total_amount: number
  tax_amount: number
  total_with_tax: number
  payment_terms: string
  payment_method: string
  payment_terms_detail: string
  notes: string
  created_at?: string
  updated_at?: string
}

export interface PurchaseOrderCreateInput {
  supplier_id: number
  project_id?: number | null
  delivery_date: string
  tax_rate?: number | null
  payment_terms?: string
  payment_method?: string
  payment_terms_detail?: string
  notes?: string
}

export interface PurchaseOrderUpdateInput {
  supplier_id?: number | null
  project_id?: number | null
  delivery_date?: string | null
  tax_rate?: number | null
  payment_terms?: string | null
  payment_method?: string | null
  payment_terms_detail?: string | null
  notes?: string | null
}

export interface PurchaseOrderListQuery extends BaseListQuery {
  keyword?: string
  status?: string
}

// ===== inventory 库存(Stock,只读),对齐 server/internal/inventory Stock =====

export interface Stock {
  id: number
  warehouse_id: number
  item_id: number
  qty_on_hand: number
  qty_reserved: number
  qty_available: number
  weighted_avg_cost: number
  created_at?: string
  updated_at?: string
}

export interface StockListQuery extends BaseListQuery {
  warehouse_id?: number
  item_id?: number
  low_stock?: boolean
}

// ===== inventory 库存移动(StockMove),对齐 server/internal/inventory StockMove =====

export interface StockMove {
  id: number
  move_no: string
  item_id: number
  warehouse_from?: number | null
  warehouse_to?: number | null
  qty: number
  unit_cost: number
  move_type: string
  reference_type: string
  reference_id?: number | null
  project?: number | null
  move_date: string
  status: string
  notes: string
  created_at?: string
  updated_at?: string
}

export interface StockMoveCreateInput {
  item_id: number
  warehouse_from?: number | null
  warehouse_to?: number | null
  qty: number
  unit_cost?: number
  move_type: string
  reference_type?: string
  move_date: string
  notes?: string
}

export interface StockMoveUpdateInput {
  qty?: number | null
  unit_cost?: number | null
  warehouse_from?: number | null
  warehouse_to?: number | null
  move_type?: string | null
  move_date?: string | null
  notes?: string | null
}

export interface StockMoveListQuery extends BaseListQuery {
  item_id?: number
  move_type?: string
  status?: string
}

// ===== projects 项目(Project),对齐 server/internal/projects Project =====

export interface Project {
  id: number
  code: string
  name: string
  customer_id: number
  sales_order_id?: number
  manager_id: number
  start_date?: string | null
  end_date?: string | null
  status: string
  budget_total: number
  budget_material: number
  budget_labor: number
  budget_expense: number
  description: string
  notes: string
  created_at?: string
  updated_at?: string
}

export interface ProjectCreateInput {
  code?: string
  name: string
  customer_id: number
  sales_order_id?: number | null
  manager_id: number
  start_date?: string | null
  end_date?: string | null
  status?: string
  budget_total?: number
  budget_material?: number
  budget_labor?: number
  budget_expense?: number
  description?: string
  notes?: string
}

export interface ProjectUpdateInput {
  name?: string | null
  customer_id?: number | null
  sales_order_id?: number | null
  manager_id?: number | null
  start_date?: string | null
  end_date?: string | null
  status?: string | null
  budget_total?: number | null
  budget_material?: number | null
  budget_labor?: number | null
  budget_expense?: number | null
  description?: string | null
  notes?: string | null
}

export interface ProjectListQuery extends BaseListQuery {
  keyword?: string
  customer_id?: number
  manager_id?: number
  status?: string
}

// ===== production 工单(WorkOrder),对齐 server/internal/production/workorder WorkOrder =====

export interface WorkOrder {
  id: number
  order_no: string
  project_id?: number
  sales_order_id?: number
  item_id?: number
  quantity: number
  required_date: string
  earliest_start?: string | null
  work_center_id?: number
  planned_start?: string | null
  planned_end?: string | null
  planned_hours?: number
  actual_start?: string | null
  actual_end?: string | null
  completed_qty: number
  priority: number
  status: string
  remarks: string
  created_at?: string
  updated_at?: string
}

export interface WorkOrderCreateInput {
  order_no?: string
  project_id?: number | null
  sales_order_id?: number | null
  item_id?: number | null
  quantity: number
  required_date: string
  earliest_start?: string | null
  work_center_id?: number | null
  priority?: number | null
  remarks?: string
}

export interface WorkOrderUpdateInput {
  project_id?: number | null
  sales_order_id?: number | null
  item_id?: number | null
  quantity?: number | null
  required_date?: string | null
  earliest_start?: string | null
  work_center_id?: number | null
  priority?: number | null
  remarks?: string | null
}

export interface WorkOrderListQuery extends BaseListQuery {
  keyword?: string
  status?: string
  priority?: number
  work_center?: number
  project?: number
}

// ===== finance 应收(AccountReceivable),对齐 server/internal/finance AccountReceivable =====

export interface Receivable {
  id: number
  ar_no: string
  customer_id: number
  so_id?: number
  project_id?: number
  invoice_no: string
  invoice_date: string
  currency_id?: number
  amount_due: number
  amount_paid: number
  exchange_rate: number
  due_date: string
  status: string
  created_at?: string
  updated_at?: string
}

export interface ReceivableCreateInput {
  customer_id: number
  so_id?: number | null
  project_id?: number | null
  invoice_no?: string
  invoice_date: string
  currency_id?: number | null
  amount_due: number
  amount_paid?: number | null
  exchange_rate?: number | null
  due_date: string
}

export interface ReceivableUpdateInput {
  customer_id?: number | null
  so_id?: number | null
  project_id?: number | null
  invoice_no?: string | null
  invoice_date?: string | null
  currency_id?: number | null
  amount_due?: number | null
  amount_paid?: number | null
  exchange_rate?: number | null
  due_date?: string | null
  status?: string | null
}

export interface ReceivableListQuery extends BaseListQuery {
  keyword?: string
  status?: string
  customer_id?: number
  project_id?: number
}

// ===== oa 车辆(Vehicle),对齐 server/internal/oa Vehicle =====

export interface Vehicle {
  id: number
  plate_number: string
  vehicle_type: string
  brand: string
  model: string
  color: string
  seats: number
  engine_no: string
  vin: string
  insurance_company: string
  insurance_no: string
  insurance_expire_date?: string | null
  annual_inspection_date?: string | null
  next_inspection_date?: string | null
  current_mileage: number
  status: string
  manager_id?: number | null
  notes: string
  created_at?: string
  updated_at?: string
}

export interface VehicleCreateInput {
  plate_number: string
  vehicle_type?: string
  brand: string
  model: string
  color?: string
  seats?: number
  engine_no?: string
  vin?: string
  insurance_company?: string
  insurance_no?: string
  current_mileage?: number
  status?: string
  notes?: string
}

export interface VehicleUpdateInput {
  vehicle_type?: string | null
  brand?: string | null
  model?: string | null
  color?: string | null
  seats?: number | null
  engine_no?: string | null
  vin?: string | null
  insurance_company?: string | null
  insurance_no?: string | null
  current_mileage?: number | null
  status?: string | null
  notes?: string | null
}

// 车辆列表查询(注意后端关键字参数为 search,经 API 客户端映射)。
export interface VehicleListQuery extends BaseListQuery {
  search?: string
  status?: string
  vehicle_type?: string
  manager?: string
}

// ===== masterdata 客户(Customer),对齐 server/internal/masterdata/customer Customer =====

export interface Customer {
  id: number
  code: string
  name: string
  short_name: string
  contact_person: string
  phone: string
  email: string
  address: string
  credit_limit: number
  payment_terms: string
  invoice_title: string
  tax_number: string
  bank_name: string
  bank_account: string
  registered_address: string
  registered_phone: string
  status: string
  notes: string
  created_at?: string
  updated_at?: string
}

export interface CustomerCreateInput {
  code?: string
  name: string
  short_name?: string
  contact_person?: string
  phone?: string
  email?: string
  address?: string
  credit_limit?: number
  payment_terms?: string
  status?: string
  notes?: string
}

export interface CustomerUpdateInput {
  name?: string | null
  short_name?: string | null
  contact_person?: string | null
  phone?: string | null
  email?: string | null
  address?: string | null
  credit_limit?: number | null
  payment_terms?: string | null
  status?: string | null
  notes?: string | null
}

export interface CustomerListQuery extends BaseListQuery {
  keyword?: string
  status?: string
}

// ===== masterdata 供应商(Supplier),对齐 server/internal/masterdata/supplier Supplier =====

export interface Supplier {
  id: number
  code: string
  name: string
  short_name: string
  contact_person: string
  phone: string
  email: string
  address: string
  payment_terms: string
  settlement_method: string
  invoice_title: string
  tax_number: string
  bank_name: string
  bank_account: string
  registered_address: string
  registered_phone: string
  status: string
  notes: string
  created_at?: string
  updated_at?: string
}

export interface SupplierCreateInput {
  code?: string
  name: string
  short_name?: string
  contact_person?: string
  phone?: string
  email?: string
  address?: string
  payment_terms?: string
  settlement_method?: string
  status?: string
  notes?: string
}

export interface SupplierUpdateInput {
  name?: string | null
  short_name?: string | null
  contact_person?: string | null
  phone?: string | null
  email?: string | null
  address?: string | null
  payment_terms?: string | null
  settlement_method?: string | null
  status?: string | null
  notes?: string | null
}

export interface SupplierListQuery extends BaseListQuery {
  keyword?: string
  status?: string
}

// ===== masterdata 仓库(Warehouse),对齐 server/internal/masterdata/warehouse Warehouse =====

export interface Warehouse {
  id: number
  code: string
  name: string
  warehouse_type: string
  address: string
  manager_id?: number | null
  contact_phone: string
  is_active: boolean
  notes: string
  created_at?: string
  updated_at?: string
}

export interface WarehouseCreateInput {
  code: string
  name: string
  warehouse_type?: string
  address?: string
  contact_phone?: string
  is_active?: boolean | null
  notes?: string
}

export interface WarehouseUpdateInput {
  name?: string | null
  warehouse_type?: string | null
  address?: string | null
  contact_phone?: string | null
  is_active?: boolean | null
  notes?: string | null
}

export interface WarehouseListQuery extends BaseListQuery {
  keyword?: string
  warehouse_type?: string
  is_active?: boolean
}

// ===== accounts 用户(User,只读列表),对齐 server/internal/accounts User =====

export interface User {
  id: number
  username: string
  first_name: string
  last_name: string
  email: string
  is_active: boolean
  is_staff: boolean
  is_superuser: boolean
  employee_id: string
  phone: string
  position: string
  department_id?: number | null
  role_id?: number | null
  last_login?: string | null
  date_joined: string
  created_at?: string
  updated_at?: string
}

export interface UserListQuery extends BaseListQuery {
  keyword?: string
  department_id?: number
  role_id?: number
  is_active?: boolean
}
