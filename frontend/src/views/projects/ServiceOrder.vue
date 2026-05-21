<template>
  <div class="service-order">
    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stat-row">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value">{{ stats.pending || 0 }}</div>
          <div class="stat-label">待派工</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card warning">
          <div class="stat-value">{{ stats.on_site || 0 }}</div>
          <div class="stat-label">现场中</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card success">
          <div class="stat-value">{{ stats.completed || 0 }}</div>
          <div class="stat-label">本月完成</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card danger">
          <div class="stat-value">{{ stats.urgent || 0 }}</div>
          <div class="stat-label">紧急服务</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="filter-card">
      <div class="filter-header">
        <el-button type="primary" v-permission="'projects:aftersales:create'" @click="handleCreate">
          <el-icon><Plus /></el-icon> 新建服务单
        </el-button>
        <div class="filter-right">
          <el-input v-model="searchText" placeholder="搜索" clearable style="width: 180px" @keyup.enter="loadData">
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
          <el-select v-model="statusFilter" placeholder="状态" clearable style="width: 120px; margin-left: 10px" @change="loadData">
            <el-option label="待派工" value="PENDING" />
            <el-option label="已派工" value="ASSIGNED" />
            <el-option label="现场中" value="ON_SITE" />
            <el-option label="已完成" value="COMPLETED" />
          </el-select>
          <el-select v-model="typeFilter" placeholder="服务类型" clearable style="width: 120px; margin-left: 10px" @change="loadData">
            <el-option label="安装" value="INSTALLATION" />
            <el-option label="调试" value="DEBUGGING" />
            <el-option label="培训" value="TRAINING" />
            <el-option label="维护" value="MAINTENANCE" />
            <el-option label="维修" value="REPAIR" />
          </el-select>
        </div>
      </div>
    </el-card>

    <el-card class="data-card">
      <!-- 批量操作 -->
      <div v-if="selectedRows.length > 0" class="batch-toolbar">
        <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>
        <el-button type="danger" size="small" @click="batchDelete">批量删除</el-button>
        <el-button size="small" @click="batchExport">导出选中</el-button>
      </div>
      <el-table :data="tableData" v-loading="loading" stripe @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="45" />
        <el-table-column prop="order_no" label="服务单号" width="130" />
        <el-table-column prop="title" label="服务标题" min-width="200" />
        <el-table-column prop="customer_name" label="客户" width="150" />
        <el-table-column prop="service_type_display" label="服务类型" width="90" />
        <el-table-column prop="service_address" label="服务地址" width="180" show-overflow-tooltip />
        <el-table-column label="期望日期" width="110">
          <template #default="{ row }">{{ row.requested_date }}</template>
        </el-table-column>
        <el-table-column label="优先级" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="getPriorityType(row.priority)" size="small">{{ row.priority_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="技术人员" width="100">
          <template #default="{ row }">
            <span v-if="row.technician_count > 0">{{ row.technician_count }}人</span>
            <span v-else class="text-muted">未派工</span>
          </template>
        </el-table-column>
        <el-table-column prop="status_display" label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="handleView(row)">查看</el-button>
            <el-button type="primary" link @click="handleDispatch(row)" v-if="['PENDING', 'ASSIGNED'].includes(row.status)">派工</el-button>
            <el-button type="success" link @click="handleComplete(row)" v-if="row.status === 'ON_SITE'">完成</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="total"
        layout="total, sizes, prev, pager, next"
        @size-change="loadData"
        @current-change="loadData"
        style="margin-top: 16px; justify-content: flex-end"
      />
    </el-card>

    <!-- 新建服务单对话框 -->
    <el-dialog v-model="createDialogVisible" title="新建服务单" width="700px" destroy-on-close>
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="服务类型" prop="service_type">
              <el-select v-model="form.service_type" placeholder="选择类型" style="width: 100%">
                <el-option label="安装" value="INSTALLATION" />
                <el-option label="调试" value="DEBUGGING" />
                <el-option label="培训" value="TRAINING" />
                <el-option label="维护" value="MAINTENANCE" />
                <el-option label="维修" value="REPAIR" />
                <el-option label="验收" value="ACCEPTANCE" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="优先级" prop="priority">
              <el-select v-model="form.priority" placeholder="选择优先级" style="width: 100%">
                <el-option label="低" value="LOW" />
                <el-option label="普通" value="NORMAL" />
                <el-option label="高" value="HIGH" />
                <el-option label="紧急" value="URGENT" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="服务标题" prop="title">
          <el-input v-model="form.title" placeholder="请输入服务标题" />
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="客户" prop="customer">
              <el-select v-model="form.customer" filterable placeholder="选择客户" style="width: 100%" @change="handleCustomerChange">
                <el-option v-for="c in customers" :key="c.id" :label="c.name" :value="c.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="关联设备">
              <el-select v-model="form.equipment" filterable clearable placeholder="选择设备" style="width: 100%">
                <el-option v-for="e in equipments" :key="e.id" :label="e.name" :value="e.id" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="服务地址" prop="service_address">
          <el-input v-model="form.service_address" type="textarea" :rows="2" placeholder="请输入服务地址" />
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="联系人" prop="contact_name">
              <el-input v-model="form.contact_name" placeholder="联系人姓名" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="联系电话" prop="contact_phone">
              <el-input v-model="form.contact_phone" placeholder="联系电话" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="期望日期" prop="requested_date">
              <el-date-picker v-model="form.requested_date" type="date" placeholder="选择日期" style="width: 100%" value-format="YYYY-MM-DD" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="预计天数">
              <el-input-number v-model="form.estimated_days" :min="0.5" :step="0.5" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="服务描述">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="请描述服务内容和要求" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmitCreate" :loading="submitting">保存</el-button>
      </template>
    </el-dialog>

    <!-- 派工对话框 -->
    <el-dialog v-model="dispatchDialogVisible" title="派工" width="600px" destroy-on-close>
      <div class="dispatch-info" v-if="currentOrder">
        <p><strong>服务单：</strong>{{ currentOrder.order_no }} - {{ currentOrder.title }}</p>
        <p><strong>客户：</strong>{{ currentOrder.customer_name }}</p>
        <p><strong>服务地址：</strong>{{ currentOrder.service_address }}</p>
      </div>
      <el-divider />
      <el-form :model="dispatchForm" label-width="100px">
        <el-form-item label="技术人员" required>
          <el-select v-model="dispatchForm.technician_id" filterable placeholder="选择技术人员" style="width: 100%">
            <el-option v-for="t in technicians" :key="t.user_id" :label="t.user_name" :value="t.user_id">
              <span>{{ t.user_name }}</span>
              <el-tag size="small" :type="t.availability === 'AVAILABLE' ? 'success' : 'warning'" style="margin-left: 10px">
                {{ t.availability_status_display }}
              </el-tag>
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="dispatchForm.role" style="width: 100%">
            <el-option label="负责人" value="LEADER" />
            <el-option label="成员" value="MEMBER" />
            <el-option label="支持" value="SUPPORT" />
          </el-select>
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="计划开始">
              <el-date-picker v-model="dispatchForm.planned_start" type="date" placeholder="开始日期" style="width: 100%" value-format="YYYY-MM-DD" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="计划结束">
              <el-date-picker v-model="dispatchForm.planned_end" type="date" placeholder="结束日期" style="width: 100%" value-format="YYYY-MM-DD" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="dispatchDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmitDispatch" :loading="submitting">确认派工</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { getServiceOrderList, createServiceOrder, getServiceOrderDashboard, completeServiceOrder, dispatchServiceOrder } from '@/api/projects/service-order'
import { getTechnicianProfileList } from '@/api/projects/technician'
import { getProjectEquipmentList } from '@/api/projects/equipment-monitoring'
import { getCustomerList } from '@/api/masterdata'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/projects_service-order/')


const router = useRouter()

const loading = ref(false)
const tableData = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(10)
const searchText = ref('')
const statusFilter = ref('')
const typeFilter = ref('')
const stats = ref({})

const createDialogVisible = ref(false)
const dispatchDialogVisible = ref(false)
const submitting = ref(false)
const formRef = ref(null)
const customers = ref([])
const equipments = ref([])
const technicians = ref([])
const currentOrder = ref(null)

const form = reactive({
  service_type: 'DEBUGGING',
  priority: 'NORMAL',
  title: '',
  customer: null,
  equipment: null,
  service_address: '',
  contact_name: '',
  contact_phone: '',
  requested_date: '',
  estimated_days: 1,
  description: ''
})

const dispatchForm = reactive({
  technician_id: null,
  role: 'MEMBER',
  planned_start: '',
  planned_end: ''
})

const rules = {
  service_type: [{ required: true, message: '请选择服务类型', trigger: 'change' }],
  title: [{ required: true, message: '请输入服务标题', trigger: 'blur' }],
  customer: [{ required: true, message: '请选择客户', trigger: 'change' }],
  service_address: [{ required: true, message: '请输入服务地址', trigger: 'blur' }],
  contact_name: [{ required: true, message: '请输入联系人', trigger: 'blur' }],
  contact_phone: [{ required: true, message: '请输入联系电话', trigger: 'blur' }],
  requested_date: [{ required: true, message: '请选择期望日期', trigger: 'change' }]
}

const getStatusType = (status) => {
  const map = { PENDING: 'info', ASSIGNED: 'warning', ON_SITE: 'primary', COMPLETED: 'success', CANCELLED: 'danger' }
  return map[status] || 'info'
}

const getPriorityType = (priority) => {
  const map = { LOW: 'info', NORMAL: '', HIGH: 'warning', URGENT: 'danger' }
  return map[priority] || ''
}

const loadData = async () => {
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value,
      search: searchText.value || undefined,
      status: statusFilter.value || undefined,
      service_type: typeFilter.value || undefined
    }
    const res = await getServiceOrderList(params)
    tableData.value = res.results || res || []
    total.value = res.count || tableData.value.length
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const loadStats = async () => {
  try {
    const res = await getServiceOrderDashboard()
    const statusStats = res.status_stats || []
    stats.value = {
      pending: statusStats.find(s => s.status === 'PENDING')?.count || 0,
      on_site: statusStats.find(s => s.status === 'ON_SITE')?.count || 0,
      completed: res.month_completed || 0,
      urgent: res.urgent_count || 0
    }
  } catch (e) {
    console.error(e)
  }
}

const loadCustomers = async () => {
  const res = await getCustomerList({ page_size: 1000 })
  customers.value = res.results || res || []
}

const loadTechnicians = async () => {
  const res = await getTechnicianProfileList({ page_size: 1000 })
  technicians.value = res.results || res || []
}

const handleCustomerChange = async (customerId) => {
  if (customerId) {
    const customer = customers.value.find(c => c.id === customerId)
    if (customer) {
      form.service_address = customer.address || ''
      form.contact_name = customer.contact_person || ''
      form.contact_phone = customer.phone || ''
    }
    const res = await getProjectEquipmentList({ customer: customerId, page_size: 1000 })
    equipments.value = res.results || res || []
  }
}

const handleCreate = () => {
  Object.assign(form, {
    service_type: 'DEBUGGING',
    priority: 'NORMAL',
    title: '',
    customer: null,
    equipment: null,
    service_address: '',
    contact_name: '',
    contact_phone: '',
    requested_date: '',
    estimated_days: 1,
    description: ''
  })
  createDialogVisible.value = true
}

const handleView = (row) => {
  router.push(`/projects/service-order/${row.id}`)
}

const handleDispatch = async (row) => {
  currentOrder.value = row
  dispatchForm.technician_id = null
  dispatchForm.role = 'MEMBER'
  dispatchForm.planned_start = row.planned_start_date || row.requested_date
  dispatchForm.planned_end = row.planned_end_date || row.requested_date
  await loadTechnicians()
  dispatchDialogVisible.value = true
}

const handleComplete = async (row) => {
  try {
    await ElMessageBox.confirm('确定完成此服务单?', '提示')
    await completeServiceOrder(row.id)
    ElMessage.success('服务已完成')
    loadData()
    loadStats()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('操作失败')
  }
}

const handleSubmitCreate = async () => {
  if (!formRef.value) return
  await formRef.value.validate()
  
  submitting.value = true
  try {
    await createServiceOrder(form)
    ElMessage.success('创建成功')
    createDialogVisible.value = false
    loadData()
    loadStats()
  } catch (e) {
    console.error(e)
    ElMessage.error('创建失败')
  } finally {
    submitting.value = false
  }
}

const handleSubmitDispatch = async () => {
  if (!dispatchForm.technician_id) {
    ElMessage.warning('请选择技术人员')
    return
  }
  
  submitting.value = true
  try {
    await dispatchServiceOrder(currentOrder.value.id, dispatchForm)
    ElMessage.success('派工成功')
    dispatchDialogVisible.value = false
    loadData()
  } catch (e) {
    console.error(e)
    ElMessage.error('派工失败')
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  loadData()
  loadStats()
  loadCustomers()
})
</script>

<style scoped>
.stat-row {
  margin-bottom: 16px;
}
.stat-card {
  text-align: center;
  cursor: pointer;
}
.stat-card .stat-value {
  font-size: 32px;
  font-weight: bold;
  color: #409eff;
}
.stat-card.warning .stat-value { color: #e6a23c; }
.stat-card.success .stat-value { color: #67c23a; }
.stat-card.danger .stat-value { color: #f56c6c; }
.stat-card .stat-label {
  font-size: 14px;
  color: #909399;
  margin-top: 8px;
}
.filter-card {
  margin-bottom: 16px;
}
.filter-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.filter-right {
  display: flex;
  align-items: center;
}
.dispatch-info p {
  margin: 8px 0;
}
.text-muted {
  color: #909399;
}
</style>
