<template>
  <div class="department-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>部门管理</span>
          <el-button type="primary" @click="handleAdd">新增部门</el-button>
        </div>
      </template>

      <el-table :data="departments" v-loading="loading" stripe border row-key="id">
        <el-table-column prop="id" label="编号" width="80" />
        <el-table-column prop="name" label="部门名称" />
        <el-table-column prop="code" label="编码" />
        <el-table-column prop="manager_name" label="负责人" />
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
        <el-form-item label="部门名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入部门名称" />
        </el-form-item>
        <el-form-item label="部门编码" prop="code">
          <el-input v-model="form.code" placeholder="请输入部门编码" />
        </el-form-item>
        <el-form-item label="上级部门">
          <el-select v-model="form.parent" placeholder="选择上级部门" clearable>
            <el-option
              v-for="dept in departments"
              :key="dept.id"
              :label="dept.name"
              :value="dept.id"
            />
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
const departments = ref([])
const dialogVisible = ref(false)
const dialogTitle = ref('新增部门')
const isEdit = ref(false)
const formRef = ref(null)

const form = reactive({
  id: null,
  name: '',
  code: '',
  parent: null
})

const rules = {
  name: [{ required: true, message: '请输入部门名称', trigger: 'blur' }],
  code: [{ required: true, message: '请输入部门编码', trigger: 'blur' }]
}

const loadDepartments = async () => {
  loading.value = true
  try {
    const { data } = await request.get('/auth/departments/')
    departments.value = data.results || data
  } catch (error) {
    ElMessage.error('加载部门失败')
  } finally {
    loading.value = false
  }
}

const handleAdd = () => {
  dialogTitle.value = '新增部门'
  isEdit.value = false
  Object.assign(form, { id: null, name: '', code: '', parent: null })
  dialogVisible.value = true
}

const handleEdit = (row) => {
  dialogTitle.value = '编辑部门'
  isEdit.value = true
  Object.assign(form, row)
  dialogVisible.value = true
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该部门吗？', '警告', {
      type: 'warning'
    })
    await request.delete(`/auth/departments/${row.id}/`)
    ElMessage.success('删除部门成功')
    loadDepartments()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除部门失败')
    }
  }
}

const handleSubmit = async () => {
  try {
    await formRef.value.validate()
    if (isEdit.value) {
      await request.put(`/auth/departments/${form.id}/`, form)
      ElMessage.success('更新部门成功')
    } else {
      await request.post('/auth/departments/', form)
      ElMessage.success('创建部门成功')
    }
    dialogVisible.value = false
    loadDepartments()
  } catch (error) {
    ElMessage.error('保存部门失败')
  }
}

onMounted(() => {
  loadDepartments()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
