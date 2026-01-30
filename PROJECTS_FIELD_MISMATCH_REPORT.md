# 前端Vue组件与后端API字段不匹配检查报告
检查时间: 2026-01-30 08:00:04
**总计发现 47 个字段不匹配问题**

---

## TaskList.vue
**对应序列化器**: `ProjectTaskSerializer`

### ❌ 后端未提供的字段
- **前端字段**: `inProgress`
  - 建议: 后端序列化器中未找到字段 "inProgress"，请检查是否需要添加或使用其他字段名
- **前端字段**: `total`
  - 建议: 后端序列化器中未找到字段 "total"，请检查是否需要添加或使用其他字段名
- **前端字段**: `totalActualHours`
  - 建议: 后端序列化器中未找到字段 "totalActualHours"，请检查是否需要添加或使用其他字段名
- **前端字段**: `completed`
  - 建议: 后端序列化器中未找到字段 "completed"，请检查是否需要添加或使用其他字段名
- **前端字段**: `totalPlannedDays`
  - 建议: 后端序列化器中未找到字段 "totalPlannedDays"，请检查是否需要添加或使用其他字段名

### 📋 前端使用的字段列表
```
actual_hours, assignee, assignee_name, completed, description, end_date, inProgress, parent, planned_hours, progress_percent, start_date, status, time_log_count, total, totalActualHours, totalPlannedDays
```

---

## ProjectDashboard.vue
**对应序列化器**: `ProjectSerializer`

### ❌ 后端未提供的字段
- **前端字段**: `finance`
  - 建议: 后端序列化器中未找到字段 "finance"，请检查是否需要添加或使用其他字段名
- **前端字段**: `time`
  - 建议: 后端序列化器中未找到字段 "time"，请检查是否需要添加或使用其他字段名
- **前端字段**: `budget`
  - 建议: 后端序列化器中未找到字段 "budget"，请检查是否需要添加或使用其他字段名
- **前端字段**: `bom`
  - 建议: 后端序列化器中未找到字段 "bom"，请检查是否需要添加或使用其他字段名

### 📋 前端使用的字段列表
```
bom, budget, customer_name, end_date, finance, manager_name, start_date, time
```

---

## ECNList.vue
**对应序列化器**: `ECNSerializer`

### ❌ 后端未提供的字段
- **前端字段**: `item_name`
  - 建议: 后端序列化器中未找到字段 "item_name"，请检查是否需要添加或使用其他字段名
- **前端字段**: `item`
  - 建议: 后端序列化器中未找到字段 "item"，请检查是否需要添加或使用其他字段名
- **前端字段**: `new_item_sku`
  - 建议: 后端序列化器中未找到字段 "new_item_sku"，请检查是否需要添加或使用其他字段名
- **前端字段**: `old_qty`
  - 建议: 后端序列化器中未找到字段 "old_qty"，请检查是否需要添加或使用其他字段名
- **前端字段**: `new_item_name`
  - 建议: 后端序列化器中未找到字段 "new_item_name"，请检查是否需要添加或使用其他字段名
- **前端字段**: `new_qty`
  - 建议: 后端序列化器中未找到字段 "new_qty"，请检查是否需要添加或使用其他字段名
- **前端字段**: `new_item`
  - 建议: 后端序列化器中未找到字段 "new_item"，请检查是否需要添加或使用其他字段名
- **前端字段**: `item_sku`
  - 建议: 后端序列化器中未找到字段 "item_sku"，请检查是否需要添加或使用其他字段名

### 📋 前端使用的字段列表
```
approved_by_name, approved_date, change_type, change_type_display, cost_impact, description, ecn_no, impact_analysis, implementation_notes, implemented_by_name, implemented_date, item, item_name, item_sku, items_count, new_item, new_item_name, new_item_sku, new_qty, old_qty, priority, priority_display, project, project_code, project_name, reason, requested_by_name, requested_date, schedule_impact, status, status_display
```

---

## BOMList.vue
**对应序列化器**: `ProjectBOMSerializer`

### ❌ 后端未提供的字段
- **前端字段**: `summary`
  - 建议: 后端序列化器中未找到字段 "summary"，请检查是否需要添加或使用其他字段名
- **前端字段**: `length`
  - 建议: 后端序列化器中未找到字段 "length"，请检查是否需要添加或使用其他字段名

### 📋 前端使用的字段列表
```
actual_qty, delivery_date, has_drawing_display, issued_qty, item, item_code, item_name, item_sku, item_type, length, order_status, order_status_display, ordered_qty, planned_qty, project_name, received_qty, requester_name, required_date, specification, status, status_display, summary, supplier_name, unit, version_brand_display
```

---

## ServiceOrderDetail.vue
**对应序列化器**: `AfterSalesOrderSerializer`

### ❌ 后端未提供的字段
- **前端字段**: `technician_name`
  - 建议: 后端序列化器中未找到字段 "technician_name"，请检查是否需要添加或使用其他字段名
- **前端字段**: `service_type_display`
  - 建议: 后端序列化器中未找到字段 "service_type_display"，请检查是否需要添加或使用其他字段名

### 📋 前端使用的字段列表
```
contact_phone, customer_name, description, order_no, service_type_display, status_display, technician_name
```

---

## MemberList.vue
**对应序列化器**: `ProjectMemberSerializer`

### ❌ 后端未提供的字段
- **前端字段**: `department`
  - 建议: 后端序列化器中未找到字段 "department"，请检查是否需要添加或使用其他字段名
- **前端字段**: `email`
  - 建议: 后端序列化器中未找到字段 "email"，请检查是否需要添加或使用其他字段名
- **前端字段**: `length`
  - 建议: 后端序列化器中未找到字段 "length"，请检查是否需要添加或使用其他字段名

### 📋 前端使用的字段列表
```
department, email, hourly_rate, join_date, labor_cost, length, role, total_hours, user_department, user_email
```

---

## ProjectList.vue
**对应序列化器**: `ProjectSerializer`

### ❌ 后端未提供的字段
- **前端字段**: `order_no`
  - 建议: 后端序列化器中未找到字段 "order_no"，请检查是否需要添加或使用其他字段名
- **前端字段**: `line_amount`
  - 建议: 后端序列化器中未找到字段 "line_amount"，请检查是否需要添加或使用其他字段名
- **前端字段**: `order_date`
  - 建议: 后端序列化器中未找到字段 "order_date"，请检查是否需要添加或使用其他字段名
- **前端字段**: `total_with_tax`
  - 建议: 后端序列化器中未找到字段 "total_with_tax"，请检查是否需要添加或使用其他字段名
- **前端字段**: `lines`
  - 建议: 后端序列化器中未找到字段 "lines"，请检查是否需要添加或使用其他字段名
- **前端字段**: `qty`
  - 建议: 后端序列化器中未找到字段 "qty"，请检查是否需要添加或使用其他字段名
- **前端字段**: `unit_price`
  - 建议: 后端序列化器中未找到字段 "unit_price"，请检查是否需要添加或使用其他字段名
- **前端字段**: `customer_order_no`
  - 建议: 后端序列化器中未找到字段 "customer_order_no"，请检查是否需要添加或使用其他字段名
- **前端字段**: `delivery_date`
  - 建议: 后端序列化器中未找到字段 "delivery_date"，请检查是否需要添加或使用其他字段名
- **前端字段**: `spec`
  - 建议: 后端序列化器中未找到字段 "spec"，请检查是否需要添加或使用其他字段名
- **前端字段**: `product_name`
  - 建议: 后端序列化器中未找到字段 "product_name"，请检查是否需要添加或使用其他字段名

### 📋 前端使用的字段列表
```
customer, customer_name, customer_order_no, delivery_date, end_date, line_amount, lines, manager_name, order_date, order_no, product_name, qty, sales_order_no, spec, start_date, status, total_with_tax, unit_price
```

---

## WorkOrderList.vue
**对应序列化器**: `AfterSalesOrderSerializer`

### ❌ 后端未提供的字段
- **前端字段**: `dispatch_count`
  - 建议: 后端序列化器中未找到字段 "dispatch_count"，请检查是否需要添加或使用其他字段名

### 📋 前端使用的字段列表
```
dispatch_count, order_no, order_type, order_type_display, priority, priority_display, project_name, status, status_display
```

---

## ServiceOrder.vue
**对应序列化器**: `AfterSalesOrderSerializer`

### ❌ 后端未提供的字段
- **前端字段**: `planned_start_date`
  - 建议: 后端序列化器中未找到字段 "planned_start_date"，请检查是否需要添加或使用其他字段名
- **前端字段**: `technician_count`
  - 建议: 后端序列化器中未找到字段 "technician_count"，请检查是否需要添加或使用其他字段名
- **前端字段**: `user_id`
  - 建议: 后端序列化器中未找到字段 "user_id"，请检查是否需要添加或使用其他字段名
- **前端字段**: `planned_end_date`
  - 建议: 后端序列化器中未找到字段 "planned_end_date"，请检查是否需要添加或使用其他字段名
- **前端字段**: `requested_date`
  - 建议: 后端序列化器中未找到字段 "requested_date"，请检查是否需要添加或使用其他字段名
- **前端字段**: `service_type`
  - 建议: 后端序列化器中未找到字段 "service_type"，请检查是否需要添加或使用其他字段名
- **前端字段**: `service_type_display`
  - 建议: 后端序列化器中未找到字段 "service_type_display"，请检查是否需要添加或使用其他字段名

### 📋 前端使用的字段列表
```
contact_phone, customer, customer_name, order_no, planned_end_date, planned_start_date, priority, priority_display, requested_date, service_type, service_type_display, status, status_display, technician_count, user_id
```

---

## TimeLogList.vue
**对应序列化器**: `TimeLogSerializer`

### ❌ 后端未提供的字段
- **前端字段**: `avgHours`
  - 建议: 后端序列化器中未找到字段 "avgHours"，请检查是否需要添加或使用其他字段名
- **前端字段**: `weekHours`
  - 建议: 后端序列化器中未找到字段 "weekHours"，请检查是否需要添加或使用其他字段名
- **前端字段**: `monthHours`
  - 建议: 后端序列化器中未找到字段 "monthHours"，请检查是否需要添加或使用其他字段名
- **前端字段**: `workDays`
  - 建议: 后端序列化器中未找到字段 "workDays"，请检查是否需要添加或使用其他字段名

### 📋 前端使用的字段列表
```
avgHours, created_at, date, description, hours, monthHours, project, project_name, status, task, task_name, weekHours, workDays
```

---

