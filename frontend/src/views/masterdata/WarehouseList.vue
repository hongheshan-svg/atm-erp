<template>
  <div class="warehouse-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>仓库管理</span>
          <el-button type="primary" v-permission="'masterdata:warehouse:create'" @click="handleAdd">新增仓库</el-button>
        </div>
      </template>

      <!-- 批量操作工具栏 -->
      <div class="table-toolbar" v-permission="'masterdata:warehouse:delete'" v-if="canDelete && selectedRows.length > 0">
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

      <el-table :data="warehouses" v-loading="loading" stripe border @selection-change="handleSelectionChange">
        <el-table-column v-permission="'masterdata:warehouse:delete'" v-if="canDelete" type="selection" width="55" fixed />
        <el-table-column prop="code" label="编码" width="120" />
        <el-table-column prop="name" label="仓库名称" />
        <el-table-column prop="address" label="地址" />
        <el-table-column prop="warehouse_type" label="类型" width="120">
          <template #default="{ row }">
            {{ getTypeLabel(row.warehouse_type) }}
          </template>
        </el-table-column>
        <el-table-column prop="is_active" label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '启用' : '停用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" :width="canDelete ? 200 : 100" fixed="right">
          <template #default="{ row }">
            <el-button size="small" v-permission="'masterdata:warehouse:edit'" @click="handleEdit(row)">编辑</el-button>
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

      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :page-sizes="[20, 50, 100]"
        :total="pagination.total"
        layout="total, sizes, prev, pager, next"
        style="margin-top: 16px; justify-content: flex-end;"
        @size-change="loadWarehouses"
        @current-change="loadWarehouses"
      />
    </el-card>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="600px">
      <el-form :model="form" ref="formRef" label-width="120px" :rules="formRules">
        <el-form-item label="编码" prop="code">
          <el-input v-model="form.code" placeholder="请输入仓库编码（唯一）" />
        </el-form-item>
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="地址">
          <el-input v-model="form.address" type="textarea" />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="form.warehouse_type">
            <el-option label="主仓库" value="MAIN" />
            <el-option label="分仓库" value="BRANCH" />
            <el-option label="中转仓" value="TRANSIT" />
            <el-option label="虚拟仓" value="VIRTUAL" />
          </el-select>
        </el-form-item>
        <el-form-item label="联系电话">
          <el-input v-model="form.contact_phone" />
        </el-form-item>
        <el-form-item label="启用状态">
          <el-switch v-model="form.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitLoading">提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getWarehouseList, createWarehouse, updateWarehouse } from '@/api/masterdata'
import { useBatchDelete } from '@/composables/useBatchDelete'
import { usePermission } from '@/composables/usePermission'

const loading = ref(false)
const submitLoading = ref(false)
const warehouses = ref<any[]>([])
const dialogVisible = ref(false)
const dialogTitle = ref('新增仓库')
const isEdit = ref(false)
const formRef = ref<any>(null)

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const formRules = {
  code: [{ required: true, message: '请输入仓库编码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入仓库名称', trigger: 'blur' }]
}

// 权限检查
const { canDelete } = usePermission()

// 批量删除功能 - 使用箭头函数包装避免 TDZ 错误
const { selectedRows, loading: deleteLoading, handleSelectionChange, batchDelete, deleteRow } = useBatchDelete(
  '/masterdata/warehouses/',
  {
    onSuccess: () => loadWarehouses(),
    confirmTitle: '删除仓库',
    confirmMessage: '确定要删除该仓库吗？删除后不可恢复！'
  }
)

const form = reactive({
  id: null,
  code: '',
  name: '',
  address: '',
  warehouse_type: 'MAIN',
  contact_phone: '',
  is_active: true
})

const getTypeLabel = (type) => {
  const labels = { 'MAIN': '主仓库', 'BRANCH': '分仓库', 'TRANSIT': '中转仓', 'VIRTUAL': '虚拟仓' }
  return labels[type] || type
}

async function loadWarehouses() {
  loading.value = true
  try {
    const response = await getWarehouseList({
      page: pagination.page,
      page_size: pagination.pageSize
    })
    warehouses.value = response.results || response || []
    pagination.total = response.count || warehouses.value.length || 0
  } catch (error) {
    ElMessage.error('加载仓库失败')
  } finally {
    loading.value = false
  }
}

const handleAdd = () => {
  dialogTitle.value = '新增仓库'
  isEdit.value = false
  Object.assign(form, {
    id: null, code: '', name: '', address: '', warehouse_type: 'MAIN', contact_phone: '', is_active: true
  })
  formRef.value?.clearValidate?.()
  dialogVisible.value = true
}

const handleEdit = (row) => {
  dialogTitle.value = '编辑仓库'
  isEdit.value = true
  Object.assign(form, row)
  formRef.value?.clearValidate?.()
  dialogVisible.value = true
}

const handleSubmit = async () => {
  if (formRef.value) {
    const valid = await formRef.value.validate().catch(() => false)
    if (!valid) return
  }
  submitLoading.value = true
  try {
    if (isEdit.value) {
      await updateWarehouse(form.id, form)
      ElMessage.success('更新仓库成功')
    } else {
      await createWarehouse(form)
      ElMessage.success('创建仓库成功')
    }
    dialogVisible.value = false
    loadWarehouses()
  } catch (error: any) {
    const data = error?.response?.data
    const detail = data?.code?.[0] || data?.name?.[0] || data?.detail || data?.error
    ElMessage.error(detail || '保存仓库失败')
  } finally {
    submitLoading.value = false
  }
}

onMounted(() => {
  loadWarehouses()
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

.table-toolbar span {
  font-size: 14px;
  color: #606266;
}
</style>
