<template>
  <div class="customer-value-report">
    <el-card>
      <template #header><span>客户价值分析报表</span></template>
      
      <el-form :inline="true" class="filter-form">
        <el-form-item label="时间范围">
          <el-select v-model="period" @change="loadData">
            <el-option label="近一年" value="1year" />
            <el-option label="近三年" value="3years" />
            <el-option label="全部" value="all" />
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
        <el-table-column prop="customer_name" label="客户名称" />
        <el-table-column prop="project_count" label="项目数" width="100" align="right" />
        <el-table-column prop="total_contract_value" label="合同总额" align="right">
          <template #default="{ row }">¥ {{ formatMoney(row.total_contract_value) }}</template>
        </el-table-column>
        <el-table-column prop="total_profit" label="贡献利润" align="right">
          <template #default="{ row }">¥ {{ formatMoney(row.total_profit) }}</template>
        </el-table-column>
        <el-table-column prop="avg_margin" label="平均利润率" width="120">
          <template #default="{ row }">{{ (row.avg_margin * 100).toFixed(2) }}%</template>
        </el-table-column>
        <el-table-column prop="customer_grade" label="客户等级" width="100">
          <template #default="{ row }">
            <el-tag :type="getGradeType(row.customer_grade)">{{ row.customer_grade }}</el-tag>
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
const period = ref('1year')
const chartRef = ref(null)

const formatMoney = (v) => v ? parseFloat(v).toLocaleString('zh-CN', { minimumFractionDigits: 2 }) : '0.00'
const getGradeType = (g) => ({ 'A': 'success', 'B': 'primary', 'C': 'warning', 'D': 'info' }[g] || 'info')

const loadData = async () => {
  loading.value = true
  try {
    const res = await getCustomerValueReport({ period: period.value })
    tableData.value = res.customers || res.customers || []
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
      name: '客户合同额',
      type: 'pie',
      radius: ['40%', '70%'],
      data: top10.map(d => ({ name: d.customer_name, value: d.total_contract_value }))
    }]
  })
}

onMounted(() => loadData())
</script>

<style scoped>
.filter-form { margin-bottom: 20px; }
.chart-container { margin-bottom: 20px; }
</style>
