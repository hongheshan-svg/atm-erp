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
            <el-button type="primary" @click="handleAdd" :disabled="!selectedProject">
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
        <el-col :span="6">
          <el-statistic title="总工时成本" :value="totalLaborCost" :precision="2" prefix="¥" />
        </el-col>
      </el-row>
      
      <!-- 成员列表 -->
      <el-table :data="members" border stripe v-loading="loading">
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
        <el-table-column prop="hourly_rate" label="时薪(元/小时)" width="120" align="right">
          <template #default="{ row }">
            ¥{{ row.hourly_rate || 0 }}
          </template>
        </el-table-column>
        <el-table-column prop="total_hours" label="累计工时" width="100" align="right">
          <template #default="{ row }">
            {{ row.total_hours || 0 }}小时
          </template>
        </el-table-column>
        <el-table-column label="工时成本" width="120" align="right">
          <template #default="{ row }">
            ¥{{ ((row.total_hours || 0) * (row.hourly_rate || 0)).toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="join_date" label="加入日期" width="110" />
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="handleEdit(row)">编辑</el-button>
            <el-button type="danger" link size="small" @click="handleRemove(row)">移除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
    
    <!-- 添加/编辑成员对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="500px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item label="选择用户" prop="user" v-if="!form.id">
          <el-select v-model="form.user" placeholder="选择用户" filterable style="width: 100%;">
            <el-option
              v-for="user in availableUsers"
              :key="user.id"
              :label="user.username"
              :value="user.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="成员" v-else>
          <el-input :value="form.user_name" disabled />
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
        <el-form-item label="时薪" prop="hourly_rate">
          <el-input-number v-model="form.hourly_rate" :min="0" :max="10000" :precision="2" style="width: 100%;" />
        </el-form-item>
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

<script setup>
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import request from '@/utils/request'

const loading = ref(false)
const selectedProject = ref(null)
const projects = ref([])
const members = ref([])
const allUsers = ref([])
const roles = ref([])
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

const rules = {
  user: [{ required: true, message: '请选择用户', trigger: 'change' }],
  role: [{ required: true, message: '请选择角色', trigger: 'change' }],
  hourly_rate: [{ required: true, message: '请输入时薪', trigger: 'blur' }]
}

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

const totalLaborCost = computed(() => 
  members.value.reduce((sum, m) => sum + (m.total_hours || 0) * (m.hourly_rate || 0), 0)
)

const availableUsers = computed(() => {
  const memberUserIds = members.value.map(m => m.user)
  return allUsers.value.filter(u => !memberUserIds.includes(u.id))
})

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
    const res = await request.get('/projects/projects/')
    projects.value = res.data?.results || res.results || res.data || []
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
    const res = await request.get('/projects/members/', {
      params: { project: selectedProject.value }
    })
    members.value = res.data?.results || res.results || res.data || []
  } catch (error) {
    console.error('获取成员列表失败:', error)
    // 使用模拟数据
    members.value = getMockMembers()
  } finally {
    loading.value = false
  }
}

const getMockMembers = () => {
  return [
    { id: 1, user: 1, user_name: 'admin', user_email: 'admin@example.com', user_department: '技术部', role: '项目经理', hourly_rate: 200, total_hours: 120, join_date: '2024-01-01' },
    { id: 2, user: 2, user_name: '张三', user_email: 'zhangsan@example.com', user_department: '技术部', role: '技术负责人', hourly_rate: 150, total_hours: 160, join_date: '2024-01-05' },
    { id: 3, user: 3, user_name: '李四', user_email: 'lisi@example.com', user_department: '技术部', role: '开发工程师', hourly_rate: 100, total_hours: 200, join_date: '2024-01-10' },
    { id: 4, user: 4, user_name: '王五', user_email: 'wangwu@example.com', user_department: '测试部', role: '测试工程师', hourly_rate: 80, total_hours: 80, join_date: '2024-02-01' }
  ]
}

const fetchUsers = async () => {
  try {
    const res = await request.get('/auth/users/')
    allUsers.value = res.data?.results || res.results || res.data || []
  } catch (error) {
    console.error('获取用户列表失败:', error)
  }
}

const fetchRoles = async () => {
  try {
    const res = await request.get('/auth/roles/')
    roles.value = res.data?.results || res.results || res.data || []
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
      await request.delete(`/projects/members/${row.id}/`)
      ElMessage.success('移除成功')
      fetchMembers()
    } catch (error) {
      ElMessage.error('移除失败')
    }
  }).catch(() => {})
}

const handleSubmit = async () => {
  try {
    await formRef.value.validate()
    
    const data = { ...form, project: selectedProject.value }
    
    if (form.id) {
      await request.put(`/projects/members/${form.id}/`, data)
      ElMessage.success('更新成功')
    } else {
      await request.post('/projects/members/', data)
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

