<template>
  <div class="ap-list">
    <el-card>
      <template #header><div class="card-header"><span>应付账款管理</span></div></template>

      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="供应商">
          <el-select v-model="searchForm.supplier" placeholder="请选择供应商" clearable filterable>
            <el-option v-for="s in suppliers" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="请选择状态" clearable>
            <el-option label="未付款" value="UNPAID" />
            <el-option label="部分付款" value="PARTIAL" />
            <el-option label="已付款" value="PAID" />
            <el-option label="已逾期" value="OVERDUE" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadAPList">查询</el-button>
          <el-button @click="resetSearch">重置</el-button>
        </el-form-item>
      </el-form>

      <el-table :data="apList" v-loading="loading" border stripe>
        <el-table-column prop="ap_no" label="应付单号" width="150" />
        <el-table-column prop="supplier_name" label="供应商" width="200" />
        <el-table-column prop="purchase_order_no" label="采购订单" width="150" />
        <el-table-column prop="invoice_no" label="发票号" width="150" />
        <el-table-column prop="invoice_date" label="发票日期" width="120" />
        <el-table-column prop="due_date" label="到期日期" width="120" />
        <el-table-column prop="amount_due" label="应付金额" width="130" align="right">
          <template #default="{ row }">¥{{ (row.amount_due || 0).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="amount_paid" label="已付金额" width="130" align="right">
          <template #default="{ row }">¥{{ (row.amount_paid || 0).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column label="未付金额" width="130" align="right">
          <template #default="{ row }">
            <span style="color: #F56C6C; font-weight: 600;">
              ¥{{ ((row.amount_due || 0) - (row.amount_paid || 0)).toFixed(2) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ getStatusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="240" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleView(row)">查看</el-button>
            <el-button size="small" type="primary" @click="handlePayment(row)" v-if="row.status !== 'PAID'">登记付款</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        layout="total, sizes, prev, pager, next"
        @size-change="loadAPList"
        @current-change="loadAPList"
        style="margin-top: 20px; justify-content: flex-end;"
      />
    </el-card>

    <!-- 详情查看对话框 -->
    <el-dialog v-model="viewDialogVisible" title="应付账款详情" width="700px">
      <el-descriptions :column="2" border v-if="currentAP">
        <el-descriptions-item label="应付单号">{{ currentAP.ap_no }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getStatusType(currentAP.status)">{{ getStatusLabel(currentAP.status) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="供应商">{{ currentAP.supplier_name }}</el-descriptions-item>
        <el-descriptions-item label="采购订单">{{ currentAP.purchase_order_no || '-' }}</el-descriptions-item>
        <el-descriptions-item label="发票号">{{ currentAP.invoice_no || '-' }}</el-descriptions-item>
        <el-descriptions-item label="发票日期">{{ currentAP.invoice_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="到期日期">{{ currentAP.due_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="关联项目">{{ currentAP.project_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="应付金额">
          <span style="font-size: 16px; font-weight: 600; color: #409EFF;">
            ¥{{ parseFloat(currentAP.amount_due || 0).toFixed(2) }}
          </span>
        </el-descriptions-item>
        <el-descriptions-item label="已付金额">
          <span style="font-size: 16px; font-weight: 600; color: #67C23A;">
            ¥{{ parseFloat(currentAP.amount_paid || 0).toFixed(2) }}
          </span>
        </el-descriptions-item>
        <el-descriptions-item label="未付金额" :span="2">
          <span style="font-size: 18px; font-weight: 600; color: #F56C6C;">
            ¥{{ (parseFloat(currentAP.amount_due || 0) - parseFloat(currentAP.amount_paid || 0)).toFixed(2) }}
          </span>
        </el-descriptions-item>
        <el-descriptions-item label="创建时间" :span="2">{{ currentAP.created_at }}</el-descriptions-item>
        <el-descriptions-item label="备注" :span="2">{{ currentAP.notes || '-' }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>

    <!-- 付款登记对话框 -->
    <el-dialog v-model="paymentVisible" title="登记付款" width="500px">
      <el-form :model="paymentForm" label-width="100px">
        <el-form-item label="应付金额">
          <span style="font-size: 16px; font-weight: 600;">¥{{ (currentAP.amount_due || 0).toFixed(2) }}</span>
        </el-form-item>
        <el-form-item label="已付金额">
          <span>¥{{ (currentAP.amount_paid || 0).toFixed(2) }}</span>
        </el-form-item>
        <el-form-item label="未付金额">
          <span style="color: #F56C6C;">¥{{ ((currentAP.amount_due || 0) - (currentAP.amount_paid || 0)).toFixed(2) }}</span>
        </el-form-item>
        <el-form-item label="本次付款" required>
          <el-input-number v-model="paymentForm.amount" :min="0" :max="(currentAP.amount_due || 0) - (currentAP.amount_paid || 0)" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="付款日期" required>
          <el-date-picker v-model="paymentForm.payment_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="付款方式">
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
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/utils/request'

const loading = ref(false)
const apList = ref([])
const suppliers = ref([])
const paymentVisible = ref(false)
const viewDialogVisible = ref(false)
const currentAP = ref({})
const searchForm = reactive({ supplier: null, status: null })
const pagination = reactive({ page: 1, pageSize: 20, total: 0 })
const paymentForm = reactive({ amount: 0, payment_date: new Date().toISOString().split('T')[0], payment_method: 'BANK', notes: '' })

const getStatusType = (s) => ({ 'UNPAID': 'warning', 'PARTIAL': 'primary', 'PAID': 'success', 'OVERDUE': 'danger' }[s] || 'info')
const getStatusLabel = (s) => ({ 'UNPAID': '未付款', 'PARTIAL': '部分付款', 'PAID': '已付款', 'OVERDUE': '已逾期' }[s] || s)

const loadAPList = async () => {
  loading.value = true
  try {
    const params = { page: pagination.page, page_size: pagination.pageSize, ...searchForm }
    Object.keys(params).forEach(k => { if (params[k] === null) delete params[k] })
    const response = await request.get('/finance/payables/', { params })
    apList.value = response.results || []
    pagination.total = response.count || 0
  } catch (error) {
    ElMessage.error('加载应付账款失败')
  } finally {
    loading.value = false
  }
}

const loadSuppliers = async () => {
  try {
    const response = await request.get('/masterdata/suppliers/', { params: { page_size: 100 } })
    suppliers.value = response.results || response || []
  } catch (error) {
    console.error('加载供应商失败:', error)
  }
}

const resetSearch = () => {
  searchForm.supplier = null
  searchForm.status = null
  pagination.page = 1
  loadAPList()
}

const handleView = (row) => {
  currentAP.value = row
  viewDialogVisible.value = true
}

const handlePayment = (row) => {
  currentAP.value = row
  paymentForm.amount = (row.amount_due || 0) - (row.amount_paid || 0)
  paymentVisible.value = true
}

const submitPayment = async () => {
  if (!paymentForm.amount || paymentForm.amount <= 0) return ElMessage.warning('请输入付款金额')
  try {
    await request.post(`/finance/payables/${currentAP.value.id}/record_payment/`, paymentForm)
    ElMessage.success('付款登记成功')
    paymentVisible.value = false
    loadAPList()
  } catch (error) {
    ElMessage.error('付款登记失败')
  }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除此应付账款记录吗？此操作不可恢复！`, 
      '删除应付账款', 
      { type: 'warning' }
    )
    await request.delete(`/finance/payables/${row.id}/`)
    ElMessage.success('应付账款已删除')
    loadAPList()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除应付账款失败')
    }
  }
}

onMounted(() => {
  loadAPList()
  loadSuppliers()
})
</script>

<style scoped>
.ap-list { padding: 20px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.search-form { margin-bottom: 20px; }
</style>

