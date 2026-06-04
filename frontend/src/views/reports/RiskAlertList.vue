<template>
  <div class="risk-alert-list">
    <!-- 统计概览 -->
    <el-row :gutter="16" class="stat-row">
      <el-col :span="6">
        <el-card class="stat-card">
          <el-statistic title="总预警" :value="stats.total" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card danger">
          <el-statistic title="严重/高" :value="stats.critical + stats.high" value-style="color: #F56C6C" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card warning">
          <el-statistic title="待处理" :value="stats.pending" value-style="color: #E6A23C" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card success">
          <el-statistic title="已解决" :value="stats.resolved" value-style="color: #67C23A" />
        </el-card>
      </el-col>
    </el-row>

    <el-card>
      <template #header>
        <div class="card-header">
          <span>风险预警</span>
          <div>
            <el-select v-model="queryParams.severity" placeholder="严重程度" clearable style="width: 120px; margin-right: 8px" @change="loadList">
              <el-option label="严重" value="critical" />
              <el-option label="高" value="high" />
              <el-option label="中" value="medium" />
              <el-option label="低" value="low" />
            </el-select>
            <el-select v-model="queryParams.alert_type" placeholder="预警类型" clearable style="width: 140px; margin-right: 8px" @change="loadList">
              <el-option label="成本超支" value="cost_overrun" />
              <el-option label="进度延迟" value="schedule_delay" />
              <el-option label="产能不足" value="capacity_shortage" />
              <el-option label="库存异常" value="inventory_anomaly" />
              <el-option label="质量风险" value="quality_risk" />
              <el-option label="供应链风险" value="supply_chain_risk" />
            </el-select>
            <el-select v-model="queryParams.status" placeholder="状态" clearable style="width: 120px" @change="loadList">
              <el-option label="待处理" value="open" />
              <el-option label="已确认" value="acknowledged" />
              <el-option label="已解决" value="resolved" />
            </el-select>
          </div>
        </div>
      </template>

      <!-- 批量操作 -->

      <div v-if="selectedRows.length > 0" class="batch-toolbar">

        <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>

        <el-button size="small" @click="batchExport">导出选中</el-button>

      </div>

      <el-table :data="alertList" v-loading="loading" stripe :row-class-name="rowClassName" @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="45" />
        <el-table-column label="严重程度" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="severityType(row.severity)" effect="dark" size="small">{{ severityLabel(row.severity) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="120">
          <template #default="{ row }">{{ alertTypeLabel(row.alert_type) }}</template>
        </el-table-column>
        <el-table-column prop="title" label="预警标题" min-width="250" />
        <el-table-column prop="description" label="描述" min-width="300" show-overflow-tooltip />
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="触发时间" width="160" />
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link type="warning" @click="acknowledgeAlert(row)" v-if="row.status === 'open'">确认</el-button>
            <el-button size="small" link type="success" @click="resolveAlert(row)" v-if="row.status !== 'resolved'">解决</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrapper">
        <el-pagination v-model:current-page="queryParams.page" v-model:page-size="queryParams.page_size"
          :total="total" :page-sizes="[20, 50, 100]" layout="total, sizes, prev, pager, next" @change="loadList" />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getRiskAlerts, acknowledgeRiskAlert, resolveRiskAlert } from '@/api/reports'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchExport } = useBatchOperation('/api/reports/risk-alerts/')


const loading = ref(false)
const alertList = ref<any[]>([])
const total = ref(0)

const stats = reactive({ total: 0, critical: 0, high: 0, pending: 0, resolved: 0 })
const queryParams = reactive({ page: 1, page_size: 20, severity: '', alert_type: '', status: '' })

const severityType = (s) => ({ critical: 'danger', high: 'danger', medium: 'warning', low: 'info' }[s] || 'info')
const severityLabel = (s) => ({ critical: '严重', high: '高', medium: '中', low: '低' }[s] || s)
const statusType = (s) => ({ open: 'danger', acknowledged: 'warning', resolved: 'success', closed: 'info' }[s] || 'info')
const statusLabel = (s) => ({ open: '待处理', acknowledged: '已确认', resolved: '已解决', closed: '已关闭' }[s] || s)
const alertTypeLabel = (t) => ({
  cost_overrun: '成本超支', schedule_delay: '进度延迟', capacity_shortage: '产能不足',
  inventory_anomaly: '库存异常', quality_risk: '质量风险', supply_chain_risk: '供应链风险'
}[t] || t)

const rowClassName = ({ row }) => row.severity === 'critical' ? 'danger-row' : (row.severity === 'high' ? 'warning-row' : '')

const loadList = async () => {
  loading.value = true
  try {
    const params = { ...queryParams }
    Object.keys(params).forEach(k => { if (params[k] === '') delete params[k] })
    const res = await getRiskAlerts(params)
    alertList.value = res.results || res.results || []
    total.value = res.count || res.count || 0
    stats.total = total.value
    stats.critical = alertList.value.filter(a => a.severity === 'critical').length
    stats.high = alertList.value.filter(a => a.severity === 'high').length
    stats.pending = alertList.value.filter(a => a.status === 'open').length
    stats.resolved = alertList.value.filter(a => a.status === 'resolved').length
  } finally { loading.value = false }
}

const acknowledgeAlert = async (row) => {
  await ElMessageBox.confirm('确认该风险预警？', '确认')
  await acknowledgeRiskAlert(row.id)
  ElMessage.success('已确认')
  loadList()
}

const resolveAlert = async (row) => {
  const { value } = await ElMessageBox.prompt('请输入解决方案', '解决预警', { inputType: 'textarea' })
  await resolveRiskAlert(row.id, { resolution: value })
  ElMessage.success('已解决')
  loadList()
}

onMounted(() => { loadList() })
</script>

<style scoped>
.risk-alert-list { padding: 0; }
.stat-row { margin-bottom: 16px; }
.stat-card { text-align: center; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.pagination-wrapper { margin-top: 16px; display: flex; justify-content: flex-end; }
:deep(.danger-row) { background: #fef0f0 !important; }
:deep(.warning-row) { background: #fdf6ec !important; }
</style>
