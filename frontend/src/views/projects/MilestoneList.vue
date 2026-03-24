<template>
  <div class="milestone-container">
    <div class="page-header">
      <h2>项目里程碑</h2>
      <div class="header-actions">
        <el-button @click="handleInitTemplate">从模板初始化</el-button>
        <el-button type="primary" @click="handleAdd">
          <el-icon><Plus /></el-icon> 新增里程碑
        </el-button>
      </div>
    </div>
    
    <!-- 筛选条件 -->
    <el-card shadow="never" class="filter-card">
      <el-form :inline="true" :model="queryParams">
        <el-form-item label="项目">
          <el-select v-model="queryParams.project" placeholder="选择项目" clearable filterable style="width: 200px">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="queryParams.milestone_type" placeholder="全部" clearable>
            <el-option v-for="t in milestoneTypes" :key="t.value" :label="t.label" :value="t.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="queryParams.status" placeholder="全部" clearable>
            <el-option label="待开始" value="PENDING" />
            <el-option label="进行中" value="IN_PROGRESS" />
            <el-option label="已完成" value="COMPLETED" />
            <el-option label="已延期" value="DELAYED" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="fetchData">查询</el-button>
          <el-button @click="resetQuery">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>
    
    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stats-row">
      <el-col :span="4">
        <el-card shadow="never" class="stat-card" @click="filterByStatus('')">
          <div class="stat-value">{{ stats.total || 0 }}</div>
          <div class="stat-label">总计</div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="never" class="stat-card" @click="filterByStatus('PENDING')">
          <div class="stat-value stat-info">{{ stats.pending || 0 }}</div>
          <div class="stat-label">待开始</div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="never" class="stat-card" @click="filterByStatus('IN_PROGRESS')">
          <div class="stat-value stat-primary">{{ stats.in_progress || 0 }}</div>
          <div class="stat-label">进行中</div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="never" class="stat-card" @click="filterByStatus('COMPLETED')">
          <div class="stat-value stat-success">{{ stats.completed || 0 }}</div>
          <div class="stat-label">已完成</div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="never" class="stat-card">
          <div class="stat-value stat-warning">{{ stats.overdue || 0 }}</div>
          <div class="stat-label">已逾期</div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="never" class="stat-card">
          <div class="stat-value stat-danger">{{ stats.upcoming_7 || 0 }}</div>
          <div class="stat-label">7天内到期</div>
        </el-card>
      </el-col>
    </el-row>
    
    <!-- 里程碑列表 -->
    <el-card shadow="never">
      <el-table :data="tableData" v-loading="loading" border stripe>
        <el-table-column prop="project_name" label="项目" width="150" show-overflow-tooltip />
        <el-table-column prop="code" label="编码" width="80" />
        <el-table-column prop="name" label="里程碑" min-width="150">
          <template #default="{ row }">
            <el-tag size="small" :type="getMilestoneTypeTag(row.milestone_type)" style="margin-right: 8px">
              {{ row.milestone_type_display }}
            </el-tag>
            <span>{{ row.name }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="planned_date" label="计划日期" width="110" />
        <el-table-column prop="actual_date" label="实际日期" width="110">
          <template #default="{ row }">
            <span :class="{ 'text-danger': row.actual_date && row.actual_date > row.planned_date }">
              {{ row.actual_date || '-' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="剩余/延期" width="100" align="center">
          <template #default="{ row }">
            <span v-if="row.status === 'COMPLETED'" class="text-success">已完成</span>
            <span v-else-if="row.is_overdue" class="text-danger">逾期{{ -row.days_remaining }}天</span>
            <span v-else>{{ row.days_remaining }}天</span>
          </template>
        </el-table-column>
        <el-table-column label="进度" width="140">
          <template #default="{ row }">
            <el-progress :percentage="row.progress" :stroke-width="10"
              :color="getProgressColor(row.progress, row.is_overdue)" />
          </template>
        </el-table-column>
        <el-table-column prop="owner_name" label="负责人" width="90" />
        <el-table-column prop="status_display" label="状态" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="getStatusTag(row.status)">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="handleView(row)">详情</el-button>
            <el-button type="success" link size="small" @click="handleUpdateProgress(row)" 
              v-if="row.status !== 'COMPLETED'">更新进度</el-button>
            <el-button type="warning" link size="small" @click="handleComplete(row)" 
              v-if="row.status !== 'COMPLETED' && row.progress >= 80">完成</el-button>
            <el-button type="primary" link size="small" @click="handleEdit(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <el-pagination
        class="pagination"
        v-model:current-page="queryParams.page"
        v-model:page-size="queryParams.page_size"
        :page-sizes="[10, 20, 50]"
        :total="total"
        layout="total, sizes, prev, pager, next"
        @size-change="fetchData"
        @current-change="fetchData"
      />
    </el-card>
    
    <!-- 新增/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="700px" destroy-on-close>
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="项目" prop="project">
              <el-select v-model="form.project" placeholder="选择项目" filterable style="width: 100%">
                <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="里程碑类型" prop="milestone_type">
              <el-select v-model="form.milestone_type" style="width: 100%">
                <el-option v-for="t in milestoneTypes" :key="t.value" :label="t.label" :value="t.value" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="编码" prop="code">
              <el-input v-model="form.code" placeholder="如 M01" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="名称" prop="name">
              <el-input v-model="form.name" placeholder="里程碑名称" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="计划日期" prop="planned_date">
              <el-date-picker v-model="form.planned_date" type="date" style="width: 100%" value-format="YYYY-MM-DD" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="负责人">
              <el-select v-model="form.owner" placeholder="选择负责人" filterable clearable style="width: 100%">
                <el-option v-for="u in users" :key="u.id" :label="u.name" :value="u.id" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="权重(%)">
              <el-input-number v-model="form.weight" :min="0" :max="100" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="关联付款">
              <el-switch v-model="form.payment_linked" />
              <el-input-number v-if="form.payment_linked" v-model="form.payment_percentage" 
                :min="0" :max="100" style="width: 100px; margin-left: 10px" /> %
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="交付物说明">
          <el-input v-model="form.deliverables" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitLoading">保存</el-button>
      </template>
    </el-dialog>
    
    <!-- 更新进度对话框 -->
    <el-dialog v-model="progressDialogVisible" title="更新进度" width="400px">
      <el-form label-width="80px">
        <el-form-item label="当前进度">
          <el-slider v-model="progressForm.progress" :step="5" show-stops />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="progressForm.comment" type="textarea" :rows="3" placeholder="进展说明" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="progressDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmProgress" :loading="progressLoading">确定</el-button>
      </template>
    </el-dialog>
    
    <!-- 初始化模板对话框 -->
    <el-dialog v-model="initDialogVisible" title="从模板初始化里程碑" width="400px">
      <el-form label-width="80px">
        <el-form-item label="项目">
          <el-select v-model="initForm.project_id" placeholder="选择项目" filterable style="width: 100%">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="开始日期">
          <el-date-picker v-model="initForm.start_date" type="date" style="width: 100%" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="模板">
          <el-select v-model="initForm.template" style="width: 100%">
            <el-option label="标准模板" value="standard" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="initDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmInit" :loading="initLoading">初始化</el-button>
      </template>
    </el-dialog>

    <!-- 里程碑详情 -->
    <el-dialog v-model="viewDialogVisible" title="里程碑详情" width="700px">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="名称">{{ viewDetail.name }}</el-descriptions-item>
        <el-descriptions-item label="项目">{{ viewDetail.project_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="计划日期">{{ viewDetail.planned_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="实际日期">{{ viewDetail.actual_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ viewDetail.status_display || viewDetail.status }}</el-descriptions-item>
        <el-descriptions-item label="负责人">{{ viewDetail.owner_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="完成率">{{ viewDetail.progress || 0 }}%</el-descriptions-item>
        <el-descriptions-item label="权重">{{ viewDetail.weight || '-' }}</el-descriptions-item>
        <el-descriptions-item label="描述" :span="2">{{ viewDetail.description || '-' }}</el-descriptions-item>
        <el-descriptions-item label="验收标准" :span="2">{{ viewDetail.acceptance_criteria || '-' }}</el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button @click="viewDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import request from '@/utils/request'
import { usePermissionStore } from '@/stores/permission'

const loading = ref(false)
const viewDialogVisible = ref(false)
const viewDetail = ref({})
const submitLoading = ref(false)
const progressLoading = ref(false)
const initLoading = ref(false)
const tableData = ref([])
const total = ref(0)
const dialogVisible = ref(false)
const dialogTitle = ref('新增里程碑')
const progressDialogVisible = ref(false)
const initDialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref(null)
const currentMilestone = ref(null)

const projects = ref([])
const users = ref([])
const milestoneTypes = ref([])
const usersLoaded = ref(false)
const permissionStore = usePermissionStore()

const queryParams = reactive({
  page: 1,
  page_size: 10,
  project: null,
  milestone_type: null,
  status: null
})

const form = reactive({
  project: null,
  milestone_type: 'CUSTOM',
  code: '',
  name: '',
  planned_date: null,
  owner: null,
  weight: 10,
  payment_linked: false,
  payment_percentage: 0,
  deliverables: '',
  description: ''
})

const progressForm = reactive({
  progress: 0,
  comment: ''
})

const initForm = reactive({
  project_id: null,
  start_date: new Date().toISOString().split('T')[0],
  template: 'standard'
})

const rules = {
  project: [{ required: true, message: '请选择项目', trigger: 'change' }],
  code: [{ required: true, message: '请输入编码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  planned_date: [{ required: true, message: '请选择计划日期', trigger: 'change' }]
}

const stats = computed(() => {
  const data = tableData.value
  return {
    total: total.value,
    pending: data.filter(d => d.status === 'PENDING').length,
    in_progress: data.filter(d => d.status === 'IN_PROGRESS').length,
    completed: data.filter(d => d.status === 'COMPLETED').length,
    overdue: data.filter(d => d.is_overdue).length,
    upcoming_7: data.filter(d => d.days_remaining > 0 && d.days_remaining <= 7).length
  }
})

const fetchData = async () => {
  loading.value = true
  try {
    const data = await request.get('/projects/milestones/', { params: queryParams })
    tableData.value = data.results || data
    total.value = data.count || data.length
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const fetchProjects = async () => {
  try {
    const data = await request.get('/projects/projects/', { params: { page_size: 500 } })
    projects.value = data.results || data
  } catch (e) {
    console.error(e)
  }
}

const fetchUsers = async () => {
  if (usersLoaded.value) {
    return true
  }

  try {
    const data = await request.get('/accounts/users/', { params: { page_size: 200 } })
    users.value = (data.results || data).map(u => ({
      id: u.id,
      name: u.first_name || u.last_name || u.username
    }))
    usersLoaded.value = true
    return true
  } catch (e) {
    if (e?.response?.status !== 403) {
      console.error(e)
    }
    users.value = []
    return false
  }
}

const ensureUsersLoaded = async () => {
  if (!permissionStore.hasPermission('system:users')) {
    users.value = []
    usersLoaded.value = false
    return false
  }

  return fetchUsers()
}

const fetchMilestoneTypes = async () => {
  try {
    const data = await request.get('/projects/milestones/milestone_types/')
    milestoneTypes.value = data
  } catch (e) {
    milestoneTypes.value = [
      { value: 'KICKOFF', label: '项目启动' },
      { value: 'DESIGN', label: '设计评审' },
      { value: 'PROCUREMENT', label: '采购完成' },
      { value: 'ASSEMBLY', label: '组装完成' },
      { value: 'DEBUGGING', label: '调试完成' },
      { value: 'FAT', label: '厂内验收' },
      { value: 'SHIPMENT', label: '设备发货' },
      { value: 'SAT', label: '现场验收' },
      { value: 'CUSTOM', label: '自定义' }
    ]
  }
}

const resetQuery = () => {
  queryParams.project = null
  queryParams.milestone_type = null
  queryParams.status = null
  queryParams.page = 1
  fetchData()
}

const filterByStatus = (status) => {
  queryParams.status = status || null
  fetchData()
}

const handleAdd = async () => {
  await ensureUsersLoaded()
  isEdit.value = false
  dialogTitle.value = '新增里程碑'
  Object.assign(form, {
    project: queryParams.project || null,
    milestone_type: 'CUSTOM',
    code: '',
    name: '',
    planned_date: null,
    owner: null,
    weight: 10,
    payment_linked: false,
    payment_percentage: 0,
    deliverables: '',
    description: ''
  })
  dialogVisible.value = true
}

const handleEdit = async (row) => {
  await ensureUsersLoaded()
  isEdit.value = true
  dialogTitle.value = '编辑里程碑'
  Object.assign(form, row)
  dialogVisible.value = true
}

const handleView = async (row) => {
  try {
    const res = await request.get(`/projects/milestones/${row.id}/`)
    viewDetail.value = res.data || res
  } catch {
    viewDetail.value = row
  }
  viewDialogVisible.value = true
}

const handleSubmit = async () => {
  const valid = await formRef.value?.validate()
  if (!valid) return
  
  submitLoading.value = true
  try {
    if (isEdit.value) {
      await request.put(`/projects/milestones/${form.id}/`, form)
      ElMessage.success('修改成功')
    } else {
      await request.post('/projects/milestones/', form)
      ElMessage.success('新增成功')
    }
    dialogVisible.value = false
    fetchData()
  } catch (e) {
    console.error(e)
    ElMessage.error('操作失败')
  } finally {
    submitLoading.value = false
  }
}

const handleUpdateProgress = (row) => {
  currentMilestone.value = row
  progressForm.progress = row.progress
  progressForm.comment = ''
  progressDialogVisible.value = true
}

const confirmProgress = async () => {
  progressLoading.value = true
  try {
    await request.post(`/projects/milestones/${currentMilestone.value.id}/update_progress/`, {
      progress: progressForm.progress
    })
    
    if (progressForm.comment) {
      await request.post(`/projects/milestones/${currentMilestone.value.id}/add_comment/`, {
        content: progressForm.comment,
        comment_type: 'PROGRESS'
      })
    }
    
    ElMessage.success('进度已更新')
    progressDialogVisible.value = false
    fetchData()
  } catch (e) {
    ElMessage.error('更新失败')
  } finally {
    progressLoading.value = false
  }
}

const handleComplete = (row) => {
  ElMessageBox.confirm('确定要完成此里程碑吗？', '提示', { type: 'warning' })
    .then(async () => {
      await request.post(`/projects/milestones/${row.id}/complete/`)
      ElMessage.success('里程碑已完成')
      fetchData()
    })
}

const handleInitTemplate = () => {
  initForm.project_id = queryParams.project || null
  initForm.start_date = new Date().toISOString().split('T')[0]
  initDialogVisible.value = true
}

const confirmInit = async () => {
  if (!initForm.project_id) {
    ElMessage.warning('请选择项目')
    return
  }
  
  initLoading.value = true
  try {
    const data = await request.post('/projects/milestones/init_template/', initForm)
    ElMessage.success(`成功创建${data.created}个里程碑`)
    initDialogVisible.value = false
    queryParams.project = initForm.project_id
    fetchData()
  } catch (e) {
    ElMessage.error('初始化失败')
  } finally {
    initLoading.value = false
  }
}

const getMilestoneTypeTag = (type) => {
  const tags = {
    KICKOFF: 'primary',
    DESIGN: 'info',
    PROCUREMENT: 'warning',
    ASSEMBLY: '',
    DEBUGGING: 'success',
    FAT: 'danger',
    SHIPMENT: 'warning',
    SAT: 'success'
  }
  return tags[type] || 'info'
}

const getStatusTag = (status) => {
  const tags = {
    PENDING: 'info',
    IN_PROGRESS: 'primary',
    COMPLETED: 'success',
    DELAYED: 'danger',
    CANCELLED: ''
  }
  return tags[status] || ''
}

const getProgressColor = (progress, isOverdue) => {
  if (isOverdue) return '#f56c6c'
  if (progress >= 80) return '#67c23a'
  if (progress >= 50) return '#409eff'
  return '#909399'
}

onMounted(() => {
  fetchData()
  fetchProjects()
  fetchMilestoneTypes()
})
</script>

<style scoped>
.milestone-container {
  padding: 0;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.page-header h2 {
  margin: 0;
  font-size: 20px;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.filter-card {
  margin-bottom: 16px;
}

.stats-row {
  margin-bottom: 16px;
}

.stat-card {
  text-align: center;
  padding: 12px 0;
  cursor: pointer;
  transition: box-shadow 0.3s;
}

.stat-card:hover {
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}

.stat-value {
  font-size: 24px;
  font-weight: bold;
  color: #303133;
}

.stat-label {
  font-size: 13px;
  color: #909399;
  margin-top: 4px;
}

.stat-info { color: #909399; }
.stat-primary { color: #409eff; }
.stat-success { color: #67c23a; }
.stat-warning { color: #e6a23c; }
.stat-danger { color: #f56c6c; }

.pagination {
  margin-top: 16px;
  justify-content: flex-end;
}

.text-success { color: #67c23a; }
.text-danger { color: #f56c6c; }
</style>
