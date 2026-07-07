<template>
  <div class="ap-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>应付账款</span>
          <div class="header-actions">
            <el-upload
              ref="uploadRef"
              :action="uploadUrl"
              :headers="uploadHeaders"
              :on-success="handleUploadSuccess"
              :on-error="handleUploadError"
              :before-upload="beforeUpload"
              :show-file-list="false"
              accept=".xlsx,.xls"
            >
              <el-button type="primary">
                <el-icon><Upload /></el-icon> 导入银行流水
              </el-button>
            </el-upload>
            <el-button @click="autoMatchAll" :loading="autoMatching">
              <el-icon><Connection /></el-icon> 自动匹配
            </el-button>
            <el-button type="success" @click="exportData">
              <el-icon><Download /></el-icon> 导出
            </el-button>
          </div>
        </div>
      </template>

      <el-tabs v-model="activeTab" @tab-change="handleTabChange">
        <!-- 应付账款列表 -->
        <el-tab-pane label="应付账款" name="payables">
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
                <el-option label="待付款" value="PENDING" />
                <el-option label="部分付款" value="PARTIAL" />
                <el-option label="已付款" value="PAID" />
                <el-option label="已逾期" value="OVERDUE" />
                <el-option label="已取消" value="CANCELLED" />
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
            <el-table-column prop="purchase_order_no" label="采购订单" width="140" show-overflow-tooltip />
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
            <el-table-column label="付款进度" width="100">
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
        </el-tab-pane>

        <!-- 银行流水(支出) -->
        <el-tab-pane label="银行流水(支出)" name="bankStatements">
          <el-form :inline="true" :model="bankSearchForm" class="search-form">
            <el-form-item label="状态">
              <el-select v-model="bankSearchForm.status" placeholder="全部" clearable style="width: 120px;">
                <el-option label="待匹配" value="PENDING" />
                <el-option label="已匹配" value="MATCHED" />
                <el-option label="已忽略" value="IGNORED" />
              </el-select>
            </el-form-item>
            <el-form-item label="供应商">
              <el-select v-model="bankSearchForm.supplier" placeholder="全部" clearable filterable style="width: 150px;">
                <el-option v-for="s in suppliers" :key="s.id" :label="s.name" :value="s.id" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="loadBankStatements">查询</el-button>
              <el-button @click="resetBankSearch">重置</el-button>
            </el-form-item>
          </el-form>

          <div class="batch-actions" v-if="selectedBankStatements.length > 0">
            <el-button type="danger" size="small" v-permission="'finance:payable:delete'" @click="handleBatchDelete">
              批量删除 ({{ selectedBankStatements.length }})
            </el-button>
          </div>

          <el-table :data="bankStatements" v-loading="bankLoading" border stripe @selection-change="handleBankSelectionChange">
            <el-table-column type="selection" width="45" />
            <el-table-column prop="transaction_time" label="交易时间" width="150">
              <template #default="{ row }">{{ formatDateTime(row.transaction_time) }}</template>
            </el-table-column>
            <el-table-column prop="counterparty_name" label="对方单位" min-width="150" show-overflow-tooltip />
            <el-table-column label="金额" width="110" align="right">
              <template #default="{ row }">
                <span class="text-danger">¥{{ formatNumber(row.amount) }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="postscript" label="附言/用途" width="150" show-overflow-tooltip>
              <template #default="{ row }">{{ row.postscript || row.purpose || '-' }}</template>
            </el-table-column>
            <el-table-column label="匹配供应商" width="120" show-overflow-tooltip>
              <template #default="{ row }">
                <span v-if="row.supplier_name" class="text-success">{{ row.supplier_name }}</span>
                <span v-else class="text-muted">未匹配</span>
              </template>
            </el-table-column>
            <el-table-column label="关联采购单" width="120" show-overflow-tooltip>
              <template #default="{ row }">
                <span v-if="row.related_order_no">{{ row.related_order_no }}</span>
                <span v-else class="text-muted">-</span>
              </template>
            </el-table-column>
            <el-table-column label="置信度" width="70" align="center">
              <template #default="{ row }">
                <el-tag v-if="row.match_confidence >= 70" type="success" size="small">{{ row.match_confidence }}%</el-tag>
                <el-tag v-else-if="row.match_confidence > 0" type="warning" size="small">{{ row.match_confidence }}%</el-tag>
                <span v-else class="text-muted">-</span>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="80" align="center">
              <template #default="{ row }">
                <el-tag :type="getBankStatusType(row.status)" size="small">{{ getBankStatusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150" fixed="right">
              <template #default="{ row }">
                <el-button size="small" link type="primary" @click="handleMatchBank(row)" v-if="row.status === 'PENDING'">匹配</el-button>
                <el-button size="small" link type="warning" @click="handleIgnoreBank(row)" v-if="row.status === 'PENDING'">忽略</el-button>
                <el-button size="small" link @click="handleViewBank(row)">详情</el-button>
              </template>
            </el-table-column>
          </el-table>

          <el-pagination
            v-model:current-page="bankPagination.page"
            v-model:page-size="bankPagination.pageSize"
            :total="bankPagination.total"
            layout="total, sizes, prev, pager, next"
            @size-change="loadBankStatements"
            @current-change="loadBankStatements"
            style="margin-top: 20px; justify-content: flex-end;"
          />
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 应付详情对话框 -->
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

    <!-- 银行流水详情对话框 -->
    <el-dialog v-model="bankDetailVisible" title="银行流水详情" width="650px">
      <el-descriptions :column="2" border v-if="currentBankStatement">
        <el-descriptions-item label="交易时间">{{ formatDateTime(currentBankStatement.transaction_time) }}</el-descriptions-item>
        <el-descriptions-item label="交易类型">
          <el-tag type="danger" size="small">支出</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="对方单位" :span="2">{{ currentBankStatement.counterparty_name }}</el-descriptions-item>
        <el-descriptions-item label="对方账号">{{ currentBankStatement.counterparty_account || '-' }}</el-descriptions-item>
        <el-descriptions-item label="金额">
          <span class="text-danger" style="font-size: 16px;">¥{{ formatNumber(currentBankStatement.amount) }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="用途">{{ currentBankStatement.purpose || '-' }}</el-descriptions-item>
        <el-descriptions-item label="附言">{{ currentBankStatement.postscript || '-' }}</el-descriptions-item>
        <el-descriptions-item label="匹配状态">
          <el-tag :type="getBankStatusType(currentBankStatement.status)" size="small">{{ getBankStatusLabel(currentBankStatement.status) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="匹配供应商">{{ currentBankStatement.supplier_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="关联采购单">{{ currentBankStatement.related_order_no || '-' }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>

    <!-- 导入结果对话框 -->
    <el-dialog v-model="importResultVisible" title="导入结果" width="450px">
      <el-descriptions :column="2" border v-if="importResult">
        <el-descriptions-item label="批次号" :span="2">{{ importResult.batch_no }}</el-descriptions-item>
        <el-descriptions-item label="成功导入">
          <span class="text-success">{{ importResult.success_count }} 条</span>
        </el-descriptions-item>
        <el-descriptions-item label="自动匹配">
          <span class="text-primary">{{ importResult.matched_count }} 条</span>
        </el-descriptions-item>
        <el-descriptions-item label="支出总额" :span="2">
          <span class="text-danger" style="font-size: 18px; font-weight: bold;">¥{{ formatNumber(importResult.debit_total) }}</span>
        </el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button type="primary" @click="importResultVisible = false; loadBankStatements()">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Upload, Download, Connection } from '@element-plus/icons-vue'
import { getPayables, getBankStatements, bulkDeleteBankStatements, ignoreBankStatement, autoMatchAllBankStatements } from '@/api/finance'
import { exportAPReport } from '@/api/core'
import { getSupplierList } from '@/api/masterdata'

const router = useRouter()

const loading = ref(false)
const bankLoading = ref(false)
const autoMatching = ref(false)
const activeTab = ref('payables')

const dataList = ref<any[]>([])
const bankStatements = ref<any[]>([])
const selectedBankStatements = ref<any[]>([])
const suppliers = ref<any[]>([])
const currentRow = ref(null)
const currentBankStatement = ref(null)
const importResult = ref(null)

const viewVisible = ref(false)
const bankDetailVisible = ref(false)
const importResultVisible = ref(false)

const summary = reactive({ total_due: 0, total_paid: 0, total_remaining: 0, overdue_amount: 0 })
const searchForm = reactive({ supplier: null, status: null })
const pagination = reactive({ page: 1, pageSize: 20, total: 0 })
const bankSearchForm = reactive({ status: null, supplier: null })
const bankPagination = reactive({ page: 1, pageSize: 20, total: 0 })

// Upload configuration
const uploadUrl = computed(() => {
  const baseUrl = import.meta.env.VITE_API_BASE_URL || '/api'
  return `${baseUrl}/finance/bank-statements/import_excel/`
})
const uploadHeaders = computed(() => {
  const token = localStorage.getItem('access_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
})

const formatNumber = (num) => parseFloat(num || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const formatDateTime = (dt) => dt ? new Date(dt).toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '-'
const getRemaining = (row) => (parseFloat(row?.amount_due) || 0) - (parseFloat(row?.amount_paid) || 0)
const getProgress = (row) => {
  const due = parseFloat(row?.amount_due) || 0
  const paid = parseFloat(row?.amount_paid) || 0
  return due > 0 ? Math.min(100, Math.round((paid / due) * 100)) : 0
}
const getProgressColor = (p) => p >= 100 ? '#67c23a' : p >= 50 ? '#409eff' : '#e6a23c'
const getStatusType = (s) => ({ PENDING: 'warning', PARTIAL: 'primary', PAID: 'success', OVERDUE: 'danger', CANCELLED: 'info' }[s] || 'info')
const getStatusLabel = (s) => ({ PENDING: '待付款', PARTIAL: '部分付款', PAID: '已付款', OVERDUE: '已逾期', CANCELLED: '已取消' }[s] || s)
const getBankStatusType = (s) => ({ PENDING: 'warning', MATCHED: 'success', IGNORED: 'info' }[s] || 'info')
const getBankStatusLabel = (s) => ({ PENDING: '待匹配', MATCHED: '已匹配', IGNORED: '已忽略' }[s] || s)

const handleTabChange = (tab) => {
  if (tab === 'payables') loadData()
  else if (tab === 'bankStatements') loadBankStatements()
}

const loadData = async () => {
  loading.value = true
  try {
    const params = { page: pagination.page, page_size: pagination.pageSize, ...searchForm }
    Object.keys(params).forEach(k => { if (params[k] === null) delete params[k] })
    const res = await getPayables(params)
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

const loadBankStatements = async () => {
  bankLoading.value = true
  try {
    const params = { page: bankPagination.page, page_size: bankPagination.pageSize, transaction_type: 'DEBIT', ...bankSearchForm }
    Object.keys(params).forEach(k => { if (params[k] === null || params[k] === '') delete params[k] })
    const res = await getBankStatements(params)
    bankStatements.value = res.results || []
    bankPagination.total = res.count || 0
  } catch (error) {
    ElMessage.error('加载银行流水失败')
  } finally {
    bankLoading.value = false
  }
}

const loadSuppliers = async () => {
  try {
    const res = await getSupplierList({ page_size: 500 })
    suppliers.value = res.results || res || []
  } catch (error) {
    console.error('APList getSupplierList error:', error)
  }
}

const resetSearch = () => { searchForm.supplier = null; searchForm.status = null; pagination.page = 1; loadData() }
const resetBankSearch = () => { bankSearchForm.status = null; bankSearchForm.supplier = null; bankPagination.page = 1; loadBankStatements() }

const handleView = (row) => { currentRow.value = row; viewVisible.value = true }
const handlePayment = () => {
  ElMessage.info('付款已统一由「付款核销工作台」核销银行流水完成，请在工作台中办理')
  router.push('/finance/payment-reconciliation')
}

const exportData = async () => {
  try {
    const res = await exportAPReport({ responseType: 'blob' })
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

// Bank statement functions
const beforeUpload = (file) => {
  const isExcel = file.name.endsWith('.xlsx') || file.name.endsWith('.xls')
  if (!isExcel) { ElMessage.error('只支持Excel文件格式(.xlsx, .xls)'); return false }
  return true
}

const handleUploadSuccess = (response) => {
  importResult.value = response
  importResultVisible.value = true
  ElMessage.success(`成功导入 ${response.success_count} 条记录，自动匹配 ${response.matched_count} 条`)
  activeTab.value = 'bankStatements'
}

const handleUploadError = () => { ElMessage.error('导入失败，请检查文件格式') }

const handleBankSelectionChange = (selection) => { selectedBankStatements.value = selection }

const handleBatchDelete = async () => {
  try {
    await ElMessageBox.confirm(`确定要删除选中的 ${selectedBankStatements.value.length} 条记录吗？`, '批量删除', { type: 'warning' })
    const ids = selectedBankStatements.value.map(item => item.id)
    await bulkDeleteBankStatements({ ids })
    ElMessage.success('删除成功')
    selectedBankStatements.value = []
    loadBankStatements()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
      console.error('APList handleBatchDelete error:', error)
    }
  }
}

const handleViewBank = (row) => { currentBankStatement.value = row; bankDetailVisible.value = true }

const handleMatchBank = () => {
  ElMessage.info('银行流水核销已统一至「付款核销工作台」办理，请在工作台中匹配')
  router.push('/finance/payment-reconciliation')
}

const handleIgnoreBank = async (row) => {
  try {
    await ElMessageBox.confirm('确定要忽略此银行流水记录吗？', '确认忽略', { type: 'warning' })
    await ignoreBankStatement(row.id, { notes: '手动忽略' })
    ElMessage.success('已忽略')
    loadBankStatements()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('操作失败')
      console.error('APList handleIgnoreBank error:', error)
    }
  }
}

const autoMatchAll = async () => {
  autoMatching.value = true
  try {
    const response = await autoMatchAllBankStatements({ type: 'AP' })
    ElMessage.success(`成功自动匹配 ${response.matched_count} 条记录`)
    loadBankStatements()
    loadData()
  } catch (error) {
    ElMessage.error('自动匹配失败')
  } finally {
    autoMatching.value = false
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
.header-actions { display: flex; gap: 10px; }
.summary-row { margin-bottom: 20px; }
.summary-card { background: #f5f7fa; padding: 16px; border-radius: 8px; text-align: center; }
.summary-card.danger { background: #fef0f0; }
.summary-label { font-size: 13px; color: #909399; margin-bottom: 8px; }
.summary-value { font-size: 20px; font-weight: bold; }
.search-form { margin-bottom: 16px; }
.batch-actions { margin-bottom: 10px; }
.text-primary { color: #409eff; font-weight: 500; }
.text-success { color: #67c23a; font-weight: 500; }
.text-warning { color: #e6a23c; font-weight: 500; }
.text-danger { color: #f56c6c; font-weight: 500; }
.text-muted { color: #909399; }
</style>
