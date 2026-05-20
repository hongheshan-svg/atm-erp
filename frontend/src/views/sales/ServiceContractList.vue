<template>
  <div class="service-contract-list">
    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stat-row">
      <el-col :span="6">
        <el-card class="stat-card">
          <el-statistic title="生效中合同" :value="stats.activeContracts" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card warning">
          <el-statistic title="即将到期(30天内)" :value="stats.expiringSoon" value-style="color: #E6A23C" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <el-statistic title="待处理服务请求" :value="stats.openRequests" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <el-statistic title="计划维护任务" :value="stats.plannedPM" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 合同列表 -->
    <el-card>
      <template #header>
        <div class="card-header">
          <span>服务合同管理</span>
          <div class="header-actions">
            <el-input v-model="searchKeyword" placeholder="搜索合同" clearable style="width: 200px; margin-right: 12px"
                      @keyup.enter="loadContracts">
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
            <el-select v-model="statusFilter" placeholder="状态" clearable style="width: 120px; margin-right: 12px"
                       @change="loadContracts">
              <el-option label="草稿" value="DRAFT" />
              <el-option label="生效中" value="ACTIVE" />
              <el-option label="已过期" value="EXPIRED" />
              <el-option label="已终止" value="TERMINATED" />
            </el-select>
            <el-button type="primary" v-permission="'sales:contract:create'" @click="showCreateDialog = true">
              <el-icon><Plus /></el-icon>新建合同
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

      <el-table :data="contracts" v-loading="loading" stripe @row-click="viewContract" @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="45" />
        <el-table-column prop="contract_no" label="合同编号" width="140" />
        <el-table-column prop="title" label="合同标题" min-width="180" show-overflow-tooltip />
        <el-table-column prop="customer_name" label="客户" width="150" show-overflow-tooltip />
        <el-table-column label="合同类型" width="120">
          <template #default="{ row }">
            <el-tag>{{ row.contract_type_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="start_date" label="开始日期" width="110" />
        <el-table-column prop="end_date" label="结束日期" width="110" />
        <el-table-column label="剩余天数" width="100" align="center">
          <template #default="{ row }">
            <span :class="{ 'text-warning': row.days_until_expiry < 30, 'text-danger': row.days_until_expiry < 7 }">
              {{ row.days_until_expiry > 0 ? row.days_until_expiry + '天' : '已到期' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="contract_amount" label="合同金额" width="120" align="right">
          <template #default="{ row }">
            ¥{{ formatMoney(row.contract_amount) }}
          </template>
        </el-table-column>
        <el-table-column label="服务次数" width="120" align="center">
          <template #default="{ row }">
            {{ row.remaining_visits }} / {{ row.includes_onsite_visits }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click.stop="viewContract(row)">详情</el-button>
            <el-button size="small" link type="success" v-if="row.status === 'DRAFT'" 
                       @click.stop="activateContract(row)">激活</el-button>
            <el-button size="small" link @click.stop="viewServiceHistory(row)">服务记录</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        @size-change="loadContracts"
        @current-change="loadContracts"
        style="margin-top: 16px; justify-content: flex-end"
      />
    </el-card>

    <!-- 新建合同对话框 -->
    <el-dialog v-model="showCreateDialog" title="新建服务合同" width="700px">
      <el-form :model="contractForm" :rules="contractRules" ref="contractFormRef" label-width="100px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="客户" prop="customer">
              <el-select v-model="contractForm.customer" filterable placeholder="选择客户" style="width: 100%">
                <el-option v-for="c in customers" :key="c.id" :label="c.name" :value="c.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="关联项目">
              <el-select v-model="contractForm.project" filterable clearable placeholder="选择项目" style="width: 100%">
                <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="合同标题" prop="title">
          <el-input v-model="contractForm.title" placeholder="输入合同标题" />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="合同类型" prop="contract_type">
              <el-select v-model="contractForm.contract_type" style="width: 100%">
                <el-option label="质保服务" value="WARRANTY" />
                <el-option label="延保服务" value="EXTENDED_WARRANTY" />
                <el-option label="维保合同" value="MAINTENANCE" />
                <el-option label="全包服务" value="FULL_SERVICE" />
                <el-option label="按需服务" value="ON_DEMAND" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="合同金额" prop="contract_amount">
              <el-input-number v-model="contractForm.contract_amount" :min="0" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="开始日期" prop="start_date">
              <el-date-picker v-model="contractForm.start_date" type="date" value-format="YYYY-MM-DD" 
                              placeholder="选择开始日期" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="结束日期" prop="end_date">
              <el-date-picker v-model="contractForm.end_date" type="date" value-format="YYYY-MM-DD" 
                              placeholder="选择结束日期" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="响应时间">
              <el-input-number v-model="contractForm.response_time_hours" :min="1" style="width: 100%">
                <template #suffix>小时</template>
              </el-input-number>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="解决时间">
              <el-input-number v-model="contractForm.resolution_time_hours" :min="1" style="width: 100%">
                <template #suffix>小时</template>
              </el-input-number>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="现场次数">
              <el-input-number v-model="contractForm.includes_onsite_visits" :min="0" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="包含服务">
          <el-checkbox v-model="contractForm.includes_parts">包含备件</el-checkbox>
          <el-checkbox v-model="contractForm.includes_travel">包含差旅</el-checkbox>
          <el-checkbox v-model="contractForm.includes_remote_support">包含远程支持</el-checkbox>
        </el-form-item>
        <el-form-item label="服务范围" prop="service_scope">
          <el-input v-model="contractForm.service_scope" type="textarea" :rows="3" placeholder="描述服务范围" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button v-permission="'sales:contract:create'" @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="createContract" :loading="submitting">创建</el-button>
      </template>
    </el-dialog>

    <!-- 合同详情抽屉 -->
    <el-drawer v-model="showDetailDrawer" title="合同详情" size="50%">
      <template v-if="currentContract">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="合同编号">{{ currentContract.contract_no }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getStatusType(currentContract.status)">{{ currentContract.status_display }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="合同标题" :span="2">{{ currentContract.title }}</el-descriptions-item>
          <el-descriptions-item label="客户">{{ currentContract.customer_name }}</el-descriptions-item>
          <el-descriptions-item label="项目">{{ currentContract.project_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="合同类型">{{ currentContract.contract_type_display }}</el-descriptions-item>
          <el-descriptions-item label="合同金额">¥{{ formatMoney(currentContract.contract_amount) }}</el-descriptions-item>
          <el-descriptions-item label="开始日期">{{ currentContract.start_date }}</el-descriptions-item>
          <el-descriptions-item label="结束日期">{{ currentContract.end_date }}</el-descriptions-item>
          <el-descriptions-item label="响应时间">{{ currentContract.response_time_hours }}小时</el-descriptions-item>
          <el-descriptions-item label="解决时间">{{ currentContract.resolution_time_hours }}小时</el-descriptions-item>
          <el-descriptions-item label="服务范围" :span="2">{{ currentContract.service_scope }}</el-descriptions-item>
        </el-descriptions>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Search, Plus } from '@element-plus/icons-vue'
import { getServiceContracts, getExpiringSoonServiceContracts, getServiceRequests, getUpcomingMaintenance, createServiceContract, getServiceContract, activateServiceContract, getServiceHistory } from '@/api/sales'
import { getCustomerList } from '@/api/masterdata'
import { getProjectList } from '@/api/projects/project'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/sales/')


const loading = ref(false)
const submitting = ref(false)
const showCreateDialog = ref(false)
const showDetailDrawer = ref(false)

const contracts = ref([])
const customers = ref([])
const projects = ref([])
const currentContract = ref(null)

const searchKeyword = ref('')
const statusFilter = ref('')

const stats = ref({
  activeContracts: 0,
  expiringSoon: 0,
  openRequests: 0,
  plannedPM: 0
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const contractForm = reactive({
  customer: null,
  project: null,
  title: '',
  contract_type: 'MAINTENANCE',
  contract_amount: 0,
  start_date: '',
  end_date: '',
  response_time_hours: 24,
  resolution_time_hours: 72,
  includes_onsite_visits: 4,
  includes_parts: false,
  includes_travel: false,
  includes_remote_support: true,
  service_scope: ''
})

const contractRules = {
  customer: [{ required: true, message: '请选择客户', trigger: 'change' }],
  title: [{ required: true, message: '请输入合同标题', trigger: 'blur' }],
  contract_type: [{ required: true, message: '请选择合同类型', trigger: 'change' }],
  start_date: [{ required: true, message: '请选择开始日期', trigger: 'change' }],
  end_date: [{ required: true, message: '请选择结束日期', trigger: 'change' }],
  service_scope: [{ required: true, message: '请描述服务范围', trigger: 'blur' }]
}

const contractFormRef = ref(null)

const formatMoney = (val) => {
  return Number(val || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2 })
}

const getStatusType = (status) => {
  const map = { DRAFT: 'info', ACTIVE: 'success', EXPIRED: 'warning', TERMINATED: 'danger' }
  return map[status] || 'info'
}

const loadContracts = async () => {
  loading.value = true
  try {
    const params = { page: pagination.page, page_size: pagination.pageSize }
    if (searchKeyword.value) params.search = searchKeyword.value
    if (statusFilter.value) params.status = statusFilter.value

    const res = await getServiceContracts(params)
    contracts.value = res.results || res
    pagination.total = res.count || contracts.value.length
  } catch (e) {
    ElMessage.error('加载合同列表失败')
  } finally {
    loading.value = false
  }
}

const loadStats = async () => {
  try {
    const activeRes = await getServiceContracts({ status: 'ACTIVE', page_size: 1 })
    stats.value.activeContracts = activeRes.count || 0

    const expiringRes = await getExpiringSoonServiceContracts({ days: 30 })
    stats.value.expiringSoon = expiringRes?.length || 0

    const requestsRes = await getServiceRequests({ status: 'NEW', page_size: 1 })
    stats.value.openRequests = requestsRes.count || 0

    const pmRes = await getUpcomingMaintenance({ days: 30 })
    stats.value.plannedPM = pmRes?.length || 0
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

const loadProjects = async () => {
  try {
    const res = await getProjectList({ page_size: 1000 })
    projects.value = res.results || res
  } catch (e) {
    console.error('加载项目列表失败')
  }
}

const createContract = async () => {
  try {
    await contractFormRef.value.validate()
    submitting.value = true
    await createServiceContract(contractForm)
    ElMessage.success('合同创建成功')
    showCreateDialog.value = false
    loadContracts()
    loadStats()
  } catch (e) {
    if (e !== false) ElMessage.error('创建失败')
  } finally {
    submitting.value = false
  }
}

const viewContract = async (row) => {
  try {
    const res = await getServiceContract(row.id)
    currentContract.value = res
    showDetailDrawer.value = true
  } catch (e) {
    ElMessage.error('加载合同详情失败')
  }
}

const activateContract = async (row) => {
  try {
    await activateServiceContract(row.id)
    ElMessage.success('合同已激活')
    loadContracts()
    loadStats()
  } catch (e) {
    ElMessage.error('激活失败')
  }
}

const viewServiceHistory = async (row) => {
  try {
    const res = await getServiceHistory(row.id)
    ElMessage.info(`服务请求: ${res.service_requests?.length || 0} 条, 预防维护: ${res.pm_records?.length || 0} 条`)
  } catch (e) {
    ElMessage.error('获取服务历史失败')
  }
}

onMounted(() => {
  loadContracts()
  loadStats()
  loadCustomers()
  loadProjects()
})
</script>

<style scoped>
.service-contract-list {
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
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.header-actions {
  display: flex;
  align-items: center;
}
.text-warning {
  color: #E6A23C;
}
.text-danger {
  color: #F56C6C;
}
</style>
