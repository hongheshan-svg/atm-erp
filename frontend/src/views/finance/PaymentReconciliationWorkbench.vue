<template>
  <div class="payment-reconciliation-workbench">
    <el-row :gutter="16">
      <!-- 左侧:待核销银行流水(转出) -->
      <el-col :span="10">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>银行流水(转出)</span>
              <el-button size="small" :loading="leftLoading" @click="loadStatements">刷新</el-button>
            </div>
          </template>

          <el-form :inline="true" class="filter-form">
            <el-form-item label="状态">
              <el-select v-model="leftFilters.status" placeholder="全部" clearable style="width: 120px" @change="handleLeftSearch">
                <el-option label="未核销" value="PENDING" />
                <el-option label="部分核销" value="PARTIAL" />
                <el-option label="已核销" value="MATCHED" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-input
                v-model="leftFilters.search"
                placeholder="搜索对方单位/摘要"
                clearable
                style="width: 180px"
                @keyup.enter="handleLeftSearch"
              />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" size="small" @click="handleLeftSearch">搜索</el-button>
            </el-form-item>
          </el-form>

          <el-table
            :data="statements"
            v-loading="leftLoading"
            border
            stripe
            highlight-current-row
            row-key="id"
            style="width: 100%"
            @current-change="handleStatementFocus"
            @expand-change="handleExpandChange"
          >
            <el-table-column type="expand">
              <template #default="{ row }">
                <div class="settlement-detail" v-loading="settlementsLoadingMap[row.id]">
                  <div v-if="!(settlementsCache[row.id] || []).length" class="text-muted">暂无核销记录</div>
                  <el-table v-else :data="settlementsCache[row.id]" size="small" border>
                    <el-table-column label="来源单号" prop="payable_item.source_no" min-width="120" show-overflow-tooltip />
                    <el-table-column label="收款方" prop="payable_item.payee_name" min-width="120" show-overflow-tooltip />
                    <el-table-column label="本次核销金额" align="right" width="120">
                      <template #default="{ row: s }">¥{{ formatMoney(s.amount) }}</template>
                    </el-table-column>
                    <el-table-column label="付款单号" prop="payment_no" min-width="120" show-overflow-tooltip />
                    <el-table-column label="核销时间" width="150">
                      <template #default="{ row: s }">{{ formatTime(s.created_at) }}</template>
                    </el-table-column>
                    <el-table-column label="操作" width="90" fixed="right">
                      <template #default="{ row: s }">
                        <el-button link type="danger" size="small" @click="handleUnsettle(s, row)">反核销</el-button>
                      </template>
                    </el-table-column>
                  </el-table>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="transaction_time" label="交易时间" width="150">
              <template #default="{ row }">{{ formatTime(row.transaction_time) }}</template>
            </el-table-column>
            <el-table-column prop="counterparty_name" label="对方单位" min-width="140" show-overflow-tooltip />
            <el-table-column label="支出金额" width="110" align="right">
              <template #default="{ row }">¥{{ formatMoney(row.amount ?? row.debit_amount) }}</template>
            </el-table-column>
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="getStatementStatusType(row.status)" size="small">{{ getStatementStatusText(row.status) }}</el-tag>
              </template>
            </el-table-column>
          </el-table>

          <el-pagination
            v-model:current-page="leftPagination.page"
            v-model:page-size="leftPagination.pageSize"
            :total="leftPagination.total"
            :page-sizes="[10, 20, 50]"
            layout="total, prev, pager, next"
            style="margin-top: 12px; justify-content: flex-end"
            @size-change="loadStatements"
            @current-change="loadStatements"
          />
        </el-card>
      </el-col>

      <!-- 右侧:待付款项台账 -->
      <el-col :span="14">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>待付款项台账</span>
              <span v-if="selectedStatement" class="selected-hint">
                已选流水:{{ selectedStatement.counterparty_name || '-' }} ¥{{ formatMoney(selectedStatement.amount ?? selectedStatement.debit_amount) }}
                (可核销余额 ¥{{ formatMoney(statementRemaining) }})
              </span>
              <span v-else class="selected-hint text-muted">请先在左侧选择一条银行流水以查看匹配候选</span>
            </div>
          </template>

          <el-tabs v-model="rightTab" @tab-change="handleTabChange">
            <el-tab-pane label="匹配候选" name="candidates">
              <div v-if="!selectedStatement" class="empty-hint">请先在左侧选择一条待核销的银行流水</div>
              <el-table v-else :data="candidates" v-loading="candidatesLoading" border stripe row-key="id">
                <el-table-column width="45">
                  <template #default="{ row }">
                    <el-checkbox :model-value="!!selection[row.id]" @change="(val: boolean) => toggleSelect(row, val)" />
                  </template>
                </el-table-column>
                <el-table-column label="来源" width="90">
                  <template #default="{ row }">{{ sourceTypeLabel(row.source_type) }}</template>
                </el-table-column>
                <el-table-column prop="source_no" label="单号" min-width="110" show-overflow-tooltip />
                <el-table-column prop="payee_name" label="收款方" min-width="110" show-overflow-tooltip />
                <el-table-column label="剩余待付" width="110" align="right">
                  <template #default="{ row }">¥{{ formatMoney(row.remaining) }}</template>
                </el-table-column>
                <el-table-column label="应付日期" width="100">
                  <template #default="{ row }">{{ row.due_date || '-' }}</template>
                </el-table-column>
                <el-table-column label="匹配度" width="150">
                  <template #default="{ row }">
                    <el-tag :type="scoreTagType(row.score)" size="small">{{ row.score }}分</el-tag>
                    <div class="reasons">{{ (row.reasons || []).join('、') }}</div>
                  </template>
                </el-table-column>
              </el-table>
            </el-tab-pane>

            <el-tab-pane label="台账查询" name="browse">
              <el-form :inline="true" class="filter-form">
                <el-form-item label="模块">
                  <el-select v-model="rightFilters.source_type" placeholder="全部" clearable style="width: 110px" @change="handleLedgerSearch">
                    <el-option label="采购" value="ap" />
                    <el-option label="报销" value="expense" />
                    <el-option label="合同付款" value="contract_payment" />
                  </el-select>
                </el-form-item>
                <el-form-item label="供应商">
                  <el-select v-model="rightFilters.supplier" placeholder="全部" clearable filterable style="width: 140px" @change="handleLedgerSearch">
                    <el-option v-for="s in suppliers" :key="s.id" :label="s.name" :value="s.id" />
                  </el-select>
                </el-form-item>
                <el-form-item label="状态">
                  <el-select v-model="rightFilters.status" placeholder="全部" clearable style="width: 100px" @change="handleLedgerSearch">
                    <el-option label="待付" value="PENDING" />
                    <el-option label="部分" value="PARTIAL" />
                    <el-option label="已付" value="PAID" />
                    <el-option label="已取消" value="CANCELLED" />
                  </el-select>
                </el-form-item>
                <el-form-item label="金额">
                  <el-input v-model="rightFilters.amount_min" placeholder="最小" style="width: 90px" @change="handleLedgerSearch" />
                  <span class="range-sep">-</span>
                  <el-input v-model="rightFilters.amount_max" placeholder="最大" style="width: 90px" @change="handleLedgerSearch" />
                </el-form-item>
                <el-form-item label="应付日期">
                  <el-date-picker
                    v-model="dateRange"
                    type="daterange"
                    start-placeholder="开始"
                    end-placeholder="结束"
                    value-format="YYYY-MM-DD"
                    style="width: 220px"
                    @change="handleLedgerSearch"
                  />
                </el-form-item>
                <el-form-item>
                  <el-button type="primary" size="small" @click="handleLedgerSearch">搜索</el-button>
                  <el-button size="small" @click="resetLedgerFilters">重置</el-button>
                </el-form-item>
              </el-form>

              <el-table :data="ledgerItems" v-loading="ledgerLoading" border stripe row-key="id">
                <el-table-column width="45">
                  <template #default="{ row }">
                    <el-checkbox :model-value="!!selection[row.id]" @change="(val: boolean) => toggleSelect(row, val)" />
                  </template>
                </el-table-column>
                <el-table-column label="来源" width="90">
                  <template #default="{ row }">{{ sourceTypeLabel(row.source_type) }}</template>
                </el-table-column>
                <el-table-column prop="source_no" label="单号" min-width="110" show-overflow-tooltip />
                <el-table-column prop="payee_name" label="收款方" min-width="110" show-overflow-tooltip />
                <el-table-column label="应付金额" width="110" align="right">
                  <template #default="{ row }">¥{{ formatMoney(row.amount_due) }}</template>
                </el-table-column>
                <el-table-column label="剩余待付" width="110" align="right">
                  <template #default="{ row }">¥{{ formatMoney(row.remaining) }}</template>
                </el-table-column>
                <el-table-column label="应付日期" width="100">
                  <template #default="{ row }">{{ row.due_date || '-' }}</template>
                </el-table-column>
                <el-table-column label="状态" width="90">
                  <template #default="{ row }">
                    <el-tag :type="getItemStatusType(row.status)" size="small">{{ getItemStatusText(row.status) }}</el-tag>
                  </template>
                </el-table-column>
              </el-table>

              <el-pagination
                v-model:current-page="ledgerPagination.page"
                v-model:page-size="ledgerPagination.pageSize"
                :total="ledgerPagination.total"
                :page-sizes="[10, 20, 50]"
                layout="total, sizes, prev, pager, next"
                style="margin-top: 12px; justify-content: flex-end"
                @size-change="loadLedger"
                @current-change="loadLedger"
              />
            </el-tab-pane>
          </el-tabs>

          <div v-if="selectedList.length > 0" class="batch-toolbar">
            <span>已选 {{ selectedList.length }} 项，合计 ¥{{ formatMoney(selectedTotal) }}</span>
            <el-button size="small" @click="clearSelection">清空所选</el-button>
            <el-button size="small" type="primary" :disabled="!selectedStatement" @click="openSettleDialog">去核销</el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 确认核销对话框 -->
    <el-dialog v-model="settleDialogVisible" title="确认核销" width="720px" destroy-on-close>
      <el-descriptions v-if="selectedStatement" :column="2" border size="small">
        <el-descriptions-item label="对方单位">{{ selectedStatement.counterparty_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="流水金额">¥{{ formatMoney(selectedStatement.amount ?? selectedStatement.debit_amount) }}</el-descriptions-item>
        <el-descriptions-item label="可核销余额">¥{{ formatMoney(statementRemaining) }}</el-descriptions-item>
        <el-descriptions-item label="本次拟核销合计">
          <span :class="{ 'text-danger': overAllocated }">¥{{ formatMoney(selectedTotal) }}</span>
        </el-descriptions-item>
      </el-descriptions>

      <el-table :data="selectedList" style="margin-top: 12px" size="small" border>
        <el-table-column label="来源单号" min-width="110" show-overflow-tooltip>
          <template #default="{ row }">{{ row.item.source_no }}</template>
        </el-table-column>
        <el-table-column label="收款方" min-width="110" show-overflow-tooltip>
          <template #default="{ row }">{{ row.item.payee_name }}</template>
        </el-table-column>
        <el-table-column label="应付金额" width="110" align="right">
          <template #default="{ row }">¥{{ formatMoney(row.item.amount_due) }}</template>
        </el-table-column>
        <el-table-column label="剩余待付" width="110" align="right">
          <template #default="{ row }">¥{{ formatMoney(row.item.remaining) }}</template>
        </el-table-column>
        <el-table-column label="本次核销金额" width="160">
          <template #default="{ row }">
            <el-input-number
              v-model="row.amount"
              :min="0.01"
              :max="Number(row.item.remaining)"
              :precision="2"
              :step="100"
              size="small"
              style="width: 140px"
            />
          </template>
        </el-table-column>
        <el-table-column label="" width="60">
          <template #default="{ row }">
            <el-button link type="danger" @click="removeSelection(row.item.id)">移除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <p v-if="overAllocated" class="text-danger" style="margin-top: 8px">本次核销合计超过可核销余额，请调整金额或移除部分台账项。</p>

      <template #footer>
        <el-button @click="settleDialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="settling"
          :disabled="overAllocated || selectedList.length === 0"
          @click="confirmSettle"
        >
          确认核销
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getPayableItems,
  getBankStatements,
  getBankStatementPayableCandidates,
  getBankStatementSettlements,
  settlePayableReconcile,
  unsettlePayableReconcile
} from '@/api/finance'
import { getSupplierList } from '@/api/masterdata'

interface SelectionEntry {
  item: any
  amount: number
}

// ========== 左侧:银行流水 ==========
const leftLoading = ref(false)
const statements = ref<any[]>([])
const leftFilters = reactive({ status: '', search: '' })
const leftPagination = reactive({ page: 1, pageSize: 20, total: 0 })
const selectedStatement = ref<any>(null)

const settlementsCache = reactive<Record<number, any[]>>({})
const settlementsLoadingMap = reactive<Record<number, boolean>>({})

const STATEMENT_STATUS_TEXT: Record<string, string> = {
  PENDING: '未核销',
  PARTIAL: '部分核销',
  MATCHED: '已核销',
  IGNORED: '已忽略',
  ERROR: '异常'
}
const STATEMENT_STATUS_TYPE: Record<string, string> = {
  PENDING: 'warning',
  PARTIAL: 'primary',
  MATCHED: 'success',
  IGNORED: 'info',
  ERROR: 'danger'
}
const getStatementStatusText = (s: string) => STATEMENT_STATUS_TEXT[s] || s || '-'
const getStatementStatusType = (s: string) => STATEMENT_STATUS_TYPE[s] || ''

async function loadStatements() {
  leftLoading.value = true
  try {
    const params: Record<string, any> = {
      page: leftPagination.page,
      page_size: leftPagination.pageSize,
      transaction_type: 'DEBIT',
      status: leftFilters.status || undefined,
      search: leftFilters.search || undefined
    }
    Object.keys(params).forEach((k) => { if (params[k] === undefined || params[k] === '') delete params[k] })
    const res = await getBankStatements(params)
    statements.value = res.results || res || []
    leftPagination.total = res.count ?? statements.value.length
  } finally {
    leftLoading.value = false
  }
}

function handleLeftSearch() {
  leftPagination.page = 1
  loadStatements()
}

async function ensureSettlements(id: number, force = false) {
  if (!force && settlementsCache[id]) return
  settlementsLoadingMap[id] = true
  try {
    const res = await getBankStatementSettlements(id)
    settlementsCache[id] = res || []
  } finally {
    settlementsLoadingMap[id] = false
  }
}

function handleExpandChange(row: any, expandedRows: any[]) {
  const isExpanded = expandedRows.some((r) => r.id === row.id)
  if (isExpanded) ensureSettlements(row.id)
}

async function handleStatementFocus(row: any) {
  if (!row || selectedStatement.value?.id === row.id) return
  if (Object.keys(selection).length > 0) {
    clearSelection()
    ElMessage.info('已切换银行流水，所选台账项已清空，请重新选择')
  }
  selectedStatement.value = row
  rightTab.value = 'candidates'
  await Promise.all([loadCandidates(), ensureSettlements(row.id)])
}

async function handleUnsettle(s: any, statementRow: any) {
  try {
    await ElMessageBox.confirm(
      `确认反核销「${s.payable_item?.source_no || ''}」本次核销金额 ¥${formatMoney(s.amount)}？反核销后台账项与流水状态将回退。`,
      '反核销',
      { type: 'warning' }
    )
  } catch {
    return
  }
  try {
    await unsettlePayableReconcile({ settlement_id: s.settlement_id })
    ElMessage.success('反核销成功')
    delete settlementsCache[statementRow.id]
    await ensureSettlements(statementRow.id, true)
    const tasks = [loadStatements(), loadLedger()]
    if (selectedStatement.value?.id === statementRow.id) tasks.push(loadCandidates())
    await Promise.all(tasks)
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '反核销失败')
  }
}

// ========== 右侧:待付款项台账 ==========
const rightTab = ref<'candidates' | 'browse'>('candidates')
const candidatesLoading = ref(false)
const candidates = ref<any[]>([])

const rightFilters = reactive({
  source_type: '',
  supplier: undefined as number | undefined,
  status: '',
  amount_min: '',
  amount_max: ''
})
const dateRange = ref<string[]>([])
const ledgerLoading = ref(false)
const ledgerItems = ref<any[]>([])
const ledgerPagination = reactive({ page: 1, pageSize: 20, total: 0 })
const suppliers = ref<any[]>([])

const SOURCE_TYPE_LABEL: Record<string, string> = {
  ap: '采购',
  expense: '报销',
  contract_payment: '合同付款'
}
const sourceTypeLabel = (t: string) => SOURCE_TYPE_LABEL[t] || t || '-'

const ITEM_STATUS_TEXT: Record<string, string> = {
  PENDING: '待付',
  PARTIAL: '部分',
  PAID: '已付',
  CANCELLED: '已取消'
}
const ITEM_STATUS_TYPE: Record<string, string> = {
  PENDING: 'warning',
  PARTIAL: 'primary',
  PAID: 'success',
  CANCELLED: 'info'
}
const getItemStatusText = (s: string) => ITEM_STATUS_TEXT[s] || s || '-'
const getItemStatusType = (s: string) => ITEM_STATUS_TYPE[s] || ''

const scoreTagType = (score: number) => {
  if (score >= 50) return 'success'
  if (score >= 20) return 'warning'
  return 'info'
}

async function loadCandidates() {
  if (!selectedStatement.value) return
  candidatesLoading.value = true
  try {
    const res = await getBankStatementPayableCandidates(selectedStatement.value.id)
    candidates.value = (res || []).map((c: any) => ({ ...c, id: c.payable_item_id }))
  } finally {
    candidatesLoading.value = false
  }
}

async function loadLedger() {
  ledgerLoading.value = true
  try {
    const params: Record<string, any> = {
      page: ledgerPagination.page,
      page_size: ledgerPagination.pageSize,
      status: rightFilters.status || undefined,
      source_type: rightFilters.source_type || undefined,
      supplier: rightFilters.supplier || undefined,
      amount_due__gte: rightFilters.amount_min || undefined,
      amount_due__lte: rightFilters.amount_max || undefined
    }
    if (dateRange.value?.length === 2) {
      params.due_date__gte = dateRange.value[0]
      params.due_date__lte = dateRange.value[1]
    }
    Object.keys(params).forEach((k) => { if (params[k] === undefined || params[k] === '') delete params[k] })
    const res = await getPayableItems(params)
    ledgerItems.value = res.results || res || []
    ledgerPagination.total = res.count ?? ledgerItems.value.length
  } finally {
    ledgerLoading.value = false
  }
}

function handleLedgerSearch() {
  ledgerPagination.page = 1
  loadLedger()
}

function resetLedgerFilters() {
  rightFilters.source_type = ''
  rightFilters.supplier = undefined
  rightFilters.status = ''
  rightFilters.amount_min = ''
  rightFilters.amount_max = ''
  dateRange.value = []
  handleLedgerSearch()
}

function handleTabChange(name: string | number) {
  if (name === 'browse' && ledgerItems.value.length === 0) {
    loadLedger()
  }
}

async function loadSuppliers() {
  try {
    const res = await getSupplierList({ page_size: 200 })
    suppliers.value = res.results || res || []
  } catch { /* ignore */ }
}

// ========== 选择 / 核销 ==========
const selection = reactive<Record<number, SelectionEntry>>({})
const selectedList = computed<SelectionEntry[]>(() => Object.values(selection))
const selectedTotal = computed(() => selectedList.value.reduce((sum, s) => sum + Number(s.amount || 0), 0))

const statementRemaining = computed(() => {
  if (!selectedStatement.value) return 0
  const already = (settlementsCache[selectedStatement.value.id] || []).reduce((s, x) => s + Number(x.amount || 0), 0)
  const total = Number(selectedStatement.value.amount ?? selectedStatement.value.debit_amount ?? 0)
  return Math.max(total - already, 0)
})

const overAllocated = computed(() => selectedTotal.value > statementRemaining.value + 0.001)

function toggleSelect(row: any, checked: boolean) {
  if (!checked) {
    delete selection[row.id]
    return
  }
  if (!selectedStatement.value) {
    ElMessage.warning('请先在左侧选择一条待核销的银行流水')
    return
  }
  const remainingCapacity = Math.max(statementRemaining.value - selectedTotal.value, 0)
  const suggested = Math.min(Number(row.remaining), remainingCapacity > 0 ? remainingCapacity : Number(row.remaining))
  selection[row.id] = { item: row, amount: Number(suggested.toFixed(2)) }
}

function removeSelection(id: number) {
  delete selection[id]
}

function clearSelection() {
  Object.keys(selection).forEach((k) => delete selection[Number(k)])
}

function openSettleDialog() {
  if (!selectedStatement.value) {
    ElMessage.warning('请先在左侧选择一条待核销的银行流水')
    return
  }
  settleDialogVisible.value = true
}

const settleDialogVisible = ref(false)
const settling = ref(false)

async function confirmSettle() {
  if (!selectedStatement.value || selectedList.value.length === 0) return
  settling.value = true
  try {
    const allocations = selectedList.value.map((s) => ({ payable_item_id: s.item.id, amount: s.amount }))
    const res = await settlePayableReconcile({ bank_statement_id: selectedStatement.value.id, allocations })
    ElMessage.success(`核销成功，生成 ${res?.settlement_ids?.length || 0} 条核销记录`)
    settleDialogVisible.value = false
    const statementId = selectedStatement.value.id
    clearSelection()
    delete settlementsCache[statementId]
    await Promise.all([loadStatements(), loadLedger(), ensureSettlements(statementId, true), loadCandidates()])
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '核销失败')
  } finally {
    settling.value = false
  }
}

// ========== 通用 ==========
const formatMoney = (val: number | string | null | undefined) => {
  return Number(val || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}
const formatTime = (t: string) => {
  if (!t) return '-'
  return String(t).replace('T', ' ').slice(0, 16)
}

onMounted(() => {
  loadStatements()
  loadSuppliers()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
.selected-hint {
  font-size: 13px;
  color: #606266;
}
.filter-form {
  margin-bottom: 12px;
}
.range-sep {
  margin: 0 4px;
  color: #909399;
}
.empty-hint {
  padding: 32px 0;
  text-align: center;
  color: #909399;
}
.reasons {
  font-size: 12px;
  color: #909399;
  margin-top: 2px;
}
.settlement-detail {
  padding: 8px 16px;
  background: #fafafa;
}
.batch-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 12px;
  padding: 8px 12px;
  background: #f0f9eb;
  border-radius: 4px;
}
.text-muted {
  color: #909399;
}
.text-danger {
  color: #f56c6c;
  font-weight: 500;
}
</style>
