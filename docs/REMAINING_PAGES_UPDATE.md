# 剩余页面批量删除功能更新清单

## ✅ 已完成（3/27）

| 页面 | 路径 | 状态 | 完成时间 |
|------|------|------|----------|
| 物料列表 | `frontend/src/views/masterdata/ItemList.vue` | ✅ 完成 | 2026-01-13 |
| 用户列表 | `frontend/src/views/system/UserList.vue` | ✅ 完成 | 2026-01-13 |
| 客户列表 | `frontend/src/views/masterdata/CustomerList.vue` | ✅ 完成 | 2026-01-13 |

## 📋 待更新（24/27）

### 🔴 高优先级 - 第1批（5个）

#### 1. SupplierList.vue - 供应商列表
```vue
文件: frontend/src/views/purchase/SupplierList.vue
API: /purchase/suppliers/
刷新方法: loadSuppliers 或 fetchData
```

**更新步骤**：
1. 导入composables
2. 添加权限检查和批量删除功能
3. 更新模板：批量工具栏、选择列、操作列
4. 删除旧的handleDelete等方法
5. 添加table-toolbar样式（如果没有）

#### 2. ProjectList.vue - 项目列表
```vue
文件: frontend/src/views/projects/ProjectList.vue
API: /projects/projects/
刷新方法: fetchProjects 或 loadProjects
```

#### 3. PurchaseOrderList.vue - 采购订单
```vue
文件: frontend/src/views/purchase/OrderList.vue
API: /purchase/orders/
刷新方法: fetchData 或 loadOrders
```

#### 4. SalesOrderList.vue - 销售订单
```vue
文件: frontend/src/views/sales/OrderList.vue
API: /sales/orders/
刷新方法: fetchData 或 loadOrders
```

#### 5. LeadList.vue - 销售线索
```vue
文件: frontend/src/views/sales/LeadList.vue
API: /sales/leads/
刷新方法: fetchData 或 loadLeads
```

---

### 🟡 中优先级 - 第2批（10个）

#### 销售管理
6. OpportunityList.vue (`/sales/opportunities/`)
7. QuotationList.vue (`/sales/quotations/`)
8. ContractList.vue (`/sales/contracts/`)

#### 采购管理
9. RequestList.vue (`/purchase/requests/`)
10. GoodsReceiptList.vue (`/purchase/receipts/`)

#### 项目管理
11. TaskList.vue (`/projects/tasks/`)
12. BOMList.vue (`/projects/bom/`)
13. DrawingList.vue (`/projects/drawings/`)
14. TimeLogList.vue (`/projects/time-logs/`)

#### 库存管理
15. StockList.vue (`/inventory/stocks/`)

---

### 🟢 低优先级 - 第3批（9个）

#### 库存管理
16. StockMoveList.vue (`/inventory/moves/`)
17. StockAdjustmentList.vue (`/inventory/adjustments/`)
18. WarehouseList.vue (`/inventory/warehouses/`)

#### 财务管理
19. ExpenseList.vue (`/finance/expenses/`)
20. InvoiceList.vue (`/finance/invoices/`)
21. AssetList.vue (`/finance/assets/`)

#### 生产管理
22. PlanList.vue (`/production/plans/`)
23. WorkOrderList.vue (`/production/work-orders/`)
24. EquipmentList.vue (`/production/equipments/`)

---

## 🚀 标准更新模板

### Vue文件通用更新模板

```vue
<!-- ==================== 步骤1: 在<script setup>开头添加 ==================== -->
<script setup>
import { useBatchDelete } from '@/composables/useBatchDelete'
import { usePermission } from '@/composables/usePermission'

// 权限检查
const { canDelete } = usePermission()

// 批量删除功能
const { selectedRows, loading: deleteLoading, handleSelectionChange, batchDelete, deleteRow } = useBatchDelete(
  '/YOUR-API-ENDPOINT/',  // ⚠️ 替换为实际API路径
  {
    confirmTitle: '确认删除XXX',  // ⚠️ 替换为实际对象名称
    confirmMessage: '此操作将永久删除选中的XXX记录，是否继续？',
    successMessage: '删除XXX成功',
    errorMessage: '删除XXX失败',
    onSuccess: () => yourRefreshMethod()  // ⚠️ 替换为实际刷新方法
  }
)

// 删除原有的以下ref/方法（如果存在）:
// const selectedItems = ref([])
// const handleDelete = async (row) => { ... }
// const handleBatchDelete = async () => { ... }
// const handleSelectionChange = (selection) => { ... }
</script>

<!-- ==================== 步骤2: 在搜索表单后添加批量工具栏 ==================== -->
<template>
  <!-- 搜索表单... -->
  
  <!-- 批量操作工具栏 - 仅管理员可见 -->
  <div class="table-toolbar" v-if="canDelete && selectedRows.length > 0">
    <span>已选择 {{ selectedRows.length }} 项</span>
    <el-button 
      type="danger" 
      size="small" 
      @click="batchDelete"
      :loading="deleteLoading"
    >
      批量删除
    </el-button>
  </div>
  
  <!-- ==================== 步骤3: 更新el-table ==================== -->
  <el-table 
    :data="tableData"
    v-loading="loading"
    @selection-change="handleSelectionChange"  <!-- 添加此行 -->
  >
    <!-- 仅管理员显示选择列 -->
    <el-table-column v-if="canDelete" type="selection" width="55" fixed />
    
    <!-- 其他数据列... -->
    
    <!-- ==================== 步骤4: 更新操作列 ==================== -->
    <el-table-column 
      label="操作" 
      :width="canDelete ? 180 : 100"  <!-- 根据权限调整宽度 -->
      fixed="right"
    >
      <template #default="{ row }">
        <el-button size="small" @click="handleEdit(row)">编辑</el-button>
        <el-button size="small" @click="handleView(row)">查看</el-button>
        
        <!-- 仅管理员显示删除按钮 -->
        <el-button 
          v-if="canDelete"
          size="small" 
          type="danger" 
          @click="deleteRow(row)"
          :loading="deleteLoading"
        >
          删除
        </el-button>
      </template>
    </el-table-column>
  </el-table>
</template>

<!-- ==================== 步骤5: 添加样式（如果没有） ==================== -->
<style scoped>
.table-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 15px;
  background-color: #f5f7fa;
  border-radius: 4px;
  margin-bottom: 10px;
  border: 1px solid #e4e7ed;
}

.table-toolbar span {
  font-size: 14px;
  color: #606266;
}
</style>
```

---

## 📝 常见页面配置

### 销售模块

| 页面 | API Endpoint | 刷新方法 | 确认消息 |
|------|-------------|----------|----------|
| LeadList | `/sales/leads/` | `loadLeads` | 确认删除销售线索 |
| OpportunityList | `/sales/opportunities/` | `loadOpportunities` | 确认删除销售商机 |
| QuotationList | `/sales/quotations/` | `fetchData` | 确认删除报价单 |
| OrderList | `/sales/orders/` | `fetchData` | 确认删除销售订单 |
| ContractList | `/sales/contracts/` | `fetchData` | 确认删除合同 |

### 采购模块

| 页面 | API Endpoint | 刷新方法 | 确认消息 |
|------|-------------|----------|----------|
| SupplierList | `/purchase/suppliers/` | `loadSuppliers` | 确认删除供应商 |
| RequestList | `/purchase/requests/` | `fetchData` | 确认删除采购申请 |
| OrderList | `/purchase/orders/` | `fetchData` | 确认删除采购订单 |
| GoodsReceiptList | `/purchase/receipts/` | `fetchData` | 确认删除收货单 |

### 项目模块

| 页面 | API Endpoint | 刷新方法 | 确认消息 |
|------|-------------|----------|----------|
| ProjectList | `/projects/projects/` | `fetchProjects` | 确认删除项目 |
| TaskList | `/projects/tasks/` | `fetchData` | 确认删除任务 |
| BOMList | `/projects/bom/` | `fetchData` | 确认删除BOM |
| DrawingList | `/projects/drawings/` | `fetchData` | 确认删除图纸 |
| TimeLogList | `/projects/time-logs/` | `fetchData` | 确认删除工时记录 |

### 库存模块

| 页面 | API Endpoint | 刷新方法 | 确认消息 |
|------|-------------|----------|----------|
| StockList | `/inventory/stocks/` | `fetchData` | 确认删除库存记录 |
| StockMoveList | `/inventory/moves/` | `fetchData` | 确认删除库存流水 |
| StockAdjustmentList | `/inventory/adjustments/` | `fetchData` | 确认删除盘点记录 |
| WarehouseList | `/inventory/warehouses/` | `fetchData` | 确认删除仓库 |

---

## 🧪 测试检查清单

每个页面更新后执行以下测试：

### 权限测试
- [ ] 以普通用户身份登录
  - [ ] 选择列不显示
  - [ ] 批量工具栏不显示
  - [ ] 删除按钮不显示
  - [ ] 操作列宽度适配（较窄）

- [ ] 以管理员身份登录
  - [ ] 选择列正常显示
  - [ ] 可以选中多行
  - [ ] 批量工具栏显示（有选中项时）
  - [ ] 删除按钮正常显示
  - [ ] 操作列宽度适配（较宽）

### 功能测试
- [ ] 单行删除
  - [ ] 点击删除按钮弹出确认对话框
  - [ ] 确认后成功删除
  - [ ] 删除后表格自动刷新
  - [ ] 显示成功提示消息
  - [ ] 取消时不删除

- [ ] 批量删除
  - [ ] 可以选中多行
  - [ ] 批量工具栏显示选中数量
  - [ ] 点击批量删除弹出确认对话框
  - [ ] 确认后成功删除所有选中项
  - [ ] 删除后表格自动刷新
  - [ ] 删除后选中状态清空
  - [ ] 显示成功提示消息（含数量）
  - [ ] 取消时不删除

- [ ] 边界情况
  - [ ] 删除最后一页的最后一项时正常跳转
  - [ ] 删除失败时显示错误提示
  - [ ] 网络错误时有正确处理

### UI测试
- [ ] 批量工具栏样式正常
- [ ] 表格选择列对齐正常
- [ ] 操作列按钮排列正常
- [ ] 删除按钮loading状态正常
- [ ] 响应式布局无错位

---

## 📊 更新进度跟踪表

| 日期 | 更新页面 | 负责人 | 测试状态 | 备注 |
|------|---------|--------|----------|------|
| 2026-01-13 | ItemList.vue | 开发团队 | ✅ 通过 | |
| 2026-01-13 | UserList.vue | 开发团队 | ✅ 通过 | |
| 2026-01-13 | CustomerList.vue | 开发团队 | ✅ 通过 | |
| | SupplierList.vue | | ⏳ 待测试 | |
| | ProjectList.vue | | ⏳ 待测试 | |
| | ... | | | |

---

## 🔍 故障排查

### 问题1：删除按钮不显示
**原因**: 权限检查未生效
**解决**: 
1. 检查是否导入了`usePermission`
2. 检查`v-if="canDelete"`是否正确添加
3. 在控制台检查用户权限：`console.log(useUserStore().userInfo)`

### 问题2：批量删除失败
**原因**: API路径错误或后端不支持批量删除
**解决**: 
1. 检查API endpoint是否正确（末尾有斜杠`/`）
2. 检查后端是否实现了DELETE方法
3. 查看Network面板的实际请求

### 问题3：删除后表格未刷新
**原因**: `onSuccess`回调设置错误
**解决**: 
1. 检查刷新方法名是否正确
2. 确保方法名没有加引号（应该是函数引用）
3. 使用箭头函数: `onSuccess: () => fetchData()`

### 问题4：选中的行未清空
**原因**: 使用了旧的`selectedItems`变量
**解决**: 
1. 删除旧的`const selectedItems = ref([])`
2. 使用composable提供的`selectedRows`
3. 确保所有地方都改为`selectedRows`

---

## 📞 支持资源

- **详细指南**: `/docs/BATCH_DELETE_GUIDE.md`
- **示例页面**: 
  - `frontend/src/views/masterdata/ItemList.vue`
  - `frontend/src/views/system/UserList.vue`
  - `frontend/src/views/masterdata/CustomerList.vue`
- **Composables**: 
  - `frontend/src/composables/useBatchDelete.js`
  - `frontend/src/composables/usePermission.js`

---

*更新日期: 2026-01-13*
*下次更新: 完成第1批5个页面后*
