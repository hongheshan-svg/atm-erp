<template>
  <div class="predictive-analysis">
    <el-tabs v-model="activeTab" type="border-card">
      <!-- 成本趋势 -->
      <el-tab-pane label="成本趋势" name="cost">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span>项目预算成本趋势</span>
              <el-button type="primary" @click="loadCostTrend" :loading="costLoading">分析</el-button>
            </div>
          </template>
          <div ref="costChartRef" style="height: 400px"></div>
          <el-table :data="costTrends" v-loading="costLoading" stripe style="margin-top: 16px" size="small">
            <el-table-column prop="month" label="月份" width="160">
              <template #default="{ row }">{{ formatMonth(row.month) }}</template>
            </el-table-column>
            <el-table-column prop="count" label="项目数" width="120" align="right" />
            <el-table-column prop="total_budget" label="预算合计" align="right">
              <template #default="{ row }">¥{{ formatMoney(row.total_budget) }}</template>
            </el-table-column>
          </el-table>
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
            <el-table-column prop="planned_end" label="计划交期" width="140" align="center" />
            <el-table-column prop="days_overdue" label="逾期天数" width="120" align="center">
              <template #default="{ row }">
                <span :style="{ color: row.days_overdue > 0 ? '#f56c6c' : '' }">{{ row.days_overdue }}</span>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <!-- 产能负荷 -->
      <el-tab-pane label="产能负荷" name="capacity">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span>工作中心产能负荷</span>
              <el-button type="primary" @click="loadCapacityLoad" :loading="capacityLoading">预测</el-button>
            </div>
          </template>
          <div ref="capacityChartRef" style="height: 400px"></div>
          <el-table :data="capacityData" v-loading="capacityLoading" stripe style="margin-top: 16px" size="small">
            <el-table-column prop="work_center_name" label="工作中心" min-width="180" />
            <el-table-column prop="active_orders" label="在制工单数" width="160" align="right" />
          </el-table>
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { getCostTrend, getDeliveryRisk, getCapacityLoad } from '@/api/reports'
import { useBatchOperation } from '@/composables/useBatchOperation'
import * as echarts from 'echarts'

const { selectedRows, handleSelectionChange, batchExport } = useBatchOperation('/api/reports/')


const activeTab = ref('cost')
const costLoading = ref(false)
const deliveryLoading = ref(false)
const capacityLoading = ref(false)

const costTrends = ref<any[]>([])
const costChartRef = ref(null)
const deliveryRisks = ref<any[]>([])
const capacityData = ref<any[]>([])
const capacityChartRef = ref(null)

const formatMoney = (v) => v ? Number(v).toLocaleString('zh-CN', { minimumFractionDigits: 2 }) : '0.00'
const formatMonth = (m) => (m ? String(m).substring(0, 7) : '')
const riskLevelType = (l) => ({ low: 'success', medium: 'warning', high: 'danger', critical: 'danger' }[l] || 'info')
const riskLevelLabel = (l) => ({ low: '低', medium: '中', high: '高', critical: '严重' }[l] || l)

const renderCostChart = () => {
  if (!costChartRef.value || !costTrends.value.length) return
  const chart = echarts.init(costChartRef.value)
  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['预算合计', '项目数'] },
    xAxis: { type: 'category', data: costTrends.value.map(d => formatMonth(d.month)) },
    yAxis: [
      { type: 'value', name: '预算' },
      { type: 'value', name: '项目数' }
    ],
    series: [
      { name: '预算合计', type: 'line', smooth: true, data: costTrends.value.map(d => d.total_budget || 0) },
      { name: '项目数', type: 'bar', yAxisIndex: 1, data: costTrends.value.map(d => d.count || 0) }
    ]
  })
}

const renderCapacityChart = () => {
  if (!capacityChartRef.value || !capacityData.value.length) return
  const chart = echarts.init(capacityChartRef.value)
  chart.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    xAxis: { type: 'category', data: capacityData.value.map(d => d.work_center_name), axisLabel: { rotate: 30 } },
    yAxis: { type: 'value', name: '在制工单数' },
    series: [{ name: '在制工单数', type: 'bar', data: capacityData.value.map(d => d.active_orders || 0) }]
  })
}

const loadCostTrend = async () => {
  costLoading.value = true
  try {
    const res = await getCostTrend()
    costTrends.value = res.trends || []
    await nextTick()
    renderCostChart()
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
    const res = await getCapacityLoad()
    capacityData.value = res.capacity_load || res.results || (Array.isArray(res) ? res : [])
    await nextTick()
    renderCapacityChart()
  } finally { capacityLoading.value = false }
}

onMounted(() => {
  loadCostTrend()
  loadDeliveryRisk()
  loadCapacityLoad()
})
</script>

<style scoped>
.predictive-analysis { padding: 0; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
</style>
