<template>
  <div class="warehouse-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>仓库管理</span>
          <el-button type="primary" @click="handleAdd">新增仓库</el-button>
        </div>
      </template>

      <el-table :data="warehouses" v-loading="loading" stripe border>
        <el-table-column prop="code" label="编码" width="120" />
        <el-table-column prop="name" label="仓库名称" />
        <el-table-column prop="location" label="位置" />
        <el-table-column prop="warehouse_type" label="类型" width="120" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="600px">
      <el-form :model="form" ref="formRef" label-width="120px">
        <el-form-item label="编码">
          <el-input v-model="form.code" />
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="位置">
          <el-input v-model="form.location" />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="form.warehouse_type">
            <el-option label="主仓" value="main" />
            <el-option label="中转仓" value="transit" />
            <el-option label="虚拟仓" value="virtual" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/utils/request'

const loading = ref(false)
const warehouses = ref([])
const dialogVisible = ref(false)
const dialogTitle = ref('新增仓库')
const isEdit = ref(false)
const formRef = ref(null)

const form = reactive({
  id: null,
  code: '',
  name: '',
  location: '',
  warehouse_type: 'main'
})

const loadWarehouses = async () => {
  loading.value = true
  try {
    const { data } = await request.get('/masterdata/warehouses/')
    warehouses.value = data.results || data
  } catch (error) {
    ElMessage.error('加载仓库失败')
  } finally {
    loading.value = false
  }
}

const handleAdd = () => {
  dialogTitle.value = '新增仓库'
  isEdit.value = false
  Object.assign(form, { id: null, code: '', name: '', location: '', warehouse_type: 'main' })
  dialogVisible.value = true
}

const handleEdit = (row) => {
  dialogTitle.value = '编辑仓库'
  isEdit.value = true
  Object.assign(form, row)
  dialogVisible.value = true
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该仓库吗？', '警告', { type: 'warning' })
    await request.delete(`/api/masterdata/warehouses/${row.id}/`)
    ElMessage.success('删除仓库成功')
    loadWarehouses()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('删除仓库失败')
  }
}

const handleSubmit = async () => {
  try {
    if (isEdit.value) {
      await request.put(`/api/masterdata/warehouses/${form.id}/`, form)
      ElMessage.success('更新仓库成功')
    } else {
      await request.post('/masterdata/warehouses/', form)
      ElMessage.success('创建仓库成功')
    }
    dialogVisible.value = false
    loadWarehouses()
  } catch (error) {
    ElMessage.error('保存仓库失败')
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
</style>

