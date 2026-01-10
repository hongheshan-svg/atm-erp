<template>
  <div class="plan-list">
    <!-- 页面标题 -->
    <div class="page-header">
      <div class="header-left">
        <h2>生产计划管理</h2>
        <span class="subtitle">项目级别的生产排程和进度跟踪</span>
      </div>
      <div class="header-right">
        <el-button type="primary" @click="handleAdd">
          <el-icon><Plus /></el-icon>
          新建计划
        </el-button>
      </div>
    </div>

    <!-- 搜索筛选 -->
    <el-card class="filter-card" shadow="never">
      <el-form :model="filters" inline>
        <el-form-item label="项目">
          <el-select
            v-model="filters.project"
            placeholder="选择项目"
            clearable
            filterable
            style="width: 220px"
          >
            <el-option
              v-for="item in projects"
              :key="item.id"
              :label="`${item.code} - ${item.name}`"
              :value="item.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部状态" clearable style="width: 120px">
            <el-option label="草稿" value="DRAFT" />
            <el-option label="已确认" value="CONFIRMED" />
            <el-option label="生产中" value="IN_PROGRESS" />
            <el-option label="已完成" value="COMPLETED" />
            <el-option label="已取消" value="CANCELLED" />
          </el-select>
        </el-form-item>
        <el-form-item label="关键词">
          <el-input
            v-model="filters.search"
            placeholder="计划编号/名称"
            clearable
            style="width: 180px"
            @keyup.enter="handleSearch"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">
            <el-icon><Search /></el-icon>
            搜索
          </el-button>
          <el-button @click="handleReset">
            <el-icon><Refresh /></el-icon>
            重置
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 计划列表 -->
    <el-card class="table-card" shadow="never">
      <el-table
        v-loading="loading"
        :data="planList"
        stripe
        border
        style="width: 100%"
        @row-click="handleRowClick"
      >
        <el-table-column prop="plan_no" label="计划编号" width="140" />
        <el-table-column prop="title" label="计划名称" min-width="180" />
        <el-table-column prop="project_code" label="项目编号" width="130" />
        <el-table-column prop="project_name" label="项目名称" width="160" show-overflow-tooltip />
        <el-table-column label="计划日期" width="200">
          <template #default="{ row }">
            {{ row.planned_start }} ~ {{ row.planned_end }}
          </template>
        </el-table-column>
        <el-table-column prop="status_display" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ row.status_display }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="进度" width="150">
          <template #default="{ row }">
            <el-progress
              :percentage="row.progress_percent"
              :status="row.progress_percent === 100 ? 'success' : ''"
              :stroke-width="8"
            />
          </template>
        </el-table-column>
        <el-table-column prop="production_manager_name" label="生产负责人" width="100" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" size="small" link @click.stop="handleEdit(row)">
              编辑
            </el-button>
            <el-button
              v-if="row.status === 'DRAFT'"
              type="success"
              size="small"
              link
              @click.stop="handleConfirm(row)"
            >
              确认
            </el-button>
            <el-button
              v-if="row.status === 'CONFIRMED' || row.status === 'DRAFT'"
              type="warning"
              size="small"
              link
              @click.stop="handleStart(row)"
            >
              开始
            </el-button>
            <el-button
              v-if="row.status === 'IN_PROGRESS'"
              type="success"
              size="small"
              link
              @click.stop="handleComplete(row)"
            >
              完成
            </el-button>
            <el-button
              v-if="row.status === 'DRAFT'"
              type="danger"
              size="small"
              link
              @click.stop="handleDelete(row)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-container">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="pagination.total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSizeChange"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>

    <!-- 计划详情对话框 -->
    <el-drawer
      v-model="detailVisible"
      :title="currentPlan?.plan_no + ' - ' + currentPlan?.title"
      size="60%"
      direction="rtl"
    >
      <template v-if="currentPlan">
        <div class="detail-section">
          <h4>基本信息</h4>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="计划编号">{{ currentPlan.plan_no }}</el-descriptions-item>
            <el-descriptions-item label="计划名称">{{ currentPlan.title }}</el-descriptions-item>
            <el-descriptions-item label="项目编号">{{ currentPlan.project_code }}</el-descriptions-item>
            <el-descriptions-item label="项目名称">{{ currentPlan.project_name }}</el-descriptions-item>
            <el-descriptions-item label="计划日期">
              {{ currentPlan.planned_start }} ~ {{ currentPlan.planned_end }}
            </el-descriptions-item>
            <el-descriptions-item label="实际日期">
              {{ currentPlan.actual_start || '-' }} ~ {{ currentPlan.actual_end || '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="getStatusType(currentPlan.status)">
                {{ currentPlan.status_display }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="完成进度">
              <el-progress
                :percentage="currentPlan.progress_percent"
                :status="currentPlan.progress_percent === 100 ? 'success' : ''"
              />
            </el-descriptions-item>
            <el-descriptions-item label="计划员">{{ currentPlan.planner_name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="生产负责人">{{ currentPlan.production_manager_name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="说明" :span="2">{{ currentPlan.description || '-' }}</el-descriptions-item>
          </el-descriptions>
        </div>

        <div class="detail-section">
          <div class="section-header">
            <h4>计划工序</h4>
            <el-button type="primary" size="small" @click="handleAddProcess">
              <el-icon><Plus /></el-icon>
              添加工序
            </el-button>
          </div>
          <el-table :data="currentPlan.plan_processes" border stripe>
            <el-table-column prop="process_no" label="工序编号" width="100" />
            <el-table-column prop="process_name" label="工序名称" min-width="120" />
            <el-table-column prop="status_display" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="getProcessStatusType(row.status)" size="small">
                  {{ row.status_display }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="进度" width="120">
              <template #default="{ row }">
                <el-progress :percentage="row.progress_percent" :stroke-width="6" />
              </template>
            </el-table-column>
            <el-table-column label="工时(计划/实际)" width="120" align="center">
              <template #default="{ row }">
                {{ row.planned_hours }}h / {{ row.actual_hours }}h
              </template>
            </el-table-column>
            <el-table-column prop="operator_name" label="操作员" width="90" />
            <el-table-column label="操作" width="140">
              <template #default="{ row }">
                <el-button
                  v-if="row.status === 'PENDING'"
                  type="primary"
                  size="small"
                  link
                  @click="handleStartProcess(row)"
                >
                  开始
                </el-button>
                <el-button
                  v-if="row.status === 'IN_PROGRESS'"
                  type="success"
                  size="small"
                  link
                  @click="handleCompleteProcess(row)"
                >
                  完成
                </el-button>
                <el-button
                  v-if="row.status === 'IN_PROGRESS'"
                  type="warning"
                  size="small"
                  link
                  @click="handleUpdateProcessProgress(row)"
                >
                  报工
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </template>
    </el-drawer>

    <!-- 新增/编辑计划对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="700px"
      destroy-on-close
    >
      <el-form
        ref="formRef"
        :model="formData"
        :rules="formRules"
        label-width="100px"
      >
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="项目" prop="project">
              <el-select
                v-model="formData.project"
                placeholder="选择项目"
                filterable
                style="width: 100%"
              >
                <el-option
                  v-for="item in projects"
                  :key="item.id"
                  :label="`${item.code} - ${item.name}`"
                  :value="item.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="计划名称" prop="title">
              <el-input v-model="formData.title" placeholder="请输入计划名称" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="计划开始" prop="planned_start">
              <el-date-picker
                v-model="formData.planned_start"
                type="date"
                placeholder="计划开始日期"
                value-format="YYYY-MM-DD"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="计划完成" prop="planned_end">
              <el-date-picker
                v-model="formData.planned_end"
                type="date"
                placeholder="计划完成日期"
                value-format="YYYY-MM-DD"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="计划员">
              <el-select
                v-model="formData.planner"
                placeholder="选择计划员"
                clearable
                filterable
                style="width: 100%"
              >
                <el-option
                  v-for="user in users"
                  :key="user.id"
                  :label="user.full_name || user.username"
                  :value="user.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="生产负责人">
              <el-select
                v-model="formData.production_manager"
                placeholder="选择生产负责人"
                clearable
                filterable
                style="width: 100%"
              >
                <el-option
                  v-for="user in users"
                  :key="user.id"
                  :label="user.full_name || user.username"
                  :value="user.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="计划说明">
          <el-input
            v-model="formData.description"
            type="textarea"
            :rows="3"
            placeholder="请输入计划说明"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">
          保存
        </el-button>
      </template>
    </el-dialog>

    <!-- 添加工序对话框 -->
    <el-dialog
      v-model="processDialogVisible"
      title="添加工序到计划"
      width="600px"
    >
      <el-checkbox-group v-model="selectedProcessIds">
        <el-table :data="projectProcesses" border stripe>
          <el-table-column width="55" align="center">
            <template #default="{ row }">
              <el-checkbox :label="row.id" :key="row.id" />
            </template>
          </el-table-column>
          <el-table-column prop="process_no" label="工序编号" width="100" />
          <el-table-column prop="name" label="工序名称" min-width="150" />
          <el-table-column prop="process_type_display" label="类型" width="100" />
          <el-table-column prop="planned_hours" label="计划工时" width="90" />
        </el-table>
      </el-checkbox-group>
      <template #footer>
        <el-button @click="processDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleAddProcessConfirm">
          添加
        </el-button>
      </template>
    </el-dialog>

    <!-- 工序报工对话框 -->
    <el-dialog
      v-model="progressDialogVisible"
      title="工序报工"
      width="500px"
    >
      <el-form :model="progressFormData" label-width="100px">
        <el-form-item label="完成进度">
          <el-slider v-model="progressFormData.progress_percent" :marks="{ 0: '0%', 50: '50%', 100: '100%' }" />
        </el-form-item>
        <el-form-item label="实际工时">
          <el-input-number v-model="progressFormData.actual_hours" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="progressDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleProgressConfirm">
          确定
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search, Refresh } from '@element-plus/icons-vue'
import request from '@/utils/request'

// 状态
const loading = ref(false)
const saving = ref(false)
const planList = ref([])
const projects = ref([])
const users = ref([])
const projectProcesses = ref([])
const dialogVisible = ref(false)
const dialogTitle = ref('新建计划')
const detailVisible = ref(false)
const currentPlan = ref(null)
const processDialogVisible = ref(false)
const progressDialogVisible = ref(false)
const selectedProcessIds = ref([])
const currentProcessRow = ref(null)
const formRef = ref(null)

// 筛选条件
const filters = reactive({
  project: null,
  status: '',
  search: ''
})

// 分页
const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

// 表单数据
const formData = reactive({
  id: null,
  project: null,
  title: '',
  planned_start: '',
  planned_end: '',
  planner: null,
  production_manager: null,
  description: ''
})

// 报工表单数据
const progressFormData = reactive({
  progress_percent: 0,
  actual_hours: 0
})

// 表单验证
const formRules = {
  project: [{ required: true, message: '请选择项目', trigger: 'change' }],
  title: [{ required: true, message: '请输入计划名称', trigger: 'blur' }],
  planned_start: [{ required: true, message: '请选择计划开始日期', trigger: 'change' }],
  planned_end: [{ required: true, message: '请选择计划完成日期', trigger: 'change' }]
}

// 获取状态标签样式
const getStatusType = (status) => {
  const map = {
    'DRAFT': 'info',
    'CONFIRMED': 'primary',
    'IN_PROGRESS': 'warning',
    'COMPLETED': 'success',
    'CANCELLED': 'danger'
  }
  return map[status] || ''
}

const getProcessStatusType = (status) => {
  const map = {
    'PENDING': 'info',
    'IN_PROGRESS': 'warning',
    'PAUSED': '',
    'COMPLETED': 'success',
    'CANCELLED': 'danger'
  }
  return map[status] || ''
}

// 加载数据
const loadData = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
      ...filters
    }
    const res = await request.get('/production/plans/', { params })
    planList.value = res.data.results || res.data
    pagination.total = res.data.count || res.data.length
  } catch (error) {
    console.error('加载计划列表失败:', error)
  } finally {
    loading.value = false
  }
}

// 加载项目列表
const loadProjects = async () => {
  try {
    const res = await request.get('/projects/', { params: { page_size: 1000 } })
    projects.value = res.data.results || res.data
  } catch (error) {
    console.error('加载项目列表失败:', error)
  }
}

// 加载用户列表
const loadUsers = async () => {
  try {
    const res = await request.get('/auth/users/', { params: { page_size: 1000 } })
    users.value = res.data.results || res.data
  } catch (error) {
    console.error('加载用户列表失败:', error)
  }
}

// 搜索
const handleSearch = () => {
  pagination.page = 1
  loadData()
}

// 重置
const handleReset = () => {
  filters.project = null
  filters.status = ''
  filters.search = ''
  pagination.page = 1
  loadData()
}

// 分页
const handleSizeChange = (size) => {
  pagination.pageSize = size
  pagination.page = 1
  loadData()
}

const handlePageChange = (page) => {
  pagination.page = page
  loadData()
}

// 点击行查看详情
const handleRowClick = async (row) => {
  try {
    const res = await request.get(`/production/plans/${row.id}/`)
    currentPlan.value = res.data
    detailVisible.value = true
  } catch (error) {
    console.error('加载计划详情失败:', error)
  }
}

// 新增
const handleAdd = () => {
  dialogTitle.value = '新建计划'
  Object.assign(formData, {
    id: null,
    project: null,
    title: '',
    planned_start: '',
    planned_end: '',
    planner: null,
    production_manager: null,
    description: ''
  })
  dialogVisible.value = true
}

// 编辑
const handleEdit = (row) => {
  dialogTitle.value = '编辑计划'
  Object.assign(formData, {
    id: row.id,
    project: row.project,
    title: row.title,
    planned_start: row.planned_start,
    planned_end: row.planned_end,
    planner: row.planner,
    production_manager: row.production_manager,
    description: row.description
  })
  dialogVisible.value = true
}

// 删除
const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该计划吗？', '确认删除', { type: 'warning' })
    await request.delete(`/production/plans/${row.id}/`)
    ElMessage.success('删除成功')
    loadData()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除失败:', error)
    }
  }
}

// 确认计划
const handleConfirm = async (row) => {
  try {
    await request.post(`/production/plans/${row.id}/confirm/`)
    ElMessage.success('计划已确认')
    loadData()
  } catch (error) {
    console.error('确认失败:', error)
  }
}

// 开始生产
const handleStart = async (row) => {
  try {
    await request.post(`/production/plans/${row.id}/start/`)
    ElMessage.success('生产已开始')
    loadData()
  } catch (error) {
    console.error('开始失败:', error)
  }
}

// 完成生产
const handleComplete = async (row) => {
  try {
    await ElMessageBox.confirm('确定要完成该生产计划吗？', '确认完成')
    await request.post(`/production/plans/${row.id}/complete/`)
    ElMessage.success('生产已完成')
    loadData()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('完成失败:', error)
    }
  }
}

// 保存
const handleSave = async () => {
  if (!formRef.value) return
  
  try {
    await formRef.value.validate()
    saving.value = true
    
    const data = { ...formData }
    if (data.id) {
      await request.put(`/production/plans/${data.id}/`, data)
      ElMessage.success('更新成功')
    } else {
      await request.post('/production/plans/', data)
      ElMessage.success('创建成功')
    }
    
    dialogVisible.value = false
    loadData()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('保存失败:', error)
    }
  } finally {
    saving.value = false
  }
}

// 添加工序
const handleAddProcess = async () => {
  if (!currentPlan.value?.project) return
  
  try {
    const res = await request.get('/production/processes/', {
      params: { project: currentPlan.value.project, page_size: 1000 }
    })
    projectProcesses.value = res.data.results || res.data
    selectedProcessIds.value = []
    processDialogVisible.value = true
  } catch (error) {
    console.error('加载工序失败:', error)
  }
}

// 确认添加工序
const handleAddProcessConfirm = async () => {
  if (selectedProcessIds.value.length === 0) {
    ElMessage.warning('请选择工序')
    return
  }
  
  try {
    saving.value = true
    await request.post(`/production/plans/${currentPlan.value.id}/add_processes/`, {
      process_ids: selectedProcessIds.value
    })
    ElMessage.success('工序已添加')
    processDialogVisible.value = false
    
    // 刷新详情
    const res = await request.get(`/production/plans/${currentPlan.value.id}/`)
    currentPlan.value = res.data
    loadData()
  } catch (error) {
    console.error('添加工序失败:', error)
  } finally {
    saving.value = false
  }
}

// 开始工序
const handleStartProcess = async (row) => {
  try {
    await request.post(`/production/plan-processes/${row.id}/start/`)
    ElMessage.success('工序已开始')
    
    // 刷新详情
    const res = await request.get(`/production/plans/${currentPlan.value.id}/`)
    currentPlan.value = res.data
    loadData()
  } catch (error) {
    console.error('开始工序失败:', error)
  }
}

// 完成工序
const handleCompleteProcess = async (row) => {
  try {
    await request.post(`/production/plan-processes/${row.id}/complete/`)
    ElMessage.success('工序已完成')
    
    // 刷新详情
    const res = await request.get(`/production/plans/${currentPlan.value.id}/`)
    currentPlan.value = res.data
    loadData()
  } catch (error) {
    console.error('完成工序失败:', error)
  }
}

// 工序报工
const handleUpdateProcessProgress = (row) => {
  currentProcessRow.value = row
  progressFormData.progress_percent = row.progress_percent || 0
  progressFormData.actual_hours = row.actual_hours || 0
  progressDialogVisible.value = true
}

// 确认报工
const handleProgressConfirm = async () => {
  try {
    saving.value = true
    await request.post(`/production/plan-processes/${currentProcessRow.value.id}/update_progress/`, {
      progress_percent: progressFormData.progress_percent,
      actual_hours: progressFormData.actual_hours
    })
    ElMessage.success('报工成功')
    progressDialogVisible.value = false
    
    // 刷新详情
    const res = await request.get(`/production/plans/${currentPlan.value.id}/`)
    currentPlan.value = res.data
    loadData()
  } catch (error) {
    console.error('报工失败:', error)
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  loadData()
  loadProjects()
  loadUsers()
})
</script>

<style scoped>
.plan-list {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.header-left h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #303133;
}

.header-left .subtitle {
  font-size: 14px;
  color: #909399;
  margin-left: 12px;
}

.filter-card {
  margin-bottom: 20px;
}

.filter-card :deep(.el-card__body) {
  padding: 16px 20px 0;
}

.table-card :deep(.el-card__body) {
  padding: 0;
}

.pagination-container {
  display: flex;
  justify-content: flex-end;
  padding: 16px 20px;
  background: #fff;
}

.detail-section {
  margin-bottom: 24px;
}

.detail-section h4 {
  margin: 0 0 16px;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.section-header h4 {
  margin: 0;
}
</style>
