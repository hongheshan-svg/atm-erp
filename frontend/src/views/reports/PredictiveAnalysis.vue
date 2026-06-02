<template>
  <div class="predictive-analysis">
    <el-tabs v-model="activeTab" type="border-card">
      <!-- 成本趋势 -->
      <el-tab-pane label="成本趋势" name="cost">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span>项目成本趋势预测</span>
              <div>
                <el-input v-model="costProjectId" placeholder="项目ID" style="width: 150px; margin-right: 12px" />
                <el-button type="primary" @click="loadCostTrend" :loading="costLoading">分析</el-button>
              </div>
            </div>
          </template>
          <div ref="costChartRef" style="height: 400px"></div>
          <el-descriptions v-if="costResult" :column="4" border style="margin-top: 16px">
            <el-descriptions-item label="当前总成本">¥{{ formatMoney(costResult.current_total) }}</el-descriptions-item>
            <el-descriptions-item label="预测总成本">¥{{ formatMoney(costResult.predicted_total) }}</el-descriptions-item>
            <el-descriptions-item label="趋势">
              <el-tag :type="costResult.trend === 'up' ? 'danger' : (costResult.trend === 'down' ? 'success' : 'info')">
                {{ { up: '上升', down: '下降', stable: '平稳' }[costResult.trend] }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="置信度">{{ costResult.confidence }}%</el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-tab-pane>

      <!-- 交付风险 -->
      <el-tab-pane label="交付风险" name="delivery">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span>项目交付风险评估</span>
              <el-button type="primary" @click="loadDeliveryRisk" :loading="deliveryLoading">刷新</el-button>
            </div>
          </template>
          <!-- 批量操作 -->
          <div v-if="selectedRows.length > 0" class="batch-toolbar">
            <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>
            <el-button size="small" @click="batchExport">导出选中</el-button>
          </div>
          <el-table :data="deliveryRisks" v-loading="deliveryLoading" stripe @selection-change="handleSelectionChange">
            <el-table-column type="selection" width="45" />
            <el-table-column prop="project_name" label="项目" min-width="180" />
            <el-table-column label="风险等级" width="100" align="center">
              <template #default="{ row }">
                <el-tag :type="riskLevelType(row.risk_level)">{{ riskLevelLabel(row.risk_level) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="完成进度" width="150">
              <template #default="{ row }">
                <el-progress :percentage="row.progress || 0" :status="row.progress < 50 && row.days_remaining < 30 ? 'exception' : ''" />
              </template>
            </el-table-column>
            <el-table-column prop="days_remaining" label="剩余天数" width="100" align="center">
              <template #default="{ row }">
                <span :style="{ color: row.days_remaining < 15 ? '#f56c6c' : '' }">{{ row.days_remaining }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="delay_probability" label="延期概率" width="100" align="center">
              <template #default="{ row }">{{ row.delay_probability }}%</template>
            </el-table-column>
            <el-table-column prop="risk_factors" label="风险因素" min-width="250" show-overflow-tooltip />
          </el-table>
        </el-card>
      </el-tab-pane>

      <!-- 产能负荷 -->
      <el-tab-pane label="产能负荷" name="capacity">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span>产能负荷预测</span>
              <div>
                <el-input-number v-model="capacityWeeks" :min="1" :max="24" style="width: 120px; margin-right: 12px" />
                <span style="margin-right: 12px; color: #909399">周</span>
                <el-button type="primary" @click="loadCapacityLoad" :loading="capacityLoading">预测</el-button>
              </div>
            </div>
          </template>
          <div ref="capacityChartRef" style="height: 400px"></div>
          <el-table :data="capacityData" v-loading="capacityLoading" stripe style="margin-top: 16px" size="small">
            <el-table-column prop="week" label="周次" width="100" />
            <el-table-column prop="planned_hours" label="计划工时" width="120" align="right" />
            <el-table-column prop="available_hours" label="可用工时" width="120" align="right" />
            <el-table-column label="负荷率" width="150">
              <template #default="{ row }">
                <el-progress :percentage="row.utilization || 0" :status="row.utilization > 100 ? 'exception' : (row.utilization > 85 ? 'warning' : '')" />
              </template>
            </el-table-column>
            <el-table-column prop="bottleneck" label="瓶颈资源" min-width="150" />
          </el-table>
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getCostTrend, getDeliveryRisk, getCapacityLoad } from '@/api/reports'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchExport } = useBatchOperation('/api/reports/')


const activeTab = ref('cost')
const costLoading = ref(false)
const deliveryLoading = ref(false)
const capacityLoading = ref(false)

const costProjectId = ref('')
const costResult = ref(null)
const costChartRef = ref(null)
const deliveryRisks = ref<any[]>([])
const capacityWeeks = ref(8)
const capacityData = ref<any[]>([])
const capacityChartRef = ref(null)

const formatMoney = (v) => v ? Number(v).toLocaleString('zh-CN', { minimumFractionDigits: 2 }) : '0.00'
const riskLevelType = (l) => ({ low: 'success', medium: 'warning', high: 'danger', critical: 'danger' }[l] || 'info')
const riskLevelLabel = (l) => ({ low: '低', medium: '中', high: '高', critical: '严重' }[l] || l)

const loadCostTrend = async () => {
  if (!costProjectId.value) return
  costLoading.value = true
  try {
    const res = await getCostTrend({ project_id: costProjectId.value })
    costResult.value = res
  } finally { costLoading.value = false }
}

const loadDeliveryRisk = async () => {
  deliveryLoading.value = true
  try {
    const res = await getDeliveryRisk()
    deliveryRisks.value = res.risks || res.results || (Array.isArray(res) ? res : [])
  } finally { deliveryLoading.value = false }
}

const loadCapacityLoad = async () => {
  capacityLoading.value = true
  try {
    const res = await getCapacityLoad({ weeks: capacityWeeks.value })
    capacityData.value = res.capacity_load || res.results || (Array.isArray(res) ? res : [])
  } finally { capacityLoading.value = false }
}

onMounted(() => { loadDeliveryRisk() })
</script>

<style scoped>
.predictive-analysis { padding: 0; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
</style>
