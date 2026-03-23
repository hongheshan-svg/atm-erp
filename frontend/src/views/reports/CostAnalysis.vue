<template>
  <div class="cost-analysis">
    <!-- 项目选择器 -->
    <el-card class="filter-card">
      <el-form :inline="true">
        <el-form-item label="选择项目">
          <el-select 
            v-model="selectedProject" 
            filterable 
            clearable
            :loading="projectLoading"
            placeholder="选择项目"
            @change="fetchCostAnalysis"
            @visible-change="handleProjectSelectorVisibleChange"
            style="width: 300px"
          >
            <el-option
              v-for="p in projectOptions"
              :key="p.id"
              :label="`${p.code} - ${p.name}`"
              :value="p.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="人工成本单价">
          <el-input-number v-model="hourlyRate" :min="50" :max="500" :step="10" />
          <span style="margin-left: 8px">元/小时</span>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="fetchCostAnalysis" :disabled="!selectedProject">
            分析
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 成本概览 -->
    <template v-if="costData">
      <el-row :gutter="16" style="margin-top: 20px">
        <el-col :span="6">
          <el-card shadow="hover" class="summary-card">
            <div class="summary-value primary">¥{{ formatNumber(costData.cost_summary.total_cost) }}</div>
            <div class="summary-label">项目总成本</div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover" class="summary-card">
            <div class="summary-value success">¥{{ formatNumber(costData.profitability.contract_amount) }}</div>
            <div class="summary-label">合同金额</div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover" class="summary-card">
            <div class="summary-value" :class="costData.profitability.gross_profit >= 0 ? 'success' : 'danger'">
              ¥{{ formatNumber(costData.profitability.gross_profit) }}
            </div>
            <div class="summary-label">毛利</div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover" class="summary-card">
            <div class="summary-value" :class="costData.profitability.gross_margin >= 20 ? 'success' : 'warning'">
              {{ costData.profitability.gross_margin }}%
            </div>
            <div class="summary-label">毛利率</div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 成本构成图表 -->
      <el-row :gutter="16" style="margin-top: 20px">
        <el-col :span="12">
          <el-card>
            <template #header>成本构成分析</template>
            <div ref="pieChart" style="height: 350px"></div>
          </el-card>
        </el-col>
        <el-col :span="12">
          <el-card>
            <template #header>成本明细</template>
            <el-descriptions :column="1" border size="large">
              <el-descriptions-item label="采购成本">
                <span class="cost-value">¥{{ formatNumber(costData.cost_summary.purchase_cost) }}</span>
              </el-descriptions-item>
              <el-descriptions-item label="外协成本">
                <span class="cost-value">¥{{ formatNumber(costData.cost_summary.outsource_cost) }}</span>
              </el-descriptions-item>
              <el-descriptions-item label="人工成本">
                <span class="cost-value">
                  ¥{{ formatNumber(costData.cost_summary.labor_cost) }}
                  <el-text type="info" size="small">
                    ({{ costData.cost_summary.labor_hours }}h × ¥{{ costData.cost_summary.hourly_rate }})
                  </el-text>
                </span>
              </el-descriptions-item>
              <el-descriptions-item label="物料成本">
                <span class="cost-value">¥{{ formatNumber(costData.cost_summary.material_cost) }}</span>
              </el-descriptions-item>
            </el-descriptions>
          </el-card>
        </el-col>
      </el-row>

      <!-- 人工成本按任务分析 -->
      <el-card style="margin-top: 20px">
        <template #header>人工成本按任务分析 (Top 10)</template>
        <el-table :data="costData.labor_by_phase" stripe>
          <el-table-column prop="task__name" label="任务名称" min-width="200" show-overflow-tooltip>
            <template #default="{ row }">
              {{ row.task__name || '未分类' }}
            </template>
          </el-table-column>
          <el-table-column prop="hours" label="工时 (h)" width="120" align="right">
            <template #default="{ row }">{{ row.hours?.toFixed(1) }}</template>
          </el-table-column>
          <el-table-column prop="cost" label="人工成本" width="150" align="right">
            <template #default="{ row }">¥{{ formatNumber(row.cost) }}</template>
          </el-table-column>
          <el-table-column label="占比" width="200">
            <template #default="{ row }">
              <el-progress 
                :percentage="getLaborPercentage(row.hours)" 
                :stroke-width="12"
                :color="getProgressColor(getLaborPercentage(row.hours))"
              />
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </template>

    <!-- 多项目对比 -->
    <el-card style="margin-top: 20px">
      <template #header>
        <div class="card-header">
          <span>多项目成本对比</span>
          <el-button type="primary" size="small" @click="fetchComparison">刷新对比</el-button>
        </div>
      </template>
      <div ref="comparisonChart" style="height: 400px"></div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import request from '@/utils/request'
import { usePermissionStore } from '@/stores/permission'

const selectedProject = ref(null)
const hourlyRate = ref(100)
const projectOptions = ref([])
const projectLoading = ref(false)
const projectsLoaded = ref(false)
const costData = ref(null)
const comparisonData = ref([])
const permissionStore = usePermissionStore()

const pieChart = ref(null)
const comparisonChart = ref(null)
let pieChartInstance = null
let comparisonChartInstance = null

const taskTypeMap = {
  'DESIGN': '设计',
  'ASSEMBLY': '组装',
  'DEBUG': '调试',
  'INSTALL': '安装',
  'TRAINING': '培训',
  'MEETING': '会议',
  'OTHER': '其他'
}

const formatNumber = (num) => {
  return (num || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

const getTaskTypeName = (type) => taskTypeMap[type] || type || '未分类'

const loadProjects = async () => {
  if (projectsLoaded.value) {
    return true
  }

  projectLoading.value = true
  try {
    const res = await request.get('/projects/projects/', { params: { page_size: 500 } })
    projectOptions.value = res.results || res || []
    projectsLoaded.value = true
    return true
  } catch (e) {
    if (e?.response?.status !== 403) {
      console.error('加载项目列表失败:', e)
    }
    projectOptions.value = []
    return false
  } finally {
    projectLoading.value = false
  }
}

const ensureProjectsLoaded = async () => {
  if (!permissionStore.hasPermission('projects:list')) {
    projectOptions.value = []
    projectsLoaded.value = false
    return false
  }

  return loadProjects()
}

const handleProjectSelectorVisibleChange = async (visible) => {
  if (visible) {
    await ensureProjectsLoaded()
  }
}

const fetchCostAnalysis = async () => {
  if (!selectedProject.value) return
  
  try {
    const res = await request({
      url: '/reports/cost/analysis/',
      method: 'get',
      params: { project: selectedProject.value, hourly_rate: hourlyRate.value }
    })
    costData.value = res  // request.js already returns response.data
    nextTick(() => renderPieChart())
  } catch (error) {
    ElMessage.error('获取成本分析失败')
    console.error(error)
  }
}

const fetchComparison = async () => {
  try {
    const res = await request({
      url: '/reports/cost/comparison/',
      method: 'get'
    })
    comparisonData.value = res?.comparison || []  // request.js already returns response.data
    nextTick(() => renderComparisonChart())
  } catch (error) {
    console.error(error)
  }
}

const getLaborPercentage = (hours) => {
  const totalHours = costData.value?.cost_summary?.labor_hours || 1
  return Math.round((hours / totalHours) * 100)
}

const getProgressColor = (percentage) => {
  if (percentage > 50) return '#f56c6c'
  if (percentage > 30) return '#e6a23c'
  return '#67c23a'
}

const renderPieChart = () => {
  if (!pieChart.value || !costData.value) return
  
  if (!pieChartInstance) {
    pieChartInstance = echarts.init(pieChart.value)
  }
  
  const data = costData.value.cost_breakdown.filter(d => d.value > 0)
  
  pieChartInstance.setOption({
    tooltip: { 
      trigger: 'item',
      formatter: '{b}: ¥{c} ({d}%)'
    },
    legend: { orient: 'vertical', left: 'left' },
    series: [{
      type: 'pie',
      radius: ['45%', '75%'],
      avoidLabelOverlap: true,
      itemStyle: {
        borderRadius: 8,
        borderColor: '#fff',
        borderWidth: 2
      },
      label: { show: true, formatter: '{b}\n{d}%' },
      data: data.map((d, i) => ({
        name: d.name,
        value: d.value,
        itemStyle: { color: ['#5470c6', '#91cc75', '#fac858', '#ee6666'][i] }
      }))
    }]
  })
}

const renderComparisonChart = () => {
  if (!comparisonChart.value || !comparisonData.value.length) return
  
  if (!comparisonChartInstance) {
    comparisonChartInstance = echarts.init(comparisonChart.value)
  }
  
  const projects = comparisonData.value.map(d => d.project_name.substring(0, 10))
  const contractAmounts = comparisonData.value.map(d => d.contract_amount)
  const totalCosts = comparisonData.value.map(d => d.total_cost)
  const margins = comparisonData.value.map(d => d.gross_margin)
  
  comparisonChartInstance.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    legend: { data: ['合同金额', '总成本', '毛利率'] },
    xAxis: {
      type: 'category',
      data: projects,
      axisLabel: { rotate: 30 }
    },
    yAxis: [
      { type: 'value', name: '金额 (元)', position: 'left' },
      { type: 'value', name: '毛利率 (%)', position: 'right', min: 0, max: 100 }
    ],
    series: [
      { name: '合同金额', type: 'bar', data: contractAmounts, itemStyle: { color: '#67c23a' } },
      { name: '总成本', type: 'bar', data: totalCosts, itemStyle: { color: '#f56c6c' } },
      { name: '毛利率', type: 'line', yAxisIndex: 1, data: margins, itemStyle: { color: '#409eff' } }
    ]
  })
}

onMounted(() => {
  fetchComparison()
})
</script>

<style scoped>
.cost-analysis {
  padding: 20px;
}
.filter-card {
  margin-bottom: 10px;
}
.summary-card {
  text-align: center;
  padding: 20px;
}
.summary-value {
  font-size: 28px;
  font-weight: bold;
}
.summary-value.primary { color: #409eff; }
.summary-value.success { color: #67c23a; }
.summary-value.warning { color: #e6a23c; }
.summary-value.danger { color: #f56c6c; }
.summary-label {
  font-size: 14px;
  color: #909399;
  margin-top: 8px;
}
.cost-value {
  font-weight: bold;
  font-size: 16px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
