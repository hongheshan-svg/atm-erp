<template>
  <div class="role-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>角色管理</span>
          <el-button type="primary" @click="handleAdd">新增角色</el-button>
        </div>
      </template>

      <el-table :data="roles" v-loading="loading" stripe border>
        <el-table-column prop="id" label="编号" width="80" />
        <el-table-column prop="name" label="角色名称" />
        <el-table-column prop="description" label="描述" />
        <el-table-column prop="data_scope" label="数据范围">
          <template #default="{ row }">
            {{ getDataScopeLabel(row.data_scope) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="600px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="120px">
        <el-form-item label="角色名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入角色名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" placeholder="请输入描述" />
        </el-form-item>
        <el-form-item label="数据范围">
          <el-select v-model="form.data_scope" placeholder="选择数据范围">
            <el-option label="全部数据" value="ALL" />
            <el-option label="部门数据" value="DEPARTMENT" />
            <el-option label="仅本人" value="SELF" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/utils/request'

const loading = ref(false)
const roles = ref([])
const dialogVisible = ref(false)
const dialogTitle = ref('新增角色')
const isEdit = ref(false)
const formRef = ref(null)

const form = reactive({
  id: null,
  name: '',
  description: '',
  data_scope: 'DEPARTMENT'
})

const rules = {
  name: [{ required: true, message: '请输入角色名称', trigger: 'blur' }]
}

const getDataScopeLabel = (scope) => {
  const labels = {
    'all': '全部数据',
    'ALL': '全部数据',
    'department': '部门数据',
    'DEPARTMENT': '部门数据',
    'self': '仅本人',
    'SELF': '仅本人'
  }
  return labels[scope] || scope
}

const loadRoles = async () => {
  loading.value = true
  try {
    const response = await request.get('/auth/roles/')
    roles.value = response.results || response || []
  } catch (error) {
    ElMessage.error('加载角色失败')
  } finally {
    loading.value = false
  }
}

const handleAdd = () => {
  dialogTitle.value = '新增角色'
  isEdit.value = false
  Object.assign(form, { id: null, name: '', description: '', data_scope: 'DEPARTMENT' })
  dialogVisible.value = true
}

const handleEdit = (row) => {
  dialogTitle.value = '编辑角色'
  isEdit.value = true
  Object.assign(form, row)
  dialogVisible.value = true
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该角色吗？', '警告', {
      type: 'warning'
    })
    await request.delete(`/auth/roles/${row.id}/`)
    ElMessage.success('删除成功')
    loadRoles()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除角色失败')
    }
  }
}

const handleSubmit = async () => {
  try {
    await formRef.value.validate()
    if (isEdit.value) {
      await request.put(`/auth/roles/${form.id}/`, form)
      ElMessage.success('更新角色成功')
    } else {
      await request.post('/auth/roles/', form)
      ElMessage.success('创建角色成功')
    }
    dialogVisible.value = false
    loadRoles()
  } catch (error) {
    ElMessage.error('保存角色失败')
  }
}

onMounted(() => {
  loadRoles()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
