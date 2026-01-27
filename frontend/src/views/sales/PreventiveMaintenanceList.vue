<template>
  <div class="preventive-maintenance-list">
    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stat-row">
      <el-col :span="6">
        <el-card class="stat-card">
          <el-statistic title="计划中任务" :value="stats.scheduled" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card warning">
          <el-statistic title="本周到期" :value="stats.dueThisWeek" value-style="color: #E6A23C" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card danger">
          <el-statistic title="已逾期" :value="stats.overdue" value-style="color: #F56C6C" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <el-statistic title="本月已完成" :value="stats.completedThisMonth" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 预防维护列表 -->
    <el-card>
      <template #header>
        <div class="card-header">
          <span>预防维护计划</span>
          <div class="header-actions">
            <el-date-picker v-model="dateRange" type="daterange" range-separator="至"
                            start-placeholder="开始日期" end-placeholder="结束日期"
                            value-format="YYYY-MM-DD" @change="loadMaintenances"
                            style="width: 240px; margin-right: 12px" />
            <el-select v-model="statusFilter" placeholder="状态" clearable style="width: 120px; margin-right: 12px"
                       @change="loadMaintenances">
              <el-option label="计划中" value="SCHEDULED" />
              <el-option label="进行中" value="IN_PROGRESS" />
              <el-option label="已完成" value="COMPLETED" />
              <el-option label="已跳过" value="SKIPPED" />
            </el-select>
            <el-button type="primary" @click="showCreateDialog = true">
              <el-icon><Plus /></el-icon>创建计划
            </el-button>
          </div>
        </div>
      </template>

      <el-table :data="maintenances" v-loading="loading" stripe>
        <el-table-column prop="contract_title" label="服务合同" width="180" show-overflow-tooltip />
        <el-table-column prop="customer_name" label="客户" width="150" show-overflow-tooltip />
        <el-table-column prop="title" label="维护标题" min-width="150" show-overflow-tooltip />
        <el-table-column label="维护类型" width="100">
          <template #default="{ row }">
            <el-tag size="small">{{ row.maintenance_type_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="频率" width="100" align="center">
          <template #default="{ row }">
            {{ row.frequency_display }}
          </template>
        </el-table-column>
        <el-table-column prop="scheduled_date" label="计划日期" width="110" />
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="assigned_to_name" label="负责人" width="100" />
        <el-table-column label="剩余天数" width="100" align="center">
          <template #default="{ row }">
            <span :class="getDaysClass(row.days_until_due)">
              {{ row.days_until_due > 0 ? row.days_until_due + '天' : (row.days_until_due === 0 ? '今天' : '逾期' + Math.abs(row.days_until_due) + '天') }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click="viewMaintenance(row)">详情</el-button>
            <el-button size="small" link v-if="row.status === 'SCHEDULED'" @click="startMaintenance(row)">开始</el-button>
            <el-button size="small" link type="success" v-if="row.status === 'IN_PROGRESS'" @click="completeMaintenance(row)">完成</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        @size-change="loadMaintenances"
        @current-change="loadMaintenances"
        style="margin-top: 16px; justify-content: flex-end"
      />
    </el-card>

    <!-- 创建计划对话框 -->
    <el-dialog v-model="showCreateDialog" title="创建预防维护计划" width="600px">
      <el-form :model="maintenanceForm" :rules="maintenanceRules" ref="maintenanceFormRef" label-width="100px">
        <el-form-item label="服务合同" prop="contract">
          <el-select v-model="maintenanceForm.contract" filterable placeholder="选择服务合同" style="width: 100%">
            <el-option v-for="c in contracts" :key="c.id" :label="c.title" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="维护标题" prop="title">
          <el-input v-model="maintenanceForm.title" placeholder="维护计划标题" />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="维护类型" prop="maintenance_type">
              <el-select v-model="maintenanceForm.maintenance_type" style="width: 100%">
                <el-option label="定期检查" value="INSPECTION" />
                <el-option label="保养维护" value="MAINTENANCE" />
                <el-option label="校准调试" value="CALIBRATION" />
                <el-option label="零件更换" value="REPLACEMENT" />
                <el-option label="软件更新" value="SOFTWARE_UPDATE" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="维护频率" prop="frequency">
              <el-select v-model="maintenanceForm.frequency" style="width: 100%">
                <el-option label="每周" value="WEEKLY" />
                <el-option label="每月" value="MONTHLY" />
                <el-option label="每季度" value="QUARTERLY" />
                <el-option label="每半年" value="SEMI_ANNUAL" />
                <el-option label="每年" value="ANNUAL" />
                <el-option label="单次" value="ONE_TIME" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="计划日期" prop="scheduled_date">
              <el-date-picker v-model="maintenanceForm.scheduled_date" type="date" 
                              value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="预计时长(h)">
              <el-input-number v-model="maintenanceForm.estimated_duration" :min="0.5" :step="0.5" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="负责人">
          <el-select v-model="maintenanceForm.assigned_to" filterable clearable placeholder="选择负责人" style="width: 100%">
            <el-option v-for="u in users" :key="u.id" :label="u.full_name || u.username" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="维护内容">
          <el-input v-model="maintenanceForm.description" type="textarea" :rows="3" placeholder="详细描述维护内容" />
        </el-form-item>
        <el-form-item label="检查清单">
          <el-input v-model="maintenanceForm.checklist" type="textarea" :rows="4" 
                    placeholder="每行一项检查内容" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="createMaintenance" :loading="submitting">创建</el-button>
      </template>
    </el-dialog>

    <!-- 维护详情抽屉 -->
    <el-drawer v-model="showDetailDrawer" title="维护计划详情" size="50%">
      <template v-if="currentMaintenance">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="服务合同">{{ currentMaintenance.contract_title }}</el-descriptions-item>
          <el-descriptions-item label="客户">{{ currentMaintenance.customer_name }}</el-descriptions-item>
          <el-descriptions-item label="维护标题" :span="2">{{ currentMaintenance.title }}</el-descriptions-item>
          <el-descriptions-item label="类型">{{ currentMaintenance.maintenance_type_display }}</el-descriptions-item>
          <el-descriptions-item label="频率">{{ currentMaintenance.frequency_display }}</el-descriptions-item>
          <el-descriptions-item label="计划日期">{{ currentMaintenance.scheduled_date }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getStatusType(currentMaintenance.status)">{{ currentMaintenance.status_display }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="负责人">{{ currentMaintenance.assigned_to_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="预计时长">{{ currentMaintenance.estimated_duration }}小时</el-descriptions-item>
          <el-descriptions-item label="维护内容" :span="2">{{ currentMaintenance.description }}</el-descriptions-item>
        </el-descriptions>

        <el-divider>检查清单</el-divider>
        <div class="checklist">
          <el-checkbox v-for="(item, index) in currentMaintenance.checklist_items" :key="index"
                       v-model="item.checked" :disabled="currentMaintenance.status === 'COMPLETED'">
            {{ item.content }}
          </el-checkbox>
        </div>

        <el-divider v-if="currentMaintenance.completion_notes">完成记录</el-divider>
        <div v-if="currentMaintenance.completion_notes" class="completion-notes">
          <p><strong>完成时间:</strong> {{ formatDate(currentMaintenance.completed_at) }}</p>
          <p><strong>实际时长:</strong> {{ currentMaintenance.actual_duration }}小时</p>
          <p><strong>完成备注:</strong> {{ currentMaintenance.completion_notes }}</p>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import request from '@/utils/request'

const loading = ref(false)
const submitting = ref(false)
const showCreateDialog = ref(false)
const showDetailDrawer = ref(false)

const maintenances = ref([])
const contracts = ref([])
const users = ref([])
const currentMaintenance = ref(null)

const dateRange = ref([])
const statusFilter = ref('')

const stats = ref({
  scheduled: 0,
  dueThisWeek: 0,
  overdue: 0,
  completedThisMonth: 0
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const maintenanceForm = reactive({
  contract: null,
  title: '',
  maintenance_type: 'INSPECTION',
  frequency: 'MONTHLY',
  scheduled_date: '',
  estimated_duration: 2,
  assigned_to: null,
  description: '',
  checklist: ''
})

const maintenanceRules = {
  contract: [{ required: true, message: '请选择服务合同', trigger: 'change' }],
  title: [{ required: true, message: '请输入维护标题', trigger: 'blur' }],
  maintenance_type: [{ required: true, message: '请选择维护类型', trigger: 'change' }],
  frequency: [{ required: true, message: '请选择维护频率', trigger: 'change' }],
  scheduled_date: [{ required: true, message: '请选择计划日期', trigger: 'change' }]
}

const maintenanceFormRef = ref(null)

const formatDate = (date) => {
  if (!date) return '-'
  return new Date(date).toLocaleString('zh-CN')
}

const getStatusType = (status) => {
  const map = { SCHEDULED: 'info', IN_PROGRESS: 'primary', COMPLETED: 'success', SKIPPED: 'warning' }
  return map[status] || 'info'
}

const getDaysClass = (days) => {
  if (days < 0) return 'days-overdue'
  if (days <= 3) return 'days-urgent'
  if (days <= 7) return 'days-soon'
  return ''
}

const loadMaintenances = async () => {
  loading.value = true
  try {
    const params = { page: pagination.page, page_size: pagination.pageSize }
    if (dateRange.value?.length === 2) {
      params.start_date = dateRange.value[0]
      params.end_date = dateRange.value[1]
    }
    if (statusFilter.value) params.status = statusFilter.value

    const res = await request.get('/api/sales/preventive-maintenance/', { params })
    maintenances.value = res.results || res
    pagination.total = res.count || maintenances.value.length
  } catch (e) {
    ElMessage.error('加载预防维护列表失败')
  } finally {
    loading.value = false
  }
}

const loadStats = async () => {
  try {
    const [scheduledRes, upcomingRes, overdueRes] = await Promise.all([
      request.get('/api/sales/preventive-maintenance/', { params: { status: 'SCHEDULED', page_size: 1 } }),
      request.get('/api/sales/preventive-maintenance/upcoming/', { params: { days: 7 } }),
      request.get('/api/sales/preventive-maintenance/overdue/')
    ])
    stats.value.scheduled = scheduledRes.count || 0
    stats.value.dueThisWeek = upcomingRes?.length || 0
    stats.value.overdue = overdueRes?.length || 0
  } catch (e) {
    console.error('加载统计数据失败')
  }
}

const loadContracts = async () => {
  try {
    const res = await request.get('/api/sales/service-contracts/', { params: { status: 'ACTIVE', page_size: 1000 } })
    contracts.value = res.results || res
  } catch (e) {
    console.error('加载合同列表失败')
  }
}

const loadUsers = async () => {
  try {
    const res = await request.get('/api/auth/users/', { params: { page_size: 1000 } })
    users.value = res.results || res
  } catch (e) {
    console.error('加载用户列表失败')
  }
}

const createMaintenance = async () => {
  try {
    await maintenanceFormRef.value.validate()
    submitting.value = true
    const data = { ...maintenanceForm }
    if (data.checklist) {
      data.checklist = data.checklist.split('\n').filter(s => s.trim())
    }
    await request.post('/api/sales/preventive-maintenance/', data)
    ElMessage.success('预防维护计划创建成功')
    showCreateDialog.value = false
    loadMaintenances()
    loadStats()
  } catch (e) {
    if (e !== false) ElMessage.error('创建失败')
  } finally {
    submitting.value = false
  }
}

const viewMaintenance = async (row) => {
  try {
    const res = await request.get(`/api/sales/preventive-maintenance/${row.id}/`)
    currentMaintenance.value = res
    showDetailDrawer.value = true
  } catch (e) {
    ElMessage.error('加载详情失败')
  }
}

const startMaintenance = async (row) => {
  try {
    await request.post(`/api/sales/preventive-maintenance/${row.id}/start/`)
    ElMessage.success('维护已开始')
    loadMaintenances()
  } catch (e) {
    ElMessage.error('操作失败')
  }
}

const completeMaintenance = async (row) => {
  ElMessageBox.prompt('请输入完成备注', '完成维护').then(async ({ value }) => {
    await request.post(`/api/sales/preventive-maintenance/${row.id}/complete/`, { 
      notes: value,
      actual_duration: row.estimated_duration
    })
    ElMessage.success('维护已完成')
    loadMaintenances()
    loadStats()
  })
}

onMounted(() => {
  loadMaintenances()
  loadStats()
  loadContracts()
  loadUsers()
})
</script>

<style scoped>
.preventive-maintenance-list {
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
.days-overdue {
  color: #F56C6C;
  font-weight: bold;
}
.days-urgent {
  color: #E6A23C;
}
.days-soon {
  color: #409EFF;
}
.checklist {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.completion-notes {
  background: #f5f7fa;
  padding: 16px;
  border-radius: 4px;
}
</style>
