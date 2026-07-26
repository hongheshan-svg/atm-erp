type ValidationRule = {
  required: boolean
  message: string
  trigger: 'blur' | 'change'
}

export const projectFormRules: Record<string, ValidationRule[]> = {
  name: [{ required: true, message: '请输入项目名称', trigger: 'blur' }],
  customer: [{ required: true, message: '请选择客户', trigger: 'change' }],
  manager: [{ required: true, message: '请选择项目经理', trigger: 'change' }],
  start_date: [{ required: true, message: '请选择开始日期', trigger: 'change' }],
  end_date: [{ required: true, message: '请选择结束日期', trigger: 'change' }]
}

function toPositiveNumber(value: unknown): number {
  const amount = Number.parseFloat(String(value ?? 0))
  return Number.isFinite(amount) && amount > 0 ? amount : 0
}

export function getBomEstimatedUnitCost(item: Record<string, any>): number {
  return toPositiveNumber(item.standard_cost) || toPositiveNumber(item.purchase_price)
}

export function getPurchaseOrderUnitPrice(item: Record<string, any>): number {
  return (
    toPositiveNumber(item.last_purchase_price)
    || toPositiveNumber(item.purchase_price)
    || toPositiveNumber(item.standard_cost)
  )
}

export function getTaxInclusiveTotal(record: Record<string, any>): number {
  return toPositiveNumber(record.total_with_tax) || toPositiveNumber(record.total_amount)
}
