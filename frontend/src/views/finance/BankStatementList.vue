<template>
  <div class="bank-statement-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>银行流水管理</span>
          <el-button type="primary" @click="showImportDialog = true">
            <el-icon><Upload /></el-icon>
            导入流水
          </el-button>
        </div>
      </template>

      <!-- 筛选栏 -->
      <el-form :inline="true" class="filter-form">
        <el-form-item label="银行">
          <el-select v-model="filters.bank_name" placeholder="全部银行" clearable style="width: 160px" @change="handleSearch">
            <el-option v-for="name in bankNames" :key="name" :label="name" :value="name" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部状态" clearable style="width: 120px" @change="handleSearch">
            <el-option label="待匹配" value="PENDING" />
            <el-option label="已匹配" value="MATCHED" />
            <el-option label="已忽略" value="IGNORED" />
          </el-select>
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="filters.transaction_type" placeholder="全部" clearable style="width: 100px" @change="handleSearch">
            <el-option label="收入" value="CREDIT" />
            <el-option label="支出" value="DEBIT" />
          </el-select>
        </el-form-item>
        <el-form-item label="日期">
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            value-format="YYYY-MM-DD"
            style="width: 240px"
            @change="handleSearch"
          />
        </el-form-item>
        <el-form-item>
          <el-input v-model="filters.search" placeholder="搜索对方单位/摘要" clearable style="width: 200px" @keyup.enter="handleSearch" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">搜索</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>

      <!-- 批量操作 -->
      <div v-if="selectedRows.length > 0" class="batch-toolbar">
        <span>已选择 {{ selectedRows.length }} 项</span>
        <el-button size="small" type="success" @click="handleBatchMatch">批量自动匹配</el-button>
        <el-button size="small" @click="handleBatchIgnore">批量忽略</el-button>
        <el-button size="small" type="danger" @click="handleBatchDelete">批量删除</el-button>
      </div>

      <!-- 表格 -->
      <el-table :data="statements" v-loading="loading" stripe border @selection-change="onSelectionChange" style="margin-top: 12px">
        <el-table-column type="selection" width="45" />
        <el-table-column label="银行" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.bank_name" size="small" :type="getBankTagType(row.bank_name)">{{ row.bank_name }}</el-tag>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="transaction_time" label="交易时间" width="160">
          <template #default="{ row }">{{ formatTime(row.transaction_time) }}</template>
        </el-table-column>
        <el-table-column prop="counterparty_name" label="对方单位" min-width="180" show-overflow-tooltip />
        <el-table-column label="收入" width="120" align="right">
          <template #default="{ row }">
            <span v-if="row.credit_amount > 0" class="text-success">+{{ formatMoney(row.credit_amount) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="支出" width="120" align="right">
          <template #default="{ row }">
            <span v-if="row.debit_amount > 0" class="text-danger">-{{ formatMoney(row.debit_amount) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="summary" label="摘要" width="150" show-overflow-tooltip />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="匹配" width="130">
          <template #default="{ row }">
            <span v-if="row.supplier_name">供: {{ row.supplier_name }}</span>
            <span v-else-if="row.customer_name">客: {{ row.customer_name }}</span>
            <span v-else class="text-muted">未匹配</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status === 'PENDING'" size="small" type="primary" @click="handleMatch(row)">匹配</el-button>
            <el-button v-if="row.status === 'PENDING'" size="small" @click="handleIgnore(row)">忽略</el-button>
            <el-button v-if="row.status === 'MATCHED'" size="small" type="info" @click="handleView(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        style="margin-top: 16px; justify-content: flex-end"
        @size-change="loadData"
        @current-change="loadData"
      />
    </el-card>

    <!-- 导入对话框 -->
    <el-dialog v-model="showImportDialog" title="导入银行流水" width="500px" destroy-on-close>
      <el-form :model="importForm" :rules="importRules" ref="importFormRef" label-width="90px">
        <el-form-item label="银行名称" prop="bank_name">
          <el-select
            v-model="importForm.bank_name"
            placeholder="选择或输入银行"
            filterable
            allow-create
            style="width: 100%"
          >
            <el-option label="工商银行" value="工商银行" />
            <el-option label="建设银行" value="建设银行" />
            <el-option label="农业银行" value="农业银行" />
            <el-option label="中国银行" value="中国银行" />
            <el-option label="招商银行" value="招商银行" />
            <el-option label="交通银行" value="交通银行" />
            <el-option label="华夏银行" value="华夏银行" />
            <el-option label="浦发银行" value="浦发银行" />
            <el-option label="中信银行" value="中信银行" />
            <el-option label="民生银行" value="民生银行" />
            <el-option v-for="name in bankNames" :key="name" :label="name" :value="name" />
          </el-select>
        </el-form-item>
        <el-form-item label="银行账号">
          <el-input v-model="importForm.bank_account" placeholder="可选，输入银行账号后四位或完整账号" />
        </el-form-item>
        <el-form-item label="流水文件" prop="file">
          <el-upload
            ref="uploadRef"
            :auto-upload="false"
            :limit="1"
            accept=".xlsx,.xls"
            :on-change="handleFileChange"
            :on-remove="handleFileRemove"
          >
            <el-button type="primary">选择文件</el-button>
            <template #tip>
              <div class="el-upload__tip">支持 .xlsx / .xls 格式</div>
            </template>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showImportDialog = false">取消</el-button>
        <el-button type="primary" :loading="importing" @click="handleImport">导入</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Upload } from '@element-plus/icons-vue'
import {
  getBankStatements,
  getBankNames,
  importBankStatements,
  matchBankStatement,
  ignoreBankStatement,
  autoMatchAllBankStatements,
  bulkDeleteBankStatements
} from '@/api/finance'

const loading = ref(false)
const importing = ref(false)
const statements = ref<any[]>([])
const bankNames = ref<string[]>([])
const selectedRows = ref<any[]>([])
const showImportDialog = ref(false)
const dateRange = ref<string[]>([])
const importFormRef = ref()
const uploadRef = ref()
const uploadFile = ref<File | null>(null)

const filters = reactive({
  bank_name: '',
  status: '',
  transaction_type: '',
  search: ''
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const importForm = reactive({
  bank_name: '',
  bank_account: ''
})

const importRules = {
  bank_name: [{ required: true, message: '请选择或输入银行名称', trigger: 'change' }]
}

const BANK_TAG_COLORS: Record<string, string> = {
  '工商银行': '',
  '建设银行': 'success',
  '农业银行': 'warning',
  '中国银行': 'danger',
  '招商银行': 'info',
}

const getBankTagType = (name: string) => {
  return BANK_TAG_COLORS[name] || ''
}

const getStatusType = (status: string) => {
  const map: Record<string, string> = { PENDING: 'warning', MATCHED: 'success', IGNORED: 'info', ERROR: 'danger' }
  return map[status] || ''
}

const formatTime = (t: string) => {
  if (!t) return '-'
  return t.replace('T', ' ').slice(0, 16)
}

const formatMoney = (val: number | string) => {
  return Number(val || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

const loadData = async () => {
  loading.value = true
  try {
    const params: Record<string, any> = {
      page: pagination.page,
      page_size: pagination.pageSize,
      ...filters
    }
    if (dateRange.value?.length === 2) {
      params.transaction_time__gte = dateRange.value[0]
      params.transaction_time__lte = dateRange.value[1]
    }
    Object.keys(params).forEach(k => { if (!params[k]) delete params[k] })
    const res = await getBankStatements(params)
    statements.value = res.results || res || []
    pagination.total = res.count || statements.value.length
  } finally {
    loading.value = false
  }
}

const loadBankNames = async () => {
  try {
    const res = await getBankNames()
    bankNames.value = res || []
  } catch { /* ignore */ }
}

const handleSearch = () => {
  pagination.page = 1
  loadData()
}

const resetFilters = () => {
  filters.bank_name = ''
  filters.status = ''
  filters.transaction_type = ''
  filters.search = ''
  dateRange.value = []
  handleSearch()
}

const onSelectionChange = (rows: any[]) => {
  selectedRows.value = rows
}

const handleFileChange = (file: any) => {
  uploadFile.value = file.raw
}

const handleFileRemove = () => {
  uploadFile.value = null
}

const handleImport = async () => {
  await importFormRef.value?.validate()
  if (!uploadFile.value) {
    ElMessage.warning('请选择文件')
    return
  }
  importing.value = true
  try {
    const formData = new FormData()
    formData.append('file', uploadFile.value)
    formData.append('bank_name', importForm.bank_name)
    if (importForm.bank_account) {
      formData.append('bank_account', importForm.bank_account)
    }
    const res = await importBankStatements(formData)
    ElMessage.success(`导入成功：${res.success_count || 0} 条，自动匹配 ${res.matched_count || 0} 条`)
    showImportDialog.value = false
    importForm.bank_name = ''
    importForm.bank_account = ''
    uploadFile.value = null
    loadData()
    loadBankNames()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error || '导入失败')
  } finally {
    importing.value = false
  }
}

const handleMatch = async (row: any) => {
  try {
    await ElMessageBox.confirm('确认对该流水执行自动匹配？如需关联具体应收/应付单，请到应收/应付页面手动匹配。', '自动匹配')
    const res = await autoMatchAllBankStatements({ ids: [row.id] })
    if (res?.matched_count > 0) {
      ElMessage.success('匹配成功')
    } else {
      ElMessage.warning('未找到匹配的客户/供应商，请到应收/应付页面手动匹配')
    }
    loadData()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('操作失败')
  }
}

const handleIgnore = async (row: any) => {
  try {
    await ElMessageBox.confirm('确认忽略该流水记录？', '提示')
    await ignoreBankStatement(row.id)
    ElMessage.success('已忽略')
    loadData()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('操作失败')
  }
}

const handleView = (row: any) => {
  ElMessage.info(`匹配到: ${row.supplier_name || row.customer_name || '-'}，置信度: ${row.match_confidence}%`)
}

const handleBatchMatch = async () => {
  try {
    await ElMessageBox.confirm(`确认对 ${selectedRows.value.length} 条记录执行自动匹配？`, '批量匹配')
    const ids = selectedRows.value.map(r => r.id)
    await autoMatchAllBankStatements({ ids })
    ElMessage.success('匹配完成')
    loadData()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('操作失败')
  }
}

const handleBatchIgnore = async () => {
  try {
    await ElMessageBox.confirm(`确认忽略 ${selectedRows.value.length} 条记录？`, '批量忽略')
    for (const row of selectedRows.value) {
      await ignoreBankStatement(row.id)
    }
    ElMessage.success('已忽略')
    loadData()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('操作失败')
  }
}

const handleBatchDelete = async () => {
  try {
    await ElMessageBox.confirm(`确认删除 ${selectedRows.value.length} 条记录？此操作不可恢复`, '批量删除', { type: 'warning' })
    const ids = selectedRows.value.map(r => r.id)
    await bulkDeleteBankStatements({ ids })
    ElMessage.success('已删除')
    loadData()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('操作失败')
  }
}

onMounted(() => {
  loadData()
  loadBankNames()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.filter-form {
  margin-bottom: 12px;
}
.batch-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  background: #f0f9eb;
  border-radius: 4px;
}
.text-success { color: #67c23a; font-weight: 500; }
.text-danger { color: #f56c6c; font-weight: 500; }
.text-muted { color: #909399; }
</style>
