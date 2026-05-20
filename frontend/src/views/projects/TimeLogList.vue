<template>
  <div class="time-log-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>工时填报</span>
          <div class="header-actions">
            <el-button type="primary" v-permission="'projects:project:create'" @click="handleAdd">
              <el-icon><Plus /></el-icon>
              填报工时
            </el-button>
          </div>
        </div>
      </template>
      
      <!-- 搜索区域 -->
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="项目">
          <el-select v-model="searchForm.project" placeholder="选择项目" clearable filterable style="width: 200px;">
            <el-option
              v-for="project in projects"
              :key="project.id"
              :label="project.name"
              :value="project.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="日期范围">
          <el-date-picker
            v-model="searchForm.dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            value-format="YYYY-MM-DD"
            style="width: 240px;"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">查询</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
      
      <!-- 工时统计 -->
      <el-row :gutter="20" class="stats-row">
        <el-col :span="6">
          <el-card shadow="hover" class="stat-card">
            <el-statistic title="本周工时" :value="stats.weekHours" suffix="小时" />
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover" class="stat-card">
            <el-statistic title="本月工时" :value="stats.monthHours" suffix="小时" />
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover" class="stat-card">
            <el-statistic title="填报天数" :value="stats.workDays" suffix="天" />
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover" class="stat-card">
            <el-statistic title="日均工时" :value="stats.avgHours" :precision="1" suffix="小时" />
          </el-card>
        </el-col>
      </el-row>
      
      <!-- 批量操作工具栏 -->
      <div class="table-toolbar" v-permission="'projects:project:delete'" v-if="canDelete && selectedRows.length > 0">
        <span>已选择 {{ selectedRows.length }} 项</span>
        <el-button type="danger" size="small" v-permission="'projects:project:delete'" @click="batchDelete" :loading="deleteLoading">批量删除</el-button>
      </div>

      <!-- 工时列表 -->
      <el-table :data="timeLogs" border stripe v-loading="loading" @selection-change="handleSelectionChange">
        <el-table-column v-permission="'projects:project:delete'" v-if="canDelete" type="selection" width="55" fixed />
        <el-table-column prop="date" label="日期" width="110" />
        <el-table-column prop="project_name" label="项目" width="180" />
        <el-table-column prop="task_name" label="任务" min-width="200" />
        <el-table-column prop="hours" label="工时" width="100" align="right">
          <template #default="{ row }">
            {{ row.hours }}小时
          </template>
        </el-table-column>
        <el-table-column prop="description" label="工作内容" min-width="250" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ getStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="提交时间" width="160" />
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" v-permission="'projects:project:edit'" @click="handleEdit(row)" :disabled="row.status !== 'PENDING'">编辑</el-button>
            <el-button v-if="canDelete" type="danger" link size="small" @click="deleteRow(row)" :loading="deleteLoading">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <!-- 分页 -->
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :page-sizes="[10, 20, 50]"
        :total="pagination.total"
        layout="total, sizes, prev, pager, next"
        class="pagination"
        @size-change="fetchData"
        @current-change="fetchData"
      />
    </el-card>
    
    <!-- 填报工时对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="600px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item label="日期" prop="date">
          <el-date-picker v-model="form.date" type="date" placeholder="选择日期" style="width: 100%;" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="项目" prop="project">
          <el-select v-model="form.project" placeholder="选择项目" filterable style="width: 100%;" @change="handleProjectChange">
            <el-option
              v-for="project in projects"
              :key="project.id"
              :label="project.name"
              :value="project.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="任务" prop="task">
          <el-select v-model="form.task" placeholder="选择任务" filterable style="width: 100%;" :disabled="!form.project">
            <el-option
              v-for="task in projectTasks"
              :key="task.id"
              :label="task.name"
              :value="task.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="工时(小时)" prop="hours">
          <el-input-number v-model="form.hours" :min="0.5" :max="24" :step="0.5" style="width: 100%;" />
        </el-form-item>
        <el-form-item label="工作内容" prop="description">
          <el-input v-model="form.description" type="textarea" :rows="4" placeholder="描述今日工作内容" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { getProjectList, getTaskList, getTimeLogList, createTimeLog, updateTimeLog } from '@/api/projects/project'
import { useBatchDelete } from '@/composables/useBatchDelete'
import { usePermission } from '@/composables/usePermission'

// 权限检查
const { canDelete } = usePermission()

// 批量删除功能
const { selectedRows, loading: deleteLoading, handleSelectionChange, batchDelete, deleteRow } = useBatchDelete(
  '/projects/time-logs/',
  { onSuccess: () => fetchData(), confirmTitle: '删除工时', confirmMessage: '确定要删除该工时记录吗？' }
)

const loading = ref(false)
const projects = ref([])
const projectTasks = ref([])
const timeLogs = ref([])
const dialogVisible = ref(false)
const formRef = ref(null)

const searchForm = reactive({
  project: '',
  dateRange: []
})

const stats = reactive({
  weekHours: 0,
  monthHours: 0,
  workDays: 0,
  avgHours: 0
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const form = reactive({
  id: null,
  date: '',
  project: null,
  task: null,
  hours: 8,
  description: ''
})

const rules = {
  date: [{ required: true, message: '请选择日期', trigger: 'change' }],
  project: [{ required: true, message: '请选择项目', trigger: 'change' }],
  hours: [{ required: true, message: '请输入工时', trigger: 'blur' }],
  description: [{ required: true, message: '请输入工作内容', trigger: 'blur' }]
}

const dialogTitle = computed(() => form.id ? '编辑工时' : '填报工时')

const getStatusType = (status) => {
  const types = {
    'PENDING': 'warning',
    'APPROVED': 'success',
    'REJECTED': 'danger'
  }
  return types[status] || 'info'
}

const getStatusLabel = (status) => {
  const labels = {
    'PENDING': '待审核',
    'APPROVED': '已通过',
    'REJECTED': '已驳回'
  }
  return labels[status] || status
}

const fetchProjects = async () => {
  try {
    const res = await getProjectList()
    projects.value = res.data?.results || res.results || res.data || []
  } catch (error) {
    console.error('获取项目列表失败:', error)
  }
}

const fetchData = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize
    }
    if (searchForm.project) params.project = searchForm.project
    if (searchForm.dateRange && searchForm.dateRange.length === 2) {
      params.start_date = searchForm.dateRange[0]
      params.end_date = searchForm.dateRange[1]
    }
    
    const res = await getTimeLogList(params)
    timeLogs.value = res.data?.results || res.results || res.data || []
    pagination.total = res.data?.count || res.count || 0
    
    calculateStats()
  } catch (error) {
    console.error('获取工时记录失败:', error)
    timeLogs.value = []
    ElMessage.error('获取工时记录失败')
  } finally {
    loading.value = false
  }
}

const calculateStats = () => {
  const now = new Date()
  const weekStart = new Date(now)
  weekStart.setDate(now.getDate() - now.getDay())
  const monthStart = new Date(now.getFullYear(), now.getMonth(), 1)
  
  stats.weekHours = timeLogs.value
    .filter(log => new Date(log.date) >= weekStart)
    .reduce((sum, log) => sum + log.hours, 0)
  
  stats.monthHours = timeLogs.value
    .filter(log => new Date(log.date) >= monthStart)
    .reduce((sum, log) => sum + log.hours, 0)
  
  const uniqueDays = new Set(timeLogs.value.map(log => log.date))
  stats.workDays = uniqueDays.size
  
  stats.avgHours = stats.workDays > 0 ? stats.monthHours / stats.workDays : 0
}

const fetchProjectTasks = async (projectId) => {
  if (!projectId) {
    projectTasks.value = []
    return
  }
  
  try {
    // 使用查询参数过滤项目任务
    const res = await getTaskList({ project: projectId })
    projectTasks.value = res.data?.results || res.results || res.data || []
  } catch (error) {
    projectTasks.value = [
      { id: 1, name: '需求分析' },
      { id: 2, name: '系统设计' },
      { id: 3, name: '开发实现' }
    ]
  }
}

const handleProjectChange = (projectId) => {
  form.task = null
  fetchProjectTasks(projectId)
}

const resetForm = () => {
  form.id = null
  form.date = new Date().toISOString().split('T')[0]
  form.project = null
  form.task = null
  form.hours = 8
  form.description = ''
}

const handleSearch = () => {
  pagination.page = 1
  fetchData()
}

const handleReset = () => {
  searchForm.project = ''
  searchForm.dateRange = []
  handleSearch()
}

const handleAdd = () => {
  resetForm()
  dialogVisible.value = true
}

const handleEdit = (row) => {
  Object.assign(form, row)
  if (row.project) {
    fetchProjectTasks(row.project)
  }
  dialogVisible.value = true
}

// handleDelete 已被 useBatchDelete 的 deleteRow 替代

const handleSubmit = async () => {
  try {
    await formRef.value.validate()
    
    if (form.id) {
      await updateTimeLog(form.id, form)
      ElMessage.success('更新成功')
    } else {
      await createTimeLog(form)
      ElMessage.success('提交成功')
    }
    
    dialogVisible.value = false
    fetchData()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('操作失败')
    }
  }
}

onMounted(() => {
  fetchProjects()
  fetchData()
})
</script>

<style scoped>
.time-log-list {
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

.search-form {
  margin-bottom: 20px;
}

.stats-row {
  margin-bottom: 20px;
}

.stat-card {
  text-align: center;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}
</style>

