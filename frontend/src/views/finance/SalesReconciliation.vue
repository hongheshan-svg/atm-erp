<template>
  <div class="sales-reconciliation">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>销售对账管理</span>
          <div class="header-actions">
            <el-button type="primary" @click="handleCreate">
              <el-icon><Plus /></el-icon> 新建对账单
            </el-button>
          </div>
        </div>
      </template>

      <!-- 搜索条件 -->
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="客户">
          <el-select v-model="searchForm.customer" placeholder="选择客户" clearable filterable style="width: 200px;">
            <el-option v-for="c in customers" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="对账期间">
          <el-date-picker v-model="searchForm.period" type="monthrange" range-separator="至" 
            start-placeholder="开始月" end-placeholder="结束月" value-format="YYYY-MM" style="width: 220px;" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="全部" clearable style="width: 120px;">
            <el-option label="草稿" value="DRAFT" />
            <el-option label="待确认" value="PENDING" />
            <el-option label="已确认" value="CONFIRMED" />
            <el-option label="有争议" value="DISPUTED" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadReconciliations">查询</el-button>
          <el-button @click="resetSearch">重置</el-button>
        </el-form-item>
      </el-form>

      <!-- 统计卡片 -->
      <el-row :gutter="16" class="summary-cards">
        <el-col :span="6">
          <div class="summary-card">
            <div class="card-title">本月销售额</div>
            <div class="card-value">¥{{ formatNumber(summary.total_sales) }}</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="summary-card">
            <div class="card-title">已开票金额</div>
            <div class="card-value">¥{{ formatNumber(summary.total_invoiced) }}</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="summary-card">
            <div class="card-title">已收款金额</div>
            <div class="card-value success">¥{{ formatNumber(summary.total_received) }}</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="summary-card">
            <div class="card-title">应收余额</div>
            <div class="card-value warning">¥{{ formatNumber(summary.total_balance) }}</div>
          </div>
        </el-col>
      </el-row>

      <!-- 对账单列表 -->
      <el-table :data="reconciliations" v-loading="loading" stripe border style="margin-top: 16px;">
        <el-table-column prop="reconciliation_no" label="对账单号" width="150" />
        <el-table-column prop="customer_name" label="客户" min-width="180" show-overflow-tooltip />
        <el-table-column label="对账期间" width="180">
          <template #default="{ row }">{{ row.period_start }} ~ {{ row.period_end }}</template>
        </el-table-column>
        <el-table-column label="订单金额" width="120" align="right">
          <template #default="{ row }">¥{{ formatNumber(row.total_order_amount) }}</template>
        </el-table-column>
        <el-table-column label="发货金额" width="120" align="right">
          <template #default="{ row }">¥{{ formatNumber(row.total_delivered_amount) }}</template>
        </el-table-column>
        <el-table-column label="开票金额" width="120" align="right">
          <template #default="{ row }">¥{{ formatNumber(row.total_invoice_amount) }}</template>
        </el-table-column>
        <el-table-column label="已收款" width="120" align="right">
          <template #default="{ row }">
            <span class="success">¥{{ formatNumber(row.total_received_amount) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="余额" width="120" align="right">
          <template #default="{ row }">
            <span :class="row.balance_amount > 0 ? 'warning' : ''">¥{{ formatNumber(row.balance_amount) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">{{ getStatusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click="handleDetail(row)">明细</el-button>
            <el-button size="small" link type="success" @click="handlePrint(row)">打印</el-button>
            <el-button v-if="row.status === 'DRAFT'" size="small" link type="warning" @click="handleSubmit(row)">提交</el-button>
            <el-button v-if="row.status === 'PENDING'" size="small" link type="success" @click="handleConfirm(row)">确认</el-button>
            <el-button v-if="row.status === 'DRAFT'" size="small" link type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        layout="total, sizes, prev, pager, next"
        @size-change="loadReconciliations"
        @current-change="loadReconciliations"
        style="margin-top: 20px; justify-content: flex-end;"
      />
    </el-card>

    <!-- 新建对账单对话框 -->
    <el-dialog v-model="createDialogVisible" title="新建销售对账单" width="600px">
      <el-form :model="createForm" ref="createFormRef" label-width="100px" :rules="createRules">
        <el-form-item label="客户" prop="customer">
          <el-select v-model="createForm.customer" placeholder="选择客户" filterable style="width: 100%;">
            <el-option v-for="c in customers" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="对账期间" prop="period">
          <el-date-picker v-model="createForm.period" type="monthrange" range-separator="至"
            start-placeholder="开始月" end-placeholder="结束月" value-format="YYYY-MM-DD" style="width: 100%;" />
        </el-form-item>
        <el-form-item label="期初余额">
          <el-input-number v-model="createForm.opening_balance" :precision="2" style="width: 100%;" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="createForm.notes" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitCreate" :loading="submitting">创建并生成明细</el-button>
      </template>
    </el-dialog>

    <!-- 对账明细对话框 -->
    <el-dialog v-model="detailDialogVisible" :title="`对账明细 - ${currentReconciliation?.reconciliation_no || ''}`" width="95%" top="3vh">
      <div v-if="currentReconciliation">
        <!-- 客户信息和汇总 -->
        <el-descriptions :column="4" border size="small" class="detail-header">
          <el-descriptions-item label="客户">{{ currentReconciliation.customer_name }}</el-descriptions-item>
          <el-descriptions-item label="对账期间">{{ currentReconciliation.period_start }} ~ {{ currentReconciliation.period_end }}</el-descriptions-item>
          <el-descriptions-item label="期初余额">¥{{ formatNumber(currentReconciliation.opening_balance) }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getStatusType(currentReconciliation.status)" size="small">{{ getStatusText(currentReconciliation.status) }}</el-tag>
          </el-descriptions-item>
        </el-descriptions>

        <!-- 三方匹配汇总 -->
        <el-row :gutter="16" class="match-summary">
          <el-col :span="6">
            <div class="match-card order">
              <div class="match-title">销售订单</div>
              <div class="match-value">¥{{ formatNumber(currentReconciliation.total_order_amount) }}</div>
              <div class="match-count">{{ orderLines.length }} 笔</div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="match-card delivery">
              <div class="match-title">发货单</div>
              <div class="match-value">¥{{ formatNumber(currentReconciliation.total_delivered_amount) }}</div>
              <div class="match-count">{{ deliveryLines.length }} 笔</div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="match-card invoice">
              <div class="match-title">销售发票</div>
              <div class="match-value">¥{{ formatNumber(currentReconciliation.total_invoice_amount) }}</div>
              <div class="match-count">{{ invoiceLines.length }} 笔</div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="match-card receipt">
              <div class="match-title">收款记录</div>
              <div class="match-value success">¥{{ formatNumber(currentReconciliation.total_received_amount) }}</div>
              <div class="match-count">{{ receiptLines.length }} 笔</div>
            </div>
          </el-col>
        </el-row>

        <!-- 明细标签页 -->
        <el-tabs v-model="detailTab" style="margin-top: 16px;">
          <el-tab-pane label="销售订单" name="order">
            <el-table :data="orderLines" border stripe max-height="350" size="small">
              <el-table-column prop="reference_no" label="订单号" width="140" />
              <el-table-column prop="reference_date" label="订单日期" width="100" />
              <el-table-column prop="description" label="摘要" min-width="200" show-overflow-tooltip />
              <el-table-column label="订单金额" width="120" align="right">
                <template #default="{ row }">¥{{ formatNumber(row.order_amount) }}</template>
              </el-table-column>
              <el-table-column label="已发货" width="100" align="right">
                <template #default="{ row }">¥{{ formatNumber(row.delivered_amount) }}</template>
              </el-table-column>
              <el-table-column label="已开票" width="100" align="right">
                <template #default="{ row }">¥{{ formatNumber(row.invoice_amount) }}</template>
              </el-table-column>
              <el-table-column label="已收款" width="100" align="right">
                <template #default="{ row }">
                  <span class="success">¥{{ formatNumber(row.received_amount) }}</span>
                </template>
              </el-table-column>
              <el-table-column label="匹配状态" width="100">
                <template #default="{ row }">
                  <el-tag :type="getMatchType(row)" size="small">{{ getMatchText(row) }}</el-tag>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>

          <el-tab-pane label="发货单" name="delivery">
            <el-table :data="deliveryLines" border stripe max-height="350" size="small">
              <el-table-column prop="reference_no" label="发货单号" width="140" />
              <el-table-column prop="reference_date" label="发货日期" width="100" />
              <el-table-column prop="description" label="摘要" min-width="200" show-overflow-tooltip />
              <el-table-column label="发货金额" width="120" align="right">
                <template #default="{ row }">¥{{ formatNumber(row.amount) }}</template>
              </el-table-column>
              <el-table-column prop="delivery_confirmed" label="客户确认" width="90" align="center">
                <template #default="{ row }">
                  <el-tag v-if="row.delivery_confirmed" type="success" size="small">已确认</el-tag>
                  <el-tag v-else type="warning" size="small">待确认</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="100" v-if="currentReconciliation.status !== 'CONFIRMED'">
                <template #default="{ row }">
                  <el-button v-if="!row.delivery_confirmed" size="small" link type="primary" @click="confirmDelivery(row)">确认收货</el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>

          <el-tab-pane label="发票" name="invoice">
            <el-table :data="invoiceLines" border stripe max-height="350" size="small">
              <el-table-column prop="reference_no" label="发票号" width="160" />
              <el-table-column prop="reference_date" label="开票日期" width="100" />
              <el-table-column prop="description" label="摘要" min-width="200" show-overflow-tooltip />
              <el-table-column label="发票金额" width="120" align="right">
                <template #default="{ row }">¥{{ formatNumber(row.amount) }}</template>
              </el-table-column>
              <el-table-column label="税额" width="100" align="right">
                <template #default="{ row }">¥{{ formatNumber(row.tax_amount) }}</template>
              </el-table-column>
            </el-table>
          </el-tab-pane>

          <el-tab-pane label="收款记录" name="receipt">
            <el-table :data="receiptLines" border stripe max-height="350" size="small">
              <el-table-column prop="reference_no" label="收款单号" width="140" />
              <el-table-column prop="reference_date" label="收款日期" width="100" />
              <el-table-column prop="description" label="摘要" min-width="200" show-overflow-tooltip />
              <el-table-column label="收款金额" width="120" align="right">
                <template #default="{ row }">
                  <span class="success">¥{{ formatNumber(row.amount) }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="payment_method" label="收款方式" width="100" />
            </el-table>
          </el-tab-pane>

          <el-tab-pane label="账龄分析" name="aging">
            <el-row :gutter="16">
              <el-col :span="16">
                <el-table :data="agingData" border stripe size="small">
                  <el-table-column prop="range" label="账龄区间" width="150" />
                  <el-table-column label="应收金额" align="right">
                    <template #default="{ row }">¥{{ formatNumber(row.amount) }}</template>
                  </el-table-column>
                  <el-table-column label="占比" width="120" align="center">
                    <template #default="{ row }">
                      <el-progress :percentage="row.percent" :stroke-width="10" />
                    </template>
                  </el-table-column>
                  <el-table-column label="笔数" width="80" align="center">
                    <template #default="{ row }">{{ row.count }}</template>
                  </el-table-column>
                </el-table>
              </el-col>
              <el-col :span="8">
                <div class="aging-summary">
                  <div class="aging-item">
                    <span class="label">应收总额</span>
                    <span class="value">¥{{ formatNumber(currentReconciliation.balance_amount) }}</span>
                  </div>
                  <div class="aging-item warning">
                    <span class="label">逾期金额</span>
                    <span class="value">¥{{ formatNumber(agingOverdue) }}</span>
                  </div>
                  <div class="aging-item">
                    <span class="label">逾期占比</span>
                    <span class="value">{{ agingOverduePercent }}%</span>
                  </div>
                </div>
              </el-col>
            </el-row>
          </el-tab-pane>
        </el-tabs>

        <!-- 期末汇总 -->
        <div class="closing-summary">
          <el-descriptions :column="5" border size="small">
            <el-descriptions-item label="期初余额">¥{{ formatNumber(currentReconciliation.opening_balance) }}</el-descriptions-item>
            <el-descriptions-item label="本期发生">¥{{ formatNumber(currentReconciliation.total_invoice_amount) }}</el-descriptions-item>
            <el-descriptions-item label="本期收款">¥{{ formatNumber(currentReconciliation.total_received_amount) }}</el-descriptions-item>
            <el-descriptions-item label="期末余额">
              <span class="warning" style="font-weight: bold; font-size: 16px;">¥{{ formatNumber(currentReconciliation.closing_balance) }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="差额">
              <span :class="currentReconciliation.balance_amount !== 0 ? 'danger' : 'success'">
                ¥{{ formatNumber(currentReconciliation.balance_amount) }}
              </span>
            </el-descriptions-item>
          </el-descriptions>
        </div>
      </div>
      <template #footer>
        <el-button @click="detailDialogVisible = false">关闭</el-button>
        <el-button type="primary" @click="handlePrint(currentReconciliation)">打印对账单</el-button>
        <el-button v-if="currentReconciliation?.status === 'PENDING'" type="success" @click="handleConfirm(currentReconciliation)">确认对账</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import request from '@/utils/request'

const loading = ref(false)
const submitting = ref(false)
const reconciliations = ref([])
const customers = ref([])
const createDialogVisible = ref(false)
const detailDialogVisible = ref(false)
const currentReconciliation = ref(null)
const reconciliationLines = ref([])
const detailTab = ref('order')

const pagination = reactive({ page: 1, pageSize: 20, total: 0 })
const searchForm = reactive({ customer: null, period: null, status: null })
const summary = reactive({ total_sales: 0, total_invoiced: 0, total_received: 0, total_balance: 0 })

const createFormRef = ref(null)
const createForm = reactive({
  customer: null,
  period: null,
  opening_balance: 0,
  notes: ''
})
const createRules = {
  customer: [{ required: true, message: '请选择客户', trigger: 'change' }],
  period: [{ required: true, message: '请选择对账期间', trigger: 'change' }]
}

// 分类明细行
const orderLines = computed(() => reconciliationLines.value.filter(l => l.line_type === 'ORDER'))
const deliveryLines = computed(() => reconciliationLines.value.filter(l => l.line_type === 'DELIVERY'))
const invoiceLines = computed(() => reconciliationLines.value.filter(l => l.line_type === 'INVOICE'))
const receiptLines = computed(() => reconciliationLines.value.filter(l => l.line_type === 'RECEIPT'))

// 账龄数据
const agingData = computed(() => {
  if (!currentReconciliation.value) return []
  const balance = currentReconciliation.value.balance_amount || 0
  // 模拟账龄分布
  return [
    { range: '0-30天（未到期）', amount: balance * 0.4, percent: 40, count: 3 },
    { range: '31-60天', amount: balance * 0.25, percent: 25, count: 2 },
    { range: '61-90天', amount: balance * 0.2, percent: 20, count: 2 },
    { range: '90天以上（逾期）', amount: balance * 0.15, percent: 15, count: 1 }
  ]
})

const agingOverdue = computed(() => {
  return agingData.value.filter(a => a.range.includes('逾期')).reduce((s, a) => s + a.amount, 0)
})

const agingOverduePercent = computed(() => {
  const total = currentReconciliation.value?.balance_amount || 1
  return Math.round(agingOverdue.value / total * 100)
})

const formatNumber = (num) => {
  if (!num) return '0.00'
  return parseFloat(num).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

const getStatusType = (status) => {
  const types = { DRAFT: 'info', PENDING: 'warning', CONFIRMED: 'success', DISPUTED: 'danger', CLOSED: '' }
  return types[status] || 'info'
}

const getStatusText = (status) => {
  const texts = { DRAFT: '草稿', PENDING: '待确认', CONFIRMED: '已确认', DISPUTED: '有争议', CLOSED: '已关闭' }
  return texts[status] || status
}

const getMatchType = (row) => {
  if (row.received_amount >= row.invoice_amount && row.invoice_amount > 0) return 'success'
  if (row.invoice_amount > 0) return 'warning'
  return 'info'
}

const getMatchText = (row) => {
  if (row.received_amount >= row.invoice_amount && row.invoice_amount > 0) return '已结清'
  if (row.invoice_amount > 0) return '部分收款'
  return '待开票'
}

const loadCustomers = async () => {
  try {
    const res = await request.get('/masterdata/customers/', { params: { page_size: 1000, status: 'ACTIVE' } })
    customers.value = res.results || res || []
  } catch (error) {
    console.error('Load customers failed:', error)
  }
}

const loadReconciliations = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
      ...searchForm
    }
    if (searchForm.period?.length === 2) {
      params.period_start = searchForm.period[0]
      params.period_end = searchForm.period[1]
    }
    delete params.period
    Object.keys(params).forEach(k => { if (params[k] === null || params[k] === '') delete params[k] })
    
    const res = await request.get('/finance/sales-reconciliations/', { params })
    reconciliations.value = res.results || res || []
    pagination.total = res.count || 0
    
    // 加载汇总
    loadSummary()
  } catch (error) {
    ElMessage.error('加载对账单失败')
  } finally {
    loading.value = false
  }
}

const loadSummary = async () => {
  try {
    const res = await request.get('/finance/sales-reconciliations/customer_summary/')
    if (res) {
      summary.total_sales = res.total_order_amount || 0
      summary.total_invoiced = res.total_invoice_amount || 0
      summary.total_received = res.total_received_amount || 0
      summary.total_balance = res.total_balance || 0
    }
  } catch (error) {
    console.error('Load summary failed:', error)
  }
}

const resetSearch = () => {
  searchForm.customer = null
  searchForm.period = null
  searchForm.status = null
  pagination.page = 1
  loadReconciliations()
}

const handleCreate = () => {
  Object.assign(createForm, { customer: null, period: null, opening_balance: 0, notes: '' })
  createDialogVisible.value = true
}

const submitCreate = async () => {
  try {
    await createFormRef.value.validate()
    submitting.value = true
    
    const data = {
      customer: createForm.customer,
      period_start: createForm.period[0],
      period_end: createForm.period[1],
      opening_balance: createForm.opening_balance,
      notes: createForm.notes
    }
    
    const res = await request.post('/finance/sales-reconciliations/', data)
    
    // 自动生成明细
    await request.post(`/finance/sales-reconciliations/${res.id}/generate_lines/`)
    
    ElMessage.success('对账单创建成功')
    createDialogVisible.value = false
    loadReconciliations()
    
    // 打开明细
    handleDetail(res)
  } catch (error) {
    ElMessage.error('创建失败: ' + (error.response?.data?.error || error.message))
  } finally {
    submitting.value = false
  }
}

const handleDetail = async (row) => {
  try {
    const res = await request.get(`/finance/sales-reconciliations/${row.id}/`)
    currentReconciliation.value = res
    reconciliationLines.value = res.lines || []
    detailTab.value = 'order'
    detailDialogVisible.value = true
  } catch (error) {
    ElMessage.error('加载明细失败')
  }
}

const handleSubmit = async (row) => {
  try {
    await ElMessageBox.confirm('确定提交此对账单吗？提交后将发送给客户确认。', '提交确认')
    await request.post(`/finance/sales-reconciliations/${row.id}/submit/`)
    ElMessage.success('提交成功')
    loadReconciliations()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('提交失败')
    }
  }
}

const handleConfirm = async (row) => {
  try {
    await ElMessageBox.confirm('确定确认此对账单吗？确认后将完成对账。', '确认对账')
    await request.post(`/finance/sales-reconciliations/${row.id}/confirm/`)
    ElMessage.success('确认成功')
    loadReconciliations()
    if (detailDialogVisible.value) {
      handleDetail(row)
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('确认失败')
    }
  }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定删除此对账单吗？', '删除确认', { type: 'warning' })
    await request.delete(`/finance/sales-reconciliations/${row.id}/`)
    ElMessage.success('删除成功')
    loadReconciliations()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const confirmDelivery = async (line) => {
  try {
    await request.post(`/finance/sales-reconciliation-lines/${line.id}/confirm_delivery/`)
    ElMessage.success('确认收货成功')
    handleDetail(currentReconciliation.value)
  } catch (error) {
    ElMessage.error('确认失败')
  }
}

const handlePrint = (row) => {
  const printWindow = window.open('', '_blank')
  const html = generatePrintHtml(row)
  printWindow.document.write(html)
  printWindow.document.close()
  printWindow.focus()
}

const generatePrintHtml = (data) => {
  return `<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>销售对账单 - ${data.reconciliation_no}</title>
<style>
@page { size: A4; margin: 10mm; }
body { font-family: '宋体', serif; font-size: 12px; }
.header { text-align: center; margin-bottom: 20px; }
.header h2 { margin: 0; }
.info-table { width: 100%; margin-bottom: 15px; }
.info-table td { padding: 5px; }
table.data { width: 100%; border-collapse: collapse; margin-bottom: 15px; }
table.data th, table.data td { border: 1px solid #000; padding: 5px; text-align: center; }
table.data th { background: #f0f0f0; }
.summary { margin-top: 20px; }
.signature { margin-top: 40px; display: flex; justify-content: space-between; }
.sig-box { width: 40%; }
@media print { body { padding: 0; } }
</style>
</head>
<body>
<div class="header">
  <h2>销售对账单</h2>
  <p>对账单号：${data.reconciliation_no}</p>
</div>
<table class="info-table">
  <tr>
    <td>客户名称：${data.customer_name}</td>
    <td>对账期间：${data.period_start} ~ ${data.period_end}</td>
  </tr>
</table>
<table class="data">
  <tr><th>项目</th><th>金额（元）</th></tr>
  <tr><td>期初余额</td><td>${formatNumber(data.opening_balance)}</td></tr>
  <tr><td>本期销售</td><td>${formatNumber(data.total_order_amount)}</td></tr>
  <tr><td>本期发货</td><td>${formatNumber(data.total_delivered_amount)}</td></tr>
  <tr><td>本期开票</td><td>${formatNumber(data.total_invoice_amount)}</td></tr>
  <tr><td>本期收款</td><td>${formatNumber(data.total_received_amount)}</td></tr>
  <tr><td><b>期末余额</b></td><td><b>${formatNumber(data.closing_balance)}</b></td></tr>
</table>
<div class="signature">
  <div class="sig-box">甲方（供方）确认：<br><br>日期：</div>
  <div class="sig-box">乙方（需方）确认：<br><br>日期：</div>
</div>
<script>window.print()<\/script>
</body>
</html>`
}

onMounted(() => {
  loadCustomers()
  loadReconciliations()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.search-form {
  margin-bottom: 16px;
}
.summary-cards {
  margin-bottom: 16px;
}
.summary-card {
  background: #f5f7fa;
  padding: 16px;
  border-radius: 4px;
  text-align: center;
}
.summary-card .card-title {
  font-size: 13px;
  color: #909399;
}
.summary-card .card-value {
  font-size: 24px;
  font-weight: bold;
  margin-top: 8px;
}
.success { color: #67c23a; }
.warning { color: #e6a23c; }
.danger { color: #f56c6c; }

.detail-header {
  margin-bottom: 16px;
}
.match-summary {
  margin-top: 16px;
}
.match-card {
  padding: 16px;
  border-radius: 4px;
  text-align: center;
  border-left: 4px solid;
}
.match-card.order { background: #ecf5ff; border-color: #409eff; }
.match-card.delivery { background: #f0f9eb; border-color: #67c23a; }
.match-card.invoice { background: #fdf6ec; border-color: #e6a23c; }
.match-card.receipt { background: #f0f9eb; border-color: #67c23a; }
.match-title { font-size: 13px; color: #606266; }
.match-value { font-size: 20px; font-weight: bold; margin: 8px 0; }
.match-count { font-size: 12px; color: #909399; }

.closing-summary {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 2px solid #409eff;
}

.aging-summary {
  padding: 20px;
  background: #f5f7fa;
  border-radius: 4px;
}
.aging-item {
  display: flex;
  justify-content: space-between;
  padding: 10px 0;
  border-bottom: 1px dashed #e4e7ed;
}
.aging-item .label { color: #606266; }
.aging-item .value { font-weight: bold; font-size: 16px; }
.aging-item.warning .value { color: #e6a23c; }
</style>
