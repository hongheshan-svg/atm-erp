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
            <el-button type="primary" v-permission="'projects:project:create'" @click="handleAdd" :disabled="!selectedProject">
              <el-icon><Plus /></el-icon>
              新增任务
            </el-button>
          </div>
        </div>
      </template>
      
      <!-- 任务统计 -->
      <el-row :gutter="20" class="stats-row" v-if="selectedProject">
        <el-col :span="4">
          <el-statistic title="总任务数" :value="stats.total" />
        </el-col>
        <el-col :span="4">
          <el-statistic title="进行中" :value="stats.inProgress" :value-style="{ color: '#409eff' }" />
        </el-col>
        <el-col :span="4">
          <el-statistic title="已完成" :value="stats.completed" :value-style="{ color: '#67c23a' }" />
        </el-col>
        <el-col :span="4">
          <el-statistic title="计划工期" :value="stats.totalPlannedDays" suffix="天" />
        </el-col>
        <el-col :span="4">
          <el-statistic title="实际工时" :value="stats.totalActualHours" suffix="小时" :value-style="{ color: '#e6a23c' }" />
        </el-col>
        <el-col :span="4">
          <el-button size="small" @click="handleRecalculateHours" :loading="recalculating">
            <el-icon><Refresh /></el-icon> 重算工时
          </el-button>
        </el-col>
      </el-row>
      
      <!-- 任务树表格 -->
      <!-- 批量操作 -->
      <div v-if="selectedRows.length > 0" class="batch-toolbar">
        <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>
        <el-button type="danger" size="small" @click="batchDelete">批量删除</el-button>
        <el-button size="small" @click="batchExport">导出选中</el-button>
      </div>
      <el-table
        :data="taskTree"
        row-key="id"
        border
        stripe
        v-loading="loading"
        :tree-props="{ children: 'children', hasChildren: 'hasChildren' }"
        default-expand-all
       @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="45" />
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
        <el-table-column prop="planned_hours" label="计划工期" width="100" align="right">
          <template #default="{ row }">
            {{ row.planned_hours || 0 }}天
          </template>
        </el-table-column>
        <el-table-column prop="actual_hours" label="实际工时" width="120" align="right">
          <template #default="{ row }">
            <el-tooltip :content="`来自 ${row.time_log_count || 0} 条工时记录`" placement="top">
              <span>{{ row.actual_hours || 0 }}小时</span>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column prop="start_date" label="开始日期" width="110" />
        <el-table-column prop="end_date" label="结束日期" width="110" />
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row, $index }">
            <el-button type="info" link size="small" @click="handleMoveUp(row, $index)" :disabled="$index === 0" title="上移">
              <el-icon><Top /></el-icon>
            </el-button>
            <el-button type="info" link size="small" @click="handleMoveDown(row, $index)" :disabled="$index === flatTasks.length - 1" title="下移">
              <el-icon><Bottom /></el-icon>
            </el-button>
            <el-button type="primary" link size="small" v-permission="'projects:project:edit'" @click="handleEdit(row)">编辑</el-button>
            <el-button type="success" link size="small" @click="handleLogTime(row)">填报工时</el-button>
            <el-button type="warning" link size="small" v-permission="'projects:project:create'" @click="handleAddChild(row)">添加子任务</el-button>
            <el-button type="danger" link size="small" v-permission="'projects:project:delete'" @click="handleDelete(row)">删除</el-button>
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
            <el-form-item label="计划工期(天)" prop="planned_days">
              <el-input-number v-model="form.planned_days" :min="0" :step="1" :max="365" style="width: 100%;" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="实际工时(小时)">
              <el-input-number v-model="form.actual_hours" :min="0" :max="10000" style="width: 100%;" disabled />
              <div class="form-tip">
                <el-text type="info" size="small">工时从"填报工时"自动汇总</el-text>
              </div>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="开始日期" prop="start_date">
              <el-date-picker
                v-model="form.start_date"
                type="date"
                placeholder="选择日期"
                style="width: 100%;"
                value-format="YYYY-MM-DD"
                :disabled-date="disablePastDates"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="结束日期" prop="end_date">
              <el-date-picker
                v-model="form.end_date"
                type="date"
                placeholder="选择日期"
                style="width: 100%;"
                value-format="YYYY-MM-DD"
                :disabled-date="disablePastDates"
              />
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
          <el-date-picker
            v-model="timeLogForm.date"
            type="date"
            placeholder="选择日期（仅限当天）"
            style="width: 100%;"
            value-format="YYYY-MM-DD"
            :disabled-date="disableNotToday"
          />
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

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Top, Bottom, Refresh } from '@element-plus/icons-vue'
import { getProjectList, getTaskList, createTask, updateTask, deleteTask, patchTask, batchRecalculateHours, getMemberList, createTimeLog } from '@/api/projects/project'
import { usePermissionStore } from '@/stores/permission'
import { getUsers } from '@/api/auth'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/projects/tasks/', { onSuccess: () => fetchTasks() })


const loading = ref(false)
const recalculating = ref(false)
const selectedProject = ref(null)
const projects = ref<any[]>([])
const taskTree = ref<any[]>([])
const projectMembers = ref<any[]>([])
const projectMembersLoadedFor = ref(null)
const dialogVisible = ref(false)
const timeLogVisible = ref(false)
const formRef = ref(null)
const currentTask = ref(null)
const parentTaskName = ref('')
const allUsersLoaded = ref(false)
const permissionStore = usePermissionStore()

const stats = reactive({
  total: 0,
  inProgress: 0,
  completed: 0,
  totalPlannedDays: 0,
  totalActualHours: 0
})

const form = reactive({
  id: null,
  code: '',
  name: '',
  parent: null,
  assignee: null,
  status: 'TODO',
  progress_percent: 0,
  planned_days: 0, // 计划工期（天）
  actual_hours: 0, // 实际工时（小时）- 只读，从工时填报汇总
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
  status: [{ required: true, message: '请选择状态', trigger: 'change' }],
  planned_days: [{ required: true, message: '请输入计划工期（天）', trigger: 'change' }],
  start_date: [{ required: true, message: '请选择开始日期', trigger: 'change' }],
  end_date: [{ required: true, message: '请选择结束日期', trigger: 'change' }]
}

// 日期限制：任务开始/结束不可选过去日期；工时填报仅限当天
const disablePastDates = (date) => {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return date.getTime() < today.getTime()
}
const disableNotToday = (date) => {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const d = new Date(date)
  d.setHours(0, 0, 0, 0)
  return d.getTime() !== today.getTime()
}

const dialogTitle = computed(() => form.id ? '编辑任务' : '新增任务')

// 扁平化任务列表（用于排序判断）
const flatTasks = computed(() => {
  const result = []
  const flatten = (tasks) => {
    for (const task of tasks) {
      result.push(task)
      if (task.children && task.children.length > 0) {
        flatten(task.children)
      }
    }
  }
  flatten(taskTree.value)
  return result
})

// 所有用户列表（用于负责人选择的备选）
const allUsers = ref<any[]>([])

// 将项目成员/用户列表转换为统一的下拉选项格式
const assigneeOptions = computed(() => {
  const options = []
  const addedUserIds = new Set()
  
  // 首先添加项目成员
  for (const member of projectMembers.value) {
    // 项目成员数据 (来自 /projects/members/)
    if (member.user !== undefined) {
      if (!addedUserIds.has(member.user)) {
        options.push({
          id: member.user,
          label: member.user_name || `用户${member.user}`
        })
        addedUserIds.add(member.user)
      }
    } else {
      // 用户数据 (来自 /auth/users/)
      const fullName = `${member.last_name || ''}${member.first_name || ''}`.trim()
      if (!addedUserIds.has(member.id)) {
        options.push({
          id: member.id,
          label: fullName || member.username || `用户${member.id}`
        })
        addedUserIds.add(member.id)
      }
    }
  }
  
  // 然后从全部用户列表中添加缺失的用户（特别是当前任务的负责人可能不在项目成员中）
  for (const user of allUsers.value) {
    if (!addedUserIds.has(user.id)) {
      const fullName = `${user.last_name || ''}${user.first_name || ''}`.trim()
      options.push({
        id: user.id,
        label: fullName || user.username || `用户${user.id}`
      })
      addedUserIds.add(user.id)
    }
  }
  
  return options
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
    const res = await getProjectList()
    projects.value = res.results || res.results || res || []
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
    stats.totalPlannedDays = 0
    stats.totalActualHours = 0
    return
  }
  
  loading.value = true
  try {
    // 使用查询参数过滤项目任务
    const res = await getTaskList({ project: selectedProject.value })
    const tasks = res.results || res.results || res || []
    taskTree.value = buildTree(tasks)
    calculateStats(tasks)
  } catch (error) {
    console.error('获取任务列表失败:', error)
    taskTree.value = []
    stats.total = 0
    stats.inProgress = 0
    stats.completed = 0
    stats.totalPlannedDays = 0
    stats.totalActualHours = 0
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
  // 计划工期汇总（天）
  stats.totalPlannedDays = tasks.reduce((sum, t) => sum + (parseFloat(t.planned_hours) || 0), 0)
  // 实际工时汇总（小时）
  stats.totalActualHours = tasks.reduce((sum, t) => sum + (parseFloat(t.actual_hours) || 0), 0)
}

const fetchProjectMembers = async () => {
  if (!selectedProject.value) {
    projectMembers.value = []
    projectMembersLoadedFor.value = null
    return false
  }

  if (projectMembersLoadedFor.value === selectedProject.value) {
    return true
  }

  try {
    const membersRes = await getMemberList({ project: selectedProject.value })
    projectMembers.value = membersRes.results || membersRes.results || membersRes || []
    projectMembersLoadedFor.value = selectedProject.value
    return true
  } catch (error) {
    if (error?.response?.status !== 403) {
      console.error('加载项目成员失败:', error)
    }
    projectMembers.value = []
    projectMembersLoadedFor.value = null
    return false
  }
}

const fetchAllUsers = async () => {
  if (allUsersLoaded.value) {
    return true
  }

  if (!permissionStore.hasPermission('system:users')) {
    allUsers.value = []
    return false
  }

  try {
    const userRes = await getUsers()
    allUsers.value = userRes.results || userRes.results || userRes || []
    allUsersLoaded.value = true
    return true
  } catch (error) {
    if (error?.response?.status !== 403) {
      console.error('加载用户列表失败:', error)
    }
    allUsers.value = []
    return false
  }
}

const ensureAssigneeOptionsLoaded = async () => {
  await fetchProjectMembers()
  await fetchAllUsers()
}

const resetForm = () => {
  form.id = null
  form.code = ''
  form.name = ''
  form.parent = null
  form.assignee = null
  form.status = 'TODO'
  form.progress_percent = 0
  form.planned_days = 0
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

const handleAdd = async () => {
  resetForm()
  await ensureAssigneeOptionsLoaded()
  dialogVisible.value = true
}

const handleAddChild = async (row) => {
  resetForm()
  await ensureAssigneeOptionsLoaded()
  form.parent = row.id
  parentTaskName.value = row.name
  dialogVisible.value = true
}

const handleEdit = async (row) => {
  await ensureAssigneeOptionsLoaded()
  form.id = row.id
  form.code = row.code || ''
  form.name = row.name || ''
  form.parent = row.parent || null
  form.assignee = row.assignee || null
  form.status = row.status || 'TODO'
  form.progress_percent = row.progress_percent || row.progress || 0
  // 后端存储的是 planned_hours，但我们用 planned_days 显示
  form.planned_days = row.planned_hours || row.planned_days || 0
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
      await deleteTask(row.id)
      ElMessage.success('删除成功')
      fetchTasks()
    } catch (error) {
      ElMessage.error('删除失败')
    }
  }).catch(error => { console.error(error) })
}

// 上移任务
const handleMoveUp = async (row, index) => {
  if (index === 0) return
  
  const tasks = flatTasks.value
  const prevTask = tasks[index - 1]
  
  try {
    // 使用索引位置作为新的 sort_order（交换位置）
    // 当前任务移到上一个位置，上一个任务移到当前位置
    await Promise.all([
      patchTask(row.id, { sort_order: index - 1 }),
      patchTask(prevTask.id, { sort_order: index })
    ])
    
    ElMessage.success('排序已更新')
    fetchTasks()
  } catch (error) {
    ElMessage.error('排序更新失败')
  }
}

// 下移任务
const handleMoveDown = async (row, index) => {
  const tasks = flatTasks.value
  if (index >= tasks.length - 1) return
  
  const nextTask = tasks[index + 1]
  
  try {
    // 使用索引位置作为新的 sort_order（交换位置）
    // 当前任务移到下一个位置，下一个任务移到当前位置
    await Promise.all([
      patchTask(row.id, { sort_order: index + 1 }),
      patchTask(nextTask.id, { sort_order: index })
    ])
    
    ElMessage.success('排序已更新')
    fetchTasks()
  } catch (error) {
    ElMessage.error('排序更新失败')
  }
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
      // 计划工期存储为 planned_hours 字段（后端字段名）
      planned_hours: form.planned_days || 0,
      // 实际工时不在这里提交，由工时填报自动汇总
    }
    
    // 新增时自动生成编号，并设置排序到最后
    if (!form.id) {
      data.code = form.code || generateTaskCode()
      // 新任务排在最后
      const maxSortOrder = flatTasks.value.reduce((max, t) => Math.max(max, t.sort_order ?? 0), 0)
      data.sort_order = maxSortOrder + 1
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
      await updateTask(form.id, data)
      ElMessage.success('更新成功')
    } else {
      await createTask(data)
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

// 重新计算所有任务的实际工时（从工时填报汇总）
const handleRecalculateHours = async () => {
  if (!selectedProject.value) return
  
  try {
    recalculating.value = true
    const res = await batchRecalculateHours({ project: selectedProject.value })
    ElMessage.success(res.message || '工时重算完成')
    fetchTasks() // 刷新任务列表
  } catch (error) {
    console.error('重算工时失败:', error)
    ElMessage.error('重算工时失败')
  } finally {
    recalculating.value = false
  }
}

const handleSubmitTimeLog = async () => {
  try {
    await createTimeLog({ task: currentTask.value.id, ...timeLogForm })
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

.form-tip {
  margin-top: 4px;
  font-size: 12px;
}
</style>

