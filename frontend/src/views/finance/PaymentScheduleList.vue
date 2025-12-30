<template>
  <div class="payment-schedule-list">
    <!-- 统计卡片 -->
    <el-row :gutter="16" class="summary-cards">
      <el-col :span="6">
        <el-card shadow="hover" class="summary-card">
          <div class="summary-content">
            <div class="summary-label">待收款总额</div>
            <div class="summary-value text-primary">¥{{ formatMoney(summary.total_remaining) }}</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="summary-card">
          <div class="summary-content">
            <div class="summary-label">收款进度</div>
            <div class="summary-value">
              <el-progress 
                :percentage="summary.overall_progress" 
                :color="getProgressColor(summary.overall_progress)"
                :stroke-width="12"
              />
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="summary-card">
          <div class="summary-content">
            <div class="summary-label">待收款</div>
            <div class="summary-value">{{ summary.pending_count + summary.partial_count }} 笔</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="summary-card warning">
          <div class="summary-content">
            <div class="summary-label">已逾期</div>
            <div class="summary-value text-danger">{{ summary.overdue_count }} 笔</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 主内容卡片 -->
    <el-card shadow="always">
      <template #header>
        <div class="card-header">
          <span>付款计划</span>
          <div class="header-actions">
            <el-button type="primary" @click="loadSummary">刷新</el-button>
          </div>
        </div>
      </template>

      <!-- 筛选条件 -->
      <el-form :inline="true" class="filter-form">
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部状态" clearable @change="loadData">
            <el-option label="待收款" value="PENDING" />
            <el-option label="部分收款" value="PARTIAL" />
            <el-option label="已收款" value="PAID" />
            <el-option label="已逾期" value="OVERDUE" />
          </el-select>
        </el-form-item>
        <el-form-item label="付款节点">
          <el-select v-model="filters.milestone_type" placeholder="全部类型" clearable @change="loadData">
            <el-option label="预付款" value="PREPAY" />
            <el-option label="发货款" value="ON_DELIVERY" />
            <el-option label="验收款" value="ON_ACCEPTANCE" />
            <el-option label="质保金" value="WARRANTY" />
            <el-option label="尾款" value="FINAL" />
          </el-select>
        </el-form-item>
        <el-form-item label="项目">
          <el-select v-model="filters.project" placeholder="全部项目" clearable filterable @change="loadData">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>

      <!-- 数据表格 -->
      <el-table :data="schedules" stripe border style="width: 100%" v-loading="loading">
        <el-table-column type="index" label="序号" width="55" align="center">
          <template #default="{ $index }">
            {{ (pagination.page - 1) * pagination.pageSize + $index + 1 }}
          </template>
        </el-table-column>
        <el-table-column prop="sales_order_no" label="销售订单" width="130" />
        <el-table-column prop="customer_name" label="客户" width="150" show-overflow-tooltip />
        <el-table-column prop="project_name" label="项目" width="120" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.project_name">{{ row.project_name }}</span>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="milestone_name" label="付款节点" width="120" />
        <el-table-column prop="percentage" label="比例" width="70" align="right">
          <template #default="{ row }">{{ row.percentage }}%</template>
        </el-table-column>
        <el-table-column prop="amount_due" label="应收金额" width="120" align="right">
          <template #default="{ row }">
            <span class="text-primary">¥{{ formatMoney(row.amount_due) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="amount_paid" label="已收金额" width="120" align="right">
          <template #default="{ row }">
            <span class="text-success">¥{{ formatMoney(row.amount_paid) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="收款进度" width="140">
          <template #default="{ row }">
            <el-progress 
              :percentage="row.payment_progress" 
              :color="getProgressColor(row.payment_progress)"
              :stroke-width="8"
              :show-text="true"
            />
          </template>
        </el-table-column>
        <el-table-column prop="due_date" label="计划收款日" width="110">
          <template #default="{ row }">
            <span :class="{ 'text-danger': row.is_overdue }">{{ row.due_date }}</span>
          </template>
        </el-table-column>
        <el-table-column label="距离到期" width="90" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.status === 'PAID'" type="success" size="small">已收款</el-tag>
            <el-tag v-else-if="row.is_overdue" type="danger" size="small">逾期{{ Math.abs(row.days_until_due) }}天</el-tag>
            <el-tag v-else-if="row.days_until_due <= 7" type="warning" size="small">{{ row.days_until_due }}天</el-tag>
            <span v-else class="text-muted">{{ row.days_until_due }}天</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="handleRecordPayment(row)" v-if="row.status !== 'PAID'">
              登记收款
            </el-button>
            <el-button type="info" link size="small" @click="handleViewDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :page-sizes="[20, 50, 100]"
        :total="pagination.total"
        layout="total, sizes, prev, pager, next"
        @size-change="handleSizeChange"
        @current-change="loadData"
        style="margin-top: 16px"
      />
    </el-card>

    <!-- 提醒卡片 -->
    <el-row :gutter="16" class="reminder-cards" v-if="summary.overdue_payments?.length || summary.upcoming_payments?.length">
      <el-col :span="12" v-if="summary.overdue_payments?.length">
        <el-card shadow="hover" class="reminder-card danger">
          <template #header>
            <div class="card-header">
              <span>⚠️ 已逾期款项</span>
            </div>
          </template>
          <el-table :data="summary.overdue_payments" size="small" stripe>
            <el-table-column prop="sales_order_no" label="订单" width="120" />
            <el-table-column prop="customer_name" label="客户" show-overflow-tooltip />
            <el-table-column prop="milestone_name" label="节点" width="90" />
            <el-table-column label="待收" width="100" align="right">
              <template #default="{ row }">¥{{ formatMoney(row.amount_due - row.amount_paid) }}</template>
            </el-table-column>
            <el-table-column label="逾期" width="70" align="center">
              <template #default="{ row }">
                <span class="text-danger">{{ Math.abs(row.days_until_due) }}天</span>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="12" v-if="summary.upcoming_payments?.length">
        <el-card shadow="hover" class="reminder-card warning">
          <template #header>
            <div class="card-header">
              <span>📅 即将到期款项 (7天内)</span>
            </div>
          </template>
          <el-table :data="summary.upcoming_payments" size="small" stripe>
            <el-table-column prop="sales_order_no" label="订单" width="120" />
            <el-table-column prop="customer_name" label="客户" show-overflow-tooltip />
            <el-table-column prop="milestone_name" label="节点" width="90" />
            <el-table-column label="待收" width="100" align="right">
              <template #default="{ row }">¥{{ formatMoney(row.amount_due - row.amount_paid) }}</template>
            </el-table-column>
            <el-table-column label="到期" width="70" align="center">
              <template #default="{ row }">
                <span class="text-warning">{{ row.days_until_due }}天</span>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <!-- 登记收款对话框 -->
    <el-dialog v-model="paymentDialogVisible" title="登记收款" width="450px">
      <el-form :model="paymentForm" label-width="100px">
        <el-form-item label="销售订单">
          <el-input :value="currentSchedule?.sales_order_no" disabled />
        </el-form-item>
        <el-form-item label="客户">
          <el-input :value="currentSchedule?.customer_name" disabled />
        </el-form-item>
        <el-form-item label="付款节点">
          <el-input :value="currentSchedule?.milestone_name" disabled />
        </el-form-item>
        <el-form-item label="应收金额">
          <el-input :value="'¥' + formatMoney(currentSchedule?.amount_due)" disabled />
        </el-form-item>
        <el-form-item label="已收金额">
          <el-input :value="'¥' + formatMoney(currentSchedule?.amount_paid)" disabled />
        </el-form-item>
        <el-form-item label="本次收款" required>
          <el-input-number v-model="paymentForm.amount" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="收款日期">
          <el-date-picker v-model="paymentForm.payment_date" type="date" placeholder="选择日期" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="paymentDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitPayment" :loading="submitting">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import request from '@/utils/request'

// 数据
const schedules = ref([])
const loading = ref(false)
const submitting = ref(false)
const projects = ref([])

const summary = ref({
  total_amount: 0,
  total_paid: 0,
  total_remaining: 0,
  overall_progress: 0,
  pending_count: 0,
  partial_count: 0,
  paid_count: 0,
  overdue_count: 0,
  upcoming_payments: [],
  overdue_payments: []
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const filters = reactive({
  status: '',
  milestone_type: '',
  project: ''
})

// 收款对话框
const paymentDialogVisible = ref(false)
const currentSchedule = ref(null)
const paymentForm = reactive({
  amount: 0,
  payment_date: new Date()
})

// 加载数据
const loadData = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
      ...filters
    }
    const response = await request.get('/finance/payment-schedules/', { params })
    schedules.value = response.results || response
    pagination.total = response.count || schedules.value.length
  } catch (error) {
    console.error('加载付款计划失败:', error)
  } finally {
    loading.value = false
  }
}

const loadSummary = async () => {
  try {
    const params = {}
    if (filters.project) params.project_id = filters.project
    const response = await request.get('/finance/payment-schedules/summary/', { params })
    summary.value = response
  } catch (error) {
    console.error('加载统计信息失败:', error)
  }
}

const loadProjects = async () => {
  try {
    const response = await request.get('/projects/', { params: { is_deleted: false, page_size: 1000 } })
    projects.value = response.results || response
  } catch (error) {
    console.error('加载项目列表失败:', error)
  }
}

const resetFilters = () => {
  filters.status = ''
  filters.milestone_type = ''
  filters.project = ''
  pagination.page = 1
  loadData()
  loadSummary()
}

const handleSizeChange = () => {
  pagination.page = 1
  loadData()
}

// 格式化
const formatMoney = (val) => {
  if (val == null) return '0.00'
  return Number(val).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

const getStatusType = (status) => {
  const types = {
    'PENDING': 'info',
    'PARTIAL': 'warning',
    'PAID': 'success',
    'OVERDUE': 'danger',
    'CANCELLED': ''
  }
  return types[status] || 'info'
}

const getProgressColor = (percentage) => {
  if (percentage >= 100) return '#67c23a'
  if (percentage >= 70) return '#409eff'
  if (percentage >= 30) return '#e6a23c'
  return '#f56c6c'
}

// 操作
const handleRecordPayment = (row) => {
  currentSchedule.value = row
  paymentForm.amount = Number(row.amount_due) - Number(row.amount_paid)
  paymentForm.payment_date = new Date()
  paymentDialogVisible.value = true
}

const submitPayment = async () => {
  if (!paymentForm.amount || paymentForm.amount <= 0) {
    ElMessage.warning('请输入有效的收款金额')
    return
  }
  
  submitting.value = true
  try {
    await request.post(`/finance/payment-schedules/${currentSchedule.value.id}/record_payment/`, {
      amount: paymentForm.amount,
      payment_date: paymentForm.payment_date?.toISOString().split('T')[0]
    })
    ElMessage.success('收款登记成功')
    paymentDialogVisible.value = false
    loadData()
    loadSummary()
  } catch (error) {
    ElMessage.error('收款登记失败: ' + (error.message || '未知错误'))
  } finally {
    submitting.value = false
  }
}

const handleViewDetail = (row) => {
  // 可以跳转到销售订单详情或显示更多信息
  ElMessage.info(`订单: ${row.sales_order_no}, 节点: ${row.milestone_name}`)
}

// 初始化
onMounted(() => {
  loadData()
  loadSummary()
  loadProjects()
})
</script>

<style scoped>
.payment-schedule-list {
  padding: 16px;
}

.summary-cards {
  margin-bottom: 16px;
}

.summary-card {
  text-align: center;
}

.summary-card.warning {
  border-left: 4px solid #f56c6c;
}

.summary-content {
  padding: 8px 0;
}

.summary-label {
  font-size: 14px;
  color: #606266;
  margin-bottom: 8px;
}

.summary-value {
  font-size: 24px;
  font-weight: bold;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.filter-form {
  margin-bottom: 16px;
}

.text-primary {
  color: #409eff;
}

.text-success {
  color: #67c23a;
}

.text-warning {
  color: #e6a23c;
}

.text-danger {
  color: #f56c6c;
}

.text-muted {
  color: #909399;
}

.reminder-cards {
  margin-top: 16px;
}

.reminder-card.danger {
  border-top: 3px solid #f56c6c;
}

.reminder-card.warning {
  border-top: 3px solid #e6a23c;
}
</style>

