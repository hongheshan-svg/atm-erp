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
              <el-option label="新建" value="NEW" />
              <el-option label="已确认" value="ACKNOWLEDGED" />
              <el-option label="已派单" value="ASSIGNED" />
              <el-option label="处理中" value="IN_PROGRESS" />
              <el-option label="等待备件" value="PENDING_PARTS" />
              <el-option label="已解决" value="RESOLVED" />
              <el-option label="已关闭" value="CLOSED" />
            </el-select>
            <el-select v-model="priorityFilter" placeholder="优先级" clearable style="width: 100px; margin-right: 12px"
                       @change="loadRequests">
              <el-option label="紧急" value="CRITICAL" />
              <el-option label="高" value="HIGH" />
              <el-option label="中" value="MEDIUM" />
              <el-option label="低" value="LOW" />
            </el-select>
            <el-button type="primary" v-permission="'sales:service_request:create'" @click="showCreateDialog = true">
              <el-icon><Plus /></el-icon>创建请求
            </el-button>
          </div>
        </div>
      </template>

      <!-- 批量操作 -->

      <div v-if="selectedRows.length > 0" class="batch-toolbar">

        <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>

        <el-button type="danger" size="small" @click="batchDelete">批量删除</el-button>

        <el-button size="small" @click="batchExport">导出选中</el-button>

      </div>

      <el-table :data="requests" v-loading="loading" stripe @row-click="viewRequest" @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="45" />
        <el-table-column prop="request_no" label="请求编号" width="140" />
        <el-table-column prop="subject" label="标题" min-width="180" show-overflow-tooltip />
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
            <span :class="row.sla_breached ? 'sla-breach' : 'sla-ok'">
              {{ row.sla_breached ? '已超时' : '正常' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="160">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="240" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click.stop="viewRequest(row)">详情</el-button>
            <el-button size="small" link v-if="row.status === 'NEW'" @click.stop="submitRequest(row)">提交</el-button>
            <el-button size="small" link v-if="row.status === 'NEW'" @click.stop="acknowledgeRequest(row)">确认</el-button>
            <el-button size="small" link v-if="['ACKNOWLEDGED', 'NEW'].includes(row.status)" @click.stop="assignRequest(row)">分配</el-button>
            <el-button size="small" link type="success" v-if="['IN_PROGRESS', 'ASSIGNED', 'PENDING_PARTS'].includes(row.status)" @click.stop="completeRequest(row)">完成</el-button>
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
          <el-select v-model="requestForm.service_contract" filterable clearable placeholder="选择合同" style="width: 100%">
            <el-option v-for="c in customerContracts" :key="c.id" :label="c.title" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="请求标题" prop="subject">
          <el-input v-model="requestForm.subject" placeholder="简要描述问题" />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="请求类型" prop="request_type">
              <el-select v-model="requestForm.request_type" style="width: 100%">
                <el-option label="故障报修" value="BREAKDOWN" />
                <el-option label="技术咨询" value="CONSULTATION" />
                <el-option label="改造需求" value="MODIFICATION" />
                <el-option label="备件需求" value="SPARE_PARTS" />
                <el-option label="培训需求" value="TRAINING" />
                <el-option label="其他" value="OTHER" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="优先级" prop="priority">
              <el-select v-model="requestForm.priority" style="width: 100%">
                <el-option label="紧急" value="CRITICAL" />
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
        <el-form-item label="联系人" prop="contact_name">
          <el-input v-model="requestForm.contact_name" placeholder="联系人姓名" />
        </el-form-item>
        <el-form-item label="联系电话" prop="contact_phone">
          <el-input v-model="requestForm.contact_phone" placeholder="联系电话" />
        </el-form-item>
        <el-form-item label="设备型号">
          <el-input v-model="requestForm.equipment_model" placeholder="设备型号" />
        </el-form-item>
        <el-form-item label="设备序列号">
          <el-input v-model="requestForm.equipment_serial" placeholder="序列号" />
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
          <el-descriptions-item label="标题" :span="2">{{ currentRequest.subject }}</el-descriptions-item>
          <el-descriptions-item label="客户">{{ currentRequest.customer_name }}</el-descriptions-item>
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
                            :timestamp="formatDate(act.start_time)" placement="top">
            <el-card shadow="hover">
              <h4>{{ act.activity_type_display }}</h4>
              <p>{{ act.description }}</p>
              <p class="text-muted">操作人: {{ act.performed_by_name }}</p>
              <p v-if="act.duration_minutes" class="text-muted">用时: {{ act.duration_minutes }}分钟</p>
            </el-card>
          </el-timeline-item>
        </el-timeline>
      </template>
    </el-drawer>

    <!-- 分配负责人对话框 -->
    <el-dialog v-model="showAssignDialog" title="分配负责人" width="400px">
      <el-form label-width="80px">
        <el-form-item label="负责人">
          <el-select v-model="assignUserId" filterable placeholder="选择负责人" style="width: 100%">
            <el-option v-for="u in users" :key="u.id" :label="u.full_name || u.username" :value="u.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAssignDialog = false">取消</el-button>
        <el-button type="primary" @click="confirmAssign">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Plus } from '@element-plus/icons-vue'
import request from '@/utils/request'
import { getServiceRequests, getServiceContracts, createServiceRequest, getServiceRequest, assignServiceRequest, completeServiceRequest } from '@/api/sales'
import { getCustomerList } from '@/api/masterdata'
import { getUsers } from '@/api/auth'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/sales/service-requests/', { onSuccess: () => loadRequests() })


const loading = ref(false)
const submitting = ref(false)
const showCreateDialog = ref(false)
const showDetailDrawer = ref(false)

const requests = ref<any[]>([])
const customers = ref<any[]>([])
const customerContracts = ref<any[]>([])
const users = ref<any[]>([])
const currentRequest = ref(null)

const searchKeyword = ref('')
const statusFilter = ref('')
const priorityFilter = ref('')

const showAssignDialog = ref(false)
const assignTarget = ref<any>(null)
const assignUserId = ref<any>(null)

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
  service_contract: null,
  subject: '',
  request_type: 'BREAKDOWN',
  priority: 'MEDIUM',
  description: '',
  contact_name: '',
  contact_phone: '',
  equipment_model: '',
  equipment_serial: ''
})

const requestRules = {
  customer: [{ required: true, message: '请选择客户', trigger: 'change' }],
  subject: [{ required: true, message: '请输入请求标题', trigger: 'blur' }],
  request_type: [{ required: true, message: '请选择请求类型', trigger: 'change' }],
  priority: [{ required: true, message: '请选择优先级', trigger: 'change' }],
  description: [{ required: true, message: '请描述问题', trigger: 'blur' }],
  contact_name: [{ required: true, message: '请输入联系人', trigger: 'blur' }],
  contact_phone: [{ required: true, message: '请输入联系电话', trigger: 'blur' }]
}

const requestFormRef = ref(null)

const formatDate = (date) => {
  if (!date) return '-'
  return new Date(date).toLocaleString('zh-CN')
}

const getStatusType = (status) => {
  const map = {
    NEW: 'info', ACKNOWLEDGED: 'warning', ASSIGNED: 'warning', IN_PROGRESS: 'primary',
    PENDING_PARTS: 'warning', RESOLVED: 'success', CLOSED: 'info'
  }
  return map[status] || 'info'
}

const getPriorityType = (priority) => {
  const map = { CRITICAL: 'danger', HIGH: 'warning', MEDIUM: '', LOW: 'info' }
  return map[priority] || ''
}

const loadRequests = async () => {
  loading.value = true
  try {
    const params = { page: pagination.page, page_size: pagination.pageSize }
    if (searchKeyword.value) params.search = searchKeyword.value
    if (statusFilter.value) params.status = statusFilter.value
    if (priorityFilter.value) params.priority = priorityFilter.value

    const res = await getServiceRequests(params)
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
      getServiceRequests({ status: 'NEW', page_size: 1 }),
      getServiceRequests({ status: 'IN_PROGRESS', page_size: 1 }),
      getServiceRequests({ status: 'PENDING_PARTS', page_size: 1 })
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
    const res = await getCustomerList({ page_size: 1000 })
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
    const res = await getServiceContracts({ customer: customerId, status: 'ACTIVE' })
    customerContracts.value = res.results || res
  } catch (e) {
    console.error('加载合同列表失败')
  }
}

const loadUsers = async () => {
  try {
    const res = await getUsers({ page_size: 1000 })
    users.value = res.results || res
  } catch (e) {
    console.error('加载用户列表失败')
  }
}

const createRequest = async () => {
  try {
    await requestFormRef.value.validate()
    submitting.value = true
    // equipment_info 为后端 JSONField，组装为对象
    const payload = {
      customer: requestForm.customer,
      service_contract: requestForm.service_contract,
      subject: requestForm.subject,
      request_type: requestForm.request_type,
      priority: requestForm.priority,
      description: requestForm.description,
      contact_name: requestForm.contact_name,
      contact_phone: requestForm.contact_phone,
      equipment_info: {
        model: requestForm.equipment_model || '',
        serial: requestForm.equipment_serial || ''
      }
    }
    await createServiceRequest(payload)
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
    const res = await getServiceRequest(row.id)
    currentRequest.value = res
    showDetailDrawer.value = true
  } catch (e) {
    ElMessage.error('加载请求详情失败')
  }
}

const assignRequest = (row) => {
  assignTarget.value = row
  assignUserId.value = row.assigned_to || null
  showAssignDialog.value = true
}

const confirmAssign = async () => {
  if (!assignUserId.value) {
    ElMessage.warning('请选择负责人')
    return
  }
  try {
    await assignServiceRequest(assignTarget.value.id, { assigned_to: assignUserId.value })
    ElMessage.success('分配成功')
    showAssignDialog.value = false
    loadRequests()
  } catch (e) {
    ElMessage.error('分配失败')
  }
}

const completeRequest = async (row) => {
  ElMessageBox.prompt('请输入处理结果', '完成请求').then(async ({ value }) => {
    await completeServiceRequest(row.id, { resolution: value })
    ElMessage.success('请求已完成')
    loadRequests()
    loadStats()
  }).catch(() => {})
}

const submitRequest = async (row) => {
  try {
    await request({ url: `/sales/service-requests/${row.id}/submit/`, method: 'post' })
    ElMessage.success('已提交')
    loadRequests()
  } catch (e) {
    ElMessage.error('提交失败')
  }
}

const acknowledgeRequest = async (row) => {
  try {
    await request({ url: `/sales/service-requests/${row.id}/acknowledge/`, method: 'post' })
    ElMessage.success('已确认')
    loadRequests()
  } catch (e) {
    ElMessage.error('确认失败')
  }
}

onMounted(() => {
  loadRequests()
  loadStats()
  loadCustomers()
  loadUsers()
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
