<template>
  <div class="project-profitability-report">
    <el-card>
      <template #header><span>项目盈利分析报表</span></template>
      
      <el-form :inline="true" class="filter-form">
        <el-form-item label="日期范围">
          <el-date-picker v-model="dateRange" type="daterange" start-placeholder="开始日期" end-placeholder="结束日期" @change="loadData" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadData">查询</el-button>
          <el-button @click="handleExport">导出</el-button>
        </el-form-item>
      </el-form>
      
      <div ref="chartRef" style="height: 400px;" class="chart-container"></div>
      
      <!-- 批量操作 -->
      
      <div v-if="selectedRows.length > 0" class="batch-toolbar">
      
        <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>
      
        <el-button size="small" @click="batchExport">导出选中</el-button>
      
      </div>
      
      <el-table :data="tableData" v-loading="loading" stripe show-summary @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="45" />
        <el-table-column prop="project_name" label="项目名称" />
        <el-table-column prop="contract_amount" label="合同金额" align="right">
          <template #default="{ row }">¥ {{ formatMoney(row.contract_amount) }}</template>
        </el-table-column>
        <el-table-column prop="total_cost" label="总成本" align="right">
          <template #default="{ row }">¥ {{ formatMoney(row.total_cost) }}</template>
        </el-table-column>
        <el-table-column prop="profit" label="利润" align="right">
          <template #default="{ row }">¥ {{ formatMoney(row.profit) }}</template>
        </el-table-column>
        <el-table-column prop="margin" label="利润率" align="right">
          <template #default="{ row }">{{ (row.margin * 100).toFixed(2) }}%</template>
        </el-table-column>
        <el-table-column prop="completion" label="完成度" width="100">
          <template #default="{ row }">{{ row.completion }}%</template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { getProjectProfitabilityReport, exportProjectProfitabilityReport } from '@/api/reports'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchExport } = useBatchOperation('/api/reports/')


const loading = ref(false)
const tableData = ref([])
const dateRange = ref([])
const chartRef = ref(null)

const formatMoney = (v) => v ? parseFloat(v).toLocaleString('zh-CN', { minimumFractionDigits: 2 }) : '0.00'

const loadData = async () => {
  loading.value = true
  try {
    const params = {}
    if (dateRange.value?.length) {
      params.start_date = dateRange.value[0]
      params.end_date = dateRange.value[1]
    }
    const res = await getProjectProfitabilityReport(params)
    tableData.value = res.data?.projects || res.projects || []
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
    legend: { data: ['合同金额', '总成本', '利润'] },
    xAxis: { type: 'category', data: tableData.value.map(d => d.project_name), axisLabel: { rotate: 45 } },
    yAxis: { type: 'value' },
    series: [
      { name: '合同金额', type: 'bar', data: tableData.value.map(d => d.contract_amount) },
      { name: '总成本', type: 'bar', data: tableData.value.map(d => d.total_cost) },
      { name: '利润', type: 'bar', data: tableData.value.map(d => d.profit) }
    ]
  })
}

const handleExport = async () => {
  try {
    const res = await exportProjectProfitabilityReport()
    const url = window.URL.createObjectURL(new Blob([res.data || res]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', '项目利润率报表.xlsx')
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch (error) {
    ElMessage.error('导出失败')
  }
}

onMounted(() => loadData())
</script>

<style scoped>
.filter-form { margin-bottom: 20px; }
.chart-container { margin-bottom: 20px; }
</style>
