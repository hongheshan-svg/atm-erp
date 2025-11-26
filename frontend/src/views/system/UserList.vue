<template>
  <div class="user-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>用户管理</span>
          <el-button type="primary" @click="handleAdd">新增用户</el-button>
        </div>
      </template>

      <!-- 搜索 Form -->
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="用户名">
          <el-input v-model="searchForm.username" placeholder="搜索用户名" clearable />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="searchForm.email" placeholder="搜索邮箱" clearable />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.is_active" placeholder="选择状态" clearable>
            <el-option label="启用" :value="true" />
            <el-option label="禁用" :value="false" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadUsers">搜索</el-button>
          <el-button @click="resetSearch">重置</el-button>
        </el-form-item>
      </el-form>

      <!-- Data Table -->
      <el-table :data="users" v-loading="loading" stripe border>
        <el-table-column prop="id" label="编号" width="80" />
        <el-table-column prop="username" label="用户名" />
        <el-table-column prop="email" label="邮箱" />
        <el-table-column prop="employee_id" label="员工编号" />
        <el-table-column prop="department_info.name" label="部门" />
        <el-table-column prop="role_info.name" label="角色" />
        <el-table-column prop="is_active" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'">
              {{ row.is_active ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- Pagination -->
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="loadUsers"
        @current-change="loadUsers"
        style="margin-top: 20px; justify-content: center"
      />
    </el-card>

    <!-- 编辑 Dialog -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="600px"
      @close="resetForm"
    >
      <el-form :model="form" :rules="rules" ref="formRef" label-width="120px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" :disabled="isEdit" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="form.email" placeholder="请输入邮箱" />
        </el-form-item>
        <el-form-item label="密码" prop="password" v-if="!isEdit">
          <el-input v-model="form.password" type="password" placeholder="请输入密码" />
        </el-form-item>
        <el-form-item label="员工编号">
          <el-input v-model="form.employee_id" placeholder="请输入员工编号" />
        </el-form-item>
        <el-form-item label="名">
          <el-input v-model="form.first_name" placeholder="请输入名" />
        </el-form-item>
        <el-form-item label="姓">
          <el-input v-model="form.last_name" placeholder="请输入姓" />
        </el-form-item>
        <el-form-item label="电话">
          <el-input v-model="form.phone" placeholder="请输入电话" />
        </el-form-item>
        <el-form-item label="部门">
          <el-select v-model="form.department" placeholder="选择部门" clearable>
            <el-option
              v-for="dept in departments"
              :key="dept.id"
              :label="dept.name"
              :value="dept.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="form.role" placeholder="选择角色" clearable>
            <el-option
              v-for="role in roles"
              :key="role.id"
              :label="role.name"
              :value="role.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="form.is_active" />
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
const users = ref([])
const departments = ref([])
const roles = ref([])
const dialogVisible = ref(false)
const dialogTitle = ref('新增用户')
const isEdit = ref(false)
const formRef = ref(null)

const searchForm = reactive({
  username: '',
  email: '',
  is_active: null
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const form = reactive({
  id: null,
  username: '',
  email: '',
  password: '',
  employee_id: '',
  first_name: '',
  last_name: '',
  phone: '',
  department: null,
  role: null,
  is_active: true
})

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入有效的邮箱', trigger: 'blur' }
  ],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

const loadUsers = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
      ...searchForm
    }
    const response = await request.get('/auth/users/', { params })
    // 兼容不同的返回格式
    if (response && response.results) {
      users.value = response.results
      pagination.total = response.count || 0
    } else if (Array.isArray(response)) {
      users.value = response
      pagination.total = response.length
    } else {
      users.value = []
      pagination.total = 0
    }
  } catch (error) {
    ElMessage.error('加载用户失败')
    users.value = []
  } finally {
    loading.value = false
  }
}

const loadDepartments = async () => {
  try {
    const response = await request.get('/auth/departments/')
    departments.value = response.results || response || []
  } catch (error) {
    console.error('加载部门失败:', error)
    departments.value = []
  }
}

const loadRoles = async () => {
  try {
    const response = await request.get('/auth/roles/')
    roles.value = response.results || response || []
  } catch (error) {
    console.error('加载角色失败:', error)
    roles.value = []
  }
}

const handleAdd = () => {
  dialogTitle.value = '新增用户'
  isEdit.value = false
  dialogVisible.value = true
}

const handleEdit = (row) => {
  dialogTitle.value = '编辑用户'
  isEdit.value = true
  Object.assign(form, row)
  dialogVisible.value = true
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该用户吗？', '警告', {
      type: 'warning'
    })
    await request.delete(`/auth/users/${row.id}/`)
    ElMessage.success('删除成功')
    loadUsers()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const handleSubmit = async () => {
  try {
    await formRef.value.validate()
    if (isEdit.value) {
      await request.put(`/auth/users/${form.id}/`, form)
      ElMessage.success('更新成功')
    } else {
      await request.post('/auth/users/', form)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadUsers()
  } catch (error) {
    ElMessage.error('保存用户失败')
  }
}

const resetForm = () => {
  formRef.value?.resetFields()
  Object.assign(form, {
    id: null,
    username: '',
    email: '',
    password: '',
    employee_id: '',
    first_name: '',
    last_name: '',
    phone: '',
    department: null,
    role: null,
    is_active: true
  })
}

const resetSearch = () => {
  Object.assign(searchForm, {
    username: '',
    email: '',
    is_active: null
  })
  pagination.page = 1
  loadUsers()
}

onMounted(() => {
  loadUsers()
  loadDepartments()
  loadRoles()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.search-form {
  margin-bottom: 20px;
}
</style>
