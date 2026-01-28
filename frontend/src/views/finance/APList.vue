<template>
  <div class="ap-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>应付账款</span>
          <el-button type="success" @click="exportAP">
            <el-icon><Download /></el-icon> 导出
          </el-button>
        </div>
      </template>

      <!-- 统计卡片 -->
      <el-row :gutter="16" class="summary-row">
        <el-col :span="6">
          <div class="summary-card">
            <div class="summary-label">应付总额</div>
            <div class="summary-value text-primary">¥{{ formatNumber(summary.total_due) }}</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="summary-card">
            <div class="summary-label">已付总额</div>
            <div class="summary-value text-success">¥{{ formatNumber(summary.total_paid) }}</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="summary-card">
            <div class="summary-label">待付总额</div>
            <div class="summary-value text-warning">¥{{ formatNumber(summary.total_remaining) }}</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="summary-card danger">
            <div class="summary-label">逾期金额</div>
            <div class="summary-value text-danger">¥{{ formatNumber(summary.overdue_amount) }}</div>
          </div>
        </el-col>
      </el-row>

      <!-- 筛选条件 -->
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="供应商">
          <el-select v-model="searchForm.supplier" placeholder="全部供应商" clearable filterable style="width: 180px;">
            <el-option v-for="s in suppliers" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="全部状态" clearable style="width: 120px;">
            <el-option label="未付款" value="UNPAID" />
            <el-option label="部分付款" value="PARTIAL" />
            <el-option label="已付款" value="PAID" />
            <el-option label="已逾期" value="OVERDUE" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadData">查询</el-button>
          <el-button @click="resetSearch">重置</el-button>
        </el-form-item>
      </el-form>

      <!-- 数据表格 -->
      <el-table :data="dataList" v-loading="loading" border stripe>
        <el-table-column type="index" label="#" width="50" align="center" />
        <el-table-column prop="supplier_name" label="供应商" min-width="120" show-overflow-tooltip />
        <el-table-column prop="purchase_order_no" label="采购订单" width="130" show-overflow-tooltip />
        <el-table-column prop="invoice_no" label="发票号" width="120" show-overflow-tooltip>
          <template #default="{ row }">{{ row.invoice_no || '-' }}</template>
        </el-table-column>
        <el-table-column label="应付金额" width="110" align="right">
          <template #default="{ row }">
            <span class="text-primary">¥{{ formatNumber(row.amount_due) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="已付金额" width="110" align="right">
          <template #default="{ row }">
            <span class="text-success">¥{{ formatNumber(row.amount_paid) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="待付金额" width="110" align="right">
          <template #default="{ row }">
            <span :class="getRemaining(row) > 0 ? 'text-warning' : ''">
              ¥{{ formatNumber(getRemaining(row)) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="付款进度" width="120">
          <template #default="{ row }">
            <el-progress 
              :percentage="getProgress(row)" 
              :stroke-width="8"
              :color="getProgressColor(getProgress(row))"
            />
          </template>
        </el-table-column>
        <el-table-column prop="due_date" label="到期日" width="100" />
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">{{ getStatusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click="handlePayment(row)" v-if="row.status !== 'PAID'">付款</el-button>
            <el-button size="small" link @click="handleView(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        layout="total, sizes, prev, pager, next"
        @size-change="loadData"
        @current-change="loadData"
        style="margin-top: 20px; justify-content: flex-end;"
      />
    </el-card>

    <!-- 详情对话框 -->
    <el-dialog v-model="viewVisible" title="应付账款详情" width="600px">
      <el-descriptions :column="2" border v-if="currentRow">
        <el-descriptions-item label="供应商">{{ currentRow.supplier_name }}</el-descriptions-item>
        <el-descriptions-item label="采购订单">{{ currentRow.purchase_order_no || '-' }}</el-descriptions-item>
        <el-descriptions-item label="发票号">{{ currentRow.invoice_no || '-' }}</el-descriptions-item>
        <el-descriptions-item label="到期日期">{{ currentRow.due_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="应付金额">
          <span class="text-primary">¥{{ formatNumber(currentRow.amount_due) }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="已付金额">
          <span class="text-success">¥{{ formatNumber(currentRow.amount_paid) }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="待付金额" :span="2">
          <span class="text-warning" style="font-size: 18px;">¥{{ formatNumber(getRemaining(currentRow)) }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getStatusType(currentRow.status)">{{ getStatusLabel(currentRow.status) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ currentRow.created_at }}</el-descriptions-item>
        <el-descriptions-item label="备注" :span="2">{{ currentRow.notes || '-' }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>

    <!-- 付款登记对话框 -->
    <el-dialog v-model="paymentVisible" title="登记付款" width="450px">
      <el-form :model="paymentForm" label-width="90px" v-if="currentRow">
        <el-form-item label="供应商">
          <el-input :value="currentRow.supplier_name" disabled />
        </el-form-item>
        <el-form-item label="待付金额">
          <el-input :value="'¥' + formatNumber(getRemaining(currentRow))" disabled />
        </el-form-item>
        <el-form-item label="本次付款" required>
          <el-input-number v-model="paymentForm.amount" :min="0" :max="getRemaining(currentRow)" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="付款日期" required>
          <el-date-picker v-model="paymentForm.payment_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="付款方式">
          <el-select v-model="paymentForm.payment_method" style="width: 100%">
            <el-option label="银行转账" value="BANK" />
            <el-option label="现金" value="CASH" />
            <el-option label="支票" value="CHECK" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="paymentForm.notes" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="paymentVisible = false">取消</el-button>
        <el-button type="primary" @click="submitPayment" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Download } from '@element-plus/icons-vue'
import request from '@/utils/request'

const loading = ref(false)
const submitting = ref(false)
const dataList = ref([])
const suppliers = ref([])
const currentRow = ref(null)

const viewVisible = ref(false)
const paymentVisible = ref(false)

const summary = reactive({
  total_due: 0,
  total_paid: 0,
  total_remaining: 0,
  overdue_amount: 0
})

const searchForm = reactive({ supplier: null, status: null })
const pagination = reactive({ page: 1, pageSize: 20, total: 0 })
const paymentForm = reactive({
  amount: 0,
  payment_date: new Date().toISOString().split('T')[0],
  payment_method: 'BANK',
  notes: ''
})

const formatNumber = (num) => parseFloat(num || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const getRemaining = (row) => (parseFloat(row?.amount_due) || 0) - (parseFloat(row?.amount_paid) || 0)
const getProgress = (row) => {
  const due = parseFloat(row?.amount_due) || 0
  const paid = parseFloat(row?.amount_paid) || 0
  return due > 0 ? Math.min(100, Math.round((paid / due) * 100)) : 0
}

const getProgressColor = (p) => {
  if (p >= 100) return '#67c23a'
  if (p >= 50) return '#409eff'
  return '#e6a23c'
}

const getStatusType = (s) => ({ UNPAID: 'warning', PARTIAL: 'primary', PAID: 'success', OVERDUE: 'danger' }[s] || 'info')
const getStatusLabel = (s) => ({ UNPAID: '未付款', PARTIAL: '部分付款', PAID: '已付款', OVERDUE: '已逾期' }[s] || s)

const loadData = async () => {
  loading.value = true
  try {
    const params = { page: pagination.page, page_size: pagination.pageSize, ...searchForm }
    Object.keys(params).forEach(k => { if (params[k] === null) delete params[k] })
    const res = await request.get('/finance/payables/', { params })
    dataList.value = res.results || []
    pagination.total = res.count || 0
    
    // 计算汇总
    summary.total_due = dataList.value.reduce((sum, r) => sum + parseFloat(r.amount_due || 0), 0)
    summary.total_paid = dataList.value.reduce((sum, r) => sum + parseFloat(r.amount_paid || 0), 0)
    summary.total_remaining = summary.total_due - summary.total_paid
    summary.overdue_amount = dataList.value.filter(r => r.status === 'OVERDUE').reduce((sum, r) => sum + getRemaining(r), 0)
  } catch (error) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

const loadSuppliers = async () => {
  try {
    const res = await request.get('/masterdata/suppliers/', { params: { page_size: 500 } })
    suppliers.value = res.results || res || []
  } catch (error) {
    console.error('加载供应商失败')
  }
}

const resetSearch = () => {
  searchForm.supplier = null
  searchForm.status = null
  pagination.page = 1
  loadData()
}

const handleView = (row) => {
  currentRow.value = row
  viewVisible.value = true
}

const handlePayment = (row) => {
  currentRow.value = row
  paymentForm.amount = getRemaining(row)
  paymentForm.payment_date = new Date().toISOString().split('T')[0]
  paymentForm.payment_method = 'BANK'
  paymentForm.notes = ''
  paymentVisible.value = true
}

const submitPayment = async () => {
  if (!paymentForm.amount || paymentForm.amount <= 0) {
    return ElMessage.warning('请输入付款金额')
  }
  submitting.value = true
  try {
    await request.post(`/finance/payables/${currentRow.value.id}/record_payment/`, paymentForm)
    ElMessage.success('付款登记成功')
    paymentVisible.value = false
    loadData()
  } catch (error) {
    ElMessage.error('付款登记失败')
  } finally {
    submitting.value = false
  }
}

const exportAP = async () => {
  try {
    const res = await request.get('/core/export/ap/', { responseType: 'blob' })
    const url = window.URL.createObjectURL(res.data)
    const link = document.createElement('a')
    link.href = url
    link.download = `应付账款_${new Date().toISOString().split('T')[0]}.xlsx`
    link.click()
    window.URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch (error) {
    ElMessage.error('导出失败')
  }
}

onMounted(() => {
  loadData()
  loadSuppliers()
})
</script>

<style scoped>
.ap-list { padding: 20px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.summary-row { margin-bottom: 20px; }
.summary-card { 
  background: #f5f7fa; 
  padding: 16px; 
  border-radius: 8px; 
  text-align: center;
}
.summary-card.danger { background: #fef0f0; }
.summary-label { font-size: 13px; color: #909399; margin-bottom: 8px; }
.summary-value { font-size: 20px; font-weight: bold; }
.search-form { margin-bottom: 16px; }
.text-primary { color: #409eff; font-weight: 500; }
.text-success { color: #67c23a; font-weight: 500; }
.text-warning { color: #e6a23c; font-weight: 500; }
.text-danger { color: #f56c6c; font-weight: 500; }
</style>
