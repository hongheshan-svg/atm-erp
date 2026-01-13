<template>
  <div class="bug-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>Bug跟踪</span>
          <div class="header-actions">
            <el-button type="primary" @click="handleAdd">
              <el-icon><Plus /></el-icon> 新建Bug
            </el-button>
          </div>
        </div>
      </template>

      <!-- 搜索筛选 -->
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="项目">
          <el-select v-model="searchForm.project" placeholder="选择项目" clearable filterable style="width: 180px;" @change="loadBugs">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="选择状态" clearable style="width: 120px;" @change="loadBugs">
            <el-option v-for="s in statusOptions" :key="s.value" :label="s.label" :value="s.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="严重程度">
          <el-select v-model="searchForm.severity" placeholder="选择严重程度" clearable style="width: 120px;" @change="loadBugs">
            <el-option v-for="s in severityOptions" :key="s.value" :label="s.label" :value="s.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="searchForm.priority" placeholder="选择优先级" clearable style="width: 120px;" @change="loadBugs">
            <el-option v-for="p in priorityOptions" :key="p.value" :label="p.label" :value="p.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="处理人">
          <el-select v-model="searchForm.assignee" placeholder="选择处理人" clearable filterable style="width: 150px;" @change="loadBugs">
            <el-option v-for="u in users" :key="u.id" :label="u.name" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-input v-model="searchForm.search" placeholder="搜索标题/编号" clearable style="width: 200px;" @keyup.enter="loadBugs" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadBugs">搜索</el-button>
          <el-button @click="resetSearch">重置</el-button>
        </el-form-item>
      </el-form>

      <!-- 快捷筛选 -->
      <div class="quick-filters">
        <el-radio-group v-model="quickFilter" @change="handleQuickFilter">
          <el-radio-button value="">全部</el-radio-button>
          <el-radio-button value="my_assigned">我处理的</el-radio-button>
          <el-radio-button value="my_reported">我报告的</el-radio-button>
          <el-radio-button value="open">待处理</el-radio-button>
          <el-radio-button value="closed">已关闭</el-radio-button>
        </el-radio-group>
      </div>

      <!-- 统计卡片 -->
      <div class="stats-cards" v-if="stats">
        <el-row :gutter="16">
          <el-col :span="4">
            <div class="stat-card total">
              <div class="stat-value">{{ stats.total }}</div>
              <div class="stat-label">总数</div>
            </div>
          </el-col>
          <el-col :span="4">
            <div class="stat-card open">
              <div class="stat-value">{{ stats.open_count }}</div>
              <div class="stat-label">待处理</div>
            </div>
          </el-col>
          <el-col :span="4">
            <div class="stat-card closed">
              <div class="stat-value">{{ stats.closed_count }}</div>
              <div class="stat-label">已关闭</div>
            </div>
          </el-col>
          <el-col :span="4">
            <div class="stat-card today-created">
              <div class="stat-value">{{ stats.created_today }}</div>
              <div class="stat-label">今日新增</div>
            </div>
          </el-col>
          <el-col :span="4">
            <div class="stat-card today-resolved">
              <div class="stat-value">{{ stats.resolved_today }}</div>
              <div class="stat-label">今日解决</div>
            </div>
          </el-col>
        </el-row>
      </div>

      <!-- 批量操作工具栏 -->
      <div class="table-toolbar" v-if="canDelete && selectedRows.length > 0">
        <span>已选择 {{ selectedRows.length }} 项</span>
        <el-button type="danger" size="small" @click="batchDelete" :loading="deleteLoading">批量删除</el-button>
      </div>

      <!-- Bug列表 -->
      <el-table :data="bugs" v-loading="loading" stripe border @row-click="handleRowClick" @selection-change="handleSelectionChange" class="bug-table">
        <el-table-column v-if="canDelete" type="selection" width="55" fixed />
        <el-table-column prop="bug_number" label="编号" width="140" fixed="left">
          <template #default="{ row }">
            <el-link type="primary" @click.stop="handleView(row)">{{ row.bug_number }}</el-link>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="标题" min-width="250" show-overflow-tooltip />
        <el-table-column prop="project_name" label="项目" width="150" show-overflow-tooltip />
        <el-table-column prop="severity" label="严重程度" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getSeverityType(row.severity)" size="small">
              {{ row.severity_display }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="priority" label="优先级" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="getPriorityType(row.priority)" size="small" effect="dark">
              {{ row.priority }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ row.status_display }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="bug_type_display" label="类型" width="100" />
        <el-table-column prop="assignee_name" label="处理人" width="100" />
        <el-table-column prop="reporter_name" label="报告人" width="100" />
        <el-table-column label="评论/附件" width="90" align="center">
          <template #default="{ row }">
            <span v-if="row.comment_count">💬{{ row.comment_count }}</span>
            <span v-if="row.attachment_count" style="margin-left: 8px;">📎{{ row.attachment_count }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="160">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click.stop="handleEdit(row)">编辑</el-button>
            <el-dropdown @command="(cmd) => handleCommand(cmd, row)" trigger="click">
              <el-button size="small" @click.stop>
                更多<el-icon class="el-icon--right"><ArrowDown /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="assign">分配</el-dropdown-item>
                  <el-dropdown-item command="status">变更状态</el-dropdown-item>
                  <el-dropdown-item command="delete" divided>删除</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="loadBugs"
        @current-change="loadBugs"
        style="margin-top: 20px; justify-content: center;"
      />
    </el-card>

    <!-- 新建/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="800px" destroy-on-close>
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-row :gutter="20">
          <el-col :span="24">
            <el-form-item label="标题" prop="title">
              <el-input v-model="form.title" placeholder="请输入Bug标题" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="所属项目" prop="project">
              <el-select v-model="form.project" placeholder="选择项目" filterable style="width: 100%;">
                <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="模块">
              <el-input v-model="form.module" placeholder="所属模块/组件" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="严重程度" prop="severity">
              <el-select v-model="form.severity" style="width: 100%;">
                <el-option v-for="s in severityOptions" :key="s.value" :label="s.label" :value="s.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="优先级" prop="priority">
              <el-select v-model="form.priority" style="width: 100%;">
                <el-option v-for="p in priorityOptions" :key="p.value" :label="p.label" :value="p.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="Bug类型" prop="bug_type">
              <el-select v-model="form.bug_type" style="width: 100%;">
                <el-option v-for="t in typeOptions" :key="t.value" :label="t.label" :value="t.value" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="处理人">
              <el-select v-model="form.assignee" placeholder="选择处理人" clearable filterable style="width: 100%;">
                <el-option v-for="u in users" :key="u.id" :label="u.name" :value="u.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="环境">
              <el-input v-model="form.environment" placeholder="测试/生产" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="版本">
              <el-input v-model="form.version" placeholder="软件版本" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row>
          <el-col :span="24">
            <el-form-item label="详细描述" prop="description">
              <el-input
                v-model="form.description"
                type="textarea"
                :rows="6"
                placeholder="请详细描述Bug的表现、复现步骤、期望结果等"
              />
            </el-form-item>
          </el-col>
        </el-row>
        
        <!-- 编辑时显示状态和解决方案 -->
        <template v-if="isEdit">
          <el-divider content-position="left">状态信息</el-divider>
          <el-row :gutter="20">
            <el-col :span="8">
              <el-form-item label="状态">
                <el-select v-model="form.status" style="width: 100%;">
                  <el-option v-for="s in statusOptions" :key="s.value" :label="s.label" :value="s.value" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="解决方式">
                <el-select v-model="form.resolution" placeholder="选择解决方式" clearable style="width: 100%;">
                  <el-option v-for="r in resolutionOptions" :key="r.value" :label="r.label" :value="r.value" />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>
          <el-row>
            <el-col :span="24">
              <el-form-item label="解决说明">
                <el-input v-model="form.solution" type="textarea" :rows="3" placeholder="解决方案说明" />
              </el-form-item>
            </el-col>
          </el-row>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="saving">保存</el-button>
      </template>
    </el-dialog>

    <!-- 分配对话框 -->
    <el-dialog v-model="assignDialogVisible" title="分配处理人" width="400px">
      <el-form label-width="80px">
        <el-form-item label="处理人">
          <el-select v-model="assignForm.assignee" placeholder="选择处理人" filterable style="width: 100%;">
            <el-option v-for="u in users" :key="u.id" :label="u.name" :value="u.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="assignDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleAssignSubmit" :loading="assigning">确定</el-button>
      </template>
    </el-dialog>

    <!-- 状态变更对话框 -->
    <el-dialog v-model="statusDialogVisible" title="变更状态" width="500px">
      <el-form :model="statusForm" label-width="100px">
        <el-form-item label="新状态">
          <el-select v-model="statusForm.status" placeholder="选择状态" style="width: 100%;">
            <el-option v-for="s in statusOptions" :key="s.value" :label="s.label" :value="s.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="解决方式" v-if="statusForm.status === 'RESOLVED'">
          <el-select v-model="statusForm.resolution" placeholder="选择解决方式" style="width: 100%;">
            <el-option v-for="r in resolutionOptions" :key="r.value" :label="r.label" :value="r.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="说明" v-if="statusForm.status === 'RESOLVED'">
          <el-input v-model="statusForm.solution" type="textarea" :rows="3" placeholder="解决方案说明" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="statusDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleStatusSubmit" :loading="changingStatus">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, ArrowDown } from '@element-plus/icons-vue'
import request from '@/utils/request'
import { useBatchDelete } from '@/composables/useBatchDelete'
import { usePermission } from '@/composables/usePermission'

const router = useRouter()

// 权限检查
const { canDelete } = usePermission()

// 批量删除功能
const { selectedRows, loading: deleteLoading, handleSelectionChange, batchDelete, deleteRow } = useBatchDelete(
  '/projects/bugs/',
  { onSuccess: loadBugs, confirmTitle: '删除Bug', confirmMessage: '确定要删除该Bug吗？' }
)

const loading = ref(false)
const saving = ref(false)
const assigning = ref(false)
const changingStatus = ref(false)

const bugs = ref([])
const projects = ref([])
const users = ref([])
const stats = ref(null)
const dialogVisible = ref(false)
const assignDialogVisible = ref(false)
const statusDialogVisible = ref(false)
const dialogTitle = ref('新建Bug')
const isEdit = ref(false)
const currentBug = ref(null)
const formRef = ref(null)
const quickFilter = ref('')

const searchForm = reactive({
  project: null,
  status: '',
  severity: '',
  priority: '',
  assignee: null,
  search: ''
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const form = reactive({
  title: '',
  description: '',
  project: null,
  module: '',
  severity: 'NORMAL',
  priority: 'P2',
  bug_type: 'FUNCTION',
  status: 'NEW',
  assignee: null,
  environment: '',
  version: '',
  resolution: '',
  solution: ''
})

const assignForm = reactive({
  assignee: null
})

const statusForm = reactive({
  status: '',
  resolution: '',
  solution: ''
})

const rules = {
  title: [{ required: true, message: '请输入Bug标题', trigger: 'blur' }],
  project: [{ required: true, message: '请选择项目', trigger: 'change' }],
  description: [{ required: true, message: '请输入详细描述', trigger: 'blur' }],
  severity: [{ required: true, message: '请选择严重程度', trigger: 'change' }],
  priority: [{ required: true, message: '请选择优先级', trigger: 'change' }],
  bug_type: [{ required: true, message: '请选择Bug类型', trigger: 'change' }]
}

const severityOptions = [
  { value: 'CRITICAL', label: '致命' },
  { value: 'MAJOR', label: '严重' },
  { value: 'NORMAL', label: '一般' },
  { value: 'MINOR', label: '轻微' },
  { value: 'SUGGESTION', label: '建议' }
]

const priorityOptions = [
  { value: 'P0', label: 'P0-紧急' },
  { value: 'P1', label: 'P1-高' },
  { value: 'P2', label: 'P2-中' },
  { value: 'P3', label: 'P3-低' }
]

const statusOptions = [
  { value: 'NEW', label: '新建' },
  { value: 'CONFIRMED', label: '已确认' },
  { value: 'IN_PROGRESS', label: '处理中' },
  { value: 'RESOLVED', label: '已解决' },
  { value: 'CLOSED', label: '已关闭' },
  { value: 'REOPENED', label: '重新打开' },
  { value: 'SUSPENDED', label: '挂起' },
  { value: 'CANNOT_REPRODUCE', label: '无法复现' },
  { value: 'BY_DESIGN', label: '设计如此' },
  { value: 'DUPLICATE', label: '重复' }
]

const typeOptions = [
  { value: 'FUNCTION', label: '功能问题' },
  { value: 'PERFORMANCE', label: '性能问题' },
  { value: 'UI', label: '界面问题' },
  { value: 'SECURITY', label: '安全问题' },
  { value: 'DATA', label: '数据问题' },
  { value: 'COMPATIBILITY', label: '兼容性问题' },
  { value: 'OTHER', label: '其他' }
]

const resolutionOptions = [
  { value: 'FIXED', label: '已修复' },
  { value: 'WONT_FIX', label: '不予修复' },
  { value: 'DUPLICATE', label: '重复问题' },
  { value: 'INVALID', label: '无效问题' },
  { value: 'CANNOT_REPRODUCE', label: '无法复现' },
  { value: 'BY_DESIGN', label: '设计如此' }
]

const getSeverityType = (severity) => {
  const types = {
    'CRITICAL': 'danger',
    'MAJOR': 'warning',
    'NORMAL': 'info',
    'MINOR': 'success',
    'SUGGESTION': ''
  }
  return types[severity] || ''
}

const getPriorityType = (priority) => {
  const types = {
    'P0': 'danger',
    'P1': 'warning',
    'P2': 'info',
    'P3': 'success'
  }
  return types[priority] || ''
}

const getStatusType = (status) => {
  const types = {
    'NEW': '',
    'CONFIRMED': 'warning',
    'IN_PROGRESS': 'primary',
    'RESOLVED': 'success',
    'CLOSED': 'info',
    'REOPENED': 'danger',
    'SUSPENDED': 'info',
    'CANNOT_REPRODUCE': 'info',
    'BY_DESIGN': 'info',
    'DUPLICATE': 'info'
  }
  return types[status] || ''
}

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', { 
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit'
  })
}

const loadBugs = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
      ...searchForm
    }
    
    // 清理空值
    Object.keys(params).forEach(key => {
      if (params[key] === '' || params[key] === null) {
        delete params[key]
      }
    })
    
    const response = await request.get('/projects/bugs/', { params })
    bugs.value = response.results || response || []
    pagination.total = response.count || 0
  } catch (error) {
    ElMessage.error('加载Bug列表失败')
  } finally {
    loading.value = false
  }
}

const loadStats = async () => {
  try {
    const params = searchForm.project ? { project: searchForm.project } : {}
    const response = await request.get('/projects/bugs/statistics/', { params })
    stats.value = response
  } catch (error) {
    console.error('加载统计失败:', error)
  }
}

const loadProjects = async () => {
  try {
    const response = await request.get('/projects/projects/', { params: { page_size: 1000 } })
    projects.value = response.results || response || []
  } catch (error) {
    console.error('加载项目失败:', error)
  }
}

const loadUsers = async () => {
  try {
    const response = await request.get('/auth/users/', { params: { is_active: true, page_size: 1000 } })
    const data = response.results || response || []
    users.value = data.map(u => ({
      id: u.id,
      name: `${u.last_name || ''}${u.first_name || ''}` || u.username
    }))
  } catch (error) {
    console.error('加载用户失败:', error)
  }
}

const handleQuickFilter = (value) => {
  if (value === 'my_assigned') {
    searchForm.assignee = null // 后端会根据my_bugs参数处理
  } else if (value === 'my_reported') {
    searchForm.assignee = null
  } else if (value === 'open') {
    searchForm.status = ''
  } else if (value === 'closed') {
    searchForm.status = 'CLOSED'
  }
  loadBugs()
}

const resetSearch = () => {
  Object.assign(searchForm, {
    project: null,
    status: '',
    severity: '',
    priority: '',
    assignee: null,
    search: ''
  })
  quickFilter.value = ''
  pagination.page = 1
  loadBugs()
  loadStats()
}

const resetForm = () => {
  Object.assign(form, {
    title: '',
    description: '',
    project: null,
    module: '',
    severity: 'NORMAL',
    priority: 'P2',
    bug_type: 'FUNCTION',
    status: 'NEW',
    assignee: null,
    environment: '',
    version: '',
    resolution: '',
    solution: ''
  })
}

const handleAdd = () => {
  dialogTitle.value = '新建Bug'
  isEdit.value = false
  resetForm()
  
  // 如果当前有选中项目，自动填充
  if (searchForm.project) {
    form.project = searchForm.project
  }
  
  dialogVisible.value = true
}

const handleEdit = (row) => {
  dialogTitle.value = `编辑Bug - ${row.bug_number}`
  isEdit.value = true
  currentBug.value = row
  
  Object.assign(form, {
    title: row.title,
    description: row.description || '',
    project: row.project,
    module: row.module || '',
    severity: row.severity,
    priority: row.priority,
    bug_type: row.bug_type,
    status: row.status,
    assignee: row.assignee,
    environment: row.environment || '',
    version: row.version || '',
    resolution: row.resolution || '',
    solution: row.solution || ''
  })
  
  dialogVisible.value = true
}

const handleView = (row) => {
  router.push(`/projects/bugs/${row.id}`)
}

const handleRowClick = (row) => {
  // 可选：点击行查看详情
}

const handleSubmit = async () => {
  try {
    await formRef.value.validate()
    saving.value = true
    
    const data = { ...form }
    
    if (isEdit.value) {
      await request.put(`/projects/bugs/${currentBug.value.id}/`, data)
      ElMessage.success('更新成功')
    } else {
      await request.post('/projects/bugs/', data)
      ElMessage.success('创建成功')
    }
    
    dialogVisible.value = false
    loadBugs()
    loadStats()
  } catch (error) {
    if (error !== 'cancel' && error !== false) {
      const msg = error.response?.data?.detail || '保存失败'
      ElMessage.error(msg)
    }
  } finally {
    saving.value = false
  }
}

const handleCommand = (command, row) => {
  currentBug.value = row
  
  if (command === 'assign') {
    assignForm.assignee = row.assignee
    assignDialogVisible.value = true
  } else if (command === 'status') {
    statusForm.status = row.status
    statusForm.resolution = row.resolution || ''
    statusForm.solution = row.solution || ''
    statusDialogVisible.value = true
  } else if (command === 'delete') {
    deleteRow(row)
  }
}

// handleDelete 已被 useBatchDelete 的 deleteRow 替代

const handleAssignSubmit = async () => {
  if (!assignForm.assignee) {
    ElMessage.warning('请选择处理人')
    return
  }
  
  assigning.value = true
  try {
    await request.post(`/projects/bugs/${currentBug.value.id}/assign/`, {
      assignee: assignForm.assignee
    })
    ElMessage.success('分配成功')
    assignDialogVisible.value = false
    loadBugs()
  } catch (error) {
    ElMessage.error('分配失败')
  } finally {
    assigning.value = false
  }
}

const handleStatusSubmit = async () => {
  if (!statusForm.status) {
    ElMessage.warning('请选择状态')
    return
  }
  
  changingStatus.value = true
  try {
    await request.post(`/projects/bugs/${currentBug.value.id}/change_status/`, statusForm)
    ElMessage.success('状态变更成功')
    statusDialogVisible.value = false
    loadBugs()
    loadStats()
  } catch (error) {
    const msg = error.response?.data?.error || '状态变更失败'
    ElMessage.error(msg)
  } finally {
    changingStatus.value = false
  }
}

onMounted(() => {
  loadProjects()
  loadUsers()
  loadBugs()
  loadStats()
})
</script>

<style scoped>
.bug-list {
  padding: 0;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.search-form {
  margin-bottom: 16px;
}

.quick-filters {
  margin-bottom: 16px;
}

.stats-cards {
  margin-bottom: 20px;
}

.stat-card {
  background: #f5f7fa;
  border-radius: 8px;
  padding: 16px;
  text-align: center;
  transition: all 0.3s;
}

.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.stat-card.total {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.stat-card.open {
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
  color: white;
}

.stat-card.closed {
  background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
  color: white;
}

.stat-card.today-created {
  background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);
  color: white;
}

.stat-card.today-resolved {
  background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);
  color: white;
}

.stat-value {
  font-size: 28px;
  font-weight: bold;
  margin-bottom: 4px;
}

.stat-label {
  font-size: 14px;
  opacity: 0.9;
}

.bug-table {
  cursor: pointer;
}

:deep(.el-table__row:hover) {
  background-color: #f5f7fa !important;
}
</style>

