# 库存模块前端字段与后端API不匹配检查报告

## 检查范围
- 前端目录：`/home/administrator/erp/frontend/src/views/inventory/`
- 后端序列化器：`/home/administrator/erp/backend/apps/inventory/serializers.py` 及相关序列化器文件

## 检查结果总结

### ✅ 已修复的问题

#### 1. StockList.vue
- **问题**：`prop="unit_cost"` 但后端提供的是 `weighted_avg_cost`
- **位置**：第39行
- **状态**：✅ 已修复为 `prop="weighted_avg_cost"`

#### 2. StockTransfer.vue  
- **问题**：使用了 `from_warehouse_name`/`to_warehouse_name`，但后端提供的是 `warehouse_from_name`/`warehouse_to_name`
- **位置**：第82-83行
- **状态**：✅ 已修复为 `warehouse_from_name`/`warehouse_to_name`

### ✅ 无问题的文件

1. **StockAdjustmentList.vue** - 所有字段匹配
2. **BatchList.vue** - 所有字段匹配
3. **RequisitionList.vue** - 所有字段匹配
4. **ReturnList.vue** - 所有字段匹配
5. **StockMoveList.vue** - 所有字段匹配（已正确使用 `warehouse_from_name`/`warehouse_to_name`）

## 详细检查结果

### StockSerializer 字段匹配检查
- ✅ `warehouse_name` - 匹配
- ✅ `item_name` - 匹配
- ✅ `item_sku` - 匹配
- ✅ `qty_on_hand` - 匹配
- ✅ `qty_reserved` - 匹配
- ✅ `qty_available` - 匹配
- ✅ `weighted_avg_cost` - ✅ 已修复

### StockMoveSerializer 字段匹配检查
- ✅ `move_no` - 匹配
- ✅ `item_name` - 匹配
- ✅ `item_code` - 匹配（后端提供兼容字段）
- ✅ `warehouse_from_name` - ✅ 已修复
- ✅ `warehouse_to_name` - ✅ 已修复
- ✅ `qty` - 匹配
- ✅ `unit_cost` - 匹配
- ✅ `move_type_display` - 匹配
- ✅ `status_display` - 匹配
- ✅ `project_name` - 匹配
- ✅ `reference_no` - 匹配
- ✅ `created_by_name` - 匹配

### StockAdjustmentSerializer 字段匹配检查
- ✅ `adjustment_no` - 匹配
- ✅ `warehouse_name` - 匹配
- ✅ `adjustment_date` - 匹配
- ✅ `reason` - 匹配
- ✅ `status` - 匹配
- ✅ `status_display` - 匹配
- ✅ `cost_impact` - 匹配
- ✅ `created_by_name` - 匹配

### BatchSerializer 字段匹配检查
- ✅ `batch_no` - 匹配
- ✅ `item_sku` - 匹配
- ✅ `item_name` - 匹配
- ✅ `warehouse_name` - 匹配
- ✅ `qty_on_hand` - 匹配
- ✅ `unit_cost` - 匹配
- ✅ `quality_status` - 匹配
- ✅ `quality_status_display` - 匹配
- ✅ `is_expired` - 匹配
- ✅ `days_to_expiry` - 匹配

### MaterialRequisitionSerializer 字段匹配检查
- ✅ `requisition_no` - 匹配
- ✅ `requisition_type_display` - 匹配
- ✅ `warehouse_name` - 匹配
- ✅ `requestor_name` - 匹配
- ✅ `request_date` - 匹配
- ✅ `status_display` - 匹配
- ✅ `project_name` - 匹配
- ✅ `line_count` - 匹配（通过 `get_line_count` 方法）

### MaterialReturnSerializer 字段匹配检查
- ✅ `return_no` - 匹配
- ✅ `return_type_display` - 匹配
- ✅ `return_reason_display` - 匹配
- ✅ `warehouse_name` - 匹配
- ✅ `requestor_name` - 匹配
- ✅ `request_date` - 匹配
- ✅ `status_display` - 匹配
- ✅ `project_name` - 匹配
- ✅ `line_count` - 匹配（通过 `get_line_count` 方法）

## 修复建议

### 已完成的修复
1. ✅ StockList.vue - 修复 `unit_cost` → `weighted_avg_cost`
2. ✅ StockTransfer.vue - 修复仓库名称字段

### 后续建议
1. **统一命名规范**：建议在后端序列化器中统一字段命名规范，避免类似问题
2. **添加字段验证**：建议添加前端字段验证，在开发阶段就能发现字段不匹配问题
3. **定期检查**：建议定期进行字段匹配检查，确保前后端字段一致性
4. **文档维护**：建议维护前后端字段映射文档，方便开发人员查阅

## 检查完成时间
2026-01-30

