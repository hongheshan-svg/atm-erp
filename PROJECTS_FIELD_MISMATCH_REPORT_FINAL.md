# 前端Vue组件与后端API字段不匹配检查报告（最终版）

检查时间: 2026-01-30 08:00:04

## 说明

本报告仅列出**真正需要修复**的字段不匹配问题，已排除：
- 前端计算的统计字段（如 `total`, `inProgress` 等）
- 数组属性（如 `length`）
- 关联对象的字段（如销售订单的字段在项目列表中显示）
- 嵌套序列化器的字段（如 ECNItem 的字段在 ECN 的 items 数组中）

---

## 需要修复的问题

### 1. ECNList.vue
**对应序列化器**: `ECNSerializer`

**状态**: ✅ **无需修复** - 代码中已正确使用 `currentECN.items` 和 `form.items` 来访问 ECNItem 的字段

**说明**: 
- 代码第328行使用 `currentECN.items` 显示变更明细，这是正确的
- 代码第215行使用 `form.items` 编辑变更项，这也是正确的
- ECNItemSerializer 已包含所有需要的字段（`item_name`, `item_sku`, `new_item_name`, `new_item_sku`, `old_qty`, `new_qty`）
- 脚本误报是因为它检查的是 ECNSerializer 本身，而不是 items 数组中的 ECNItem

---

### 2. ServiceOrderDetail.vue
**对应序列化器**: `AfterSalesOrderSerializer`

**问题**: 
1. `order.service_type_display` - AfterSalesOrderSerializer 中没有 `service_type_display` 字段，这个字段应该在 `service_records` 数组中
2. `order.dispatches` - 序列化器中没有 `dispatches` 字段，应该使用 `service_records`

**问题字段**:
- `service_type_display` (第9行) → 如果工单本身有服务类型，需要在序列化器中添加；否则应该从 `service_records[0].service_type_display` 获取
- `dispatches` (第21行) → 应改为 `service_records`
- `technician_name` (第22行) → 应使用 `service_records[].technician_name`

**建议修复方案**:
```vue
<!-- 修改前 -->
<el-descriptions-item label="服务类型">{{ order.service_type_display }}</el-descriptions-item>
<el-table :data="order.dispatches || []" stripe>
  <el-table-column prop="technician_name" label="技术员" />

<!-- 修改后 -->
<el-descriptions-item label="服务类型">
  {{ order.service_records?.[0]?.service_type_display || '-' }}
</el-descriptions-item>
<el-table :data="order.service_records || []" stripe>
  <el-table-column prop="technician_name" label="技术员" />
```

---

### 3. ServiceOrder.vue
**对应序列化器**: `AfterSalesOrderSerializer` / `AfterSalesOrderListSerializer`

**问题**: 
1. `row.service_type_display` - AfterSalesOrderListSerializer 中没有 `service_type_display` 字段
2. `row.requested_date` - 序列化器中使用的是 `reported_at` 或 `expected_date`，没有 `requested_date`
3. `row.technician_count` - 序列化器中没有此字段，可能需要从 `service_records` 计算

**问题字段**:
- `service_type_display` (第62行) → 需要从 `service_records[0].service_type_display` 获取，或后端添加此字段
- `requested_date` (第65行) → 应改为 `reported_at` 或 `expected_date`
- `technician_count` (第74行) → 应改为 `service_count`（序列化器已提供）或从 `service_records.length` 计算

**建议修复方案**:
```vue
<!-- 修改前 -->
<el-table-column prop="service_type_display" label="服务类型" width="90" />
<el-table-column label="期望日期" width="110">
  <template #default="{ row }">{{ row.requested_date }}</template>
</el-table-column>
<span v-if="row.technician_count > 0">{{ row.technician_count }}人</span>

<!-- 修改后 -->
<el-table-column label="服务类型" width="90">
  <template #default="{ row }">
    {{ row.service_records?.[0]?.service_type_display || '-' }}
  </template>
</el-table-column>
<el-table-column label="期望日期" width="110">
  <template #default="{ row }">{{ row.expected_date || row.reported_at }}</template>
</el-table-column>
<span v-if="row.service_count > 0">{{ row.service_count }}人</span>
```

---

### 3. MemberList.vue
**对应序列化器**: `ProjectMemberSerializer`

**状态**: ✅ **无需修复** - 代码中已正确使用序列化器提供的字段

**说明**:
- 表格中已使用 `user_email` 和 `user_department`（第60-61行）
- `user.department_name` 和 `user.email` 是在表单中选择用户时从用户列表获取的，不是API返回的字段，这是正常的

---

## 正常情况（无需修复）

以下字段不匹配是**正常情况**，无需修复：

### TaskList.vue
- `inProgress`, `total`, `totalActualHours`, `completed`, `totalPlannedDays` - 前端计算的统计字段

### ProjectDashboard.vue
- `finance`, `time`, `budget`, `bom` - 前端计算的统计字段或关联数据

### BOMList.vue
- `summary` - 齐套检查接口返回的数据结构
- `length` - 数组属性

### ProjectList.vue
- `order_no`, `lines`, `qty`, `unit_price`, `line_amount`, `customer_order_no`, `delivery_date`, `order_date`, `total_with_tax`, `spec`, `product_name` - 这些是关联的销售订单字段，在项目详情中显示是正常的

### TimeLogList.vue
- `avgHours`, `weekHours`, `monthHours`, `workDays` - 前端计算的统计字段

### WorkOrderList.vue
- `dispatch_count` - 可能是前端计算的统计字段

### ServiceOrder.vue
- `planned_start_date`, `planned_end_date`, `requested_date` - 可能是前端表单字段或关联数据
- `technician_count`, `user_id` - 前端计算的统计字段或关联数据

---

## 总结

**真正需要修复的问题**: 2个文件

1. **ServiceOrderDetail.vue** - 需要修复 `service_type_display` 和 `dispatches` 字段的访问方式
2. **ServiceOrder.vue** - 需要修复 `service_type_display`、`requested_date` 和 `technician_count` 字段

**已确认无需修复**:
- **ECNList.vue** - 已正确使用 `items` 数组访问字段
- **MemberList.vue** - 已正确使用序列化器提供的字段

建议优先修复这两个文件中的问题，以确保前端能正确获取和显示后端API返回的数据。
