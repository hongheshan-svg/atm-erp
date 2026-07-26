export function createInventoryCostConfigForm(): Record<string, any> {
  return {
    id: null,
    name: '',
    costing_method: 'WEIGHTED_AVG',
    period_type: 'MONTHLY',
    include_purchase_price: true,
    include_freight: true,
    include_tax: false,
    include_handling: false,
    is_default: false,
    is_active: true,
    description: ''
  }
}

export function toInventoryCostConfigPayload(form: Record<string, any>): Record<string, any> {
  return {
    name: form.name,
    costing_method: form.costing_method,
    period_type: form.period_type,
    include_purchase_price: form.include_purchase_price,
    include_freight: form.include_freight,
    include_tax: form.include_tax,
    include_handling: form.include_handling,
    is_default: form.is_default,
    is_active: form.is_active,
    description: form.description
  }
}
