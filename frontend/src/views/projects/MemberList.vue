<template>
  <div class="member-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>项目成员管理</span>
          <div class="header-actions">
            <el-select v-model="selectedProject" placeholder="选择项目" clearable filterable style="width: 250px; margin-right: 10px;">
              <el-option
                v-for="project in projects"
                :key="project.id"
                :label="project.name"
                :value="project.id"
              />
            </el-select>
            <el-button type="primary" v-permission="'projects:project:create'" @click="handleAdd" :disabled="!selectedProject">
              <el-icon><Plus /></el-icon>
              添加成员
            </el-button>
          </div>
        </div>
      </template>
      
      <!-- 成员统计 -->
      <el-row :gutter="20" class="stats-row" v-if="selectedProject">
        <el-col :span="6">
          <el-statistic title="成员总数" :value="members.length" suffix="人" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="项目经理" :value="managerCount" suffix="人" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="开发人员" :value="developerCount" suffix="人" />
        </el-col>
        <el-col :span="6" v-if="canViewSalary">
          <el-statistic title="总工时成本" :value="totalLaborCost" :precision="2" prefix="¥" />
        </el-col>
        <el-col :span="6" v-else>
          <el-statistic title="总工时" :value="totalHours" :precision="2" suffix="小时" />
        </el-col>
      </el-row>
      
      <!-- 权限提示 -->
      <el-alert
        v-if="!canViewSalary && selectedProject"
        title="隐私保护提示"
        type="info"
        :closable="false"
        style="margin-bottom: 15px;"
      >
        <template #default>
          <span>出于隐私保护，时薪和工时成本信息仅对项目经理、HR和财务部门可见。</span>
        </template>
      </el-alert>
      
      <!-- 成员列表 -->
      <!-- 批量操作 -->
      <div v-if="selectedRows.length > 0" class="batch-toolbar">
        <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>
        <el-button type="danger" size="small" @click="batchDelete">批量删除</el-button>
        <el-button size="small" @click="batchExport">导出选中</el-button>
      </div>
      <el-table :data="members" border stripe v-loading="loading" @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="45" />
        <el-table-column type="index" label="序号" width="60" />
        <el-table-column prop="user_name" label="成员姓名" width="120" />
        <el-table-column prop="user_email" label="邮箱" width="180" />
        <el-table-column prop="user_department" label="部门" width="120" />
        <el-table-column label="项目角色" width="120">
          <template #default="{ row }">
            <el-tag :type="getRoleType(row.role)" size="small">
              {{ getRoleLabel(row.role) }}
            </el-tag>
          </template>
        </el-table-column>
        <!-- 时薪列：仅对有权限的用户显示 -->
        <el-table-column v-if="canViewSalary" prop="hourly_rate" label="时薪(元/小时)" width="120" align="right">
          <template #default="{ row }">
            <span v-if="row.hourly_rate !== null && row.hourly_rate !== undefined">
              ¥{{ parseFloat(row.hourly_rate).toFixed(2) }}
            </span>
            <span v-else style="color: #ccc;">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="total_hours" label="累计工时" width="100" align="right">
          <template #default="{ row }">
            {{ parseFloat(row.total_hours || 0).toFixed(2) }}小时
          </template>
        </el-table-column>
        <!-- 工时成本列：仅对有权限的用户显示 -->
        <el-table-column v-if="canViewSalary" label="工时成本" width="120" align="right">
          <template #default="{ row }">
            <span v-if="row.labor_cost !== null && row.labor_cost !== undefined">
              ¥{{ parseFloat(row.labor_cost).toFixed(2) }}
            </span>
            <span v-else style="color: #ccc;">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="join_date" label="加入日期" width="110" />
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" v-permission="'projects:project:edit'" @click="handleEdit(row)">编辑</el-button>
            <el-button type="danger" link size="small" v-permission="'projects:project:delete'" @click="handleRemove(row)">移除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
    
    <!-- 添加/编辑成员对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="500px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item label="选择用户" prop="user" v-if="!form.id">
          <el-select v-model="form.user" placeholder="选择用户" filterable style="width: 100%;" @change="handleUserChange">
            <el-option
              v-for="user in availableUsers"
              :key="user.id"
              :label="getUserDisplayName(user)"
              :value="user.id"
            >
              <div style="display: flex; justify-content: space-between; align-items: center;">
                <span>{{ getUserDisplayName(user) }}</span>
                <span style="color: #999; font-size: 12px;">{{ user.department_name || '' }}</span>
              </div>
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="成员" v-else>
          <el-input :value="form.user_name" disabled />
        </el-form-item>
        <el-form-item label="邮箱" v-if="form.user">
          <el-input :value="selectedUserInfo.email" disabled placeholder="自动带出" />
        </el-form-item>
        <el-form-item label="部门" v-if="form.user">
          <el-input :value="selectedUserInfo.department" disabled placeholder="自动带出" />
        </el-form-item>
        <el-form-item label="项目角色" prop="role">
          <el-select v-model="form.role" placeholder="选择角色" filterable style="width: 100%;">
            <el-option
              v-for="role in roles"
              :key="role.id"
              :label="role.name"
              :value="role.name"
            />
          </el-select>
        </el-form-item>
        <!-- 时薪字段：仅对有权限的用户显示 -->
        <el-form-item v-if="canViewSalary" label="时薪" prop="hourly_rate">
          <el-input-number v-model="form.hourly_rate" :min="0" :max="10000" :precision="2" style="width: 100%;">
            <template #suffix>
              <span style="color: #999; font-size: 12px;">元/小时</span>
            </template>
          </el-input-number>
          <div style="color: #999; font-size: 12px; margin-top: 5px;">
            <el-icon><Lock /></el-icon> 薪资信息仅项目经理、HR和财务可见
          </div>
        </el-form-item>
        <el-alert v-else type="warning" :closable="false" style="margin-bottom: 15px;">
          <template #default>
            <span>您没有权限设置或查看时薪信息。如需设置，请联系项目经理或HR。</span>
          </template>
        </el-alert>
        <el-form-item label="加入日期" prop="join_date">
          <el-date-picker v-model="form.join_date" type="date" placeholder="选择日期" style="width: 100%;" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.notes" type="textarea" :rows="2" placeholder="备注信息" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Lock } from '@element-plus/icons-vue'
import { getProjectList, getMemberList, createMember, updateMember, deleteMember } from '@/api/projects/project'
import { getRoles, getUsers } from '@/api/auth'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/projects_project/')


const loading = ref(false)
const selectedProject = ref(null)
const projects = ref<any[]>([])
const members = ref<any[]>([])
const allUsers = ref<any[]>([])
const roles = ref<any[]>([])
const dialogVisible = ref(false)
const formRef = ref(null)

const form = reactive({
  id: null,
  user: null,
  user_name: '',
  role: '',
  hourly_rate: 100,
  join_date: '',
  notes: ''
})

// 表单验证规则（时薪字段根据权限动态设置）
const rules = computed(() => ({
  user: [{ required: true, message: '请选择用户', trigger: 'change' }],
  role: [{ required: true, message: '请选择角色', trigger: 'change' }],
  // 只有有权限的用户才需要填写时薪
  hourly_rate: canViewSalary.value 
    ? [{ required: true, message: '请输入时薪', trigger: 'blur' }]
    : []
}))

const dialogTitle = computed(() => form.id ? '编辑成员' : '添加成员')

const managerCount = computed(() => 
  members.value.filter(m => {
    const role = m.role || ''
    return role.includes('经理') || role.includes('负责人') || role.includes('主管') || role.includes('总监')
  }).length
)

const developerCount = computed(() => 
  members.value.filter(m => {
    const role = m.role || ''
    return role.includes('开发') || role.includes('工程师') || role.includes('技术')
  }).length
)

// 判断当前用户是否有查看薪资的权限
const canViewSalary = computed(() => {
  // 如果有任何一个成员的 can_view_salary 为 true，说明当前用户有权限
  // 后端已经做了权限判断，前端只需要检查返回值
  if (members.value.length > 0) {
    return members.value.some(m => m.can_view_salary === true)
  }
  return false
})

const totalLaborCost = computed(() => {
  // 只有有权限时才计算总成本
  if (!canViewSalary.value) return 0
  return members.value.reduce((sum, m) => {
    // 使用后端返回的 labor_cost
    return sum + (m.labor_cost || 0)
  }, 0)
})

const totalHours = computed(() => {
  // 总工时（不涉及薪资信息，所有人可见）
  return members.value.reduce((sum, m) => sum + parseFloat(m.total_hours || 0), 0)
})

const availableUsers = computed(() => {
  const memberUserIds = members.value.map(m => m.user)
  return allUsers.value.filter(u => !memberUserIds.includes(u.id))
})

// 选中用户的信息（用于自动带出邮箱和部门）
const selectedUserInfo = computed(() => {
  if (!form.user) return { email: '', department: '' }
  const user = allUsers.value.find(u => u.id === form.user)
  if (!user) return { email: '', department: '' }
  return {
    email: user.email || '',
    department: user.department_name || ''
  }
})

// 获取用户显示名称
const getUserDisplayName = (user) => {
  const fullName = `${user.last_name || ''}${user.first_name || ''}`.trim()
  return fullName || user.username || `用户${user.id}`
}

// 用户选择变更时的处理
const handleUserChange = (userId) => {
  const user = allUsers.value.find(u => u.id === userId)
  if (user) {
    form.user_name = getUserDisplayName(user)
  }
}

const getRoleType = (role) => {
  // 根据角色名称返回不同的标签类型
  if (!role) return 'info'
  if (role.includes('经理') || role.includes('总监') || role.includes('主管')) return 'danger'
  if (role.includes('负责人') || role.includes('组长')) return 'warning'
  if (role.includes('测试') || role.includes('质量')) return 'success'
  return ''
}

const getRoleLabel = (role) => {
  return role || '未分配'
}

const fetchProjects = async () => {
  try {
    const res = await getProjectList()
    projects.value = res.results || res.results || res || []
  } catch (error) {
    console.error('获取项目列表失败:', error)
  }
}

const fetchMembers = async () => {
  if (!selectedProject.value) {
    members.value = []
    return
  }
  
  loading.value = true
  try {
    // 使用查询参数过滤项目成员
    const res = await getMemberList({ project: selectedProject.value })
    members.value = res.results || res.results || res || []
  } catch (error) {
    console.error('获取成员列表失败:', error)
    members.value = []
  } finally {
    loading.value = false
  }
}

const fetchUsers = async () => {
  try {
    const res = await getUsers()
    allUsers.value = res.results || res.results || res || []
  } catch (error) {
    console.error('获取用户列表失败:', error)
  }
}

const fetchRoles = async () => {
  try {
    const res = await getRoles()
    roles.value = res.results || res.results || res || []
  } catch (error) {
    console.error('获取角色列表失败:', error)
    // 使用默认角色
    roles.value = [
      { id: 1, name: '项目经理' },
      { id: 2, name: '技术负责人' },
      { id: 3, name: '开发人员' },
      { id: 4, name: '测试人员' },
      { id: 5, name: '设计人员' },
      { id: 6, name: '其他' }
    ]
  }
}

const resetForm = () => {
  form.id = null
  form.user = null
  form.user_name = ''
  form.role = roles.value.length > 0 ? roles.value[0].name : ''
  form.hourly_rate = 100
  form.join_date = new Date().toISOString().split('T')[0]
  form.notes = ''
}

const handleAdd = () => {
  resetForm()
  dialogVisible.value = true
}

const handleEdit = (row) => {
  Object.assign(form, row)
  dialogVisible.value = true
}

const handleRemove = (row) => {
  ElMessageBox.confirm(`确定要将 ${row.user_name} 从项目中移除吗？`, '提示', {
    type: 'warning'
  }).then(async () => {
    try {
      await deleteMember(row.id)
      ElMessage.success('移除成功')
      fetchMembers()
    } catch (error) {
      ElMessage.error('移除失败')
    }
  }).catch(error => { console.error(error) })
}

const handleSubmit = async () => {
  try {
    await formRef.value.validate()
    
    const data = { ...form, project: selectedProject.value }
    
    // 如果当前用户没有查看薪资权限，移除 hourly_rate 字段
    // 后端会保留原有的时薪值或使用默认值
    if (!canViewSalary.value) {
      delete data.hourly_rate
    }
    
    if (form.id) {
      await updateMember(form.id, data)
      ElMessage.success('更新成功')
    } else {
      await createMember(data)
      ElMessage.success('添加成功')
    }
    
    dialogVisible.value = false
    fetchMembers()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('操作失败')
    }
  }
}

watch(selectedProject, () => {
  fetchMembers()
})

onMounted(() => {
  fetchProjects()
  fetchUsers()
  fetchRoles()
})
</script>

<style scoped>
.member-list {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 16px;
  font-weight: bold;
}

.header-actions {
  display: flex;
  align-items: center;
}

.stats-row {
  margin-bottom: 20px;
  padding: 15px;
  background-color: #f5f7fa;
  border-radius: 8px;
}
</style>

