<template>
  <div class="oee-analysis">
    <el-card class="header-card">
      <div class="header-content">
        <h2>设备OEE分析</h2>
        <div class="header-filters">
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            style="width: 280px"
            @change="loadData"
          />
          <el-select v-model="selectedEquipment" placeholder="选择设备" clearable style="width: 200px" @change="loadData">
            <el-option v-for="e in equipments" :key="e.id" :label="e.name" :value="e.id" />
          </el-select>
        </div>
      </div>
    </el-card>

    <!-- OEE概览 -->
    <el-row :gutter="16" class="oee-overview">
      <el-col :span="6">
        <el-card class="oee-card">
          <div class="oee-gauge">
            <div class="oee-value" :style="{ color: getOEEColor(oeeData.oee) }">
              {{ (oeeData.oee * 100).toFixed(1) }}%
            </div>
            <div class="oee-label">综合OEE</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="factor-card">
          <div class="factor-header">
            <span>可用率</span>
            <strong>{{ (oeeData.availability * 100).toFixed(1) }}%</strong>
          </div>
          <el-progress :percentage="oeeData.availability * 100" :color="getFactorColor(oeeData.availability)" :stroke-width="10" />
          <div class="factor-detail">
            计划时间: {{ oeeData.planned_time }}h | 实际运行: {{ oeeData.actual_running_time }}h
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="factor-card">
          <div class="factor-header">
            <span>性能率</span>
            <strong>{{ (oeeData.performance * 100).toFixed(1) }}%</strong>
          </div>
          <el-progress :percentage="oeeData.performance * 100" :color="getFactorColor(oeeData.performance)" :stroke-width="10" />
          <div class="factor-detail">
            理想产量: {{ oeeData.ideal_output }} | 实际产量: {{ oeeData.actual_output }}
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="factor-card">
          <div class="factor-header">
            <span>质量率</span>
            <strong>{{ (oeeData.quality * 100).toFixed(1) }}%</strong>
          </div>
          <el-progress :percentage="oeeData.quality * 100" :color="getFactorColor(oeeData.quality)" :stroke-width="10" />
          <div class="factor-detail">
            总产量: {{ oeeData.total_output }} | 合格数: {{ oeeData.good_output }}
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <!-- OEE趋势 -->
      <el-col :span="16">
        <el-card>
          <template #header>OEE趋势</template>
          <div ref="trendChart" style="height: 350px;"></div>
        </el-card>
      </el-col>

      <!-- 停机原因分析 -->
      <el-col :span="8">
        <el-card>
          <template #header>停机原因分析</template>
          <div ref="downtimeChart" style="height: 350px;"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 设备OEE排名 -->
    <el-card style="margin-top: 16px;">
      <template #header>设备OEE排名</template>
      <!-- 批量操作 -->
      <div v-if="selectedRows.length > 0" class="batch-toolbar">
        <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>
        <el-button type="danger" size="small" @click="batchDelete">批量删除</el-button>
        <el-button size="small" @click="batchExport">导出选中</el-button>
      </div>
      <el-table :data="equipmentRanking" stripe @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="45" />
        <el-table-column prop="rank" label="排名" width="70" align="center">
          <template #default="{ $index }">
            <el-tag v-if="$index < 3" :type="$index === 0 ? 'danger' : ($index === 1 ? 'warning' : 'info')" size="small">
              {{ $index + 1 }}
            </el-tag>
            <span v-else>{{ $index + 1 }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="equipment_name" label="设备名称" />
        <el-table-column prop="oee" label="OEE" width="150">
          <template #default="{ row }">
            <el-progress :percentage="row.oee * 100" :color="getOEEColor(row.oee)" />
          </template>
        </el-table-column>
        <el-table-column prop="availability" label="可用率" width="100" align="center">
          <template #default="{ row }">
            {{ (row.availability * 100).toFixed(1) }}%
          </template>
        </el-table-column>
        <el-table-column prop="performance" label="性能率" width="100" align="center">
          <template #default="{ row }">
            {{ (row.performance * 100).toFixed(1) }}%
          </template>
        </el-table-column>
        <el-table-column prop="quality" label="质量率" width="100" align="center">
          <template #default="{ row }">
            {{ (row.quality * 100).toFixed(1) }}%
          </template>
        </el-table-column>
        <el-table-column prop="total_downtime" label="停机时长" width="100" align="center">
          <template #default="{ row }">
            {{ row.total_downtime }}h
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import {
getEquipmentList, getOEESummary, getOEERanking, getOEETrend, getOEEDowntime
} from '@/api/equipment'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchDelete, batchExport } = useBatchOperation('/api/equipment/')


const dateRange = ref<any[]>([])
const selectedEquipment = ref(null)
const equipments = ref<any[]>([])
const oeeData = ref({
  oee: 0, availability: 0, performance: 0, quality: 0,
  planned_time: 0, actual_running_time: 0,
  ideal_output: 0, actual_output: 0,
  total_output: 0, good_output: 0
})
const equipmentRanking = ref<any[]>([])
const trendData = ref<any[]>([])
const downtimeData = ref<any[]>([])

const trendChart = ref(null)
const downtimeChart = ref(null)
let trendChartInstance = null
let downtimeChartInstance = null

const formatDateParam = (d) => {
  if (!d) return ''
  const dt = new Date(d)
  return `${dt.getFullYear()}-${String(dt.getMonth()+1).padStart(2,'0')}-${String(dt.getDate()).padStart(2,'0')}`
}

const buildParams = () => {
  const params = {}
  if (selectedEquipment.value) params.equipment_id = selectedEquipment.value
  if (dateRange.value && dateRange.value.length === 2) {
    params.start_date = formatDateParam(dateRange.value[0])
    params.end_date = formatDateParam(dateRange.value[1])
  }
  return params
}

const loadEquipments = async () => {
  try {
    const res = await getEquipmentList({ page_size: 1000 })
    equipments.value = res.results || res.results || res || []
  } catch (error) {
    console.error('OEEAnalysis getEquipmentList error:', error)
  }
}

const loadOEESummary = async () => {
  try {
    const res = await getOEESummary(buildParams())
    const d = res
    oeeData.value = {
      oee: d.oee || 0,
      availability: d.availability || 0,
      performance: d.performance || 0,
      quality: d.quality || 0,
      planned_time: d.planned_time || 0,
      actual_running_time: d.actual_running_time || 0,
      ideal_output: d.ideal_output || 0,
      actual_output: d.actual_output || 0,
      total_output: d.total_output || 0,
      good_output: d.good_output || 0
    }
  } catch (error) {
    console.error(error)
    // If API not available, keep zeros
  }
}

const loadRanking = async () => {
  try {
    const res = await getOEERanking(buildParams())
    equipmentRanking.value = res.ranking || res.results || (Array.isArray(res) ? res : [])
  } catch (error) {
    console.error(error)
    equipmentRanking.value = []
  }
}

const loadTrendData = async () => {
  try {
    const res = await getOEETrend(buildParams())
    trendData.value = res.trend || (Array.isArray(res) ? res : [])
  } catch (error) {
    console.error(error)
    trendData.value = []
  }
}

const loadDowntimeData = async () => {
  try {
    const res = await getOEEDowntime(buildParams())
    downtimeData.value = res.reasons || (Array.isArray(res) ? res : [])
  } catch (error) {
    console.error(error)
    downtimeData.value = []
  }
}

const initCharts = () => {
  // OEE趋势图
  if (trendChart.value) {
    trendChartInstance = echarts.init(trendChart.value)
    const days = trendData.value.map(t => t.date || t.day || '')
    trendChartInstance.setOption({
      tooltip: { trigger: 'axis' },
      legend: { data: ['OEE', '可用率', '性能率', '质量率'] },
      grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
      xAxis: { type: 'category', data: days },
      yAxis: { type: 'value', min: 0, max: 100, axisLabel: { formatter: '{value}%' } },
      series: [
        { name: 'OEE', type: 'line', data: trendData.value.map(t => ((t.oee || 0) * 100).toFixed(1)), smooth: true, lineStyle: { width: 3 } },
        { name: '可用率', type: 'line', data: trendData.value.map(t => ((t.availability || 0) * 100).toFixed(1)), smooth: true },
        { name: '性能率', type: 'line', data: trendData.value.map(t => ((t.performance || 0) * 100).toFixed(1)), smooth: true },
        { name: '质量率', type: 'line', data: trendData.value.map(t => ((t.quality || 0) * 100).toFixed(1)), smooth: true }
      ]
    })
  }

  // 停机原因图
  if (downtimeChart.value) {
    downtimeChartInstance = echarts.init(downtimeChart.value)
    const pieData = downtimeData.value.map(d => ({
      value: d.duration || d.value || 0,
      name: d.reason || d.name || '未知'
    }))
    downtimeChartInstance.setOption({
      tooltip: { trigger: 'item' },
      series: [{
        type: 'pie',
        radius: ['40%', '70%'],
        avoidLabelOverlap: false,
        itemStyle: { borderRadius: 10, borderColor: '#fff', borderWidth: 2 },
        label: { show: true, formatter: '{b}: {d}%' },
        data: pieData.length ? pieData : [{ value: 0, name: '暂无数据' }]
      }]
    })
  }
}

const loadData = async () => {
  await loadEquipments()
  try {
    await Promise.all([loadOEESummary(), loadRanking(), loadTrendData(), loadDowntimeData()])
  } catch (error) {
    console.error('加载数据失败', error)
    ElMessage.error('加载数据失败')
  }
  await nextTick()
  initCharts()
}

const getOEEColor = (value) => {
  if (value >= 0.85) return '#67C23A'
  if (value >= 0.70) return '#E6A23C'
  return '#F56C6C'
}

const getFactorColor = (value) => {
  if (value >= 0.90) return '#67C23A'
  if (value >= 0.80) return '#E6A23C'
  return '#F56C6C'
}

onMounted(() => {
  const end = new Date()
  const start = new Date()
  start.setDate(start.getDate() - 7)
  dateRange.value = [start, end]
  loadData()
})

watch([dateRange, selectedEquipment], () => {
  if (trendChartInstance) { trendChartInstance.dispose(); trendChartInstance = null }
  if (downtimeChartInstance) { downtimeChartInstance.dispose(); downtimeChartInstance = null }
  loadData()
})
</script>

<style scoped>
.oee-analysis { padding: 0; }
.header-card { margin-bottom: 16px; }
.header-content { display: flex; justify-content: space-between; align-items: center; }
.header-content h2 { margin: 0; }
.header-filters { display: flex; gap: 12px; }
.oee-overview { margin-bottom: 16px; }
.oee-card { text-align: center; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: #fff; }
.oee-gauge { padding: 20px; }
.oee-value { font-size: 48px; font-weight: bold; }
.oee-label { font-size: 14px; opacity: 0.9; }
.factor-card { padding: 8px; }
.factor-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.factor-header strong { font-size: 20px; }
.factor-detail { margin-top: 8px; font-size: 12px; color: #909399; }
</style>
