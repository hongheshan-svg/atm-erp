#!/bin/bash

# 批量为Vue页面添加删除功能脚本
# Usage: ./update-batch-delete.sh <vue-file-path> <api-endpoint> <confirm-message> <data-method>

set -e

VUE_FILE="$1"
API_ENDPOINT="$2"
CONFIRM_MESSAGE="${3:-此操作将永久删除选中的记录，是否继续？}"
DATA_METHOD="${4:-fetchData}"

if [ -z "$VUE_FILE" ] || [ -z "$API_ENDPOINT" ]; then
  echo "Usage: $0 <vue-file-path> <api-endpoint> [confirm-message] [data-method]"
  echo "Example: $0 frontend/src/views/sales/CustomerList.vue /sales/customers/ '确认删除客户' loadCustomers"
  exit 1
fi

if [ ! -f "$VUE_FILE" ]; then
  echo "Error: File $VUE_FILE not found"
  exit 1
fi

echo "正在更新 $VUE_FILE..."
echo "API Endpoint: $API_ENDPOINT"
echo "刷新方法: $DATA_METHOD"

# 创建备份
cp "$VUE_FILE" "$VUE_FILE.backup"
echo "已创建备份: $VUE_FILE.backup"

# 提示：这个脚本仅提供参考
# 实际使用时需要根据具体页面结构手动调整

cat <<'EOF'

=== 更新步骤 ===

1. 导入composables（在<script setup>开头）:
   import { useBatchDelete } from '@/composables/useBatchDelete'
   import { usePermission } from '@/composables/usePermission'

2. 添加权限检查:
   const { canDelete } = usePermission()

3. 添加批量删除功能:
   const { selectedRows, loading, handleSelectionChange, batchDelete, deleteRow } = useBatchDelete(
     '$API_ENDPOINT',
     {
       confirmMessage: '$CONFIRM_MESSAGE',
       onSuccess: $DATA_METHOD
     }
   )

4. 在搜索表单后添加批量操作工具栏:
   <div class="table-toolbar" v-if="canDelete && selectedRows.length > 0">
     <span>已选择 {{ selectedRows.length }} 项</span>
     <el-button type="danger" size="small" @click="batchDelete" :loading="loading">
       批量删除
     </el-button>
   </div>

5. 在<el-table>添加选择列:
   <el-table-column v-if="canDelete" type="selection" width="55" fixed />

6. 更新操作列:
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

7. 删除旧的handleDelete函数

8. 添加样式（如果没有）:
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

=== 已完成的示例页面 ===
- frontend/src/views/masterdata/ItemList.vue
- frontend/src/views/system/UserList.vue

请参考这些页面的实现！

EOF

echo ""
echo "提示: 由于每个页面结构不同，建议手动更新"
echo "参考文档: docs/BATCH_DELETE_GUIDE.md"
echo "备份文件: $VUE_FILE.backup"
