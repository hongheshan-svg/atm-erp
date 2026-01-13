<template>
  <div class="item-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>物料主数据</span>
          <div class="header-actions">
            <el-button type="primary" @click="handleAdd">新增物料</el-button>
            <el-dropdown style="margin-left: 10px;">
              <el-button type="success">
                导入/导出 <el-icon class="el-icon--right"><ArrowDown /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item @click="handleExport">
                    <el-icon><Download /></el-icon> 导出Excel
                  </el-dropdown-item>
                  <el-dropdown-item @click="handleImport">
                    <el-icon><Upload /></el-icon> 导入Excel
                  </el-dropdown-item>
                  <el-dropdown-item @click="handleDownloadTemplate">
                    <el-icon><Document /></el-icon> 下载导入模板
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </div>
      </template>

      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="物料编码">
          <el-input v-model="searchForm.sku" placeholder="搜索物料编码" clearable />
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model="searchForm.name" placeholder="搜索物料名称" clearable />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadItems">搜索</el-button>
          <el-button @click="resetSearch">重置</el-button>
        </el-form-item>
      </el-form>

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
      
      <el-table 
        :data="items" 
        v-loading="loading" 
        stripe 
        border 
        @selection-change="handleSelectionChange"
      >
        <!-- 仅管理员显示选择列 -->
        <el-table-column v-if="canDelete" type="selection" width="45" fixed />
        <el-table-column type="index" label="序号" width="60" fixed />
        <el-table-column prop="sku" label="物料编码" width="100" fixed />
        <el-table-column prop="name" label="物料名称" width="150" show-overflow-tooltip />
        <el-table-column prop="specification" label="规格型号" width="120" show-overflow-tooltip />
        <el-table-column label="版本/品牌" width="120">
          <template #default="{ row }">
            {{ row.brand || row.model ? `${row.brand || ''}${row.brand && row.model ? '/' : ''}${row.model || ''}` : '' }}
          </template>
        </el-table-column>
        <el-table-column prop="unit_display" label="单位" width="60" />
        <el-table-column prop="item_type_display" label="物料类型" width="80" />
        <el-table-column label="采购单价" width="90" align="right">
          <template #default="{ row }">
            ¥{{ parseFloat(row.purchase_price || 0).toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column label="销售单价" width="90" align="right">
          <template #default="{ row }">
            ¥{{ parseFloat(row.sale_price || 0).toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column label="标准成本" width="90" align="right">
          <template #default="{ row }">
            ¥{{ parseFloat(row.standard_cost || 0).toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column label="税率(%)" width="70" align="center">
          <template #default="{ row }">
            {{ row.tax_rate }}
          </template>
        </el-table-column>
        <el-table-column prop="manufacturer" label="生产厂家" width="120" show-overflow-tooltip />
        <el-table-column prop="origin_country" label="产地" width="80" show-overflow-tooltip />
        <el-table-column prop="safety_stock" label="安全库存" width="80" align="right" />
        <el-table-column label="采购周期(天)" width="90" align="center">
          <template #default="{ row }">
            {{ row.lead_time || '' }}
          </template>
        </el-table-column>
        <el-table-column prop="is_active" label="状态" width="70" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
              {{ row.is_active ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" :width="canDelete ? 180 : 80" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleEdit(row)">编辑</el-button>
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
      </el-table>

      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="loadItems"
        @current-change="loadItems"
        style="margin-top: 20px; justify-content: center"
      />
    </el-card>

    <!-- 其他对话框内容保持不变... -->
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowDown, Download, Upload, Document, Setting } from '@element-plus/icons-vue'
import request from '@/utils/request'
import { useBatchDelete } from '@/composables/useBatchDelete'
import { usePermission } from '@/composables/usePermission'

// 权限检查
const { canDelete, isAdmin } = usePermission()

// 批量删除功能 - 使用箭头函数包装避免 TDZ 错误
const { selectedRows, loading, handleSelectionChange, batchDelete, deleteRow } = useBatchDelete(
  '/masterdata/items/',
  {
    confirmTitle: '确认删除物料',
    confirmMessage: '此操作将永久删除选中的物料记录，是否继续？',
    successMessage: '删除物料成功',
    errorMessage: '删除物料失败',
    onSuccess: () => loadItems()
  }
)

// 其他现有代码...
const items = ref([])
const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const searchForm = reactive({
  sku: '',
  name: ''
})

const loadItems = async () => {
  // 现有的loadItems实现...
}

const handleEdit = (row) => {
  // 现有的编辑逻辑...
}

const handleAdd = () => {
  // 现有的新增逻辑...
}

const resetSearch = () => {
  searchForm.sku = ''
  searchForm.name = ''
  loadItems()
}

onMounted(() => {
  loadItems()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.search-form {
  margin-bottom: 20px;
}

.table-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px;
  background-color: #f5f7fa;
  border-radius: 4px;
  margin-bottom: 10px;
}
</style>
