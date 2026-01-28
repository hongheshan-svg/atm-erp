<template>
  <div class="service-request-list">
    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stat-row">
      <el-col :span="5">
        <el-card class="stat-card">
          <el-statistic title="新请求" :value="stats.new" />
        </el-card>
      </el-col>
      <el-col :span="5">
        <el-card class="stat-card">
          <el-statistic title="处理中" :value="stats.inProgress" />
        </el-card>
      </el-col>
      <el-col :span="5">
        <el-card class="stat-card warning">
          <el-statistic title="等待配件" :value="stats.waitingParts" value-style="color: #E6A23C" />
        </el-card>
      </el-col>
      <el-col :span="5">
        <el-card class="stat-card danger">
          <el-statistic title="即将超时" :value="stats.nearSLA" value-style="color: #F56C6C" />
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card class="stat-card">
          <el-statistic title="今日完成" :value="stats.completedToday" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 服务请求列表 -->
    <el-card>
      <template #header>
        <div class="card-header">
          <span>服务请求管理</span>
          <div class="header-actions">
            <el-input v-model="searchKeyword" placeholder="搜索请求" clearable style="width: 180px; margin-right: 12px"
                      @keyup.enter="loadRequests">
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
            <el-select v-model="statusFilter" placeholder="状态" clearable style="width: 120px; margin-right: 12px"
                       @change="loadRequests">
              <el-option label="新请求" value="NEW" />
              <el-option label="已分配" value="ASSIGNED" />
              <el-option label="处理中" value="IN_PROGRESS" />
              <el-option label="等待配件" value="WAITING_PARTS" />
              <el-option label="待确认" value="PENDING_APPROVAL" />
              <el-option label="已完成" value="COMPLETED" />
              <el-option label="已取消" value="CANCELLED" />
            </el-select>
            <el-select v-model="priorityFilter" placeholder="优先级" clearable style="width: 100px; margin-right: 12px"
                       @change="loadRequests">
              <el-option label="紧急" value="URGENT" />
              <el-option label="高" value="HIGH" />
              <el-option label="中" value="MEDIUM" />
              <el-option label="低" value="LOW" />
            </el-select>
            <el-button type="primary" @click="showCreateDialog = true">
              <el-icon><Plus /></el-icon>创建请求
            </el-button>
          </div>
        </div>
      </template>

      <el-table :data="requests" v-loading="loading" stripe @row-click="viewRequest">
        <el-table-column prop="request_no" label="请求编号" width="140" />
        <el-table-column prop="title" label="标题" min-width="180" show-overflow-tooltip />
        <el-table-column prop="customer_name" label="客户" width="150" show-overflow-tooltip />
        <el-table-column label="类型" width="100">
          <template #default="{ row }">
            <el-tag size="small">{{ row.request_type_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="优先级" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="getPriorityType(row.priority)" size="small">{{ row.priority_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="assigned_to_name" label="负责人" width="100" />
        <el-table-column label="SLA状态" width="100" align="center">
          <template #default="{ row }">
            <span :class="getSLAClass(row)">
              {{ row.sla_status || '-' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="160">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click.stop="viewRequest(row)">详情</el-button>
            <el-button size="small" link v-if="row.status === 'NEW'" @click.stop="assignRequest(row)">分配</el-button>
            <el-button size="small" link v-if="row.status === 'IN_PROGRESS'" @click.stop="completeRequest(row)">完成</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        @size-change="loadRequests"
        @current-change="loadRequests"
        style="margin-top: 16px; justify-content: flex-end"
      />
    </el-card>

    <!-- 创建请求对话框 -->
    <el-dialog v-model="showCreateDialog" title="创建服务请求" width="600px">
      <el-form :model="requestForm" :rules="requestRules" ref="requestFormRef" label-width="100px">
        <el-form-item label="客户" prop="customer">
          <el-select v-model="requestForm.customer" filterable placeholder="选择客户" style="width: 100%"
                     @change="loadContractsForCustomer">
            <el-option v-for="c in customers" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="服务合同">
          <el-select v-model="requestForm.contract" filterable clearable placeholder="选择合同" style="width: 100%">
            <el-option v-for="c in customerContracts" :key="c.id" :label="c.title" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="请求标题" prop="title">
          <el-input v-model="requestForm.title" placeholder="简要描述问题" />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="请求类型" prop="request_type">
              <el-select v-model="requestForm.request_type" style="width: 100%">
                <el-option label="故障报修" value="BREAKDOWN" />
                <el-option label="技术咨询" value="CONSULTATION" />
                <el-option label="安装调试" value="INSTALLATION" />
                <el-option label="保养维护" value="MAINTENANCE" />
                <el-option label="备件更换" value="PARTS_REPLACEMENT" />
                <el-option label="其他" value="OTHER" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="优先级" prop="priority">
              <el-select v-model="requestForm.priority" style="width: 100%">
                <el-option label="紧急" value="URGENT" />
                <el-option label="高" value="HIGH" />
                <el-option label="中" value="MEDIUM" />
                <el-option label="低" value="LOW" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="问题描述" prop="description">
          <el-input v-model="requestForm.description" type="textarea" :rows="4" placeholder="详细描述问题" />
        </el-form-item>
        <el-form-item label="联系人">
          <el-input v-model="requestForm.contact_person" placeholder="联系人姓名" />
        </el-form-item>
        <el-form-item label="联系电话">
          <el-input v-model="requestForm.contact_phone" placeholder="联系电话" />
        </el-form-item>
        <el-form-item label="设备信息">
          <el-input v-model="requestForm.equipment_info" placeholder="设备型号/序列号" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="createRequest" :loading="submitting">创建</el-button>
      </template>
    </el-dialog>

    <!-- 请求详情抽屉 -->
    <el-drawer v-model="showDetailDrawer" title="服务请求详情" size="50%">
      <template v-if="currentRequest">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="请求编号">{{ currentRequest.request_no }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getStatusType(currentRequest.status)">{{ currentRequest.status_display }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="标题" :span="2">{{ currentRequest.title }}</el-descriptions-item>
          <el-descriptions-item label="客户">{{ currentRequest.customer_name }}</el-descriptions-item>
          <el-descriptions-item label="合同">{{ currentRequest.contract_title || '-' }}</el-descriptions-item>
          <el-descriptions-item label="类型">{{ currentRequest.request_type_display }}</el-descriptions-item>
          <el-descriptions-item label="优先级">
            <el-tag :type="getPriorityType(currentRequest.priority)">{{ currentRequest.priority_display }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="问题描述" :span="2">{{ currentRequest.description }}</el-descriptions-item>
          <el-descriptions-item label="负责人">{{ currentRequest.assigned_to_name || '未分配' }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatDate(currentRequest.created_at) }}</el-descriptions-item>
        </el-descriptions>

        <el-divider>服务活动</el-divider>
        <el-timeline>
          <el-timeline-item v-for="act in currentRequest.activities" :key="act.id" 
                            :timestamp="formatDate(act.activity_time)" placement="top">
            <el-card shadow="hover">
              <h4>{{ act.activity_type_display }}</h4>
              <p>{{ act.description }}</p>
              <p class="text-muted">操作人: {{ act.performed_by_name }}</p>
              <p v-if="act.duration_hours" class="text-muted">用时: {{ act.duration_hours }}小时</p>
            </el-card>
          </el-timeline-item>
        </el-timeline>
      </template>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Plus } from '@element-plus/icons-vue'
import request from '@/utils/request'

const loading = ref(false)
const submitting = ref(false)
const showCreateDialog = ref(false)
const showDetailDrawer = ref(false)

const requests = ref([])
const customers = ref([])
const customerContracts = ref([])
const currentRequest = ref(null)

const searchKeyword = ref('')
const statusFilter = ref('')
const priorityFilter = ref('')

const stats = ref({
  new: 0,
  inProgress: 0,
  waitingParts: 0,
  nearSLA: 0,
  completedToday: 0
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const requestForm = reactive({
  customer: null,
  contract: null,
  title: '',
  request_type: 'BREAKDOWN',
  priority: 'MEDIUM',
  description: '',
  contact_person: '',
  contact_phone: '',
  equipment_info: ''
})

const requestRules = {
  customer: [{ required: true, message: '请选择客户', trigger: 'change' }],
  title: [{ required: true, message: '请输入请求标题', trigger: 'blur' }],
  request_type: [{ required: true, message: '请选择请求类型', trigger: 'change' }],
  priority: [{ required: true, message: '请选择优先级', trigger: 'change' }],
  description: [{ required: true, message: '请描述问题', trigger: 'blur' }]
}

const requestFormRef = ref(null)

const formatDate = (date) => {
  if (!date) return '-'
  return new Date(date).toLocaleString('zh-CN')
}

const getStatusType = (status) => {
  const map = {
    NEW: 'info', ASSIGNED: 'warning', IN_PROGRESS: 'primary',
    WAITING_PARTS: 'warning', PENDING_APPROVAL: 'warning',
    COMPLETED: 'success', CANCELLED: 'danger'
  }
  return map[status] || 'info'
}

const getPriorityType = (priority) => {
  const map = { URGENT: 'danger', HIGH: 'warning', MEDIUM: '', LOW: 'info' }
  return map[priority] || ''
}

const getSLAClass = (row) => {
  if (!row.sla_status) return ''
  if (row.sla_status === 'OK') return 'sla-ok'
  if (row.sla_status === 'WARNING') return 'sla-warning'
  return 'sla-breach'
}

const loadRequests = async () => {
  loading.value = true
  try {
    const params = { page: pagination.page, page_size: pagination.pageSize }
    if (searchKeyword.value) params.search = searchKeyword.value
    if (statusFilter.value) params.status = statusFilter.value
    if (priorityFilter.value) params.priority = priorityFilter.value

    const res = await request.get('/sales/service-requests/', { params })
    requests.value = res.results || res
    pagination.total = res.count || requests.value.length
  } catch (e) {
    ElMessage.error('加载服务请求失败')
  } finally {
    loading.value = false
  }
}

const loadStats = async () => {
  try {
    const [newRes, inProgressRes, waitingRes] = await Promise.all([
      request.get('/sales/service-requests/', { params: { status: 'NEW', page_size: 1 } }),
      request.get('/sales/service-requests/', { params: { status: 'IN_PROGRESS', page_size: 1 } }),
      request.get('/sales/service-requests/', { params: { status: 'WAITING_PARTS', page_size: 1 } })
    ])
    stats.value.new = newRes.count || 0
    stats.value.inProgress = inProgressRes.count || 0
    stats.value.waitingParts = waitingRes.count || 0
  } catch (e) {
    console.error('加载统计数据失败')
  }
}

const loadCustomers = async () => {
  try {
    const res = await request.get('/masterdata/customers/', { params: { page_size: 1000 } })
    customers.value = res.results || res
  } catch (e) {
    console.error('加载客户列表失败')
  }
}

const loadContractsForCustomer = async (customerId) => {
  if (!customerId) {
    customerContracts.value = []
    return
  }
  try {
    const res = await request.get('/sales/service-contracts/', { params: { customer: customerId, status: 'ACTIVE' } })
    customerContracts.value = res.results || res
  } catch (e) {
    console.error('加载合同列表失败')
  }
}

const createRequest = async () => {
  try {
    await requestFormRef.value.validate()
    submitting.value = true
    await request.post('/sales/service-requests/', requestForm)
    ElMessage.success('服务请求创建成功')
    showCreateDialog.value = false
    loadRequests()
    loadStats()
  } catch (e) {
    if (e !== false) ElMessage.error('创建失败')
  } finally {
    submitting.value = false
  }
}

const viewRequest = async (row) => {
  try {
    const res = await request.get(`/api/sales/service-requests/${row.id}/`)
    currentRequest.value = res
    showDetailDrawer.value = true
  } catch (e) {
    ElMessage.error('加载请求详情失败')
  }
}

const assignRequest = async (row) => {
  ElMessageBox.prompt('请输入负责人ID', '分配任务').then(async ({ value }) => {
    await request.post(`/api/sales/service-requests/${row.id}/assign/`, { assigned_to: parseInt(value) })
    ElMessage.success('分配成功')
    loadRequests()
  })
}

const completeRequest = async (row) => {
  ElMessageBox.prompt('请输入处理结果', '完成请求').then(async ({ value }) => {
    await request.post(`/api/sales/service-requests/${row.id}/complete/`, { resolution: value })
    ElMessage.success('请求已完成')
    loadRequests()
  })
}

onMounted(() => {
  loadRequests()
  loadStats()
  loadCustomers()
})
</script>

<style scoped>
.service-request-list {
  padding: 20px;
}
.stat-row {
  margin-bottom: 16px;
}
.stat-card {
  text-align: center;
}
.stat-card.warning {
  border-left: 3px solid #E6A23C;
}
.stat-card.danger {
  border-left: 3px solid #F56C6C;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.header-actions {
  display: flex;
  align-items: center;
}
.sla-ok {
  color: #67C23A;
}
.sla-warning {
  color: #E6A23C;
}
.sla-breach {
  color: #F56C6C;
  font-weight: bold;
}
.text-muted {
  color: #909399;
  font-size: 12px;
}
</style>
