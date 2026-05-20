<template>
  <div class="user-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>用户管理</span>
          <el-button type="primary" v-permission="'accounts:user:create'" @click="handleAdd">新增用户</el-button>
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

      <!-- 批量操作工具栏 - 仅管理员可见 -->
      <div class="table-toolbar" v-permission="'accounts:user:delete'" v-if="canDelete && selectedRows.length > 0">
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

      <!-- Data Table -->
      <el-table :data="users" v-loading="loading" stripe border @selection-change="handleSelectionChange">
        <!-- 仅管理员显示选择列 -->
        <el-table-column v-permission="'accounts:user:delete'" v-if="canDelete" type="selection" width="55" fixed />
        <el-table-column prop="id" label="编号" width="80" />
        <el-table-column prop="username" label="用户名" />
        <el-table-column prop="email" label="邮箱" />
        <el-table-column prop="phone" label="手机号码" width="130" />
        <el-table-column prop="department_name" label="部门" />
        <el-table-column prop="role_name" label="角色" />
        <el-table-column prop="is_active" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'">
              {{ row.is_active ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" :width="canDelete ? 180 : 80" fixed="right">
          <template #default="{ row }">
            <el-button size="small" v-permission="'accounts:user:edit'" @click="handleEdit(row)">编辑</el-button>
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
          <el-input v-model="form.password" type="password" placeholder="请输入密码" show-password />
        </el-form-item>
        <el-form-item label="确认密码" prop="password_confirm" v-if="!isEdit">
          <el-input v-model="form.password_confirm" type="password" placeholder="请再次输入密码" show-password />
        </el-form-item>
        <el-form-item label="姓名">
          <el-input v-model="form.full_name" placeholder="请输入姓名" />
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
import { getUsers, createUser, updateUser, getRoles, getDepartments } from '@/api/auth'
import { useBatchDelete } from '@/composables/useBatchDelete'
import { usePermission } from '@/composables/usePermission'

// 权限检查
const { canDelete } = usePermission()

// 批量删除功能
const { selectedRows, loading: deleteLoading, handleSelectionChange, batchDelete, deleteRow } = useBatchDelete(
  '/auth/users/',
  {
    confirmTitle: '确认删除用户',
    confirmMessage: '删除用户将同时删除其关联的所有数据，此操作不可恢复！',
    successMessage: '删除用户成功',
    errorMessage: '删除用户失败',
    onSuccess: () => loadUsers()
  }
)

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
  password_confirm: '',
  full_name: '',
  phone: '',
  department: null,
  role: null,
  is_active: true
})

const validatePasswordConfirm = (rule, value, callback) => {
  if (!isEdit.value && value !== form.password) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入有效的邮箱', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码长度至少6位', trigger: 'blur' }
  ],
  password_confirm: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    { validator: validatePasswordConfirm, trigger: 'blur' }
  ]
}

const loadUsers = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
      ...searchForm
    }
    const response = await getUsers(params)
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
    const response = await getDepartments()
    departments.value = response.results || response || []
  } catch (error) {
    console.error('加载部门失败:', error)
    departments.value = []
  }
}

const loadRoles = async () => {
  try {
    const response = await getRoles()
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
  // 合并姓名
  const fullName = [row.last_name, row.first_name].filter(Boolean).join('')
  Object.assign(form, {
    id: row.id,
    username: row.username,
    email: row.email,
    full_name: fullName,
    phone: row.phone || '',
    department: row.department,
    role: row.role,
    is_active: row.is_active
  })
  dialogVisible.value = true
}

// 删除功能已迁移到 useBatchDelete composable

const handleSubmit = async () => {
  try {
    await formRef.value.validate()
    // 拆分姓名：第一个字为姓，其余为名
    const fullName = form.full_name || ''
    const lastName = fullName.length > 0 ? fullName.charAt(0) : ''
    const firstName = fullName.length > 1 ? fullName.slice(1) : ''
    
    if (isEdit.value) {
      const updateData = {
        email: form.email,
        first_name: firstName,
        last_name: lastName,
        phone: form.phone,
        department: form.department,
        role: form.role,
        is_active: form.is_active
      }
      await updateUser(form.id, updateData)
      ElMessage.success('更新成功')
    } else {
      const createData = {
        username: form.username,
        email: form.email,
        password: form.password,
        password_confirm: form.password_confirm,
        first_name: firstName,
        last_name: lastName,
        phone: form.phone,
        department: form.department,
        role: form.role,
        is_active: form.is_active
      }
      await createUser(createData)
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
    password_confirm: '',
    full_name: '',
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
