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
      <el-table :data="equipmentRanking" stripe>
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

<script setup>
import { ref, reactive, onMounted, watch } from 'vue'
import * as echarts from 'echarts'
import request from '@/utils/request'

const dateRange = ref([])
const selectedEquipment = ref(null)
const equipments = ref([])
const oeeData = ref({
  oee: 0.85,
  availability: 0.92,
  performance: 0.95,
  quality: 0.98,
  planned_time: 480,
  actual_running_time: 442,
  ideal_output: 1000,
  actual_output: 950,
  total_output: 950,
  good_output: 931
})
const equipmentRanking = ref([])

const trendChart = ref(null)
const downtimeChart = ref(null)
let trendChartInstance = null
let downtimeChartInstance = null

const loadData = async () => {
  try {
    // 加载设备列表
    const equipRes = await request.get('/projects/equipment/')
    equipments.value = equipRes.results || equipRes || []
    
    // TODO: 加载OEE数据
    // 使用模拟数据
    initCharts()
    loadRanking()
  } catch (error) {
    console.error(error)
  }
}

const loadRanking = () => {
  // 模拟数据
  equipmentRanking.value = [
    { equipment_name: 'CNC加工中心-01', oee: 0.92, availability: 0.95, performance: 0.98, quality: 0.99, total_downtime: 4 },
    { equipment_name: '激光切割机-02', oee: 0.88, availability: 0.92, performance: 0.96, quality: 0.99, total_downtime: 6.5 },
    { equipment_name: '焊接机器人-01', oee: 0.85, availability: 0.90, performance: 0.95, quality: 0.99, total_downtime: 8 },
    { equipment_name: '装配线-A', oee: 0.82, availability: 0.88, performance: 0.94, quality: 0.99, total_downtime: 9.6 },
    { equipment_name: 'CNC加工中心-02', oee: 0.78, availability: 0.85, performance: 0.92, quality: 0.99, total_downtime: 12 }
  ]
}

const initCharts = () => {
  // OEE趋势图
  if (trendChart.value) {
    trendChartInstance = echarts.init(trendChart.value)
    const days = []
    const oeeValues = []
    const availabilityValues = []
    const performanceValues = []
    const qualityValues = []
    
    for (let i = 6; i >= 0; i--) {
      const d = new Date()
      d.setDate(d.getDate() - i)
      days.push(`${d.getMonth() + 1}/${d.getDate()}`)
      oeeValues.push((85 + Math.random() * 10).toFixed(1))
      availabilityValues.push((90 + Math.random() * 8).toFixed(1))
      performanceValues.push((92 + Math.random() * 6).toFixed(1))
      qualityValues.push((97 + Math.random() * 3).toFixed(1))
    }
    
    trendChartInstance.setOption({
      tooltip: { trigger: 'axis' },
      legend: { data: ['OEE', '可用率', '性能率', '质量率'] },
      grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
      xAxis: { type: 'category', data: days },
      yAxis: { type: 'value', min: 70, max: 100, axisLabel: { formatter: '{value}%' } },
      series: [
        { name: 'OEE', type: 'line', data: oeeValues, smooth: true, lineStyle: { width: 3 } },
        { name: '可用率', type: 'line', data: availabilityValues, smooth: true },
        { name: '性能率', type: 'line', data: performanceValues, smooth: true },
        { name: '质量率', type: 'line', data: qualityValues, smooth: true }
      ]
    })
  }
  
  // 停机原因图
  if (downtimeChart.value) {
    downtimeChartInstance = echarts.init(downtimeChart.value)
    downtimeChartInstance.setOption({
      tooltip: { trigger: 'item' },
      series: [{
        type: 'pie',
        radius: ['40%', '70%'],
        avoidLabelOverlap: false,
        itemStyle: { borderRadius: 10, borderColor: '#fff', borderWidth: 2 },
        label: { show: true, formatter: '{b}: {d}%' },
        data: [
          { value: 35, name: '计划停机', itemStyle: { color: '#909399' } },
          { value: 25, name: '设备故障', itemStyle: { color: '#F56C6C' } },
          { value: 20, name: '换模换型', itemStyle: { color: '#E6A23C' } },
          { value: 12, name: '缺料等待', itemStyle: { color: '#409EFF' } },
          { value: 8, name: '其他', itemStyle: { color: '#67C23A' } }
        ]
      }]
    })
  }
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
  if (trendChartInstance) trendChartInstance.dispose()
  if (downtimeChartInstance) downtimeChartInstance.dispose()
  loadData()
})
</script>

<style scoped>
.oee-analysis {
  padding: 0;
}

.header-card {
  margin-bottom: 16px;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-content h2 {
  margin: 0;
}

.header-filters {
  display: flex;
  gap: 12px;
}

.oee-overview {
  margin-bottom: 16px;
}

.oee-card {
  text-align: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
}

.oee-gauge {
  padding: 20px;
}

.oee-value {
  font-size: 48px;
  font-weight: bold;
}

.oee-label {
  font-size: 14px;
  opacity: 0.9;
}

.factor-card {
  padding: 8px;
}

.factor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.factor-header strong {
  font-size: 20px;
}

.factor-detail {
  margin-top: 8px;
  font-size: 12px;
  color: #909399;
}
</style>
