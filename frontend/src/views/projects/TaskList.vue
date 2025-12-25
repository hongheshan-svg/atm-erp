<template>
  <div class="task-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>任务管理 (WBS)</span>
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
              新增任务
            </el-button>
          </div>
        </div>
      </template>
      
      <!-- 任务统计 -->
      <el-row :gutter="20" class="stats-row" v-if="selectedProject">
        <el-col :span="6">
          <el-statistic title="总任务数" :value="stats.total" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="进行中" :value="stats.inProgress" :value-style="{ color: '#409eff' }" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="已完成" :value="stats.completed" :value-style="{ color: '#67c23a' }" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="总工时" :value="stats.totalHours" suffix="小时" />
        </el-col>
      </el-row>
      
      <!-- 任务树表格 -->
      <el-table
        :data="taskTree"
        row-key="id"
        border
        stripe
        v-loading="loading"
        :tree-props="{ children: 'children', hasChildren: 'hasChildren' }"
        default-expand-all
      >
        <el-table-column prop="name" label="任务名称" min-width="250">
          <template #default="{ row }">
            <span :style="{ paddingLeft: (row.level || 0) * 20 + 'px' }">
              {{ row.name }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="assignee_name" label="负责人" width="100" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ getStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="进度" width="150">
          <template #default="{ row }">
            <el-progress :percentage="row.progress_percent || row.progress || 0" :status="getProgressStatus(row.progress_percent || row.progress)" />
          </template>
        </el-table-column>
        <el-table-column prop="planned_hours" label="计划工时" width="100" align="right">
          <template #default="{ row }">
            {{ row.planned_hours || 0 }}小时
          </template>
        </el-table-column>
        <el-table-column prop="actual_hours" label="实际工时" width="100" align="right">
          <template #default="{ row }">
            {{ row.actual_hours || 0 }}小时
          </template>
        </el-table-column>
        <el-table-column prop="start_date" label="开始日期" width="110" />
        <el-table-column prop="end_date" label="结束日期" width="110" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="handleEdit(row)">编辑</el-button>
            <el-button type="success" link size="small" @click="handleLogTime(row)">填报工时</el-button>
            <el-button type="warning" link size="small" @click="handleAddChild(row)">添加子任务</el-button>
            <el-button type="danger" link size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
    
    <!-- 任务编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="600px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item label="任务名称" prop="name">
          <el-input v-model="form.name" placeholder="输入任务名称" />
        </el-form-item>
        <el-form-item label="父任务" v-if="form.parent">
          <el-input :value="parentTaskName" disabled />
        </el-form-item>
        <el-form-item label="负责人" prop="assignee">
          <el-select v-model="form.assignee" placeholder="选择负责人" filterable style="width: 100%;">
            <el-option
              v-for="member in assigneeOptions"
              :key="member.id"
              :label="member.label"
              :value="member.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-select v-model="form.status" placeholder="选择状态" style="width: 100%;">
            <el-option label="待办" value="TODO" />
            <el-option label="进行中" value="IN_PROGRESS" />
            <el-option label="已完成" value="COMPLETED" />
            <el-option label="已取消" value="CANCELLED" />
          </el-select>
        </el-form-item>
        <el-form-item label="进度" prop="progress_percent">
          <el-slider v-model="form.progress_percent" :marks="{ 0: '0%', 50: '50%', 100: '100%' }" />
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="计划工时" prop="planned_hours">
              <el-input-number v-model="form.planned_hours" :min="0" :max="1000" style="width: 100%;" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="实际工时" prop="actual_hours">
              <el-input-number v-model="form.actual_hours" :min="0" :max="1000" style="width: 100%;" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="开始日期" prop="start_date">
              <el-date-picker v-model="form.start_date" type="date" placeholder="选择日期" style="width: 100%;" value-format="YYYY-MM-DD" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="结束日期" prop="end_date">
              <el-date-picker v-model="form.end_date" type="date" placeholder="选择日期" style="width: 100%;" value-format="YYYY-MM-DD" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="任务描述" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
    
    <!-- 工时填报对话框 -->
    <el-dialog v-model="timeLogVisible" title="填报工时" width="500px">
      <el-form :model="timeLogForm" label-width="100px">
        <el-form-item label="任务">
          <el-input :value="currentTask?.name" disabled />
        </el-form-item>
        <el-form-item label="日期" required>
          <el-date-picker v-model="timeLogForm.date" type="date" placeholder="选择日期" style="width: 100%;" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="工时(小时)" required>
          <el-input-number v-model="timeLogForm.hours" :min="0.5" :max="24" :step="0.5" style="width: 100%;" />
        </el-form-item>
        <el-form-item label="工作内容">
          <el-input v-model="timeLogForm.description" type="textarea" :rows="3" placeholder="描述工作内容" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="timeLogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmitTimeLog">提交</el-button>
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
const taskTree = ref([])
const projectMembers = ref([])
const dialogVisible = ref(false)
const timeLogVisible = ref(false)
const formRef = ref(null)
const currentTask = ref(null)
const parentTaskName = ref('')

const stats = reactive({
  total: 0,
  inProgress: 0,
  completed: 0,
  totalHours: 0
})

const form = reactive({
  id: null,
  code: '',
  name: '',
  parent: null,
  assignee: null,
  status: 'TODO',
  progress_percent: 0,
  planned_hours: 0,
  actual_hours: 0,
  start_date: '',
  end_date: '',
  description: ''
})

const timeLogForm = reactive({
  date: '',
  hours: 1,
  description: ''
})

const rules = {
  name: [{ required: true, message: '请输入任务名称', trigger: 'blur' }],
  status: [{ required: true, message: '请选择状态', trigger: 'change' }]
}

const dialogTitle = computed(() => form.id ? '编辑任务' : '新增任务')

// 将项目成员/用户列表转换为统一的下拉选项格式
const assigneeOptions = computed(() => {
  return projectMembers.value.map(member => {
    // 项目成员数据 (来自 /projects/members/)
    if (member.user !== undefined) {
      return {
        id: member.user,
        label: member.user_name || `用户${member.user}`
      }
    }
    // 用户数据 (来自 /auth/users/)
    const fullName = `${member.last_name || ''}${member.first_name || ''}`.trim()
    return {
      id: member.id,
      label: fullName || member.username || `用户${member.id}`
    }
  })
})

const getStatusType = (status) => {
  const types = {
    'TODO': 'info',
    'PENDING': 'info',
    'IN_PROGRESS': '',
    'COMPLETED': 'success',
    'CANCELLED': 'danger'
  }
  return types[status] || 'info'
}

const getStatusLabel = (status) => {
  const labels = {
    'TODO': '待办',
    'PENDING': '待办',
    'IN_PROGRESS': '进行中',
    'COMPLETED': '已完成',
    'CANCELLED': '已取消'
  }
  return labels[status] || status
}

const getProgressStatus = (progress) => {
  if (progress >= 100) return 'success'
  if (progress >= 50) return ''
  return 'warning'
}

const fetchProjects = async () => {
  try {
    const res = await request.get('/projects/projects/')
    projects.value = res.data?.results || res.results || res.data || []
  } catch (error) {
    console.error('获取项目列表失败:', error)
  }
}

const fetchTasks = async () => {
  if (!selectedProject.value) {
    taskTree.value = []
    stats.total = 0
    stats.inProgress = 0
    stats.completed = 0
    stats.totalHours = 0
    return
  }
  
  loading.value = true
  try {
    // 使用查询参数过滤项目任务
    const res = await request.get('/projects/tasks/', {
      params: { project: selectedProject.value }
    })
    const tasks = res.data?.results || res.results || res.data || []
    taskTree.value = buildTree(tasks)
    calculateStats(tasks)
  } catch (error) {
    console.error('获取任务列表失败:', error)
    taskTree.value = []
    stats.total = 0
    stats.inProgress = 0
    stats.completed = 0
    stats.totalHours = 0
  } finally {
    loading.value = false
  }
}

const buildTree = (tasks, parentId = null) => {
  return tasks
    .filter(task => {
      const taskParent = task.parent ?? task.parent_id ?? null
      return taskParent === parentId
    })
    .map(task => ({
      ...task,
      children: buildTree(tasks, task.id)
    }))
}

const calculateStats = (tasks) => {
  stats.total = tasks.length
  stats.inProgress = tasks.filter(t => t.status === 'IN_PROGRESS').length
  stats.completed = tasks.filter(t => t.status === 'COMPLETED').length
  stats.totalHours = tasks.reduce((sum, t) => sum + (t.actual_hours || 0), 0)
}

const fetchProjectMembers = async () => {
  if (!selectedProject.value) return
  
  try {
    // 使用查询参数过滤项目成员
    const res = await request.get('/projects/members/', {
      params: { project: selectedProject.value }
    })
    projectMembers.value = res.data?.results || res.results || res.data || []
    
    // 如果没有成员，使用用户列表作为备选
    if (projectMembers.value.length === 0) {
      const userRes = await request.get('/auth/users/')
      projectMembers.value = userRes.data?.results || userRes.results || userRes.data || []
    }
  } catch (error) {
    // 使用用户列表作为备选
    try {
      const userRes = await request.get('/auth/users/')
      projectMembers.value = userRes.data?.results || userRes.results || userRes.data || []
    } catch (e) {
      projectMembers.value = [{ id: 1, username: 'admin' }]
    }
  }
}

const resetForm = () => {
  form.id = null
  form.code = ''
  form.name = ''
  form.parent = null
  form.assignee = null
  form.status = 'TODO'
  form.progress_percent = 0
  form.planned_hours = 0
  form.actual_hours = 0
  form.start_date = ''
  form.end_date = ''
  form.description = ''
  parentTaskName.value = ''
}

// 生成任务编号
const generateTaskCode = () => {
  const timestamp = Date.now().toString(36).toUpperCase()
  return `T-${timestamp}`
}

const handleAdd = () => {
  resetForm()
  dialogVisible.value = true
}

const handleAddChild = (row) => {
  resetForm()
  form.parent = row.id
  parentTaskName.value = row.name
  dialogVisible.value = true
}

const handleEdit = (row) => {
  form.id = row.id
  form.code = row.code || ''
  form.name = row.name || ''
  form.parent = row.parent || null
  form.assignee = row.assignee || null
  form.status = row.status || 'TODO'
  form.progress_percent = row.progress_percent || row.progress || 0
  form.planned_hours = row.planned_hours || 0
  form.actual_hours = row.actual_hours || 0
  form.start_date = row.start_date || ''
  form.end_date = row.end_date || ''
  form.description = row.description || ''
  parentTaskName.value = ''
  dialogVisible.value = true
}

const handleDelete = (row) => {
  ElMessageBox.confirm('确定要删除该任务吗？', '提示', {
    type: 'warning'
  }).then(async () => {
    try {
      await request.delete(`/projects/tasks/${row.id}/`)
      ElMessage.success('删除成功')
      fetchTasks()
    } catch (error) {
      ElMessage.error('删除失败')
    }
  }).catch(() => {})
}

const handleSubmit = async () => {
  try {
    await formRef.value.validate()
    
    // 构建提交数据
    const data = {
      project: selectedProject.value,
      name: form.name,
      status: form.status,
      progress_percent: form.progress_percent || 0,
      planned_hours: form.planned_hours || 0,
      actual_hours: form.actual_hours || 0,
    }
    
    // 新增时自动生成编号
    if (!form.id) {
      data.code = form.code || generateTaskCode()
    } else {
      data.code = form.code
    }
    
    // 可选字段，只有有值时才添加
    if (form.parent) {
      data.parent = form.parent
    }
    if (form.assignee) {
      data.assignee = form.assignee
    }
    if (form.start_date) {
      data.start_date = form.start_date
    }
    if (form.end_date) {
      data.end_date = form.end_date
    }
    if (form.description) {
      data.description = form.description
    }
    
    if (form.id) {
      await request.put(`/projects/tasks/${form.id}/`, data)
      ElMessage.success('更新成功')
    } else {
      await request.post('/projects/tasks/', data)
      ElMessage.success('创建成功')
    }
    
    dialogVisible.value = false
    fetchTasks()
  } catch (error) {
    console.error('操作失败:', error)
    if (error !== 'cancel') {
      ElMessage.error('操作失败')
    }
  }
}

const handleLogTime = (row) => {
  currentTask.value = row
  timeLogForm.date = new Date().toISOString().split('T')[0]
  timeLogForm.hours = 1
  timeLogForm.description = ''
  timeLogVisible.value = true
}

const handleSubmitTimeLog = async () => {
  try {
    await request.post('/projects/time-logs/', {
      task: currentTask.value.id,
      ...timeLogForm
    })
    ElMessage.success('工时填报成功')
    timeLogVisible.value = false
    fetchTasks()
  } catch (error) {
    ElMessage.error('工时填报失败')
  }
}

watch(selectedProject, () => {
  fetchTasks()
  fetchProjectMembers()
})

onMounted(() => {
  fetchProjects()
})
</script>

<style scoped>
.task-list {
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

