# Finance模块字段不匹配检查报告

## 检查时间
2026-01-30

## 检查范围
- 前端文件：`/home/administrator/erp/frontend/src/views/finance/` 目录下的所有Vue组件
- 后端序列化器：`/home/administrator/erp/backend/apps/finance/` 目录下的序列化器

---

## 1. APList.vue (应付账款列表)

### 对应序列化器
`AccountPayableSerializer`

### 前端使用的字段
- `supplier_name` ✓
- `purchase_order_no` ✓ (后端提供)
- `invoice_no` ✓
- `amount_due` ✓
- `amount_paid` ✓
- `due_date` ✓
- `status` ✓
- `created_at` ✓
- `notes` ✓ (在详情中使用)

### 问题字段
**无问题** - 所有使用的字段都在序列化器中定义

### 建议
无需修复

---

## 2. ARList.vue (应收账款列表)

### 对应序列化器
`AccountReceivableSerializer`

### 前端使用的字段
- `customer_name` ✓
- `sales_order_no` ✓ (后端提供)
- `project_name` ✓ (后端提供)
- `amount_due` ✓
- `amount_paid` ✓
- `due_date` ✓
- `status` ✓
- `created_at` ✓
- `notes` ✓ (在详情中使用)

### 问题字段
**无问题** - 所有使用的字段都在序列化器中定义

### 建议
无需修复

---

## 3. AssetList.vue (固定资产列表)

### 对应序列化器
`FixedAssetListSerializer` (列表) / `FixedAssetSerializer` (详情)

### 前端使用的字段
- `asset_no` ✓
- `name` ✓
- `model` ✓
- `category_name` ✓
- `department_name` ✓
- `custodian_name` ✓
- `original_value` ✓
- `accumulated_depreciation` ✓
- `net_value` ✓
- `status` ✓
- `status_display` ✓
- `purchase_date` ✓
- `start_date` ⚠️ (详情中使用，但序列化器使用`__all__`，需要确认模型字段)
- `location` ✓
- `brand` ⚠️ (表单中使用，但列表序列化器未包含)
- `serial_number` ⚠️ (表单中使用，但列表序列化器未包含)
- `manufacturer` ⚠️ (表单中使用，但列表序列化器未包含)
- `depreciation_records` ⚠️ (详情中使用，序列化器有`depreciations`字段)
- `changes` ⚠️ (详情中使用，序列化器有`transfers`字段)

### 问题字段

1. **`start_date`** 
   - 前端使用：详情对话框显示
   - 后端：`FixedAssetSerializer`使用`__all__`，如果模型有该字段则可用
   - 状态：需确认模型字段

2. **`brand`, `serial_number`, `manufacturer`**
   - 前端使用：表单编辑
   - 后端：`FixedAssetListSerializer`未包含这些字段
   - 状态：列表视图可能不需要，但详情视图需要

3. **`depreciation_records` vs `depreciations`**
   - 前端使用：`currentAsset.depreciation_records`
   - 后端提供：`depreciations`
   - 状态：字段名不一致

4. **`changes` vs `transfers`**
   - 前端使用：`currentAsset.changes`
   - 后端提供：`transfers`
   - 状态：字段名不一致，且`transfers`只包含调拨记录，不包含所有变动

### 建议修复方案

1. 将`depreciation_records`改为`depreciations`
2. 将`changes`改为`transfers`，或后端添加`changes`字段包含所有变动记录
3. 确认`start_date`字段在模型和序列化器中是否存在

---

## 4. CollectionPlanList.vue (回款计划列表)

### 对应序列化器
`CollectionPlanListSerializer` (列表) / `CollectionPlanSerializer` (详情)

### 前端使用的字段
- `plan_no` ✓
- `name` ✓
- `customer_name` ✓
- `project_name` ✓
- `total_amount` ✓
- `collected_amount` ✓
- `collection_rate` ✓
- `status` ✓
- `status_display` ✓
- `milestone_count` ✓
- `overdue_count` ✓
- `milestones` ✓ (详情中使用)
- `milestone_type_display` ✓ (在milestones中)
- `planned_amount` ✓ (在milestones中)
- `collected_amount` ✓ (在milestones中)
- `planned_date` ✓ (在milestones中)
- `is_overdue` ✓ (在milestones中)

### 问题字段
**无问题** - 所有使用的字段都在序列化器中定义

### 建议
无需修复

---

## 5. ExpenseList.vue (费用报销列表)

### 对应序列化器
`ExpenseSerializer`

### 前端使用的字段
- `expense_no` ✓
- `user_name` ✓
- `project_name` ✓
- `category` ✓
- `amount` ✓
- `expense_date` ✓
- `status` ✓
- `description` ✓
- `department_name` ✓ (详情中使用)
- `reimbursement_date` ✓ (详情中使用)
- `created_at` ✓ (详情中使用)

### 问题字段
**无问题** - 所有使用的字段都在序列化器中定义

### 建议
无需修复

---

## 6. InvoiceList.vue (发票列表)

### 对应序列化器
`InvoiceSerializer`

### 前端使用的字段
- `digital_invoice_no` ✓
- `invoice_no` ✓
- `invoice_type` ✓
- `invoice_date` ✓
- `seller_name` ✓
- `buyer_name` ✓
- `amount_before_tax` ✓
- `tax_amount` ✓
- `total_amount` ✓
- `status` ✓
- `sales_order_no` ✓
- `purchase_order_no` ✓
- `project_code` ✓
- `project_name` ✓
- `item_count` ✓
- `attachment_count` ✓
- `items` ✓ (详情中使用)
- `invoice_source` ✓ (详情中使用)
- `invoice_category_display` ✓ (详情中使用)
- `created_by_name` ✓ (详情中使用)
- `notes` ✓ (详情中使用)
- `seller_tax_no` ✓ (详情中使用)
- `buyer_tax_no` ✓ (详情中使用)

### 问题字段
**无问题** - 所有使用的字段都在序列化器中定义

### 建议
无需修复

---

## 7. ProjectCostList.vue (项目成本核算)

### 对应序列化器
**未找到对应的序列化器** - 该组件调用`/analytics/project-costs/`接口

### 前端使用的字段
- `code` ⚠️
- `name` ⚠️
- `manager_name` ⚠️
- `status` ⚠️
- `budget_total` ⚠️
- `revenue` ⚠️
- `material_cost` ⚠️
- `labor_cost` ⚠️
- `expense_cost` ⚠️
- `total_cost` ⚠️
- `profit` ⚠️
- `profit_margin` ⚠️
- `budget_usage` ⚠️
- `budget_material` ⚠️ (详情中使用)
- `budget_labor` ⚠️ (详情中使用)
- `budget_expense` ⚠️ (详情中使用)
- `start_date` ⚠️ (详情中使用)
- `end_date` ⚠️ (详情中使用)

### 问题字段
**无法验证** - 该组件使用的API端点不在finance模块中，可能在analytics模块

### 建议
1. 检查`/analytics/project-costs/`接口对应的序列化器
2. 确认该接口返回的字段是否与前端使用的一致

---

## 8. PurchaseReconciliation.vue (采购对账)

### 对应序列化器
`PurchaseReconciliationListSerializer` (列表) / `PurchaseReconciliationSerializer` (详情)

### 前端使用的字段
- `reconciliation_no` ✓
- `supplier_name` ✓
- `period_start` ✓
- `period_end` ✓
- `total_order_amount` ✓
- `total_received_amount` ✓
- `total_invoice_amount` ✓
- `total_paid_amount` ✓
- `balance_amount` ✓
- `status` ✓
- `opening_balance` ✓ (详情中使用)
- `closing_balance` ✓ (详情中使用)
- `lines` ✓ (详情中使用)
- `line_type` ✓ (在lines中)
- `reference_no` ✓ (在lines中)
- `reference_date` ✓ (在lines中)
- `description` ✓ (在lines中)
- `order_amount` ✓ (在lines中)
- `received_amount` ✓ (在lines中)
- `invoice_amount` ✓ (在lines中)
- `paid_amount` ✓ (在lines中)
- `receipt_confirmed` ✓ (在lines中)
- `tax_amount` ✓ (在lines中)
- `payment_method` ✓ (在lines中)
- `is_deducted` ✓ (在lines中)
- `created_by_name` ✓ (详情中使用)
- `supplier_contact` ✓ (详情中使用)
- `supplier_phone` ✓ (详情中使用)

### 问题字段
**无问题** - 所有使用的字段都在序列化器中定义

### 建议
无需修复

---

## 9. SalesReconciliation.vue (销售对账)

### 对应序列化器
`SalesReconciliationListSerializer` (列表) / `SalesReconciliationSerializer` (详情)

### 前端使用的字段
- `reconciliation_no` ✓
- `customer_name` ✓
- `period_start` ✓
- `period_end` ✓
- `total_order_amount` ✓
- `total_delivered_amount` ✓
- `total_invoice_amount` ✓
- `total_received_amount` ✓
- `balance_amount` ✓
- `status` ✓
- `opening_balance` ✓ (详情中使用)
- `closing_balance` ✓ (详情中使用)
- `lines` ✓ (详情中使用)
- `line_type` ✓ (在lines中)
- `reference_no` ✓ (在lines中)
- `reference_date` ✓ (在lines中)
- `description` ✓ (在lines中)
- `order_amount` ✓ (在lines中)
- `delivered_amount` ✓ (在lines中)
- `invoice_amount` ✓ (在lines中)
- `received_amount` ✓ (在lines中)
- `delivery_confirmed` ✓ (在lines中)
- `tax_amount` ✓ (在lines中)
- `payment_method` ✓ (在lines中)
- `created_by_name` ✓ (详情中使用)
- `customer_contact` ✓ (详情中使用)
- `customer_phone` ✓ (详情中使用)

### 问题字段
**无问题** - 所有使用的字段都在序列化器中定义

### 建议
无需修复

---

## 10. SharedExpenseList.vue (公共费用分摊)

### 对应序列化器
`SharedExpenseSerializer`

### 前端使用的字段
- `expense_no` ✓
- `name` ✓
- `category_display` ✓
- `expense_date` ✓
- `amount` ✓
- `allocation_method_display` ✓
- `status` ✓
- `status_display` ✓
- `period_start` ✓
- `period_end` ✓
- `allocations` ✓ (详情中使用)
- `project_code` ✓ (在allocations中)
- `project_name` ✓ (在allocations中)
- `allocation_ratio` ✓ (在allocations中)
- `allocated_amount` ✓ (在allocations中)
- `description` ✓ (详情中使用)
- `notes` ✓ (详情中使用)
- `allocated_by_name` ✓ (详情中使用)

### 问题字段

1. **`data` vs `response`**
   - 第395行：`currentExpense.value = data` 
   - 但实际变量是`response`
   - 状态：代码错误，应该是`response`而不是`data`

2. **`data.allocations` vs `response.allocations`**
   - 第434行：`allocationPreview.value = data.allocations || []`
   - 但实际变量是`response`
   - 状态：代码错误，应该是`response.allocations`

### 建议修复方案

1. 修复第395行：将`data`改为`response`
2. 修复第434行：将`data.allocations`改为`response.allocations`

---

## 总结

### 已修复的文件

1. **AssetList.vue** ✅
   - ✅ 已修复：`depreciation_records` → `depreciations` (第257-258行)
   - ✅ 已修复：`changes` → `transfers` (第287-290行)
   - ⚠️ 注意：`transfers`只包含调拨记录，如需显示所有变动（购置、维修、升级、重估、处置、报废等），建议后端添加`changes`字段或使用其他方式获取完整变动记录
   - ⚠️ 需要确认：`start_date`字段（第244行）- 如果模型中没有该字段，可能需要使用其他字段或后端添加

2. **SharedExpenseList.vue** ✅
   - ✅ 已修复：第395行 `data` → `response`
   - ✅ 已修复：第434行 `data.allocations` → `response.allocations`

### 需要进一步检查

1. **ProjectCostList.vue** - 需要检查analytics模块的序列化器，确认`/analytics/project-costs/`接口返回的字段
2. **AssetList.vue** - 确认`start_date`字段是否存在，以及是否需要添加完整的变动记录字段

### 无需修复的文件

- APList.vue
- ARList.vue
- CollectionPlanList.vue
- ExpenseList.vue
- InvoiceList.vue
- PurchaseReconciliation.vue
- SalesReconciliation.vue

---

## 修复优先级

1. **高优先级**：SharedExpenseList.vue的代码错误（会导致运行时错误）
2. **中优先级**：AssetList.vue的字段名不匹配（会导致数据显示问题）
3. **低优先级**：ProjectCostList.vue的字段验证（需要检查analytics模块）
