// ===== Base Types =====

export interface BaseModel {
  id: number
  created_at: string
  updated_at: string
  created_by?: number
  updated_by?: number
  is_deleted?: boolean
}

export interface PaginatedResponse<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

// ===== Auth & Accounts =====

export interface User {
  id: number
  username: string
  email: string
  first_name: string
  last_name: string
  is_active: boolean
  is_staff: boolean
  is_superuser: boolean
  department?: Department
  roles: Role[]
  permissions: string[]
  menus: string[]
  data_scopes: Record<string, string>
}

export interface Role {
  id: number
  name: string
  code: string
  permissions: string[]
  data_scope: string
}

export interface Department {
  id: number
  name: string
  code: string
  parent?: number
  manager?: number
}

export interface LoginResponse {
  access: string
  refresh: string
  user: User
}

// ===== Projects =====

export interface Project extends BaseModel {
  code: string
  name: string
  customer?: number
  customer_name?: string
  manager?: number
  manager_name?: string
  status: ProjectStatus
  start_date?: string
  end_date?: string
  budget?: string
  actual_cost?: string
  progress?: number
}

export type ProjectStatus =
  | 'PLANNING'
  | 'DESIGN'
  | 'PROCUREMENT'
  | 'PRODUCTION'
  | 'ASSEMBLY'
  | 'TESTING'
  | 'DELIVERY'
  | 'COMPLETED'
  | 'ON_HOLD'
  | 'CANCELLED'

export interface ProjectBOM extends BaseModel {
  project: number
  item: number
  item_name?: string
  qty: string
  unit_price?: string
  is_critical: boolean
  is_long_lead: boolean
  function_module?: string
  drawing_no?: string
  technical_requirement?: string
}

// ===== Sales =====

export interface SalesOrder extends BaseModel {
  order_no: string
  customer: number
  customer_name?: string
  project?: number
  project_name?: string
  order_date: string
  delivery_date: string
  status: SalesOrderStatus
  total_amount: string
  tax_rate: number
  tax_amount: string
  total_with_tax: string
  notes?: string
}

export type SalesOrderStatus =
  | 'DRAFT'
  | 'SUBMITTED'
  | 'PENDING'
  | 'APPROVED'
  | 'PREPARING'
  | 'LOGISTICS_BOOKING'
  | 'CUSTOMER_SIGNING'
  | 'UPLOADING_RECEIPT'
  | 'PROJECT_CONFIRMING'
  | 'COMPLETED'
  | 'REJECTED'

export interface Quotation extends BaseModel {
  quotation_no: string
  customer: number
  customer_name?: string
  project?: number
  status: 'DRAFT' | 'SENT' | 'ACCEPTED' | 'REJECTED' | 'EXPIRED'
  total_amount: string
  valid_until: string
}

export interface DeliveryOrder extends BaseModel {
  delivery_no: string
  sales_order: number
  status: 'DRAFT' | 'CONFIRMED' | 'SHIPPED' | 'DELIVERED'
  delivery_date: string
  logistics_company?: string
  tracking_no?: string
}

export interface SalesContract extends BaseModel {
  contract_no: string
  customer: number
  sales_order?: number
  status: 'DRAFT' | 'PENDING' | 'APPROVED' | 'SIGNED' | 'COMPLETED' | 'CANCELLED'
  total_amount: string
  contract_date: string
}

// ===== Purchase =====

export interface PurchaseRequest extends BaseModel {
  request_no: string
  project?: number
  supplier?: number
  supplier_name?: string
  requestor: number
  request_date: string
  required_date: string
  status: PurchaseRequestStatus
  tax_rate: number
  total_amount: string
  tax_amount: string
  total_with_tax: string
  notes?: string
}

export type PurchaseRequestStatus =
  | 'DRAFT'
  | 'SUBMITTED'
  | 'APPROVED'
  | 'REJECTED'
  | 'CONVERTED'

export interface PurchaseOrder extends BaseModel {
  order_no: string
  supplier: number
  supplier_name?: string
  project?: number
  order_date: string
  delivery_date: string
  status: PurchaseOrderStatus
  tax_rate: number
  total_amount: string
  tax_amount: string
  total_with_tax: string
  payment_terms: string
  payment_method: string
  notes?: string
}

export type PurchaseOrderStatus =
  | 'DRAFT'
  | 'PENDING'
  | 'APPROVED'
  | 'REJECTED'
  | 'CONFIRMED'
  | 'PARTIAL'
  | 'COMPLETED'
  | 'CANCELLED'

export interface PurchaseContract extends BaseModel {
  contract_no: string
  po: number
  supplier: number
  supplier_name?: string
  project?: number
  title: string
  contract_date: string
  status: 'DRAFT' | 'PENDING' | 'APPROVED' | 'REJECTED' | 'SIGNED' | 'COMPLETED' | 'CANCELLED'
  total_amount: string
  total_with_tax: string
}

// ===== Inventory =====

export interface InventoryItem extends BaseModel {
  item: number
  item_name?: string
  warehouse: number
  warehouse_name?: string
  qty: string
  available_qty: string
  reserved_qty: string
}

export interface StockMove extends BaseModel {
  move_no: string
  move_type: 'IN' | 'OUT' | 'TRANSFER'
  status: 'DRAFT' | 'CONFIRMED' | 'COMPLETED'
  source_warehouse?: number
  dest_warehouse?: number
  item: number
  qty: string
}

export interface Material extends BaseModel {
  sku: string
  name: string
  category?: number
  unit: string
  spec?: string
  safety_stock?: string
  lead_time_days?: number
}

// ===== Finance =====

export interface Expense extends BaseModel {
  expense_no: string
  category: string
  amount: string
  status: 'DRAFT' | 'SUBMITTED' | 'APPROVED' | 'REJECTED' | 'PAID'
  applicant: number
  expense_date: string
}

export interface PaymentRequest extends BaseModel {
  payment_no: string
  supplier?: number
  amount: string
  status: 'DRAFT' | 'PENDING' | 'APPROVED' | 'REJECTED' | 'PAID'
  due_date: string
}

// ===== Workflow =====

export interface WorkflowDefinition extends BaseModel {
  name: string
  business_type: string
  is_active: boolean
  steps: WorkflowStep[]
  amount_min?: string
  amount_max?: string
}

export interface WorkflowStep {
  id?: number
  step_order: number
  name: string
  approver_type: 'USER' | 'ROLE' | 'DEPARTMENT_HEAD' | 'PROJECT_MANAGER'
  approver_id?: number
  approver_role?: number
}

export interface WorkflowInstance extends BaseModel {
  workflow: number
  business_type: string
  business_id: number
  business_no: string
  status: WorkflowInstanceStatus
  current_step: number
  initiator: number
  initiator_name?: string
}

export type WorkflowInstanceStatus =
  | 'PENDING'
  | 'IN_PROGRESS'
  | 'APPROVED'
  | 'REJECTED'
  | 'WITHDRAWN'

export interface WorkflowTask extends BaseModel {
  instance: number
  step: number
  step_name: string
  assignee: number
  assignee_name?: string
  status: 'PENDING' | 'APPROVED' | 'REJECTED'
  comment?: string
  completed_at?: string
}

// ===== Notification =====

export interface Notification {
  id: number
  title: string
  message: string
  type: 'INFO' | 'WARNING' | 'ERROR' | 'SUCCESS'
  is_read: boolean
  created_at: string
}

// ===== API Request Types =====

export interface ListParams {
  page?: number
  page_size?: number
  search?: string
  ordering?: string
  [key: string]: any
}
