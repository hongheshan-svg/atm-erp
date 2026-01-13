# 批量删除功能和权限控制更新指南

## 概述

本指南说明如何为所有数据管理页面添加：
1. ✅ **批量删除功能** - 多选+批量删除按钮
2. ✅ **单独删除功能** - 每行操作列添加删除按钮
3. ✅ **权限控制** - 仅管理员可见删除按钮

---

## 一、准备工作

### 1.1 已创建的Composables

**`/frontend/src/composables/useBatchDelete.js`**
- 提供批量删除和单独删除功能
- 自动处理确认对话框
- 统一的成功/失败消息提示

**`/frontend/src/composables/usePermission.js`**
- 提供权限检查功能
- `isAdmin`: 是否是管理员
- `canDelete`: 是否有删除权限
- `hasPermission(permission)`: 检查特定权限

---

## 二、标准更新步骤

### 2.1 在Vue组件的`<script setup>`中导入

```javascript
import { useBatchDelete } from '@/composables/useBatchDelete'
import { usePermission } from '@/composables/usePermission'

// 权限检查
const { canDelete, isAdmin } = usePermission()

// 批量删除功能（根据实际API endpoint调整）
const { 
  selectedRows,          // 选中的行
  loading,               // 加载状态
  handleSelectionChange, // 选择变化处理
  batchDelete,           // 批量删除方法
  deleteRow              // 单行删除方法
} = useBatchDelete(
  '/api-endpoint/',      // ⚠️ 替换为实际的API endpoint
  {
    confirmTitle: '确认删除',
    confirmMessage: '此操作将永久删除选中的记录，是否继续？',
    successMessage: '删除成功',
    errorMessage: '删除失败',
    onSuccess: fetchData  // ⚠️ 替换为实际的刷新方法
  }
)
```

### 2.2 更新模板 - 添加批量操作工具栏

在`<el-form>`搜索表单和`<el-table>`之间添加：

```vue
<!-- 批量操作工具栏 - 仅管理员可见 -->
<div class="table-toolbar" v-if="canDelete && selectedRows.length > 0">
  <span>已选择 {{ selectedRows.length }} 项</span>
  <el-button 
    type="danger" 
    size="small" 
    @click="batchDelete"
    :loading="loading"
  >
    批量删除
  </el-button>
</div>
```

### 2.3 更新`<el-table>` - 添加选择列

在`<el-table>`开头添加：

```vue
<el-table 
  :data="tableData" 
  v-loading="loading" 
  @selection-change="handleSelectionChange"
>
  <!-- 仅管理员显示选择列 -->
  <el-table-column v-if="canDelete" type="selection" width="55" fixed />
  
  <!-- 其他列... -->
</el-table>
```

### 2.4 更新操作列 - 添加删除按钮

```vue
<el-table-column label="操作" :width="canDelete ? 180 : 100" fixed="right">
  <template #default="{ row }">
    <el-button size="small" @click="handleEdit(row)">编辑</el-button>
    <el-button size="small" @click="handleView(row)">查看</el-button>
    
    <!-- 仅管理员显示删除按钮 -->
    <el-button 
      v-if="canDelete"
      size="small" 
      type="danger" 
      @click="deleteRow(row)"
      :loading="loading"
    >
      删除
    </el-button>
  </template>
</el-table-column>
```

### 2.5 添加样式（如果没有）

```vue
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

## 三、各模块页面清单

### 3.1 基础数据管理 (Master Data)

| 页面 | 路径 | API Endpoint | 刷新方法 | 状态 |
|------|------|--------------|----------|------|
| 物料列表 | `/views/masterdata/ItemList.vue` | `/masterdata/items/` | `loadItems` | ✅ 已更新 |
| 供应商列表 | `/views/purchase/SupplierList.vue` | `/purchase/suppliers/` | `fetchData` | ⏳ 待更新 |
| 客户列表 | `/views/sales/CustomerList.vue` | `/sales/customers/` | `fetchData` | ⏳ 待更新 |
| 仓库列表 | `/views/inventory/WarehouseList.vue` | `/inventory/warehouses/` | `fetchData` | ⏳ 待更新 |

### 3.2 项目管理 (Projects)

| 页面 | 路径 | API Endpoint | 刷新方法 | 状态 |
|------|------|--------------|----------|------|
| 项目列表 | `/views/projects/ProjectList.vue` | `/projects/projects/` | `fetchData` | ⏳ 待更新 |
| 任务列表 | `/views/projects/TaskList.vue` | `/projects/tasks/` | `fetchData` | ⏳ 待更新 |
| BOM列表 | `/views/projects/BOMList.vue` | `/projects/bom/` | `fetchData` | ⏳ 待更新 |
| 工时记录 | `/views/projects/TimeLogList.vue` | `/projects/time-logs/` | `fetchData` | ⏳ 待更新 |

### 3.3 采购管理 (Purchase)

| 页面 | 路径 | API Endpoint | 刷新方法 | 状态 |
|------|------|--------------|----------|------|
| 采购申请 | `/views/purchase/RequestList.vue` | `/purchase/requests/` | `fetchData` | ⏳ 待更新 |
| 采购订单 | `/views/purchase/OrderList.vue` | `/purchase/orders/` | `fetchData` | ⏳ 待更新 |
| 收货单 | `/views/purchase/GoodsReceiptList.vue` | `/purchase/receipts/` | `fetchData` | ⏳ 待更新 |

### 3.4 销售管理 (Sales)

| 页面 | 路径 | API Endpoint | 刷新方法 | 状态 |
|------|------|--------------|----------|------|
| 销售线索 | `/views/sales/LeadList.vue` | `/sales/leads/` | `fetchData` | ⏳ 待更新 |
| 销售商机 | `/views/sales/OpportunityList.vue` | `/sales/opportunities/` | `fetchData` | ⏳ 待更新 |
| 报价单 | `/views/sales/QuotationList.vue` | `/sales/quotations/` | `fetchData` | ⏳ 待更新 |
| 销售订单 | `/views/sales/OrderList.vue` | `/sales/orders/` | `fetchData` | ⏳ 待更新 |

### 3.5 库存管理 (Inventory)

| 页面 | 路径 | API Endpoint | 刷新方法 | 状态 |
|------|------|--------------|----------|------|
| 库存查询 | `/views/inventory/StockList.vue` | `/inventory/stocks/` | `fetchData` | ⏳ 待更新 |
| 库存流水 | `/views/inventory/StockMoveList.vue` | `/inventory/moves/` | `fetchData` | ⏳ 待更新 |
| 库存盘点 | `/views/inventory/StockAdjustmentList.vue` | `/inventory/adjustments/` | `fetchData` | ⏳ 待更新 |

### 3.6 财务管理 (Finance)

| 页面 | 路径 | API Endpoint | 刷新方法 | 状态 |
|------|------|--------------|----------|------|
| 费用报销 | `/views/finance/ExpenseList.vue` | `/finance/expenses/` | `fetchData` | ⏳ 待更新 |
| 发票管理 | `/views/finance/InvoiceList.vue` | `/finance/invoices/` | `fetchData` | ⏳ 待更新 |
| 固定资产 | `/views/finance/AssetList.vue` | `/finance/assets/` | `fetchData` | ⏳ 待更新 |

### 3.7 生产管理 (Production/MES)

| 页面 | 路径 | API Endpoint | 刷新方法 | 状态 |
|------|------|--------------|----------|------|
| 生产计划 | `/views/production/PlanList.vue` | `/production/plans/` | `fetchData` | ⏳ 待更新 |
| 工单管理 | `/views/production/WorkOrderList.vue` | `/production/work-orders/` | `fetchData` | ⏳ 待更新 |
| 设备台账 | `/views/production/EquipmentList.vue` | `/production/equipments/` | `fetchData` | ⏳ 待更新 |

### 3.8 系统管理 (System)

| 页面 | 路径 | API Endpoint | 刷新方法 | 状态 |
|------|------|--------------|----------|------|
| 用户管理 | `/views/system/UserList.vue` | `/accounts/users/` | `fetchData` | ⏳ 待更新 |
| 角色管理 | `/views/system/RoleList.vue` | `/accounts/roles/` | `fetchData` | ⏳ 待更新 |
| 部门管理 | `/views/system/DepartmentList.vue` | `/accounts/departments/` | `fetchData` | ⏳ 待更新 |

---

## 四、特殊情况处理

### 4.1 如果已有删除功能

如果页面已有删除功能（如ItemList.vue），需要：
1. 移除原有的`handleDelete`和`handleBatchDelete`方法
2. 移除原有的`selectedItems` ref
3. 使用新的`useBatchDelete`替代

### 4.2 自定义确认消息

```javascript
const { batchDelete, deleteRow } = useBatchDelete(
  '/api-endpoint/',
  {
    confirmTitle: '删除用户',
    confirmMessage: '删除用户将同时删除其关联的所有数据，此操作不可恢复！',
    successMessage: '用户删除成功',
    errorMessage: '用户删除失败，可能存在关联数据',
    onSuccess: () => {
      fetchData()
      // 额外的成功后操作
    },
    onError: (error) => {
      console.error('删除失败:', error)
      // 额外的错误处理
    }
  }
)
```

### 4.3 软删除vs硬删除

默认调用的是DELETE接口（硬删除）。如果需要软删除：
- 确保后端`/api-endpoint/<id>/`的DELETE方法支持软删除
- 或者修改`useBatchDelete.js`使用PATCH方法更新`is_deleted`字段

---

## 五、测试清单

更新每个页面后，请测试：

- [ ] 普通用户登录，删除按钮不可见
- [ ] 管理员登录，删除按钮可见
- [ ] 单行删除功能正常
- [ ] 批量选择功能正常
- [ ] 批量删除功能正常
- [ ] 删除后表格自动刷新
- [ ] 删除失败时有正确的错误提示
- [ ] 取消删除时不执行删除操作

---

## 六、快速参考

### 完整示例代码

```vue
<template>
  <div class="page-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>数据列表</span>
          <el-button type="primary" @click="handleAdd">新增</el-button>
        </div>
      </template>

      <!-- 搜索表单 -->
      <el-form :inline="true" :model="searchForm">
        <!-- 搜索字段... -->
      </el-form>

      <!-- 批量操作工具栏 -->
      <div class="table-toolbar" v-if="canDelete && selectedRows.length > 0">
        <span>已选择 {{ selectedRows.length }} 项</span>
        <el-button type="danger" size="small" @click="batchDelete" :loading="loading">
          批量删除
        </el-button>
      </div>

      <!-- 数据表格 -->
      <el-table 
        :data="tableData" 
        v-loading="loading"
        @selection-change="handleSelectionChange"
      >
        <el-table-column v-if="canDelete" type="selection" width="55" fixed />
        <el-table-column type="index" label="序号" width="60" />
        <!-- 其他数据列... -->
        
        <el-table-column label="操作" :width="canDelete ? 180 : 100" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleEdit(row)">编辑</el-button>
            <el-button 
              v-if="canDelete"
              size="small" 
              type="danger" 
              @click="deleteRow(row)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        @size-change="fetchData"
        @current-change="fetchData"
      />
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import request from '@/utils/request'
import { useBatchDelete } from '@/composables/useBatchDelete'
import { usePermission } from '@/composables/usePermission'

// 权限
const { canDelete } = usePermission()

// 批量删除
const { selectedRows, loading, handleSelectionChange, batchDelete, deleteRow } = useBatchDelete(
  '/api-endpoint/',
  {
    onSuccess: fetchData
  }
)

// 数据
const tableData = ref([])
const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})
const searchForm = reactive({})

// 加载数据
const fetchData = async () => {
  try {
    const res = await request.get('/api-endpoint/', {
      params: {
        page: pagination.page,
        page_size: pagination.pageSize,
        ...searchForm
      }
    })
    tableData.value = res.results || res.data || []
    pagination.total = res.count || 0
  } catch (error) {
    ElMessage.error('加载数据失败')
  }
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

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
</style>
```

---

## 七、常见问题

**Q: 为什么删除按钮不显示？**
A: 检查用户是否是管理员。可以在浏览器控制台输入`console.log(useUserStore().userInfo)`查看用户信息。

**Q: 批量删除时API报错404？**
A: 检查API endpoint是否正确，注意末尾的斜杠`/`。

**Q: 删除后表格没有刷新？**
A: 检查`onSuccess`回调是否正确设置为刷新数据的方法名。

**Q: 能否自定义删除的HTTP方法？**
A: 可以修改`useBatchDelete.js`中的`request.delete()`为其他方法。

---

## 八、贡献者

- 开发团队
- 最后更新: 2026-01-13

---

*此文档随项目更新，请保持文档与代码同步。*
