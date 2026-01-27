<template>
  <div class="capacity-utilization-report">
    <el-card>
      <template #header><span>产能利用率报表</span></template>
      
      <el-form :inline="true" class="filter-form">
        <el-form-item label="日期范围">
          <el-date-picker v-model="dateRange" type="daterange" start-placeholder="开始" end-placeholder="结束" @change="loadData" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadData">查询</el-button>
        </el-form-item>
      </el-form>
      
      <div ref="chartRef" style="height: 400px;" class="chart-container"></div>
      
      <el-table :data="tableData" v-loading="loading" stripe>
        <el-table-column prop="work_center_name" label="工作中心" />
        <el-table-column prop="available_hours" label="可用工时" align="right" />
        <el-table-column prop="planned_hours" label="计划工时" align="right" />
        <el-table-column prop="actual_hours" label="实际工时" align="right" />
        <el-table-column prop="utilization_rate" label="利用率" width="150">
          <template #default="{ row }">
            <el-progress :percentage="row.utilization_rate" :status="row.utilization_rate >= 80 ? 'success' : row.utilization_rate >= 50 ? '' : 'warning'" />
          </template>
        </el-table-column>
        <el-table-column prop="efficiency" label="效率" width="100">
          <template #default="{ row }">{{ row.efficiency }}%</template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import request from '@/utils/request'
import * as echarts from 'echarts'

const loading = ref(false)
const tableData = ref([])
const dateRange = ref([])
const chartRef = ref(null)

const loadData = async () => {
  loading.value = true
  try {
    const params = {}
    if (dateRange.value?.length) {
      params.start_date = dateRange.value[0]
      params.end_date = dateRange.value[1]
    }
    const res = await request.get('/reports/industry/capacity-utilization/', { params })
    tableData.value = res.data?.work_centers || res.work_centers || []
    await nextTick()
    renderChart()
  } catch (error) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

const renderChart = () => {
  if (!chartRef.value || !tableData.value.length) return
  const chart = echarts.init(chartRef.value)
  chart.setOption({
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: tableData.value.map(d => d.work_center_name) },
    yAxis: { type: 'value', max: 100 },
    series: [{ name: '利用率', type: 'bar', data: tableData.value.map(d => d.utilization_rate), itemStyle: { color: '#409eff' } }]
  })
}

onMounted(() => loadData())
</script>

<style scoped>
.filter-form { margin-bottom: 20px; }
.chart-container { margin-bottom: 20px; }
</style>
