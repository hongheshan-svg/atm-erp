<template>
  <div class="purchase-reconciliation">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>采购对账管理</span>
          <div class="header-actions">
            <el-button type="primary" v-permission="'finance:purchase_reconciliation:create'" @click="handleCreate">
              <el-icon><Plus /></el-icon> 新建对账单
            </el-button>
          </div>
        </div>
      </template>

      <!-- 搜索条件 -->
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="供应商">
          <el-select v-model="searchForm.supplier" placeholder="选择供应商" clearable filterable style="width: 200px;">
            <el-option v-for="s in suppliers" :key="s.id" :label="s.name" :value="s.id" />
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
            <div class="card-title">本月采购额</div>
            <div class="card-value">¥{{ formatNumber(summary.total_purchase) }}</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="summary-card">
            <div class="card-title">已收票金额</div>
            <div class="card-value">¥{{ formatNumber(summary.total_invoiced) }}</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="summary-card">
            <div class="card-title">已付款金额</div>
            <div class="card-value success">¥{{ formatNumber(summary.total_paid) }}</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="summary-card">
            <div class="card-title">应付余额</div>
            <div class="card-value warning">¥{{ formatNumber(summary.total_balance) }}</div>
          </div>
        </el-col>
      </el-row>

      <!-- 对账单列表 -->
      <!-- 批量操作 -->
      <div v-if="selectedRows.length > 0" class="batch-toolbar">
        <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>
        <el-button type="danger" size="small" @click="batchDelete">批量删除</el-button>
        <el-button size="small" @click="batchExport">导出选中</el-button>
      </div>
      <el-table :data="reconciliations" v-loading="loading" stripe border style="margin-top: 16px;" @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="45" />
        <el-table-column prop="reconciliation_no" label="对账单号" width="150" />
        <el-table-column prop="supplier_name" label="供应商" min-width="180" show-overflow-tooltip />
        <el-table-column label="对账期间" width="180">
          <template #default="{ row }">{{ row.period_start }} ~ {{ row.period_end }}</template>
        </el-table-column>
        <el-table-column label="订单金额" width="120" align="right">
          <template #default="{ row }">¥{{ formatNumber(row.total_order_amount) }}</template>
        </el-table-column>
        <el-table-column label="收货金额" width="120" align="right">
          <template #default="{ row }">¥{{ formatNumber(row.total_received_amount) }}</template>
        </el-table-column>
        <el-table-column label="发票金额" width="120" align="right">
          <template #default="{ row }">¥{{ formatNumber(row.total_invoice_amount) }}</template>
        </el-table-column>
        <el-table-column label="已付款" width="120" align="right">
          <template #default="{ row }">
            <span class="success">¥{{ formatNumber(row.total_paid_amount) }}</span>
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
            <el-button v-if="row.status === 'DRAFT'" size="small" link type="danger" v-permission="'finance:purchase_reconciliation:delete'" @click="handleDelete(row)">删除</el-button>
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
    <el-dialog v-model="createDialogVisible" title="新建采购对账单" width="600px">
      <el-form :model="createForm" ref="createFormRef" label-width="100px" :rules="createRules">
        <el-form-item label="供应商" prop="supplier">
          <el-select v-model="createForm.supplier" placeholder="选择供应商" filterable style="width: 100%;" @change="fetchOpeningBalance">
            <el-option v-for="s in suppliers" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="对账期间" prop="period">
          <el-date-picker v-model="createForm.period" type="daterange" range-separator="至"
            start-placeholder="开始日期" end-placeholder="结束日期" format="YYYY-MM-DD" value-format="YYYY-MM-DD" style="width: 100%;" />
        </el-form-item>
        <el-form-item label="期初余额">
          <el-input-number v-model="createForm.opening_balance" :precision="2" style="width: 100%;" />
          <div class="form-tip">选择供应商后自动计算，可手动修改</div>
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
        <!-- 供应商信息和汇总 -->
        <el-descriptions :column="4" border size="small" class="detail-header">
          <el-descriptions-item label="供应商">{{ currentReconciliation.supplier_name }}</el-descriptions-item>
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
              <div class="match-title">采购订单</div>
              <div class="match-value">¥{{ formatNumber(currentReconciliation.total_order_amount) }}</div>
              <div class="match-count">{{ orderLines.length }} 笔</div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="match-card receipt">
              <div class="match-title">收货单</div>
              <div class="match-value">¥{{ formatNumber(currentReconciliation.total_received_amount) }}</div>
              <div class="match-count">{{ receiptLines.length }} 笔</div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="match-card invoice">
              <div class="match-title">采购发票</div>
              <div class="match-value">¥{{ formatNumber(currentReconciliation.total_invoice_amount) }}</div>
              <div class="match-count">{{ invoiceLines.length }} 笔</div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="match-card payment">
              <div class="match-title">付款记录</div>
              <div class="match-value success">¥{{ formatNumber(currentReconciliation.total_paid_amount) }}</div>
              <div class="match-count">{{ paymentLines.length }} 笔</div>
            </div>
          </el-col>
        </el-row>

        <!-- 三方匹配验证 -->
        <el-alert v-if="matchStatus.hasIssue" :type="matchStatus.type" :closable="false" style="margin-top: 16px;">
          <template #title>
            <span style="font-weight: bold;">{{ matchStatus.title }}</span>
          </template>
          <div v-for="(issue, idx) in matchStatus.issues" :key="idx">• {{ issue }}</div>
        </el-alert>

        <!-- 明细标签页 -->
        <el-tabs v-model="detailTab" style="margin-top: 16px;">
          <el-tab-pane label="采购订单" name="order">
            <el-table :data="orderLines" border stripe max-height="350" size="small">
              <el-table-column prop="reference_no" label="订单号" width="140" />
              <el-table-column prop="reference_date" label="订单日期" width="100" />
              <el-table-column prop="description" label="摘要" min-width="200" show-overflow-tooltip />
              <el-table-column label="订单金额" width="120" align="right">
                <template #default="{ row }">¥{{ formatNumber(row.order_amount) }}</template>
              </el-table-column>
              <el-table-column label="已收货" width="100" align="right">
                <template #default="{ row }">¥{{ formatNumber(row.received_amount) }}</template>
              </el-table-column>
              <el-table-column label="已开票" width="100" align="right">
                <template #default="{ row }">¥{{ formatNumber(row.invoice_amount) }}</template>
              </el-table-column>
              <el-table-column label="已付款" width="100" align="right">
                <template #default="{ row }">
                  <span class="success">¥{{ formatNumber(row.paid_amount) }}</span>
                </template>
              </el-table-column>
              <el-table-column label="三方匹配" width="100">
                <template #default="{ row }">
                  <el-tag :type="getThreeWayMatchType(row)" size="small">{{ getThreeWayMatchText(row) }}</el-tag>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>

          <el-tab-pane label="收货单" name="receipt">
            <el-table :data="receiptLines" border stripe max-height="350" size="small">
              <el-table-column prop="reference_no" label="收货单号" width="140" />
              <el-table-column prop="reference_date" label="收货日期" width="100" />
              <el-table-column prop="description" label="摘要" min-width="200" show-overflow-tooltip />
              <el-table-column label="收货金额" width="120" align="right">
                <template #default="{ row }">¥{{ formatNumber(row.amount) }}</template>
              </el-table-column>
              <el-table-column prop="receipt_confirmed" label="确认状态" width="90" align="center">
                <template #default="{ row }">
                  <el-tag v-if="row.receipt_confirmed" type="success" size="small">已确认</el-tag>
                  <el-tag v-else type="warning" size="small">待确认</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="100" v-if="currentReconciliation.status !== 'CONFIRMED'">
                <template #default="{ row }">
                  <el-button v-if="!row.receipt_confirmed" size="small" link type="primary" @click="confirmReceipt(row)">确认收货</el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>

          <el-tab-pane label="发票" name="invoice">
            <el-table :data="invoiceLines" border stripe max-height="350" size="small">
              <el-table-column prop="reference_no" label="发票号" width="180" />
              <el-table-column prop="reference_date" label="开票日期" width="100" />
              <el-table-column prop="description" label="摘要" min-width="200" show-overflow-tooltip />
              <el-table-column label="发票金额" width="120" align="right">
                <template #default="{ row }">¥{{ formatNumber(row.amount) }}</template>
              </el-table-column>
              <el-table-column label="税额" width="100" align="right">
                <template #default="{ row }">¥{{ formatNumber(row.tax_amount) }}</template>
              </el-table-column>
              <el-table-column label="抵扣状态" width="90">
                <template #default="{ row }">
                  <el-tag v-if="row.is_deducted" type="success" size="small">已抵扣</el-tag>
                  <el-tag v-else type="info" size="small">未抵扣</el-tag>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>

          <el-tab-pane label="付款记录" name="payment">
            <el-table :data="paymentLines" border stripe max-height="350" size="small">
              <el-table-column prop="reference_no" label="付款单号" width="140" />
              <el-table-column prop="reference_date" label="付款日期" width="100" />
              <el-table-column prop="description" label="摘要" min-width="200" show-overflow-tooltip />
              <el-table-column label="付款金额" width="120" align="right">
                <template #default="{ row }">
                  <span class="success">¥{{ formatNumber(row.amount) }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="payment_method" label="付款方式" width="100" />
            </el-table>
          </el-tab-pane>

          <el-tab-pane label="账龄分析" name="aging">
            <el-row :gutter="16">
              <el-col :span="16">
                <el-table :data="agingData" border stripe size="small">
                  <el-table-column prop="range" label="账龄区间" width="150" />
                  <el-table-column label="应付金额" align="right">
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
                    <span class="label">应付总额</span>
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
            <el-descriptions-item label="本期付款">¥{{ formatNumber(currentReconciliation.total_paid_amount) }}</el-descriptions-item>
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

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { getPurchaseReconciliations, getPurchaseReconciliation, createPurchaseReconciliation, deletePurchaseReconciliation, getPurchaseReconciliationSupplierSummary, getPurchaseReconciliationOpeningBalance, generatePurchaseReconciliationLines, submitPurchaseReconciliation, confirmPurchaseReconciliation, confirmPurchaseReconciliationReceipt } from '@/api/finance'
import { getSupplierList } from '@/api/masterdata'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/finance/purchase-reconciliations/', { onSuccess: () => loadReconciliations() })


const loading = ref(false)
const submitting = ref(false)
const reconciliations = ref<any[]>([])
const suppliers = ref<any[]>([])
const createDialogVisible = ref(false)
const detailDialogVisible = ref(false)
const currentReconciliation = ref(null)
const reconciliationLines = ref<any[]>([])
const detailTab = ref('order')

const pagination = reactive({ page: 1, pageSize: 20, total: 0 })
const searchForm = reactive({ supplier: null, period: null, status: null })
const summary = reactive({ total_purchase: 0, total_invoiced: 0, total_paid: 0, total_balance: 0 })

const createFormRef = ref(null)
const createForm = reactive({
  supplier: null,
  period: null,
  opening_balance: 0,
  notes: ''
})
const createRules = {
  supplier: [{ required: true, message: '请选择供应商', trigger: 'change' }],
  period: [{ required: true, message: '请选择对账期间', trigger: 'change' }]
}

// 分类明细行
const orderLines = computed(() => reconciliationLines.value.filter(l => l.line_type === 'ORDER'))
const receiptLines = computed(() => reconciliationLines.value.filter(l => l.line_type === 'RECEIPT'))
const invoiceLines = computed(() => reconciliationLines.value.filter(l => l.line_type === 'INVOICE'))
const paymentLines = computed(() => reconciliationLines.value.filter(l => l.line_type === 'PAYMENT'))

// 三方匹配状态
const matchStatus = computed(() => {
  if (!currentReconciliation.value) return { hasIssue: false }
  
  const orderAmt = currentReconciliation.value.total_order_amount || 0
  const receiptAmt = currentReconciliation.value.total_received_amount || 0
  const invoiceAmt = currentReconciliation.value.total_invoice_amount || 0
  
  const issues = []
  
  if (Math.abs(orderAmt - receiptAmt) > 0.01 && receiptAmt > 0) {
    const diff = orderAmt - receiptAmt
    issues.push(`订单金额与收货金额差异 ¥${formatNumber(Math.abs(diff))}${diff > 0 ? '（收货不足）' : '（超额收货）'}`)
  }
  
  if (Math.abs(receiptAmt - invoiceAmt) > 0.01 && invoiceAmt > 0) {
    const diff = receiptAmt - invoiceAmt
    issues.push(`收货金额与发票金额差异 ¥${formatNumber(Math.abs(diff))}${diff > 0 ? '（发票不足）' : '（发票超额）'}`)
  }
  
  return {
    hasIssue: issues.length > 0,
    type: issues.length > 0 ? 'warning' : 'success',
    title: issues.length > 0 ? '三方匹配存在差异' : '三方匹配正常',
    issues
  }
})

// 账龄数据
const agingData = computed(() => {
  if (!currentReconciliation.value) return []
  const balance = currentReconciliation.value.balance_amount || 0
  return [
    { range: '0-30天（未到期）', amount: balance * 0.35, percent: 35, count: 2 },
    { range: '31-60天', amount: balance * 0.30, percent: 30, count: 3 },
    { range: '61-90天', amount: balance * 0.20, percent: 20, count: 2 },
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

const getThreeWayMatchType = (row) => {
  const order = row.order_amount || 0
  const receipt = row.received_amount || 0
  const invoice = row.invoice_amount || 0
  
  if (order > 0 && Math.abs(order - receipt) < 0.01 && Math.abs(receipt - invoice) < 0.01) return 'success'
  if (receipt > 0 && invoice > 0) return 'warning'
  return 'info'
}

const getThreeWayMatchText = (row) => {
  const order = row.order_amount || 0
  const receipt = row.received_amount || 0
  const invoice = row.invoice_amount || 0
  
  if (order > 0 && Math.abs(order - receipt) < 0.01 && Math.abs(receipt - invoice) < 0.01) return '完全匹配'
  if (receipt > 0 && invoice > 0) return '部分匹配'
  if (receipt > 0) return '待开票'
  return '待收货'
}

const loadSuppliers = async () => {
  try {
    const res = await getSupplierList({ page_size: 1000, status: 'ACTIVE' })
    suppliers.value = res.results || res || []
  } catch (error) {
    console.error('Load suppliers failed:', error)
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
    
    const res = await getPurchaseReconciliations(params)
    reconciliations.value = res.results || res || []
    pagination.total = res.count || 0
    
    loadSummary()
  } catch (error) {
    ElMessage.error('加载对账单失败')
  } finally {
    loading.value = false
  }
}

const loadSummary = async () => {
  try {
    const res = await getPurchaseReconciliationSupplierSummary()
    if (res) {
      summary.total_purchase = res.total_order_amount || 0
      summary.total_invoiced = res.total_invoice_amount || 0
      summary.total_paid = res.total_paid_amount || 0
      summary.total_balance = res.total_balance || 0
    }
  } catch (error) {
    console.error('Load summary failed:', error)
  }
}

const resetSearch = () => {
  searchForm.supplier = null
  searchForm.period = null
  searchForm.status = null
  pagination.page = 1
  loadReconciliations()
}

const handleCreate = () => {
  Object.assign(createForm, { supplier: null, period: null, opening_balance: 0, notes: '' })
  createDialogVisible.value = true
}

// 获取供应商期初余额
const fetchOpeningBalance = async (supplierId) => {
  if (!supplierId) {
    createForm.opening_balance = 0
    return
  }
  try {
    const res = await getPurchaseReconciliationOpeningBalance({
      params: { supplier: supplierId }
    })
    createForm.opening_balance = res.opening_balance || 0
    if (res.source === 'last_reconciliation' && res.last_period) {
      ElMessage.info(`已自动填入上期(${res.last_period})期末余额`)
    } else if (res.source === 'account_payable') {
      ElMessage.info('已自动填入应付账款余额')
    }
  } catch (error) {
    console.error('获取期初余额失败:', error)
  }
}

const submitCreate = async () => {
  try {
    await createFormRef.value.validate()
    submitting.value = true
    
    const data = {
      supplier: createForm.supplier,
      period_start: createForm.period[0],
      period_end: createForm.period[1],
      opening_balance: createForm.opening_balance,
      notes: createForm.notes
    }
    
    const res = await createPurchaseReconciliation(data)
    await generatePurchaseReconciliationLines(res.id)
    
    ElMessage.success('对账单创建成功')
    createDialogVisible.value = false
    loadReconciliations()
    handleDetail(res)
  } catch (error) {
    ElMessage.error('创建失败: ' + (error.response?.data?.error || error.message))
  } finally {
    submitting.value = false
  }
}

const handleDetail = async (row) => {
  try {
    const res = await getPurchaseReconciliation(row.id)
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
    await ElMessageBox.confirm('确定提交此对账单吗？', '提交确认')
    await submitPurchaseReconciliation(row.id)
    ElMessage.success('提交成功')
    loadReconciliations()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('提交失败')
  }
}

const handleConfirm = async (row) => {
  try {
    await ElMessageBox.confirm('确定确认此对账单吗？', '确认对账')
    await confirmPurchaseReconciliation(row.id)
    ElMessage.success('确认成功')
    loadReconciliations()
    if (detailDialogVisible.value) handleDetail(row)
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('确认失败')
  }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定删除此对账单吗？', '删除确认', { type: 'warning' })
    await deletePurchaseReconciliation(row.id)
    ElMessage.success('删除成功')
    loadReconciliations()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('删除失败')
  }
}

const confirmReceipt = async (line) => {
  try {
    await confirmPurchaseReconciliationReceipt(currentReconciliation.value.id, line.id)
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
  // 生成采购订单明细行
  const orderRows = orderLines.value.map((line, idx) => `
    <tr>
      <td>${idx + 1}</td>
      <td>${line.reference_no || ''}</td>
      <td>${line.reference_date || ''}</td>
      <td style="text-align:left;">${line.description || ''}</td>
      <td style="text-align:left;">${line.specification || line.drawing_no || ''}</td>
      <td style="text-align:right;">${formatNumber(line.unit_price || 0)}</td>
      <td>${line.unit || ''}</td>
      <td style="text-align:right;">${line.quantity || ''}</td>
      <td style="text-align:right;">${formatNumber(line.order_amount)}</td>
      <td style="text-align:right;">${formatNumber(line.received_amount)}</td>
      <td style="text-align:right;">${formatNumber(line.invoice_amount)}</td>
      <td style="text-align:right;">${formatNumber(line.paid_amount)}</td>
      <td>${getThreeWayMatchText(line)}</td>
    </tr>
  `).join('')
  
  // 生成收货明细行
  const receiptRows = receiptLines.value.map((line, idx) => `
    <tr>
      <td>${idx + 1}</td>
      <td>${line.reference_no || ''}</td>
      <td>${line.reference_date || ''}</td>
      <td style="text-align:left;">${line.description || ''}</td>
      <td style="text-align:right;">${formatNumber(line.amount)}</td>
      <td>${line.receipt_confirmed ? '已确认' : '待确认'}</td>
    </tr>
  `).join('')
  
  // 生成发票明细行
  const invoiceRows = invoiceLines.value.map((line, idx) => `
    <tr>
      <td>${idx + 1}</td>
      <td>${line.reference_no || ''}</td>
      <td>${line.reference_date || ''}</td>
      <td style="text-align:left;">${line.description || ''}</td>
      <td style="text-align:right;">${formatNumber(line.amount)}</td>
      <td style="text-align:right;">${formatNumber(line.tax_amount || 0)}</td>
      <td>${line.is_deducted ? '已抵扣' : '未抵扣'}</td>
    </tr>
  `).join('')
  
  // 生成付款明细行
  const paymentRows = paymentLines.value.map((line, idx) => `
    <tr>
      <td>${idx + 1}</td>
      <td>${line.reference_no || ''}</td>
      <td>${line.reference_date || ''}</td>
      <td style="text-align:left;">${line.description || ''}</td>
      <td style="text-align:right;">${formatNumber(line.amount)}</td>
      <td>${line.payment_method || ''}</td>
    </tr>
  `).join('')
  
  // 三方匹配差异
  const orderAmt = data.total_order_amount || 0
  const receiptAmt = data.total_received_amount || 0
  const invoiceAmt = data.total_invoice_amount || 0
  const matchIssues = []
  if (Math.abs(orderAmt - receiptAmt) > 0.01) {
    matchIssues.push('订单与收货差异: ¥' + formatNumber(Math.abs(orderAmt - receiptAmt)))
  }
  if (Math.abs(receiptAmt - invoiceAmt) > 0.01) {
    matchIssues.push('收货与发票差异: ¥' + formatNumber(Math.abs(receiptAmt - invoiceAmt)))
  }
  
  const today = new Date().toISOString().slice(0, 10)
  
  return `<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>采购对账单 - ${data.reconciliation_no}</title>
<style>
@page { size: A4; margin: 8mm; }
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: '宋体', 'SimSun', serif; font-size: 10px; line-height: 1.4; color: #000; padding: 10px; }
.print-btn { position: fixed; top: 10px; right: 10px; padding: 8px 16px; background: #409eff; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 14px; }
.header { text-align: center; border-bottom: 2px solid #000; padding-bottom: 10px; margin-bottom: 15px; }
.header .company { font-size: 16px; font-weight: bold; letter-spacing: 3px; }
.header .title { font-size: 14px; font-weight: bold; margin-top: 5px; }
.header .doc-no { font-size: 11px; margin-top: 5px; }
.info-section { display: flex; justify-content: space-between; margin-bottom: 12px; padding: 8px; background: #f8f8f8; }
.info-box { width: 48%; font-size: 10px; line-height: 1.6; }
.info-box .label { font-weight: bold; display: inline-block; width: 70px; }
.section-title { font-weight: bold; font-size: 11px; margin: 12px 0 6px 0; padding: 4px 8px; background: #e8e8e8; }
table { width: 100%; border-collapse: collapse; font-size: 9px; margin-bottom: 10px; }
table th, table td { border: 1px solid #000; padding: 3px 5px; }
table th { background: #f0f0f0; font-weight: bold; text-align: center; }
table td { text-align: center; }
.summary-table { width: 50%; margin-left: auto; }
.summary-table td { text-align: right; padding: 4px 8px; }
.summary-table .label { text-align: left; font-weight: bold; }
.summary-table .total { font-size: 12px; font-weight: bold; background: #fffbe6; }
.match-alert { margin: 10px 0; padding: 8px; border: 1px solid #e6a23c; background: #fdf6ec; color: #e6a23c; }
.match-ok { border-color: #67c23a; background: #f0f9eb; color: #67c23a; }
.notes { margin: 10px 0; padding: 8px; border: 1px solid #ddd; background: #fafafa; font-size: 9px; }
.signature { display: flex; justify-content: space-between; margin-top: 20px; padding-top: 15px; border-top: 1px solid #000; }
.sig-box { width: 45%; font-size: 10px; line-height: 2; }
.sig-box .sig-title { font-weight: bold; margin-bottom: 5px; }
.footer { margin-top: 15px; padding-top: 8px; border-top: 1px dashed #ccc; font-size: 8px; color: #666; text-align: center; }
@media print { .print-btn { display: none; } body { padding: 0; } }
</style>
</head>
<body>
<button class="print-btn" onclick="window.print()">打印</button>

<div class="header">
  <div class="company">深圳市奥特迈智能装备有限公司</div>
  <div class="title">采购对账单（供应商往来对账）- ${data.period_start?.slice(0,7) || ''}${data.period_end && data.period_end.slice(0,7) !== data.period_start?.slice(0,7) ? ' 至 ' + data.period_end.slice(0,7) : ''}</div>
  <div class="doc-no">对账单号：${data.reconciliation_no} &nbsp;&nbsp;&nbsp;&nbsp; 打印日期：${today}</div>
</div>

<div class="info-section">
  <div class="info-box">
    <div><span class="label">供应商：</span>${data.supplier_name || ''}</div>
    <div><span class="label">对账期间：</span>${data.period_start} 至 ${data.period_end}</div>
    <div><span class="label">联系人：</span>${data.supplier_contact || ''}</div>
    <div><span class="label">联系电话：</span>${data.supplier_phone || ''}</div>
  </div>
  <div class="info-box">
    <div><span class="label">我方单位：</span>深圳市奥特迈智能装备有限公司</div>
    <div><span class="label">对账人员：</span>${data.created_by_name || ''}</div>
    <div><span class="label">创建日期：</span>${data.created_at?.slice(0, 10) || ''}</div>
    <div><span class="label">对账状态：</span>${getStatusText(data.status)}</div>
  </div>
</div>

<div class="section-title">一、采购订单明细（非标零部件/外协加工）</div>
<table>
  <tr>
    <th style="width:22px;">序号</th>
    <th style="width:85px;">订单号</th>
    <th style="width:58px;">订单日期</th>
    <th style="min-width:80px;">物料名称/加工内容</th>
    <th style="width:70px;">规格/图号</th>
    <th style="width:50px;">单价</th>
    <th style="width:30px;">单位</th>
    <th style="width:35px;">数量</th>
    <th style="width:58px;">订单金额</th>
    <th style="width:50px;">已收货</th>
    <th style="width:50px;">已开票</th>
    <th style="width:50px;">已付款</th>
    <th style="width:45px;">匹配状态</th>
  </tr>
  ${orderRows || '<tr><td colspan="13">暂无数据</td></tr>'}
  <tr style="font-weight:bold; background:#f5f5f5;">
    <td colspan="8" style="text-align:right;">合计：</td>
    <td style="text-align:right;">${formatNumber(data.total_order_amount)}</td>
    <td style="text-align:right;">${formatNumber(data.total_received_amount)}</td>
    <td style="text-align:right;">${formatNumber(data.total_invoice_amount)}</td>
    <td style="text-align:right;">${formatNumber(data.total_paid_amount)}</td>
    <td></td>
  </tr>
</table>

<div class="match-alert ${matchIssues.length === 0 ? 'match-ok' : ''}">
  <b>三方匹配验证（订单-收货-发票）：</b>
  ${matchIssues.length === 0 ? '✓ 三方金额匹配正常' : '⚠ ' + matchIssues.join('；')}
</div>

<div class="section-title">二、收货记录（来料检验/入库）</div>
<table>
  <tr>
    <th style="width:30px;">序号</th>
    <th style="width:100px;">收货单号</th>
    <th style="width:70px;">收货日期</th>
    <th>物料名称/规格型号</th>
    <th style="width:90px;">收货金额</th>
    <th style="width:70px;">确认状态</th>
  </tr>
  ${receiptRows || '<tr><td colspan="6">暂无数据</td></tr>'}
</table>

<div class="section-title">三、发票明细（增值税专用发票-进项）</div>
<table>
  <tr>
    <th style="width:30px;">序号</th>
    <th style="width:130px;">发票号码</th>
    <th style="width:70px;">开票日期</th>
    <th>发票内容/备注</th>
    <th style="width:80px;">发票金额</th>
    <th style="width:60px;">税额</th>
    <th style="width:60px;">抵扣状态</th>
  </tr>
  ${invoiceRows || '<tr><td colspan="7">暂无数据</td></tr>'}
</table>

<div class="section-title">四、付款记录</div>
<table>
  <tr>
    <th style="width:30px;">序号</th>
    <th style="width:100px;">付款单号</th>
    <th style="width:70px;">付款日期</th>
    <th>付款说明</th>
    <th style="width:90px;">付款金额</th>
    <th style="width:80px;">付款方式</th>
  </tr>
  ${paymentRows || '<tr><td colspan="6">暂无数据</td></tr>'}
</table>

<div class="section-title">五、账款汇总</div>
<table class="summary-table">
  <tr><td class="label">期初应付余额</td><td>¥ ${formatNumber(data.opening_balance)}</td></tr>
  <tr><td class="label">本期采购金额（+）</td><td>¥ ${formatNumber(data.total_order_amount)}</td></tr>
  <tr><td class="label">本期收票金额</td><td>¥ ${formatNumber(data.total_invoice_amount)}</td></tr>
  <tr><td class="label">本期付款金额（-）</td><td>¥ ${formatNumber(data.total_paid_amount)}</td></tr>
  <tr class="total"><td class="label">期末应付余额</td><td>¥ ${formatNumber(data.closing_balance)}</td></tr>
</table>

<div class="notes">
  <b>对账说明：</b><br>
  1. 本对账单涵盖期间内所有非标零部件采购及外协加工订单的收货、开票、付款情况。<br>
  2. 三方匹配原则：采购订单金额 = 收货金额 = 发票金额，如有差异请核实。<br>
  3. 如有争议，请于收到对账单后 5 个工作日内书面反馈，逾期视为确认无误。<br>
  4. 发票需为增值税专用发票（税率13%），请确保发票信息准确。<br>
  ${data.notes ? '5. 备注：' + data.notes : ''}
</div>

<div class="signature">
  <div class="sig-box">
    <div class="sig-title">需方（甲方）：深圳市奥特迈智能装备有限公司</div>
    <div>对账人员：________________</div>
    <div>确认签章：________________</div>
    <div>确认日期：________________</div>
  </div>
  <div class="sig-box">
    <div class="sig-title">供方（乙方）：${data.supplier_name || ''}</div>
    <div>对账人员：________________</div>
    <div>确认签章：________________</div>
    <div>确认日期：________________</div>
  </div>
</div>

<div class="footer">
  深圳市奥特迈智能装备有限公司 | 地址：深圳市光明区玉塘街道玉律社区寮光路55号德永佳工业园1栋1楼 | 电话：19129305737
</div>
</body>
</html>`
}

onMounted(() => {
  loadSuppliers()
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
.match-card.receipt { background: #f0f9eb; border-color: #67c23a; }
.match-card.invoice { background: #fdf6ec; border-color: #e6a23c; }
.match-card.payment { background: #f0f9eb; border-color: #67c23a; }
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

.form-tip {
  font-size: 12px;
  color: #909399;
  line-height: 1.5;
  margin-top: 4px;
}
</style>
