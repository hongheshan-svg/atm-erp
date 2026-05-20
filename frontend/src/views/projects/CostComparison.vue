<template>
  <div class="cost-comparison">
    <el-card>
      <template #header><span>项目成本对比</span></template>
      
      <el-form :inline="true" class="filter-form">
        <el-form-item label="选择项目">
          <el-select v-model="selectedProjects" multiple placeholder="选择多个项目进行对比" style="width: 400px">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadComparison">对比</el-button>
        </el-form-item>
      </el-form>
      
      <div v-if="comparisonData.length" class="comparison-chart" ref="chartRef" style="height: 400px;"></div>
      
      <el-table :data="comparisonData" v-loading="loading" stripe>
        <el-table-column prop="project_name" label="项目" />
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
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getProjectList, getProjectCostComparison } from '@/api/projects/project'
import * as echarts from 'echarts'

const loading = ref(false)
const projects = ref([])
const selectedProjects = ref([])
const comparisonData = ref([])
const chartRef = ref(null)

const formatMoney = (v) => v ? parseFloat(v).toLocaleString('zh-CN', { minimumFractionDigits: 2 }) : '0.00'

const loadProjects = async () => {
  try {
    const res = await getProjectList({ page_size: 1000 })
    projects.value = res.data?.results || res.results || []
  } catch (error) {
    console.error('CostComparison getProjectList error:', error)
  }
}

const loadComparison = async () => {
  if (selectedProjects.value.length < 2) {
    ElMessage.warning('请至少选择2个项目进行对比')
    return
  }
  loading.value = true
  try {
    const res = await getProjectCostComparison({ project_ids: selectedProjects.value.join(',') })
    comparisonData.value = res.data?.projects || res.projects || []
    renderChart()
  } catch (error) {
    ElMessage.error('加载对比数据失败')
  } finally {
    loading.value = false
  }
}

const renderChart = () => {
  if (!chartRef.value || !comparisonData.value.length) return
  const chart = echarts.init(chartRef.value)
  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['合同金额', '总成本', '利润'] },
    xAxis: { type: 'category', data: comparisonData.value.map(d => d.project_name) },
    yAxis: { type: 'value' },
    series: [
      { name: '合同金额', type: 'bar', data: comparisonData.value.map(d => d.contract_amount) },
      { name: '总成本', type: 'bar', data: comparisonData.value.map(d => d.total_cost) },
      { name: '利润', type: 'bar', data: comparisonData.value.map(d => d.profit) }
    ]
  })
}

onMounted(() => loadProjects())
</script>

<style scoped>
.filter-form { margin-bottom: 20px; }
.comparison-chart { margin-bottom: 20px; }
</style>
