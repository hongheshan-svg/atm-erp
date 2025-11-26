<template>
  <div class="ar-list">
    <el-card>
      <template #header><div class="card-header"><span>应收账款管理</span></div></template>

      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="客户">
          <el-select v-model="searchForm.customer" placeholder="请选择客户" clearable filterable>
            <el-option v-for="c in customers" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="请选择状态" clearable>
            <el-option label="未收款" value="UNPAID" />
            <el-option label="部分收款" value="PARTIAL" />
            <el-option label="已收款" value="PAID" />
            <el-option label="已逾期" value="OVERDUE" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadARList">查询</el-button>
          <el-button @click="resetSearch">重置</el-button>
        </el-form-item>
      </el-form>

      <el-table :data="arList" v-loading="loading" border stripe>
        <el-table-column prop="ar_no" label="应收单号" width="150" />
        <el-table-column prop="customer_name" label="客户" width="200" />
        <el-table-column prop="sales_order_no" label="销售订单" width="150" />
        <el-table-column prop="invoice_no" label="发票号" width="150" />
        <el-table-column prop="invoice_date" label="发票日期" width="120" />
        <el-table-column prop="due_date" label="到期日期" width="120" />
        <el-table-column prop="amount_due" label="应收金额" width="130" align="right">
          <template #default="{ row }">¥{{ (row.amount_due || 0).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="amount_paid" label="已收金额" width="130" align="right">
          <template #default="{ row }">¥{{ (row.amount_paid || 0).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column label="未收金额" width="130" align="right">
          <template #default="{ row }">
            <span style="color: #E6A23C; font-weight: 600;">
              ¥{{ ((row.amount_due || 0) - (row.amount_paid || 0)).toFixed(2) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ getStatusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleView(row)">查看</el-button>
            <el-button size="small" type="primary" @click="handlePayment(row)" v-if="row.status !== 'PAID'">登记收款</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        layout="total, sizes, prev, pager, next"
        @size-change="loadARList"
        @current-change="loadARList"
        style="margin-top: 20px; justify-content: flex-end;"
      />
    </el-card>

    <!-- 详情查看对话框 -->
    <el-dialog v-model="viewDialogVisible" title="应收账款详情" width="700px">
      <el-descriptions :column="2" border v-if="currentAR">
        <el-descriptions-item label="应收单号">{{ currentAR.ar_no }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getStatusType(currentAR.status)">{{ getStatusLabel(currentAR.status) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="客户">{{ currentAR.customer_name }}</el-descriptions-item>
        <el-descriptions-item label="销售订单">{{ currentAR.sales_order_no || '-' }}</el-descriptions-item>
        <el-descriptions-item label="发票号">{{ currentAR.invoice_no || '-' }}</el-descriptions-item>
        <el-descriptions-item label="发票日期">{{ currentAR.invoice_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="到期日期">{{ currentAR.due_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="关联项目">{{ currentAR.project_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="应收金额">
          <span style="font-size: 16px; font-weight: 600; color: #409EFF;">
            ¥{{ parseFloat(currentAR.amount_due || 0).toFixed(2) }}
          </span>
        </el-descriptions-item>
        <el-descriptions-item label="已收金额">
          <span style="font-size: 16px; font-weight: 600; color: #67C23A;">
            ¥{{ parseFloat(currentAR.amount_paid || 0).toFixed(2) }}
          </span>
        </el-descriptions-item>
        <el-descriptions-item label="未收金额" :span="2">
          <span style="font-size: 18px; font-weight: 600; color: #E6A23C;">
            ¥{{ (parseFloat(currentAR.amount_due || 0) - parseFloat(currentAR.amount_paid || 0)).toFixed(2) }}
          </span>
        </el-descriptions-item>
        <el-descriptions-item label="创建时间" :span="2">{{ currentAR.created_at }}</el-descriptions-item>
        <el-descriptions-item label="备注" :span="2">{{ currentAR.notes || '-' }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>

    <!-- 收款登记对话框 -->
    <el-dialog v-model="paymentVisible" title="登记收款" width="500px">
      <el-form :model="paymentForm" label-width="100px">
        <el-form-item label="应收金额">
          <span style="font-size: 16px; font-weight: 600;">¥{{ (currentAR.amount_due || 0).toFixed(2) }}</span>
        </el-form-item>
        <el-form-item label="已收金额">
          <span>¥{{ (currentAR.amount_paid || 0).toFixed(2) }}</span>
        </el-form-item>
        <el-form-item label="未收金额">
          <span style="color: #E6A23C;">¥{{ ((currentAR.amount_due || 0) - (currentAR.amount_paid || 0)).toFixed(2) }}</span>
        </el-form-item>
        <el-form-item label="本次收款" required>
          <el-input-number v-model="paymentForm.amount" :min="0" :max="(currentAR.amount_due || 0) - (currentAR.amount_paid || 0)" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="收款日期" required>
          <el-date-picker v-model="paymentForm.payment_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="收款方式">
          <el-select v-model="paymentForm.payment_method" style="width: 100%">
            <el-option label="现金" value="CASH" />
            <el-option label="银行转账" value="BANK" />
            <el-option label="支票" value="CHECK" />
            <el-option label="其他" value="OTHER" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="paymentForm.notes" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="paymentVisible = false">取消</el-button>
        <el-button type="primary" @click="submitPayment">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import request from '@/utils/request'

const loading = ref(false)
const arList = ref([])
const customers = ref([])
const paymentVisible = ref(false)
const viewDialogVisible = ref(false)
const currentAR = ref({})
const searchForm = reactive({ customer: null, status: null })
const pagination = reactive({ page: 1, pageSize: 20, total: 0 })
const paymentForm = reactive({ amount: 0, payment_date: new Date().toISOString().split('T')[0], payment_method: 'BANK', notes: '' })

const getStatusType = (s) => ({ 'UNPAID': 'warning', 'PARTIAL': 'primary', 'PAID': 'success', 'OVERDUE': 'danger' }[s] || 'info')
const getStatusLabel = (s) => ({ 'UNPAID': '未收款', 'PARTIAL': '部分收款', 'PAID': '已收款', 'OVERDUE': '已逾期' }[s] || s)

const loadARList = async () => {
  loading.value = true
  try {
    const params = { page: pagination.page, page_size: pagination.pageSize, ...searchForm }
    Object.keys(params).forEach(k => { if (params[k] === null) delete params[k] })
    const { data } = await request.get('/finance/receivables/', { params })
    arList.value = data.results || []
    pagination.total = data.count || 0
  } catch (error) {
    ElMessage.error('加载应收账款失败')
  } finally {
    loading.value = false
  }
}

const loadCustomers = async () => {
  try {
    const { data } = await request.get('/masterdata/customers/', { params: { page_size: 100 } })
    customers.value = data.results || data
  } catch (error) {
    console.error('加载客户失败:', error)
  }
}

const resetSearch = () => {
  searchForm.customer = null
  searchForm.status = null
  pagination.page = 1
  loadARList()
}

const handleView = (row) => {
  currentAR.value = row
  viewDialogVisible.value = true
}

const handlePayment = (row) => {
  currentAR.value = row
  paymentForm.amount = (row.amount_due || 0) - (row.amount_paid || 0)
  paymentVisible.value = true
}

const submitPayment = async () => {
  if (!paymentForm.amount || paymentForm.amount <= 0) return ElMessage.warning('请输入收款金额')
  try {
    await request.post(`/finance/receivables/${currentAR.value.id}/record_payment/`, paymentForm)
    ElMessage.success('收款登记成功')
    paymentVisible.value = false
    loadARList()
  } catch (error) {
    ElMessage.error('收款登记失败')
  }
}

onMounted(() => {
  loadARList()
  loadCustomers()
})
</script>

<style scoped>
.ar-list { padding: 20px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.search-form { margin-bottom: 20px; }
</style>

