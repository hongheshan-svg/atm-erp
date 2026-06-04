<template>
  <div class="data-accuracy">
    <!-- 统计概览 -->
    <el-row :gutter="16" class="stat-row">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value">{{ stats.accuracy || 0 }}%</div>
          <div class="stat-label">库存准确率</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card warning">
          <div class="stat-value">{{ stats.pendingIssues || 0 }}</div>
          <div class="stat-label">待处理问题</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card danger">
          <div class="stat-value">{{ stats.negativeStock || 0 }}</div>
          <div class="stat-label">负库存物料</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card success">
          <div class="stat-value">{{ stats.itemsWithStock || 0 }}</div>
          <div class="stat-label">有库存物料</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <!-- 准确率趋势 -->
      <el-col :span="14">
        <el-card>
          <template #header>
            <span>库存准确率趋势</span>
          </template>
          <div ref="accuracyChartRef" style="height: 300px"></div>
        </el-card>
      </el-col>

      <!-- 问题分布 -->
      <el-col :span="10">
        <el-card>
          <template #header>
            <span>问题严重程度分布</span>
          </template>
          <div ref="severityChartRef" style="height: 300px"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 操作区域 -->
    <el-card style="margin-top: 16px">
      <template #header>
        <div class="card-header">
          <span>数据校验操作</span>
          <div>
            <el-button type="primary" @click="runValidation" :loading="validating">
              <el-icon><Refresh /></el-icon> 运行校验
            </el-button>
            <el-button type="success" @click="showReconcileDialog">
              <el-icon><Document /></el-icon> 创建对账
            </el-button>
          </div>
        </div>
      </template>
      
      <el-tabs v-model="activeTab">
        <!-- 待处理问题 -->
        <el-tab-pane label="待处理问题" name="issues">
          <!-- 批量操作 -->
          <div v-if="selectedRows.length > 0" class="batch-toolbar">
            <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>
            <el-button type="danger" size="small" @click="batchDelete">批量删除</el-button>
            <el-button size="small" @click="batchExport">导出选中</el-button>
          </div>
          <el-table :data="pendingIssues" v-loading="loading" stripe size="small" @selection-change="handleSelectionChange">
            <el-table-column type="selection" width="45" />
            <el-table-column label="严重程度" width="90">
              <template #default="{ row }">
                <el-tag :type="getSeverityType(row.severity)" size="small">{{ row.severity }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="rule_name" label="校验规则" width="150" show-overflow-tooltip />
            <el-table-column prop="item_code" label="物料" width="120" />
            <el-table-column prop="warehouse_name" label="仓库" width="100" />
            <el-table-column prop="issue_description" label="问题描述" min-width="200" show-overflow-tooltip />
            <el-table-column label="差异值" width="100" align="right">
              <template #default="{ row }">
                <span :class="{ 'text-danger': row.variance < 0 }">{{ row.variance || '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="check_date" label="检查时间" width="150">
              <template #default="{ row }">{{ formatDateTime(row.check_date) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="150" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link size="small" @click="handleIssue(row)">处理</el-button>
                <el-button type="info" link size="small" @click="ignoreIssue(row)">忽略</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-pagination
            v-model:current-page="issuePage"
            :total="issueTotal"
            layout="total, prev, pager, next"
            @current-change="loadPendingIssues"
            style="margin-top: 16px; justify-content: flex-end"
          />
        </el-tab-pane>

        <!-- 对账记录 -->
        <el-tab-pane label="对账记录" name="reconciliation">
          <el-table :data="reconciliations" v-loading="loading" stripe size="small">
            <el-table-column prop="session_no" label="会话编号" width="130" />
            <el-table-column prop="session_type_display" label="对账类型" width="120" />
            <el-table-column prop="warehouse_name" label="仓库" width="100" />
            <el-table-column label="期间" width="180">
              <template #default="{ row }">{{ row.start_date }} ~ {{ row.end_date }}</template>
            </el-table-column>
            <el-table-column prop="total_items_checked" label="检查物料" width="90" align="center" />
            <el-table-column prop="issues_found" label="发现问题" width="90" align="center">
              <template #default="{ row }">
                <span :class="{ 'text-danger': row.issues_found > 0 }">{{ row.issues_found }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="status_display" label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="getStatusType(row.status)">{{ row.status_display }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="完成时间" width="150">
              <template #default="{ row }">{{ row.completed_at ? formatDateTime(row.completed_at) : '-' }}</template>
            </el-table-column>
            <el-table-column label="操作" width="100">
              <template #default="{ row }">
                <el-button type="primary" link size="small" @click="viewReconciliation(row)">查看</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- 校验规则 -->
        <el-tab-pane label="校验规则" name="rules">
          <div style="margin-bottom: 10px">
            <el-button type="primary" size="small" @click="initDefaultRules">初始化默认规则</el-button>
          </div>
          <el-table :data="validationRules" v-loading="loading" stripe size="small">
            <el-table-column prop="code" label="规则编码" width="150" />
            <el-table-column prop="name" label="规则名称" min-width="200" />
            <el-table-column prop="rule_type_display" label="类型" width="120" />
            <el-table-column prop="severity_display" label="严重程度" width="90">
              <template #default="{ row }">
                <el-tag :type="getSeverityType(row.severity)" size="small">{{ row.severity }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="check_frequency" label="检查频率" width="90" />
            <el-table-column prop="is_active" label="启用" width="70" align="center">
              <template #default="{ row }">
                <el-switch v-model="row.is_active" size="small" @change="toggleRule(row)" />
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 对账对话框 -->
    <el-dialog v-model="reconcileDialogVisible" title="创建对账" width="500px">
      <el-form :model="reconcileForm" label-width="100px">
        <el-form-item label="对账类型">
          <el-select v-model="reconcileForm.session_type" style="width: 100%">
            <el-option label="进销存平衡" value="IN_OUT_BALANCE" />
            <el-option label="库存成本对账" value="STOCK_COST" />
            <el-option label="全面审计" value="FULL_AUDIT" />
          </el-select>
        </el-form-item>
        <el-form-item label="仓库">
          <el-select v-model="reconcileForm.warehouse_id" clearable placeholder="全部仓库" style="width: 100%">
            <el-option v-for="w in warehouses" :key="w.id" :label="w.name" :value="w.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="开始日期">
          <el-date-picker v-model="reconcileForm.start_date" type="date" placeholder="选择日期" style="width: 100%" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="结束日期">
          <el-date-picker v-model="reconcileForm.end_date" type="date" placeholder="选择日期" style="width: 100%" value-format="YYYY-MM-DD" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="reconcileDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="createReconciliation" :loading="submitting">创建并运行</el-button>
      </template>
    </el-dialog>

    <!-- 处理问题对话框 -->
    <el-dialog v-model="handleDialogVisible" title="处理问题" width="500px">
      <div class="issue-info" v-if="currentIssue">
        <p><strong>问题：</strong>{{ currentIssue.issue_description }}</p>
        <p><strong>物料：</strong>{{ currentIssue.item_code }} - {{ currentIssue.item_name }}</p>
        <p><strong>仓库：</strong>{{ currentIssue.warehouse_name }}</p>
        <p><strong>差异：</strong>{{ currentIssue.variance }}</p>
      </div>
      <el-divider />
      <el-form :model="handleForm" label-width="80px">
        <el-form-item label="处理状态">
          <el-select v-model="handleForm.status" style="width: 100%">
            <el-option label="已修复" value="FIXED" />
            <el-option label="误报" value="FALSE_POSITIVE" />
            <el-option label="已忽略" value="IGNORED" />
          </el-select>
        </el-form-item>
        <el-form-item label="处理说明">
          <el-input v-model="handleForm.resolution" type="textarea" :rows="3" placeholder="请输入处理说明" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="handleDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitHandle" :loading="submitting">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Document } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import * as echarts from 'echarts'
import { getAccuracyReport, getValidationResults, getReconciliationSessions, getValidationRules, runValidationChecks, createAndRunReconciliation, handleValidationResult, initDefaultValidationRules, updateValidationRule } from '@/api/inventory'
import { getWarehouseList } from '@/api/masterdata'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/inventory/validation-results/', { onSuccess: () => loadPendingIssues() })


const router = useRouter()

const loading = ref(false)
const validating = ref(false)
const submitting = ref(false)
const activeTab = ref('issues')

const stats = ref<Record<string, any>>({})
const pendingIssues = ref<any[]>([])
const issuePage = ref(1)
const issueTotal = ref(0)
const reconciliations = ref<any[]>([])
const validationRules = ref<any[]>([])
const warehouses = ref<any[]>([])
const accuracyTrend = ref<any[]>([])
const severityData = ref<any[]>([])

const reconcileDialogVisible = ref(false)
const handleDialogVisible = ref(false)
const currentIssue = ref(null)

const accuracyChartRef = ref(null)
const severityChartRef = ref(null)
let accuracyChart = null
let severityChart = null

const reconcileForm = reactive({
  session_type: 'IN_OUT_BALANCE',
  warehouse_id: null,
  start_date: '',
  end_date: ''
})

const handleForm = reactive({
  status: 'FIXED',
  resolution: ''
})

const getSeverityType = (severity) => {
  const map = { INFO: 'info', WARNING: 'warning', ERROR: 'danger', CRITICAL: 'danger' }
  return map[severity] || 'info'
}

const getStatusType = (status) => {
  const map = { DRAFT: 'info', IN_PROGRESS: 'warning', COMPLETED: 'success', CANCELLED: 'danger' }
  return map[status] || 'info'
}

const formatDateTime = (dt) => {
  if (!dt) return '-'
  return new Date(dt).toLocaleString('zh-CN')
}

const loadStats = async () => {
  try {
    const res = await getAccuracyReport()
    accuracyTrend.value = res.accuracy_trend || []
    severityData.value = res.issue_by_severity || []
    stats.value = {
      accuracy: accuracyTrend.value[0]?.accuracy || 100,
      pendingIssues: res.current_status?.pending_issues || 0,
      negativeStock: res.current_status?.negative_stock_items || 0,
      itemsWithStock: res.current_status?.total_items_with_stock || 0
    }
    
    await nextTick()
    renderCharts()
  } catch (e) {
    console.error(e)
  }
}

const loadPendingIssues = async () => {
  loading.value = true
  try {
    const res = await getValidationResults({ status: 'PENDING', page: issuePage.value, page_size: 10 })
    pendingIssues.value = res.results || res
    issueTotal.value = res.count || pendingIssues.value.length
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const loadReconciliations = async () => {
  try {
    const res = await getReconciliationSessions({ page_size: 20 })
    reconciliations.value = res.results || res
  } catch (e) {
    console.error(e)
  }
}

const loadValidationRules = async () => {
  try {
    const res = await getValidationRules({ page_size: 100 })
    validationRules.value = res.results || res
  } catch (e) {
    console.error(e)
  }
}

const loadWarehouses = async () => {
  const res = await getWarehouseList({ page_size: 100 })
  warehouses.value = res.results || res
}

const renderCharts = () => {
  // 准确率趋势图
  if (accuracyChartRef.value) {
    if (!accuracyChart) {
      accuracyChart = echarts.init(accuracyChartRef.value)
    }
    accuracyChart.setOption({
      tooltip: { trigger: 'axis' },
      xAxis: {
        type: 'category',
        data: accuracyTrend.value.map(t => t.date)
      },
      yAxis: {
        type: 'value',
        min: 90,
        max: 100,
        axisLabel: { formatter: '{value}%' }
      },
      series: [{
        name: '准确率',
        type: 'line',
        smooth: true,
        areaStyle: { opacity: 0.3 },
        data: accuracyTrend.value.map(t => t.accuracy),
        markLine: {
          data: [{ yAxis: 98, name: '目标', lineStyle: { color: '#67c23a' } }]
        }
      }]
    })
  }
  
  // 严重程度饼图
  if (severityChartRef.value) {
    if (!severityChart) {
      severityChart = echarts.init(severityChartRef.value)
    }
    const colorMap = { INFO: '#909399', WARNING: '#e6a23c', ERROR: '#f56c6c', CRITICAL: '#f56c6c' }
    severityChart.setOption({
      tooltip: { trigger: 'item' },
      series: [{
        type: 'pie',
        radius: ['40%', '70%'],
        data: severityData.value.map(s => ({
          name: s.rule__severity || 'INFO',
          value: s.count,
          itemStyle: { color: colorMap[s.rule__severity] }
        })),
        label: { formatter: '{b}: {c}' }
      }]
    })
  }
}

const runValidation = async () => {
  validating.value = true
  try {
    const res = await runValidationChecks()
    ElMessage.success(`校验完成，发现 ${res.total_issues} 个问题`)
    loadStats()
    loadPendingIssues()
  } catch (e) {
    ElMessage.error('校验失败')
  } finally {
    validating.value = false
  }
}

const showReconcileDialog = () => {
  const today = new Date()
  reconcileForm.session_type = 'IN_OUT_BALANCE'
  reconcileForm.warehouse_id = null
  reconcileForm.end_date = today.toISOString().slice(0, 10)
  reconcileForm.start_date = new Date(today.getFullYear(), today.getMonth(), 1).toISOString().slice(0, 10)
  reconcileDialogVisible.value = true
}

const createReconciliation = async () => {
  submitting.value = true
  try {
    const res = await createAndRunReconciliation(reconcileForm)
    ElMessage.success(`对账完成，检查 ${res.total_items_checked} 个物料，发现 ${res.issues_found} 个问题`)
    reconcileDialogVisible.value = false
    loadReconciliations()
    loadStats()
  } catch (e) {
    ElMessage.error('对账失败')
  } finally {
    submitting.value = false
  }
}

const handleIssue = (issue) => {
  currentIssue.value = issue
  handleForm.status = 'FIXED'
  handleForm.resolution = ''
  handleDialogVisible.value = true
}

const ignoreIssue = async (issue) => {
  try {
    await handleValidationResult(issue.id, {
      status: 'IGNORED',
      resolution: '手动忽略'
    })
    ElMessage.success('已忽略')
    loadPendingIssues()
    loadStats()
  } catch (e) {
    ElMessage.error('操作失败')
  }
}

const submitHandle = async () => {
  submitting.value = true
  try {
    await handleValidationResult(currentIssue.value.id, handleForm)
    ElMessage.success('处理成功')
    handleDialogVisible.value = false
    loadPendingIssues()
    loadStats()
  } catch (e) {
    ElMessage.error('处理失败')
  } finally {
    submitting.value = false
  }
}

const viewReconciliation = (session) => {
  router.push(`/inventory/reconciliation/${session.id}`)
}

const initDefaultRules = async () => {
  try {
    const res = await initDefaultValidationRules()
    ElMessage.success(`初始化完成，创建 ${res.created_count} 条规则`)
    loadValidationRules()
  } catch (e) {
    ElMessage.error('初始化失败')
  }
}

const toggleRule = async (rule) => {
  try {
    await updateValidationRule(rule.id, {
      is_active: rule.is_active
    })
  } catch (e) {
    rule.is_active = !rule.is_active
    ElMessage.error('操作失败')
  }
}

onMounted(() => {
  loadStats()
  loadPendingIssues()
  loadReconciliations()
  loadValidationRules()
  loadWarehouses()
})
</script>

<style scoped>
.stat-row {
  margin-bottom: 16px;
}
.stat-card {
  text-align: center;
  cursor: pointer;
}
.stat-card .stat-value {
  font-size: 32px;
  font-weight: bold;
  color: #409eff;
}
.stat-card.warning .stat-value { color: #e6a23c; }
.stat-card.success .stat-value { color: #67c23a; }
.stat-card.danger .stat-value { color: #f56c6c; }
.stat-card .stat-label {
  font-size: 14px;
  color: #909399;
  margin-top: 8px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.issue-info p {
  margin: 8px 0;
}
.text-danger { color: #f56c6c; }
</style>
