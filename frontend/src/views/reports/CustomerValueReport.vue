<template>
  <div class="customer-value-report">
    <el-card>
      <template #header><span>客户价值分析报表</span></template>
      
      <el-form :inline="true" class="filter-form">
        <el-form-item label="统计年度">
          <el-select v-model="year" @change="loadData" style="width: 140px;">
            <el-option v-for="y in yearOptions" :key="y" :label="`${y}年`" :value="y" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadData">查询</el-button>
        </el-form-item>
      </el-form>
      
      <div ref="chartRef" style="height: 400px;" class="chart-container"></div>
      
      <!-- 批量操作 -->
      
      <div v-if="selectedRows.length > 0" class="batch-toolbar">
      
        <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>
      
        <el-button size="small" @click="batchExport">导出选中</el-button>
      
      </div>
      
      <el-table :data="tableData" v-loading="loading" stripe @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="45" />
        <el-table-column prop="customer_name" label="客户名称" min-width="160" />
        <el-table-column prop="project_count" label="项目数" width="90" align="right" />
        <el-table-column prop="project_amount" label="项目金额" align="right">
          <template #default="{ row }">¥ {{ formatMoney(row.project_amount) }}</template>
        </el-table-column>
        <el-table-column prop="order_count" label="订单数" width="90" align="right" />
        <el-table-column prop="order_amount" label="订单金额" align="right">
          <template #default="{ row }">¥ {{ formatMoney(row.order_amount) }}</template>
        </el-table-column>
        <el-table-column prop="total_revenue" label="总收入" align="right">
          <template #default="{ row }">¥ {{ formatMoney(row.total_revenue) }}</template>
        </el-table-column>
        <el-table-column prop="service_count" label="服务次数" width="90" align="right" />
        <el-table-column prop="service_cost" label="服务成本" align="right">
          <template #default="{ row }">¥ {{ formatMoney(row.service_cost) }}</template>
        </el-table-column>
        <el-table-column prop="tier" label="客户等级" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getGradeType(row.tier)">{{ row.tier }}</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { getCustomerValueReport } from '@/api/reports'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { useBatchOperation } from '@/composables/useBatchOperation'

const { selectedRows, handleSelectionChange, batchExport } = useBatchOperation('/api/reports/')


const loading = ref(false)
const tableData = ref<any[]>([])
const currentYear = new Date().getFullYear()
const year = ref(currentYear)
const yearOptions = Array.from({ length: 5 }, (_, i) => currentYear - i)
const chartRef = ref(null)

const formatMoney = (v) => v ? parseFloat(v).toLocaleString('zh-CN', { minimumFractionDigits: 2 }) : '0.00'
const getGradeType = (g) => ({ 'A': 'success', 'B': 'primary', 'C': 'warning', 'D': 'info' }[g] || 'info')

const loadData = async () => {
  loading.value = true
  try {
    const res = await getCustomerValueReport({ year: year.value })
    tableData.value = res.customers || []
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
  const top10 = tableData.value.slice(0, 10)
  chart.setOption({
    tooltip: { trigger: 'item' },
    series: [{
      name: '客户总收入',
      type: 'pie',
      radius: ['40%', '70%'],
      data: top10.map(d => ({ name: d.customer_name, value: d.total_revenue }))
    }]
  })
}

onMounted(() => loadData())
</script>

<style scoped>
.filter-form { margin-bottom: 20px; }
.chart-container { margin-bottom: 20px; }
</style>
