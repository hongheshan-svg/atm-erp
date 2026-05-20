<template>
  <div class="work-order-container">
    <div class="page-header">
      <h2>工单管理</h2>
      <el-button type="primary" v-permission="'projects:project:create'" @click="handleAdd">
        <el-icon><Plus /></el-icon> 新建工单
      </el-button>
    </div>
    
    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stats-row">
      <el-col :span="4">
        <el-card shadow="never" class="stat-card" @click="filterByStatus('')">
          <div class="stat-value">{{ stats.total || 0 }}</div>
          <div class="stat-label">总工单</div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="never" class="stat-card" @click="filterByStatus('PENDING')">
          <div class="stat-value stat-warning">{{ getStatusCount('PENDING') }}</div>
          <div class="stat-label">待派工</div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="never" class="stat-card" @click="filterByStatus('ASSIGNED')">
          <div class="stat-value stat-info">{{ getStatusCount('ASSIGNED') }}</div>
          <div class="stat-label">已派工</div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="never" class="stat-card" @click="filterByStatus('IN_PROGRESS')">
          <div class="stat-value stat-primary">{{ getStatusCount('IN_PROGRESS') }}</div>
          <div class="stat-label">执行中</div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="never" class="stat-card" @click="filterByStatus('COMPLETED')">
          <div class="stat-value stat-success">{{ getStatusCount('COMPLETED') }}</div>
          <div class="stat-label">已完成</div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="never" class="stat-card">
          <div class="stat-value stat-danger">{{ stats.overdue || 0 }}</div>
          <div class="stat-label">已逾期</div>
        </el-card>
      </el-col>
    </el-row>
    
    <!-- 筛选 -->
    <el-card shadow="never" class="filter-card">
      <el-form :inline="true" :model="queryParams">
        <el-form-item label="工单类型">
          <el-select v-model="queryParams.order_type" placeholder="全部" clearable>
            <el-option v-for="t in orderTypes" :key="t.value" :label="t.label" :value="t.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="queryParams.priority" placeholder="全部" clearable>
            <el-option label="低" value="LOW" />
            <el-option label="普通" value="NORMAL" />
            <el-option label="高" value="HIGH" />
            <el-option label="紧急" value="URGENT" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="queryParams.status" placeholder="全部" clearable>
            <el-option label="待派工" value="PENDING" />
            <el-option label="已派工" value="ASSIGNED" />
            <el-option label="执行中" value="IN_PROGRESS" />
            <el-option label="已完成" value="COMPLETED" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="fetchData">查询</el-button>
          <el-button @click="resetQuery">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>
    
    <!-- 工单列表 -->
    <el-card shadow="never">
      <el-table :data="tableData" v-loading="loading" border stripe>
        <el-table-column prop="order_no" label="工单编号" width="140" />
        <el-table-column prop="title" label="工单标题" min-width="200" show-overflow-tooltip />
        <el-table-column prop="order_type_display" label="类型" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="getOrderTypeTag(row.order_type)">{{ row.order_type_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="project_name" label="项目" width="120" show-overflow-tooltip />
        <el-table-column prop="priority_display" label="优先级" width="80">
          <template #default="{ row }">
            <el-tag size="small" :type="getPriorityTag(row.priority)">{{ row.priority_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="计划时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.planned_start) }} ~ {{ formatDate(row.planned_end) }}
          </template>
        </el-table-column>
        <el-table-column label="进度" width="120">
          <template #default="{ row }">
            <el-progress :percentage="row.progress" :stroke-width="10"
              :color="getProgressColor(row.progress, row.is_overdue)" />
          </template>
        </el-table-column>
        <el-table-column prop="dispatch_count" label="派工人数" width="90" align="center" />
        <el-table-column prop="status_display" label="状态" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="getStatusTag(row.status)">
              {{ row.status_display }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="handleView(row)">详情</el-button>
            <el-button type="success" link size="small" @click="handleDispatch(row)" 
              v-if="['PENDING', 'ASSIGNED'].includes(row.status)">派工</el-button>
            <el-button type="warning" link size="small" @click="handleStart(row)" 
              v-if="row.status === 'ASSIGNED'">开始</el-button>
            <el-button type="success" link size="small" @click="handleComplete(row)" 
              v-if="row.status === 'IN_PROGRESS'">完成</el-button>
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
    
    <!-- 新建/编辑工单对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="700px" destroy-on-close>
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="工单编号" prop="order_no">
              <el-input v-model="form.order_no" placeholder="自动生成" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="工单类型" prop="order_type">
              <el-select v-model="form.order_type" style="width: 100%">
                <el-option v-for="t in orderTypes" :key="t.value" :label="t.label" :value="t.value" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="工单标题" prop="title">
          <el-input v-model="form.title" placeholder="请输入工单标题" />
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="关联项目">
              <el-select v-model="form.project" placeholder="选择项目" clearable filterable style="width: 100%">
                <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="优先级" prop="priority">
              <el-select v-model="form.priority" style="width: 100%">
                <el-option label="低" value="LOW" />
                <el-option label="普通" value="NORMAL" />
                <el-option label="高" value="HIGH" />
                <el-option label="紧急" value="URGENT" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="计划开始" prop="planned_start">
              <el-date-picker v-model="form.planned_start" type="datetime" style="width: 100%" 
                value-format="YYYY-MM-DDTHH:mm:ss" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="计划结束" prop="planned_end">
              <el-date-picker v-model="form.planned_end" type="datetime" style="width: 100%" 
                value-format="YYYY-MM-DDTHH:mm:ss" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="预估工时">
              <el-input-number v-model="form.estimated_hours" :min="0" :precision="1" style="width: 100%" /> 小时
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="工作地点">
              <el-input v-model="form.location" placeholder="工作地点" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="工单描述">
          <el-input v-model="form.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="工作要求">
          <el-input v-model="form.requirements" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitLoading">保存</el-button>
      </template>
    </el-dialog>
    
    <!-- 派工对话框 -->
    <el-dialog v-model="dispatchDialogVisible" title="工单派工" width="500px">
      <el-form label-width="80px">
        <el-form-item label="工单">
          <span>{{ currentOrder?.order_no }} - {{ currentOrder?.title }}</span>
        </el-form-item>
        <el-form-item label="选择人员">
          <el-select v-model="dispatchForm.worker_ids" multiple filterable style="width: 100%" placeholder="选择执行人">
            <el-option v-for="u in users" :key="u.id" :label="u.name" :value="u.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dispatchDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmDispatch" :loading="dispatchLoading">确认派工</el-button>
      </template>
    </el-dialog>

    <!-- 工单详情 -->
    <el-dialog v-model="viewDialogVisible" title="工单详情" width="700px">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="工单编号">{{ viewDetail.order_no }}</el-descriptions-item>
        <el-descriptions-item label="项目">{{ viewDetail.project_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="类型">{{ viewDetail.order_type_display || viewDetail.order_type }}</el-descriptions-item>
        <el-descriptions-item label="优先级">{{ viewDetail.priority_display || viewDetail.priority }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ viewDetail.status_display || viewDetail.status }}</el-descriptions-item>
        <el-descriptions-item label="负责人">{{ viewDetail.assignee_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="计划开始">{{ viewDetail.planned_start || '-' }}</el-descriptions-item>
        <el-descriptions-item label="计划完成">{{ viewDetail.planned_end || '-' }}</el-descriptions-item>
        <el-descriptions-item label="实际开始">{{ viewDetail.actual_start || '-' }}</el-descriptions-item>
        <el-descriptions-item label="实际完成">{{ viewDetail.actual_end || '-' }}</el-descriptions-item>
        <el-descriptions-item label="描述" :span="2">{{ viewDetail.description || '-' }}</el-descriptions-item>
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
import { getWorkOrderList, getWorkOrder, createWorkOrder, updateWorkOrder, getWorkOrderStatistics, getWorkOrderTypes, dispatchWorkOrder, startWorkOrder, completeWorkOrder } from '@/api/projects/work-order'
import { getProjectList } from '@/api/projects/project'
import { getUsers } from '@/api/auth'

const loading = ref(false)
const viewDialogVisible = ref(false)
const viewDetail = ref({})
const submitLoading = ref(false)
const dispatchLoading = ref(false)
const tableData = ref([])
const total = ref(0)
const dialogVisible = ref(false)
const dispatchDialogVisible = ref(false)
const dialogTitle = ref('新建工单')
const isEdit = ref(false)
const formRef = ref(null)
const currentOrder = ref(null)

const projects = ref([])
const users = ref([])
const orderTypes = ref([])
const stats = ref({})

const queryParams = reactive({
  page: 1,
  page_size: 10,
  order_type: null,
  priority: null,
  status: null
})

const form = reactive({
  order_no: '',
  order_type: 'PRODUCTION',
  title: '',
  description: '',
  project: null,
  priority: 'NORMAL',
  planned_start: null,
  planned_end: null,
  estimated_hours: 0,
  location: '',
  requirements: ''
})

const dispatchForm = reactive({
  worker_ids: []
})

const rules = {
  order_no: [{ required: true, message: '请输入工单编号', trigger: 'blur' }],
  order_type: [{ required: true, message: '请选择工单类型', trigger: 'change' }],
  title: [{ required: true, message: '请输入工单标题', trigger: 'blur' }],
  priority: [{ required: true, message: '请选择优先级', trigger: 'change' }],
  planned_start: [{ required: true, message: '请选择计划开始时间', trigger: 'change' }],
  planned_end: [{ required: true, message: '请选择计划结束时间', trigger: 'change' }]
}

const fetchData = async () => {
  loading.value = true
  try {
    const data = await getWorkOrderList(queryParams)
    tableData.value = data.results || data
    total.value = data.count || data.length
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const fetchStats = async () => {
  try {
    const data = await getWorkOrderStatistics()
    stats.value = data
  } catch (e) {
    console.error(e)
  }
}

const fetchProjects = async () => {
  try {
    const data = await getProjectList({ page_size: 500 })
    projects.value = data.results || data
  } catch (e) {
    console.error(e)
  }
}

const fetchUsers = async () => {
  try {
    const data = await getUsers({ page_size: 200 })
    users.value = (data.results || data).map(u => ({
      id: u.id,
      name: u.first_name || u.last_name || u.username
    }))
  } catch (e) {
    console.error(e)
  }
}

const fetchOrderTypes = async () => {
  try {
    const data = await getWorkOrderTypes()
    orderTypes.value = data
  } catch (e) {
    orderTypes.value = [
      { value: 'PRODUCTION', label: '生产工单' },
      { value: 'ASSEMBLY', label: '装配工单' },
      { value: 'DEBUG', label: '调试工单' },
      { value: 'REPAIR', label: '维修工单' },
      { value: 'INSTALLATION', label: '安装工单' },
      { value: 'MAINTENANCE', label: '保养工单' }
    ]
  }
}

const getStatusCount = (status) => {
  const item = (stats.value.by_status || []).find(s => s.status === status)
  return item?.count || 0
}

const resetQuery = () => {
  queryParams.order_type = null
  queryParams.priority = null
  queryParams.status = null
  queryParams.page = 1
  fetchData()
}

const filterByStatus = (status) => {
  queryParams.status = status || null
  fetchData()
}

const handleAdd = () => {
  isEdit.value = false
  dialogTitle.value = '新建工单'
  Object.assign(form, {
    order_no: `WO-${new Date().toISOString().slice(0,10).replace(/-/g,'')}-${String(Date.now()).slice(-4)}`,
    order_type: 'PRODUCTION',
    title: '',
    description: '',
    project: null,
    priority: 'NORMAL',
    planned_start: null,
    planned_end: null,
    estimated_hours: 0,
    location: '',
    requirements: '',
    status: 'PENDING'
  })
  dialogVisible.value = true
}

const handleView = async (row) => {
  try {
    const res = await getWorkOrder(row.id)
    viewDetail.value = res.data || res
  } catch (error) {
    console.error(error)
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
      await updateWorkOrder(form.id, form)
      ElMessage.success('修改成功')
    } else {
      await createWorkOrder(form)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchData()
    fetchStats()
  } catch (e) {
    console.error(e)
    ElMessage.error('操作失败')
  } finally {
    submitLoading.value = false
  }
}

const handleDispatch = (row) => {
  currentOrder.value = row
  dispatchForm.worker_ids = []
  dispatchDialogVisible.value = true
}

const confirmDispatch = async () => {
  if (dispatchForm.worker_ids.length === 0) {
    ElMessage.warning('请选择执行人')
    return
  }
  
  dispatchLoading.value = true
  try {
    await dispatchWorkOrder(currentOrder.value.id, {
      worker_ids: dispatchForm.worker_ids
    })
    ElMessage.success('派工成功')
    dispatchDialogVisible.value = false
    fetchData()
  } catch (e) {
    ElMessage.error('派工失败')
  } finally {
    dispatchLoading.value = false
  }
}

const handleStart = (row) => {
  ElMessageBox.confirm('确定要开始执行此工单吗？', '提示', { type: 'warning' })
    .then(async () => {
      await startWorkOrder(row.id)
      ElMessage.success('工单已开始')
      fetchData()
      fetchStats()
    })
}

const handleComplete = (row) => {
  ElMessageBox.confirm('确定要完成此工单吗？', '提示', { type: 'warning' })
    .then(async () => {
      await completeWorkOrder(row.id)
      ElMessage.success('工单已完成')
      fetchData()
      fetchStats()
    })
}

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleDateString('zh-CN')
}

const getOrderTypeTag = (type) => {
  const tags = { PRODUCTION: 'primary', ASSEMBLY: '', DEBUG: 'success', REPAIR: 'danger', INSTALLATION: 'warning' }
  return tags[type] || 'info'
}

const getPriorityTag = (priority) => {
  const tags = { LOW: 'info', NORMAL: '', HIGH: 'warning', URGENT: 'danger' }
  return tags[priority] || ''
}

const getStatusTag = (status) => {
  const tags = { DRAFT: 'info', PENDING: 'warning', ASSIGNED: '', IN_PROGRESS: 'primary', COMPLETED: 'success', CANCELLED: 'info' }
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
  fetchStats()
  fetchProjects()
  fetchUsers()
  fetchOrderTypes()
})
</script>

<style scoped>
.work-order-container {
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
.stat-warning { color: #e6a23c; }
.stat-primary { color: #409eff; }
.stat-success { color: #67c23a; }
.stat-danger { color: #f56c6c; }

.filter-card {
  margin-bottom: 16px;
}

.pagination {
  margin-top: 16px;
  justify-content: flex-end;
}
</style>
